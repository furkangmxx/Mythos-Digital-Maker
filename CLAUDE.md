# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MythosCards Exporter - Turkish sports card checklist processing application with GUI and CLI interfaces. Processes Excel checklists into card lists, matches images, and shortens filenames.

## Commands

```bash
# Run GUI application
python src/main.py

# Run tests
pytest tests/

# Run single test file
pytest tests/test_headers.py -v

# Build executable (Windows)
pyinstaller build.spec
```

## Architecture

Three-part sequential pipeline:

### Part 1: Checklist Processing
`headers.py` → `validate.py` → `expand.py` → `export.py`

- **Input**: Excel checklist with variant columns (1/1, /5, /25, Base, X İmzalı, etc.)
- **Output**: Excel with individual card rows in "Çıktı" sheet

### Part 2: Image Matching (`images.py`)
- **ImageMatcher class**: Reads cards from Excel, parses image filenames, matches by content
- **Key method**: `_parse_filename()` - extracts denominator, signed status, content parts from filename
- **Denominator types**: numeric (5, 25) or text ("X", "BASE", "SHORT PRINT")
- **Text denominators learned from Excel** via `known_text_denoms` set before parsing files

### Part 3: Filename Shortening (`shorten.py`)
- Shortens filenames exceeding max length by truncating `player_name` portion
- Preserves: series, group, denominator, signed marker, extension

## Excel Column Structure (Çıktı Sheet)

| Index | Column | Content |
|-------|--------|---------|
| 0 | A | Kart Listesi (display text) |
| 1 | B | Görsel Dosyası (Part 2 fills) |
| 2 | C | player_name |
| 3 | D | series_name |
| 4 | E | group |
| 5 | F | denominator (int or str) |
| 6 | G | is_signed (Evet/Hayır) |

## Key Patterns

### Turkish Character Normalization
`normalize_for_matching()` in `images.py` and similar in other files:
- ğ→g, ş→s, ç→c, ö→o, ü→u, ı→i
- European chars: ä→a, é→e, ñ→n, etc.
- Spaces/hyphens → underscore, special chars removed

### Image Filename Format
```
[YYYYMMDD_]content_parts[_s]_denominator.ext
```
- `_s` = signed marker
- `_base` = base card
- `_x_s_1` = text denominator X, signed, sequence number 1

### Denominator Handling
- `Union[int, str]` type throughout codebase
- Numeric: `/5`, `/25` → stored as int
- Text: `X İmzalı`, `Base`, `Short Print` → stored as uppercase str

## Language

- Code comments and log messages are in Turkish
- Variable/function names mix English and Turkish
- User-facing text is Turkish
