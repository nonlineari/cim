package com.nls.rand.blockcode;

/**
 * STEM hierarchy module tags for NLS blockcode pipelines.
 */
public enum STEMModule {
    SCIENCE("science", "S"),
    TECHNOLOGY("technology", "T"),
    ENGINEERING("engineering", "E"),
    MATHEMATICS("mathematics", "M"),
    ARTS("arts", "A");

    private final String label;
    private final String code;

    STEMModule(String label, String code) {
        this.label = label;
        this.code = code;
    }

    public String label() {
        return label;
    }

    public String code() {
        return code;
    }

    public static STEMModule fromLabel(String label) {
        if (label == null) {
            return ENGINEERING;
        }
        String normalized = label.trim().toLowerCase();
        for (STEMModule m : values()) {
            if (m.label.equals(normalized) || m.code.equalsIgnoreCase(normalized)) {
                return m;
            }
        }
        return ENGINEERING;
    }
}