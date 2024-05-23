import requests
from bs4 import BeautifulSoup
import time
import csv
from datetime import datetime
import gradio as gr
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from PIL import Image
import schedule
import cv2
import os
import pandas as pd

# Налаштування Selenium WebDriver
chrome_options = Options()
chrome_options.add_argument("--headless")  # запуск без графічного інтерфейсу
chrome_service = ChromeService(executable_path='/usr/local/bin/chromedriver')  # замініть на ваш шлях до chromedriver

# Ініціалізація змінних
tracked_blocks = {}
URL = ''
SECTION = ''
TITLE = ''
BLOCK_ID = ''
SCREENSHOT_FOLDER = 'screenshots'
CSV_FILE = 'news_metadata.csv'

if not os.path.exists(SCREENSHOT_FOLDER):
    os.makedirs(SCREENSHOT_FOLDER)

# Створення CSV файлу, якщо не існує
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['section', 'title', 'block_id', 'screenshot_link', 'start_date', 'end_date']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

def fetch_news(url, section, title, block_id):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Знайти новинні блоки (змінити відповідно до структури сайту)
    news_blocks = soup.find_all('div', class_='news-block')

    current_blocks = {}

    for block in news_blocks:
        block_section = block.find('div', class_='news-section').text.strip()
        block_title = block.find('h2', class_='news-title').text.strip()
        time_posted = block.find('time', class_='news-time')['datetime']

        block_identifier = f"{block_section}:{block_title}:{time_posted}"

        if block_section == section and block_title == title:
            current_blocks[block_identifier] = True

    screenshot_path = os.path.join(SCREENSHOT_FOLDER, f"{block_id}.png")
    current_screenshot_path = os.path.join(SCREENSHOT_FOLDER, f"{block_id}_current.png")

    # Зробити скріншот сторінки
    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
    driver.get(url)

    # Виконати JavaScript для отримання повного розміру сторінки
    total_width = driver.execute_script("return document.body.scrollWidth")
    total_height = driver.execute_script("return document.body.scrollHeight")
    driver.set_window_size(total_width, total_height)
    driver.save_screenshot(current_screenshot_path)
    driver.quit()

    # Порівняти збережений скріншот з новим
    if os.path.exists(screenshot_path):
        img1 = cv2.imread(screenshot_path)
        img2 = cv2.imread(current_screenshot_path)
        if not img1 is None and not img2 is None and cv2.norm(img1, img2, cv2.NORM_L2) == 0:
            return
        else:
            # Оновити скріншот і зареєструвати видалення блоку
            os.remove(screenshot_path)
            os.rename(current_screenshot_path, screenshot_path)
            if block_identifier in current_blocks:
                current_blocks[block_identifier] = True
            else:
                current_blocks[block_identifier] = False

            if block_identifier not in tracked_blocks or not tracked_blocks[block_identifier]:
                tracked_blocks[block_identifier] = {
                    'section': section,
                    'title': title,
                    'time_posted': time_posted,
                    'time_displaced': datetime.now().isoformat()
                }

def export_to_csv(section, title, block_id, screenshot_link, start_date, end_date):
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['section', 'title', 'block_id', 'screenshot_link', 'start_date', 'end_date'])
        writer.writerow({
            'section': section,
            'title': title,
            'block_id': block_id,
            'screenshot_link': screenshot_link,
            'start_date': start_date,
            'end_date': end_date
        })

def start_tracking(interval):
    schedule.clear()  # Очистити всі заплановані завдання

    def job():
        fetch_news(URL, SECTION, TITLE, BLOCK_ID)
        screenshot_link = os.path.join(SCREENSHOT_FOLDER, f"{BLOCK_ID}.png")
        start_date = datetime.now().isoformat()
        end_date = (datetime.now() + pd.Timedelta(seconds=interval)).isoformat()
        export_to_csv(SECTION, TITLE, BLOCK_ID, screenshot_link, start_date, end_date)
        print("Дані експортовані у файл news_metadata.csv")

    schedule.every(interval).seconds.do(job)

    while True:
        schedule.run_pending()
        time.sleep(1)

def stop_tracking():
    schedule.clear()
    return "Трекінг зупинено"

def show_screenshot(url):
    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
    driver.get(url)

    # Виконати JavaScript для отримання повного розміру сторінки
    total_width = driver.execute_script("return document.body.scrollWidth")
    total_height = driver.execute_script("return document.body.scrollHeight")
    driver.set_window_size(total_width, total_height)
    screenshot_path = os.path.join(SCREENSHOT_FOLDER, 'temp_screenshot.png')
    driver.save_screenshot(screenshot_path)
    driver.quit()
    return screenshot_path

def confirm_selection(uploaded_image, section, title, block_id, start_date, end_date):
    global URL, SECTION, TITLE, BLOCK_ID
    SECTION = section
    TITLE = title
    BLOCK_ID = block_id
    saved_path = os.path.join(SCREENSHOT_FOLDER, f"{block_id}.png")
    image = Image.open(uploaded_image)
    image.save(saved_path)
    export_to_csv(section, title, block_id, saved_path, start_date, end_date)
    return f"Виділення збережено як {saved_path}"

def load_titles():
    data = pd.read_csv(CSV_FILE)
    return data['title'].unique().tolist()

def load_parameters(title):
    data = pd.read_csv(CSV_FILE)
    row = data[data['title'] == title].iloc[0]
    return row['section'], row['title'], row['block_id'], row['start_date'], row['end_date']

# Візуальний інтерфейс Gradio
with gr.Blocks() as demo:
    url_input = gr.Textbox(label="Адреса сайту")
    screenshot_output = gr.Image(label="Скріншот сторінки")
    upload_input = gr.Image(type="filepath", label="Завантажити скріншот для виділення")
    section_input = gr.Textbox(label="Назва розділу")
    title_dropdown = gr.Dropdown(label="Заголовок", choices=load_titles())
    title_input = gr.Textbox(label="Заголовок")
    block_id_input = gr.Textbox(label="Номерний ідентифікатор")
    start_date_input = gr.Textbox(label="Дата початку (YYYY-MM-DD HH:MM)", value=datetime.now().strftime('%Y-%m-%d %H:%M'))
    end_date_input = gr.Textbox(label="Дата закінчення (YYYY-MM-DD HH:MM)", value=datetime.now().strftime('%Y-%m-%d %H:%M'))
    interval_input = gr.Number(label="Інтервал трекінгу (секунди)", value=3600)
    confirm_button = gr.Button("Підтвердити виділення")
    confirm_output = gr.Textbox(label="Статус підтвердження")
    start_button = gr.Button("Запустити трекінг")
    stop_button = gr.Button("Зупинити трекінг")
    tracking_status = gr.Textbox(label="Статус трекінгу")

    def update_screenshot(url):
        global URL
        URL = url
        return show_screenshot(url)

    def update_parameters(title):
        section, title, block_id, start_date, end_date = load_parameters(title)
        return section, title, block_id, start_date, end_date

    url_input.change(update_screenshot, inputs=url_input, outputs=screenshot_output)
    title_dropdown.change(update_parameters, inputs=title_dropdown, outputs=[section_input, title_input, block_id_input, start_date_input, end_date_input])
    confirm_button.click(confirm_selection, inputs=[upload_input, section_input, title_input, block_id_input, start_date_input, end_date_input], outputs=confirm_output)
    start_button.click(start_tracking, inputs=interval_input, outputs=tracking_status)
    stop_button.click(stop_tracking, outputs=tracking_status)

demo.launch()
