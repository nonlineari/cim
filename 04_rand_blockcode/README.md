# RAND BlockCode Java

**CIM v1.0.0** · MIT License

Modular a priori blockcode engine for **RAND System A**, **RAND System B**, and **NLS YOLODarket STEM**.

## Build & run

```bash
./build.sh
```

Requires JDK 11+ and `javac`/`java` on PATH.

## Systems wired

| Layer | Blocks |
|-------|--------|
| **RAND System A** (Neat Stacking) | `extrusion_dual_adapter`, `pixel_stack`, `lsystem_stack`, `recursive_sphere`, `spout_output` |
| **RAND System B** (Cloud Collision) | `extrusion_dup_adapter`, `audio_in`, `fft_collision`, `duplex_branch`, `spectrum_render` |
| **NLS YOLODarket STEM** | `yolo_darket`, `hierarchy_stem`, `nls_visualist_bridge` |

Pipeline definition: [`blocks/pipeline.json`](blocks/pipeline.json)

Architecture map: [`sketch_refs/SYSTEM_MAP.md`](sketch_refs/SYSTEM_MAP.md)

## Entry point

`com.nls.rand.RANDNLSLauncher`