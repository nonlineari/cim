# RAND NLS BlockCode — System Map

CIM generation entity archive for **04_rand_blockcode**.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    RANDNLSLauncher                               │
│                         │                                        │
│                  BlockCodeEngine                                   │
│                         │                                        │
│                  BlockRegistry (14 blocks)                       │
└─────────────────────────────────────────────────────────────────┘
          │                              │
   SYSTEM A (stacking)            SYSTEM B (collision)
          │                              │
   extrusion_dual_adapter          extrusion_dup_adapter
   pixel_stack [h][w]              audio_in
   lsystem_stack                    fft_collision
   recursive_sphere                 duplex_branch
   spout_output                     spectrum_render
          │                              │
          └──────────┬───────────────────┘
                     │
              NLS LAYER
         yolo_darket → hierarchy_stem → nls_visualist_bridge
```

## Sketch References (05_extrusion_sketches)

| Mode | Sketch Root | PDE | Spout Sender |
|------|-------------|-----|--------------|
| **Dual / neat stacking** | `/home/s9/Downloads/CIM/05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dual` | `Extrusion3_2_2_1_MONO_XXI_PS_INT_dual.pde` | `Extrusion3_2_2_1_MONO_XXI_PS_INT_dual` |
| **dUP / cloud collision** | `/home/s9/Downloads/CIM/05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dUP` | `Extrusion3_2_2_1_MONO_XXI_PS_INT_dUP.pde` | `Extrusion3_2_2_1_MONO_XXI_PS_INT_dUP` |

Default image (System A pixel stack):

`/home/s9/Downloads/CIM/05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dual/data/mwo_001.jpg`

## Pixel Layout

`PixelStackBlock` uses **`int[height][width]`** (row `y`, column `x` → `pixels[y][x]`).

## Pipeline

Defined in `blocks/pipeline.json` — runs hybrid System A → System B → NLS bridge.

## Build & Run

```bash
cd /home/s9/Downloads/CIM/04_rand_blockcode
chmod +x build.sh
./build.sh
```

## Block IDs

| ID | Package | Role |
|----|---------|------|
| `pixel_stack` | systema | Load image → int[height][width] |
| `lsystem_stack` | systema | L-system stack simulation |
| `recursive_sphere` | systema | Recursive box extrusion |
| `spout_output` | systema | Spout sender registration |
| `audio_in` | systemb | Audio input buffer |
| `fft_collision` | systemb | FFT spectrum bands |
| `duplex_branch` | systemb | Duplex-numeric ID |
| `spectrum_render` | systemb | Collision energy render |
| `yolo_darket` | nls | YOLO/Darknet search stub |
| `hierarchy_stem` | nls | STEM hierarchy tag |
| `nls_visualist_bridge` | nls | Visualist catalog bridge |
| `extrusion_dual_adapter` | extrusion | System A sketch paths |
| `extrusion_dup_adapter` | extrusion | System B sketch paths |