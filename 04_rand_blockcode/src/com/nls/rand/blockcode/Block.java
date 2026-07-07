package com.nls.rand.blockcode;

/**
 * Executable pipeline block in the RAND NLS blockcode engine.
 */
public interface Block {
    String id();

    /** "systema" | "systemb" | "nls" | "extrusion" */
    String system();

    BlockResult execute(BlockContext ctx);
}