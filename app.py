#!/usr/bin/env python3
"""
Phytoextraction Research Data Extractor Backend
FastAPI backend for processing scientific articles and extracting experimental data
"""

import os
import json
import asyncio
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

# Load environment variables from config.env FIRST
from dotenv import load_dotenv
load_dotenv('config.env')

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import pymongo
from pymongo import MongoClient
import openai
import requests
from PyPDF2 import PdfReader
import fitz  # PyMuPDF
from validator_module import JSONValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Log which config file is being used
config_file = 'config.env'
if os.path.exists(config_file):
    logger.info(f"🔍 Loading environment variables from: {config_file}")
else:
    logger.warning(f"🔍 Config file not found: {config_file}")

# Set validator module logging to INFO level
validator_logger = logging.getLogger('validator_module')
validator_logger.setLevel(logging.INFO)

# Initialize FastAPI app
app = FastAPI(title="Phytoextraction Data Extractor", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files with no-cache headers for development
class NoCacheStaticFiles(StaticFiles):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    async def __call__(self, scope, receive, send):
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Add no-cache headers for CSS and JS files in development
                headers = list(message.get("headers", []))
                headers.append((b"cache-control", b"no-store, no-cache, must-revalidate, max-age=0"))
                headers.append((b"pragma", b"no-cache"))
                headers.append((b"expires", b"0"))
                message["headers"] = headers
            await send(message)
        
        await super().__call__(scope, receive, send_wrapper)

app.mount("/static", NoCacheStaticFiles(directory="static"), name="static")

# Serve the main page
@app.get("/")
async def read_root():
    response = FileResponse('index.html')
    # Add no-cache headers for development
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Configuration
class Config:
    MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017/")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "phytoextraction_db")
    COLLECTION_NAME = os.getenv("COLLECTION_NAME", "research_articles")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234")
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # Nougat configuration
    NOUGAT_MODEL = "0.1.0-base"
    NOUGAT_TIMEOUT = 300  # 5 minutes timeout

config = Config()

# Database connection
try:
    client = MongoClient(config.MONGODB_URL)
    db = client[config.DATABASE_NAME]
    collection = db[config.COLLECTION_NAME]
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    client = None
    db = None
    collection = None

# Pydantic models
class DOIRequest(BaseModel):
    doi: str
    method: str

class LLMExtractionRequest(BaseModel):
    text: str
    provider: str
    original_filename: Optional[str] = None
    ocr_filename: Optional[str] = None

class QueryGenerationRequest(BaseModel):
    natural_language: str
    provider: str = "simple"  # "simple", "openai", "lm-studio", "ollama"

class DatabaseQueryRequest(BaseModel):
    query: str

class ProcessingResponse(BaseModel):
    processed_text: str
    success: bool
    message: str
    saved_files: Optional[List[Dict[str, str]]] = None

class ExtractionResponse(BaseModel):
    extracted_data: Dict[Any, Any]
    success: bool
    message: str
    json_filename: Optional[str] = None
    ocr_filename: Optional[str] = None

# Load extraction prompt
def load_extraction_prompt():
    """Load the LLM extraction prompt from prompt.md"""
    try:
        with open("prompt.md", "r", encoding="utf-8") as f:
            prompt_content = f.read()
            logger.info(f"Successfully loaded prompt.md ({len(prompt_content)} characters)")
            return prompt_content
    except FileNotFoundError:
        logger.warning("prompt.md not found, using default prompt")
        return """
        Extract experimental data from this phytoextraction research article.
        Focus on:
        - Plant species used
        - Heavy metals studied (Cd, Pb, Zn, Cu, Ni, Cr, etc.)
        - Soil concentrations
        - Plant tissue concentrations
        - Bioaccumulation factors
        - Translocation factors
        - Experimental conditions (pH, temperature, duration)
        - Growth parameters
        
        Return the data in JSON format with clear structure.
        """

# Load query generation prompt
def load_query_prompt():
    """Load the query generation prompt from prompt_query.md"""
    try:
        with open("prompt_query.md", "r", encoding="utf-8") as f:
            prompt_content = f.read()
            logger.info(f"Successfully loaded prompt_query.md ({len(prompt_content)} characters)")
            return prompt_content
    except FileNotFoundError:
        logger.warning("prompt_query.md not found, using default query prompt")
        return """
        You are a MongoDB query generator for a phytoextraction research database.
        Convert natural language queries to MongoDB query syntax.
        
        The database contains documents with fields like:
        - plant_species: string
        - heavy_metals: array of metal symbols (Cd, Pb, Zn, Cu, Ni, Cr, As, Hg)
        - soil_concentrations: object with metal concentrations
        - plant_concentrations: object with metal concentrations
        - bioaccumulation_factors: object
        - translocation_factors: object
        - experimental_conditions: object (pH, temperature, duration)
        - growth_parameters: object
        
        Return only valid MongoDB query JSON, no explanations.
        """

# Serve the main HTML page
@app.get("/")
async def serve_index():
    return FileResponse("index.html")

@app.get("/health")
async def health_check():
    """Health check endpoint to verify database connection"""
    try:
        if client is not None:
            # Ping the database
            client.admin.command('ping')
            return {"status": "healthy", "database": "connected"}
        else:
            return {"status": "unhealthy", "database": "disconnected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database health check failed: {str(e)}")

@app.get("/prompt-info")
async def get_prompt_info():
    """Get information about the loaded extraction prompt"""
    try:
        prompt_content = load_extraction_prompt()
        return {
            "prompt_length": len(prompt_content),
            "prompt_preview": prompt_content[:500] + "..." if len(prompt_content) > 500 else prompt_content,
            "prompt_source": "prompt.md" if os.path.exists("prompt.md") else "default",
            "success": True
        }
    except Exception as e:
        logger.error(f"Error getting prompt info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/query-prompt-info")
async def get_query_prompt_info():
    """Get information about the loaded query generation prompt"""
    try:
        prompt_content = load_query_prompt()
        return {
            "prompt_length": len(prompt_content),
            "prompt_preview": prompt_content[:500] + "..." if len(prompt_content) > 500 else prompt_content,
            "prompt_source": "prompt_query.md" if os.path.exists("prompt_query.md") else "default",
            "success": True
        }
    except Exception as e:
        logger.error(f"Error getting query prompt info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test-prompt")
async def test_prompt(request: LLMExtractionRequest):
    """Test prompt formatting without sending to LLM"""
    try:
        system_prompt = load_extraction_prompt()
        
        # Format the request as it would be sent to different LLM providers
        openai_format = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract experimental data from this text:\n\n{request.text}"}
            ]
        }
        
        lm_studio_format = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract experimental data from this text:\n\n{request.text}"}
            ]
        }
        
        ollama_format = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract experimental data from this text:\n\n{request.text}"}
            ]
        }
        
        return {
            "system_prompt_length": len(system_prompt),
            "text_length": len(request.text),
            "openai_format": openai_format,
            "lm_studio_format": lm_studio_format,
            "ollama_format": ollama_format,
            "success": True
        }
    except Exception as e:
        logger.error(f"Error testing prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/file-pairs")
