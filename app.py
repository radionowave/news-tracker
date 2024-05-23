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

# Налаштування Selenium WebDriver
chrome_options = Options()
chrome_options.add_argument("--headless")  # запуск без графічного інтерфейсу
chrome_service = ChromeService(executable_path='/path/to/chromedriver')  # замініть на ваш шлях до chromedriver

# Ініціалізація змінних
tracked_blocks = {}
URL = ''
SECTION = ''
TITLE = ''
BLOCK_ID = ''
SCREENSHOT_FOLDER = 'screenshots'

if not os.path.exists(SCREENSHOT_FOLDER):
    os.makedirs(SCREENSHOT_FOLDER)

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

def export_to_csv():
    with open('news_metadata.csv', 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['section', 'title', 'time_posted', 'time_displaced']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for block_id, data in tracked_blocks.items():
            writer.writerow(data)

def start_tracking():
    global URL, SECTION, TITLE, BLOCK_ID
    fetch_news(URL, SECTION, TITLE, BLOCK_ID)
    export_to_csv()
    print("Дані експортовані у файл news_metadata.csv")

def show_screenshot(url):
    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
    driver.get(url)
    screenshot_path = os.path.join(SCREENSHOT_FOLDER, 'temp_screenshot.png')
    driver.save_screenshot(screenshot_path)
    driver.quit()
    return screenshot_path

def confirm_selection(section, title, block_id):
    global URL, SECTION, TITLE, BLOCK_ID
    SECTION = section
    TITLE = title
    BLOCK_ID = block_id
    screenshot_path = os.path.join(SCREENSHOT_FOLDER, 'temp_screenshot.png')
    saved_path = os.path.join(SCREENSHOT_FOLDER, f"{block_id}.png")
    os.rename(screenshot_path, saved_path)
    return f"Виділення збережено як {saved_path}"

def schedule_tracking(start_date, end_date):
    def job():
        start_tracking()

    schedule.every().hour.until(end_date).do(job)

    while datetime.now() < end_date:
        schedule.run_pending()
        time.sleep(1)

# Візуальний інтерфейс Gradio
with gr.Blocks() as demo:
    url_input = gr.Textbox(label="Адреса сайту")
    screenshot_output = gr.Image(label="Скріншот сторінки")
    section_input = gr.Textbox(label="Назва розділу")
    title_input = gr.Textbox(label="Заголовок")
    block_id_input = gr.Textbox(label="Номерний ідентифікатор")
    confirm_button = gr.Button("Підтвердити виділення")
    confirm_output = gr.Textbox(label="Статус підтвердження")

    schedule_start_input = gr.Date(label="Дата початку")
    schedule_end_input = gr.Date(label="Дата закінчення")
    schedule_button = gr.Button("Запланувати трекінг")
    schedule_output = gr.Textbox(label="Статус планування")

    def update_screenshot(url):
        global URL
        URL = url
        return show_screenshot(url)

    url_input.change(update_screenshot, inputs=url_input, outputs=screenshot_output)
    confirm_button.click(confirm_selection, inputs=[section_input, title_input, block_id_input], outputs=confirm_output)
    schedule_button.click(schedule_tracking, inputs=[schedule_start_input, schedule_end_input], outputs=schedule_output)

demo.launch()
