package com.nls.rand.extrusion;

import com.nls.rand.blockcode.Block;
import com.nls.rand.blockcode.BlockContext;
import com.nls.rand.blockcode.BlockResult;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

/**
 * Adapter for RAND System A extrusion sketch (neat stacking / dual).
 */
public final class ExtrusionDualAdapter implements Block {
    public static final Path SKETCH_ROOT = Path.of(
            "/home/s9/Downloads/CIM/05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dual"
    );

    @Override
    public String id() {
        return "extrusion_dual_adapter";
    }

    @Override
    public String system() {
        return "extrusion";
    }

    @Override
    public BlockResult execute(BlockContext ctx) {
        Path sketchRoot = SKETCH_ROOT;
        String configured = ctx.config().get("sketch_root", "");
        if (!configured.isBlank()) {
            sketchRoot = Path.of(configured);
        }

        Path pde = sketchRoot.resolve("Extrusion3_2_2_1_MONO_XXI_PS_INT_dual.pde");
        Path dataImage = sketchRoot.resolve("data/mwo_001.jpg");

        ctx.put("sketch_root", sketchRoot.toString());
        ctx.put("sketch_pde", pde.toString());
        ctx.put("image", dataImage.toString());
        ctx.put("system_mode", "dual_stacking");

        boolean pdeExists = Files.exists(pde);
        boolean imageExists = Files.exists(dataImage);

        return BlockResult.ok(
                "ExtrusionDualAdapter → " + sketchRoot + " (pde=" + pdeExists + ", image=" + imageExists + ")",
                Map.of(
                        "sketch_root", sketchRoot.toString(),
                        "pde_exists", pdeExists,
                        "image_exists", imageExists,
                        "sender", "Extrusion3_2_2_1_MONO_XXI_PS_INT_dual"
                )
        );
    }
}