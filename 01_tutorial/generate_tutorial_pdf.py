#!/usr/bin/env python3
"""Generate landscape PDF tutorial from stacking-vs-collision content."""

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Preformatted
)
from reportlab.pdfgen import canvas

OUTPUT = "/home/s9/Downloads/stacking-vs-collision-digital-arts-tutorial.pdf"
PAGE_W, PAGE_H = landscape(A4)
MARGIN = 0.55 * inch

# Palette — Warm Terracotta (architectural / material)
PRIMARY = colors.HexColor("#B85042")
SECONDARY = colors.HexColor("#E7E8D1")
ACCENT = colors.HexColor("#A7BEAE")
DARK = colors.HexColor("#36454F")
LIGHT_BG = colors.HexColor("#FCF9F5")
CODE_BG = colors.HexColor("#F4F0EB")


def build_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"],
            fontName="Helvetica-Bold", fontSize=28, leading=32,
            textColor=PRIMARY, alignment=TA_CENTER, spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"],
            fontName="Helvetica", fontSize=14, leading=18,
            textColor=DARK, alignment=TA_CENTER, spaceAfter=14,
        ),
        "slide_title": ParagraphStyle(
            "slide_title", parent=base["Heading1"],
            fontName="Helvetica-Bold", fontSize=20, leading=24,
            textColor=PRIMARY, spaceBefore=4, spaceAfter=10,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontName="Helvetica", fontSize=11, leading=14,
            textColor=DARK, spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"],
            fontName="Helvetica", fontSize=10.5, leading=13,
            textColor=DARK, leftIndent=14, bulletIndent=0, spaceAfter=4,
        ),
        "timing": ParagraphStyle(
            "timing", parent=base["Normal"],
            fontName="Helvetica-Oblique", fontSize=9,
            textColor=ACCENT, spaceAfter=8,
        ),
        "code": ParagraphStyle(
            "code", parent=base["Code"],
            fontName="Courier", fontSize=7.5, leading=9,
            textColor=DARK, backColor=CODE_BG,
            leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=4,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"],
            fontName="Helvetica", fontSize=8, textColor=colors.grey,
            alignment=TA_CENTER,
        ),
    }


