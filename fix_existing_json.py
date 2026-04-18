"""
Rescue script: Re-extract blocks from the jammed ontological_scaffolding
field in existing JSON files created by the old (broken) extractor.
"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_gemini_playwright_v2 import extract_semantic_blocks, clean_semantic_block


def fix_json_file(path):
    """Re-extract blocks from jammed ontological_scaffolding and fix the JSON."""
    data = json.loads(open(path, 'r', encoding='utf-8').read())
    task = data[0]
    convs = task['conversations']

    # Parse the inner content JSON (Turn 1 assistant content)
    try:
        content_obj = json.loads(convs[1]['content'])
    except (json.JSONDecodeError, IndexError):
        print(f"Cannot parse inner content JSON in {path}")
        return False

    onto = content_obj.get('ontological_scaffolding', '')
    if not onto or len(onto) < 1000:
        print(f"ontological_scaffolding is too short or empty, nothing to fix")
        return False

    # Re-extract blocks from the jammed content
    blocks = extract_semantic_blocks(onto)
    print(f"Re-extracted {len(blocks)} blocks from ontological_scaffolding")

    if len(blocks) < 5:
        print("Not enough blocks found in the jammed content, skipping fix")
        return False

    # --- Fix concept element fields ---
    concept_fields = [
        'abstraction_level', 'axiomatic_base', 'relational_network',
        'inferential_framework', 'methodological_apparatus', 'illustrative_corpus',
        'goal_orientation', 'limitations_and_risks', 'inter_concept_relationships'
    ]

    # Trim ontological_scaffolding to only content BEFORE the first sub-block delimiter
    # Find the position of the first !!!!!BLOCK!!!!! after the actual scaffolding text
    delim_pattern = re.compile(r'!{5}(ABSTRACTION_LEVEL|AXIOMATIC_BASE|RELATIONAL_NETWORK)!{5}')
    # Search in the normalized text (with escaped newlines converted)
    onto_norm = onto.replace('\\\\n', '\n').replace('\\n', '\n')
    delim_match = delim_pattern.search(onto_norm)
    if delim_match:
        # Find corresponding position in original text
        # Use the block name to find it
        block_name = delim_match.group(1)
        pos = onto.find(f"!!!!!{block_name}!!!!!")
        if pos < 0:
            # Try with escaped newlines before
            pos = onto.find(block_name)
            if pos > 5:
                pos = onto.rfind('!', 0, pos - 1)
                while pos > 0 and onto[pos - 1] == '!':
                    pos -= 1

        if pos > 0:
            content_obj['ontological_scaffolding'] = onto[:pos].rstrip().rstrip('\\n').strip()
            print(f"  Trimmed ontological_scaffolding to {len(content_obj['ontological_scaffolding'])} chars")

    for field in concept_fields:
        block_key = field.upper()
        if block_key in blocks and blocks[block_key]:
            content_obj[field] = blocks[block_key]
            print(f"  Fixed {field}: {len(blocks[block_key])} chars")

    # --- Fix follow-up turns ---
    turn_map = {
        'TURN-3-USER': 2,
        'TURN-4-ASSISTANT': 3,
        'TURN-5-USER': 4,
        'TURN-6-ASSISTANT': 5,
    }
    for block_name, idx in turn_map.items():
        if block_name in blocks and blocks[block_name]:
            existing = convs[idx].get('content', '')
            new_content = blocks[block_name]
            if len(new_content) > len(existing):
                convs[idx]['content'] = new_content
                print(f"  Fixed Turn {idx}: {len(new_content)} chars (was {len(existing)})")

    # Write back
    convs[1]['content'] = json.dumps(content_obj, indent=2, ensure_ascii=False)
    task['conversations'] = convs
    data[0] = task

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\nSaved fixed JSON to {path}")
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        # Default: fix all JSON in json_terms
        json_dir = os.path.join(os.path.dirname(__file__), 'Output', 'json_terms')
        files = [os.path.join(json_dir, f) for f in os.listdir(json_dir) if f.endswith('.json')]
    else:
        files = [sys.argv[1]]

    for fpath in files:
        print(f"\n{'='*60}")
        print(f"Processing: {os.path.basename(fpath)}")
        print('='*60)
        fix_json_file(fpath)
