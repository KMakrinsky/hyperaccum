import os
import google.generativeai as genai
import json
import time

# --- SETTINGS ---
OCR_DIR = 'ocr'
JSON_OUTPUT_DIR = 'json'
PROMPT_FILE = 'prompt.md'

# Retry settings as in your example
RETRY_COUNT = 3
RETRY_DELAY = 5  # seconds
# --- END OF SETTINGS ---

def configure_gemini():
    """Configures and verifies the API key for Gemini."""
    try:
        # The library automatically picks up the key from the GOOGLE_API_KEY environment variable
        api_key = "API here"
        if not api_key:
            print("[ERROR] Environment variable GOOGLE_API_KEY not found.")
            print("Please set it and restart the script.")
            return None
        genai.configure(api_key=api_key)
        print("Google Gemini API key configured successfully.")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to configure Gemini: {e}")
        return None

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

def get_gemini_response(system_prompt, user_content):
    """
    Sends a request to the Gemini API using syntax compatible with your library version.
    Includes a retry mechanism.
    """
    # Initialize the model. Recommended to use 'gemini-1.5-pro-latest'
    # for the best balance of performance and availability.
    model = genai.GenerativeModel('gemini-2.5-flash')

    # IMPORTANT: Ensure your prompt.md clearly specifies
    # to return ONLY JSON, as we cannot use response_mime_type.
    # Example: "Your answer must be a valid JSON object without ```json ... ```"

    for attempt in range(RETRY_COUNT):
        try:
            print(f"  Sending request to Google Gemini API (attempt {attempt + 1}/{RETRY_COUNT})...")

            # Create a list containing the system prompt and the article text, as in your working example.
            # This syntax is for older versions of the library.
            response = model.generate_content([system_prompt, user_content])
            
            # response.text is the simplest way to get the result
            gemini_response_text = response.text.strip()
            
            print("  Successfully received response from Gemini.")
            return gemini_response_text

        except Exception as e:
            print(f"  [ERROR] An error occurred while requesting Gemini API: {e}")
            if attempt < RETRY_COUNT - 1:
                print(f"  Retrying after {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  Failed to get a response from Gemini after {RETRY_COUNT} attempts.")
                return None
    return None

def main():
    """Main function to start the generation process."""
    print("--- Starting JSON generation script using Gemini ---")
    
    if not configure_gemini():
        return

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

        gemini_result = get_gemini_response(system_prompt, article_text)
        
        if gemini_result is not None:
            # Try to clean the response from possible artifacts such as ```json ... ```
            if gemini_result.startswith("```json"):
                gemini_result = gemini_result.strip("```json").strip()

            try:
                # Verify that the response is valid JSON
                json.loads(gemini_result)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(gemini_result)
                print(f"  ✅ Valid JSON from Gemini saved to '{output_path}'")
            except json.JSONDecodeError:
                print(f"  [WARNING] Gemini response is not valid JSON. Response was:\n---\n{gemini_result}\n---")
                # Save the raw response in a text file for debugging
                error_path = os.path.join(JSON_OUTPUT_DIR, f"{base_name}_error.txt")
                with open(error_path, 'w', encoding='utf-8') as f:
                    f.write(gemini_result)
                print(f"  Raw response saved for analysis at '{error_path}'")
            except Exception as e:
                print(f"  [ERROR] Failed to save file: {e}")
        else:
            print("  No response from Gemini; file will not be created.")

    print("\n--- Generation process completed. ---")

if __name__ == "__main__":
    main()