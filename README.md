# Phytoextraction Research Data Extractor

A web application for automating the extraction of experimental results from scientific articles about phytoextraction and hyperaccumulation of heavy metals from soils.

## Features

### 🔍 OCR Processing
- **Multiple OCR Methods**: Support for Nougat OCR, LM Studio, and Gemini API direct OCR
- **Direct PDF Processing**: Gemini API can process PDF files directly without PyMuPDF preprocessing
- **PDF & DOI Support**: Process local PDF files or fetch articles by DOI
- **Reference Removal**: Automatically removes reference sections from processed text
- **Batch Processing**: Handle multiple files simultaneously

### 🧠 LLM Extraction
- **Structured Data Extraction**: Convert research text to structured JSON format
- **Multiple LLM Providers**: OpenAI API, Google Gemini 2.5 Pro, LM Studio (local), Ollama (local)
- **Custom Prompts**: Configurable extraction prompts via `prompt.md`
- **JSON Validation**: Automatic validation and formatting of extracted data

### 🗃️ Database Management
- **MongoDB Integration**: Store and query extracted research data
- **Natural Language Queries**: Generate database queries from plain English
- **Advanced Search**: Query by plant species, heavy metals, experimental conditions
- **Export Capabilities**: Copy and export results in JSON format

## Installation

### Prerequisites
- Python 3.8+
- MongoDB (local or cloud instance)
- Node.js (for optional frontend development)

### Optional Dependencies
- **Nougat OCR**: For advanced PDF processing
- **LM Studio**: For local LLM processing
- **Ollama**: Alternative local LLM option
- **Google Gemini API**: For cloud-based LLM processing

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd phytoextraction-extractor
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Nougat OCR (optional)**
   ```bash
   pip install nougat-ocr
   ```

4. **Configure environment variables**
   ```bash
   cp config.env.example .env
   # Edit .env with your configuration
   ```

5. **Start MongoDB**
   - Local: `mongod`
   - Or use MongoDB Atlas (cloud)

6. **Run the application**
   ```bash
   python start.py
   ```

7. **Access the application**
   Open your browser to `http://localhost:8000`

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# MongoDB Configuration
MONGODB_URL=mongodb://localhost:27/
DATABASE_NAME=phytoextraction_db
COLLECTION_NAME=research_articles

# API Keys
OPENAI_API_KEY="your_openai_api_key_here"
GEMINI_API_KEY="your_gemini_api_key_here"

# Local Model URLs
LM_STUDIO_URL=http://localhost:1234
OLLAMA_URL=http://localhost:11434
```

### LM Studio Setup (Optional)

1. Download and install [LM Studio](https://lmstudio.ai/)
2. Load a compatible model (e.g., CodeLlama, Mistral)
3. Start the local server (default: `localhost:1234`)
4. Update `LM_STUDIO_URL` in your configuration

### Ollama Setup (Optional)

1. Install [Ollama](https://ollama.ai/)
2. Pull a model: `ollama pull llama2`
3. Start the service: `ollama serve`
4. Update `OLLAMA_URL` in your configuration

## Usage

### 1. OCR Processing

#### Upload PDF Files
1. Select one or more PDF files using the file upload interface
2. Choose your preferred OCR method:
   - **Nougat OCR**: Advanced academic document processing (requires installation)
   - **LM Studio**: Local model-based text improvement
   - **API Call**: Direct Gemini API OCR processing 
3. Click "Start OCR Processing"
4. Review the processed text and save as Markdown if needed

#### Process by DOI
1. Enter the DOI of the article in the DOI field
2. Select your OCR method
3. Click "Start OCR Processing"

### 2. LLM Extraction

1. The processed text from OCR will automatically populate the LLM input
   - Or upload existing Markdown files directly
2. Choose your LLM provider:
   - **OpenAI API**: Cloud-based processing (requires API key)
   - **LM Studio**: Local model processing
   - **Ollama**: Alternative local processing
3. Click "Start LLM Processing"
4. Review the extracted JSON data
5. Copy the JSON or add it to the database

### 3. Database Queries

#### Manual Queries
Write MongoDB queries directly:
```json
{"heavy_metals": "Cd", "plant_species": {"$regex": "Brassica"}}
```

#### Natural Language Queries
1. Enter a description like: "Find studies about cadmium accumulation in Brassica species"
2. Click "Generate Query" to convert to MongoDB syntax
3. Click "Send Query" to execute

## API Documentation

The application provides a REST API for programmatic access:


## Data Schema

The application extracts data according to a comprehensive schema designed for phytoextraction research:

### Core Fields
- **article_metadata**: Title, authors, journal, year, DOI
- **plant_species**: Scientific name, family, hyperaccumulator status
- **heavy_metals**: List of metals studied (Cd, Pb, Zn, Cu, Ni, Cr, As, Hg)
- **experimental_conditions**: Soil type, pH, temperature, duration
- **concentrations**: Soil and plant tissue metal concentrations
- **factors**: Bioaccumulation and translocation factors
- **growth_parameters**: Biomass, height, survival data
- **removal_efficiency**: Uptake and removal percentages

See `prompt.md` for the complete extraction prompt and schema details.

## Troubleshooting

### Common Issues

1. **Nougat OCR not terminating**
   - The application handles this known bug with automatic timeout and process termination
   - Falls back to basic PDF extraction if Nougat fails

2. **MongoDB connection issues**
   - Check that MongoDB is running
   - Verify connection string in environment variables
   - Check firewall settings

3. **API key errors**
   - Ensure API keys are correctly set in `.env` file
   - Check API key permissions and quotas

4. **LM Studio connection failed**
   - Verify LM Studio is running and accessible
   - Check the model is loaded and server is started
   - Confirm the URL in configuration

### Performance Notes

- **Large PDF files**: Consider using Nougat OCR for best results with academic papers
- **Batch processing**: Process multiple files individually for better error handling
- **Database queries**: Use indexes on frequently queried fields (heavy_metals, plant_species)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Nougat OCR for academic document processing
- MongoDB for flexible document storage
- FastAPI for the web framework
- OpenAI, LM Studio, and Ollama for LLM capabilities

## Support

For issues and questions:
1. Check the troubleshooting section
2. Search existing issues
3. Create a new issue with detailed information

---

**Note**: This application is designed for research purposes. Ensure compliance with journal access policies and API terms of service when processing copyrighted content.
