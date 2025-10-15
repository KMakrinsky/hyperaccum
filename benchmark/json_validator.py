import json
import random
import os
import csv
from pathlib import Path
import requests 

# --- SETTINGS ---
SCRIPT_DIR = Path(__file__).parent.resolve()
JSON_DIR = SCRIPT_DIR / "json"
OCR_DIR = SCRIPT_DIR / "ocr"
OUTPUT_CSV_FILENAME = "validation_summary.csv"
NUM_SAMPLES_TO_VALIDATE = 3

# --- SETTINGS FOR CONNECTING TO LM STUDIO ---
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
# -----------------------------------------

# --- Helper functions (unchanged) ---
def load_json_data(filepath: Path) -> dict | None:
    try:
        with open(filepath, 'r', encoding='utf-8') as f: 
            return json.load(f)
    except FileNotFoundError: 
        print(f"  ERROR: JSON file not found: {filepath}")
        return None
    except json.JSONDecodeError: 
        print(f"  ERROR: Failed to read JSON file: {filepath}")
        return None

def load_source_text(filepath: Path) -> str | None:
    try:
        with open(filepath, 'r', encoding='utf-8') as f: 
            return f.read()
    except FileNotFoundError: 
        print(f"  ERROR: Source text file not found: {filepath}")
        return None

def flatten_json(data, parent_key='', sep='.'):
    items = {}
    if isinstance(data, dict):
        for k, v in data.items():
            new_key = parent_key + sep + k if parent_key else k
            items.update(flatten_json(v, new_key, sep=sep))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            new_key = f"{parent_key}{sep}{i}" if parent_key else str(i)
            items.update(flatten_json(v, new_key, sep=sep))
    else:
        if data is not None and data != "" and not isinstance(data, list):
             items[parent_key] = data
    return items

def get_structured_context(full_json: dict, path: str) -> dict | None:
    path_parts = path.split('.')
    context = {}
    try:
        if 'experimental_groups' in path_parts:
            group_index = int(path_parts[path_parts.index('experimental_groups') + 1])
            group_object = full_json.get('experimental_groups', [])[group_index]
            group_info = {
                "group_id": group_object.get("group_id"),
                "description": group_object.get("description"),
                "species": group_object.get("biological_material", {}).get("species")
            }
            context['group_info'] = {k: v for k, v in group_info.items() if v is not None}
    except (IndexError, ValueError, TypeError):
        context['group_info'] = None
    try:
        parent_path, temp_obj = path_parts[:-1], full_json
        for part in parent_path:
            if isinstance(temp_obj, list) and part.isdigit(): 
                temp_obj = temp_obj[int(part)]
            elif isinstance(temp_obj, dict): 
                temp_obj = temp_obj[part]
        if isinstance(temp_obj, dict): 
            context['local_context'] = temp_obj
        else: 
            context['local_context'] = None
    except (IndexError, KeyError, TypeError):
        context['local_context'] = None
    return context if context.get('local_context') else None

