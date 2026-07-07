# CIM — Conversation Entity Archive (Generation 1)

Local archive of the Grok conversation entity: **RAND SYSTEM B \ RAND SYSTEM A | NLS YOLODarket STEM**

## Structure

| Folder | Contents |
|--------|----------|
| `01_tutorial/` | Stacking vs. Cloud Collision — 30min tutorial (.md, landscape .pdf, generator) |
| `02_source_pdfs/` | `grok_report-2.pdf`, `RAND_System_Design_Document.pdf` |
| `03_parsed_sources/` | OCR text, page PNGs, RAND SDD extract |
| `04_rand_blockcode/` | Modular blockcode Java system (13 blocks, `./build.sh`) |
| `05_extrusion_sketches/` | MONO dual/dUP Processing sketches + GL002B reference |
| `06_nls_refs/` | NLS Visualist (`GravityDesktop`, `nls-video-monitor`) |
| `07_conversation_entity/` | Manifest, generation metadata |

## Quick start

```bash
cd /home/s9/Downloads/CIM/04_rand_blockcode
./build.sh
```

## Notation

```
RAND SYSTEM B \ RAND SYSTEM A | NLS YOLODarket STEM
```

- **SYSTEM A** (`MONO_XXI_PS_INT_dual`) — neat stacking: pixel matrix, LSystem gen -13, Spout
- **SYSTEM B** (`MONO_XXI_PS_INT_dUP`) — cloud collision: FFT 512 bands, AudioIn, BOX/QUAD
- **NLS pipe** — YOLODarket → 11D Hierarchy STEM → Visualist catalog

## Git

Local repository rooted here. Large TIFF sequences under `VX_GL002B_A02/` are on disk but gitignored.