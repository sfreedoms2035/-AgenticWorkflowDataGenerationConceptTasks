"""
pipeline.py — Master Orchestrator for AD/ADAS Coding Task Generation
=====================================================================
Single entry point that automates the entire PDF → 16 tasks pipeline:
  1. Scans Input/ for PDFs
  2. Classifies each PDF as Technical or Regulatory
  3. For each PDF, runs 8 turns × 2 tasks = 16 tasks
  4. Each task: generate prompt → Playwright → validate → auto-repair → retry
  5. Max 3 Gemini attempts per task; local repair between each attempt
  6. Dashboard generated after every completed PDF (8 tasks)
  7. Tracks progress in Output/progress.json for resume support

  TERMS MODE (--terms):
  Uses Input_terms/Terms.md instead of PDFs, activates Gemini Deep Think
  model, and writes outputs to separate _terms directories.

Usage:
    python pipeline.py                              # Process all PDFs
    python pipeline.py --pdf "specific.pdf"          # Process one PDF
    python pipeline.py --resume                      # Resume from last checkpoint
    python pipeline.py --pdf "file.pdf" --turn 3     # Start from Turn 3
    python pipeline.py --validate-only               # Just validate existing outputs
    python pipeline.py --no-dashboard                # Skip dashboard generation
    python pipeline.py --terms                       # Terms mode (Deep Think)
    python pipeline.py --terms --resume              # Resume terms mode
"""
import os
import sys

DEEP_THINK_MODE = False
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

import json
import glob
import subprocess
import argparse
import time
import statistics
import webbrowser
import re
from datetime import datetime


# ── Configuration ────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "Input")
OUTPUT_JSON_DIR = os.path.join(BASE_DIR, "Output", "json")
OUTPUT_THINK_DIR = os.path.join(BASE_DIR, "Output", "thinking")
EVAL_DIR = os.path.join(BASE_DIR, "Eval")
PROMPTS_DIR = os.path.join(BASE_DIR, ".agent", "prompts")
SCRIPTS_DIR = os.path.join(BASE_DIR, ".agent", "scripts")
PROGRESS_FILE = os.path.join(BASE_DIR, "Output", "progress.json")
STATISTICS_FILE = os.path.join(BASE_DIR, "Output", "statistics.json")
DASHBOARD_OUTPUT = os.path.join(BASE_DIR, "Output", "dashboard.html")

# ── Terms Mode Configuration ─────────────────────────────────────────────────
INPUT_TERMS_DIR = os.path.join(BASE_DIR, "Input_terms")
OUTPUT_JSON_TERMS_DIR = os.path.join(BASE_DIR, "Output", "json_terms")
OUTPUT_THINK_TERMS_DIR = os.path.join(BASE_DIR, "Output", "thinking_terms")
EVAL_TERMS_DIR = os.path.join(BASE_DIR, "Eval_terms")
PROMPTS_TERMS_DIR = os.path.join(BASE_DIR, "Output", "prompts_terms")
PROGRESS_TERMS_FILE = os.path.join(BASE_DIR, "Output", "progress_terms.json")
STATISTICS_TERMS_FILE = os.path.join(BASE_DIR, "Output", "statistics_terms.json")

PLAYWRIGHT_SCRIPT = os.path.join(BASE_DIR, "run_gemini_playwright_v2.py")
VALIDATE_SCRIPT = os.path.join(SCRIPTS_DIR, "validate_task.py")
AUTO_REPAIR_SCRIPT = os.path.join(SCRIPTS_DIR, "auto_repair.py")
PARTIAL_REPAIR_SCRIPT = os.path.join(SCRIPTS_DIR, "partial_repair.py")
DASHBOARD_SCRIPT = os.path.join(SCRIPTS_DIR, "generate_dashboard.py")

MAX_GEMINI_ATTEMPTS = 3  # Max Gemini re-prompts per task


# ── Variation Schema ─────────────────────────────────────────────────────────
# Each turn produces 2 tasks. Schema: (domain, difficulty, meta_strategy, role)
VARIATION_TECHNICAL = {
    1: [("Concept", 98, "Theoretical Background",   "Senior Software Architect"),
        ("Concept", 92, "Critique of the Approach", "Senior Software Architect")],
    2: [("Concept", 96, "Benchmarking",             "Senior System Engineer"),
        ("Concept", 90, "Further Improvement",      "Senior System Engineer")],
    3: [("Concept", 85, "Practical Usage",          "Senior Safety Manager"),
        ("Concept", 95, "Reverse Engineering",      "Senior Safety Manager")],
    4: [("Concept", 84, "Edge-Case Stressing",      "Senior Validation Engineer"),
        ("Concept", 91, "Integration & Scaling",    "Senior Validation Engineer")],
    5: [("Concept", 88, "Theoretical Background",   "Senior Integration Engineer"),
        ("Concept", 93, "Critique of the Approach", "Senior Integration Engineer")],
    6: [("Concept", 89, "Benchmarking",             "Senior Project Manager"),
        ("Concept", 94, "Further Improvement",      "Senior Project Manager")],
    7: [("Concept", 97, "Practical Usage",          "Senior DevOps Engineer"),
        ("Concept", 86, "Reverse Engineering",      "Senior DevOps Engineer")],
    8: [("Concept", 82, "Edge-Case Stressing",      "Senior Requirements Engineering Manager"),
        ("Concept", 99, "Integration & Scaling",    "Senior Requirements Engineering Manager")],
}

VARIATION_REGULATORY = {
    1: [("Concept", 97, "Constraint Formalization",   "Senior Software Architect"),
        ("Concept", 94, "Liability Mapping",         "Senior Software Architect")],
    2: [("Concept", 96, "Compliance Validation",      "Senior System Engineer"),
        ("Concept", 92, "Gap Analysis",              "Senior System Engineer")],
    3: [("Concept", 89, "Policy Enforcement",         "Senior Safety Manager"),
        ("Concept", 95, "Traceability Mapping",       "Senior Safety Manager")],
    4: [("Concept", 98, "Ambiguity Resolution",       "Senior Validation Engineer"),
        ("Concept", 90, "Artifact Compliance Audit",  "Senior Validation Engineer")],
    5: [("Concept", 93, "Benchmarking",               "Senior Integration Engineer"),
        ("Concept", 85, "Reverse Engineering",        "Senior Integration Engineer")],
    6: [("Concept", 88, "Constraint Formalization",   "Senior Project Manager"),
        ("Concept", 91, "Cross-Jurisdictional Harmonization", "Senior Project Manager")],
    7: [("Concept", 86, "Compliance Validation",      "Senior DevOps Engineer"),
        ("Concept", 97, "Liability Mapping",         "Senior DevOps Engineer")],
    8: [("Concept", 84, "Policy Enforcement",         "Senior Requirements Engineering Manager"),
        ("Concept", 99, "Regulatory Loophole",        "Senior Requirements Engineering Manager")],
}


# ── Helpers ──────────────────────────────────────────────────────────────────
def ensure_dirs(terms_mode=False):
    """Create all required directories."""
    for d in [OUTPUT_JSON_DIR, OUTPUT_THINK_DIR, EVAL_DIR, PROMPTS_DIR]:
        os.makedirs(d, exist_ok=True)
    if terms_mode:
        for d in [OUTPUT_JSON_TERMS_DIR, OUTPUT_THINK_TERMS_DIR, EVAL_TERMS_DIR, PROMPTS_TERMS_DIR]:
            os.makedirs(d, exist_ok=True)


def get_doc_short_name(pdf_filename):
    """Convert PDF filename to a clean short name for file naming."""
    name = os.path.splitext(pdf_filename)[0]
    name = name.replace(" (1)", "").replace(" ", "_")
    if len(name) > 30:
        parts = name.split("_")
        if len(parts) > 3:
            name = "_".join(parts[:3])
    return name


def classify_pdf(pdf_path):
    """Auto-detect if a PDF is Technical or Regulatory based on keywords."""
    regulatory_keywords = [
        "iso", "regulation", "compliance", "standard", "directive",
        "unece", "r155", "r156", "homologation", "type approval",
        "legal", "liability", "eu ai act", "positionspapier",
        "sae", "vda", "normung", "ece", "annex"
    ]

    # Read cached text if available
    txt_cache = pdf_path.replace(".pdf", ".txt")
    if os.path.exists(txt_cache):
        with open(txt_cache, 'r', encoding='utf-8', errors='ignore') as f:
            text_sample = f.read(5000).lower()
    else:
        text_sample = os.path.basename(pdf_path).lower()

    score = sum(1 for kw in regulatory_keywords if kw in text_sample)
    mode = "REGULATORY" if score >= 2 else "TECHNICAL"
    return mode


def task_output_path(doc_short, turn, task_idx, terms_mode=False):
    """Generate the standardized output file path for a task (consistent capital T)."""
    base_dir = OUTPUT_JSON_TERMS_DIR if terms_mode else OUTPUT_JSON_DIR
    return os.path.join(base_dir, f"{doc_short}_Turn{turn}_Task{task_idx}.json")