async def get_saved_file_pairs():
    """Get list of saved OCR-JSON file pairs"""
    try:
        pairs = get_file_pairs()
        return {
            "file_pairs": pairs,
            "count": len(pairs),
            "success": True
        }
    except Exception as e:
        logger.error(f"Error getting file pairs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download a saved file"""
    try:
        # Check in markdown directory for .md files
        if filename.endswith('.md'):
            file_path = Path("markdown") / filename
        # Check in json directory for .json files
        elif filename.endswith('.json'):
            file_path = Path("json") / filename
        else:
            # Fallback to outputs directory for backwards compatibility
            file_path = Path("outputs") / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type='application/octet-stream'
        )
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# semantic_anchor: doi_processing_implementation
@app.post("/process-doi", response_model=ProcessingResponse)
async def process_doi(request: DOIRequest):
    """Process a scientific article using its DOI"""
    try:
        logger.info(f"Processing DOI: {request.doi} with method: {request.method}")
        
        # For now, return a placeholder response
        # In a real implementation, you would:
        # 1. Fetch the PDF from the DOI
        # 2. Process it with the selected OCR method
        processed_text = f"[Processed text for DOI: {request.doi}]\n\nThis is a placeholder for the actual OCR processing results. The article would be downloaded and processed using {request.method}."
        
        return ProcessingResponse(
            processed_text=processed_text,
            success=True,
            message=f"Successfully processed DOI with {request.method}"
        )
    except Exception as e:
        logger.error(f"Error processing DOI: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# semantic_anchor: file_processing_implementation
@app.post("/process-files", response_model=ProcessingResponse)
async def process_files(files: List[UploadFile] = File(...), method: str = Form("nougat")):
    """Process uploaded PDF files with the selected OCR method"""
    try:
        logger.info(f"Processing {len(files)} files with method: {method}")
        logger.info(f"Method type: {type(method)}, Method value: '{method}'")
        logger.info(f"Method comparison - 'api': {method == 'api'}, 'nougat': {method == 'nougat'}, 'lm-studio': {method == 'lm-studio'}")
        
        processed_texts = []
        saved_files = []
        
        for file in files:
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF")
            
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            try:
                if method == "nougat":
                    logger.info("🔍 Selected method is 'nougat', calling process_with_nougat")
                    text = await process_with_nougat(temp_file_path)
                elif method == "lm-studio":
                    logger.info("🔍 Selected method is 'lm-studio', calling process_with_lm_studio")
                    text = await process_with_lm_studio(temp_file_path)
                elif method == "api":
                    logger.info("🔍 Selected method is 'api', calling process_with_api")
                    text = await process_with_api(temp_file_path)
                else:
                    logger.error(f"🔍 Unknown method: '{method}'")
                    raise HTTPException(status_code=400, detail=f"Unknown OCR method: {method}")
                
                # Remove references section
                text = remove_references_section(text)
                
                # semantic_anchor: parallel_ocr_saving
                # Save OCR text automatically
                ocr_filename = save_ocr_text(file.filename, text, method)
                saved_files.append({
                    "original_file": file.filename,
                    "ocr_file": ocr_filename,
                    "method": method
                })
                
                processed_texts.append(f"=== {file.filename} ===\n\n{text}")
                
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
        
        combined_text = "\n\n" + "="*50 + "\n\n".join(processed_texts)
        
        return ProcessingResponse(
            processed_text=combined_text,
            success=True,
            message=f"Successfully processed {len(files)} files with {method}",
            saved_files=saved_files
        )
        
    except Exception as e:
        logger.error(f"Error processing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# semantic_anchor: nougat_ocr_execution
async def process_with_nougat(pdf_path: str) -> str:
    """Process PDF with Nougat OCR (handles the termination bug)"""
    try:
        logger.info("🔍 process_with_nougat() called - using Nougat OCR")
        output_dir = tempfile.mkdtemp()
        output_file = os.path.join(output_dir, "output.mmd")
        
        # Construct nougat command
        cmd = [
            "nougat", 
            pdf_path,
            "-o", output_dir,
            "--no-skipping",
            "--markdown",
            "--batchsize==1", #checking stability
            "-m", config.NOUGAT_MODEL
        ]
        
        logger.info(f"Running Nougat command: {' '.join(cmd)}")
        
        # Run nougat with timeout
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Wait for process completion or timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=config.NOUGAT_TIMEOUT
            )
        except asyncio.TimeoutError:
            # Kill the process if it times out (handles the bug)
            process.kill()
            await process.wait()
            logger.warning("Nougat process timed out, checking for output file")
        
        # Check if output file exists (even if process didn't terminate properly)
        expected_output = os.path.join(output_dir, os.path.splitext(os.path.basename(pdf_path))[0] + ".mmd")
        
        if os.path.exists(expected_output):
            with open(expected_output, 'r', encoding='utf-8') as f:
                result = f.read()
        elif os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                result = f.read()
        else:
            # Fallback to basic PDF text extraction
            logger.warning("Nougat failed, falling back to basic PDF extraction")
            result = extract_text_from_pdf(pdf_path)
        
        # Clean up
        shutil.rmtree(output_dir, ignore_errors=True)
        
        return result
        
    except Exception as e:
        logger.error(f"Nougat processing failed: {e}")
        # Fallback to basic PDF extraction
        return extract_text_from_pdf(pdf_path)

# semantic_anchor: lm_studio_integration
async def process_with_lm_studio(pdf_path: str) -> str:
    """Process PDF using LM Studio for OCR"""
    try:
        # First extract text using PyMuPDF
        text = extract_text_from_pdf(pdf_path)
        
        # Prepare prompt for LM Studio
        prompt = f"""
        Please clean and format this extracted PDF text. Remove any OCR artifacts, 
        fix formatting issues, and structure the text properly:
        
        {text}
        """
        
        # Call LM Studio API
        response = requests.post(
            f"{config.LM_STUDIO_URL}/v1/completions",
            json={
                "prompt": prompt,
                "max_tokens": 4000,
                "temperature": 0.1
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("choices", [{}])[0].get("text", text)
        else:
            logger.warning(f"LM Studio API failed: {response.status_code}")
            return text
            
    except Exception as e:
        logger.error(f"LM Studio processing failed: {e}")
        return extract_text_from_pdf(pdf_path)

# semantic_anchor: gemini_ocr_implementation
async def process_with_api(pdf_path: str) -> str:
    """Process PDF using Gemini API for direct OCR without PyMuPDF preprocessing"""
    try:
        logger.info("🔍 process_with_api() called - using Gemini API for direct OCR")
        logger.info(f"🔍 GEMINI_API_KEY: {config.GEMINI_API_KEY[:10]}...{config.GEMINI_API_KEY[-10:] if len(config.GEMINI_API_KEY) > 20 else '***'}")
        logger.info(f"🔍 GEMINI_API_KEY length: {len(config.GEMINI_API_KEY) if config.GEMINI_API_KEY else 0}")
        
        if not config.GEMINI_API_KEY:
            logger.warning("No Gemini API key configured, falling back to basic extraction")
            return extract_text_from_pdf(pdf_path)
        
        # Use Gemini API for direct OCR
        return await process_with_gemini_ocr(pdf_path)
            
    except Exception as e:
        logger.error(f"API processing failed: {e}")
        return extract_text_from_pdf(pdf_path)

async def process_with_gemini_ocr(pdf_path: str) -> str:
    """Process PDF using Gemini API with page-by-page OCR by default"""
    try:
        logger.info("Using page-by-page Gemini OCR processing by default")
        return await process_large_pdf_with_gemini(pdf_path)
            
    except Exception as e:
        logger.error(f"Gemini OCR processing failed: {e}")
        # Fallback to basic PDF extraction
        return extract_text_from_pdf(pdf_path)

async def process_large_pdf_with_gemini(pdf_path: str) -> str:
    """Process PDF files by splitting into pages and processing with Gemini (default method)"""
    try:
        import google.generativeai as genai
        import base64
        import fitz  # PyMuPDF for page splitting
        
        # Configure the Gemini API
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Open PDF and get page count
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        logger.info(f"Processing PDF with {total_pages} pages using Gemini page-by-page OCR")
        
        extracted_texts = []
        
        # Process each page individually
        for page_num in range(total_pages):
            try:
                # Get page as image
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Higher resolution
                
                # Convert to PNG bytes
                png_bytes = pix.tobytes("png")
                png_base64 = base64.b64encode(png_bytes).decode('utf-8')
                
                # Create prompt for page OCR
                page_prompt = f"""
                You are an expert at extracting content from scientific research papers. 
                Please extract all  content from this page {page_num + 1} of {total_pages}, 


                maintaining the original structure and formatting.
                     Focus on:
                    - Main text content
                    - Headers and subheaders

                    - For tables return Dataframe with extracted data wich will be ready for visualization in pandas or seaborn or matplotlib and place them in box for example ===TABLE=== ===ENDTABLE===
                    - For figures with charts and plots return dataframe with detailed extracted data, which will be ready for reprodution in python with seaborn or matplotlib and place them in box for example ===FIGURE=== ===ENDFIGURE===
                    - For complex figures return extensive explanation of the figure and the data behind it and place them in box for example ===FIGURE=== ===ENDFIGURE===
                    - References (include full citations)
                    - Any numerical data, formulas, or experimental results
                    
                    Please return the complete extracted text in a clean, readable format.
                    Preserve the logical structure of the document including sections, subsections, and paragraphs.
                    
                """
                
                # Create content parts for this page
                content_parts = [
                    page_prompt,
                    {
                        "mime_type": "image/png",
                        "data": png_base64
                    }
                ]
                
                logger.info(f"Processing page {page_num + 1}/{total_pages}")
                
                # Generate content for this page
                response = model.generate_content(content_parts)
                
                if response.text:
                    page_text = response.text.strip()
                    extracted_texts.append(f"\n--- Page {page_num + 1} ---\n{page_text}")
                    logger.info(f"Successfully extracted {len(page_text)} characters from page {page_num + 1}")
                else:
                    logger.warning(f"Empty response for page {page_num + 1}")
                
                # Add small delay to avoid rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing page {page_num + 1}: {e}")
                # Continue with next page
        
        doc.close()
        
        if extracted_texts:
            combined_text = "\n".join(extracted_texts)
            logger.info(f"Successfully processed {len(extracted_texts)} pages with Gemini page-by-page OCR")
            return combined_text
        else:
            logger.warning("No pages were successfully processed, falling back to basic extraction")
            return extract_text_from_pdf(pdf_path)
            
    except Exception as e:
        logger.error(f"Page-by-page PDF processing with Gemini failed: {e}")
        return extract_text_from_pdf(pdf_path)

def extract_text_from_pdf(pdf_path: str) -> str:
    """Basic PDF text extraction using PyMuPDF"""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        logger.error(f"PDF text extraction failed: {e}")
        return "Failed to extract text from PDF"

def remove_references_section(text: str) -> str:
    """Remove the references section from the text"""
    # Common patterns for references sections
    patterns = [
        "references",
        "bibliography",
        "works cited",
        "literature cited"
    ]
    
    text_lower = text.lower()
    
    for pattern in patterns:
        # Find the last occurrence of the pattern
        pos = text_lower.rfind(pattern)
        if pos != -1:
            # Check if it's likely a section header
            lines = text[pos:].split('\n')
            if len(lines[0].strip()) < 50:  # Likely a header
                return text[:pos].strip()
    
    return text

def clean_markdown_json(text: str) -> str:
    """Clean markdown code blocks from JSON response"""
    import re
    
    # Remove markdown code blocks (```json ... ```)
    text = re.sub(r'```json\s*\n?(.*?)\n?```', r'\1', text, flags=re.DOTALL)
    
    # Remove generic code blocks (``` ... ```)
    text = re.sub(r'```\s*\n?(.*?)\n?```', r'\1', text, flags=re.DOTALL)
    
    # Remove single backticks
    text = re.sub(r'`([^`]*)`', r'\1', text)
    
    # Clean up extra whitespace
    text = text.strip()
    
    return text

# semantic_anchor: parallel_ocr_saving
def save_ocr_text(original_filename: str, text: str, method: str) -> str:
    """Save OCR processed text to markdown file"""
    try:
        # Create markdown directory if it doesn't exist
        markdown_dir = Path("markdown")
        markdown_dir.mkdir(exist_ok=True)
        
        # Generate filename with timestamp and method
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = Path(original_filename).stem
        ocr_filename = f"{base_name}_{method}_{timestamp}.md"
        ocr_path = markdown_dir / ocr_filename
        
        # Add metadata header
        metadata_header = f"""---
                                original_file: {original_filename}
                                ocr_method: {method}
                                processed_date: {datetime.now().isoformat()}
                                ---

                                # OCR Processed Text: {original_filename}

                                **Method:** {method}
                                **Processed:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

                                ---

                                """
        
        # Save the file
        with open(ocr_path, 'w', encoding='utf-8') as f:
            f.write(metadata_header + text)
        
        logger.info(f"Saved OCR text to: {ocr_filename}")
        return ocr_filename
        
    except Exception as e:
        logger.error(f"Failed to save OCR text: {e}")
        return ""

# semantic_anchor: parallel_json_saving  
def save_extracted_json(original_filename: str, ocr_filename: str, json_data: Dict[Any, Any], provider: str) -> str:
    """Save extracted JSON data with reference to OCR file"""
    try:
        # Create json directory if it doesn't exist
        json_dir = Path("json")
        json_dir.mkdir(exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = Path(original_filename).stem
        json_filename = f"{base_name}_extracted_{provider}_{timestamp}.json"
        json_path = json_dir / json_filename
        
        # Add extraction metadata
        extraction_metadata = {
            "extraction_metadata": {
                "original_pdf": original_filename,
                "ocr_file": ocr_filename,
                "extraction_method": provider,
                "extraction_date": datetime.now().isoformat(),
                "version": "1.0"
            },
            "extracted_data": json_data
        }
        
        # Save the file
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(extraction_metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved extracted JSON to: {json_filename}")
        return json_filename
        
    except Exception as e:
        logger.error(f"Failed to save JSON data: {e}")
        return ""

def get_file_pairs() -> List[Dict[str, Any]]:
    """Get list of OCR-JSON file pairs"""
    try:
        markdown_dir = Path("markdown")
        json_dir = Path("json")
        
        if not markdown_dir.exists() and not json_dir.exists():
            return []
        
        pairs = []
        ocr_files = list(markdown_dir.glob("*.md")) if markdown_dir.exists() else []
        
        for ocr_file in ocr_files:
            # Find corresponding JSON files
            base_pattern = ocr_file.stem.split("_")[0]  # Get base filename
            json_files = list(json_dir.glob(f"{base_pattern}_extracted_*.json")) if json_dir.exists() else []
            
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    
                    pairs.append({
                        "ocr_file": ocr_file.name,
                        "json_file": json_file.name,
                        "original_pdf": json_data.get("extraction_metadata", {}).get("original_pdf", "unknown"),
                        "extraction_date": json_data.get("extraction_metadata", {}).get("extraction_date", ""),
                        "extraction_method": json_data.get("extraction_metadata", {}).get("extraction_method", "")
                    })
                except Exception as e:
                    logger.error(f"Error reading JSON file {json_file}: {e}")
        
        # Sort by extraction date
        pairs.sort(key=lambda x: x["extraction_date"], reverse=True)
        return pairs
        
    except Exception as e:
        logger.error(f"Error getting file pairs: {e}")
        return []

# semantic_anchor: llm_extraction_implementation
@app.post("/extract-data", response_model=ExtractionResponse)
async def extract_data(request: LLMExtractionRequest):
    """Extract structured data using LLM"""
    try:
        logger.info(f"Extracting data using provider: {request.provider}")
        
        # Load extraction prompt
        system_prompt = load_extraction_prompt()
        logger.info(f"Using prompt with {len(system_prompt)} characters for {request.provider}")
        logger.info(f"OCR text length: {len(request.text)} characters")
        logger.info(f"OCR text preview: {request.text[:200]}...")
        
        if request.provider == "openai":
            extracted_data = await extract_with_openai(request.text, system_prompt)
        elif request.provider == "lm-studio":
            extracted_data = await extract_with_lm_studio_llm(request.text, system_prompt)
        elif request.provider == "ollama":
            extracted_data = await extract_with_ollama(request.text, system_prompt)
        elif request.provider == "gemini":
            extracted_data = await extract_with_gemini(request.text, system_prompt)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown LLM provider: {request.provider}")
        
        # semantic_anchor: parallel_json_saving
        # Automatically save extracted JSON
        json_filename = ""
        if request.original_filename and request.ocr_filename:
            json_filename = save_extracted_json(
                request.original_filename,
                request.ocr_filename,
                extracted_data,
                request.provider
            )
        
        return ExtractionResponse(
            extracted_data=extracted_data,
            success=True,
            message=f"Successfully extracted data using {request.provider}",
            json_filename=json_filename,
            ocr_filename=request.ocr_filename
        )
        
    except Exception as e:
        logger.error(f"Error extracting data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def extract_with_openai(text: str, system_prompt: str) -> Dict[Any, Any]:
    """Extract data using OpenAI API"""
    if not config.OPENAI_API_KEY:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured")
    
    try:
        openai.api_key = config.OPENAI_API_KEY
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract experimental data from this text:\n\n{text}"}
            ],
            max_tokens=4000,
            temperature=0.1
        )
        
        result_text = response.choices[0].message.content
        
        # Try to parse as JSON
        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            # If not valid JSON, wrap in a structure
            return {"extracted_text": result_text, "parsing_error": "Could not parse as JSON"}
            
    except Exception as e:
        logger.error(f"OpenAI extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(e)}")

async def extract_with_lm_studio_llm(text: str, system_prompt: str) -> Dict[Any, Any]:
    """Extract data using LM Studio"""
    try:
        # LM Studio uses chat completion format similar to OpenAI
        response = requests.post(
            f"{config.LM_STUDIO_URL}/v1/chat/completions",
            json={
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract experimental data from this text:\n\n{text}"}
                ],
                "max_tokens": 35000,
                "temperature": 0.3
            },
            timeout=1000
        )
        
        if response.status_code == 200:
            result = response.json()
            result_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Try to parse as JSON
            try:
                return json.loads(result_text)
            except json.JSONDecodeError:
                return {"extracted_text": result_text, "parsing_error": "Could not parse as JSON"}
        else:
            raise HTTPException(status_code=500, detail=f"LM Studio API error: {response.status_code}")
            
    except Exception as e:
        logger.error(f"LM Studio extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def extract_with_ollama(text: str, system_prompt: str) -> Dict[Any, Any]:
    """Extract data using Ollama"""
    try:
        # Ollama uses chat completion format
        response = requests.post(
            f"{config.OLLAMA_URL}/api/chat",
            json={
                "model": "llama2",  # Default model, should be configurable
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract experimental data from this text:\n\n{text}"}
                ],
                "stream": False
            },
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            result_text = result.get("message", {}).get("content", "")
            
            # Try to parse as JSON
            try:
                return json.loads(result_text)
            except json.JSONDecodeError:
                return {"extracted_text": result_text, "parsing_error": "Could not parse as JSON"}
        else:
            raise HTTPException(status_code=500, detail=f"Ollama API error: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Ollama extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def extract_with_gemini(text: str, system_prompt: str) -> Dict[Any, Any]:
    """Extract data using Google Gemini API"""
    if not config.GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="Gemini API key not configured")
    
    try:
        import google.generativeai as genai
        
        # Configure the Gemini API
        genai.configure(api_key=config.GEMINI_API_KEY)
        
        # Use Gemini 2.5 Pro model
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        # Combine system prompt and user text
        full_prompt = f"{system_prompt}\n\nExtract experimental data from this text:\n\n{text}"
        
        # Generate content
        response = model.generate_content(full_prompt)
        
        if response.text:
            result_text = response.text
            
            # Try to parse as JSON
            try:
                return json.loads(result_text)
            #except result_text
            except json.JSONDecodeError:
                # If not valid JSON, wrap in a structure
                return {"extracted_text": result_text, "parsing_error": "Could not parse as JSON"}
        else:
            raise HTTPException(status_code=500, detail="Gemini API returned empty response")
            
    except Exception as e:
        logger.error(f"Gemini extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")

# semantic_anchor: database_operations
class DatabaseSaveRequest(BaseModel):
    data: Dict[Any, Any]
    source_text: Optional[str] = None
    validate_with_llm: bool = False
    num_validation_samples: Optional[int] = 3

@app.post("/add-to-database")
async def add_to_database(request: DatabaseSaveRequest):
    """Add extracted data to MongoDB with optional LLM validation"""
    try:
        if collection is None:
            raise HTTPException(status_code=503, detail="Database not available")
        
        # Initialize validation results
        validation_results = None
        llm_accuracy = None
        
        # Perform LLM validation if requested and source text is provided
        if request.validate_with_llm and request.source_text:
            try:
                logger.info("Performing LLM validation before saving to database")
                validator = JSONValidator(config.LM_STUDIO_URL + "/v1/chat/completions")
                validation_result = validator.validate_json_data(
                    request.data, 
                    request.source_text, 
                    request.num_validation_samples
                )
                
                if validation_result["success"]:
                    validation_results = validation_result["validation_results"]
                    llm_accuracy = validation_result["accuracy"]
                    logger.info(f"LLM validation completed with {llm_accuracy:.2f}% accuracy")
                else:
                    logger.warning(f"LLM validation failed: {validation_result['message']}")
                    
            except Exception as e:
                logger.error(f"Error during LLM validation: {e}")
                # Continue with saving even if validation fails
        
        # Add metadata
        document = {
            **request.data,
            "created_at": datetime.utcnow(),
            "version": "1.0"
        }
        
        # Add validation metadata if available
        if validation_results is not None:
            document["llm_validation"] = {
                "accuracy": llm_accuracy,
                "validation_results": validation_results,
                "total_validated": len(validation_results),
                "correct_count": sum(1 for r in validation_results if r["verdict"].get("is_correct", False)),
                "validation_timestamp": datetime.utcnow().isoformat()
            }
        
        result = collection.insert_one(document)
        logger.info(f"Inserted document with ID: {result.inserted_id}")
        
        return {
            "success": True,
            "message": "Document added successfully",
            "document_id": str(result.inserted_id),
            "llm_validation": {
                "performed": validation_results is not None,
                "accuracy": llm_accuracy,
                "total_validated": len(validation_results) if validation_results else 0
            } if validation_results else None
        }
        
    except Exception as e:
        logger.error(f"Error adding to database: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-query")
async def generate_query(request: QueryGenerationRequest):
    """Generate MongoDB query from natural language"""
    try:
        logger.info(f"Generating query for: '{request.natural_language}' using provider: {request.provider}")
        
        if request.provider == "simple":
            query = generate_simple_query(request.natural_language)
            method = "simple"
        elif request.provider == "openai":
            if not config.OPENAI_API_KEY or not config.OPENAI_API_KEY.strip():
                logger.warning("OpenAI API key not configured, falling back to simple query")
                query = generate_simple_query(request.natural_language)
                method = "simple (fallback)"
            else:
                try:
                    query = await generate_query_with_openai(request.natural_language)
                    method = "openai"
                except Exception as e:
                    logger.warning(f"OpenAI query generation failed: {e}, falling back to simple query")
                    query = generate_simple_query(request.natural_language)
                    method = "simple (fallback)"
        elif request.provider == "lm-studio":
            try:
                query = await generate_query_with_lm_studio(request.natural_language)
                method = "lm-studio"
            except Exception as e:
                logger.warning(f"LM Studio query generation failed: {e}, falling back to simple query")
                query = generate_simple_query(request.natural_language)
                method = "simple (fallback)"
        elif request.provider == "gemini":
            if not config.GEMINI_API_KEY or not config.GEMINI_API_KEY.strip():
                logger.warning("Gemini API key not configured, falling back to simple query")
                query = generate_simple_query(request.natural_language)
                method = "simple (fallback)"
            else:
                try:
                    query = await generate_query_with_gemini(request.natural_language)
                    method = "gemini"
                except Exception as e:
                    logger.warning(f"Gemini query generation failed: {e}, falling back to simple query")
                    query = generate_simple_query(request.natural_language)
                    method = "simple (fallback)"
        elif request.provider == "ollama":
            try:
                query = await generate_query_with_ollama(request.natural_language)
                method = "ollama"
            except Exception as e:
                logger.warning(f"Ollama query generation failed: {e}, falling back to simple query")
                query = generate_simple_query(request.natural_language)
                method = "simple (fallback)"
        else:
            logger.warning(f"Unknown provider: {request.provider}, using simple query")
            query = generate_simple_query(request.natural_language)
            method = "simple (fallback)"
        
        logger.info(f"Generated query: {query}")
        
        return {
            "generated_query": query,
            "success": True,
            "message": "Query generated successfully",
            "method": method,
            "provider": request.provider
        }
        
    except Exception as e:
        logger.error(f"Error generating query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def generate_simple_query(natural_language: str) -> str:
    """Generate a simple MongoDB query based on keywords"""
    text = natural_language.lower()
    
    # Heavy metals mapping
    metals = {
        "cadmium": "Cd", "lead": "Pb", "zinc": "Zn", "copper": "Cu",
        "nickel": "Ni", "chromium": "Cr", "arsenic": "As", "mercury": "Hg"
    }
    
    query_parts = []
    
    # Check for metal mentions
    for metal_name, symbol in metals.items():
        if metal_name in text or symbol.lower() in text:
            query_parts.append(f'"heavy_metals": "{symbol}"')
    
    # Check for plant species
    if "plant" in text or "species" in text:
        query_parts.append('"plant_species": {"$exists": true}')
    
    # Check for concentration
    if "concentration" in text:
        query_parts.append('"concentrations": {"$exists": true}')
    
    if query_parts:
        return "{" + ", ".join(query_parts) + "}"
    else:
        return "{}"

async def generate_query_with_openai(natural_language: str) -> str:
    """Generate MongoDB query using OpenAI API"""
    try:
        openai.api_key = config.OPENAI_API_KEY
        
        # Load prompt from file
        system_prompt = load_query_prompt()
        logger.info(f"Using query prompt with {len(system_prompt)} characters")
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Convert to MongoDB query: {natural_language}"}
            ],
            max_tokens=500,
            temperature=0.1
        )
        
        query = response.choices[0].message.content.strip()
        
        # Clean markdown code blocks if present
        query = clean_markdown_json(query)
        
        # Validate JSON
        try:
            json.loads(query)
            return query
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from OpenAI: {query}")
            return "{}"
            
    except Exception as e:
        logger.error(f"OpenAI query generation failed: {e}")
        return "{}"

async def generate_query_with_lm_studio(natural_language: str) -> str:
    """Generate MongoDB query using LM Studio"""
    try:
        # Load prompt from file
        system_prompt = load_query_prompt()
        logger.info(f"Using query prompt with {len(system_prompt)} characters for LM Studio")
        
        response = requests.post(
            f"{config.LM_STUDIO_URL}/v1/chat/completions",
            json={
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Convert to MongoDB query: {natural_language}"}
                ],
                "max_tokens": 500,
                "temperature": 0.1
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            query = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            # Clean markdown code blocks if present
            query = clean_markdown_json(query)
            
            # Validate JSON
            try:
                json.loads(query)
                return query
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from LM Studio: {query}")
                # Attempt to extract from a common string format if JSON fails
                if 'db.collection.find' in query:
                    try:
                        # Extract the JSON part of the find command
                        start = query.find('{')
                        end = query.rfind('}') + 1
                        if 0 <= start < end:
                            json_part = query[start:end]
                            json.loads(json_part)  # Validate extracted JSON
                            logger.info(f"Successfully extracted JSON from string: {json_part}")
                            return json_part
                    except json.JSONDecodeError:
                        logger.warning(f"Could not extract valid JSON from LM Studio string: {query}")

                return "{}"
        else:
            raise Exception(f"LM Studio API error: {response.status_code}")
            
    except Exception as e:
        logger.error(f"LM Studio query generation failed: {e}")
        return "{}"

async def generate_query_with_ollama(natural_language: str) -> str:
    """Generate MongoDB query using Ollama"""
    try:
        # Load prompt from file
        system_prompt = load_query_prompt()
        logger.info(f"Using query prompt with {len(system_prompt)} characters for Ollama")
        
        response = requests.post(
            f"{config.OLLAMA_URL}/api/chat",
            json={
                "model": "llama2",  # Default model, should be configurable
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Convert to MongoDB query: {natural_language}"}
                ],
                "stream": False
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            query = result.get("message", {}).get("content", "").strip()
            
            # Clean markdown code blocks if present
            query = clean_markdown_json(query)
            
            # Validate JSON
            try:
                json.loads(query)
                return query
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from Ollama: {query}")
                return "{}"
        else:
            raise Exception(f"Ollama API error: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Ollama query generation failed: {e}")
        return "{}"

async def generate_query_with_gemini(natural_language: str) -> str:
    """Generate MongoDB query using Google Gemini API"""
    try:
        import google.generativeai as genai
        
        # Configure the Gemini API
        genai.configure(api_key=config.GEMINI_API_KEY)
        
        # Use Gemini 2.5 Pro model
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Load prompt from file
        system_prompt = load_query_prompt()
        logger.info(f"Using query prompt with {len(system_prompt)} characters for Gemini")
        
        # Combine system prompt and user request
        full_prompt = f"{system_prompt}\n\nConvert to MongoDB query: {natural_language}"
        
        # Generate content
        response = model.generate_content(full_prompt)
        
        if response.text:
            query = response.text.strip()
            
            # Clean markdown code blocks if present
            query = clean_markdown_json(query)
            
            # Validate JSON
            try:
                json.loads(query)
                return query
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from Gemini: {query}")
                return "{}"
        else:
            raise Exception("Gemini API returned empty response")
            
    except Exception as e:
        logger.error(f"Gemini query generation failed: {e}")
        return "{}"

@app.post("/execute-query")
async def execute_query(request: DatabaseQueryRequest):
    """Execute MongoDB query"""
    try:
        if collection is None:
            raise HTTPException(status_code=503, detail="Database not available")
        
        # Parse the query
        try:
            query_dict = json.loads(request.query) if request.query.strip() else {}
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON query")
        
        # Execute query
        cursor = collection.find(query_dict).limit(100)  # Limit results
        results = list(cursor)
        
        # Convert ObjectId to string for JSON serialization
        for result in results:
            if "_id" in result:
                result["_id"] = str(result["_id"])
        
        return {
            "results": results,
            "count": len(results),
            "query": query_dict,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Validation endpoints
class ValidationRequest(BaseModel):
    json_data: Dict[Any, Any]
    source_text: str
    num_samples: Optional[int] = 3

class ValidationResponse(BaseModel):
    success: bool
    message: str
    validation_results: List[Dict[str, Any]]
    accuracy: float
    total_validated: int
    correct_count: int
    sample_size: int

@app.post("/validate-json", response_model=ValidationResponse)
async def validate_json_data(request: ValidationRequest):
    """Validate JSON data against source text using LLM as judge"""
    try:
        logger.info(f"Starting JSON validation with {request.num_samples} samples")
        
        # Initialize validator
        validator = JSONValidator(config.LM_STUDIO_URL + "/v1/chat/completions")
        
        # Perform validation
        result = validator.validate_json_data(
            request.json_data, 
            request.source_text, 
            request.num_samples
        )
        
        logger.info(f"Validation completed with {result.get('accuracy', 0):.2f}% accuracy")
        
        return ValidationResponse(**result)
        
    except Exception as e:
        logger.error(f"Error during validation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/validate-json-file")
async def validate_json_file(json_filename: str, markdown_filename: str, num_samples: Optional[int] = 3):
    """Validate JSON file against markdown file"""
    try:
        logger.info(f"Validating JSON file: {json_filename} against markdown: {markdown_filename}")
        
        # Construct file paths
        json_path = os.path.join("json", json_filename)
        markdown_path = os.path.join("markdown", markdown_filename)
        
        # Check if files exist
        if not os.path.exists(json_path):
            raise HTTPException(status_code=404, detail=f"JSON file not found: {json_filename}")
        if not os.path.exists(markdown_path):
            raise HTTPException(status_code=404, detail=f"Markdown file not found: {markdown_filename}")
        
        # Initialize validator
        validator = JSONValidator(config.LM_STUDIO_URL + "/v1/chat/completions")
        
        # Perform validation
        result = validator.validate_json_file(json_path, markdown_path, num_samples)
        
        logger.info(f"File validation completed with {result.get('accuracy', 0):.2f}% accuracy")
        
        return result
        
    except Exception as e:
        logger.error(f"Error during file validation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    from datetime import datetime
    
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
