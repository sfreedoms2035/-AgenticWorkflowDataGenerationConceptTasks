import sys

pipelines = [
  r'C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright_Concepts',
  r'C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright\AgenticWorkflowDataGeneration',
  r'C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright_QAs',
  r'C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright_Reviews',
  r'C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright_Tooling',
  r'C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright_Visuals',
]

for p in pipelines:
  file_path = f'{p}\\pipeline.py'
  try:
      with open(file_path, 'r', encoding='utf-8') as f:
          content = f.read()
          
      if '--deep-think' not in content:
          content = content.replace(
              'help="Terms mode: use Input_terms/Terms.md instead of PDFs, activates Deep Think")',
              'help="Terms mode: use Input_terms/Terms.md instead of PDFs")\n    parser.add_argument("--deep-think", action="store_true",\n                        help="Force use of Deep Think model")'
          )
          
      content = content.replace(
          'def process_task(task_index, block_name, turn_index, pdf_name, max_retries, extracted_blocks, progress, repair_enabled=True, terms_mode=False):',
          'def process_task(task_index, block_name, turn_index, pdf_name, max_retries, extracted_blocks, progress, repair_enabled=True, terms_mode=False, deep_think=False):'
      )
      
      content = content.replace(
          'def process_pdf(pdf_path, progress, start_turn=1, start_task=1, end_turn=8, skip_dashboard=False, test_setup=False, limit_tasks=0, preview=False):',
          'def process_pdf(pdf_path, progress, start_turn=1, start_task=1, end_turn=8, skip_dashboard=False, test_setup=False, limit_tasks=0, preview=False, deep_think=False):'
      )
      
      content = content.replace(
          'def process_term(term_num, term_name, reference_text, progress, start_turn=1, start_task=1, end_turn=8, test_setup=False, limit_tasks=0, preview=False):',
          'def process_term(term_num, term_name, reference_text, progress, start_turn=1, start_task=1, end_turn=8, test_setup=False, limit_tasks=0, preview=False, deep_think=False):'
      )
      
      content = content.replace(
          'def process_terms(progress, start_turn=1, start_task=1, end_turn=8, skip_dashboard=False, test_setup=False, limit_tasks=0, preview=False, start_term=1, limit_terms=0):',
          'def process_terms(progress, start_turn=1, start_task=1, end_turn=8, skip_dashboard=False, test_setup=False, limit_tasks=0, preview=False, start_term=1, limit_terms=0, deep_think=False):'
      )
      
      content = content.replace('start_term=args.start_term, limit_terms=args.limit_terms)', 'start_term=args.start_term, limit_terms=args.limit_terms, deep_think=args.deep_think)')
      content = content.replace('limit_tasks=args.limit_tasks,\n                   preview=args.preview)', 'limit_tasks=args.limit_tasks,\n                   preview=args.preview, deep_think=args.deep_think)')
      content = content.replace('limit_tasks=args.limit_tasks, preview=args.preview)', 'limit_tasks=args.limit_tasks, preview=args.preview, deep_think=args.deep_think)')
      content = content.replace('limit_tasks=limit_tasks, preview=preview)', 'limit_tasks=limit_tasks, preview=preview, deep_think=deep_think)')
      content = content.replace('repair_enabled=True, terms_mode=True)', 'repair_enabled=True, terms_mode=True, deep_think=deep_think)')
      content = content.replace('repair_enabled=True)', 'repair_enabled=True, deep_think=deep_think)')
      content = content.replace('repair_enabled=True, terms_mode=False)', 'repair_enabled=True, terms_mode=False, deep_think=deep_think)')
      content = content.replace('pw_result = run_playwright(effective_input, p_path, deep_think=terms_mode)', 'pw_result = run_playwright(effective_input, p_path, deep_think=deep_think)')
      content = content.replace('TERMS MODE (Deep Think)', 'TERMS MODE')
      
      dt_fstr = 'print(f"  🧠 Model: Google Gemini 3.1 Pro {\\\'(Deep Think)\\\' if args.deep_think else \\\'\\\'}")'
      content = content.replace('print(f"  🧠 Model: Google Gemini 3.1 Pro Deep Think")', dt_fstr)
      
      with open(file_path, 'w', encoding='utf-8') as f:
          f.write(content)
      print(f'Done {p}')
  except Exception as e:
      print(f'Error {p}: {e}')
