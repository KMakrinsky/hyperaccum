# Scientific Paper Data Extraction - Validation Pipeline

This project is a pipeline designed to extract structured data from scientific papers in PDF format, convert it into a structured JSON format using Large Language Models (LLMs), and validate the extracted data for accuracy.

## Project Overview

**Note:** This repository contains a separate pipeline used for testing and validation purposes.

The main goal of this project is to automate the process of extracting detailed experimental information from scientific publications, particularly in the domain of phytoextraction and hyperaccumulation. It uses a combination of OCR, LLM-based data extraction, and LLM-assisted validation to ensure the quality of the extracted data.

## Workflow

The pipeline consists of three main stages:

1.  **PDF Processing (OCR)**: PDFs of scientific papers located in the `papers` directory are processed. Each page is converted into an image, and Google's Gemini API is used to perform Optical Character Recognition (OCR) to extract the raw text. The output is stored as Markdown files in the `ocr` directory.

2.  **Structured Data Generation**: The raw text from the Markdown files is then processed by an LLM to extract information according to a predefined JSON schema (found in `prompt.md`). This project supports two methods for this step:
    *   Using the **Google Gemini API** (`json_gen_gemini.py`).
    *   Using a **local LLM** served via LM Studio (`json_gen.py`).
    The generated structured data is saved as JSON files in the `json` directory.

3.  **Data Validation**: The accuracy of the extracted JSON data is assessed using two different validation scripts:
    *   **Semantic Validation against Ground Truth** (`csv_validator.py`): This script compares the generated JSON files against a manually created `ground_truth.csv`. It uses an LLM to semantically compare the data and calculates precision, recall, and F1-scores.
    *   **Claim Verification against Source Text** (`json_validator.py`): This script takes a different approach. It samples data points from the JSON, uses an LLM to formulate a verifiable claim (a statement in plain English), and then uses another LLM instance to act as a "judge" to verify if the claim is supported by the original text extracted from the PDF.

## File Descriptions

-   `process_papers.py`: Converts PDFs from the `/papers` folder into text via OCR and saves them as `.md` files in the `/ocr` folder.
-   `json_gen_gemini.py`: Uses the Google Gemini API to convert the `.md` text files into structured `.json` files based on the schema in `prompt.md`.
-   `json_gen.py`: Uses a local LLM (via LM Studio) to do the same task as `json_gen_gemini.py`.
-   `prompt.md`: Contains the detailed instructions and the JSON schema for the LLM to follow during data extraction.
-   `csv_validator.py`: Validates the generated JSON files against a `ground_truth.csv` by calculating precision, recall, and F1-score using an LLM for semantic comparison.
-   `json_validator.py`: Validates the generated JSON by creating factual claims from the data and having an LLM verify them against the source text.

## Setup and Usage

### Prerequisites

-   Python 3.x
-   An `.env` file containing your `GOOGLE_API_KEY`.
-   If using local models, an instance of [LM Studio](https://lmstudio.ai/) running with a model loaded.

### Installation

1.  Clone the repository:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```
2.  Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: A `requirements.txt` file should be created for this project)*

### Running the Pipeline

1.  **Place PDFs**: Add the scientific papers you want to process into the `papers/` directory.

2.  **Run OCR**: Execute the `process_papers.py` script to perform OCR on the PDFs.
    ```bash
    python process_papers.py
    ```

3.  **Generate JSON**: Run one of the JSON generation scripts.
    *   Using Gemini:
        ```bash
        python json_gen_gemini.py
        ```
    *   Using a local model via LM Studio:
        ```bash
        python json_gen.py
        ```

4.  **Validate Data**: Run the validation scripts to check the quality of the extracted data.
    *   For semantic validation (requires `ground_truth.csv`):
        ```bash
        python csv_validator.py
        ```
    *   For claim verification:
        ```bash
        python json_validator.py
        ```
The validation scripts will output CSV files with detailed metrics.
