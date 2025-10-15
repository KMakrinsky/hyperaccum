import google.generativeai as genai
import os
import fitz  # PyMuPDF
from PIL import Image
import time

# --- SETTINGS ---
# Insert your API key for Gemini
GOOGLE_API_KEY = 'Api gere'

# Folder names
PAPERS_DIR = 'papers'
OCR_DIR = 'ocr'
TEMP_IMAGE_DIR = 'temp_images'

# API settings
# Delay between API requests in seconds
DELAY_BETWEEN_REQUESTS = 5
# Number of retry attempts on error
RETRY_COUNT = 3
# Delay before a retry attempt in seconds
RETRY_DELAY = 10
# --- END SETTINGS ---

# Gemini API configuration
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')


def create_directories():
    """Creates necessary directories if they do not exist."""
    for dir_path in [PAPERS_DIR, OCR_DIR, TEMP_IMAGE_DIR]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"Folder '{dir_path}' created.")


def get_system_prompt(page_num, total_pages):
    """Forms the system prompt for the specified page."""
    return f"""
You are an expert at extracting content from scientific research papers. 
Please extract all content from this page {page_num} of {total_pages}, maintaining the original structure and formatting.
Focus on:
- Main text content
- Headers and subheaders
- For tables return in text pandas Dataframe with extracted data wich will be ready for visualization in pandas or seaborn or matplotlib and place them in box for example ===TABLE=== ===ENDTABLE===
- For figures with charts and plots return dataframe with detailed extracted data, which will be ready for reprodution in python with seaborn or matplotlib and place them in box for example ===FIGURE=== ===ENDFIGURE===
- For complex figures return extensive explanation of the figure and the data behind it and place them in box for example ===FIGURE=== ===ENDFIGURE===
- References (include full citations)
- Any numerical data, formulas, or experimental results
- formulas and equations in LaTeX format

Please return the complete extracted text in a clean, readable format.
Preserve the logical structure of the document including sections, subsections, and paragraphs.
"""


def ocr_page_with_gemini(image_path, page_num, total_pages):
    """Sends the page image and system prompt to the Gemini API."""
    prompt = get_system_prompt(page_num, total_pages)

    for attempt in range(RETRY_COUNT):
        try:
            print(f"Sending page {page_num} for OCR (attempt {attempt + 1}/{RETRY_COUNT})...")
            img = Image.open(image_path)

            response = model.generate_content([prompt, img], stream=True)
            response.resolve()

            if response.candidates and response.candidates[0].content.parts:
                return response.text
            else:
                print(f"Warning: API response for page {page_num} does not contain text.")
                return "[Content not found]"

        except Exception as e:
            print(f"Error contacting Gemini API for page {page_num}: {e}")
            if attempt < RETRY_COUNT - 1:
                print(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"Failed to get a response from the API for page {page_num} after {RETRY_COUNT} attempts.")
                return None
    return None


def process_pdf(pdf_path, temp_dir):
    """
    Splits a PDF into pages, saves them as images, and returns their paths.
    FIXED VERSION OF THE FUNCTION.
    """
    image_paths = []
    try:
        doc = fitz.open(pdf_path)
        # Store the page count before closing the document
        total_pages = len(doc)
        print(f"Processing PDF: '{os.path.basename(pdf_path)}'. Total pages: {total_pages}")

        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            # DPI 300 – good quality for OCR
            pix = page.get_pixmap(dpi=300)
            image_path = os.path.join(temp_dir, f"page_{page_num + 1}.png")
            pix.save(image_path)
            image_paths.append(image_path)

        # Close the document after all operations are finished
        doc.close()
        # Return the list of image paths and the page count
        return image_paths, total_pages
    except Exception as e:
        print(f"Failed to process PDF file '{pdf_path}': {e}")
        return [], 0


def main():
    """Main function that runs the whole process."""
    create_directories()

    pdf_files = [f for f in os.listdir(PAPERS_DIR) if f.lower().endswith('.pdf')]

    if not pdf_files:
        print(f"No PDF files found in folder '{PAPERS_DIR}'.")
        return

    for pdf_file in pdf_files:
        pdf_path = os.path.join(PAPERS_DIR, pdf_file)
        base_name = os.path.splitext(pdf_file)[0]
        md_file_path = os.path.join(OCR_DIR, f"{base_name}.md")

        # Create a temporary folder for images of the current PDF
        current_temp_dir = os.path.join(TEMP_IMAGE_DIR, base_name)
        if not os.path.exists(current_temp_dir):
            os.makedirs(current_temp_dir)

        page_image_paths, total_pages = process_pdf(pdf_path, current_temp_dir)

        if not page_image_paths:
            continue

        full_text = f"# OCR text from file: {pdf_file}\n\n"
        for i, img_path in enumerate(page_image_paths):
            page_number = i + 1
            print(f"\n--- Processing page {page_number}/{total_pages} of file '{pdf_file}' ---")

            extracted_text = ocr_page_with_gemini(img_path, page_number, total_pages)

            # Add a separator and header for each page
            full_text += "---\n\n"
            full_text += f"## Page {page_number}\n\n"

            if extracted_text:
                full_text += extracted_text + "\n\n"
                print("Text successfully extracted.")
            else:
                full_text += "[Failed to extract text on this page]\n\n"
                print("Failed to extract text.")

            # Delete the temporary image after processing
            os.remove(img_path)

            # Delay before the next request to avoid hitting API limits
            if i < len(page_image_paths) - 1:
                print(f"Delaying for {DELAY_BETWEEN_REQUESTS} seconds...")
                time.sleep(DELAY_BETWEEN_REQUESTS)

        # Save the full text to an MD file
        try:
            with open(md_file_path, 'w', encoding='utf-8') as md_file:
                md_file.write(full_text)
            print(f"\n✅ OCR text fully saved to: '{md_file_path}'")
        except IOError as e:
            print(f"❌ Error writing to file '{md_file_path}': {e}")

        # Delete the temporary folder for images after processing the PDF
        try:
            os.rmdir(current_temp_dir)
        except OSError as e:
            print(f"Could not delete temporary folder '{current_temp_dir}': {e}")

    # Delete the main temporary folder if it is empty
    try:
        if not os.listdir(TEMP_IMAGE_DIR):
            os.rmdir(TEMP_IMAGE_DIR)
    except OSError as e:
        print(f"Could not delete main temporary folder '{TEMP_IMAGE_DIR}': {e}")


if __name__ == '__main__':
    main()
