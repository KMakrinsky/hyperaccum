import os
import requests

# --- SETTINGS ---
OCR_DIR = 'ocr'
JSON_OUTPUT_DIR = 'json'
PROMPT_FILE = 'prompt.md'

# Settings for connecting to LM Studio
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
HEADERS = {"Content-Type": "application/json"}
# --- END SETTINGS ---

def load_prompt(file_path):
    """Loads the system prompt from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: System prompt file not found at path '{file_path}'")
        return None
    except Exception as e:
        print(f"Error reading the prompt file: {e}")
        return None

def get_llm_response(system_prompt, user_content):
    """Sends the system prompt and user content to the LLM, returning the raw response."""
    
    # Form the request with two messages: system and user
    payload = {
        "model": "local-model",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.1,
    }
    
    print("  Sending request to LM Studio...")
    try:
        response = requests.post(LM_STUDIO_URL, headers=HEADERS, json=payload, timeout=1500)
        response.raise_for_status()
        
        # Simply get the text response and return it
        llm_response_text = response.json()['choices'][0]['message']['content'].strip()
        print("  Successfully received response from LLM.")
        return llm_response_text

    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Failed to connect to LM Studio: {e}")
        return None
    except Exception as e:
        print(f"  [ERROR] Unexpected error during request: {e}")
        return None

def main():
    """Main function to start the generation process."""
    print("--- Starting JSON generation script ---")
    
    system_prompt = load_prompt(PROMPT_FILE)
    if not system_prompt:
        return
    print(f"Successfully loaded system prompt from '{PROMPT_FILE}'.")
    
    if not os.path.isdir(OCR_DIR):
        print(f"Error: Directory with MD files '{OCR_DIR}' not found.")
        return
    os.makedirs(JSON_OUTPUT_DIR, exist_ok=True)
    
    md_files = [f for f in os.listdir(OCR_DIR) if f.endswith('.md')]
    if not md_files:
        print(f"No .md files found in '{OCR_DIR}' for processing.")
        return
    
    total_files = len(md_files)
    print(f"Found {total_files} .md files to process.")

    for i, md_filename in enumerate(md_files):
        print(f"\n--- [ File {i + 1}/{total_files} ]: {md_filename} ---")
        
        base_name = os.path.splitext(md_filename)[0]
        input_path = os.path.join(OCR_DIR, md_filename)
        output_path = os.path.join(JSON_OUTPUT_DIR, f"{base_name}.json")
        
        if os.path.exists(output_path):
            print("  JSON file already exists. Skipping.")
            continue
            
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                article_text = f.read()
        except Exception as e:
            print(f"  [ERROR] Failed to read file: {e}")
            continue

        # Get raw response from LLM, passing prompt and text separately
        llm_result = get_llm_response(system_prompt, article_text)
        
        # If something was received, simply write it to a file
        if llm_result is not None:
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(llm_result)
                print(f"  ✅ LLM response saved as is to '{output_path}'")
            except Exception as e:
                print(f"  [ERROR] Failed to save file: {e}")
        else:
            print("  No response from LLM; file will not be created.")


    print("\n--- Generation process completed. ---")

if __name__ == "__main__":
    main()