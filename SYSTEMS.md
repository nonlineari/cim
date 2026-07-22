# CIM Systems Catalog

Readily available named systems in this repository (**v1.0.6**). See [CHANGELOG.md](CHANGELOG.md).

## Core systems

| System | Folder | Description |
|--------|--------|-------------|
| **RAND BlockCode Java** | `04_rand_blockcode/` | Modular a priori block pipeline — 14 blocks, `./build.sh` |
| **RAND System A** (Neat Stacking) | `05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dual/` | Processing sketch — pixel stack, LSystem gen -13, Spout |
| **RAND System B** (Cloud Collision) | `05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dUP/` | Processing sketch — FFT 512 bands, AudioIn, spectrum overlay |
| **NLS YOLODarket STEM** | `04_rand_blockcode/src/com/nls/rand/nls/` | Vision scan + 11D hierarchy + Visualist catalog bridge |
| **NLS OSINT Agent STEM** | `08_osint_agent/` + `04_rand_blockcode/src/com/nls/rand/osint/` | Best OSINT resources modules + Grok persona (EN/FR). Block id `osint_agent`. Pipeline: `pipeline-osint.json` |
| **RAND Stacking vs Cloud Collision Tutorial** | `01_tutorial/` | 30-minute `.diff` tutorial (.md + landscape .pdf).pdf) |
| **NLS Visualist** | `06_nls_refs/nls-video-monitor/` | H.264 pipeline, hierarchy interpreter, video pipe |

## Reference materials

| System | Folder |
|--------|--------|
| **RAND Source PDFs** | `02_source_pdfs/` — `grok_report-2.pdf`, `RAND_System_Design_Document.pdf` |
| **RAND Parsed Extracts** | `03_parsed_sources/` — OCR text, page images |
| **Extrusion3 GL002B Reference** | `05_extrusion_sketches/Extrusion3_2_2_1_DUAL_VX_GL002B_Complete/` |

## Pipeline notation

```
RAND System B \ RAND System A | NLS YOLODarket STEM | NLS OSINT Agent STEM
```

1. **RAND System A** runs first (stacking foundation)
2. **RAND System B** extends A (collision overlay)
3. **NLS YOLODarket STEM** pipes output to Visualist catalog
4. **NLS OSINT Agent STEM** injects intelligence knowledge base + bilingual Grok persona

## Quick commands

```bash
# RAND BlockCode Java
cd 04_rand_blockcode && ./build.sh

# NLS hierarchy explorer
python3 06_nls_refs/nls-video-monitor/hierarchy_interpreter.py

# Regenerate tutorial PDF
python3 01_tutorial/generate_tutorial_pdf.py

# Load OSINT Agent (Grok)
cat 08_osint_agent/agent/SYSTEM_PROMPT_FR.md
```

## License

**Code:** [MIT](LICENSE) · **Architecture:** [CIM](LICENSE-CIM) · **Sketches:** [WTFPL](LICENSE-WTFPL) · **Fonts:** [OFL-1.1](LICENSE-OFL) · © 2026 NLS Records
