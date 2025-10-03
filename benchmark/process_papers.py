import google.generativeai as genai
import os
import fitz  # PyMuPDF
from PIL import Image
import time

# --- НАСТРОЙКИ ---
# Вставьте свой API ключ для Gemini
GOOGLE_API_KEY = 'AIzaSyCs6uzqbha1z6kx7_urs-UBIjvAGNAk9Is'

# Названия папок
PAPERS_DIR = 'papers'
OCR_DIR = 'ocr'
TEMP_IMAGE_DIR = 'temp_images'

# Настройки для API
# Задержка между запросами к API в секундах
DELAY_BETWEEN_REQUESTS = 5
# Количество повторных попыток при ошибке
RETRY_COUNT = 3
# Задержка перед повторной попыткой в секундах
RETRY_DELAY = 10
# --- КОНЕЦ НАСТРОЕК ---

# Конфигурация Gemini API
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

def create_directories():
    """Создает необходимые директории, если они не существуют."""
    for dir_path in [PAPERS_DIR, OCR_DIR, TEMP_IMAGE_DIR]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"Папка '{dir_path}' создана.")

def get_system_prompt(page_num, total_pages):
    """Формирует системный промпт для указанной страницы."""
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
    """Отправляет изображение страницы и системный промпт в Gemini API."""
    prompt = get_system_prompt(page_num, total_pages)
    
    for attempt in range(RETRY_COUNT):
        try:
            print(f"Отправка страницы {page_num} на распознавание (попытка {attempt + 1}/{RETRY_COUNT})...")
            img = Image.open(image_path)
            
            response = model.generate_content([prompt, img], stream=True)
            response.resolve()
            
            if response.candidates and response.candidates[0].content.parts:
                return response.text
            else:
                print(f"Предупреждение: Ответ от API для страницы {page_num} не содержит текста.")
                return "[Содержимое не найдено]"
                
        except Exception as e:
            print(f"Ошибка при обращении к Gemini API для страницы {page_num}: {e}")
            if attempt < RETRY_COUNT - 1:
                print(f"Повторная попытка через {RETRY_DELAY} секунд...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"Не удалось получить ответ от API для страницы {page_num} после {RETRY_COUNT} попыток.")
                return None
    return None

def process_pdf(pdf_path, temp_dir):
    """
    Разбивает PDF на страницы, сохраняет их как изображения и возвращает пути к ним.
    ИСПРАВЛЕННАЯ ВЕРСИЯ ФУНКЦИИ.
    """
    image_paths = []
    try:
        doc = fitz.open(pdf_path)
        # Сохраняем количество страниц в переменную ПЕРЕД закрытием документа
        total_pages = len(doc)
        print(f"Обработка PDF: '{os.path.basename(pdf_path)}'. Всего страниц: {total_pages}")
        
        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            # DPI 300 - хорошее качество для OCR
            pix = page.get_pixmap(dpi=300)
            image_path = os.path.join(temp_dir, f"page_{page_num + 1}.png")
            pix.save(image_path)
            image_paths.append(image_path)
            
        # Закрываем документ после того, как все операции с ним завершены
        doc.close()
        # Возвращаем переменную с количеством страниц
        return image_paths, total_pages
    except Exception as e:
        print(f"Не удалось обработать PDF-файл '{pdf_path}': {e}")
        return [], 0


def main():
    """Основная функция для запуска процесса."""
    create_directories()
    
    pdf_files = [f for f in os.listdir(PAPERS_DIR) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"В папке '{PAPERS_DIR}' не найдено PDF-файлов.")
        return

    for pdf_file in pdf_files:
        pdf_path = os.path.join(PAPERS_DIR, pdf_file)
        base_name = os.path.splitext(pdf_file)[0]
        md_file_path = os.path.join(OCR_DIR, f"{base_name}.md")
        
        # Создаем временную папку для изображений текущего PDF
        current_temp_dir = os.path.join(TEMP_IMAGE_DIR, base_name)
        if not os.path.exists(current_temp_dir):
            os.makedirs(current_temp_dir)
            
        page_image_paths, total_pages = process_pdf(pdf_path, current_temp_dir)
        
        if not page_image_paths:
            continue
            
        full_text = f"# Распознанный текст из файла: {pdf_file}\n\n"
        for i, img_path in enumerate(page_image_paths):
            page_number = i + 1
            print(f"\n--- Обработка страницы {page_number}/{total_pages} файла '{pdf_file}' ---")
            
            extracted_text = ocr_page_with_gemini(img_path, page_number, total_pages)
            
            # Добавляем разделитель и заголовок для каждой страницы
            full_text += "---\n\n"
            full_text += f"## Страница {page_number}\n\n"

            if extracted_text:
                full_text += extracted_text + "\n\n"
                print("Текст успешно распознан.")
            else:
                full_text += "[Не удалось распознать текст на этой странице]\n\n"
                print("Не удалось распознать текст.")
                
            # Удаляем временное изображение страницы после обработки
            os.remove(img_path)
            
            # Задержка перед следующим запросом, чтобы не превышать лимиты API
            if i < len(page_image_paths) - 1:
                print(f"Задержка {DELAY_BETWEEN_REQUESTS} секунд...")
                time.sleep(DELAY_BETWEEN_REQUESTS)

        # Сохраняем весь текст в MD-файл
        try:
            with open(md_file_path, 'w', encoding='utf-8') as md_file:
                md_file.write(full_text)
            print(f"\n✅ Распознанный текст полностью сохранен в файл: '{md_file_path}'")
        except IOError as e:
            print(f"❌ Ошибка при записи в файл '{md_file_path}': {e}")
            
        # Удаляем временную папку для изображений после обработки PDF
        try:
            os.rmdir(current_temp_dir)
        except OSError as e:
            print(f"Не удалось удалить временную папку '{current_temp_dir}': {e}")
        
    # Удаляем основную временную папку, если она пуста
    try:
        if not os.listdir(TEMP_IMAGE_DIR):
            os.rmdir(TEMP_IMAGE_DIR)
    except OSError as e:
        print(f"Не удалось удалить основную временную папку '{TEMP_IMAGE_DIR}': {e}")


if __name__ == '__main__':
    main()