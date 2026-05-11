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

      bad_str1 = "print(f\"  🧠 Model: Google Gemini 3.1 Pro {\\\'(Deep Think)\\\' if args.deep_think else \\\'\\\'}\")"
      bad_str2 = 'print(f"  🧠 Model: Google Gemini 3.1 Pro {\\\'(Deep Think)\\\' if args.deep_think else \\\'\\\'}")'
      
      good_str = 'dt_label = " (Deep Think)" if args.deep_think else ""\n        print(f"  🧠 Model: Google Gemini 3.1 Pro{dt_label}")'
      
      # We just look for the corrupted line. Since it has bad backslash formatting:
      lines = content.split('\n')
      for i, l in enumerate(lines):
          if '🧠 Model: Google Gemini 3.1 Pro' in l and 'if args.deep_think' in l:
              lines[i] = "        " + good_str
              
      content = '\n'.join(lines)
      
      with open(file_path, 'w', encoding='utf-8') as f:
          f.write(content)
      print(f'Fixed f-string in {p}')
  except Exception as e:
      print(f'Error: {e}')
