import os
import requests

# --- НАСТРОЙКИ ---
OCR_DIR = 'ocr'
JSON_OUTPUT_DIR = 'json'
PROMPT_FILE = 'prompt.md'

# Настройки для подключения к LM Studio
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
HEADERS = {"Content-Type": "application/json"}
# --- КОНЕЦ НАСТРОЕК ---

def load_prompt(file_path):
    """Загружает системный промпт из файла."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Ошибка: Файл с системным промптом не найден по пути '{file_path}'")
        return None
    except Exception as e:
        print(f"Ошибка при чтении файла с промптом: {e}")
        return None

def get_llm_response(system_prompt, user_content):
    """Отправляет системный промпт и контент пользователя, возвращает сырой ответ."""
    
    # Формируем запрос с двумя сообщениями: системным и пользовательским
    payload = {
        "model": "local-model",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.1,
    }
    
    print("  Отправка запроса в LM Studio...")
    try:
        response = requests.post(LM_STUDIO_URL, headers=HEADERS, json=payload, timeout=1500)
        response.raise_for_status()
        
        # Просто получаем текстовый ответ и возвращаем его
        llm_response_text = response.json()['choices'][0]['message']['content'].strip()
        print("  Успешно получен ответ от LLM.")
        return llm_response_text

    except requests.exceptions.RequestException as e:
        print(f"  [ОШИБКА] Не удалось подключиться к LM Studio: {e}")
        return None
    except Exception as e:
        print(f"  [ОШИБКА] Произошла непредвиденная ошибка при запросе: {e}")
        return None

def main():
    """Основная функция для запуска процесса генерации."""
    print("--- Запуск скрипта генерации JSON ---")
    
    system_prompt = load_prompt(PROMPT_FILE)
    if not system_prompt:
        return
    print(f"Успешно загружен системный промпт из '{PROMPT_FILE}'.")
    
    if not os.path.isdir(OCR_DIR):
        print(f"Ошибка: Папка с MD-файлами '{OCR_DIR}' не найдена.")
        return
    os.makedirs(JSON_OUTPUT_DIR, exist_ok=True)
    
    md_files = [f for f in os.listdir(OCR_DIR) if f.endswith('.md')]
    if not md_files:
        print(f"В папке '{OCR_DIR}' не найдено .md файлов для обработки.")
        return
    
    total_files = len(md_files)
    print(f"Найдено {total_files} .md файлов для обработки.")

    for i, md_filename in enumerate(md_files):
        print(f"\n--- [ Файл {i + 1}/{total_files} ]: {md_filename} ---")
        
        base_name = os.path.splitext(md_filename)[0]
        input_path = os.path.join(OCR_DIR, md_filename)
        output_path = os.path.join(JSON_OUTPUT_DIR, f"{base_name}.json")
        
        if os.path.exists(output_path):
            print("  JSON-файл уже существует. Пропускаем.")
            continue
            
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                article_text = f.read()
        except Exception as e:
            print(f"  [ОШИБКА] Не удалось прочитать файл: {e}")
            continue

        # Получаем сырой ответ от LLM, передавая промпт и текст раздельно
        llm_result = get_llm_response(system_prompt, article_text)
        
        # Если что-то получили, просто записываем это в файл
        if llm_result is not None:
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(llm_result)
                print(f"  ✅ Ответ от LLM как есть сохранен в '{output_path}'")
            except Exception as e:
                print(f"  [ОШИБКА] Не удалось сохранить файл: {e}")
        else:
            print("  Не получен ответ от LLM, файл не будет создан.")


    print("\n--- Процесс генерации завершен. ---")

if __name__ == "__main__":
    main()