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

      # Remove all DEEP_THINK_MODE = False
      content = content.replace("DEEP_THINK_MODE = False\n", "")
      content = content.replace("\nDEEP_THINK_MODE = False", "")
      
      # Now inject it back correctly at the top, right after `import time` or `import sys`
      # We know all pipelines import os, sys, time.
      if "import sys\n" in content:
          content = content.replace("import sys\n", "import sys\n\nDEEP_THINK_MODE = False\n")

      with open(file_path, 'w', encoding='utf-8') as f:
          f.write(content)
      print(f'Fixed DEEP_THINK_MODE indent in {p}')
  except Exception as e:
      print(f'Error: {e}')
