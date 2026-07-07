package com.nls.rand.blockcode;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Loads pipeline.json and executes registered blocks in sequence.
 */
public final class BlockCodeEngine {
    private final BlockRegistry registry;

    public BlockCodeEngine(BlockRegistry registry) {
        this.registry = registry;
    }

    public List<BlockResult> runPipeline(Path pipelineJson) throws IOException {
        String json = Files.readString(pipelineJson);
        ParsedPipeline pipeline = parsePipeline(json);
        SimpleConfig config = new SimpleConfig(pipeline.globalConfig);
        BlockContext ctx = new BlockContext(config);
        ctx.put("pipeline_name", pipeline.name);
        ctx.put("pipeline_system", pipeline.system);

        List<BlockResult> results = new ArrayList<>();
        for (PipelineStep step : pipeline.steps) {
            Block block = registry.get(step.blockId);
            for (Map.Entry<String, String> e : step.params.entrySet()) {
                config.put(step.blockId + "." + e.getKey(), e.getValue());
                config.put(e.getKey(), e.getValue());
            }
            BlockResult result = block.execute(ctx);
            results.add(result);
            if (!result.success()) {
                break;
            }
        }
        return results;
    }

    private static final class PipelineStep {
        final String blockId;
        final Map<String, String> params = new LinkedHashMap<>();

        PipelineStep(String blockId) {
            this.blockId = blockId;
        }
    }

    private static final class ParsedPipeline {
        String name = "unnamed";
        String system = "systema";
        Map<String, String> globalConfig = new LinkedHashMap<>();
        List<PipelineStep> steps = new ArrayList<>();
    }

    static ParsedPipeline parsePipeline(String json) {
        ParsedPipeline p = new ParsedPipeline();
        String name = extractString(json, "name");
        if (name != null) {
            p.name = name;
        }
        String system = extractString(json, "system");
        if (system != null) {
            p.system = system;
        }

        String stepsArray = extractArray(json, "steps");
        if (stepsArray != null) {
            List<String> objects = splitTopLevelObjects(stepsArray);
            for (String obj : objects) {
                String blockId = extractString(obj, "block");
                if (blockId == null) {
                    continue;
                }
                PipelineStep step = new PipelineStep(blockId);
                String paramsObj = extractObject(obj, "params");
                if (paramsObj != null) {
                    for (String key : List.of("image", "width", "height", "iterations", "sender", "bands",
                            "branch", "query", "stem", "sketch_root", "catalog")) {
                        String val = extractString(paramsObj, key);
                        if (val != null) {
                            step.params.put(key, val);
                        }
                    }
                }
                p.steps.add(step);
            }
        }

        String configObj = extractObject(json, "config");
        if (configObj != null) {
            for (String key : List.of("sketch_dual", "sketch_dup", "image_default", "cim_root")) {
                String val = extractString(configObj, key);
                if (val != null) {
                    p.globalConfig.put(key, val);
                }
            }
        }
        return p;
    }

    private static String extractString(String json, String key) {
        String pattern = "\"" + key + "\"";
        int idx = json.indexOf(pattern);
        if (idx < 0) {
            return null;
        }
        int colon = json.indexOf(':', idx + pattern.length());
        if (colon < 0) {
            return null;
        }
        int startQuote = json.indexOf('"', colon + 1);
        if (startQuote < 0) {
            return null;
        }
        int endQuote = json.indexOf('"', startQuote + 1);
        if (endQuote < 0) {
            return null;
        }
        return json.substring(startQuote + 1, endQuote);
    }

    private static String extractObject(String json, String key) {
        String pattern = "\"" + key + "\"";
        int idx = json.indexOf(pattern);
        if (idx < 0) {
            return null;
        }
        int brace = json.indexOf('{', idx);
        if (brace < 0) {
            return null;
        }
        return extractBalanced(json, brace, '{', '}');
    }

    private static String extractArray(String json, String key) {
        String pattern = "\"" + key + "\"";
        int idx = json.indexOf(pattern);
        if (idx < 0) {
            return null;
        }
        int bracket = json.indexOf('[', idx);
        if (bracket < 0) {
            return null;
        }
        return extractBalanced(json, bracket, '[', ']');
    }

    private static String extractBalanced(String json, int start, char open, char close) {
        int depth = 0;
        for (int i = start; i < json.length(); i++) {
            char c = json.charAt(i);
            if (c == open) {
                depth++;
            } else if (c == close) {
                depth--;
                if (depth == 0) {
                    return json.substring(start, i + 1);
                }
            }
        }
        return null;
    }

    private static List<String> splitTopLevelObjects(String arrayJson) {
        List<String> out = new ArrayList<>();
        int depth = 0;
        int start = -1;
        for (int i = 0; i < arrayJson.length(); i++) {
            char c = arrayJson.charAt(i);
            if (c == '{') {
                if (depth == 0) {
                    start = i;
                }
                depth++;
            } else if (c == '}') {
                depth--;
                if (depth == 0 && start >= 0) {
                    out.add(arrayJson.substring(start, i + 1));
                    start = -1;
                }
            }
        }
        return out;
    }
}