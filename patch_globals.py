import sys
import re

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

      # 1. Clean up my broken string replacements
      content = content.replace(" deep_think=deep_think", "")
      content = content.replace(", deep_think=args.deep_think", "")
      content = content.replace(", deep_think=False", "")
      
      # For run_playwright calls, replace whatever they are currently with DEEP_THINK_MODE
      content = re.sub(r'deep_think=[a-zA-Z_]+', 'deep_think=DEEP_THINK_MODE', content)
      
      # 2. Inject DEEP_THINK_MODE at the top of the file
      if 'DEEP_THINK_MODE = False' not in content:
          content = content.replace("MAX_GEMINI_ATTEMPTS = 3", "MAX_GEMINI_ATTEMPTS = 3\nDEEP_THINK_MODE = False")
      elif 'DEEP_THINK_MODE = False' not in content and 'MAX_GEMINI_ATTEMPTS = 1' in content:
          content = content.replace("MAX_GEMINI_ATTEMPTS = 1", "MAX_GEMINI_ATTEMPTS = 1\nDEEP_THINK_MODE = False")
          
      # 3. Inject global assignment inside main
      if 'global DEEP_THINK_MODE' not in content:
          content = content.replace('args = parser.parse_args()', 'args = parser.parse_args()\n    global DEEP_THINK_MODE\n    DEEP_THINK_MODE = getattr(args, "deep_think", False)')

      with open(file_path, 'w', encoding='utf-8') as f:
          f.write(content)
      print(f'Refactored DEEP_THINK into global in {p}')
  except Exception as e:
      print(f'Error patching {p}: {e}')
