package com.nls.rand.nls;

import com.nls.rand.blockcode.Block;
import com.nls.rand.blockcode.BlockContext;
import com.nls.rand.blockcode.BlockResult;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * NLS — steady YOLO/Darknet search stub (view-only, no alter/delete).
 */
public final class YOLODarketBlock implements Block {
    @Override
    public String id() {
        return "yolo_darket";
    }

    @Override
    public String system() {
        return "nls";
    }

    @Override
    public BlockResult execute(BlockContext ctx) {
        String query = ctx.config().get("query", "extrusion");
        String imagePath = ctx.has("image_path") ? ctx.get("image_path") : ctx.config().get("image", "");
        boolean allowDistribution = ctx.config().getBoolean("allow_distribution", false);

        List<String> hits = new ArrayList<>();
        if (!allowDistribution) {
            hits.add("YOLO_SEARCH_LOCAL: distribution not opted-in");
        }

        Path path = imagePath == null || imagePath.isBlank() ? null : Path.of(imagePath);
        if (path != null && Files.exists(path)) {
            String name = path.getFileName().toString().toLowerCase();
            if (name.contains(query.toLowerCase()) || query.equalsIgnoreCase("extrusion")) {
                hits.add("YOLO-DETECT: class=POV_IMAGE conf=0.88 path=" + path);
                hits.add("OCR: metadata tag '" + query + "' matched");
            } else {
                hits.add("YOLO no detection for '" + query + "' in " + name);
            }
        } else {
            hits.add("YOLO stub: no image path — simulated POV_IMAGE conf=0.75");
        }

        ctx.put("yolo_hits", hits);
        return BlockResult.ok(
                "YOLODarketBlock search '" + query + "' — " + hits.size() + " result(s)",
                Map.of("query", query, "hits", hits.size(), "allow_distribution", allowDistribution)
        );
    }
}