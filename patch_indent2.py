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

      lines = content.split('\n')
      for i, l in enumerate(lines):
          if l.strip() == 'dt_label = " (Deep Think)" if args.deep_think else ""':
              lines[i] = '    ' + l.strip()
          elif l.strip() == 'print(f"  🧠 Model: Google Gemini 3.1 Pro{dt_label}")':
              lines[i] = '    ' + l.strip()
              
      content = '\n'.join(lines)
      
      with open(file_path, 'w', encoding='utf-8') as f:
          f.write(content)
      print(f'Fixed indent in {p}')
  except Exception as e:
      print(f'Error: {e}')
