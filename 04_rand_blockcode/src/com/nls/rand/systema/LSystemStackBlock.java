package com.nls.rand.systema;

import com.nls.rand.blockcode.Block;
import com.nls.rand.blockcode.BlockContext;
import com.nls.rand.blockcode.BlockResult;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * RAND System A — L-system stack simulation (mirrors Extrusion dual sketch).
 */
public final class LSystemStackBlock implements Block {
    @Override
    public String id() {
        return "lsystem_stack";
    }

    @Override
    public String system() {
        return "systema";
    }

    @Override
    public BlockResult execute(BlockContext ctx) {
        int width = ctx.has("width") ? ctx.get("width") : ctx.config().getInt("width", 1080);
        int height = ctx.has("height") ? ctx.get("height") : ctx.config().getInt("height", 790);
        int iterations = ctx.config().getInt("iterations", 4);
        int simulateDepth = ctx.config().getInt("simulate", -13);

        int[][] values = ctx.get("values");
        if (values == null) {
            values = new int[height][width];
        }

        List<String> stackTrace = new ArrayList<>();
        int nodes = 0;
        for (int y = 1; y < height; y += 12) {
            for (int x = 1; x < width; x++) {
                int v = values[y][x];
                if (v > 0) {
                    String branch = expandLSystem("F", iterations);
                    stackTrace.add("y=" + y + " x=" + x + " depth=" + simulateDepth + " len=" + branch.length());
                    nodes++;
                    if (nodes >= 8) {
                        break;
                    }
                }
            }
            if (nodes >= 8) {
                break;
            }
        }

        ctx.put("lsystem_nodes", nodes);
        ctx.put("lsystem_trace", stackTrace);
        return BlockResult.ok(
                "LSystemStackBlock simulated " + nodes + " stack nodes (iterations=" + iterations + ")",
                Map.of("nodes", nodes, "simulate_depth", simulateDepth)
        );
    }

    private static String expandLSystem(String axiom, int iterations) {
        String current = axiom;
        for (int i = 0; i < iterations; i++) {
            StringBuilder next = new StringBuilder(current.length() * 2);
            for (char c : current.toCharArray()) {
                if (c == 'F') {
                    next.append("F[+F]F[-F]F");
                } else {
                    next.append(c);
                }
            }
            current = next.toString();
        }
        return current;
    }
}