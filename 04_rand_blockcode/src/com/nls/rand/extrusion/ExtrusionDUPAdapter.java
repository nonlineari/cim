package com.nls.rand.extrusion;

import com.nls.rand.blockcode.Block;
import com.nls.rand.blockcode.BlockContext;
import com.nls.rand.blockcode.BlockResult;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

/**
 * Adapter for RAND System B extrusion sketch (cloud collision / dUP).
 */
public final class ExtrusionDUPAdapter implements Block {
    public static final Path SKETCH_ROOT = Path.of(
            "/home/s9/Downloads/CIM/05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dUP"
    );

    @Override
    public String id() {
        return "extrusion_dup_adapter";
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

        Path pde = sketchRoot.resolve("Extrusion3_2_2_1_MONO_XXI_PS_INT_dUP.pde");
        Path dataImage = sketchRoot.resolve("data/mwo_001.jpg");

        ctx.put("sketch_root", sketchRoot.toString());
        ctx.put("sketch_pde", pde.toString());
        ctx.put("system_mode", "dup_collision");
        ctx.put("bands", 512);

        boolean pdeExists = Files.exists(pde);

        return BlockResult.ok(
                "ExtrusionDUPAdapter → " + sketchRoot + " (pde=" + pdeExists + ", fft_bands=512)",
                Map.of(
                        "sketch_root", sketchRoot.toString(),
                        "pde_exists", pdeExists,
                        "sender", "Extrusion3_2_2_1_MONO_XXI_PS_INT_dUP",
                        "data_image", dataImage.toString()
                )
        );
    }
}