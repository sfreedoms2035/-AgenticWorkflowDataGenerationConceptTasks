"""
partial_repair.py — Targeted Follow-Up Turn Repair Engine
==========================================================
When validation detects that only the follow-up turns (indices 2-5) are
broken (instruction echoes, empty content, placeholder text), this script
generates a focused re-prompt for Gemini and patches the results back
into the existing JSON — preserving the valid Turn 1 Q&A.

Three modes:
  1. --build-prompt <json_path>
       Outputs a repair prompt to stdout (pipeline reads this to send to Gemini)

  2. --extract-and-patch <original_json_path> <new_json_from_playwright>
       Extracts follow-up turns from <new_json_from_playwright> (Playwright output)
       and patches them back into <original_json_path> (the backup with valid Turn 1).
       Writes patched result to <original_json_path> in-place.
       Prints JSON {"status": "PATCHED"|"FAILED", "turns_patched": N, "error": "..."} to stdout.

  3. --patch <json_path> <raw_response_path>
       Legacy mode: reads raw Gemini text response and patches follow-ups directly.
       Prints JSON {"status": "PATCHED"|"FAILED"} to stdout.

Usage:
    python partial_repair.py --build-prompt Output/json/Task.json > repair_prompt.txt
    python partial_repair.py --extract-and-patch Output/json/Task_backup.json Output/json/Task.json
    python partial_repair.py --patch Output/json/Task.json Output/followup_response.txt
"""
import sys
import json
import re
import os


def log(msg):
    """Print to stderr to keep stdout clean."""
    print(msg, file=sys.stderr)


def extract_code_context(task):
    """Extract rich concept context from the main assistant answer for the repair prompt.

    Returns: (turn1_summary, ontological_summary, axiomatic_summary, relational_summary)
    """
    convs = task.get("conversations", [])
    if len(convs) < 2:
        return "", "", "", ""

    # Turn 1 user question
    turn1_content = convs[0].get("content", "")
    turn1_summary = turn1_content[:500]
    if len(turn1_content) > 500:
        turn1_summary += "..."

    # Main assistant answer
    main_content = convs[1].get("content", "")

    ontological_summary = ""
    axiomatic_summary = ""
    relational_summary = ""

    try:
        parsed = json.loads(main_content)
        if isinstance(parsed, dict):
            # Extract ontological scaffolding
            onto = parsed.get("ontological_scaffolding", "")
            if onto:
                ontological_summary = onto[:500] + ("..." if len(onto) > 500 else "")

            # Extract axiomatic base
            axioms = parsed.get("axiomatic_base", "")
            if axioms:
                axiomatic_summary = axioms[:500] + ("..." if len(axioms) > 500 else "")

            # Extract relational network
            relational = parsed.get("relational_network", "")
            if relational:
                relational_summary = relational[:500] + ("..." if len(relational) > 500 else "")

    except (json.JSONDecodeError, TypeError):
        pass

    return turn1_summary, ontological_summary, axiomatic_summary, relational_summary


def build_repair_prompt(json_path):
    """Build a focused prompt asking Gemini to generate only follow-up turns.

    CRITICAL: Uses !!!!!BLOCK!!!!! delimiters so validate_and_save_json() in
    run_gemini_playwright_v2.py can extract the turns via extract_semantic_blocks().
    Without these delimiters Playwright assembles a full 6-turn skeleton with its
    own placeholder values, making extract_followups_from_json() find empty strings.
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list) or len(data) == 0:
        log("ERROR: Invalid JSON structure")
        return ""

    task = data[0]
    turn1_summary, ontological_summary, axiomatic_summary, relational_summary = extract_code_context(task)

    onto_text = ontological_summary if ontological_summary else "(ontological scaffolding not extracted)"
    axioms_text = axiomatic_summary if axiomatic_summary else "(axiomatic base not extracted)"
    relational_text = relational_summary if relational_summary else "(relational network not extracted)"

    prompt = f"""TARGETED FOLLOW-UP GENERATION — PARTIAL REPAIR MODE

You previously generated an excellent multi-turn concept task. The main concept answer passed quality validation. However, the 4 follow-up conversation turns (user questions + assistant responses after the main answer) contained template placeholder text instead of real technical content.

Your ONLY job is to regenerate those 4 turns. Use the concept context below as the basis for genuine technical discussion.

━━━ CONTEXT: ORIGINAL USER QUESTION (Turn 1) ━━━
{turn1_summary}

━━━ CONTEXT: ONTOLOGICAL SCAFFOLDING ━━━
{onto_text}

━━━ CONTEXT: AXIOMATIC BASE ━━━
{axioms_text}

