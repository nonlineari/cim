# FONTLOG — CIM Typography (NLS Records)

Copyright (c) 2026 NLS Records  
License: SIL Open Font License 1.1 — see [LICENSE-OFL](../LICENSE-OFL)

## Purpose

The `fonts/` directory holds OFL-licensed typefaces for CIM deliverables:

- RAND Stacking vs Cloud Collision tutorial PDFs
- SYSTEMS / MANIFEST documentation exports
- NLS Records visual identity in Disinformation Architecture materials

## Families

| Family | Files | Reserved Font Name | Status |
|--------|-------|-------------------|--------|
| *(slot)* | — | — | Add `.ttf` / `.otf` / `.woff2` here |

When adding a font:

1. Place files under `fonts/<FamilyName>/`
2. Add a row to this FONTLOG with Reserved Font Name(s)
3. Include `OFL.txt` copy in the family directory (or reference root `LICENSE-OFL`)
4. Do not release Modified Versions under Reserved Font Names without permission

## Tutorial PDF note

`01_tutorial/generate_tutorial_pdf.py` currently uses ReportLab built-in
Helvetica/Courier (not OFL). When NLS Records brand fonts are added here,
update the generator to load from `fonts/` under OFL terms.