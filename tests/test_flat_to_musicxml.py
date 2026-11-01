"""Functional tests for flat_to_musicxml.py."""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from flat_to_musicxml import build_tree, fetch_score_json, parse_flat_url, to_musicxml_string

# End-to-end test score created in the Flat.io account for this test suite.
E2E_SCORE_ID = "6ae7138294c474c776026ec6"
E2E_SHARING_KEY = ""

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


# ── URL parsing ───────────────────────────────────────────────────────────────

def test_parse_flat_url_extracts_id_and_key():
    url = (
        "https://flat.io/score/000000000000000000000000-viva-la-vida"
        "?sharingKey=abc123def456"
    )
    score_id, sharing_key = parse_flat_url(url)
    assert score_id == "000000000000000000000000"
    assert sharing_key == "abc123def456"


def test_parse_flat_url_no_sharing_key():
    url = "https://flat.io/score/000000000000000000000000-title"
    score_id, sharing_key = parse_flat_url(url)
    assert score_id == "000000000000000000000000"
    assert sharing_key == ""


# ── Conversion correctness ────────────────────────────────────────────────────

def test_attributes_before_notes_in_measure():
    """<attributes> must appear before <note> in every measure."""
    root = build_tree(load("minimal.json"))
    for measure in root.iter('measure'):
        tags = [c.tag for c in measure]
        if 'attributes' in tags and 'note' in tags:
            assert tags.index('attributes') < tags.index('note')


def test_beam_text_content_not_child_element():
    """beam value must be text ('begin'/'end'), not a <content> child element."""
    root = build_tree(load("beam.json"))
    beams = root.findall('.//beam')
    assert beams
    for beam in beams:
        assert beam.text in ('begin', 'end', 'continue')
        assert list(beam) == []


def test_adagio_keys_stripped():
    """$adagio-* keys from Flat.io must not appear anywhere in the XML output."""
    xml_str = to_musicxml_string(build_tree(load("adagio_attrs.json")))
    assert 'adagio' not in xml_str.lower()


def test_output_is_valid_xml_with_doctype():
    xml_str = to_musicxml_string(build_tree(load("minimal.json")))
    assert '<!DOCTYPE score-partwise' in xml_str
    assert 'MusicXML' in xml_str
    # Strip DOCTYPE line (ET can't parse it) then check well-formedness
    clean = '\n'.join(l for l in xml_str.splitlines() if not l.startswith('<!DOCTYPE'))
    ET.fromstring(clean)


def test_version_attribute():
    assert build_tree(load("minimal.json")).get('version') == '4.0'


def test_work_title_preserved():
    assert build_tree(load("minimal.json")).findtext('.//work-title') == 'Test'


# ── End-to-end: live Flat.io API ─────────────────────────────────────────────

@pytest.mark.network
def test_e2e_real_account_score():
    """Fetch 'flat2musicxml test score' (string quartet) from the real Flat.io API
    and verify the full pipeline produces valid 4-part MusicXML."""
    data = fetch_score_json(E2E_SCORE_ID, E2E_SHARING_KEY)
    root = build_tree(data)

    parts = root.findall('.//part')
    assert len(parts) == 4, f"Expected 4 parts (Vln1, Vln2, Vla, Vc), got {len(parts)}"

    part_names = [p.findtext('part-name') or '' for p in root.findall('.//score-part')]
    assert any('violin' in n.lower() for n in part_names), f"No Violin found: {part_names}"
    assert any('viola' in n.lower() for n in part_names), f"No Viola found: {part_names}"
    assert any('cello' in n.lower() for n in part_names), f"No Cello found: {part_names}"

    xml_str = to_musicxml_string(root)
    assert '<!DOCTYPE score-partwise' in xml_str
    assert 'adagio' not in xml_str.lower()

    clean = '\n'.join(l for l in xml_str.splitlines() if not l.startswith('<!DOCTYPE'))
    ET.fromstring(clean)

    for measure in root.iter('measure'):
        tags = [c.tag for c in measure]
        if 'attributes' in tags and 'note' in tags:
            assert tags.index('attributes') < tags.index('note')


# ── Real score excerpt ────────────────────────────────────────────────────────

def test_real_score_excerpt_viva_la_vida():
    """Convert the first 2 measures of the real Viva La Vida score."""
    root = build_tree(load("viva_la_vida_excerpt.json"))

    parts = root.findall('.//part')
    assert len(parts) == 2, "Expected Violin 1 and Violin 2"

    for part in parts:
        measures = part.findall('measure')
        assert len(measures) == 2
        for measure in measures:
            tags = [c.tag for c in measure]
            if 'attributes' in tags and 'note' in tags:
                assert tags.index('attributes') < tags.index('note')

    xml_str = to_musicxml_string(root)
    assert 'adagio' not in xml_str.lower()
    assert '<!DOCTYPE score-partwise' in xml_str
