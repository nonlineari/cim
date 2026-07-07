# CIM Systems Catalog

Readily available named systems in this repository (**v1.0.0**).

## Core systems

| System | Folder | Description |
|--------|--------|-------------|
| **RAND BlockCode Java** | `04_rand_blockcode/` | Modular a priori block pipeline — 13 blocks, `./build.sh` |
| **RAND System A** (Neat Stacking) | `05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dual/` | Processing sketch — pixel stack, LSystem gen -13, Spout |
| **RAND System B** (Cloud Collision) | `05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dUP/` | Processing sketch — FFT 512 bands, AudioIn, spectrum overlay |
| **NLS YOLODarket STEM** | `04_rand_blockcode/src/com/nls/rand/nls/` | Vision scan + 11D hierarchy + Visualist catalog bridge |
| **RAND Stacking vs Cloud Collision Tutorial** | `01_tutorial/` | 30-minute `.diff` tutorial (.md + landscape .pdf) |
| **NLS Visualist** | `06_nls_refs/nls-video-monitor/` | H.264 pipeline, hierarchy interpreter, video pipe |

## Reference materials

| System | Folder |
|--------|--------|
| **RAND Source PDFs** | `02_source_pdfs/` — `grok_report-2.pdf`, `RAND_System_Design_Document.pdf` |
| **RAND Parsed Extracts** | `03_parsed_sources/` — OCR text, page images |
| **Extrusion3 GL002B Reference** | `05_extrusion_sketches/Extrusion3_2_2_1_DUAL_VX_GL002B_Complete/` |

## Pipeline notation

```
RAND System B \ RAND System A | NLS YOLODarket STEM
```

1. **RAND System A** runs first (stacking foundation)
2. **RAND System B** extends A (collision overlay)
3. **NLS YOLODarket STEM** pipes output to Visualist catalog

## Quick commands

```bash
# RAND BlockCode Java
cd 04_rand_blockcode && ./build.sh

# NLS hierarchy explorer
python3 06_nls_refs/nls-video-monitor/hierarchy_interpreter.py

# Regenerate tutorial PDF
python3 01_tutorial/generate_tutorial_pdf.py
```

## License

MIT — see [LICENSE](LICENSE).