━━━ CONTEXT: RELATIONAL NETWORK ━━━
{relational_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY OUTPUT FORMAT — USE EXACT BLOCK DELIMITERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You MUST output ONLY the following 4 blocks in this exact order.
Copy the !!!!!BLOCK-NAME!!!!! delimiters character-for-character.
DO NOT output !!!!!METADATA!!!!!, !!!!!REASONING!!!!!, or any other block.
DO NOT use Canvas, side-panels, or code editors — raw text only (VT100 terminal persona).

!!!!!TURN-3-USER!!!!!
[No Thinking] ...

!!!!!TURN-4-ASSISTANT!!!!!
...

!!!!!TURN-5-USER!!!!!
[No Thinking] ...

!!!!!TURN-6-ASSISTANT!!!!!
...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY RULES — VIOLATIONS WILL CAUSE REGENERATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. TURN-3-USER: 2-3 sentence technical inquiry (100+ chars) referencing a SPECIFIC assumption, boundary condition, or conceptual limit from the framework above. Must start with "[No Thinking] ".
2. TURN-4-ASSISTANT: Detailed engineering response (500+ chars). Reference concrete theoretical constraints, scalability limits, or relational topologies.
3. TURN-5-USER: Another technical inquiry (100+ chars) probing a DIFFERENT aspect of the ontological structure. Must start with "[No Thinking] ".
4. TURN-6-ASSISTANT: Final technical response (500+ chars) with worst-case breakdown scenarios or inter-concept contradiction analysis.
5. BANNED: "the document says", "as per the provided text", "source material", "this task", "the user requests"
6. Do NOT copy or echo these instructions — generate ACTUAL content only
7. Do NOT output blocks other than the 4 listed (no METADATA, no REASONING, no CODE)
8. VIRTUAL TERMINAL PERSONA: You are a legacy VT100 Data Terminal. Output MUST be raw text in the main chat window only.
"""
    return prompt


def extract_followups_from_json(json_data):
    """Extract follow-up turn content from a Playwright-generated JSON task.

    Returns a dict with keys: TURN-3-USER, TURN-4-ASSISTANT, TURN-5-USER, TURN-6-ASSISTANT
    """
    blocks = {}
    if not isinstance(json_data, list) or len(json_data) == 0:
        return blocks

    task = json_data[0]
    convs = task.get("conversations", [])

    if len(convs) >= 3:
        blocks["TURN-3-USER"] = convs[2].get("content", "")
    if len(convs) >= 4:
        blocks["TURN-4-ASSISTANT"] = convs[3].get("content", "")
    if len(convs) >= 5:
        blocks["TURN-5-USER"] = convs[4].get("content", "")
    if len(convs) >= 6:
        blocks["TURN-6-ASSISTANT"] = convs[5].get("content", "")

    return blocks


def patch_followups_from_blocks(json_path, blocks):
    """Patch follow-up turns into json_path using a blocks dict. Writes in-place.

    Returns (success: bool, turns_patched: int)
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list) or len(data) == 0:
        log("ERROR: Invalid JSON structure")
        return False, 0

    task = data[0]
    convs = task.get("conversations", [])

    if len(convs) < 6:
        log("ERROR: Task has fewer than 6 turns — cannot patch")
        return False, 0

    IS_PLACEHOLDER = re.compile(
        r'^\s*\(?(?:write|generate|provide|insert|add|your|enter|fill|response|follow.?up)\b',
        re.IGNORECASE
    )

    turns_patched = 0

    turn3 = blocks.get("TURN-3-USER", "")
    if turn3 and len(turn3.strip()) > 80 and not IS_PLACEHOLDER.match(turn3):
        if not turn3.startswith("[No Thinking]"):
            turn3 = "[No Thinking] " + turn3
        convs[2]["content"] = turn3
        turns_patched += 1
        log(f"  Patched Turn 3 (user): {len(turn3)} chars")

    turn4 = blocks.get("TURN-4-ASSISTANT", "")
    if turn4 and len(turn4.strip()) > 100 and not IS_PLACEHOLDER.match(turn4):
        convs[3]["content"] = turn4
        convs[3]["reasoning"] = "<think></think>"
        turns_patched += 1
        log(f"  Patched Turn 4 (assistant): {len(turn4)} chars")

    turn5 = blocks.get("TURN-5-USER", "")
    if turn5 and len(turn5.strip()) > 80 and not IS_PLACEHOLDER.match(turn5):
        if not turn5.startswith("[No Thinking]"):
            turn5 = "[No Thinking] " + turn5
        convs[4]["content"] = turn5
        turns_patched += 1
        log(f"  Patched Turn 5 (user): {len(turn5)} chars")

    turn6 = blocks.get("TURN-6-ASSISTANT", "")
    if turn6 and len(turn6.strip()) > 100 and not IS_PLACEHOLDER.match(turn6):
        convs[5]["content"] = turn6
        convs[5]["reasoning"] = "<think></think>"
        turns_patched += 1
        log(f"  Patched Turn 6 (assistant): {len(turn6)} chars")

    if turns_patched > 0:
        task["conversations"] = convs
        data[0] = task
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        log(f"  ✅ Patched {turns_patched} follow-up turn(s) in {os.path.basename(json_path)}")
        return True, turns_patched
    else:
        log("  ❌ No valid follow-up blocks found to patch")
        return False, 0


