# Changelog

All notable changes to **CIM — Conversation Entity Archive** are documented here.  
Copyright © 2026 NLS Records.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.4] — 2026-07-07

### Added

- **`index.htm`** — mandatory CIM Serve Hub (`06_nls_refs/nls-video-monitor/`)
- `licenses.html`, `changelog.html`, `cim-approved-plan.html`, `git-review.html`
- `serve-hub-common.css`, `build_review_html.py`
- [`LICENSE-TYPOGRAPHY`](LICENSE-TYPOGRAPHY), [`URW-SCOPE.md`](07_conversation_entity/URW-SCOPE.md)

### Changed

- License matrix: Helvetica (URW) separate from OFL
- [`plan.html`](06_nls_refs/nls-video-monitor/plan.html) nav → `index.htm`
- [`LICENSE-CIM`](LICENSE-CIM) §5 — full license relationship table

## [1.0.3] — 2026-07-07

### Added

- **Helvetica canon** — `fonts/CIM-Visualist/A-VISUALIST.md` (NLS Visualist · A. Visualist)
- `fonts/cim_visualist_typography.py` — shared Helvetica / Visualist constants
- `fonts/CIM-Visualist/Helvetica/NimbusSans/` — archived URW substitute (`.afm`, `.t1`)
- `fonts/preserve_helvetica.sh` — re-copy fonts before host takedown

### Changed

- `01_tutorial/generate_tutorial_pdf.py` — Helvetica via typography module; Visualist header/footer; output under CIM
- `fonts/FONTLOG.md` — Helvetica registered as primary face (not OFL placeholder)

## [1.0.2] — 2026-07-07

### Added

- `CHANGELOG.md` — release history
- `LICENSE-OFL` — SIL Open Font License 1.1 (OFL-1.1)
- `fonts/` — typography layer directory with `FONTLOG.md` and `OFL-NOTICE.txt`
- `07_conversation_entity/OFL-SCOPE.md` — scope for OFL-licensed fonts

### Changed

- License map extended to quad-license: MIT + CIM + WTFPL + OFL
- `README.md`, `SYSTEMS.md`, `MANIFEST.md`, `generation.json` updated

## [1.0.1] — 2026-07-07

### Added

- `LICENSE-CIM` — CIM License v1.0 (Disinformation Architecture)
- `LICENSE-WTFPL` — Do What The Fuck You Want To Public License v2
- `07_conversation_entity/CIM-LICENSE.md` — CIM license summary
- `07_conversation_entity/WTFPL-SCOPE.md` — WTFPL scope for sketches & experiments

### Changed

- Tri-license model: MIT (code) · CIM (architecture) · WTFPL (experiments)
- Version bumped to 1.0.1 across `VERSION`, pipeline, build banner
- Tutorial front-matter cites CIM License

### Tagged

- `v1.0.1` — MIT + CIM Disinformation Architecture + WTFPL (© NLS Records)

## [1.0.0] — 2026-07-07

### Added

- Initial CIM Generation 1 archive at `/home/s9/Downloads/CIM`
- `01_tutorial/` — RAND Stacking vs Cloud Collision (`.md`, landscape `.pdf`)
- `02_source_pdfs/` — `grok_report-2.pdf`, `RAND_System_Design_Document.pdf`
- `03_parsed_sources/` — OCR text, grok report page PNGs
- `04_rand_blockcode/` — **RAND BlockCode Java** (13 modular blocks)
- `05_extrusion_sketches/` — RAND System A (dual) & B (dUP) Processing sketches
- `06_nls_refs/` — NLS Visualist (`nls-video-monitor`)
- `07_conversation_entity/` — `MANIFEST.md`, `generation.json`
- `LICENSE` — MIT License
- `SYSTEMS.md`, `README.md`, `VERSION`
- Named systems catalog: RAND BlockCode Java, RAND System A/B, NLS YOLODarket STEM

### Changed

- Copyright holder set to **NLS Records**

### Tagged

- `v1.0.0` — RAND BlockCode Java (MIT, © NLS Records)

[1.0.4]: https://github.com/nlsrecords/cim/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/nlsrecords/cim/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/nlsrecords/cim/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/nlsrecords/cim/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/nlsrecords/cim/releases/tag/v1.0.0