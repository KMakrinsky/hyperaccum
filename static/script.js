    /* semantic_anchor: application_state_management */
class PhytoextractionApp {
    constructor() {
        this.currentFiles = [];
        this.currentMarkdownFiles = [];
        this.processedText = '';
        this.extractedJSON = null;
        this.apiBaseURL = 'http://localhost:8000';
        this.currentOCRFiles = []; // Track OCR files for pairing with JSON
        
        this.initializeEventListeners();
        this.checkDatabaseConnection();
        this.loadSavedFiles();
        
        // Initialize button states
        this.validateOCRInputs();
        this.validateLLMInputs();
        this.validateQuery();
    }

    /* semantic_anchor: event_listeners_initialization */
    initializeEventListeners() {

        
        // OCR Block Event Listeners
        document.getElementById('pdf-files').addEventListener('change', this.handleFileUpload.bind(this));
        document.getElementById('start-ocr').addEventListener('click', this.startOCRProcessing.bind(this));
        document.getElementById('save-markdown').addEventListener('click', this.saveMarkdown.bind(this));
        document.getElementById('proceed-to-llm').addEventListener('click', this.proceedToLLM.bind(this));

        // LLM Block Event Listeners
        document.getElementById('md-files').addEventListener('change', this.handleMarkdownUpload.bind(this));
        document.getElementById('start-llm').addEventListener('click', this.startLLMProcessing.bind(this));
        document.getElementById('copy-json').addEventListener('click', this.copyJSON.bind(this));
        document.getElementById('validate-json').addEventListener('click', this.startValidation.bind(this));
        document.getElementById('add-to-db').addEventListener('click', this.addToDatabase.bind(this));

        // Validation Block Event Listeners
        document.getElementById('start-validation').addEventListener('click', this.startValidation.bind(this));
        document.getElementById('save-with-validation').addEventListener('click', this.saveWithValidation.bind(this));

        // Database Block Event Listeners
        document.getElementById('generate-query').addEventListener('click', this.generateQuery.bind(this));
        document.getElementById('send-query').addEventListener('click', this.sendQuery.bind(this));
        document.getElementById('db-query').addEventListener('input', this.validateQuery.bind(this));

        // File Management Event Listeners
        document.getElementById('refresh-files').addEventListener('click', this.loadSavedFiles.bind(this));
        document.getElementById('clear-files').addEventListener('click', this.clearAllFiles.bind(this));

        // DOI input listener
        document.getElementById('doi-input').addEventListener('input', this.validateOCRInputs.bind(this));
    }

    /* semantic_anchor: file_upload_handling */
    handleFileUpload(event) {
        console.log('🔍 handleFileUpload called');
        console.log('🔍 event.target.files:', event.target.files);
        
        const files = Array.from(event.target.files);
        console.log('🔍 files array:', files);
        
        this.currentFiles = files;
        console.log('🔍 this.currentFiles set to:', this.currentFiles);
        
        this.displayFileList(files);
        this.validateOCRInputs();
    }

    async handleMarkdownUpload(event) {
        console.log('🔍 handleMarkdownUpload called!');
        console.log('🔍 Event:', event);
        console.log('🔍 Files:', event.target.files);
        
        const files = Array.from(event.target.files);
        console.log('🔍 Files array:', files);
        
        this.currentMarkdownFiles = files;
        console.log('🔍 Current markdown files set to:', this.currentMarkdownFiles);
        
        await this.displayMarkdownFiles(files);
        this.validateLLMInputs();
    }

