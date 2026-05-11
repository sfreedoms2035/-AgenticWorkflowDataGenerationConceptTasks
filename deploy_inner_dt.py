import sys, os

pipelines = [
  r'C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright\AgenticWorkflowDataGeneration',
  r'C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright_QAs',
  r'C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright_Reviews',
  r'C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright_Tooling',
  r'C:\Users\User\VS_Projects\Helpers\Antigravity\AgenticWorkflowPlaywright_Visuals',
]

deep_think_injection = '''
        if deep_think:
            log("Activating Deep Think tool...")
            deep_think_activated = False
            
            def activate_deep_think(max_retries=3):
                """Click Tools → Deep Think in the Gemini UI using Playwright native locators."""
                nonlocal selected_model_name, deep_think_activated
                
                for attempt in range(max_retries):
                    try:
                        # Step 1: Find and click the Tools button
                        tools_clicked = False
                        
                        # Native locators based on screenshot "+ | Tools"
                        tools_selectors = [
                            \'button:has-text("Tools")\',
                            \'button:has-text("Werkzeuge")\',
                            \'button[aria-label*="Tools"]\',
                            \'button[aria-label*="Werkzeuge"]\',
                            \'button.tool-button\',
                            \'button[data-test-id="tools-button"]\'
                        ]
                        
                        for sel in tools_selectors:
                            try:
                                btn = page.locator(sel).first
                                if btn.is_visible(timeout=1000):
                                    btn.click()
                                    tools_clicked = True
                                    log(f"  Clicked tools button via: {sel}")
                                    break
                            except Exception:
                                continue
                        
                        if not tools_clicked:
                            # Try JS fallback
                            tools_clicked = page.evaluate("""() => {
                                const allBtns = document.querySelectorAll('button');
                                for (const btn of allBtns) {
                                    const text = (btn.innerText || '').trim().toLowerCase();
                                    if (text === 'tools' || text === 'werkzeuge' || text.includes('tool')) {
                                        if (btn.offsetParent !== null) {
                                            btn.click();
                                            return true;
                                        }
                                    }
                                }
                                return false;
                            }""")
                            
                        if not tools_clicked:
                            log(f"  ⚠️ Could not find Tools button (attempt {attempt+1})")
                            page.wait_for_timeout(1000)
                            continue
                        
                        page.wait_for_timeout(1500)  # Wait for menu animation
                        
                        # Step 2: Find and click Deep Think in the menu
                        dt_clicked = False
                        
                        # Native locators for dropdown item
                        dt_selectors = [
                            \'button:has-text("Deep Think")\',
                            \'.mat-mdc-menu-item:has-text("Deep Think")\',
                            \'[role="menuitem"]:has-text("Deep Think")\',
                            \'div[role="option"]:has-text("Deep Think")\',
                            \'span:has-text("Deep Think")\'
                        ]
                        
                        for sel in dt_selectors:
                            try:
                                option = page.locator(sel).last
                                if option.is_visible(timeout=1000):
                                    option.click()
                                    dt_clicked = True
                                    log(f"  ✅ Deep Think activated natively via: {sel}")
                                    break
                            except Exception:
                                continue
                        
                        if not dt_clicked:
                            # Try JS fallback
                            dt_clicked = page.evaluate("""() => {
                                const allElements = document.querySelectorAll('button, a, div[role="option"], span, [role="menuitem"]');
                                for (const el of allElements) {
                                    const text = (el.innerText || '').trim().toLowerCase();
                                    if ((text.includes('deep think') || text.includes('deepthink')) && el.offsetParent !== null) {
                                        el.click();
                                        return true;
                                    }
                                }
                                return false;
                            }""")
                            if dt_clicked:
                                log(f"  ✅ Deep Think activated JS fallback")
                        
                        if dt_clicked:
                            selected_model_name = "Gemini-3.1-pro-deep-think"
                            deep_think_activated = True
                            page.wait_for_timeout(1500)  # Wait for mode to take effect
                            return True
                        else:
                            log(f"  ⚠️ Deep Think option not found in menu (attempt {attempt+1})")
                            page.keyboard.press("Escape")
                            page.wait_for_timeout(500)
                    
                    except Exception as e:
                        log(f"  ⚠️ Deep Think activation error (attempt {attempt+1}): {e}")
                        try:
                            page.keyboard.press("Escape")
                        except Exception:
                            pass
                        page.wait_for_timeout(1000)
                
                log("  ⚠️ Could not activate Deep Think after all retries — proceeding without it")
                return False
            
            activate_deep_think()
            if deep_think_activated:
                selected_model_name = "Gemini-3.1-pro-deep-think"
'''

for p in pipelines:
  file_path = f'{p}\\run_gemini_playwright_v2.py'
  try:
      with open(file_path, 'r', encoding='utf-8') as f:
          content = f.read()

      # Remove the garbage top-level activate_deep_think injected originally by transfer_terms_mode.py
      # The problem: it spans around 40-50 lines. We need to snip it globally.
      if 'def activate_deep_think(page):' in content:
          parts = content.split('def activate_deep_think(page):')
          before = parts[0]
          
          # Find where the function ends - there is usually a "return False" followed by a blank line then maybe something else.
          # We can safely use regex or string finding.
          rest = parts[1]
          # Since it's exactly the snippet from transfer_terms_mode:
          end_sig = 'return False\n        \n    except Exception as e:\n        log(f"  ⚠️ Deep Think activation error: {e}")\n        return False\n'
          if end_sig in rest:
              idx = rest.find(end_sig) + len(end_sig)
              content = before + rest[idx:]
          else:
              print(f"Warning: Could not cleanly snip old global function in {p}")
              
      # Ensure it's not already injected inside run_gemini
      if 'def activate_deep_think(max_retries' not in content:
          # Inject the new deep think block right before: # --- FORCE DISABLE CANVAS UI CHIPS ---
          target_sig = '        # --- FORCE DISABLE CANVAS UI CHIPS ---'
          content = content.replace(target_sig, deep_think_injection + '\n' + target_sig)
          
      with open(file_path, 'w', encoding='utf-8') as f:
          f.write(content)
      print(f'Successfully injected locator logic into {p}')
      
  except Exception as e:
      print(f'Error patching {p}: {e}')
