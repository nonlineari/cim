package com.nls.rand.systemb;

import com.nls.rand.blockcode.Block;
import com.nls.rand.blockcode.BlockContext;
import com.nls.rand.blockcode.BlockResult;

import java.util.Map;

/**
 * RAND System B — render spectrum collision into stroke weights (dUP sketch draw loop).
 */
public final class SpectrumRenderBlock implements Block {
    @Override
    public String id() {
        return "spectrum_render";
    }

    @Override
    public String system() {
        return "systemb";
    }

    @Override
    public BlockResult execute(BlockContext ctx) {
        float[] spectrum = ctx.get("spectrum");
        int[][] values = ctx.get("values");
        if (spectrum == null) {
            return BlockResult.fail("SpectrumRenderBlock: missing spectrum from FFTCollisionBlock");
        }

        int width = ctx.has("width") ? ctx.get("width") : 1024;
        int height = ctx.has("height") ? ctx.get("height") : 768;
        int bands = spectrum.length;

        float collisionEnergy = 0f;
        int samples = 0;
        for (int y = 0; y < height; y += 12) {
            for (int x = 0; x < width; x++) {
                int band = (x + y) % bands;
                float weight = spectrum[band] * 100f;
                if (values != null && y < values.length && x < values[y].length) {
                    weight += (values[y][x] % 16) * 0.01f;
                }
                collisionEnergy += weight;
                samples++;
            }
        }

        float avg = samples > 0 ? collisionEnergy / samples : 0f;
        ctx.put("collision_energy", avg);
        ctx.put("render_mode", "cloud_collision");

        return BlockResult.ok(
                "SpectrumRenderBlock collision energy=" + String.format("%.4f", avg) + " over " + samples + " samples",
                Map.of("collision_energy", avg, "samples", samples, "bands", bands)
        );
    }
}