"""Generate a supervisor-ready progress report PDF."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
PLOTS = ROOT / "runs" / "reports" / "plots"
OUT = ROOT / "progress_report.pdf"

# ── Colour palette ────────────────────────────────────────────────────────────
NAVY = colors.HexColor("#1a2e52")
BLUE = colors.HexColor("#2563eb")
LIGHT_BLUE = colors.HexColor("#dbeafe")
MID_GREY = colors.HexColor("#6b7280")
LIGHT_GREY = colors.HexColor("#f3f4f6")
GREEN = colors.HexColor("#16a34a")
AMBER = colors.HexColor("#d97706")
RED = colors.HexColor("#dc2626")
WHITE = colors.white

W, H = A4


# ── Styles ────────────────────────────────────────────────────────────────────
def build_styles():
    base = getSampleStyleSheet()
    s = {}
    s["cover_title"] = ParagraphStyle(
        "cover_title",
        fontSize=22,
        leading=28,
        textColor=NAVY,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        spaceAfter=8,
    )
    s["cover_sub"] = ParagraphStyle(
        "cover_sub",
        fontSize=13,
        leading=18,
        textColor=BLUE,
        alignment=TA_CENTER,
        fontName="Helvetica",
        spaceAfter=6,
    )
    s["cover_meta"] = ParagraphStyle(
        "cover_meta",
        fontSize=10,
        leading=14,
        textColor=MID_GREY,
        alignment=TA_CENTER,
        fontName="Helvetica",
    )
    s["section"] = ParagraphStyle(
        "section",
        fontSize=14,
        leading=18,
        textColor=NAVY,
        fontName="Helvetica-Bold",
        spaceBefore=16,
        spaceAfter=6,
    )
    s["subsection"] = ParagraphStyle(
        "subsection",
        fontSize=11,
        leading=15,
        textColor=BLUE,
        fontName="Helvetica-Bold",
        spaceBefore=10,
        spaceAfter=4,
    )
    s["body"] = ParagraphStyle(
        "body",
        fontSize=10,
        leading=14,
        textColor=colors.black,
        alignment=TA_JUSTIFY,
        fontName="Helvetica",
        spaceAfter=4,
    )
    s["bullet"] = ParagraphStyle(
        "bullet",
        parent=s["body"],
        leftIndent=14,
        bulletIndent=4,
        spaceAfter=2,
    )
    s["caption"] = ParagraphStyle(
        "caption",
        fontSize=8,
        leading=11,
        textColor=MID_GREY,
        alignment=TA_CENTER,
        fontName="Helvetica-Oblique",
        spaceAfter=8,
    )
    s["table_header"] = ParagraphStyle(
        "table_header",
        fontSize=9,
        leading=11,
        textColor=WHITE,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    )
    s["table_cell"] = ParagraphStyle(
        "table_cell",
        fontSize=9,
        leading=11,
        textColor=colors.black,
        fontName="Helvetica",
        alignment=TA_CENTER,
    )
    s["table_cell_l"] = ParagraphStyle(
        "table_cell_l",
        parent=s["table_cell"],
        alignment=TA_LEFT,
    )
    s["highlight"] = ParagraphStyle(
        "highlight",
        fontSize=10,
        leading=14,
        textColor=NAVY,
        fontName="Helvetica-Bold",
        backColor=LIGHT_BLUE,
        borderPad=6,
        spaceAfter=6,
    )
    return s


# ── Helper builders ───────────────────────────────────────────────────────────
def section_rule():
    return HRFlowable(width="100%", thickness=1.5, color=BLUE, spaceAfter=4)


def divider():
    return HRFlowable(width="100%", thickness=0.5, color=LIGHT_GREY, spaceAfter=6)


def phase_badge(label: str, status: str, s) -> Table:
    """Coloured status badge for a phase row."""
    colour = GREEN if status == "Complete" else AMBER if status == "In Progress" else MID_GREY
    data = [[
        Paragraph(f"<b>{label}</b>", s["table_cell_l"]),
        Paragraph(f"<b>{status}</b>", ParagraphStyle("badge", parent=s["table_cell"],
                                                     textColor=colour, fontName="Helvetica-Bold")),
    ]]
    t = Table(data, colWidths=[13 * cm, 4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT_GREY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MID_GREY),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (0, -1), 8),
    ]))
    return t


def data_table(headers, rows, col_widths, s, zebra=True) -> Table:
    header_row = [Paragraph(h, s["table_header"]) for h in headers]
    body_rows = []
    for row in rows:
        body_rows.append([Paragraph(str(c), s["table_cell"]) for c in row])
    all_rows = [header_row] + body_rows
    t = Table(all_rows, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.5, MID_GREY),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
    ]
    if zebra:
        for i in range(1, len(all_rows)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), LIGHT_GREY))
    t.setStyle(TableStyle(style))
    return t


def try_image(path: Path, width_cm: float, caption: str, s) -> list:
    if path.exists():
        img = Image(str(path), width=width_cm * cm, height=width_cm * cm * 0.6)
        return [img, Paragraph(caption, s["caption"])]
    return [Paragraph(f"<i>[Figure not found: {path.name}]</i>", s["caption"])]


# ── Page template ─────────────────────────────────────────────────────────────
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, H - 1.2 * cm, W, 1.2 * cm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(1.5 * cm, H - 0.75 * cm,
                      "Coordinating Speculative Agent Workloads — MSc Progress Report")
    canvas.drawRightString(W - 1.5 * cm, H - 0.75 * cm, f"Page {doc.page}")

    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, W, 0.7 * cm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(W / 2, 0.22 * cm, f"Confidential — Supervisor Review — {date.today().strftime('%B %Y')}")
    canvas.restoreState()


# ── Content builders ──────────────────────────────────────────────────────────
def build_cover(s) -> list:
    story = []
    story.append(Spacer(1, 3.5 * cm))
    story.append(Paragraph("MSc Research Progress Report", s["cover_sub"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "Coordinating Speculative Agent Workloads<br/>Over Data Backends",
        s["cover_title"],
    ))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="60%", thickness=2, color=BLUE, spaceAfter=10))
    story.append(Paragraph(
        "Middleware coordination policies for redundancy elimination<br/>"
        "in multi-agent BIRD text-to-SQL workloads",
        s["cover_sub"],
    ))
    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph(f"Prepared: {date.today().strftime('%d %B %Y')}", s["cover_meta"]))
    story.append(Paragraph("Author: gorenkinp@gmail.com", s["cover_meta"]))
    story.append(Paragraph("Programme: MSc Computer Science", s["cover_meta"]))
    story.append(Spacer(1, 3 * cm))

    # Quick-look status table on cover
    headers = ["Phase", "Status", "Key Deliverable"]
    rows = [
        ["Phase 0 — Scaffold", "✓ Complete", "Repo, CI, BIRD data, configs"],
        ["Phase 1a — Gold SQL / EX metric", "✓ Complete", "Execution accuracy harness"],
        ["Phase 1b — JSONL traces", "✓ Complete", "Per-run trace schema"],
        ["Phase 1c — Single-agent loop", "✓ Complete", "Tool-calling agent (3 models)"],
        ["Phase 2 — Parallel agents (P0)", "✓ Complete", "N-replica coordinator + metrics"],
        ["Phase 2a — Baseline redundancy", "✓ Complete", "Chapter 2 draft + plots"],
        ["Early-stop optimisation", "✓ Complete", "Cost reduction analysis"],
        ["Phase P1–P4 Middleware", "Planned", "Shared cache, sub-expr dedup"],
    ]
    cw = [6.5 * cm, 3.5 * cm, 7 * cm]
    story.append(data_table(headers, rows, cw, s))
    story.append(PageBreak())
    return story


def build_overview(s) -> list:
    story = []
    story.append(Paragraph("1. Project Overview", s["section"]))
    story.append(section_rule())
    story.append(Paragraph(
        "This MSc research investigates <b>middleware coordination policies</b> for multi-agent "
        "LLM systems that perform text-to-SQL translation over relational databases. The central "
        "hypothesis is that independent parallel agents waste substantial work through redundant "
        "database exploration, and that lightweight middleware — shared caches, early stopping, "
        "sub-expression propagation — can eliminate this waste while preserving or improving "
        "answer quality.",
        s["body"],
    ))
    story.append(Paragraph(
        "The benchmark is <b>BIRD</b> (Benchmark for Intelligent Reasoning over Diverse databases), "
        "specifically the mini-dev split (500 tasks, 11 SQLite databases). The evaluation metric is "
        "<b>Execution Accuracy (EX)</b>: the fraction of tasks where the agent's submitted SQL "
        "returns a result set matching the gold answer.",
        s["body"],
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Research questions", s["subsection"]))
    bullets = [
        "How much redundant database exploration occurs when N identical agents solve the same task independently (baseline P0)?",
        "Does early stopping (cancel sibling replicas when one finds a correct answer) reduce token cost without harming EX?",
        "Can shared SQL result caches (P1) eliminate duplicate explore queries, and by how much?",
        "Do richer coordination policies (P2–P4: sub-expression sharing, majority vote, ensemble) further reduce cost or improve accuracy?",
    ]
    for b in bullets:
        story.append(Paragraph(f"• {b}", s["bullet"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Models under evaluation", s["subsection"]))
    headers = ["Registry Key", "Provider", "API Model ID", "Role"]
    rows = [
        ["gpt-4o-mini", "OpenAI", "gpt-4o-mini", "Primary baseline"],
        ["gemini-2.5-flash", "Google", "gemini-2.5-flash", "Evaluation matrix"],
        ["deepseek-v3.2", "DeepSeek", "deepseek-chat (V3.2)", "Evaluation matrix"],
    ]
    cw = [4 * cm, 3.5 * cm, 5 * cm, 4.5 * cm]
    story.append(data_table(headers, rows, cw, s))
    story.append(Spacer(1, 0.2 * cm))
    return story


def build_architecture(s) -> list:
    story = []
    story.append(Paragraph("2. System Architecture", s["section"]))
    story.append(section_rule())
    story.append(Paragraph(
        "The codebase follows a layered architecture. The innermost layer is a thin "
        "<b>SQLite execution harness</b> that matches the official BIRD evaluation logic. "
        "Above it sits an <b>LLM client</b> with provider-agnostic retry/backoff supporting "
        "OpenAI, Google Gemini, and DeepSeek via their respective SDKs. The <b>agent loop</b> "
        "implements a tool-calling cycle with two tools: <code>execute_sql</code> (read-only "
        "exploration) and <code>submit_sql</code> (final answer). A <b>coordination layer</b> "
        "spawns N replicas in a thread pool and applies a selection policy once all "
        "(or enough) replicas complete.",
        s["body"],
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Key source modules", s["subsection"]))
    headers = ["Module", "Path", "Responsibility"]
    rows = [
        ["LLM client", "src/llm/client.py", "Provider-agnostic chat completions"],
        ["Retry/backoff", "src/llm/retry.py", "Exponential backoff, rate-limit handling"],
        ["Agent loop", "src/agent/loop.py", "Tool-calling loop, turn tracking, traces"],
        ["Coordination", "src/coord/parallel.py", "Thread pool, early-stop logic"],
        ["Policies", "src/coord/policies.py", "best_of_n, first_success, majority_vote"],
        ["Redundancy analysis", "src/coord/redundancy.py", "String + AST dedup, sub-expr overlap"],
        ["Baseline plots", "src/coord/baseline_plots.py", "Matplotlib scaling-curve figures"],
        ["Config", "src/config.py", "Pydantic settings, YAML loading"],
        ["BIRD tasks", "src/bird/tasks.py", "Task loader, SQLite path resolution"],
        ["SQLite exec", "src/db/sqlite_exec.py", "Timeout-guarded execution"],
    ]
    cw = [4 * cm, 5.5 * cm, 7.5 * cm]
    story.append(data_table(headers, rows, cw, s))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("JSONL trace schema", s["subsection"]))
    story.append(Paragraph(
        "Every agent run writes a structured JSONL trace to <code>runs/&lt;run_id&gt;.jsonl</code>. "
        "Coordinator runs additionally write <code>runs/coord_&lt;id&gt;.jsonl</code>. "
        "Traces record all events needed for offline redundancy analysis:",
        s["body"],
    ))
    headers2 = ["Event", "Key fields"]
    rows2 = [
        ["run_start", "question_id, db_id, policy, seed, bird_split, agent_id"],
        ["sql_execute", "sql_raw, sql_role, latency_ms, row_count, result_sample, error"],
        ["run_end", "ex_correct, predicted_sql, gold_sql, wall_clock_ms"],
        ["parallel_start", "replicas, policy, early_stop flag"],
        ["coordination_end", "selected_agent_id, redundancy metrics, token totals"],
    ]
    cw2 = [4.5 * cm, 12.5 * cm]
    story.append(data_table(headers2, rows2, cw2, s))
    return story


def build_phase_progress(s) -> list:
    story = []
    story.append(Paragraph("3. Phase-by-Phase Progress", s["section"]))
    story.append(section_rule())

    phases = [
        ("Phase 0 — Project Scaffold", "Complete",
         "Repository structure, CI configuration (pytest), uv dependency management, "
         "BIRD mini-dev download scripts, YAML configuration system (Pydantic), "
         "model registry (<code>configs/models.yaml</code>), and environment setup "
         "verified across all three LLM providers."),
        ("Phase 1a — Gold SQL & Execution Accuracy", "Complete",
         "SQLite execution harness matching official BIRD <code>evaluation.py</code> logic. "
         "Gold-vs-gold sanity check (20/20 EX=1 confirmed). Scripts: "
         "<code>run_one_gold.py</code>, <code>run_gold_sanity.py</code>."),
        ("Phase 1b — JSONL Traces", "Complete",
         "Structured event logging for every agent run. Schema covers run lifecycle, "
         "all SQL executions (with latency and row counts), and final evaluation. "
         "Offline inspection via <code>scripts/inspect_trace.py</code>."),
        ("Phase 1c — Single-Agent Loop", "Complete",
         "Tool-calling agent with <code>execute_sql</code> / <code>submit_sql</code> tools. "
         "Validated on all three models. Batch runner with CSV/JSON output "
         "(<code>run_batch.py</code>). LLM retry/backoff layer added (exponential, "
         "jitter, per-provider rate-limit detection)."),
        ("Phase 2 — Parallel Agent Coordinator", "Complete",
         "Thread-pool N-replica launcher with three selection policies: "
         "<b>best_of_n</b> (fewest-turn correct replica), <b>first_success</b> "
         "(first EX=1 replica), <b>majority_vote</b> (result-set bucket voting). "
         "Per-replica and coordinator JSONL traces. Redundancy metrics computed "
         "inline (string + AST dedup, token overhead ratio)."),
        ("Phase 2a — Baseline Redundancy Analysis (P0)", "Complete",
         "Replica-count sweep (N ∈ {3, 10, 25}) across all three models on 50-task "
         "smoke subset. Full redundancy report suite: explore duplication, "
         "sub-expression overlap, token overhead, wall-clock. Six scaling-curve "
         "figures (Matplotlib). Chapter 2 thesis draft auto-generated "
         "(<code>scripts/generate_chapter2_draft.py</code>)."),
        ("Early-Stop Optimisation", "Complete",
         "Early stopping (cancel sibling replicas when one achieves EX=1) evaluated "
         "apples-to-apples vs P0 at N=10. Key finding: DeepSeek saves <b>14.3% "
         "tokens</b> with no EX loss; Gemini saves 2.5%; GPT-4o mini shows marginal "
         "increase due to pre-emption timing."),
        ("Eval Matrix (all models × variations)", "Complete",
         "Concurrent matrix runner (<code>run_eval_matrix.py</code>) executing "
         "single-agent and parallel variations across all three models simultaneously. "
         "Manifest JSON aggregates all batch results."),
    ]

    for title, status, desc in phases:
        story.append(KeepTogether([
            phase_badge(title, status, s),
            Spacer(1, 0.15 * cm),
            Paragraph(desc, s["body"]),
            Spacer(1, 0.2 * cm),
        ]))
    return story


def build_results(s) -> list:
    story = []
    story.append(PageBreak())
    story.append(Paragraph("4. Key Experimental Results", s["section"]))
    story.append(section_rule())

    story.append(Paragraph("4.1 Baseline Redundancy (P0)", s["subsection"]))
    story.append(Paragraph(
        "The P0 baseline runs N independent replicas with no shared state. "
        "Results below are on the 50-task BIRD mini-dev smoke subset with "
        "<code>best_of_n</code> coordination policy.",
        s["body"],
    ))
    story.append(Spacer(1, 0.2 * cm))

    # Main results table
    headers = ["Replicas", "DeepSeek EX%", "DeepSeek Redund%", "Gemini EX%",
               "Gemini Redund%", "GPT-4o mini EX%", "GPT-4o mini Redund%"]
    rows = [
        ["3",  "60.0", "54.1%", "72.0", "45.9%", "58.0", "50.9%"],
        ["10", "60.0", "71.3%", "74.0", "73.6%", "58.0", "78.5%"],
        ["25", "64.0", "82.9%", "70.0†", "81.5%", "36.0†", "90.2%"],
    ]
    cw = [2 * cm, 2.5 * cm, 2.8 * cm, 2.5 * cm, 2.8 * cm, 2.7 * cm, 2.7 * cm]
    story.append(data_table(headers, rows, cw, s))
    story.append(Paragraph(
        "† API failures at N=25: Gemini 3 tasks, GPT-4o mini 14 tasks. "
        "EX on completed tasks: Gemini 74.5%, GPT-4o mini 50.0%.",
        s["caption"],
    ))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Token overhead (N=3 vs N=25):", s["subsection"]))
    headers2 = ["Model", "Tokens at N=3", "Tokens at N=25", "Growth", "Overhead at N=25"]
    rows2 = [
        ["DeepSeek V3.2", "2,193,564", "18,889,223", "8.6×", "32.66×"],
        ["Gemini 2.5 Flash", "463,742", "3,685,459", "7.9×", "26.55×"],
        ["GPT-4o mini", "732,572", "4,026,175", "5.5×", "25.97×"],
    ]
    cw2 = [4 * cm, 3.5 * cm, 3.5 * cm, 2 * cm, 4 * cm]
    story.append(data_table(headers2, rows2, cw2, s))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("4.2 Early-Stop vs P0 (N=10)", s["subsection"]))
    story.append(Paragraph(
        "Early stopping cancels remaining replicas as soon as one achieves EX=1. "
        "Evaluated at N=10 with <code>best_of_n</code> policy (identical to P0 baseline).",
        s["body"],
    ))
    headers3 = ["Model", "P0 EX%", "ES EX%", "P0 Redund%", "ES Redund%",
                "P0 Tokens", "ES Tokens", "Token Δ", "ES Triggered"]
    rows3 = [
        ["GPT-4o mini", "58.0", "60.0", "78.5%", "77.8%", "2,400,807", "2,432,022", "+1.3%", "30/50"],
        ["Gemini 2.5 Flash", "74.0", "74.0", "73.6%", "73.6%", "1,568,278", "1,529,204", "−2.5%", "37/50"],
        ["DeepSeek V3.2", "60.0", "60.0", "71.3%", "75.0%", "7,792,210", "6,676,709", "−14.3%", "30/50"],
    ]
    cw3 = [3.3 * cm, 1.7 * cm, 1.7 * cm, 2.2 * cm, 2.2 * cm, 2.8 * cm, 2.8 * cm, 1.8 * cm, 2.5 * cm]
    story.append(data_table(headers3, rows3, cw3, s))
    story.append(Paragraph(
        "DeepSeek V3.2 benefits most (−14.3% tokens, 30/50 tasks triggered, avg 5.1 replicas cancelled). "
        "GPT-4o mini shows marginal increase due to pre-emption timing at N=10.",
        s["caption"],
    ))
    return story


def build_figures(s) -> list:
    story = []
    story.append(PageBreak())
    story.append(Paragraph("5. Scaling-Curve Figures", s["section"]))
    story.append(section_rule())
    story.append(Paragraph(
        "All figures below are generated from the P0 baseline sweep "
        "(N ∈ {3, 10, 25}, three models, 50-task BIRD mini-dev smoke subset).",
        s["body"],
    ))
    story.append(Spacer(1, 0.3 * cm))

    fig_pairs = [
        ("baseline_overview.png",
         "Figure 1. P0 baseline overview: four-panel summary across all models and replica counts."),
        ("baseline_explore_redundancy.png",
         "Figure 2. Mean explore-query redundancy vs replica count. "
         "Redundancy exceeds 80% at N=25 for all models."),
        ("baseline_subexpr_overlap.png",
         "Figure 3. Sub-expression overlap: shared tables/columns/predicates across replicas. "
         "Reaches 84–94% at N=3 already."),
        ("baseline_token_overhead.png",
         "Figure 4. Token overhead ratio (total tokens / cheapest correct replica). "
         "Approaches 26–33× at N=25."),
        ("baseline_wall_clock_s.png",
         "Figure 5. Wall-clock time vs replica count. Sub-linear scaling due to concurrency; "
         "DeepSeek higher due to longer per-replica latency."),
        ("baseline_ex_accuracy.png",
         "Figure 6. Execution accuracy vs replica count. "
         "Dashed lines exclude API-failure tasks at N=25."),
    ]

    for i in range(0, len(fig_pairs), 2):
        pair = fig_pairs[i:i + 2]
        row_content = []
        for fname, caption in pair:
            path = PLOTS / fname
            cell = []
            if path.exists():
                cell.append(Image(str(path), width=8.2 * cm, height=5.5 * cm))
            else:
                cell.append(Paragraph(f"<i>[{fname} not found]</i>", s["caption"]))
            cell.append(Spacer(1, 0.1 * cm))
            cell.append(Paragraph(caption, s["caption"]))
            row_content.append(cell)
        if len(row_content) == 1:
            row_content.append([""])
        fig_table = Table([row_content], colWidths=[8.5 * cm, 8.5 * cm])
        fig_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(fig_table)
        story.append(Spacer(1, 0.4 * cm))
    return story


def build_findings(s) -> list:
    story = []
    story.append(PageBreak())
    story.append(Paragraph("6. Key Findings", s["section"]))
    story.append(section_rule())

    findings = [
        ("Redundancy is the dominant cost of parallel agents",
         "At N=10, roughly four out of five explore queries are duplicates. Token spend scales "
         "linearly with N (~10× at N=10, ~25–33× at N=25) while EX% moves only a few points. "
         "Parallelism buys reliability at a large and measurable token premium."),
        ("Unique exploration saturates quickly",
         "The count of distinct explore SQL strings plateaus far below total explore volume. "
         "For Gemini, unique queries increase only 16% from N=3 to N=25 while total volume "
         "grows 7.9×. Replicas are not discovering more of the search space — they are "
         "re-executing the same probes."),
        ("Sub-expression overlap motivates fragment-level middleware",
         "String-level deduplication (P1) handles exact copies; the 84–94% sub-expression "
         "overlap at N=3 already shows that replicas share tables, columns, and predicates "
         "even when full SQL strings differ. This motivates P2 (fragment-level sharing)."),
        ("Early stopping saves tokens without harming accuracy",
         "At N=10, DeepSeek V3.2 saves 14.3% of total tokens with zero EX loss. "
         "Gemini saves 2.5%. Early stopping is a simple, safe optimisation that should "
         "always be enabled in production-like deployments."),
        ("API reliability degrades at high N",
         "GPT-4o mini at N=25 saw 14/50 tasks fail at the API layer (all retries exhausted), "
         "dropping headline EX from 50% (completed tasks only) to 36% (all tasks). "
         "Any high-N deployment must account for replica failure modes."),
    ]

    for i, (title, body) in enumerate(findings, 1):
        story.append(KeepTogether([
            Paragraph(f"<b>Finding {i}: {title}</b>", s["highlight"]),
            Paragraph(body, s["body"]),
            Spacer(1, 0.15 * cm),
        ]))

    return story


def build_next_steps(s) -> list:
    story = []
    story.append(Paragraph("7. Planned Next Steps", s["section"]))
    story.append(section_rule())
    story.append(Paragraph(
        "The remaining thesis phases build the middleware stack on top of the P0 baseline "
        "established in Phases 0–2a:",
        s["body"],
    ))
    story.append(Spacer(1, 0.2 * cm))

    phases = [
        ("P1 — Shared SQL Result Cache",
         "A server-side LRU cache keyed by AST-normalised SQL. When a replica submits an "
         "explore query already executed by another replica, return the cached result set "
         "immediately without a database round-trip. Expected to eliminate the ~50–90% of "
         "duplicate string-identical queries measured in P0."),
        ("P2 — Sub-Expression Propagation",
         "Extend P1 to share individual SQL fragments (table probes, predicate evaluations, "
         "join patterns) across replicas even when full SQL strings differ. Targets the "
         "85–94% sub-expression overlap observed at N=3."),
        ("P3/P4 — Richer Coordination Policies",
         "Evaluate majority_vote and cross-model ensemble coordination. "
         "Investigate whether sharing intermediate results (not just caching) changes "
         "the exploration frontier and improves EX%."),
        ("Scale-up to Full BIRD Dev",
         "Re-run the baseline sweep and all middleware policies on the full 1,534-task "
         "BIRD dev set to validate that smoke-subset magnitudes generalise."),
        ("Thesis Write-up",
         "Chapters 3–5 covering P1–P4 middleware evaluation; "
         "Chapter 6 discussion and conclusions."),
    ]

    for title, desc in phases:
        story.append(Paragraph(f"<b>{title}</b>", s["subsection"]))
        story.append(Paragraph(desc, s["body"]))
        story.append(Spacer(1, 0.1 * cm))
    return story


def build_artefacts(s) -> list:
    story = []
    story.append(PageBreak())
    story.append(Paragraph("8. Repository Artefacts", s["section"]))
    story.append(section_rule())
    story.append(Paragraph(
        "All code, data, traces, and reports are versioned in the project repository. "
        "Key artefacts produced to date:",
        s["body"],
    ))
    story.append(Spacer(1, 0.2 * cm))

    headers = ["Artefact", "Location", "Description"]
    rows = [
        ["Source modules", "src/", "Agent loop, LLM client, coord policies, BIRD loader"],
        ["Test suite", "tests/", "pytest unit tests (~15 test files)"],
        ["Scripts", "scripts/", "18 runnable scripts covering all eval phases"],
        ["Configs", "configs/", "YAML config, model registry, subset files"],
        ["BIRD mini-dev", "data/bird/mini_dev/", "500-task dev set, 11 SQLite databases"],
        ["Agent traces", "runs/*.jsonl", "Per-run JSONL traces (hundreds of files)"],
        ["Batch CSVs/JSONs", "runs/batches/", "28+ batch result files across models"],
        ["Baseline reports", "runs/reports/", "10 Markdown + JSON analysis reports"],
        ["Scaling plots", "runs/reports/plots/", "6 publication-quality PNG figures"],
        ["Chapter 2 draft", "thesis/chapter2_baseline_redundancy.md", "Thesis-ready write-up with embedded figures"],
        ["Progress report", "progress_report.pdf", "This document"],
    ]
    cw = [4 * cm, 5.5 * cm, 7.5 * cm]
    story.append(data_table(headers, rows, cw, s))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "Git history: 2 commits to date. "
        "Branch: <code>main</code>. "
        "Working tree has active modifications across all core modules "
        "(retry logic, batch pacing, Gemini 2.5 migration complete).",
        s["body"],
    ))
    return story


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=2 * cm,
        bottomMargin=1.8 * cm,
        title="MSc Progress Report — Coordinating Speculative Agent Workloads",
        author="gorenkinp@gmail.com",
        subject="BIRD text-to-SQL multi-agent middleware research",
    )

    s = build_styles()
    story = []
    story += build_cover(s)
    story += build_overview(s)
    story += build_architecture(s)
    story += build_phase_progress(s)
    story += build_results(s)
    story += build_figures(s)
    story += build_findings(s)
    story += build_next_steps(s)
    story += build_artefacts(s)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"PDF written to: {OUT}")


if __name__ == "__main__":
    main()
