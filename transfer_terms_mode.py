"""
Transfer script: Adds Terms Mode to all AD/ADAS pipelines.
Reads the reference implementation from Concepts pipeline and
applies the necessary changes to each target pipeline.
"""
import os
import re
import shutil


# Source pipeline (fully working terms mode)
SOURCE = r"C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright_Concepts"

# Target pipelines
TARGETS = [
    r"C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright\AgenticWorkflowDataGeneration",
    r"C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright_QAs",
    r"C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright_Reviews",
    r"C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright_Tooling",
    r"C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright_Visuals",
]


def copy_terms_input(target_dir):
    """Copy Input_terms/Terms.md to the target pipeline."""
    src_dir = os.path.join(SOURCE, "Input_terms")
    dst_dir = os.path.join(target_dir, "Input_terms")
    os.makedirs(dst_dir, exist_ok=True)
    
    terms_src = os.path.join(src_dir, "Terms.md")
    terms_dst = os.path.join(dst_dir, "Terms.md")
    
    if os.path.exists(terms_src):
        shutil.copy2(terms_src, terms_dst)
        print(f"  ✅ Copied Terms.md → {dst_dir}")
    else:
        print(f"  ❌ Source Terms.md not found at {terms_src}")


def patch_pipeline(target_dir):
    """Add terms mode support to pipeline.py."""
    pipeline_path = os.path.join(target_dir, "pipeline.py")
    
    if not os.path.exists(pipeline_path):
        print(f"  ❌ pipeline.py not found in {target_dir}")
        return False
    
    with open(pipeline_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Skip if already patched
    if 'INPUT_TERMS_DIR' in content:
        print(f"  ⏭️ pipeline.py already has terms mode, skipping")
        return True
    
    # 1. Add 'import re' if missing
    if 'import re' not in content:
        content = content.replace('from datetime import datetime', 'import re\nfrom datetime import datetime')
        print(f"    + Added import re")
    
    # 2. Add terms mode config vars after existing config block
    terms_config = '''
# ── Terms Mode Configuration ─────────────────────────────────────────────────
INPUT_TERMS_DIR = os.path.join(BASE_DIR, "Input_terms")
OUTPUT_JSON_TERMS_DIR = os.path.join(BASE_DIR, "Output", "json_terms")
OUTPUT_THINK_TERMS_DIR = os.path.join(BASE_DIR, "Output", "thinking_terms")
EVAL_TERMS_DIR = os.path.join(BASE_DIR, "Eval_terms")
PROMPTS_TERMS_DIR = os.path.join(BASE_DIR, "Output", "prompts_terms")
PROGRESS_TERMS_FILE = os.path.join(BASE_DIR, "Output", "progress_terms.json")
STATISTICS_TERMS_FILE = os.path.join(BASE_DIR, "Output", "statistics_terms.json")
'''
    # Insert after DASHBOARD_OUTPUT line
    if 'DASHBOARD_OUTPUT' in content:
        content = re.sub(
            r'(DASHBOARD_OUTPUT\s*=\s*os\.path\.join\(.+?\)\s*\n)',
            r'\1' + terms_config,
            content)
        print(f"    + Added terms mode config vars")
    
    # 3. Update ensure_dirs to support terms_mode
    if 'def ensure_dirs():' in content:
        content = content.replace(
            'def ensure_dirs():',
            'def ensure_dirs(terms_mode=False):')
        # Add terms dirs creation
        content = content.replace(
            '    for d in [OUTPUT_JSON_DIR, OUTPUT_THINK_DIR, EVAL_DIR, PROMPTS_DIR]:',
            '''    dirs = [OUTPUT_JSON_DIR, OUTPUT_THINK_DIR, EVAL_DIR, PROMPTS_DIR]
    if terms_mode:
        dirs.extend([OUTPUT_JSON_TERMS_DIR, OUTPUT_THINK_TERMS_DIR, EVAL_TERMS_DIR, PROMPTS_TERMS_DIR, INPUT_TERMS_DIR])
    for d in dirs:''')
        print(f"    + Updated ensure_dirs for terms_mode")
    
    # 4. Update task_output_path to support terms_mode
    if 'def task_output_path(doc_short, turn, task_idx):' in content:
        content = content.replace(
            'def task_output_path(doc_short, turn, task_idx):',
            'def task_output_path(doc_short, turn, task_idx, terms_mode=False):')
        content = content.replace(
            '    return os.path.join(OUTPUT_JSON_DIR, f"{doc_short}_Turn{turn}_Task{task_idx}.json")',
            '    out_dir = OUTPUT_JSON_TERMS_DIR if terms_mode else OUTPUT_JSON_DIR\n'
            '    return os.path.join(out_dir, f"{doc_short}_Turn{turn}_Task{task_idx}.json")')
        print(f"    + Updated task_output_path for terms_mode")
    
    # 5. Update thinking_output_path to support terms_mode
    if 'def thinking_output_path(doc_short, turn, task_idx):' in content:
        content = content.replace(
            'def thinking_output_path(doc_short, turn, task_idx):',
            'def thinking_output_path(doc_short, turn, task_idx, terms_mode=False):')
        content = content.replace(
            '    return os.path.join(OUTPUT_THINK_DIR, f"{doc_short}_Turn{turn}_Task{task_idx}.txt")',
            '    out_dir = OUTPUT_THINK_TERMS_DIR if terms_mode else OUTPUT_THINK_DIR\n'
            '    return os.path.join(out_dir, f"{doc_short}_Turn{turn}_Task{task_idx}.txt")')
        print(f"    + Updated thinking_output_path for terms_mode")
    
    # 6. Update prompt_path to support terms_mode
    if 'def prompt_path(doc_short, turn, task_idx, is_repair=False):' in content:
        content = content.replace(
            'def prompt_path(doc_short, turn, task_idx, is_repair=False):',
            'def prompt_path(doc_short, turn, task_idx, is_repair=False, terms_mode=False):')
        # Find and update the return for prompts dir
        content = content.replace(
            '    return os.path.join(PROMPTS_DIR, f"{doc_short}_Turn{turn}_Task{task_idx}{suffix}.txt")',
            '    out_dir = PROMPTS_TERMS_DIR if terms_mode else PROMPTS_DIR\n'
            '    return os.path.join(out_dir, f"{doc_short}_Turn{turn}_Task{task_idx}{suffix}.txt")')
        print(f"    + Updated prompt_path for terms_mode")
    
    # 7. Update load_progress and save_progress for terms_mode
    if 'def load_progress():' in content:
        content = content.replace(
            'def load_progress():',
            'def load_progress(terms_mode=False):')
        content = content.replace(
            '    if os.path.exists(PROGRESS_FILE):',
            '    pf = PROGRESS_TERMS_FILE if terms_mode else PROGRESS_FILE\n    if os.path.exists(pf):')
        content = content.replace(
            '        with open(PROGRESS_FILE, \'r\', encoding=\'utf-8\') as f:',
            '        with open(pf, \'r\', encoding=\'utf-8\') as f:')
        print(f"    + Updated load_progress for terms_mode")
    
    if 'def save_progress(progress):' in content:
        content = content.replace(
            'def save_progress(progress):',
            'def save_progress(progress, terms_mode=False):')
        content = content.replace(
            '    with open(PROGRESS_FILE, \'w\', encoding=\'utf-8\') as f:',
            '    pf = PROGRESS_TERMS_FILE if terms_mode else PROGRESS_FILE\n    with open(pf, \'w\', encoding=\'utf-8\') as f:')
        print(f"    + Updated save_progress for terms_mode")
    
    # 8. Update compute_statistics for terms_mode
    if 'def compute_statistics(progress):' in content:
        content = content.replace(
            'def compute_statistics(progress):',
            'def compute_statistics(progress, terms_mode=False):')
        content = content.replace(
            '    with open(STATISTICS_FILE, \'w\', encoding=\'utf-8\') as f:',
            '    sf = STATISTICS_TERMS_FILE if terms_mode else STATISTICS_FILE\n    with open(sf, \'w\', encoding=\'utf-8\') as f:')
        print(f"    + Updated compute_statistics for terms_mode")
    
    # 9. Update run_playwright to support deep_think flag
    if 'def run_playwright(pdf_path, prompt_file):' in content:
        content = content.replace(
            'def run_playwright(pdf_path, prompt_file):',
            'def run_playwright(pdf_path, prompt_file, deep_think=False):')
        content = content.replace(
            '    cmd = f\'python "{PLAYWRIGHT_SCRIPT}" "{pdf_path}" "{prompt_file}"\'',
            '    cmd = f\'python "{PLAYWRIGHT_SCRIPT}" "{pdf_path}" "{prompt_file}"\'\n'
            '    if deep_think:\n'
            '        cmd += \' --deep-think\'')
        print(f"    + Updated run_playwright for deep_think flag")
    
    # 10. Add parse_terms function before process_task or main pipeline section
    parse_terms_code = '''

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
    pattern = re.compile(r'^(\\d+)\\.\\s+\\*\\*(.+?):\\*\\*\\s*(.+)$', re.MULTILINE)
    
    for match in pattern.finditer(content):
        num = int(match.group(1))
        name = match.group(2).strip()
        full_line = match.group(0).strip()
        terms.append((num, name, full_line))
    
    return sorted(terms, key=lambda t: t[0])

'''
    # Insert before the Main Pipeline comment or process_task
    main_pipeline_marker = '# ── Main Pipeline'
    if main_pipeline_marker in content:
        content = content.replace(main_pipeline_marker, parse_terms_code + main_pipeline_marker)
        print(f"    + Added parse_terms() function")
    
    # 11. Update process_task signature to accept terms params
    # Find the existing process_task signature
    pt_match = re.search(r'def process_task\(([^)]+)\):', content)
    if pt_match:
        old_sig = pt_match.group(0)
        old_params = pt_match.group(1)
        if 'terms_mode' not in old_params:
            new_params = old_params.rstrip() + ',\n                 terms_mode=False, terms_text=None,\n                 terms_number=None, terms_name=None'
            new_sig = f'def process_task({new_params}):'
            content = content.replace(old_sig, new_sig)
            print(f"    + Updated process_task signature with terms params")
    
    # 12. Add terms_mode handling inside process_task
    # Update json_out to use terms_mode
    if 'json_out = task_output_path(doc_short, turn, task_idx)' in content:
        content = content.replace(
            'json_out = task_output_path(doc_short, turn, task_idx)',
            'json_out = task_output_path(doc_short, turn, task_idx, terms_mode=terms_mode)')
    
    # Update qa_report_path
    if 'qa_report_path = os.path.join(EVAL_DIR,' in content:
        content = content.replace(
            'qa_report_path = os.path.join(EVAL_DIR,',
            'eval_dir = EVAL_TERMS_DIR if terms_mode else EVAL_DIR\n    qa_report_path = os.path.join(eval_dir,')
    
    # Add terms source file creation before gemini_attempts
    terms_source_block = '''
    # In terms mode, write a single-term .txt file so Playwright only injects THIS term
    if terms_mode and terms_text:
        term_source_file = os.path.join(INPUT_TERMS_DIR, f"Term{terms_number:03d}.txt")
        with open(term_source_file, 'w', encoding='utf-8') as f:
            f.write(terms_text)
        effective_input = term_source_file
    else:
        effective_input = pdf_path
'''
    if 'effective_input' not in content:
        content = content.replace(
            '    gemini_attempts = 0\n    final_repair_type = "none"',
            terms_source_block + '\n    gemini_attempts = 0\n    final_repair_type = "none"')
        print(f"    + Added terms source file creation in process_task")
    
    # Update prompt builder call to use terms_mode
    if 'base_prompt_text = build_generation_prompt(variation, turn, task_idx, doc_name, mode)' in content:
        content = content.replace(
            '    base_prompt_text = build_generation_prompt(variation, turn, task_idx, doc_name, mode)',
            '''    if terms_mode:
        base_prompt_text = build_generation_prompt(variation, turn, task_idx, doc_name, mode)
        # Terms mode uses same prompt builder but passes deep_think to Playwright
    else:
        base_prompt_text = build_generation_prompt(variation, turn, task_idx, doc_name, mode)''')
    
    # Update prompt_path calls to pass terms_mode
    content = content.replace(
        'p_path = prompt_path(doc_short, turn, task_idx, is_repair=False)',
        'p_path = prompt_path(doc_short, turn, task_idx, is_repair=False, terms_mode=terms_mode)')
    content = content.replace(
        'p_path = prompt_path(doc_short, turn, task_idx, is_repair=True)',
        'p_path = prompt_path(doc_short, turn, task_idx, is_repair=True, terms_mode=terms_mode)')
    
    # Update run_playwright calls to pass deep_think
    if 'pw_result = run_playwright(pdf_path, p_path)' in content:
        content = content.replace(
            'pw_result = run_playwright(pdf_path, p_path)',
            'pw_result = run_playwright(effective_input if terms_mode else pdf_path, p_path, deep_think=terms_mode)')
    
    # Update save_progress calls to pass terms_mode
    content = re.sub(
        r'save_progress\(progress\)',
        'save_progress(progress, terms_mode=terms_mode)',
        content)
    
    # 13. Add process_term and process_terms functions before validate_only_mode
    terms_functions = '''

def process_term(term_number, term_name, term_text, progress,
                  start_turn=1, start_task=1, end_turn=8,
                  test_setup=False, limit_tasks=0):
    """Process all 16 tasks for a single term (analogous to process_pdf).
    
    Each term gets 8 turns x 2 tasks = 16 tasks, just like a PDF.
    Output files are named like: Term001_Turn1_Task1.json
    """
    doc_short = f"Term{term_number:03d}"
    doc_name = f"AD_ADAS_Term_{term_number:03d}_{term_name.replace(' ', '_')}"
    terms_file = os.path.join(INPUT_TERMS_DIR, "Terms.md")

    print(f"\\n{'═'*70}")
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
                turn, task_idx, variation, mode, progress,
                terms_mode=True, terms_text=term_text,
                terms_number=term_number, terms_name=term_name)

            if result:
                total_pass += 1
            else:
                total_fail += 1

            tasks_processed_this_run += 1

            if test_setup:
                print("\\n  [TEST SETUP] Exiting after 1 task.")
                return total_pass, total_fail, True

            if limit_tasks > 0 and tasks_processed_this_run >= limit_tasks:
                print(f"\\n  [LIMIT REACHED] Exiting after {limit_tasks} tasks.")
                return total_pass, total_fail, True

    # Term summary
    term_elapsed = time.time() - term_start
    term_min = int(term_elapsed // 60)
    term_sec = term_elapsed % 60
    print(f"\\n{'═'*70}")
    print(f"  📚 Term {term_number} ({term_name}) COMPLETE: {total_pass}/16 passed, {total_fail}/16 failed")
    print(f"  ⏱️  Elapsed: {term_min}m {term_sec:.0f}s")
    print(f"{'═'*70}")

    if total_fail == 0:
        if "terms_completed" not in progress:
            progress["terms_completed"] = []
        progress["terms_completed"].append(doc_short)
        save_progress(progress, terms_mode=True)

    return total_pass, total_fail, False


def process_terms(progress, start_turn=1, start_task=1, end_turn=8,
                  skip_dashboard=False, test_setup=False, limit_tasks=0,
                  start_term=1, limit_terms=0):
    """Process all terms from Terms.md (terms mode entry point).
    
    Iterates over each of the 200 terms, treating each one like a separate
    PDF document. Each term gets 16 tasks (8 turns x 2 tasks).
    """
    terms_file = os.path.join(INPUT_TERMS_DIR, "Terms.md")
    if not os.path.exists(terms_file):
        print(f"❌ Terms file not found: {terms_file}")
        sys.exit(1)

    all_terms = parse_terms(terms_file)
    if not all_terms:
        print("❌ No terms found in Terms.md")
        sys.exit(1)

    print(f"\\n{'═'*70}")
    print(f"  📋 TERMS MODE: {len(all_terms)} terms found")
    print(f"  📁 Input: {terms_file}")
    print(f"  📁 Output: {OUTPUT_JSON_TERMS_DIR}")
    print(f"  🧠 Model: Google Gemini 3.1 Pro Deep Think")
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
            limit_tasks=limit_tasks)

        overall_pass += tp
        overall_fail += tf
        terms_done += 1

        # Reset start position after first term
        start_turn = 1
        start_task = 1

        if early_exit:
            break

        if limit_terms > 0 and terms_done >= limit_terms:
            print(f"\\n  [LIMIT REACHED] Exiting after processing {terms_done} terms.")
            break

    # Compute and print statistical summary
    stats_summary = compute_statistics(progress, terms_mode=True)
    print_statistical_summary(stats_summary, label="Terms Mode")

    total_expected = terms_done * 16
    print(f"\\n{'═'*70}")
    print(f"  📋 Terms Run Complete: {terms_done} terms, {overall_pass}/{total_expected} tasks passed")
    print(f"{'═'*70}")

'''
    # Insert before validate_only_mode
    if 'def validate_only_mode():' in content:
        content = content.replace(
            'def validate_only_mode():',
            terms_functions + '\ndef validate_only_mode():')
        print(f"    + Added process_term() and process_terms() functions")
    
    # 14. Update CLI args in main()
    # Add terms args after --pdf arg
    terms_cli_args = '''    parser.add_argument("--terms", action="store_true",
                        help="Terms mode: use Input_terms/Terms.md instead of PDFs, activates Deep Think")
    parser.add_argument("--start-term", type=int, default=1,
                        help="Start from term N (1-indexed, terms mode only)")
    parser.add_argument("--limit-terms", type=int, default=0,
                        help="Stop after processing N terms (terms mode only)")
'''
    if '--terms' not in content:
        content = content.replace(
            '    parser.add_argument("--resume"',
            terms_cli_args + '    parser.add_argument("--resume"')
        print(f"    + Added --terms, --start-term, --limit-terms CLI args")
    
    # 15. Update main() to call ensure_dirs with terms_mode
    if 'ensure_dirs()' in content and 'ensure_dirs(terms_mode=' not in content:
        content = content.replace(
            '    ensure_dirs()',
            '    ensure_dirs(terms_mode=getattr(args, "terms", False))')
    
    # 16. Add terms mode branch in main() before PDF mode
    terms_main_block = '''
    # ── TERMS MODE ────────────────────────────────────────────────────────
    if args.terms:
        progress = load_progress(terms_mode=True)
        start_time = time.time()

        print(f"\\n{'═'*70}")
        print(f"  🚀 Pipeline Starting: TERMS MODE (Deep Think)")
        print(f"  📂 Input:  {INPUT_TERMS_DIR}")
        print(f"  📂 Output: {OUTPUT_JSON_TERMS_DIR}")
        print(f"  🔄 Max Gemini attempts per task: {MAX_GEMINI_ATTEMPTS}")
        print(f"{'═'*70}")

        completed = progress.get("terms_completed", [])
        if args.resume and len(completed) >= 200:
            print("✅ All 200 terms already completed!")
            return

        process_terms(progress,
                      start_turn=args.turn, start_task=args.task,
                      end_turn=args.end_turn, skip_dashboard=args.no_dashboard,
                      test_setup=args.test_setup, limit_tasks=args.limit_tasks,
                      start_term=args.start_term, limit_terms=args.limit_terms)

        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = elapsed % 60
        print(f"\\n{'='*70}")
        print(f"  🏁 Terms Pipeline Complete: {minutes}m {seconds:.0f}s elapsed")
        print(f"{'='*70}")
        return

'''
    if '# ── TERMS MODE' not in content:
        # Insert before the PDF mode section
        pdf_mode_marker = '    # ── PDF MODE'
        if pdf_mode_marker not in content:
            # Try to find where PDF processing starts (after validate_only check)
            pdf_mode_marker = '    progress = load_progress()'
            if pdf_mode_marker in content:
                content = content.replace(
                    pdf_mode_marker,
                    terms_main_block + '    # ── PDF MODE (default) ────────────────────────────────────────────────\n    ' + pdf_mode_marker.lstrip(),
                    1)  # Only replace first occurrence
        else:
            content = content.replace(pdf_mode_marker, terms_main_block + pdf_mode_marker)
        print(f"    + Added terms mode branch in main()")
    
    # 17. Update docstring
    if 'python pipeline.py --terms' not in content:
        content = content.replace(
            '    python pipeline.py --validate-only',
            '    python pipeline.py --validate-only               # Just validate existing outputs\n'
            '    python pipeline.py --terms                       # Terms mode (Deep Think)\n'
            '    python pipeline.py --terms --resume              # Resume terms mode')
        content = content.replace(
            '    python pipeline.py --validate-only               # Just validate existing outputs\n'
            '    python pipeline.py --validate-only',
            '    python pipeline.py --validate-only')  # Remove duplicates
    
    # Write back
    with open(pipeline_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  ✅ pipeline.py patched successfully")
    return True


def patch_playwright(target_dir):
    """Add Deep Think support and escaped newline fix to run_gemini_playwright_v2.py."""
    pw_path = os.path.join(target_dir, "run_gemini_playwright_v2.py")
    
    if not os.path.exists(pw_path):
        print(f"  ❌ run_gemini_playwright_v2.py not found in {target_dir}")
        return False
    
    with open(pw_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Add --deep-think CLI argument
    if '--deep-think' not in content:
        content = content.replace(
            'parser.add_argument("prompt_file"',
            'parser.add_argument("--deep-think", action="store_true", help="Use Deep Think model")\n    parser.add_argument("prompt_file"')
        print(f"    + Added --deep-think CLI argument")
    
    # 2. Fix extract_semantic_blocks: add escaped newline normalization
    if 'Pre-process: Normalize escaped newlines' not in content:
        old_block = '''    blocks = {}
    if not text:
        return blocks
        
    # Require delimiters'''
        new_block = '''    blocks = {}
    if not text:
        return blocks
    
    # Pre-process: Normalize escaped newlines around !!!!! delimiters to real newlines.
    # Deep Think / long-form outputs often produce: \\\\n!!!!!BLOCK_NAME!!!!!\\\\n
    # where \\\\n is a literal two-character escape, not a real newline.
    # We convert these to real newlines so the regex can match block boundaries.
    for _ in range(3):
        text = re.sub(r'\\\\\\\\n\\s*(!{3,})', r'\\n\\1', text)
        text = re.sub(r'(!{3,}[A-Z0-9_-]+!{3,})\\s*\\\\\\\\n', r'\\1\\n', text)
        text = re.sub(r'\\\\n\\s*(!{3,})', r'\\n\\1', text)
        text = re.sub(r'(!{3,}[A-Z0-9_-]+!{3,})\\s*\\\\n', r'\\1\\n', text)
        
    # Require delimiters'''
        if old_block in content:
            content = content.replace(old_block, new_block)
            print(f"    + Added escaped newline normalization to extract_semantic_blocks")
    
    # 3. Update timeout to 18 min for deep_think
    content = re.sub(
        r'max_wait\s*=\s*\d+\s*#\s*\d+\.?\d*\s*min',
        'max_wait = 1080 if deep_think else 750  # 18 min for Deep Think, 12.5 min otherwise',
        content, count=1)
    
    # But we need 'deep_think' variable to be available. Check if it's in the function args
    if 'deep_think' not in content.split('def run_generation')[0] if 'def run_generation' in content else True:
        # Need to add deep_think to the main execution flow
        pass
    
    # 4. Add activate_deep_think function if not present
    if 'def activate_deep_think' not in content:
        deep_think_func = '''

def activate_deep_think(page):
    """Activate Deep Think mode via the Gemini UI Tools menu."""
    try:
        log("🧠 Activating Deep Think mode...")
        
        # Click the "Tools" or model picker button
        tools_selectors = [
            'button[aria-label*="Tool"]',
            'button[data-test-id="tools-button"]',
            '.tools-button',
            'button:has-text("Tools")',
        ]
        
        clicked = False
        for sel in tools_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    page.wait_for_timeout(1500)
                    clicked = True
                    log(f"  Clicked tools button: {sel}")
                    break
            except:
                continue
        
        if not clicked:
            log("  ⚠️ Could not find Tools button, trying direct Deep Think selection")
        
        # Look for "Deep Think" option
        deep_think_selectors = [
            'text="Deep Think"',
            '[data-value="deep-think"]',
            'button:has-text("Deep Think")',
            'div:has-text("Deep Think")',
        ]
        
        for sel in deep_think_selectors:
            try:
                option = page.locator(sel).first
                if option.is_visible(timeout=2000):
                    option.click()
                    page.wait_for_timeout(1500)
                    log(f"  ✅ Deep Think activated via: {sel}")
                    return True
            except:
                continue
        
        log("  ⚠️ Deep Think option not found in UI, continuing without it")
        return False
        
    except Exception as e:
        log(f"  ⚠️ Deep Think activation failed: {e}")
        return False

'''
        # Insert before the main function or at a sensible place
        # Find a good insertion point
        if 'def validate_and_save_json' in content:
            content = content.replace(
                'def validate_and_save_json',
                deep_think_func + '\ndef validate_and_save_json')
            print(f"    + Added activate_deep_think() function")
    
    # Write back
    with open(pw_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  ✅ run_gemini_playwright_v2.py patched successfully")
    return True


def main():
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    print("=" * 70)
    print("  Terms Mode Transfer Script")
    print("  Source: AgenticWorkflowPlaywright_Concepts")
    print(f"  Targets: {len(TARGETS)} pipelines")
    print("=" * 70)
    
    for target in TARGETS:
        name = os.path.basename(target)
        print(f"\n{'─'*70}")
        print(f"📦 Processing: {name}")
        print(f"   Path: {target}")
        print(f"{'─'*70}")
        
        if not os.path.exists(target):
            print(f"  ❌ Directory not found, skipping")
            continue
        
        # Step 1: Copy Terms.md
        copy_terms_input(target)
        
        # Step 2: Patch pipeline.py
        patch_pipeline(target)
        
        # Step 3: Patch run_gemini_playwright_v2.py
        patch_playwright(target)
    
    print(f"\n{'='*70}")
    print("  ✅ Transfer complete!")
    print("='*70")


if __name__ == '__main__':
    main()