# --- Updated function for interacting with LM Studio ---
def query_lm_studio(messages: list) -> str | None:
    """Sends a request to the LM Studio server using an HTTP request."""
    headers = {"Content-Type": "application/json"}
    payload = {
        "messages": messages,
        "temperature": 0.5,
    }
    try:
        response = requests.post(LM_STUDIO_URL, headers=headers, json=payload, timeout=300)
        response.raise_for_status()
        response_json = response.json()
        return response_json['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        print(f"\n  NETWORK ERROR: Failed to connect to LM Studio. Ensure the server is running. {e}")
        return None
    except (KeyError, IndexError):
        print(f"\n  ERROR: Unexpected response format from LLM.")
        return None

# --- Functions for LLM adapted for query_lm_studio ---
def formulate_claim_with_llm(path: str, value, structured_context: dict) -> str | None:
    key_to_validate = path.split('.')[-1]
    system_prompt = "You are an expert in scientific data analysis. Your task is to turn a data snippet from JSON into a clear, verifiable statement in English. Use all the provided context to make the statement as informative as possible. Your response must contain ONLY the statement itself."
    user_prompt = f"""
                Here is the data for analysis:
                - Key to validate: "{key_to_validate}"
                - Its value: "{value}"
                [High-Level Group Context]:
                {json.dumps(structured_context.get('group_info'), ensure_ascii=False, indent=2)}
                [Local Data Context (the object where the key is located)]:
                {json.dumps(structured_context.get('local_context'), ensure_ascii=False, indent=2)}
                Rules:
                1. Create a single, highly informative sentence that can be verified against a scientific article.
                2. Combine information from both the high-level and local context.
                3. If validating a descriptive key (like 'element' or 'units'), formulate the statement about the associated numerical value from the local context.
                Example of a good result (if validating 'element: "Pb"'):
                In the study of Sesbania drummondii under the 'Pb only' treatment (group G1), the concentration of Pb in the shoot was 1268.0 mg/kg dw.
                Formulate a statement for the provided data.
                """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    print("    -> STEP 1: Sending request to formulate claim...")
    claim = query_lm_studio(messages)
    return claim.strip() if claim else None

def validate_claim_with_llm(claim: str, source_text: str) -> dict | None:
    system_prompt = "You are an AI assistant acting as a meticulous judge. Your task is to verify a statement against a source text. Your response must be ONLY a valid JSON object with the specified keys."
    user_prompt = f"""
                [SOURCE TEXT]:
                ---
                {source_text}
                ---
                [STATEMENT TO VERIFY]:
                ---
                {claim}
                ---
                Analyze the text and return ONLY a JSON object with:
                - "is_correct" (boolean): true if confirmed, otherwise false.
                - "quote_from_text" (string): The exact quote that confirms or refutes the statement.
                """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    print("    -> STEP 2: Sending claim to judge for verification...")
    response_str = query_lm_studio(messages)
    if not response_str: 
        return None
    try:
        json_part = response_str[response_str.find('{'):response_str.rfind('}')+1]
        return json.loads(json_part)
    except json.JSONDecodeError: 
        print(f"  ERROR: Judge returned invalid JSON: {response_str}")
        return None

# --- Core logic (unchanged) ---
def find_file_pairs(json_dir: Path, ocr_dir: Path) -> list:
    pairs = []
    if not json_dir.is_dir() or not ocr_dir.is_dir():
        print(f"ERROR: One of the directories was not found.")
        return []
    for json_file in json_dir.glob("*.json"):
        md_file = ocr_dir / f"{json_file.stem}.md"
        if md_file.exists(): 
            pairs.append({"name": json_file.stem, "json_path": json_file, "md_path": md_file})
    return pairs

def validate_file_pair(json_path: Path, source_text_path: Path) -> float:
    print(f"  Loading files: {json_path.name} and {source_text_path.name}...")
    full_json_data, source_text = load_json_data(json_path), load_source_text(source_text_path)
    if not full_json_data or not source_text: 
        return 0.0

    flat_data = flatten_json(full_json_data)
    filtered_points = [ (path, value) for path, value in flat_data.items()
        if not isinstance(value, bool) and not (isinstance(value, str) and len(value) > 300) and len(path.split('.')) > 1 ]
    
    sample_size = min(NUM_SAMPLES_TO_VALIDATE, len(filtered_points))
    if sample_size == 0:
        print("  WARNING: No suitable fields found for validation.")
        return 0.0
        
    sampled_points = random.sample(filtered_points, sample_size)
    print(f"  ✓ Selected {sample_size} random fields for verification.")

    validation_results, correct_answers_count = [], 0

    for i, (path, value) in enumerate(sampled_points):
        print(f"\n  --- Checking element {i+1}/{sample_size} (path: {path}) ---")
        
        structured_context = get_structured_context(full_json_data, path)
        if not structured_context:
            print("    ⚠️ Failed to collect structured context, skipping.")
            continue
        
        claim = formulate_claim_with_llm(path, value, structured_context)
        if not claim or '?' in claim or len(claim.split()) < 5:
            print("    ⚠️ Failed to formulate a correct statement, skipping.")
            continue
        print(f"    ✅ Formulated statement: \"{claim}\"")

        llm_verdict = validate_claim_with_llm(claim, source_text)
        if not llm_verdict:
            print("    ⚠️ Failed to obtain verdict from the judge, skipping.")
            continue
        
        validation_results.append({"path": path, "claim": claim, "verdict": llm_verdict})
        is_correct = llm_verdict.get("is_correct", False)
        quote = llm_verdict.get("quote_from_text", "Quote not found.")
        if is_correct:
            correct_answers_count += 1
            print(f"    ✅ VERDICT: Correct")
        else:
            print(f"    ❌ VERDICT: Incorrect")
        print(f"   💬 Quote from text: \"{quote}\"")

    if not validation_results:
        print("  No successful verifications were performed.")
        return 0.0
        
    accuracy = (correct_answers_count / len(validation_results)) * 100
    print(f"\n  --- Summary for file {json_path.name} ---\n  📊 Validation Score: {accuracy:.2f}%")
    return accuracy

def main():
    print("--- Starting data validation script ---")
    file_pairs = find_file_pairs(JSON_DIR, OCR_DIR)
    if not file_pairs:
        print("No matching .json/.md file pairs found.")
        return

    print(f"Found {len(file_pairs)} file pairs to process.")
    output_csv_path = SCRIPT_DIR / OUTPUT_CSV_FILENAME
    
    try:
        with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['filename', 'validation_score'])
            for i, pair in enumerate(file_pairs):
                print(f"\n{'='*50}\nProcessing pair {i+1}/{len(file_pairs)}: {pair['name']}\n{'='*50}")
                score = validate_file_pair(pair['json_path'], pair['md_path'])
                writer.writerow([pair['name'], f"{score:.2f}"])
        print("\n--- VALIDATION COMPLETED ---")
        print(f"✓ Final report saved to file: {output_csv_path}")
    except IOError as e: 
        print(f"ERROR: Failed to write final file. {e}")

if __name__ == "__main__":
    main()
