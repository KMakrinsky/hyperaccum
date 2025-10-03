import pandas as pd
import json
import os
import re
import requests

# --- НАСТРОЙКИ ---
GROUND_TRUTH_CSV = 'ground_truth.csv'
JSON_DIR = 'json'
OUTPUT_METRICS_CSV = 'validation_metrics_llm_comparison.csv'

# Настройки для подключения к LM Studio
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
HEADERS = {"Content-Type": "application/json"}
# --- КОНЕЦ НАСТРОЕК ---

def normalize_doi_for_filename(doi):
    if 'doi.org/' in doi:
        doi = doi.split('doi.org/')[-1]
    return doi.replace('/', '')

def clean_text(text):
    if not isinstance(text, str): return ""
    return text.lower().strip()

def parse_csv_list(text):
    if not isinstance(text, str) or not text: return set()
    text = re.sub(r'\s*\(\d+[a-z]?\)\s*', '', text)
    text = text.replace(' and ', ',')
    items = text.split(',')
    return {clean_text(item) for item in items if clean_text(item)}

def calculate_prf1_from_counts(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1_score

def create_llm_evaluator_prompt(json_content_str, ground_truth_list, item_type_name):
    ground_truth_str = ", ".join(f'"{item}"' for item in ground_truth_list)

    return f"""
You are an expert data validation agent performing semantic comparison. Your task is to compare a ground truth list of items against a generated JSON document.

**Generated JSON Content:**
```json
{json_content_str}
```

**Ground Truth Items to Validate ({item_type_name}):**
[{ground_truth_str}]

**Your Task:**
1.  Carefully analyze the **meaning** of the "Generated JSON Content".
2.  Compare the "Ground Truth Items" list against the JSON content semantically. For example, "lead" should match an entry like `{{"element": "Pb"}}`.
3.  Identify and count the following:
    *   **True Positives (TP):** Items from the ground truth list that are correctly represented in the JSON.
    *   **False Positives (FP):** Items found in the JSON related to '{item_type_name}' that are NOT in the ground truth list.
    *   **False Negatives (FN):** Items from the ground truth list that are MISSING from the JSON.

**Output Format:**
Return ONLY a single, valid JSON object with the following structure. Do NOT include any other text or explanations.

{{
  "reasoning": "A brief explanation of your findings.",
  "true_positives_list": ["item1", "item2"],
  "false_positives_list": ["extra_item"],
  "false_negatives_list": ["missing_item"],
  "TP": 2,
  "FP": 1,
  "FN": 1
}}
"""

def evaluate_with_llm(json_content_str, ground_truth_set, item_type_name):
    if not json_content_str or not ground_truth_set:
        return 0, 0, len(ground_truth_set)

    prompt = create_llm_evaluator_prompt(json_content_str, list(ground_truth_set), item_type_name)
    
    payload = {
        "model": "local-model", "messages": [{"role": "user", "content": prompt}], "temperature": 0.0
    }

    try:
        response = requests.post(LM_STUDIO_URL, headers=HEADERS, json=payload, timeout=300)
        response.raise_for_status()
        llm_response_text = response.json()['choices'][0]['message']['content'].strip()
        
        json_match = re.search(r'\{.*\}', llm_response_text, re.DOTALL)
        if not json_match: raise ValueError("No JSON object found in LLM response")
            
        data = json.loads(json_match.group(0))
        tp = int(data.get("TP", 0))
        fp = int(data.get("FP", 0))
        fn = int(data.get("FN", 0))

        print(f"  LLM Eval for {item_type_name}: TP={tp}, FP={fp}, FN={fn}")
        return tp, fp, fn
    except Exception as e:
        print(f"  [ERROR] Failed to get/parse LLM response for {item_type_name}: {e}")
        return 0, 0, len(ground_truth_set)

def validate_entry(csv_row, current_index, total_rows):
    doi = csv_row['doi']
    filename_base = normalize_doi_for_filename(doi)
    json_path = os.path.join(JSON_DIR, f"{filename_base}.json")

    print(f"\n--- [ Статья {current_index}/{total_rows} ] ---")
    print(f"Processing DOI: {doi} -> File: {filename_base}.json")
    
    metrics = {'doi': doi, 'status': 'Error'}

    if not os.path.exists(json_path) or os.path.getsize(json_path) == 0:
        metrics['status'] = 'JSON File Not Found or Empty'
        return metrics

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            # Читаем JSON как одну большую строку
            json_content_str = f.read()
    except Exception as e:
        metrics['status'] = f'Cannot Read JSON File: {e}'
        return metrics

    all_precisions, all_recalls, all_f1s = [], [], []

    # --- LLM-оценка для каждой категории ---
    categories = ['group_list', 'plants', 'metals', 'methods_list']
    for category in categories:
        gt_set = parse_csv_list(csv_row[category])
        tp, fp, fn = evaluate_with_llm(json_content_str, gt_set, category)
        p, r, f1 = calculate_prf1_from_counts(tp, fp, fn)
        
        # Обрезаем имя для ключа словаря
        key_name = category.replace('_list', '')
        metrics.update({f'{key_name}_precision': p, f'{key_name}_recall': r, f'{key_name}_f1': f1})
        all_precisions.append(p); all_recalls.append(r); all_f1s.append(f1)

    # --- Средние метрики ---
    avg_p = sum(all_precisions) / len(all_precisions) if all_precisions else 0.0
    avg_r = sum(all_recalls) / len(all_recalls) if all_recalls else 0.0
    avg_f1 = sum(all_f1s) / len(all_f1s) if all_f1s else 0.0
    
    metrics.update({'article_avg_precision': avg_p, 'article_avg_recall': avg_r, 'article_avg_f1': avg_f1})
    print(f"\n  >>> Article Averages: Precision={avg_p:.2f}, Recall={avg_r:.2f}, F1={avg_f1:.2f}")

    metrics['status'] = 'Processed by LLM'
    return metrics

def main():
    if not os.path.exists(GROUND_TRUTH_CSV):
        print(f"Ошибка: Эталонный файл '{GROUND_TRUTH_CSV}' не найден.")
        return
    
    gt_df = pd.read_csv(GROUND_TRUTH_CSV)
    total_rows = len(gt_df)
    print(f"Найден файл '{GROUND_TRUTH_CSV}', содержащий {total_rows} статей для обработки.")

    all_metrics = []
    for index, row in gt_df.iterrows():
        metrics = validate_entry(row, index + 1, total_rows)
        all_metrics.append(metrics)

    metrics_df = pd.DataFrame(all_metrics)
    if not metrics_df.empty:
        core_metrics = ['doi', 'status', 'article_avg_precision', 'article_avg_recall', 'article_avg_f1']
        detail_metrics = sorted([col for col in metrics_df.columns if col not in core_metrics])
        metrics_df = metrics_df[core_metrics + detail_metrics]

    metrics_df.to_csv(OUTPUT_METRICS_CSV, index=False)
    print(f"\n✅ Валидация завершена. Результаты в '{OUTPUT_METRICS_CSV}'")

if __name__ == "__main__":
    main()