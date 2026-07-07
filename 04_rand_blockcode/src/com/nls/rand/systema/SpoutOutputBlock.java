package com.nls.rand.systema;

import com.nls.rand.blockcode.Block;
import com.nls.rand.blockcode.BlockContext;
import com.nls.rand.blockcode.BlockResult;

import java.util.Map;

/**
 * RAND System A — Spout sender stub (Extrusion3_2_2_1_MONO_XXI_PS_INT_dual).
 */
public final class SpoutOutputBlock implements Block {
    @Override
    public String id() {
        return "spout_output";
    }

    @Override
    public String system() {
        return "systema";
    }

    @Override
    public BlockResult execute(BlockContext ctx) {
        String sender = ctx.config().get("sender", "Extrusion3_2_2_1_MONO_XXI_PS_INT_dual");
        int width = ctx.has("width") ? ctx.get("width") : 1080;
        int height = ctx.has("height") ? ctx.get("height") : 790;

        String frame = String.format("spout://%s/%dx%d/frame", sender, width, height);
        ctx.put("spout_sender", sender);
        ctx.put("spout_frame", frame);

        return BlockResult.ok(
                "SpoutOutputBlock registered sender '" + sender + "' (" + width + "x" + height + ")",
                Map.of("sender", sender, "frame_uri", frame)
        );
    }
}