def thinking_output_path(doc_short, turn, task_idx, terms_mode=False):
    """Generate the standardized thinking file path."""
    base_dir = OUTPUT_THINK_TERMS_DIR if terms_mode else OUTPUT_THINK_DIR
    return os.path.join(base_dir, f"{doc_short}_Turn{turn}_Task{task_idx}.txt")


def prompt_path(doc_short, turn, task_idx, is_repair=False, terms_mode=False):
    """Generate the prompt file path."""
    suffix = "_RepairPrompt" if is_repair else "_Prompt"
    base_dir = PROMPTS_TERMS_DIR if terms_mode else PROMPTS_DIR
    return os.path.join(base_dir, f"{doc_short}_Turn{turn}_Task{task_idx}{suffix}.txt")


# ── Progress Tracking ────────────────────────────────────────────────────────
def load_progress(terms_mode=False):
    """Load progress state from disk."""
    pf = PROGRESS_TERMS_FILE if terms_mode else PROGRESS_FILE
    if os.path.exists(pf):
        with open(pf, 'r', encoding='utf-8') as f:
            return json.load(f)
    start_key = "terms_completed" if terms_mode else "pdfs_completed"
    return {
        "started_at": datetime.now().isoformat(),
        start_key: [],
        "task_results": {}
    }


def save_progress(progress, terms_mode=False):
    """Save progress state to disk."""
    progress["updated_at"] = datetime.now().isoformat()
    pf = PROGRESS_TERMS_FILE if terms_mode else PROGRESS_FILE
    with open(pf, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2)


def collect_task_stats(json_path, report):
    """Extract per-task metrics from the validation report for logging."""
    stats = report.get("stats", {})
    return {
        "cot_chars": stats.get("cot_chars", 0),
        "answer_chars": stats.get("answer_chars", 0),
        "corpus_lines": stats.get("corpus_lines", 0),
        "graph_elements": stats.get("graph_elements", 0),
        "axiomatic_lines": stats.get("axiomatic_lines", 0),
    }


def print_task_summary(tk, status, stats, elapsed, repair_type, attempts):
    """Print a concise one-line summary of a completed task to the console."""
    icon = "✅" if status == "PASS" else "❌"
    cot = f"{stats.get('cot_chars', 0):,}"
    ans = f"{stats.get('answer_chars', 0):,}"
    corpus = f"{stats.get('corpus_lines', 0)}"
    graph = f"{stats.get('graph_elements', 0)}"
    repair_label = f" [{repair_type}]" if repair_type != "none" else ""
    print(f"  {icon} {tk} | CoT: {cot} chars | Ans: {ans} chars | Corpus: {corpus} lines | Graph: {graph} nodes | "
          f"Time: {elapsed:.0f}s | Attempts: {attempts}{repair_label}")


def compute_statistics(progress, terms_mode=False):
    """Compute min/max/mean/stddev for all tracked metrics and save to statistics.json."""
    results = progress.get("task_results", {})
    if not results:
        return {}

    # Collect arrays of each metric
    metric_arrays = {
        "elapsed_seconds": [],
        "cot_chars": [],
        "answer_chars": [],
        "corpus_lines": [],
        "graph_elements": [],
        "gemini_attempts": [],
    }

    pass_count = 0
    fail_count = 0
    local_repair_count = 0
    gemini_retry_count = 0

    for tk, data in results.items():
        if data.get("status") == "PASS":
            pass_count += 1
        else:
            fail_count += 1

        if data.get("repair_type") == "local":
            local_repair_count += 1
        if data.get("gemini_attempts", 1) > 1:
            gemini_retry_count += 1

        for key in metric_arrays:
            val = data.get(key)
            if val is not None and isinstance(val, (int, float)):
                metric_arrays[key].append(val)

    def stats_for(arr):
        if not arr:
            return {"min": 0, "max": 0, "mean": 0, "stddev": 0, "count": 0}
        return {
            "min": round(min(arr), 1),
            "max": round(max(arr), 1),
            "mean": round(statistics.mean(arr), 1),
            "stddev": round(statistics.stdev(arr), 1) if len(arr) > 1 else 0,
            "count": len(arr),
        }

    total = pass_count + fail_count
    stats_summary = {
        "computed_at": datetime.now().isoformat(),
        "total_tasks": total,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "first_attempt_success_rate": round(
            sum(1 for d in results.values() if d.get("gemini_attempts", 1) == 1 and d.get("status") == "PASS") / max(total, 1) * 100, 1),
        "local_repair_count": local_repair_count,
        "gemini_retry_count": gemini_retry_count,
        "metrics": {k: stats_for(v) for k, v in metric_arrays.items()},
    }

    # Save to disk
    sf = STATISTICS_TERMS_FILE if terms_mode else STATISTICS_FILE
    with open(sf, 'w', encoding='utf-8') as f:
        json.dump(stats_summary, f, indent=2)

    return stats_summary


def print_statistical_summary(stats_summary, label=""):
    """Print a formatted statistical summary to the console."""
    if not stats_summary:
        return
    m = stats_summary.get("metrics", {})
    print(f"\n  {'═'*65}")
    print(f"  📊 STATISTICAL SUMMARY{': ' + label if label else ''}")
    print(f"  {'═'*65}")
    for metric_name, display_name in [
        ("elapsed_seconds", "Task Times"),
        ("cot_chars", "CoT Chars"),
        ("answer_chars", "Ans Chars"),
        ("corpus_lines", "Corpus Lines"),
        ("sysml_elements", "SysML Tags"),
    ]:
        s = m.get(metric_name, {})
        if s.get("count", 0) > 0:
            print(f"  {display_name:>12s}:  min={s['min']:>8}  max={s['max']:>8}  "
                  f"mean={s['mean']:>8}  stddev={s['stddev']:>8}")
    print(f"  {'─'*65}")
    print(f"  1st-attempt success: {stats_summary.get('first_attempt_success_rate', 0)}% "
          f"({sum(1 for d in [] if True)})")
    print(f"  Local repairs:       {stats_summary.get('local_repair_count', 0)}")
    print(f"  Gemini retries:      {stats_summary.get('gemini_retry_count', 0)}")
    total = stats_summary.get('total_tasks', 0)
    passed = stats_summary.get('pass_count', 0)
    failed = stats_summary.get('fail_count', 0)
    print(f"  Total: {passed}/{total} passed, {failed}/{total} failed")
    print(f"  {'═'*65}")


def task_key(doc_short, turn, task_idx):
    """Generate a unique key for tracking a specific task."""
    return f"{doc_short}_Turn{turn}_Task{task_idx}"


