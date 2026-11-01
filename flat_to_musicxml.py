#!/usr/bin/env python3
"""
Download a Flat.io score and save it as MusicXML.

Usage:
  flat_to_musicxml.py <flat-url> [output.musicxml]
  flat_to_musicxml.py <score-id> <sharing-key> [output.musicxml]

Examples:
  python3 flat_to_musicxml.py "https://flat.io/score/000000000000000000000000-viva-la-vida?sharingKey=abc..."
  python3 flat_to_musicxml.py 000000000000000000000000 abc123 my-score.musicxml

Requires only the Python standard library.
"""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

FLAT_API = "https://api.flat.io/v2"

# Keys in Flat.io JSON that have no MusicXML equivalent
_SKIP_KEYS = {'uuid', 'voiceMapping', 'staffMapping',
              'voiceIdxToUuidMapping', 'voiceUuidToIdxMapping'}
_SKIP_PREFIXES = ('$adagio-',)

# Required child-element order within a MusicXML <measure>
_MEASURE_CHILD_ORDER = ['print', 'attributes', 'direction', 'harmony',
                        'note', 'backup', 'forward', 'barline', 'sound', 'grouping']

# Required child-element order within <score-partwise>
_SCORE_CHILD_ORDER = ['work', 'identification', 'defaults', 'credit', 'part-list', 'part']


# ── JSON → XML conversion ─────────────────────────────────────────────────────

def _should_skip(key: str) -> bool:
    if key in _SKIP_KEYS:
        return True
    return any(key.startswith(p) for p in _SKIP_PREFIXES)


def _json_to_xml(parent: ET.Element, key: str, value) -> None:
    """Recursively convert a Flat.io JSON node to XML children of `parent`."""
    if _should_skip(key):
        return

    if key.startswith('$'):
        attr = key[1:]
        if not attr.startswith('adagio-'):
            parent.set(attr, str(value))
        return

    if isinstance(value, list):
        for item in value:
            child = ET.SubElement(parent, key)
            if isinstance(item, dict):
                # 'content' means text body of the element, not a child element
                if 'content' in item:
                    child.text = str(item['content'])
                for k, v in item.items():
                    if k != 'content':
                        _json_to_xml(child, k, v)
            elif item is not None:
                child.text = str(item)
    elif isinstance(value, dict):
        child = ET.SubElement(parent, key)
        if 'content' in value:
            child.text = str(value['content'])
        for k, v in value.items():
            if k != 'content':
                _json_to_xml(child, k, v)
    elif value is not None:
        child = ET.SubElement(parent, key)
        child.text = str(value)


def _reorder_measures(root: ET.Element) -> None:
    """Move <attributes> before <note> in every measure (required by MusicXML)."""
    for measure in root.iter('measure'):
        children = list(measure)
        children.sort(key=lambda el: _MEASURE_CHILD_ORDER.index(el.tag)
                      if el.tag in _MEASURE_CHILD_ORDER else len(_MEASURE_CHILD_ORDER))
        for child in children:
            measure.remove(child)
        for child in children:
            measure.append(child)


def build_tree(data: dict) -> ET.Element:
    """Convert a Flat.io score JSON dict to a MusicXML ElementTree."""
    score = data['score-partwise']
    root = ET.Element('score-partwise')
    root.set('version', score.get('$version', '4.0'))

    processed: set[str] = set()
    for key in _SCORE_CHILD_ORDER:
        if key in score:
            processed.add(key)
            _json_to_xml(root, key, score[key])

    for key, value in score.items():
        if key not in processed and not _should_skip(key) \
                and not key.startswith('$') and key != 'measure-list':
            _json_to_xml(root, key, value)

    _reorder_measures(root)
    return root


def to_musicxml_string(root: ET.Element) -> str:
    """Serialise an ElementTree to a pretty-printed MusicXML string."""
    raw = ET.tostring(root, encoding='unicode')
    dom = minidom.parseString(raw)
    pretty = dom.toprettyxml(indent='  ', encoding='UTF-8').decode('utf-8')
    lines = pretty.split('\n')
    lines.insert(1, '<!DOCTYPE score-partwise PUBLIC'
                 ' "-//Recordare//DTD MusicXML 4.0 Partwise//EN"'
                 ' "http://www.musicxml.org/dtds/partwise.dtd">')
    return '\n'.join(lines)


# ── Flat.io API ───────────────────────────────────────────────────────────────

def parse_flat_url(url: str) -> tuple[str, str]:
    """Return (score_id, sharing_key) from a Flat.io share URL."""
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    sharing_key = (params.get('sharingKey') or [''])[0]
    m = re.search(r'/score/([a-f0-9]{24})', parsed.path)
    if not m:
        raise ValueError(f"No score ID found in URL: {url}")
    return m.group(1), sharing_key


def _api_get(path: str, sharing_key: str = '') -> dict | list:
    url = f"{FLAT_API}{path}"
    if sharing_key:
        url += f"?sharingKey={urllib.parse.quote(sharing_key, safe='')}"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def fetch_score_json(score_id: str, sharing_key: str) -> dict:
    """Fetch the latest revision JSON for a Flat.io score."""
    revisions = _api_get(f"/scores/{score_id}/revisions", sharing_key)
    if not revisions:
        raise RuntimeError("No revisions found for this score.")
    rev_id = revisions[0]['id']
    print(f"  revision: {rev_id}", file=sys.stderr)
    return _api_get(f"/scores/{score_id}/revisions/{rev_id}/json", sharing_key)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Download a Flat.io score and convert it to MusicXML.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('url_or_id',
                        help='Flat.io share URL, or bare score ID (24 hex chars)')
    parser.add_argument('key_or_output', nargs='?',
                        help='Sharing key (when first arg is a bare ID), or output path')
    parser.add_argument('output', nargs='?',
                        help='Output .musicxml path')
    args = parser.parse_args()

    first = args.url_or_id
    if first.startswith('http'):
        score_id, sharing_key = parse_flat_url(first)
        output_path = args.key_or_output
    else:
        score_id = first
        second = args.key_or_output or ''
        if second.endswith(('.musicxml', '.xml')) or '/' in second:
            sharing_key = ''
            output_path = second or None
        else:
            sharing_key = second
            output_path = args.output

    if not output_path:
        output_path = f"{score_id}.musicxml"

    print(f"Score:  {score_id}", file=sys.stderr)
    print(f"Output: {output_path}", file=sys.stderr)

    data = fetch_score_json(score_id, sharing_key)
    root = build_tree(data)
    xml = to_musicxml_string(root)
    Path(output_path).write_text(xml, encoding='utf-8')

    parts = root.findall('.//part')
    notes = sum(len(p.findall('.//note')) for p in parts)
    measures = len(parts[0].findall('measure')) if parts else 0
    print(f"Saved {output_path}  ({len(parts)} part(s), {measures} measures, {notes} notes)")


if __name__ == '__main__':
    main()