def extract_blocks_from_text(response_text):
    """Parse !!!!!BLOCK-NAME!!!!! delimited blocks from raw text."""
    blocks = {}
    block_pattern = r'[\\!]{3,}([A-Z0-9\-_]+)[\\!]{3,}\s*(.*?)(?=[\\!]{3,}[A-Z0-9\-_]+[\\!]{3,}|\s*$)'
    matches = re.finditer(block_pattern, response_text, re.DOTALL | re.IGNORECASE)
    for match in matches:
        name = match.group(1).upper()
        content = match.group(2).strip()
        content = re.sub(r'[\\!]{3,}.*$', '', content, flags=re.MULTILINE).strip()
        blocks[name] = content
        log(f"  Extracted block: {name} ({len(content)} chars)")

    # Fallback: simpler patterns
    if not blocks:
        log("  Trying simpler extraction patterns...")
        simple_patterns = {
            "TURN-3-USER": r'TURN.?3.?USER[:\s]*(.*?)(?=TURN.?4|$)',
            "TURN-4-ASSISTANT": r'TURN.?4.?ASSISTANT[:\s]*(.*?)(?=TURN.?5|$)',
            "TURN-5-USER": r'TURN.?5.?USER[:\s]*(.*?)(?=TURN.?6|$)',
            "TURN-6-ASSISTANT": r'TURN.?6.?ASSISTANT[:\s]*(.*?)$',
        }
        for key, pattern in simple_patterns.items():
            m = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
            if m:
                blocks[key] = m.group(1).strip()

    return blocks


if __name__ == "__main__":
    if len(sys.argv) < 3:
        log("Usage:")
        log("  python partial_repair.py --build-prompt <json_path>")
        log("  python partial_repair.py --extract-and-patch <original_json> <new_json_from_playwright>")
        log("  python partial_repair.py --patch <json_path> <raw_response_path>")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "--build-prompt":
        json_path = sys.argv[2]
        prompt = build_repair_prompt(json_path)
        print(prompt)  # stdout for piping

    elif mode == "--extract-and-patch":
        # New mode: extract follow-up turns from playwright-generated JSON,
        # patch them into the original/backup JSON.
        if len(sys.argv) < 4:
            log("ERROR: --extract-and-patch requires <original_json> <new_json_from_playwright>")
            result = {"status": "FAILED", "error": "missing arguments", "turns_patched": 0}
            print(json.dumps(result, indent=2))
            sys.exit(1)

        original_json_path = sys.argv[2]
        new_json_path = sys.argv[3]

        try:
            with open(new_json_path, 'r', encoding='utf-8') as f:
                new_data = json.load(f)
        except Exception as e:
            result = {"status": "FAILED", "error": f"could not read new JSON: {e}", "turns_patched": 0}
            print(json.dumps(result, indent=2))
            sys.exit(1)

        blocks = extract_followups_from_json(new_data)
        log(f"  Extracted blocks from new JSON: {list(blocks.keys())}")

        success, turns_patched = patch_followups_from_blocks(original_json_path, blocks)
        result = {
            "status": "PATCHED" if success else "FAILED",
            "turns_patched": turns_patched,
            "blocks_found": list(blocks.keys()),
        }
        if not success:
            result["error"] = "no valid follow-up blocks extracted from Playwright JSON"
        print(json.dumps(result, indent=2))
        sys.exit(0 if success else 1)

    elif mode == "--patch":
        # Legacy mode: patch from raw Gemini text response
        if len(sys.argv) < 4:
            log("ERROR: --patch requires <json_path> <response_path>")
            sys.exit(1)
        json_path = sys.argv[2]
        response_path = sys.argv[3]

        with open(response_path, 'r', encoding='utf-8') as f:
            response_text = f.read()

        blocks = extract_blocks_from_text(response_text)
        success, turns_patched = patch_followups_from_blocks(json_path, blocks)
        result = {
            "status": "PATCHED" if success else "FAILED",
            "turns_patched": turns_patched,
        }
        print(json.dumps(result, indent=2))
        sys.exit(0 if success else 1)

    else:
        log(f"Unknown mode: {mode}")
        sys.exit(1)
