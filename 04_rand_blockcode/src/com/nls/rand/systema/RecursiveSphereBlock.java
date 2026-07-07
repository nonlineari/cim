package com.nls.rand.systema;

import com.nls.rand.blockcode.Block;
import com.nls.rand.blockcode.BlockContext;
import com.nls.rand.blockcode.BlockResult;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * RAND System A — recursive box/sphere extrusion from stacked pixel values.
 */
public final class RecursiveSphereBlock implements Block {
    @Override
    public String id() {
        return "recursive_sphere";
    }

    @Override
    public String system() {
        return "systema";
    }

    @Override
    public BlockResult execute(BlockContext ctx) {
        int width = ctx.has("width") ? ctx.get("width") : 1080;
        int height = ctx.has("height") ? ctx.get("height") : 790;
        int[][] values = ctx.get("values");
        if (values == null) {
            return BlockResult.fail("RecursiveSphereBlock: missing values int[height][width]");
        }

        float theta = (float) ctx.config().getDouble("theta", 10.0);
        float divisor = (float) ctx.config().getDouble("divisor", 2.0f);
        int maxDepth = ctx.config().getInt("max_depth", 4);

        List<String> draws = new ArrayList<>();
        int count = 0;
        for (int y = 0; y < height; y += 12) {
            for (int x = 0; x < width; x += 1) {
                float radio = Math.max(1f, values[y][x] % 64);
                int depth = recurseDraw(x, y, radio, 0, maxDepth, divisor, draws);
                count += depth;
                if (draws.size() >= 6) {
                    break;
                }
            }
            if (draws.size() >= 6) {
                break;
            }
        }

        ctx.put("sphere_draws", draws);
        ctx.put("theta", theta);
        return BlockResult.ok(
                "RecursiveSphereBlock rendered " + draws.size() + " recursive boxes (total_depth=" + count + ")",
                Map.of("draw_samples", draws.size(), "theta", theta)
        );
    }

    private static int recurseDraw(float x, float y, float radio, int z, int maxDepth, float divisor, List<String> out) {
        if (z > maxDepth) {
            return 0;
        }
        out.add(String.format("box(%.1f,%.1f,z=%d,r=%.2f)", x, y, z, radio));
        if (z > 16) {
            return 1 + recurseDraw(0, 0, radio / divisor, z + 1, maxDepth, divisor, out);
        }
        return 1;
    }
}