    displayFileList(files) {
        const fileList = document.getElementById('file-list');
        fileList.innerHTML = '';
        
        files.forEach(file => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            fileItem.innerHTML = `
                <span class="file-name">${file.name}</span>
                <span class="file-size">${this.formatFileSize(file.size)}</span>
            `;
            fileList.appendChild(fileItem);
        });
    }

    async displayMarkdownFiles(files) {
        const textArea = document.getElementById('llm-input-text');
        
        console.log('🔍 displayMarkdownFiles called with files:', files);
        
        if (files.length > 0) {
            try {
                const fileContents = [];
                
                for (const file of files) {
                    console.log('🔍 Reading file:', file.name, 'size:', file.size);
                    const content = await this.readFileContent(file);
                    console.log('🔍 File content length:', content.length);
                    console.log('🔍 File content preview:', content.substring(0, 200));
                    fileContents.push(`=== ${file.name} ===\n${content}\n=== END ${file.name} ===\n`);
                }
                
                const finalText = fileContents.join('\n');
                console.log('🔍 Final text length:', finalText.length);
                textArea.value = finalText;
                
                // CRITICAL FIX: Set processedText for validation to work
                this.processedText = finalText;
                console.log('🔍 processedText set for validation:', this.processedText.length, 'characters');
                
                console.log('🔍 TextArea value set successfully');
            } catch (error) {
                console.error('Error reading markdown files:', error);
                const fileNames = files.map(f => f.name).join(', ');
                const errorText = `Error reading files: ${fileNames}\n\nError: ${error.message}`;
                textArea.value = errorText;
                
                // Set processedText even for error case
                this.processedText = errorText;
            }
        }
    }

    readFileContent(file) {
        return new Promise((resolve, reject) => {
            console.log('🔍 readFileContent called for file:', file.name);
            const reader = new FileReader();
            
            reader.onload = (event) => {
                console.log('🔍 FileReader onload triggered for:', file.name);
                console.log('🔍 Result type:', typeof event.target.result);
                console.log('🔍 Result length:', event.target.result.length);
                resolve(event.target.result);
            };
            
            reader.onerror = (error) => {
                console.error('🔍 FileReader error for file:', file.name, error);
                reject(error);
            };
            
            console.log('🔍 Starting to read file:', file.name);
            reader.readAsText(file);
        });
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /* semantic_anchor: input_validation */
    validateOCRInputs() {
        const hasFiles = this.currentFiles.length > 0;
        const hasDOI = document.getElementById('doi-input').value.trim() !== '';
        const startButton = document.getElementById('start-ocr');
        
        // Debug logging
        console.log('🔍 validateOCRInputs called');
        console.log('🔍 currentFiles:', this.currentFiles);
        console.log('🔍 hasFiles:', hasFiles);
        console.log('🔍 hasDOI:', hasDOI);
        console.log('🔍 startButton:', startButton);
        
        const shouldEnable = hasFiles || hasDOI;
        startButton.disabled = !shouldEnable;
        
        console.log('🔍 Button should be enabled:', shouldEnable);
        console.log('🔍 Button disabled state:', startButton.disabled);
    }

    validateLLMInputs() {
        const hasText = this.processedText !== '' || this.currentMarkdownFiles.length > 0;
        const startButton = document.getElementById('start-llm');
        
        startButton.disabled = !hasText;
    }

    validateQuery() {
        const queryText = document.getElementById('db-query').value.trim();
        const sendButton = document.getElementById('send-query');
        
        sendButton.disabled = queryText === '';
    }

    /* semantic_anchor: ocr_processing_implementation */
    async startOCRProcessing() {
        const selectedMethod = document.querySelector('input[name="ocr-method"]:checked').value;
        const doiInput = document.getElementById('doi-input').value.trim();
        
        console.log('🔍 Selected OCR method:', selectedMethod);
        console.log('🔍 Selected method type:', typeof selectedMethod);
        
        this.showProgress('ocr-progress', 'Processing with ' + selectedMethod + '...');
        this.updateStatus('Processing documents...');

        try {
            let result;
            
            if (doiInput) {
                result = await this.processDOI(doiInput, selectedMethod);
            } else {
                result = await this.processFiles(this.currentFiles, selectedMethod);
            }

            this.displayOCRResults(result);
            this.updateStatus('OCR processing completed');
            
        } catch (error) {
            console.error('OCR processing failed:', error);
            this.updateStatus('OCR processing failed: ' + error.message);
            alert('OCR processing failed: ' + error.message);
        } finally {
            this.hideProgress('ocr-progress');
        }
    }

    async processDOI(doi, method) {
        const response = await fetch(`${this.apiBaseURL}/process-doi`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                doi: doi,
                method: method
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    async processFiles(files, method) {
        console.log('🔍 processFiles called with method:', method);
        console.log('🔍 method type:', typeof method);
        
        const formData = new FormData();
        files.forEach(file => {
            formData.append('files', file);
        });
        formData.append('method', method);

        console.log('🔍 FormData method value:', formData.get('method'));
        
        const response = await fetch(`${this.apiBaseURL}/process-files`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    /* semantic_anchor: nougat_ocr_execution */
    // This would be handled by the backend, but here's the conceptual implementation
    async executeNougatOCR(file) {
        // Backend would execute: nougat --no-skipping -m 0.1.0-base <file>
        // With timeout handling for the completion bug
        return "Nougat OCR result would be here...";
    }

    displayOCRResults(result) {
        this.processedText = result.processed_text;
        this.currentOCRFiles = result.saved_files || [];
        
        document.getElementById('ocr-text').value = this.processedText;
        document.getElementById('ocr-results').style.display = 'block';
        
        // Auto-populate LLM input
        document.getElementById('llm-input-text').value = this.processedText;
        this.validateLLMInputs();
        
        // Refresh file list to show new OCR files
        this.loadSavedFiles();
        
        // Show message about saved files
        if (this.currentOCRFiles.length > 0) {
            const fileNames = this.currentOCRFiles.map(f => f.ocr_file).join(', ');
            this.updateStatus(`OCR completed. Saved files: ${fileNames}`);
        }
    }

    /* semantic_anchor: markdown_file_operations */
    async saveMarkdown() {
        if (!this.processedText) return;
        
        const blob = new Blob([this.processedText], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'processed_article.md';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        this.updateStatus('Markdown file downloaded');
    }

    proceedToLLM() {
        document.getElementById('llm-input-text').value = this.processedText;
        this.validateLLMInputs();
        document.getElementById('llm-block').scrollIntoView({ behavior: 'smooth' });
    }

    /* semantic_anchor: llm_extraction_implementation */
    async startLLMProcessing() {
        const selectedProvider = document.querySelector('input[name="llm-provider"]:checked').value;
        const inputText = document.getElementById('llm-input-text').value;
        
        console.log('🔍 startLLMProcessing called');
        console.log('🔍 Selected provider:', selectedProvider);
        console.log('🔍 Input text length:', inputText.length);
        console.log('🔍 Input text preview:', inputText.substring(0, 200));
        console.log('🔍 Current markdown files:', this.currentMarkdownFiles);
        
        this.showProgress('llm-progress', 'Extracting data with ' + selectedProvider + '...');
        this.updateStatus('Processing with LLM...');

        try {
            const result = await this.extractWithLLM(inputText, selectedProvider);
            this.displayLLMResults(result);
            this.updateStatus('LLM extraction completed');
            
        } catch (error) {
            console.error('LLM processing failed:', error);
            this.updateStatus('LLM processing failed: ' + error.message);
            alert('LLM processing failed: ' + error.message);
        } finally {
            this.hideProgress('llm-progress');
        }
    }

    async extractWithLLM(text, provider) {
        console.log('🔍 extractWithLLM called');
        console.log('🔍 Text to send:', text.substring(0, 200));
        console.log('🔍 Provider:', provider);
        
        // Get file information for parallel saving
        let originalFilename = null;
        let ocrFilename = null;
        
        if (this.currentOCRFiles.length > 0) {
            // Use the first OCR file for simplicity, or could be enhanced for multiple files
            const firstOCRFile = this.currentOCRFiles[0];
            originalFilename = firstOCRFile.original_file;
            ocrFilename = firstOCRFile.ocr_file;
        }
        
        const requestBody = {
            text: text,
            provider: provider,
            original_filename: originalFilename,
            ocr_filename: ocrFilename
        };
        
        console.log('🔍 Request body:', requestBody);
        
        const response = await fetch(`${this.apiBaseURL}/extract-data`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    /* semantic_anchor: json_results_display */
    displayLLMResults(result) {
        this.extractedJSON = result.extracted_data;
        
        const jsonOutput = document.getElementById('json-output');
        jsonOutput.textContent = JSON.stringify(this.extractedJSON, null, 2);
        
        document.getElementById('llm-results').style.display = 'block';
        
        // Show validation block if source text is available
        if (this.processedText || this.currentMarkdownFiles.length > 0) {
            document.getElementById('validation-block').style.display = 'block';
        }
        
        // Refresh file list to show new JSON file
        this.loadSavedFiles();
        
        // Show message about saved JSON file
        if (result.json_filename) {
            this.updateStatus(`LLM extraction completed. JSON saved as: ${result.json_filename}`);
        }
    }

    copyJSON() {
        if (!this.extractedJSON) return;
        
        const jsonText = JSON.stringify(this.extractedJSON, null, 2);
        navigator.clipboard.writeText(jsonText).then(() => {
            this.updateStatus('JSON copied to clipboard');
            
            // Visual feedback
            const button = document.getElementById('copy-json');
            const originalText = button.textContent;
            button.textContent = 'Copied!';
            setTimeout(() => {
                button.textContent = originalText;
            }, 2000);
        });
    }

    /* semantic_anchor: database_operations */
    async addToDatabase() {
        if (!this.extractedJSON) return;
        
        // Check if validation is enabled
        const validateOnSave = document.getElementById('validate-on-save')?.checked || false;
        
        if (validateOnSave && !this.processedText) {
            alert('Validation is enabled but no source text is available. Please ensure OCR text is loaded or markdown files are uploaded before saving.');
            return;
        }
        
        this.updateStatus('Adding to database...');

        try {
            const requestBody = {
                data: this.extractedJSON,
                source_text: this.processedText,
                validate_with_llm: validateOnSave,
                num_validation_samples: parseInt(document.getElementById('validation-samples')?.value || '3')
            };

            const response = await fetch(`${this.apiBaseURL}/add-to-database`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            
            if (result.success) {
                this.updateStatus('Successfully added to database');
                let message = 'Article data successfully added to database!';
                
                if (result.llm_validation && result.llm_validation.performed) {
                    message += `\n\nLLM Validation Results:\nAccuracy: ${result.llm_validation.accuracy?.toFixed(1)}%\nValidated: ${result.llm_validation.total_validated} items`;
                }
                
                alert(message);
            } else {
                throw new Error(result.message || 'Save failed');
            }
            
        } catch (error) {
            console.error('Database operation failed:', error);
            this.updateStatus('Failed to add to database: ' + error.message);
            alert('Failed to add to database: ' + error.message);
        }
    }

    async generateQuery() {
        const naturalLanguageQuery = document.getElementById('db-query').value.trim();
        const provider = document.getElementById('query-provider').value;
        
        if (!naturalLanguageQuery) {
            alert('Please enter a natural language query description');
            return;
        }

        this.updateStatus(`Generating database query using ${provider}...`);

        try {
            const response = await fetch(`${this.apiBaseURL}/generate-query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    natural_language: naturalLanguageQuery,
                    provider: provider
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            document.getElementById('db-query').value = result.generated_query;
            this.validateQuery();
            this.updateStatus(`Query generated successfully using ${result.method}`);
            
        } catch (error) {
            console.error('Query generation failed:', error);
            this.updateStatus('Query generation failed: ' + error.message);
            alert('Query generation failed: ' + error.message);
        }
    }

    async sendQuery() {
        const query = document.getElementById('db-query').value.trim();
        
        this.updateStatus('Executing database query...');

        try {
            const response = await fetch(`${this.apiBaseURL}/execute-query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: query
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            this.displayQueryResults(result);
            this.updateStatus(`Query executed successfully - ${result.results.length} results found`);
            
        } catch (error) {
            console.error('Query execution failed:', error);
            this.updateStatus('Query execution failed: ' + error.message);
            alert('Query execution failed: ' + error.message);
        }
    }

    displayQueryResults(result) {
        const queryOutput = document.getElementById('query-output');
        queryOutput.textContent = JSON.stringify(result.results, null, 2);
        
        document.getElementById('result-count').textContent = result.results.length;
        document.getElementById('query-results').style.display = 'block';
    }

    /* semantic_anchor: database_connection_management */
    async checkDatabaseConnection() {
        const statusIndicator = document.getElementById('db-status');
        statusIndicator.className = 'status-indicator connecting';

        try {
            const response = await fetch(`${this.apiBaseURL}/health`);
            
            if (response.ok) {
                statusIndicator.className = 'status-indicator connected';
                this.updateStatus('Connected to database');
            } else {
                throw new Error('Database connection failed');
            }
        } catch (error) {
            statusIndicator.className = 'status-indicator';
            this.updateStatus('Database connection failed');
        }
    }

    /* semantic_anchor: ui_helper_functions */
    showProgress(progressId, message) {
        const progressSection = document.getElementById(progressId);
        const progressText = progressSection.querySelector('.progress-text');
        
        progressText.textContent = message;
        progressSection.style.display = 'block';
    }

    hideProgress(progressId) {
        document.getElementById(progressId).style.display = 'none';
    }

    updateStatus(message) {
        document.getElementById('status-text').textContent = message;
    }
    

    
    /* semantic_anchor: file_management_functions */
    async loadSavedFiles() {
        try {
            const response = await fetch(`${this.apiBaseURL}/file-pairs`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            this.displayFilePairs(result.file_pairs);
            
        } catch (error) {
            console.error('Error loading saved files:', error);
            this.updateStatus('Failed to load saved files');
        }
    }
    
    displayFilePairs(pairs) {
        const container = document.getElementById('file-pairs-container');
        const statsElement = document.getElementById('file-stats');
        const totalPairsElement = document.getElementById('total-pairs');
        
        if (pairs.length === 0) {
            container.innerHTML = '<p class="no-files-message">No saved files found. Process some documents to see them here.</p>';
            statsElement.style.display = 'none';
            return;
        }
        
        // Show statistics
        totalPairsElement.textContent = pairs.length;
        statsElement.style.display = 'block';
        
        // Generate HTML for file pairs
        const pairsHTML = pairs.map(pair => {
            const extractionDate = new Date(pair.extraction_date).toLocaleString();
            const ocrMethod = this.getMethodFromFilename(pair.ocr_file);
            const extractionMethod = pair.extraction_method;
            
            return `
                <div class="file-pair">
                    <div class="file-pair-header">
                        <div class="file-pair-title">${pair.original_pdf}</div>
                        <div class="file-pair-date">${extractionDate}</div>
                    </div>
                    
                    <div class="file-pair-details">
                        <div class="file-detail">
                            <span class="file-detail-label">OCR Method:</span>
                            <span class="file-detail-value">
                                <span class="method-badge ${ocrMethod}">${ocrMethod}</span>
                            </span>
                        </div>
                        <div class="file-detail">
                            <span class="file-detail-label">Extraction Method:</span>
                            <span class="file-detail-value">
                                <span class="method-badge ${extractionMethod}">${extractionMethod}</span>
                            </span>
                        </div>
                        <div class="file-detail">
                            <span class="file-detail-label">OCR File:</span>
                            <span class="file-detail-value">${pair.ocr_file}</span>
                        </div>
                        <div class="file-detail">
                            <span class="file-detail-label">JSON File:</span>
                            <span class="file-detail-value">${pair.json_file}</span>
                        </div>
                    </div>
                    
                    <div class="file-pair-actions">
                        <button class="secondary-btn" onclick="app.downloadFile('${pair.ocr_file}')">
                            Download OCR
                        </button>
                        <button class="secondary-btn" onclick="app.downloadFile('${pair.json_file}')">
                            Download JSON
                        </button>
                        <button class="secondary-btn" onclick="app.loadOCRFile('${pair.ocr_file}')">
                            Load OCR Text
                        </button>
                        <button class="secondary-btn" onclick="app.loadJSONFile('${pair.json_file}')">
                            Load JSON Data
                        </button>
                    </div>
                </div>
            `;
        }).join('');
        
        container.innerHTML = pairsHTML;
    }
    
    getMethodFromFilename(filename) {
        if (filename.includes('_nougat_')) return 'nougat';
        if (filename.includes('_lm-studio_')) return 'lm-studio';
        if (filename.includes('_api_')) return 'api';
        return 'unknown';
    }
    
    async downloadFile(filename) {
        try {
            const response = await fetch(`${this.apiBaseURL}/download/${filename}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            this.updateStatus(`Downloaded: ${filename}`);
            
        } catch (error) {
            console.error('Error downloading file:', error);
            this.updateStatus(`Failed to download: ${filename}`);
            alert(`Failed to download: ${filename}`);
        }
    }
    
    async loadOCRFile(filename) {
        try {
            const response = await fetch(`${this.apiBaseURL}/download/${filename}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const text = await response.text();
            
            // Remove metadata header if present
            const cleanText = this.removeMarkdownMetadata(text);
            
            // Load into LLM input
            document.getElementById('llm-input-text').value = cleanText;
            this.processedText = cleanText;
            this.validateLLMInputs();
            
            // Scroll to LLM block
            document.getElementById('llm-block').scrollIntoView({ behavior: 'smooth' });
            
            this.updateStatus(`Loaded OCR text from: ${filename}`);
            
        } catch (error) {
            console.error('Error loading OCR file:', error);
            this.updateStatus(`Failed to load OCR file: ${filename}`);
            alert(`Failed to load OCR file: ${filename}`);
        }
    }
    
    async loadJSONFile(filename) {
        try {
            const response = await fetch(`${this.apiBaseURL}/download/${filename}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const jsonData = await response.json();
            this.extractedJSON = jsonData.extracted_data || jsonData;
            
            console.log('🔍 JSON LOADING DEBUG:');
            console.log('🔍 Raw jsonData:', jsonData);
            console.log('🔍 Final extractedJSON:', this.extractedJSON);
            console.log('🔍 processedText at JSON load:', this.processedText ? this.processedText.length + ' chars' : 'null');
            
            // Display in JSON output
            const jsonOutput = document.getElementById('json-output');
            jsonOutput.textContent = JSON.stringify(this.extractedJSON, null, 2);
            
            document.getElementById('llm-results').style.display = 'block';
            
            // Scroll to results
            document.getElementById('json-output').scrollIntoView({ behavior: 'smooth' });
            
            this.updateStatus(`Loaded JSON data from: ${filename}`);
            
        } catch (error) {
            console.error('Error loading JSON file:', error);
            this.updateStatus(`Failed to load JSON file: ${filename}`);
            alert(`Failed to load JSON file: ${filename}`);
        }
    }
    
    removeMarkdownMetadata(text) {
        // Remove YAML frontmatter and initial headers
        const lines = text.split('\n');
        let startIndex = 0;
        
        // Skip YAML frontmatter
        if (lines[0] === '---') {
            for (let i = 1; i < lines.length; i++) {
                if (lines[i] === '---') {
                    startIndex = i + 1;
                    break;
                }
            }
        }
        
        // Skip headers and metadata
        while (startIndex < lines.length) {
            const line = lines[startIndex].trim();
            if (line.startsWith('#') || line.startsWith('**') || line === '' || line === '---') {
                startIndex++;
            } else {
                break;
            }
        }
        
        return lines.slice(startIndex).join('\n').trim();
    }
    
    async clearAllFiles() {
        if (!confirm('Are you sure you want to delete all saved files? This action cannot be undone.')) {
            return;
        }
        
        try {
            // This would need to be implemented in the backend
            this.updateStatus('Clear all files feature not yet implemented');
            
        } catch (error) {
            console.error('Error clearing files:', error);
            this.updateStatus('Failed to clear files');
        }
    }

    /* semantic_anchor: validation_implementation */
    async startValidation() {
        console.log('🔍 VALIDATION DEBUG:');
        console.log('🔍 extractedJSON exists:', !!this.extractedJSON);
        console.log('🔍 processedText exists:', !!this.processedText);
        console.log('🔍 processedText length:', this.processedText ? this.processedText.length : 0);
        console.log('🔍 currentMarkdownFiles length:', this.currentMarkdownFiles.length);
        
        if (!this.extractedJSON || !this.processedText) {
            console.error('🔍 VALIDATION FAILED: Missing data');
            console.error('🔍 extractedJSON:', this.extractedJSON);
            console.error('🔍 processedText length:', this.processedText ? this.processedText.length : 'null/undefined');
            alert('Please extract JSON data and ensure source text is available before validation.');
            return;
        }

        const numSamples = parseInt(document.getElementById('validation-samples').value) || 3;
        
        this.showProgress('validation-progress', 'Validating with LLM...');
        this.updateStatus('Starting LLM validation...');

        try {
            const response = await fetch(`${this.apiBaseURL}/validate-json`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    json_data: this.extractedJSON,
                    source_text: this.processedText,
                    num_samples: numSamples
                })
            });

            if (!response.ok) {
                throw new Error(`Validation failed: ${response.status}`);
            }

            const result = await response.json();
            this.displayValidationResults(result);
            this.hideProgress('validation-progress');
            this.updateStatus('Validation completed');

        } catch (error) {
            console.error('Validation error:', error);
            this.hideProgress('validation-progress');
            this.updateStatus('Validation failed');
            alert(`Validation failed: ${error.message}`);
        }
    }

    displayValidationResults(result) {
        const validationBlock = document.getElementById('validation-block');
        const validationResults = document.getElementById('validation-results');
        const accuracyValue = document.getElementById('accuracy-value');
        const validatedCount = document.getElementById('validated-count');
        const correctCount = document.getElementById('correct-count');
        const validationDetails = document.getElementById('validation-details');

        // Show validation block and results
        validationBlock.style.display = 'block';
        validationResults.style.display = 'block';

        // Update summary
        accuracyValue.textContent = `${result.accuracy.toFixed(1)}%`;
        validatedCount.textContent = result.total_validated;
        correctCount.textContent = result.correct_count;

        // Set accuracy color class
        accuracyValue.className = 'accuracy-value';
        if (result.accuracy >= 80) {
            accuracyValue.classList.add('high');
        } else if (result.accuracy >= 60) {
            accuracyValue.classList.add('medium');
        } else {
            accuracyValue.classList.add('low');
        }

        // Display detailed results
        validationDetails.innerHTML = '';
        result.validation_results.forEach(item => {
            const validationItem = document.createElement('div');
            validationItem.className = 'validation-item';
            
            const isCorrect = item.verdict.is_correct;
            const statusClass = isCorrect ? 'correct' : 'incorrect';
            const statusText = isCorrect ? 'Correct' : 'Incorrect';

            validationItem.innerHTML = `
                <div class="validation-item-header">
                    <span class="validation-path">${item.path}</span>
                    <span class="validation-status ${statusClass}">${statusText}</span>
                </div>
                <div class="validation-claim">"${item.claim}"</div>
                <div class="validation-reasoning">${item.verdict.reasoning}</div>
                <div class="validation-quote">Quote: "${item.verdict.quote_from_text}"</div>
            `;
            
            validationDetails.appendChild(validationItem);
        });

        // Scroll to validation results
        validationBlock.scrollIntoView({ behavior: 'smooth' });
    }

    async saveWithValidation() {
        if (!this.extractedJSON) {
            alert('No JSON data to save.');
            return;
        }

        const validateOnSave = document.getElementById('validate-on-save').checked;
        const numSamples = parseInt(document.getElementById('validation-samples').value) || 3;

        this.updateStatus('Saving to database with validation...');

        try {
            const response = await fetch(`${this.apiBaseURL}/add-to-database`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    data: this.extractedJSON,
                    source_text: this.processedText,
                    validate_with_llm: validateOnSave,
                    num_validation_samples: numSamples
                })
            });

            if (!response.ok) {
                throw new Error(`Save failed: ${response.status}`);
            }

            const result = await response.json();
            
            if (result.success) {
                this.updateStatus('Successfully saved to database');
                alert(`Document saved successfully!\nDocument ID: ${result.document_id}`);
                
                if (result.llm_validation) {
                    alert(`LLM Validation Results:\nAccuracy: ${result.llm_validation.accuracy?.toFixed(1)}%\nValidated: ${result.llm_validation.total_validated} items`);
                }
            } else {
                throw new Error(result.message || 'Save failed');
            }

        } catch (error) {
            console.error('Save error:', error);
            this.updateStatus('Failed to save to database');
            alert(`Save failed: ${error.message}`);
        }
    }
}

/* semantic_anchor: application_initialization */
// Initialize the application when the DOM is loaded
let app; // Global reference for HTML onclick handlers

document.addEventListener('DOMContentLoaded', () => {
    app = new PhytoextractionApp();
});

/* semantic_anchor: lm_studio_integration */
// Helper functions for LM Studio integration
class LMStudioClient {
    constructor(baseURL = 'http://localhost:1234') {
        this.baseURL = baseURL;
    }

    async generateCompletion(prompt, options = {}) {
        const response = await fetch(`${this.baseURL}/v1/completions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                prompt: prompt,
                max_tokens: options.max_tokens || 4000,
                temperature: options.temperature || 0.1,
                ...options
            })
        });

        if (!response.ok) {
            throw new Error(`LM Studio API error: ${response.status}`);
        }

        return await response.json();
    }
}

/* semantic_anchor: api_call_option */
// Helper functions for external API calls (Gemini, OpenAI, etc.)
class ExternalAPIClient {
    constructor(provider, apiKey) {
        this.provider = provider;
        this.apiKey = apiKey;
    }

    async processDocument(content, options = {}) {
        // Implementation would depend on the specific API
        // This is a placeholder for the actual API integration
        throw new Error('External API integration not implemented');
    }
}
