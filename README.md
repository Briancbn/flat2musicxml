# flat2musicxml

Convert a [Flat.io](https://flat.io) shared score to MusicXML 4.0.

> [!WARNING]
> This tool relies on an undocumented internal Flat.io API endpoint (`/v2/scores/{id}/revisions/{rev}/json`). It may break without notice if Flat.io changes their backend. Use at your own risk.

## How it works

Flat.io's official XML/MXL export requires a paid subscription (returns HTTP 402). However, the JSON revision endpoint is accessible with just a sharing key. This script fetches that JSON — which encodes the score as MusicXML-in-JSON — and converts it back to standard MusicXML.

## Usage

```bash
python flat_to_musicxml.py <url-or-score-id> [--key <sharing-key>] [--out output.musicxml]
```

**Examples:**

```bash
# From a full shareable link (sharing key embedded in URL)
python flat_to_musicxml.py "https://flat.io/score/abc123?sharingKey=xyz..."

# From a bare score ID + explicit key
python flat_to_musicxml.py abc123 --key xyz... --out score.musicxml
```

The output file defaults to `<score-id>.musicxml` in the current directory.

## Requirements

Python 3.10+, no third-party dependencies.

## Running tests

```bash
uv run pytest -v                    # all tests (includes live network call)
uv run pytest -v -m "not network"  # offline tests only
```

The network test (`test_e2e_real_account_score`) calls the real Flat.io API and requires internet access.

## License

MIT — see [LICENSE](LICENSE).
