import os
import subprocess
import re

pipelines = [
    r"..\AgenticWorkflowPlaywright\AgenticWorkflowDataGeneration",
    r"..\AgenticWorkflowPlaywright_QAs",
    r"..\AgenticWorkflowPlaywright_Reviews",
    r"..\AgenticWorkflowPlaywright_Tooling"
]

replacement_append = """

### Terms Mode and Deep Think Mode

**To use Terms Mode (generates tasks based on autonomous driving terms instead of PDFs):**
Place your terms list in `Input_terms/Terms.md`.
```bash
python pipeline.py --terms-mode
```

**To enable the Deep Think model (e.g., Gemini 2.0 Flash Thinking / Gemini Thinking):**
Can be combined with any mode to enable advanced reasoning capabilities.
```bash
python pipeline.py --deep-think
python pipeline.py --terms-mode --deep-think
```
"""

for repo in pipelines:
    print(f"=== Processing {repo} ===")
    readme_path = os.path.join(repo, "README.md")
    
    if not os.path.exists(readme_path):
        print(f"Skipping {repo}: README not found")
        continue

    # Update README
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "--terms-mode" not in content:
        # Append to the end of the file
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content.rstrip() + "\n" + replacement_append)
        print("Updated README.md content by appending!")
    else:
        print("Already updated or pattern found in README")

    # Now git commands
    subprocess.run(["git", "add", "README.md", "pipeline.py", "run_gemini_playwright_v2.py"], cwd=repo)
    terms_md = os.path.join("Input_terms", "Terms.md")
    subprocess.run(["git", "add", terms_md], cwd=repo)

    res = subprocess.run(["git", "commit", "-m", "feat: document and finalize terms mode and deep think pipeline versions"], cwd=repo, capture_output=True, text=True)
    if "nothing to commit" in res.stdout:
        print("Nothing to commit")
    else:
        print("Committed changes")

    tags_res = subprocess.run(["git", "tag", "-l"], cwd=repo, capture_output=True, text=True)
    existing_tags = tags_res.stdout.split()
    
    new_tag = "v1.4.0"
    if "v1.4.0" in existing_tags:
        new_tag = "v1.4.1"
    
    subprocess.run(["git", "tag", "-a", new_tag, "-m", f"Release {new_tag} - Integrated Terms Mode and Deep Think Support"], cwd=repo)
    print(f"Tagged as {new_tag}")

    # Find the current branch
    branch_res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, capture_output=True, text=True)
    branch = branch_res.stdout.strip()
    
    print(f"Pushing branch {branch}...")
    subprocess.run(["git", "push", "origin", branch], cwd=repo)
    print("Pushing tags...")
    subprocess.run(["git", "push", "origin", new_tag], cwd=repo)
    print("Done!\n")

# Re-push for Visuals and Concepts to ensure they pushed the branch properly
extra_repos = [r"..\AgenticWorkflowPlaywright_Visuals", r"..\AgenticWorkflowPlaywright_Concepts"]
for repo in extra_repos:
    branch_res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, capture_output=True, text=True)
    branch = branch_res.stdout.strip()
    subprocess.run(["git", "push", "origin", branch], cwd=repo)
    subprocess.run(["git", "push", "origin", "v1.4.0"], cwd=repo)
