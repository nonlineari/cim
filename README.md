# CIM — Conversation Entity Archive

**Version 1.0.0** · MIT License · Copyright © 2026 NLS Records

Local archive of the Grok conversation entity:

```
RAND System B \ RAND System A | NLS YOLODarket STEM
```

## Readily available systems

| System | Path |
|--------|------|
| **RAND BlockCode Java** | [`04_rand_blockcode/`](04_rand_blockcode/) |
| **RAND System A** (Neat Stacking) | [`05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dual/`](05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dual/) |
| **RAND System B** (Cloud Collision) | [`05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dUP/`](05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dUP/) |
| **NLS YOLODarket STEM** | [`04_rand_blockcode/src/com/nls/rand/nls/`](04_rand_blockcode/src/com/nls/rand/nls/) |
| **RAND Stacking vs Cloud Collision Tutorial** | [`01_tutorial/`](01_tutorial/) |
| **NLS Visualist** | [`06_nls_refs/nls-video-monitor/`](06_nls_refs/nls-video-monitor/) |

Full catalog: [SYSTEMS.md](SYSTEMS.md)

## Structure

| Folder | Contents |
|--------|----------|
| `01_tutorial/` | RAND Stacking vs Cloud Collision — 30min tutorial |
| `02_source_pdfs/` | RAND source PDFs |
| `03_parsed_sources/` | OCR text, page PNGs |
| `04_rand_blockcode/` | **RAND BlockCode Java** — 13 blocks |
| `05_extrusion_sketches/` | RAND System A & B Processing sketches |
| `06_nls_refs/` | NLS Visualist references |
| `07_conversation_entity/` | Manifest, generation metadata |

## Quick start

```bash
cd 04_rand_blockcode
./build.sh
```

## RAND BlockCode Java

Modular block pipeline wiring **RAND System A → RAND System B → NLS YOLODarket STEM**:

- **System A blocks:** `pixel_stack`, `lsystem_stack`, `recursive_sphere`, `spout_output`
- **System B blocks:** `audio_in`, `fft_collision`, `duplex_branch`, `spectrum_render`
- **NLS blocks:** `yolo_darket`, `hierarchy_stem`, `nls_visualist_bridge`

## Git

```bash
git tag -l          # v1.0.0
git log --oneline
```

Large TIFF sequences (`VX_GL002B_A02/`) and build artifacts are gitignored but remain on disk.

## License

MIT — see [LICENSE](LICENSE).