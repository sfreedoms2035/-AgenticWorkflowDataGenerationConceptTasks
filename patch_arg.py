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

      if 'parser.add_argument("--deep-think"' not in content:
          content = content.replace(
              'help="Terms mode: use Input_terms/Terms.md instead of PDFs, activates Deep Think")',
              'help="Terms mode: use Input_terms/Terms.md instead of PDFs")\n    parser.add_argument("--deep-think", action="store_true",\n                        help="Force use of Deep Think model")'
          )
          
      with open(file_path, 'w', encoding='utf-8') as f:
          f.write(content)
      print(f'Injected arg {p}')
  except Exception as e:
      print(f'Error: {e}')
