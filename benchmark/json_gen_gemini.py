import os
import google.generativeai as genai
import json
import time

# --- НАСТРОЙКИ ---
OCR_DIR = 'ocr'
JSON_OUTPUT_DIR = 'json'
PROMPT_FILE = 'prompt.md'

# Настройки для повторных попыток, как в вашем примере
RETRY_COUNT = 3
RETRY_DELAY = 5 # секунд
# --- КОНЕЦ НАСТРОЕК ---

def configure_gemini():
    """Настраивает и проверяет API-ключ для Gemini."""
    try:
        # Библиотека автоматически подхватит ключ из переменной окружения GOOGLE_API_KEY
        api_key = "AIzaSyCs6uzqbha1z6kx7_urs-UBIjvAGNAk9Is"
        if not api_key:
            print("[ОШИБКА] Переменная окружения GOOGLE_API_KEY не найдена.")
            print("Пожалуйста, установите её и перезапустите скрипт.")
            return None
        genai.configure(api_key=api_key)
        print("API-ключ Google Gemini успешно сконфигурирован.")
        return True
    except Exception as e:
        print(f"[ОШИБКА] Не удалось сконфигурировать Gemini: {e}")
        return None

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

def get_gemini_response(system_prompt, user_content):
    """
    Отправляет запрос к Gemini API, используя синтаксис, совместимый
    с вашей версией библиотеки. Включает механизм повторных попыток.
    """
    # Инициализируем модель. Рекомендуется использовать 'gemini-1.5-pro-latest'
    # для наилучшего соотношения производительности и доступности.
    model = genai.GenerativeModel('gemini-2.5-flash')

    # ВАЖНО: Убедитесь, что в вашем prompt.md есть четкое указание
    # возвращать ТОЛЬКО JSON, так как мы не можем использовать response_mime_type.
    # Пример: "Твой ответ должен быть только валидным JSON объектом без ```json ... ```"

    for attempt in range(RETRY_COUNT):
        try:
            print(f"  Отправка запроса в Google Gemini API (попытка {attempt + 1}/{RETRY_COUNT})...")

            # Создаем список из промпта и текста статьи, как в вашем рабочем примере.
            # Это синтаксис для более старых версий библиотеки.
            response = model.generate_content([system_prompt, user_content])
            
            # response.text - это самый простой способ получить результат
            gemini_response_text = response.text.strip()
            
            print("  Успешно получен ответ от Gemini.")
            return gemini_response_text

        except Exception as e:
            print(f"  [ОШИБКА] Произошла ошибка при запросе к Gemini API: {e}")
            if attempt < RETRY_COUNT - 1:
                print(f"  Повторная попытка через {RETRY_DELAY} секунд...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  Не удалось получить ответ от Gemini после {RETRY_COUNT} попыток.")
                return None
    return None

def main():
    """Основная функция для запуска процесса генерации."""
    print("--- Запуск скрипта генерации JSON с использованием Gemini ---")
    
    if not configure_gemini():
        return

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

        gemini_result = get_gemini_response(system_prompt, article_text)
        
        if gemini_result is not None:
            # Пытаемся очистить ответ от возможных артефактов, таких как ```json ... ```
            if gemini_result.startswith("```json"):
                gemini_result = gemini_result.strip("```json").strip()

            try:
                # Проверяем, является ли ответ валидным JSON
                json.loads(gemini_result)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(gemini_result)
                print(f"  ✅ Валидный JSON от Gemini сохранен в '{output_path}'")
            except json.JSONDecodeError:
                print(f"  [ПРЕДУПРЕЖДЕНИЕ] Ответ от Gemini не является валидным JSON. Ответ был:\n---\n{gemini_result}\n---")
                # Сохраняем "сырой" ответ в текстовый файл для отладки
                error_path = os.path.join(JSON_OUTPUT_DIR, f"{base_name}_error.txt")
                with open(error_path, 'w', encoding='utf-8') as f:
                    f.write(gemini_result)
                print(f"  'Сырой' ответ сохранен для анализа в '{error_path}'")
            except Exception as e:
                print(f"  [ОШИБКА] Не удалось сохранить файл: {e}")
        else:
            print("  Не получен ответ от Gemini, файл не будет создан.")

    print("\n--- Процесс генерации завершен. ---")

if __name__ == "__main__":
    main()