import json
import random
import requests
import os
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class JSONValidator:
    """Modular JSON validator using LLM as judge"""
    
    def __init__(self, lm_studio_url: str = "http://localhost:1234/v1/chat/completions"):
        self.lm_studio_url = lm_studio_url
        self.num_samples_to_validate = 3
    
    def query_lm_studio(self, prompt: str) -> Optional[str]:
        """Universal function for sending requests to LM Studio."""
        headers = {"Content-Type": "application/json"}
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1, 
            "max_tokens": 2000
        }
        
        logger.info(f"🌐 Sending request to LM Studio at: {self.lm_studio_url}")
        logger.info(f"📤 Request payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        
        try:
            response = requests.post(self.lm_studio_url, headers=headers, json=payload, timeout=180)
            logger.info(f"📥 Response status: {response.status_code}")
            
            response.raise_for_status()
            response_json = response.json()
            
            logger.info(f"📥 Response JSON: {json.dumps(response_json, ensure_ascii=False, indent=2)}")
            
            content = response_json['choices'][0]['message']['content']
            logger.info(f"🤖 LLM Response content: {content}")
            
            return content
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error: {e}")
            return None
        except (KeyError, IndexError) as e:
            logger.error(f"❌ Unexpected response format from LLM: {e}")
            logger.error(f"❌ Response was: {response.text if 'response' in locals() else 'No response'}")
            return None

    def flatten_json(self, data: Any, parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """Flatten JSON structure for easier processing"""
        items = {}
        if isinstance(data, dict):
            for k, v in data.items():
                new_key = parent_key + sep + k if parent_key else k
                items.update(self.flatten_json(v, new_key, sep=sep))
        elif isinstance(data, list):
            for i, v in enumerate(data):
                new_key = f"{parent_key}{sep}{i}" if parent_key else str(i)
                items.update(self.flatten_json(v, new_key, sep=sep))
        else:
            if data is not None and data != "" and not isinstance(data, list):
                 items[parent_key] = data
        return items

    def get_context_objects(self, full_json: Dict[str, Any], path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Find parent object and group ID for given path."""
        path_parts = path.split('.')
        parent_obj = None
        group_id = None
        
        # Start search from 'extracted_data' or use the whole json
        search_base = full_json.get('extracted_data', full_json)
        if not search_base:
            return None, None

        # Find group ID
        try:
            if 'groups' in path_parts:
                group_index = int(path_parts[path_parts.index('groups') + 1])
                group_id = search_base.get('groups', [])[group_index].get('group_id')
        except (KeyError, IndexError, ValueError, TypeError):
            pass

        # Find parent object
        try:
            parent_path = path_parts[:-1]
            temp_obj = search_base
            for part in parent_path:
                if isinstance(temp_obj, list) and part.isdigit():
                    temp_obj = temp_obj[int(part)]
                elif isinstance(temp_obj, dict):
                    temp_obj = temp_obj[part]
            
            if isinstance(temp_obj, dict):
                parent_obj = temp_obj
                
        except (KeyError, IndexError, TypeError):
            pass
            
        return parent_obj, group_id

    def formulate_claim_with_llm(self, path: str, value: Any, parent_obj: Dict[str, Any], group_id: Optional[str]) -> Optional[str]:
        """Stage 1: Ask LLM to formulate a meaningful claim."""
        key_to_validate = path.split('.')[-1]
        
        prompt = f"""
        You are an expert in analyzing scientific data. Your task is to turn a data fragment from JSON into a clear, meaningful, and verifiable statement in Russian.

        Here is the data for analysis:
        - Key to validate: "{key_to_validate}"
        - Its value: "{value}"
        - Context (object containing the key): {json.dumps(parent_obj, ensure_ascii=False, indent=2)}
        - Top-level context (experimental group, if any): "{group_id if group_id else 'No data'}"

        Rules:
        1. Create one sentence that can be verified against the scientific article text.
        2. If the context contains numerical data (e.g., 'total_abundance'), and the key to validate is a name (e.g., 'class_name'), FORMULATE A STATEMENT ABOUT THE NUMERICAL VALUE using the name as an identifier. This is the most important point!
        3. Your response should contain ONLY the statement itself, without extra words like "Here is the statement:".

        Example of good result:
        For lipid class 'PG' in group 'SA + Cd', the total content (total abundance) was 2.13.

        Formulate a statement for the provided data.
        """
        
        logger.info(f"🔍 Stage 1: Formulating claim for path: {path}")
        logger.info(f"🔍 Key to validate: {key_to_validate}")
        logger.info(f"🔍 Value: {value}")
        logger.info(f"🔍 Parent object: {json.dumps(parent_obj, ensure_ascii=False, indent=2)}")
        logger.info(f"🔍 Group ID: {group_id}")
        
        claim = self.query_lm_studio(prompt)
        
        if claim:
            logger.info(f"✅ Formulated claim: {claim}")
            return claim.strip()
        else:
            logger.error(f"❌ Failed to formulate claim for path: {path}")
            return None

    def validate_claim_with_llm(self, claim: str, source_text: str) -> Optional[Dict[str, Any]]:
        """Stage 2: Ask LLM judge to verify the formulated claim."""
        prompt = f"""
        You are an AI assistant acting as a meticulous judge. Your task is to verify whether the STATEMENT corresponds to the ORIGINAL TEXT of the scientific article.

        [ORIGINAL TEXT]:
        ---
        {source_text}
        ---

        [STATEMENT TO VERIFY]:
        ---
        {claim}
        ---

        Analyze the text and return ONLY a JSON object with the following keys:
        - "reasoning" (string): Brief reasoning on whether the statement satisfies the facts from the text.
        - "is_correct" (boolean): true if the statement is confirmed by the text, otherwise false.
        - "quote_from_text" (string): Exact quote from the text that confirms or refutes the statement.
        """
        
        logger.info(f"⚖️ Stage 2: Validating claim with LLM judge")
        logger.info(f"⚖️ Claim to validate: {claim}")
        logger.info(f"⚖️ Source text length: {len(source_text)} characters")
        
        response_str = self.query_lm_studio(prompt)
        if not response_str:
            logger.error(f"❌ No response from LLM judge for claim: {claim}")
            return None
        
        try:
            # Clean from possible artifacts like ```json ... ```
            if response_str.strip().startswith("```json"):
                response_str = response_str.strip()[7:-3]
            
            verdict = json.loads(response_str)
            logger.info(f"✅ Judge verdict: {json.dumps(verdict, ensure_ascii=False, indent=2)}")
            return verdict
        except json.JSONDecodeError as e:
            logger.error(f"❌ Judge returned invalid JSON: {response_str}")
            logger.error(f"❌ JSON decode error: {e}")
            return None

    def validate_json_data(self, json_data: Dict[str, Any], source_text: str, num_samples: Optional[int] = None) -> Dict[str, Any]:
        """Main validation function that validates JSON data against source text."""
        if num_samples is None:
            num_samples = self.num_samples_to_validate
            
        logger.info(f"🚀 Starting validation of JSON data with {num_samples} samples")
        logger.info(f"📊 JSON data keys: {list(json_data.keys())}")
        logger.info(f"📄 Source text length: {len(source_text)} characters")
        
        # Try to get extracted_data first, if not found, use the whole json_data
        extracted_data = json_data.get('extracted_data', json_data)
        flat_data = self.flatten_json(extracted_data)
        data_points = list(flat_data.items())
        
        logger.info(f"📋 Total flattened data points: {len(data_points)}")
        
        # Filter points for validation
        filtered_points = [
            (path, value) for path, value in data_points 
            if len(path.split('.')) > 2 and not isinstance(value, bool)
        ]

        logger.info(f"🔍 Filtered data points: {len(filtered_points)}")
        logger.info(f"🔍 Sample paths: {[path for path, _ in filtered_points[:5]]}")

        sample_size = min(num_samples, len(filtered_points))
        if sample_size == 0:
            logger.warning(f"❌ No suitable data points found for validation after filtering")
            return {
                "success": False,
                "message": "No suitable data points found for validation after filtering",
                "validation_results": [],
                "accuracy": 0.0,
                "total_validated": 0,
                "correct_count": 0,
                "sample_size": 0
            }
            
        sampled_points = random.sample(filtered_points, sample_size)
        logger.info(f"🎯 Selected {sample_size} random points for validation")
        logger.info(f"🎯 Sampled paths: {[path for path, _ in sampled_points]}")

        validation_results = []
        correct_answers_count = 0

        for i, (path, value) in enumerate(sampled_points):
            logger.info(f"🔄 Validating element {i+1}/{sample_size} (path: {path})")
            
            parent_obj, group_id = self.get_context_objects(json_data, path)
            if not parent_obj:
                logger.warning(f"❌ Could not find context for element {path}, skipping")
                continue
            
            # Stage 1: Formulation
            claim = self.formulate_claim_with_llm(path, value, parent_obj, group_id)
            if not claim:
                logger.warning(f"❌ Could not formulate claim for {path}, skipping")
                continue

            # Stage 2: Validation
            llm_verdict = self.validate_claim_with_llm(claim, source_text)
            if not llm_verdict:
                logger.warning(f"❌ Could not get verdict from judge for {path}, skipping")
                continue
            
            validation_results.append({
                "path": path, 
                "value": value,
                "claim": claim, 
                "verdict": llm_verdict
            })
            
            is_correct = llm_verdict.get("is_correct", False)
            if is_correct:
                correct_answers_count += 1
                logger.info(f"✅ Validation {i+1} CORRECT")
            else:
                logger.info(f"❌ Validation {i+1} INCORRECT")

        # Calculate accuracy
        accuracy = (correct_answers_count / len(validation_results)) * 100 if validation_results else 0.0
        
        logger.info(f"📈 Final results: {len(validation_results)} validated, {correct_answers_count} correct, {accuracy:.1f}% accuracy")
        
        return {
            "success": True,
            "message": f"Validation completed successfully",
            "validation_results": validation_results,
            "accuracy": accuracy,
            "total_validated": len(validation_results),
            "correct_count": correct_answers_count,
            "sample_size": sample_size
        }

    def validate_json_file(self, json_file_path: str, source_text_path: str, num_samples: Optional[int] = None) -> Dict[str, Any]:
        """Validate JSON file against source text file."""
        try:
            # Load JSON data
            with open(json_file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # Load source text
            with open(source_text_path, 'r', encoding='utf-8') as f:
                source_text = f.read()
                
            return self.validate_json_data(json_data, source_text, num_samples)
            
        except FileNotFoundError as e:
            return {
                "success": False,
                "message": f"File not found: {str(e)}",
                "validation_results": [],
                "accuracy": 0.0,
                "total_validated": 0,
                "correct_count": 0,
                "sample_size": 0
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "message": f"Invalid JSON file: {str(e)}",
                "validation_results": [],
                "accuracy": 0.0,
                "total_validated": 0,
                "correct_count": 0,
                "sample_size": 0
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Validation error: {str(e)}",
                "validation_results": [],
                "accuracy": 0.0,
                "total_validated": 0,
                "correct_count": 0,
                "sample_size": 0
            }
