import requests
from bs4 import BeautifulSoup
import time
import csv
from datetime import datetime
import gradio as gr

# URL сайту для перевірки
URL = 'https://example.com/news'

# Періодичність перевірки (в секундах)
CHECK_INTERVAL = 300  # кожні 5 хвилин

# Ініціалізація змінних
tracked_blocks = {}

def fetch_news():
    response = requests.get(URL)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Знайти новинні блоки (змінити відповідно до структури сайту)
    news_blocks = soup.find_all('div', class_='news-block')
    
    current_blocks = {}
    
    for block in news_blocks:
        section = block.find('div', class_='news-section').text.strip()
        title = block.find('h2', class_='news-title').text.strip()
        time_posted = block.find('time', class_='news-time')['datetime']
        
        block_id = f"{section}:{title}:{time_posted}"
        
        if block_id not in tracked_blocks:
            # Новий блок, додати до відслідковуваних
            tracked_blocks[block_id] = {
                'section': section,
                'title': title,
                'time_posted': time_posted,
                'time_displaced': None
            }
        
        current_blocks[block_id] = True
    
    # Оновити час витіснення для блоків, яких більше немає на головній
    for block_id in tracked_blocks.keys():
        if block_id not in current_blocks:
            if tracked_blocks[block_id]['time_displaced'] is None:
                tracked_blocks[block_id]['time_displaced'] = datetime.now().isoformat()

def export_to_csv():
    with open('news_metadata.csv', 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['section', 'title', 'time_posted', 'time_displaced']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for block_id, data in tracked_blocks.items():
            writer.writerow(data)

def start_tracking():
    try:
        while True:
            fetch_news()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        export_to_csv()
        print("Дані експортовані у файл news_metadata.csv")

def stop_tracking():
    # Експорт даних при зупинці
    export_to_csv()
    return "Дані експортовані у файл news_metadata.csv"

def show_csv():
    try:
        with open('news_metadata.csv', 'r', encoding='utf-8') as csvfile:
            content = csvfile.read()
        return content
    except FileNotFoundError:
        return "Файл news_metadata.csv не знайдено. Спробуйте запустити трекінг."

# Візуальний інтерфейс Gradio
iface = gr.Interface(
    fn=lambda action: start_tracking() if action == "Запустити трекінг" else stop_tracking(),
    inputs=gr.inputs.Radio(["Запустити трекінг", "Зупинити трекінг"], label="Дія"),
    outputs="text",
    live=True,
    title="Новинний трекер",
    description="Система для трекінгу новинних блоків на головній сторінці сайту та експорту метаданих у CSV файл."
)

iface.launch()
