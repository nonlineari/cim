package com.nls.rand;

import com.nls.rand.blockcode.BlockCodeEngine;
import com.nls.rand.blockcode.BlockRegistry;
import com.nls.rand.blockcode.BlockResult;

import java.nio.file.Path;
import java.util.List;

/**
 * RAND NLS Blockcode launcher — compiles and runs pipeline.json.
 */
public final class RANDNLSLauncher {
    public static void main(String[] args) throws Exception {
        Path root = Path.of(System.getProperty("user.dir"));
        Path pipeline = args.length > 0
                ? Path.of(args[0])
                : root.resolve("blocks/pipeline.json");

        System.out.println("=== RAND NLS BlockCode Engine ===");
        System.out.println("Pipeline: " + pipeline.toAbsolutePath());

        BlockRegistry registry = new BlockRegistry();
        BlockCodeEngine engine = new BlockCodeEngine(registry);
        List<BlockResult> results = engine.runPipeline(pipeline);

        int step = 1;
        boolean allOk = true;
        for (BlockResult r : results) {
            System.out.printf("[%02d] %s%n", step++, r);
            if (!r.success()) {
                allOk = false;
            }
        }

        System.out.println("---");
        System.out.println("Blocks registered: " + registry.all().size());
        System.out.println("Pipeline steps run: " + results.size());
        System.out.println(allOk ? "STATUS: SUCCESS" : "STATUS: FAILED");

        if (!allOk) {
            System.exit(1);
        }
    }
}