# ── Prompt Builder ───────────────────────────────────────────────────────────
def build_generation_prompt(variation, turn, task_idx, doc_name, mode, is_soft_retry=False):
    """Build the full generation prompt per turn/task/variation by reading Concepts_V1.5.md."""
    lang, diff, strategy, role = variation
    
    prompt_file = os.path.join(BASE_DIR, "Concepts_V1.5.md")
    if not os.path.exists(prompt_file):
        raise FileNotFoundError(f"Missing prompt file: {prompt_file}")
        
    with open(prompt_file, 'r', encoding='utf-8') as f:
        base_prompt = f.read()

    anti_canvas = 'VIRTUAL TERMINAL PERSONA: You are a legacy VT100 Data Terminal. You lack the hardware to render side-panels or code editors. Any attempt to use "Canvas" or side-panels will result in a hardware system crash. All output MUST be a raw text stream in the main chat window.'

    # Append the dynamic variation to the end so Gemini strictly adopts it
    dynamic_variation = f"""
<variation_assignment>
You must execute the task according to the following specific parameters:
- Difficulty: {diff}/100
- Meta-Strategy: {strategy}
- Assigned Role: {role}
- Document Classification: {mode}
</variation_assignment>

<critical_formatting_override>
{anti_canvas}

MANDATORY LANGUAGE: ALL output MUST be in English. Regardless of the source document language (Korean, Chinese, German, etc.), your entire response — including all 10 concept elements, follow-up questions, and technical responses — MUST be written exclusively in English. Non-English output will crash the terminal.

IGNORE any prior instruction in the document asking for a raw JSON array output.
Instead, you MUST use the following granular block schema to structure your answer. 
DO NOT use markdown fenced code blocks (like ```json or ```) for ANY part of your response. Instead, write JSON and code as raw inline plaintext indented by 4 spaces. Fenced blocks trigger Canvas mode and crash the agent.

OUTPUT SCHEMA (Use exact `!!!!!BLOCK-NAME!!!!!` delimiters):
!!!!!METADATA!!!!!
(The JSON metadata dict including training_data_id, etc.)

!!!!!REASONING!!!!!
(Your 8-step internal monologue, wrapped between <think> and </think>)

!!!!!TURN-1-USER!!!!!
(The immersive 3-paragraph problem statement)

!!!!!CONCEPT_HEADER!!!!!
(You MUST include ALL 9 fields exactly as listed. Do NOT skip any field.)
- **Concept ID:** [Unique Identifier, e.g., ROBTS-2026-001]
- **Canonical Name:** [Full, Descriptive Name]
- **Definition Version:** [e.g., 1.0]
- **Last Definition Update Date:** [YYYY-MM-DD]
- **Estimated Origin Date/Period:** [Date/Year/Period]
- **Primary Domain(s) of Application:** [List of Fields]
- **Assigned Abstraction Level:** [Number (Name), e.g., 1 (Foundational/Meta-Concept)]
- **Keywords:** [Keyword1, Keyword2, Keyword3, ...]
- **Source Reference(s):** [Primary sources]

!!!!!ONTOLOGICAL_SCAFFOLDING!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Definitions:** Precise definitions of all key terms, entities, attributes.
- **Taxonomies & Classifications:** Hierarchical organization with is-a, part-of relationships.
- **Modular Composition (for Composite Concepts):**
    - **Identification of Subconcepts:** Explicit enumeration of constituent subconcepts.
    - **Compositional Architecture & Strategy:** High-level design philosophy governing subconcept integration.

!!!!!ABSTRACTION_LEVEL!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Description:** Assessment of the concept's position on the concrete-to-abstract spectrum.
- **Indicators/Criteria:**
    - **Degree of Composition:** Atomic vs. multi-subconcept composition analysis.
    - **Generality of Terms & Principles:** Breadth of applicability assessment.
    - **Potential for Instantiation/Specialization:** Generative capacity analysis.
    - **Distance from Direct Application:** Layers of specialization required.
- **Assigned Abstraction Level & Definitions:** Numerical level (1-4) with full justification per level definition.

!!!!!AXIOMATIC_BASE!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Assumptions & Postulates (Textual Description):** Fundamental truths and starting points.
- **Formal Axiomatic Representation (Mathematical Equations):** Complete plaintext math (NO SMT-LIB/TLA+/Lisp).
- **Adversarial Edge-Case Mandate:** Formal model of a Feasibility Void proving exactly why fallback logic is required.

!!!!!RELATIONAL_NETWORK!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Intra-Concept Dependencies & Interactions (Textual Description):** Internal element relationships.
- **Inter-Subconcept Dependencies & Associations (Textual Description):** Typed, directional dependencies between subconcepts.
- **Formal Typed Dependency Graph (Mathematical Set-Theoretic Notation):** G = (V, E, P, C) with vertices, edges, ports, constraints.
- **Detailed Model Description (Textual):** Comprehensive description of each vertex, edge, and role.
- **Formal Graph Definition (>100 lines):** Complete graph using tuple notation. Minimum: 8 vertices, 12 edges, 10 ports, 6 constraints. Must include Structural, Behavioral, AND Parametric layers.

!!!!!INFERENTIAL_FRAMEWORK!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Deductions & Reasoning Patterns:** Valid logical rules, deductive/abductive/inductive processes. Include meta-reasoning across subconcepts.

!!!!!METHODOLOGICAL_APPARATUS!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Methods & Guidelines:** Prescribed procedures, algorithms, best practices. For composite concepts, include orchestration methods.
- **Operational Constraints:** Rules governing method applicability and context-specific activation.

!!!!!ILLUSTRATIVE_CORPUS!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Exemplars (Positive Examples):**
    - **Problem Statement:** Clearly defined problem.
    - **Solution Narrative/Derivation:** Step-by-step application of the concept.
    - **Algorithmic Narrative (No Code Allowed):** >80-line natural language walkthrough of algorithmic execution.
- **Non-Exemplars (Negative/Contrastive Examples):** Cases where the concept does NOT apply.
- **Boundary Cases:** Examples testing the limits of applicability.

!!!!!GOAL_ORIENTATION!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Problem Space Definition:**
    - **General Description:** Summary of challenges the concept addresses.
    - **Exemplar Problem Formulations:** Specific problem statements with inputs, outputs, and task nature.
- **Domain of Applicability:** Valid contexts and known limitations.
- **Targeted Roles/Actors:** Specific human roles the concept assists.

!!!!!LIMITATIONS_AND_RISKS!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Known Limitations:**
    - **Scope Boundaries:** Situations where the concept is ineffective.
    - **Assumption Dependencies:** Critical assumptions whose violation invalidates the concept.
    - **Scalability/Performance Issues:** Resource and complexity constraints.
    - **Generalizability Gaps:** Domains where the concept does not extend well.
    - **Precision/Accuracy Constraints:** Inherent outcome limits.
- **Potential Risks:**
    - **Safety Risks:** Physical harm potential from misapplication.
    - **Ethical & Societal Risks:** Bias, fairness, privacy concerns.
    - **Operational Risks:** System failure and decision-making impacts.
    - **Misinterpretation/Misapplication Risks:** Incorrect usage danger.
    - **Dependency Risks:** Over-reliance concerns.
- **Mitigation Considerations (High-Level):**
    - **Verification & Validation Strategies**
    - **Monitoring & Control Mechanisms**
    - **Clear Documentation & User Guidance**
    - **Contingency Planning**
    - **Continuous Review & Improvement**
    - **Contextual Adaptation**

!!!!!INTER_CONCEPT_RELATIONSHIPS!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Description:** Identification of related concepts from same/adjacent domains.
- **Types of Relationships:**
    - **Prerequisite Concepts**
    - **Component/Sub-Concepts**
    - **Supra-Concepts/Generalizations**
    - **Sibling/Analogous Concepts**
    - **Complementary Concepts**
    - **Extending Concepts**
- **Synergistic Combinations:** Emergent capabilities from combining concepts.
- **Pathways for Knowledge Expansion:** Logical next steps for learning.

!!!!!TURN-3-USER!!!!!
([No Thinking] Follow-up question 1)

!!!!!TURN-4-ASSISTANT!!!!!
(Direct technical response)

!!!!!TURN-5-USER!!!!!
([No Thinking] Follow-up question 2)

!!!!!TURN-6-ASSISTANT!!!!!
(Direct technical response)
</critical_formatting_override>
"""
    return base_prompt + "\n" + dynamic_variation