def on_page(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFillColor(SECONDARY)
    canvas_obj.rect(0, PAGE_H - 0.35 * inch, PAGE_W, 0.35 * inch, fill=1, stroke=0)
    canvas_obj.setFillColor(PRIMARY)
    canvas_obj.rect(0, 0, PAGE_W, 0.22 * inch, fill=1, stroke=0)
    canvas_obj.setFillColor(colors.white)
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.drawString(MARGIN, PAGE_H - 0.24 * inch, "Stacking vs. Cloud Collision — Digital Arts for Architectural Designers")
    canvas_obj.drawRightString(PAGE_W - MARGIN, 0.08 * inch, f"Slide {doc.page}")
    canvas_obj.restoreState()


def slide_title_block(styles, title, timing=None):
    items = [Paragraph(title, styles["slide_title"])]
    if timing:
        items.append(Paragraph(timing, styles["timing"]))
    return items


def bullets(styles, lines):
    return [Paragraph(f"• {line}", styles["bullet"]) for line in lines]


def diff_block(styles, text):
    return [Preformatted(text, styles["code"])]


def make_table(data, col_widths=None):
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("BACKGROUND", (0, 1), (-1, -1), LIGHT_BG),
        ("GRID", (0, 0), (-1, -1), 0.5, ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def build_story(styles):
    s = []
    # Title slide
    s.append(Spacer(1, 1.2 * inch))
    s.append(Paragraph("Stacking vs. Cloud Collision", styles["title"]))
    s.append(Paragraph("A .diff Tutorial on Data Content for Architectural Designers", styles["subtitle"]))
    s.append(Spacer(1, 0.3 * inch))
    s.append(Paragraph(
        "<b>30 minutes</b> · Comparative .diff of <i>grok_report-2.pdf</i> and <i>RAND_System_Design_Document.pdf</i>",
        styles["body"]
    ))
    s.append(PageBreak())

    # Objectives
    s.extend(slide_title_block(styles, "Learning Objectives", "0:00 – 2:00"))
    s.extend(bullets(styles, [
        "Read a unified .diff and spot where data content diverges",
        "Explain neat stacking (duplex-numeric) vs. cloud collision (multi-service metadata)",
        "Map both models onto a design portfolio workflow",
        "Choose or hybridize for your archive / render / competition pipeline",
    ]))
    s.append(PageBreak())

    # Why architects
    s.extend(slide_title_block(styles, "Why Architects Already Think in Layers", "2:00 – 5:00"))
    s.extend(diff_block(styles, """┌─────────────────────────────────────┐
│  Presentation  — sheet layout, PDF  │
├─────────────────────────────────────┤
│  Annotation    — dimensions, notes  │
├─────────────────────────────────────┤
│  Geometry      — walls, meshes      │
├─────────────────────────────────────┤
│  Materials     — textures, shaders  │
└─────────────────────────────────────┘
         ▲ neatly stacked Z-order"""))
    s.append(Spacer(1, 0.15 * inch))
    s.append(Paragraph(
        "<b>Cloud collision</b> = the same facade photo living in a mood-board folder, "
        "a numeric sheet index, and three cloud buckets—with overlapping truths about where it lives.",
        styles["body"],
    ))
    s.append(PageBreak())

    # Two philosophies
    s.extend(slide_title_block(styles, "Two Documents, Two Data Philosophies", "5:00 – 7:00"))
    s.append(make_table([
        ["Aspect", "grok_report-2 (Stacking)", "RAND SDD (Collision)"],
        ["Core unit", "DocumentNode + duplex ID", "Document row + relational joins"],
        ["Placement", "Fixed numeric slot + branch", "Category tree + tags + JSONB"],
        ["Search", "Register + numeric order", "Elasticsearch + ML rerank"],
        ["Distribution", "WebSocket + numeric links", "Expiring tokens + RBAC + audit"],
        ["Metaphor", "Stacked index cards", "Service mesh over tables"],
    ], col_widths=[1.6 * inch, 3.4 * inch, 3.4 * inch]))
    s.append(PageBreak())

    # Master diff
    s.extend(slide_title_block(styles, "Master .diff — Data Content Model", "7:00 – 11:00"))
    s.extend(diff_block(styles, """--- grok_report-2.pdf (Neat Stacking)
+++ RAND_System_Design_Document.pdf (Cloud Collision)

@@ CORE ENTITY @@
-CLASS DocumentNode { ID: "7-4a.1-2b"; ContentHash; Branches; Links; RegisterIndex }
+TABLE documents + metadata(EAV) + categories + tags + distribution_links

@@ PLACEMENT @@
-baseID := FindNearestNumericalSlot(); AlphaSubBranch(); RegisterLinks()
+FilingEngine + ai_classifier.enrich() + category tree traversal

@@ INTEGRITY @@
-ContentHash + Git-like versioning on node
+S3 key + version column + transactional DB boundary"""))
    s.append(Paragraph(
        "<b>Designer reading:</b> Grok = coordinate on the stack (A-101a). RAND = row referenced by half a dozen services.",
        styles["body"],
    ))
    s.append(PageBreak())

    # Filing diff
    s.extend(slide_title_block(styles, "Filing & Sorting .diff", "11:00 – 15:00"))
    s.extend(diff_block(styles, """--- Grok: SortDocuments()
+++ RAND: sort_documents() + SortInterpreter

- QueryRegisterIndex(query) → ApplyNumericOrder → SerendipityBoost(Links)
+ sorted(docs, composite_key) → ml_relevance_rerank(query_intent)
+ SQL ORDER BY category, upload_date, title (dynamic CASE)"""))
    s.append(Spacer(1, 0.1 * inch))
    s.append(make_table([
        ["Query", "Stacking", "Collision"],
        ["Facade studies", "Keyword register → numeric reorder", "Full-text + embedding + ML rerank"],
        ["Near sheet 7-4", "FetchBranch(\"7-4*\")", "Category + JSONB + Elasticsearch"],
        ["Surprise links", "SerendipityBoost(Links)", "Faceted tags + AccessLog analytics"],
    ], col_widths=[1.8 * inch, 3.1 * inch, 3.1 * inch]))
    s.append(PageBreak())

    # Distribution diff
    s.extend(slide_title_block(styles, "Distribution & Sync .diff", "15:00 – 18:00"))
    s.extend(diff_block(styles, """--- Grok Layer 3–4
+++ RAND DistributionEngine

-BroadcastToConnectedClients(node.ID, "filed", numericID)
+generate_distribution_link() → token_urlsafe(32) → email notification
+re-check permissions on EVERY access

-API /sort?prefix=7-4 → RenderAsTree(nodes)
+POST /api/v1/distribution/documents/{id}/share
+GET /share/{token} → StreamingResponse from object storage"""))
    s.append(Paragraph(
        "<b>Stacking:</b> pin a sheet on the studio wall—same coordinate moves in real time. "
        "<b>Collision:</b> time-limited portal; security, storage, audit align per request.",
        styles["body"],
    ))
    s.append(PageBreak())

    # Query diff
    s.extend(slide_title_block(styles, "Query Interpreter .diff", "18:00 – 21:00"))
    s.extend(diff_block(styles, """RAND SDD — 7-step pipeline:
  Security → Category → Metadata → Full-Text → Sort → Distribution → Pagination

Grok — 4-hop chain:
  ParseNumericQuery → StorageLayer.Fetch → ApplyContentAwareness → RenderForEndUser

@@ COUPLING @@
-Single chain: storage ⊥ logic ⊥ UI
+5 layers: Presentation → Gateway → Business → Data → Audit (more collision surfaces)"""))
    s.append(PageBreak())

    # Visualization
    s.extend(slide_title_block(styles, "Visualization for Designers", "21:00 – 24:00"))
    s.extend(diff_block(styles, """Grok — Numeric Tree (stacking visible):
1 → 1-1 → 1-1a → 1-1a1b (render pass)

RAND SDD — Dashboard flow:
Upload → AI Tags → [Category | Tags] → NL Search → ML Grid → Share Modal"""))
    s.append(Paragraph(
        "<b>Exercise:</b> Sketch your last project as both diagrams. Where would collision hurt? "
        "(texture duplicated in S3, Elasticsearch, local cache with different timestamps.)",
        styles["body"],
    ))
    s.append(PageBreak())

    # Workshop
    s.extend(slide_title_block(styles, "Workshop — Competition Submission", "24:00 – 27:00"))
    s.append(make_table([
        ["Step", "Stacking", "Collision"],
        ["Ingest plates", "7-4a slot beside elevation", "file_document + AI category"],
        ["Sort", "Numeric prefix + keyword", "ML rerank on brief"],
        ["Share with jury", "Link /7-4a + live sync", "72h token, view-only RBAC"],
        ["Find sketches", "Follow Links serendipity", "Faceted tags + analytics"],
    ], col_widths=[1.5 * inch, 3.3 * inch, 3.3 * inch]))
    s.append(Spacer(1, 0.12 * inch))
    s.extend(diff_block(styles, """+ duplex-numeric IDs for sheet discipline
+ object storage + expiring links for clients
+ one mandatory register — never folder names alone
- duplicate metadata across Redis, ES, DB without source of truth"""))
    s.append(PageBreak())

    # Roadmap
    s.extend(slide_title_block(styles, "Implementation Roadmap .diff", "27:00 – 29:00"))
    s.extend(diff_block(styles, """Grok bootstrap:
  1. SQLite/PostgreSQL + full-text register
  2. PDF/DOCX interpreter  3. Docker + React/Flask
  4. ID Generator  5. Test: Ingest → IDs → Search → Branch

RAND Phase 1–4 (16 weeks):
  Wk 1-4:  PostgreSQL + MinIO + file_document()
  Wk 5-8:  SortInterpreter + Elasticsearch
  Wk 9-12: Distribution + RBAC + audit
  Wk 13-16: AI classification + ML rerank"""))
    s.append(Paragraph(
        "<b>Solo designer starter:</b> stacking IDs + single SQLite register. "
        "Add collision services when multi-user sharing and ML search justify ops cost.",
        styles["body"],
    ))
    s.append(PageBreak())

    # Takeaways
    s.extend(slide_title_block(styles, "Key Takeaways", "29:00 – 30:00"))
    s.append(make_table([
        ["", "Neat Stacking", "Cloud Collision"],
        ["Strength", "Predictable coords, serendipitous links", "Scale, compliance, ML"],
        ["Risk", "Register neglect", "Metadata drift across services"],
        ["Best for", "Archive-heavy digital arts", "Multi-tenant studio platform"],
        ["Visual", "Index-card wall, Z-ordered sheets", "Service topology diagram"],
    ], col_widths=[1.3 * inch, 3.35 * inch, 3.35 * inch]))
    s.append(Spacer(1, 0.15 * inch))
    s.extend(diff_block(styles, """--- grok_report-2
+++ RAND_System_Design_Document

- duplex-numeric fixed placement + mandatory register
+ relational schema + AI enrichment + microservice interpreters

Both inherit RAND/Luhmann DNA: metadata over folder superstition.
Difference = geometry vs. gravity — stack into coordinates or collide through distributed engines."""))
    return s


def main():
    styles = build_styles()
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=landscape(A4),
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN + 0.2 * inch, bottomMargin=MARGIN + 0.15 * inch,
        title="Stacking vs. Cloud Collision — Digital Arts Tutorial",
        author="Comparative .diff Tutorial",
    )
    doc.build(build_story(styles), onFirstPage=on_page, onLaterPages=on_page)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()