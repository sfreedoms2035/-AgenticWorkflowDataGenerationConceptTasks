# Agentic Workflow - Data Generation Concepts Pipeline

This repository contains an autonomous Playwright-driven web agent that automatically extracts highly theoretical 10-element automotive Concept data structures from PDF documents using Google Gemini's web interface. 

The pipeline handles advanced mathematical reasoning, extracts continuous kinematic/SOTIF topologies, and outputs rigorous, schema-compliant JSON data files without utilizing restricted web APIs.

## Features
- **Browser Automation Layer:** Leverages Playwright to automate interactions with the Google Gemini web application, bypassing the need for paid API tokens.
- **Canvas-Mode Safety Gate:** Prompts and extraction heuristics are strictly hardened to prevent Gemini from utilizing interactive Canvas/Code environments, guaranteeing raw JSON responses. 
- **Auto-Repair Engine:** Included `auto_repair.py` catches malformed schemas, structurally truncated logic, and corrupted metadata block injections.
- **Topological Integrity:** Designed to mandate strict verification of formal mathematical elements (Vertices, Edges, Constraints) using a set-theoretic graph model over SysML/XML tags.

## Installation Guidelines (For a New Computer)

### Prerequisites
- Python 3.10+
- Google Chrome browser (for the Playwright default user-data hook)

### 1. Clone the Repository
```bash
git clone https://github.com/sfreedoms2035/-AgenticWorkflowDataGenerationConceptTasks.git
cd -AgenticWorkflowDataGenerationConceptTasks
```

### 2. Set Up a Virtual Environment (Recommended)
```bash
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

### 3. Install Dependencies
Install the strictly required Python packages:
```bash
pip install playwright pygetwindow json_repair
```

### 4. Install Playwright Browsers
The pipeline strictly requires the automated Chromium binaries. Run the following command:
```bash
playwright install chromium
```

### 5. Google Context Authentication
Because this pipeline interfaces directly with the Gemini Web Application, you must authenticate manually the *first* time.
1. Run a script using Playwright in non-headless mode, or run `process_pdf` sequentially.
2. The browser will open. Log into your Google account.
3. The session data is permanently cached in the `.playwright_profile/` directory.

## Pipeline Usage

Place your source PDF documents in the `Input/` directory.

**To start or resume the standard PDF generation pipeline:**
```bash
python pipeline.py --resume
```

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

**(Optional) Enable the live UI render preview to visually monitor progress:**
```bash
python pipeline.py --resume --preview
```

### Artifacts and Output
- Validated Tasks: `./Output/json/`
- Full Chain-of-Thought Traces: `./Output/thinking/`
- Process State: `./Output/progress.json`
- Prompt Trace Cache: `./Output/prompts/`