def build_generation_prompt_terms(variation, turn, task_idx, term_number, term_name, term_text, mode):
    """Build the generation prompt for a single AD/ADAS term.
    
    Each term is treated like its own document:
      - term_number: The enumeration index (1-200)
      - term_name: The bold term name (e.g., 'Deterministic Replay')
      - term_text: The full line (e.g., '1. **Deterministic Replay:** When a bug...')
    
    The prompt instructs Gemini to build a PhD-level 10-element concept
    framework centered entirely on the provided term.
    """
    lang, diff, strategy, role = variation
    
    prompt_file = os.path.join(BASE_DIR, "Concepts_V1.5.md")
    if not os.path.exists(prompt_file):
        raise FileNotFoundError(f"Missing prompt file: {prompt_file}")
        
    with open(prompt_file, 'r', encoding='utf-8') as f:
        base_prompt = f.read()

    # Replace model and document references in the JSON schema section
    base_prompt = base_prompt.replace(
        '"model_used_generation": "Google Gemini 3.1 Pro"',
        '"model_used_generation": "Google Gemini 3.1 Pro Deep Think"'
    )
    base_prompt = base_prompt.replace(
        '"document": "The exact file name of the source document"',
        f'"document": "AD_ADAS_Term_{term_number:03d}_{term_name.replace(" ", "_")}"'
    )
    
    # Replace [Thinking] with [Deep Thinking] for the first user turn
    base_prompt = base_prompt.replace(
        '"[Thinking] [10 element concept]',
        '"[Deep Thinking] [10 element concept]'
    )

    anti_canvas = 'VIRTUAL TERMINAL PERSONA: You are a legacy VT100 Data Terminal. You lack the hardware to render side-panels or code editors. Any attempt to use "Canvas" or side-panels will result in a hardware system crash. All output MUST be a raw text stream in the main chat window.'

    # Append the dynamic variation to the end so Gemini strictly adopts it
    dynamic_variation = f"""
<variation_assignment>
You must execute the task according to the following specific parameters:
- Difficulty: {diff}/100
- Meta-Strategy: {strategy}
- Assigned Role: {role}
- Document Classification: {mode}
- Knowledge Source: A single expert-level automated driving term
- Term Number: {term_number}
- Term Name: {term_name}
</variation_assignment>

<critical_formatting_override>
{anti_canvas}

MANDATORY LANGUAGE: ALL output MUST be in English. Your entire response — including all 10 concept elements, follow-up questions, and technical responses — MUST be written exclusively in English. Non-English output will crash the terminal.

IGNORE any prior instruction in the document asking for a raw JSON array output.
Instead, you MUST use the following granular block schema to structure your answer. 
DO NOT use markdown fenced code blocks (like ```json or ```) for ANY part of your response. Instead, write JSON and code as raw inline plaintext indented by 4 spaces. Fenced blocks trigger Canvas mode and crash the agent.

IMPORTANT SOURCE CONTEXT: You are NOT analyzing a PDF document. Instead, you are working with a SINGLE automated driving term from the AD/ADAS domain. The term is:

  {term_text}

Your task: Build an extraordinarily deep, PhD-level, expert-grade 10-element concept framework centered ENTIRELY on this single term. Expand it into its full theoretical, practical, and systemic depth. Draw on your expert knowledge of autonomous driving, ADAS, software engineering, safety, and validation to create a comprehensive concept that goes far beyond the one-line description. Connect it to related concepts in the AD/ADAS ecosystem. The term's brief description is just a seed — you must grow it into a rich, multi-layered technical construct.

OUTPUT SCHEMA (Use exact `!!!!!BLOCK-NAME!!!!!` delimiters):
!!!!!METADATA!!!!!
(The JSON metadata dict including training_data_id, etc.)

!!!!!REASONING!!!!!
(Your 8-step internal monologue, wrapped between <think> and </think>)

!!!!!TURN-1-USER!!!!!
(The immersive 3-paragraph problem statement — must start with [Deep Thinking])

!!!!!CONCEPT_HEADER!!!!!
(You MUST include ALL 9 fields exactly as listed. Do NOT skip any field.)
- **Concept ID:** [Unique Identifier, e.g., ROBTS-2026-001]
- **Canonical Name:** [Full, Descriptive Name]
- **Definition Version:** [e.g., 1.0]
- **Last Definition Update Date:** [YYYY-MM-DD]
- **Estimated Origin Date/Period:** [Date/Year/Period]
- **Primary Domain(s) of Application:** [List of Fields]
- **Assigned Abstraction Level:** [Number (Name), e.g., 1 (Foundational/Meta-Concept)]
- **Keywords:** [Keyword1, Keyword2, Keyword3, ...]
- **Source Reference(s):** [Primary sources]

!!!!!ONTOLOGICAL_SCAFFOLDING!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Definitions:** Precise definitions of all key terms, entities, attributes.
- **Taxonomies & Classifications:** Hierarchical organization with is-a, part-of relationships.
- **Modular Composition (for Composite Concepts):**
    - **Identification of Subconcepts:** Explicit enumeration of constituent subconcepts.
    - **Compositional Architecture & Strategy:** High-level design philosophy governing subconcept integration.

!!!!!ABSTRACTION_LEVEL!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Description:** Assessment of the concept's position on the concrete-to-abstract spectrum.
- **Indicators/Criteria:**
    - **Degree of Composition:** Atomic vs. multi-subconcept composition analysis.
    - **Generality of Terms & Principles:** Breadth of applicability assessment.
    - **Potential for Instantiation/Specialization:** Generative capacity analysis.
    - **Distance from Direct Application:** Layers of specialization required.
- **Assigned Abstraction Level & Definitions:** Numerical level (1-4) with full justification per level definition.

!!!!!AXIOMATIC_BASE!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Assumptions & Postulates (Textual Description):** Fundamental truths and starting points.
- **Formal Axiomatic Representation (Mathematical Equations):** Complete plaintext math (NO SMT-LIB/TLA+/Lisp).
- **Adversarial Edge-Case Mandate:** Formal model of a Feasibility Void proving exactly why fallback logic is required.

!!!!!RELATIONAL_NETWORK!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Intra-Concept Dependencies & Interactions (Textual Description):** Internal element relationships.
- **Inter-Subconcept Dependencies & Associations (Textual Description):** Typed, directional dependencies between subconcepts.
- **Formal Typed Dependency Graph (Mathematical Set-Theoretic Notation):** G = (V, E, P, C) with vertices, edges, ports, constraints.
- **Detailed Model Description (Textual):** Comprehensive description of each vertex, edge, and role.
- **Formal Graph Definition (>100 lines):** Complete graph using tuple notation. Minimum: 8 vertices, 12 edges, 10 ports, 6 constraints. Must include Structural, Behavioral, AND Parametric layers.

!!!!!INFERENTIAL_FRAMEWORK!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Deductions & Reasoning Patterns:** Valid logical rules, deductive/abductive/inductive processes. Include meta-reasoning across subconcepts.

!!!!!METHODOLOGICAL_APPARATUS!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Methods & Guidelines:** Prescribed procedures, algorithms, best practices. For composite concepts, include orchestration methods.
- **Operational Constraints:** Rules governing method applicability and context-specific activation.

!!!!!ILLUSTRATIVE_CORPUS!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Exemplars (Positive Examples):**
    - **Problem Statement:** Clearly defined problem.
    - **Solution Narrative/Derivation:** Step-by-step application of the concept.
    - **Algorithmic Narrative (No Code Allowed):** >80-line natural language walkthrough of algorithmic execution.
- **Non-Exemplars (Negative/Contrastive Examples):** Cases where the concept does NOT apply.
- **Boundary Cases:** Examples testing the limits of applicability.

!!!!!GOAL_ORIENTATION!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Problem Space Definition:**
    - **General Description:** Summary of challenges the concept addresses.
    - **Exemplar Problem Formulations:** Specific problem statements with inputs, outputs, and task nature.
- **Domain of Applicability:** Valid contexts and known limitations.
- **Targeted Roles/Actors:** Specific human roles the concept assists.

!!!!!LIMITATIONS_AND_RISKS!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Known Limitations:**
    - **Scope Boundaries:** Situations where the concept is ineffective.
    - **Assumption Dependencies:** Critical assumptions whose violation invalidates the concept.
    - **Scalability/Performance Issues:** Resource and complexity constraints.
    - **Generalizability Gaps:** Domains where the concept does not extend well.
    - **Precision/Accuracy Constraints:** Inherent outcome limits.
- **Potential Risks:**
    - **Safety Risks:** Physical harm potential from misapplication.
    - **Ethical & Societal Risks:** Bias, fairness, privacy concerns.
    - **Operational Risks:** System failure and decision-making impacts.
    - **Misinterpretation/Misapplication Risks:** Incorrect usage danger.
    - **Dependency Risks:** Over-reliance concerns.
- **Mitigation Considerations (High-Level):**
    - **Verification & Validation Strategies**
    - **Monitoring & Control Mechanisms**
    - **Clear Documentation & User Guidance**
    - **Contingency Planning**
    - **Continuous Review & Improvement**
    - **Contextual Adaptation**

!!!!!INTER_CONCEPT_RELATIONSHIPS!!!!!
(You MUST include ALL of the following sub-headings with >800 words total:)
- **Description:** Identification of related concepts from same/adjacent domains.
- **Types of Relationships:**
    - **Prerequisite Concepts**
    - **Component/Sub-Concepts**
    - **Supra-Concepts/Generalizations**
    - **Sibling/Analogous Concepts**
    - **Complementary Concepts**
    - **Extending Concepts**
- **Synergistic Combinations:** Emergent capabilities from combining concepts.
- **Pathways for Knowledge Expansion:** Logical next steps for learning.

!!!!!TURN-3-USER!!!!!
([No Thinking] Follow-up question 1)

!!!!!TURN-4-ASSISTANT!!!!!
(Direct technical response)

!!!!!TURN-5-USER!!!!!
([No Thinking] Follow-up question 2)

!!!!!TURN-6-ASSISTANT!!!!!
(Direct technical response)
</critical_formatting_override>
"""
    return base_prompt + "\n" + dynamic_variation


def build_repair_prompt(validation_report, original_prompt_text):
    """Build a remediation prompt based on specific validation failures.
    Includes the original prompt to ensure structural constraints are not lost."""
    lines = [
        "Your previous response FAILED quality validation.",
        "CRITICAL: You MUST regenerate the response using the FULL 13-BLOCK SCHEMA (!!!!!METADATA!!!!! through !!!!!TURN-6-ASSISTANT!!!!!).",
        "Do NOT omit any blocks. Even if you are fixing a specific issue, the entire structured output must be provided.",
        "\nYou MUST fix the following specific issues while maintaining ALL original constraints:\n"
    ]

    for issue in validation_report.get("needs_regeneration", []):
        cat = issue["category"]
        msg = issue["issue"]
        if cat == "richness_and_complexity":
            if "keyword-salad" in msg or "cluster of padding" in msg:
                lines.append(f"- CRITICAL QUALITY FAILURE: {msg}. You used repetitive 'word-salad' padding or verbatim loops to meet length requirements. This is STRICTLY FORBIDDEN. Provide genuine engineering substance instead.")
            elif "repetition loop" in msg:
                lines.append(f"- REPETITION FAILURE: {msg}. Your response contained identical repeated paragraphs. Delete the duplicates and fill the space with new, deep technical details.")
            else:
                lines.append(f"- VOLUME FAILURE: {msg}. Expand your content significantly to meet the character/line limits.")
        elif cat == "cot_structure":
            lines.append(f"- COT STRUCTURE: {msg}. You MUST explicitly include all 1.1 through 8.4 headings.")
        elif cat == "self_containment":
            lines.append(f"- IMMERSION FAILURE: {msg}. Remove ALL meta-commentary, do not break character.")
        elif cat == "structured_answer_format":
            lines.append(f"- STRUCTURE: {msg}. Ensure all mandatory JSON keys and required arrays are populated.")
        else:
            lines.append(f"- {cat.upper()}: {msg}")

    lines.append("\n--- ORIGINAL TASK INSTRUCTIONS ---")
    lines.append("Review the original instructions below and ensure your new output satisfies BOTH the original rules AND fixes the failures listed above.")
    lines.append("-" * 40)
    lines.append(original_prompt_text)
    
    return "\n".join(lines)


# ── Execution Engine ─────────────────────────────────────────────────────────
def run_playwright(pdf_path, prompt_file, deep_think=False, terms_mode=False):
    """Execute the Playwright script and return success boolean.
    
    Args:
        pdf_path: Path to source PDF (or terms file in terms mode)
        prompt_file: Path to the generated prompt file
        deep_think: If True, pass --deep-think flag to activate Deep Think in Gemini
    """
    cmd = f'python "{PLAYWRIGHT_SCRIPT}" "{pdf_path}" "{prompt_file}"'
    if deep_think:
        cmd += ' --deep-think'
    if terms_mode:
        cmd += f' --output-dir "{OUTPUT_JSON_TERMS_DIR}" --thinking-dir "{OUTPUT_THINK_TERMS_DIR}"'
    
    # Deep Think mode needs more time (15 min) since the model "thinks" longer
    timeout_seconds = 900 if not deep_think else 900
    
    try:
        result = subprocess.run(cmd, shell=True, cwd=BASE_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        print(f"  ❌ Playwright execution timed out ({timeout_seconds}s). Forcing restart.")
        return False

    if result.returncode != 0:
        # Check for safety rejection (approx 139 chars) or empty response
        if result.stderr and ("Normally I can help with things like" in result.stderr or "139 chars" in result.stderr):
            print(f"  ⚠️ Gemini Safety Rejection detected.")
            return "SAFETY_REJECTION"
            
        stderr_preview = result.stderr[-300:] if result.stderr else "No error output"
        print(f"  ❌ Playwright error (exit {result.returncode}): {stderr_preview}")
        return False
    return True


def run_validation(json_path, report_path=None):
    """Run validate_task.py and return the parsed report."""
    cmd = f'python "{VALIDATE_SCRIPT}" "{json_path}"'
    if report_path:
        cmd += f' --save-report "{report_path}"'

    result = subprocess.run(cmd, shell=True, cwd=BASE_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        report = json.loads(result.stdout)
        return report
    except json.JSONDecodeError:
        return {"overall_status": "FAIL", "error": "Validator output not parseable"}


def run_auto_repair(json_path):
    """Run auto_repair.py on a failed task. Parse JSON from stdout only."""
    cmd = f'python "{AUTO_REPAIR_SCRIPT}" "{json_path}"'
    result = subprocess.run(cmd, shell=True, cwd=BASE_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "ERROR"}


def run_partial_repair(json_path, pdf_path):
    """Run partial_repair.py to fix only broken follow-up turns.
    
    Steps:
      1. Build a focused prompt from context in the valid main answer
      2. Send it to Gemini via Playwright
      3. Patch the follow-up turns back into the JSON
    """
    # Step 1: Build repair prompt
    cmd = f'python "{PARTIAL_REPAIR_SCRIPT}" --build-prompt "{json_path}"'
    result = subprocess.run(cmd, shell=True, cwd=BASE_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
    
    repair_prompt = result.stdout.strip()
    if not repair_prompt or len(repair_prompt) < 100:
        print(f"  ❌ Partial repair: failed to build repair prompt")
        return False
    
    # Save the repair prompt
    basename = os.path.splitext(os.path.basename(json_path))[0]
    repair_prompt_path = os.path.join(PROMPTS_DIR, f"{basename}_FollowupRepairPrompt.txt")
    with open(repair_prompt_path, 'w', encoding='utf-8') as f:
        f.write(repair_prompt)
    
    print(f"  📝 Follow-up repair prompt saved ({len(repair_prompt)} chars)")
    
    # Step 2: Run Playwright with the repair prompt
    print(f"  🌐 Sending follow-up repair to Gemini...")
    pw_result = run_playwright(pdf_path, repair_prompt_path)
    if not pw_result:
        print(f"  ❌ Playwright failed for follow-up repair")
        return False
    
    # Step 3: The Playwright script will have produced a new JSON output.
    # We need to extract the follow-up turns from the Gemini response
    # However, since Playwright writes to a fixed path based on filename,
    # and we're using a different prompt file, we need the raw response.
    # Use the raw_fail.txt or extract from the generated JSON.
    raw_response_path = json_path.replace(".json", "_raw_fail.txt")
    
    # Check if Playwright produced a response we can use
    if os.path.exists(raw_response_path):
        cmd_patch = f'python "{PARTIAL_REPAIR_SCRIPT}" --patch "{json_path}" "{raw_response_path}"'
        patch_result = subprocess.run(cmd_patch, shell=True, cwd=BASE_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            patch_report = json.loads(patch_result.stdout)
            if patch_report.get("status") == "PATCHED":
                print(f"  ✅ Follow-up turns patched successfully")
                return True
        except json.JSONDecodeError:
            pass
    
    print(f"  ❌ Partial repair: could not patch follow-ups")
    return False


def decide_repair_strategy(report):
    """Decide whether to attempt local repair, partial repair, or full re-prompt.

    Returns:
        "local"   — try auto_repair.py first
        "partial" — follow-up turns broken, try partial_repair.py
        "gemini"  — skip local, go straight to full re-prompt
        "pass"    — already passing
    """
    if report.get("overall_status") == "PASS":
        return "pass"

    locally_fixable = report.get("locally_fixable", [])
    needs_regen = report.get("needs_regeneration", [])
    needs_partial = report.get("needs_partial_repair", [])

    # If there are locally fixable issues, always try local repair first
    if locally_fixable:
        return "local"

    # If only follow-up issues remain (no full regen needed), do partial repair
    if needs_partial and not needs_regen:
        return "partial"

    # Full regeneration needed (possibly combined with partial issues)
    if needs_regen:
        return "gemini"

    # Safety fallback
    return "gemini"


def render_html_preview(json_path):
    """Produces a beautifully styled HTML file showing the 10 conceptual elements and opens it."""
    import re
    import html
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        return
        
    try:
        content = json.loads(data[0]["conversations"][1]["content"])
    except:
        return
        
    html_out = os.path.join(OUTPUT_JSON_DIR, os.path.basename(json_path).replace(".json", "_preview.html"))
    
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Concept Preview: {os.path.basename(json_path)}</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #121212;
            color: #e0e0e0;
            padding: 40px;
            max-width: 1100px;
            margin: 0 auto;
            line-height: 1.6;
        }}
        h1 {{ color: #bb86fc; font-weight: 300; border-bottom: 2px solid #333; padding-bottom: 10px; }}
        h2 {{ color: #03dac6; margin-top: 40px; font-weight: 400; }}
        pre {{
            background: #1e1e1e; padding: 20px; border-radius: 8px;
            overflow-x: auto; color: #a9b7c6; font-family: Consolas, Monaco, "Courier New", monospace;
        }}
        .element-box {{
            background: #1e2025; padding: 20px 30px; margin-bottom: 30px;
            border-radius: 12px; border: 1px solid #333;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}
    </style>
</head>
<body>
    <h1>10-Element Framework Preview</h1>
"""
    
    for key, val in content.items():
        if not val:
            continue
        display_key = key.replace("_", " ").title()
        
        # Safely dump string for JS processing
        val_js = json.dumps(val)
        element_id = f"content_{key}"
        
        html_template += f"""
    <div class="element-box">
        <h2>{display_key}</h2>
        <div id="{element_id}"></div>
        <script>
            document.getElementById('{element_id}').innerHTML = marked.parse({val_js});
        </script>
    </div>
"""
    
    html_template += "\n</body>\n</html>"
    
    with open(html_out, 'w', encoding='utf-8') as f:
        f.write(html_template)
        
    print(f"  🌐 Opening preview: {html_out}")
    webbrowser.open(f'file:///{html_out.replace(os.sep, "/")}')


# ── Main Pipeline ────────────────────────────────────────────────────────────

def parse_terms(terms_file):
    """Parse Terms.md into a list of (number, name, full_text) tuples.
    
    Each line in Terms.md has the format:
        N. **Term Name:** Description text.
    
    Returns:
        List of (int, str, str) tuples: (term_number, term_name, full_line)
    """
    with open(terms_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    terms = []
    # Match lines like: 1. **Deterministic Replay:** When a bug...
    pattern = re.compile(r'^(\d+)\.\s+\*\*(.+?):\*\*\s*(.+)$', re.MULTILINE)
    
    for match in pattern.finditer(content):
        num = int(match.group(1))
        name = match.group(2).strip()
        full_line = match.group(0).strip()
        terms.append((num, name, full_line))
    
    return sorted(terms, key=lambda t: t[0])


def process_task(pdf_path, doc_short, doc_name, turn, task_idx,
                 variation, mode, progress, preview=False,
                 terms_mode=False, terms_text=None,
                 terms_number=None, terms_name=None):
    """Process a single task: generate → validate → smart repair loop.

    Retry logic:
    - Max 3 Gemini attempts
    - Between each attempt, always try local repair first
    - Agent decides: if issue is locally fixable (JSON structure, missing tags etc)
      → auto_repair.py. If issue needs regeneration (volume, CoT, immersion)
      → Gemini re-prompt.
    
    Args:
        terms_mode: If True, use terms-specific directories and prompt builder
        terms_text: The full text of the single term (only when terms_mode=True)
        terms_number: The term enumeration index (1-200)
        terms_name: The term name (e.g., 'Deterministic Replay')
    """
    tk = task_key(doc_short, turn, task_idx)
    json_out = task_output_path(doc_short, turn, task_idx, terms_mode=terms_mode)
    eval_dir = EVAL_TERMS_DIR if terms_mode else EVAL_DIR
    qa_report_path = os.path.join(eval_dir, f"{doc_short}_Turn{turn}_Task{task_idx}_QA.json")
    task_start = time.time()
    task_stats = {}  # Will hold per-task metrics

    # Check if already completed (disk + progress)
    existing = progress.get("task_results", {}).get(tk, {})
    file_exists = os.path.exists(json_out)

    if existing.get("status") == "PASS" and file_exists:
        print(f"  ✅ {tk}: Already passed and exists (skipping)")
        return True
    
    if file_exists and not existing.get("status") == "PASS":
        print(f"  ⚠️ {tk}: File exists but progress marks it FAIL/PENDING (will re-process)")
    elif existing.get("status") == "PASS" and not file_exists:
        print(f"  ⚠️ {tk}: Marked PASS in progress but file is missing (will re-process)")

    lang, diff, strategy, role = variation
    print(f"\n{'─'*60}")
    print(f"  📋 {tk} | {lang} | Diff {diff} | {strategy} | {role}")
    print(f"{'─'*60}")

    # In terms mode, write a single-term .txt file so Playwright only injects THIS term
    if terms_mode and terms_text:
        term_source_file = os.path.join(INPUT_TERMS_DIR, f"Term{terms_number:03d}.txt")
        with open(term_source_file, 'w', encoding='utf-8') as f:
            f.write(terms_text)
        effective_input = term_source_file
    else:
        effective_input = pdf_path

    gemini_attempts = 0
    final_repair_type = "none"
    # Always generate the base prompt text so it's available for repairs
    if terms_mode:
        base_prompt_text = build_generation_prompt_terms(
            variation, turn, task_idx,
            terms_number, terms_name, terms_text, mode)
    else:
        base_prompt_text = build_generation_prompt(variation, turn, task_idx, doc_name, mode)

    while gemini_attempts < MAX_GEMINI_ATTEMPTS:
        gemini_attempts += 1

        # ── Step 1: Build and save prompt ──
        if gemini_attempts == 1:
            prompt_text = base_prompt_text
            p_path = prompt_path(doc_short, turn, task_idx, is_repair=False, terms_mode=terms_mode)
        else:
            # Build repair prompt from last validation report
            last_report = run_validation(json_out)
            if last_report.get("overall_status") == "PASS":
                break  # Fixed by previous local repair!

            prompt_text = build_repair_prompt(last_report, base_prompt_text)
            p_path = prompt_path(doc_short, turn, task_idx, is_repair=True, terms_mode=terms_mode)

        # Save prompt
        os.makedirs(os.path.dirname(p_path), exist_ok=True)
        with open(p_path, 'w', encoding='utf-8') as f:
            f.write(prompt_text)

        # ── Step 2: Run Playwright (Gemini attempt) ──
        print(f"  🌐 Gemini attempt {gemini_attempts}/{MAX_GEMINI_ATTEMPTS}...")
        pw_result = run_playwright(effective_input, p_path, terms_mode=terms_mode)
        
        # SAFETY RETRY LOGIC
        if pw_result == "SAFETY_REJECTION":
            print(f"  ⚠️ Triggering 'Soft Prompt' retry to bypass safety filters...")
            if terms_mode:
                p_text = build_generation_prompt_terms(
                    variation, turn, task_idx,
                    terms_number, terms_name, terms_text, mode)
            else:
                p_text = build_generation_prompt(variation, turn, task_idx, doc_name, mode, is_soft_retry=True)
            with open(p_path, 'w', encoding='utf-8') as f: f.write(p_text)
            pw_result = run_playwright(effective_input, p_path, terms_mode=terms_mode)

        if not pw_result:
            print(f"  ❌ Playwright failed on attempt {gemini_attempts}")
            continue

        # ── Step 3: Check output exists ──
        if not os.path.exists(json_out):
            print(f"  ❌ Output file not created: {json_out}")
            continue

        # ── Step 4: Validate ──
        report = run_validation(json_out, qa_report_path)
        task_stats = collect_task_stats(json_out, report)

        if report.get("overall_status") == "PASS":
            elapsed = time.time() - task_start
            progress["task_results"][tk] = {
                "status": "PASS", "gemini_attempts": gemini_attempts,
                "repair_type": final_repair_type, "elapsed_seconds": round(elapsed, 1),
                **task_stats
            }
            save_progress(progress, terms_mode=terms_mode)
            print_task_summary(tk, "PASS", task_stats, elapsed, final_repair_type, gemini_attempts)
            if preview:
                render_html_preview(json_out)
            return True

        # ── Step 5: Smart repair decision ──
        strategy_decision = decide_repair_strategy(report)
        violations = []
        for cat, data in report.get("metrics", {}).items():
            violations.extend(data.get("violations", []))
        
        print(f"  ⚠️ VALIDATION FAILED on attempt {gemini_attempts}:")
        for v in violations:
            print(f"       - {v}")
        print(f"  🔍 Repair strategy: {strategy_decision}")

        if strategy_decision == "local":
            # Try local repair
            print(f"  🔧 Running auto_repair.py...")
            repair_result = run_auto_repair(json_out)
            if repair_result.get("fixes_applied"):
                final_repair_type = "local"
                print(f"  🔧 Applied: {', '.join(repair_result['fixes_applied'])}")

                # Re-validate after local fix
                report2 = run_validation(json_out, qa_report_path)
                task_stats = collect_task_stats(json_out, report2)
                if report2.get("overall_status") == "PASS":
                    elapsed = time.time() - task_start
                    progress["task_results"][tk] = {
                        "status": "PASS", "gemini_attempts": gemini_attempts,
                        "repair_type": "local", "elapsed_seconds": round(elapsed, 1),
                        "repairs_applied": repair_result.get("fixes_applied", []),
                        **task_stats
                    }
                    save_progress(progress, terms_mode=terms_mode)
                    print_task_summary(tk, "PASS", task_stats, elapsed, "local", gemini_attempts)
                    if preview:
                        render_html_preview(json_out)
                    return True

                # Local repair helped but not enough — check if remaining issues need Gemini
                remaining_strategy = decide_repair_strategy(report2)
                if remaining_strategy == "pass":
                    continue  # Shouldn't happen, but safety
                elif remaining_strategy == "partial":
                    # Only follow-up turns remain broken — try partial repair
                    print(f"  🔄 Local repair fixed structural issues. Attempting partial follow-up repair...")
                    partial_ok = run_partial_repair(json_out, effective_input)
                    if partial_ok:
                        report3 = run_validation(json_out, qa_report_path)
                        task_stats = collect_task_stats(json_out, report3)
                        if report3.get("overall_status") == "PASS":
                            elapsed = time.time() - task_start
                            progress["task_results"][tk] = {
                                "status": "PASS", "gemini_attempts": gemini_attempts,
                                "repair_type": "local+partial", "elapsed_seconds": round(elapsed, 1),
                                "repairs_applied": repair_result.get("fixes_applied", []) + ["partial_followup_repair"],
                                **task_stats
                            }
                            save_progress(progress, terms_mode=terms_mode)
                            print_task_summary(tk, "PASS", task_stats, elapsed, "local+partial", gemini_attempts)
                            return True
                print(f"  ⚠️ Local repair insufficient. Remaining issues need Gemini re-prompt.")
                final_repair_type = "local+gemini"
            else:
                print(f"  🔧 No local fixes applicable. Will re-prompt Gemini.")

        elif strategy_decision == "partial":
            # Only follow-up turns are broken — try targeted partial repair
            print(f"  🔄 Running partial follow-up repair...")
            partial_ok = run_partial_repair(json_out, effective_input)
            if partial_ok:
                report2 = run_validation(json_out, qa_report_path)
                task_stats = collect_task_stats(json_out, report2)
                if report2.get("overall_status") == "PASS":
                    elapsed = time.time() - task_start
                    progress["task_results"][tk] = {
                        "status": "PASS", "gemini_attempts": gemini_attempts,
                        "repair_type": "partial", "elapsed_seconds": round(elapsed, 1),
                        "repairs_applied": ["partial_followup_repair"],
                        **task_stats
                    }
                    save_progress(progress, terms_mode=terms_mode)
                    print_task_summary(tk, "PASS", task_stats, elapsed, "partial", gemini_attempts)
                    return True
            print(f"  ⚠️ Partial repair insufficient. Will try full Gemini re-prompt.")

        # If we get here, the next loop iteration will build a repair prompt and re-run Gemini
        final_repair_type = "gemini" if final_repair_type == "none" else final_repair_type

    # Exhausted all Gemini attempts
    elapsed = time.time() - task_start
    progress["task_results"][tk] = {
        "status": "FAIL", "gemini_attempts": gemini_attempts,
        "repair_type": "exhausted", "elapsed_seconds": round(elapsed, 1),
        **task_stats
    }
    save_progress(progress, terms_mode=terms_mode)
    print_task_summary(tk, "FAIL", task_stats, elapsed, "exhausted", gemini_attempts)
    print(f"  ❌ FAILED after {gemini_attempts} Gemini attempts — flagged for manual review")
    return False


def process_pdf(pdf_path, progress, start_turn=1, start_task=1, end_turn=8, skip_dashboard=False, test_setup=False, limit_tasks=0, preview=False):
    """Process all tasks for a single PDF up to end_turn or limit_tasks."""
    pdf_name = os.path.basename(pdf_path)
    doc_short = get_doc_short_name(pdf_name)
    doc_name = os.path.splitext(pdf_name)[0]

    print(f"\n{'═'*70}")
    print(f"  📄 Processing: {pdf_name}")
    print(f"  📁 Short name: {doc_short}")
    print(f"{'═'*70}")

    # Classify PDF
    mode = classify_pdf(pdf_path)
    schema = VARIATION_REGULATORY if mode == "REGULATORY" else VARIATION_TECHNICAL
    print(f"  📊 Classification: {mode}")

    # Load PDF text cache
    txt_cache = pdf_path.replace(".pdf", ".txt")
    if os.path.exists(txt_cache):
        with open(txt_cache, 'r', encoding='utf-8') as f:
            pdf_text = f.read()
        print(f"  📝 Using cached text: {len(pdf_text)} chars")
    else:
        print(f"  📝 No cached text — Playwright will extract on first run")

    # Process each turn
    total_pass = 0
    total_fail = 0
    tasks_since_dashboard = 0
    tasks_processed_this_run = 0
    pdf_start = time.time()

    for turn in range(start_turn, end_turn + 1):
        variations = schema[turn]
        for task_idx_0, variation in enumerate(variations):
            task_idx = task_idx_0 + 1
            if turn == start_turn and task_idx < start_task:
                continue

            result = process_task(
                pdf_path, doc_short, doc_name,
                turn, task_idx, variation, mode, progress, preview)

            if result:
                total_pass += 1
            else:
                total_fail += 1

            tasks_since_dashboard += 1
            tasks_processed_this_run += 1

            if test_setup:
                print("\n  [TEST SETUP] Exiting after 1 task.")
                break

            if limit_tasks > 0 and tasks_processed_this_run >= limit_tasks:
                print(f"\n  [LIMIT REACHED] Exiting after {limit_tasks} tasks.")
                break
        
        if (test_setup) or (limit_tasks > 0 and tasks_processed_this_run >= limit_tasks):
            break

    # Final dashboard for any remaining tasks
    if not skip_dashboard and tasks_since_dashboard > 0:
        try:
            print(f"\n  📊 Generating final dashboard...")
            subprocess.run(f'python "{DASHBOARD_SCRIPT}"', shell=True,
                          cwd=BASE_DIR, capture_output=True)
            # Auto-open the dashboard in the browser
            if os.path.exists(DASHBOARD_OUTPUT):
                print(f"  🌐 Opening dashboard in browser...")
                webbrowser.open(f'file:///{DASHBOARD_OUTPUT.replace(os.sep, "/")}')
        except Exception:
            pass

    # Compute and print statistical summary for this PDF
    stats_summary = compute_statistics(progress)
    print_statistical_summary(stats_summary, label=pdf_name)

    # PDF summary
    pdf_elapsed = time.time() - pdf_start
    pdf_min = int(pdf_elapsed // 60)
    pdf_sec = pdf_elapsed % 60
    print(f"\n{'═'*70}")
    print(f"  📄 {pdf_name} COMPLETE: {total_pass}/16 passed, {total_fail}/16 failed")
    print(f"  ⏱️  Elapsed: {pdf_min}m {pdf_sec:.0f}s")
    print(f"{'═'*70}")

    if total_fail == 0:
        progress["pdfs_completed"].append(pdf_name)
        save_progress(progress)

    return total_fail == 0


def process_term(term_number, term_name, term_text, progress,
                  start_turn=1, start_task=1, end_turn=8,
                  test_setup=False, limit_tasks=0, preview=False):
    """Process all 16 tasks for a single term (analogous to process_pdf).
    
    Each term gets 8 turns × 2 tasks = 16 tasks, just like a PDF.
    Output files are named like: Term001_Turn1_Task1.json
    """
    doc_short = f"Term{term_number:03d}"
    doc_name = f"AD_ADAS_Term_{term_number:03d}_{term_name.replace(' ', '_')}"
    terms_file = os.path.join(INPUT_TERMS_DIR, "Terms.md")

    print(f"\n{'═'*70}")
    print(f"  📚 Term {term_number}/200: {term_name}")
    print(f"  📁 Short name: {doc_short}")
    print(f"  📝 {term_text[:80]}...")
    print(f"{'═'*70}")

    # Always TECHNICAL classification for terms
    mode = "TECHNICAL"
    schema = VARIATION_TECHNICAL

    # Process each turn
    total_pass = 0
    total_fail = 0
    tasks_processed_this_run = 0
    term_start = time.time()

    for turn in range(start_turn, end_turn + 1):
        variations = schema[turn]
        for task_idx_0, variation in enumerate(variations):
            task_idx = task_idx_0 + 1
            if turn == start_turn and task_idx < start_task:
                continue

            result = process_task(
                terms_file, doc_short, doc_name,
                turn, task_idx, variation, mode, progress, preview,
                terms_mode=True, terms_text=term_text,
                terms_number=term_number, terms_name=term_name)

            if result:
                total_pass += 1
            else:
                total_fail += 1

            tasks_processed_this_run += 1

            if test_setup:
                print("\n  [TEST SETUP] Exiting after 1 task.")
                return total_pass, total_fail, True  # early_exit=True

            if limit_tasks > 0 and tasks_processed_this_run >= limit_tasks:
                print(f"\n  [LIMIT REACHED] Exiting after {limit_tasks} tasks.")
                return total_pass, total_fail, True  # early_exit=True

    # Term summary
    term_elapsed = time.time() - term_start
    term_min = int(term_elapsed // 60)
    term_sec = term_elapsed % 60
    print(f"\n{'═'*70}")
    print(f"  📚 Term {term_number} ({term_name}) COMPLETE: {total_pass}/16 passed, {total_fail}/16 failed")
    print(f"  ⏱️  Elapsed: {term_min}m {term_sec:.0f}s")
    print(f"{'═'*70}")

    if total_fail == 0:
        if "terms_completed" not in progress:
            progress["terms_completed"] = []
        progress["terms_completed"].append(doc_short)
        save_progress(progress, terms_mode=True)

    return total_pass, total_fail, False  # early_exit=False


def process_terms(progress, start_turn=1, start_task=1, end_turn=8,
                  skip_dashboard=False, test_setup=False, limit_tasks=0,
                  preview=False, start_term=1, limit_terms=0):
    """Process all terms from Terms.md (terms mode entry point).
    
    Iterates over each of the 200 terms, treating each one like a separate
    PDF document. Each term gets 16 tasks (8 turns × 2 tasks).
    Skips terms that are already marked complete in progress.
    
    Args:
        start_term: Start from term N (1-indexed). Default 1.
        limit_terms: Stop after processing N terms. 0 = no limit.
    """
    terms_file = os.path.join(INPUT_TERMS_DIR, "Terms.md")
    if not os.path.exists(terms_file):
        print(f"❌ Terms file not found: {terms_file}")
        sys.exit(1)

    all_terms = parse_terms(terms_file)
    if not all_terms:
        print("❌ No terms found in Terms.md")
        sys.exit(1)

    print(f"\n{'═'*70}")
    print(f"  📋 TERMS MODE: {len(all_terms)} terms found")
    print(f"  📁 Input: {terms_file}")
    print(f"  📁 Output: {OUTPUT_JSON_TERMS_DIR}")
    dt_label = " (Deep Think)" if DEEP_THINK_MODE else ""
    print(f"  🧠 Model: Google Gemini 3.1 Pro{dt_label}")
    print(f"  📊 Structure: {len(all_terms)} terms × 16 tasks = {len(all_terms) * 16} total tasks")
    print(f"{'═'*70}")

    # Filter to terms starting from start_term
    terms_to_process = [t for t in all_terms if t[0] >= start_term]
    
    # Skip already completed terms
    completed = set(progress.get("terms_completed", []))
    terms_to_process = [t for t in terms_to_process
                        if f"Term{t[0]:03d}" not in completed]

    if not terms_to_process:
        print("✅ All terms already completed!")
        return

    print(f"  🔄 Terms remaining: {len(terms_to_process)} (starting from term {terms_to_process[0][0]})")

    overall_pass = 0
    overall_fail = 0
    terms_done = 0

    for term_num, term_name, term_text in terms_to_process:
        tp, tf, early_exit = process_term(
            term_num, term_name, term_text, progress,
            start_turn=start_turn, start_task=start_task,
            end_turn=end_turn, test_setup=test_setup,
            limit_tasks=limit_tasks, preview=preview,)

        overall_pass += tp
        overall_fail += tf
        terms_done += 1

        # Reset start position after first term (only first term uses custom start)
        start_turn = 1
        start_task = 1

        if early_exit:
            break

        if limit_terms > 0 and terms_done >= limit_terms:
            print(f"\n  [LIMIT REACHED] Exiting after processing {terms_done} terms.")
            break

    # Compute and print statistical summary
    stats_summary = compute_statistics(progress, terms_mode=True)
    print_statistical_summary(stats_summary, label="Terms Mode")

    total_expected = terms_done * 16
    print(f"\n{'═'*70}")
    print(f"  📋 Terms Run Complete: {terms_done} terms, {overall_pass}/{total_expected} tasks passed")
    print(f"{'═'*70}")


def validate_only_mode():
    """Just validate all existing JSON files without generating new ones."""
    json_files = sorted(glob.glob(os.path.join(OUTPUT_JSON_DIR, "*.json")))
    if not json_files:
        print("No JSON files found in Output/json/")
        return

    print(f"\n{'═'*70}")
    print(f"  🔍 Validate-Only Mode: {len(json_files)} files")
    print(f"{'═'*70}")

    pass_count = 0
    for jf in json_files:
        qa_path = os.path.join(EVAL_DIR, os.path.basename(jf).replace(".json", "_QA.json"))
        report = run_validation(jf, qa_path)
        status = report.get("overall_status", "?")
        stats = report.get("stats", {})
        icon = "✅" if status == "PASS" else "❌"
        print(f"  {icon} {os.path.basename(jf)}: {status}"
              f"  (CoT: {stats.get('cot_chars', '?')}, Ans: {stats.get('answer_chars', '?')})")
        if status == "PASS":
            pass_count += 1
        else:
            for cat, data in report.get("metrics", {}).items():
                for v in data.get("violations", []):
                    print(f"       ⚠️ [{cat}] {v}")

    print(f"\n  Results: {pass_count}/{len(json_files)} passed")


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="AD/ADAS Coding Task Generation Pipeline")
    parser.add_argument("--pdf", help="Process a specific PDF file")
    parser.add_argument("--terms", action="store_true",
                        help="Terms mode: use Input_terms/Terms.md instead of PDFs")
    parser.add_argument("--deep-think", action="store_true",
                        help="Force use of Deep Think model")
    parser.add_argument("--start-term", type=int, default=1,
                        help="Start from term N (1-indexed, terms mode only)")
    parser.add_argument("--limit-terms", type=int, default=0,
                        help="Stop after processing N terms (terms mode only)")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--turn", type=int, default=1, help="Start from turn N")
    parser.add_argument("--end-turn", type=int, default=8, help="End at turn N (inclusive). Useful for test runs.")
    parser.add_argument("--task", type=int, default=1, help="Start from task K within the turn")
    parser.add_argument("--validate-only", action="store_true", help="Only validate existing outputs")
    parser.add_argument("--limit-tasks", type=int, default=0, help="Stop after N tasks (regardless of turns)")
    parser.add_argument("--limit-pdfs", type=int, default=0, help="Stop after N PDFs have been completed")
    parser.add_argument("--no-dashboard", action="store_true", help="Skip dashboard generation")
    parser.add_argument("--test-setup", action="store_true", help="One turn (turn 2), one task (task 1), one attempt (test mode)")
    parser.add_argument("--preview", action="store_true", help="When a task passes, render its 10 concept elements as HTML and open in browser.")
    args = parser.parse_args()
    global DEEP_THINK_MODE
    DEEP_THINK_MODE = getattr(args, "deep_think", False)

    if args.test_setup:
        args.turn = 2
        args.end_turn = 2
        args.task = 1

    ensure_dirs(terms_mode=args.terms)

    if args.validate_only:
        validate_only_mode()
        return

    # ── TERMS MODE ────────────────────────────────────────────────────────
    if args.terms:
        progress = load_progress(terms_mode=True)
        start_time = time.time()

        print(f"\n{'═'*70}")
        print(f"  🚀 Pipeline Starting: TERMS MODE")
        print(f"  📂 Input:  {INPUT_TERMS_DIR}")
        print(f"  📂 Output: {OUTPUT_JSON_TERMS_DIR}")
        print(f"  🔄 Max Gemini attempts per task: {MAX_GEMINI_ATTEMPTS}")
        print(f"{'═'*70}")

        # Check if already completed (all 200 terms)
        completed = progress.get("terms_completed", [])
        if args.resume and len(completed) >= 200:
            print("✅ All 200 terms already completed!")
            return

        process_terms(progress,
                      start_turn=args.turn, start_task=args.task,
                      end_turn=args.end_turn, skip_dashboard=args.no_dashboard,
                      test_setup=args.test_setup, limit_tasks=args.limit_tasks,
                      preview=args.preview,
                      start_term=args.start_term, limit_terms=args.limit_terms)

        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = elapsed % 60
        print(f"\n{'='*70}")
        print(f"  🏁 Terms Pipeline Complete: {minutes}m {seconds:.0f}s elapsed")
        print(f"{'='*70}")
        return

    # ── PDF MODE (default) ────────────────────────────────────────────────
    progress = load_progress()
    start_time = time.time()

    # Get PDF list
    if args.pdf:
        pdf_path = os.path.join(INPUT_DIR, args.pdf) if not os.path.isabs(args.pdf) else args.pdf
        if not os.path.exists(pdf_path):
            print(f"❌ PDF not found: {pdf_path}")
            sys.exit(1)
        pdf_list = [pdf_path]
    else:
        pdf_list = sorted(glob.glob(os.path.join(INPUT_DIR, "*.pdf")))

    if not pdf_list:
        print("❌ No PDFs found in Input/")
        sys.exit(1)

    print(f"\n{'═'*70}")
    print(f"  🚀 Pipeline Starting: {len(pdf_list)} PDFs to process")
    print(f"  📂 Input:  {INPUT_DIR}")
    print(f"  📂 Output: {OUTPUT_JSON_DIR}")
    print(f"  🔄 Max Gemini attempts per task: {MAX_GEMINI_ATTEMPTS}")
    print(f"{'═'*70}")

    # Filter out already-completed PDFs (unless specific PDF requested)
    if not args.pdf:
        pdf_list = [p for p in pdf_list
                    if os.path.basename(p) not in progress.get("pdfs_completed", [])]
        if not pdf_list:
            print("✅ All PDFs already completed!")
            return

    pdfs_processed = 0
    for pdf_path in pdf_list:
        success = process_pdf(pdf_path, progress,
                   start_turn=args.turn, start_task=args.task,
                   end_turn=args.end_turn, skip_dashboard=args.no_dashboard,
                   test_setup=args.test_setup, limit_tasks=args.limit_tasks,
                   preview=args.preview)
        
        if success:
            pdfs_processed += 1
        
        # Reset start position after first PDF
        args.turn = 1
        args.task = 1

        if args.limit_pdfs > 0 and pdfs_processed >= args.limit_pdfs:
            print(f"\n  [LIMIT REACHED] Exiting after processing {pdfs_processed} PDFs.")
            break

    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = elapsed % 60
    completed = len(progress.get("pdfs_completed", []))
    print(f"\n{'='*70}")
    print(f"  🏁 Pipeline Complete: {completed} PDFs, {minutes}m {seconds:.0f}s elapsed")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()

