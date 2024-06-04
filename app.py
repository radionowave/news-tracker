import os
import sqlite3
import time
import csv
import requests
from bs4 import BeautifulSoup
import gradio as gr

# Створення та підключення до бази даних
def initialize_db():
    conn = sqlite3.connect('news_aggregator.db')
    c = conn.cursor()

    # Видалення існуючої таблиці monitors (якщо є)
    c.execute('''DROP TABLE IF EXISTS monitors''')

    # Створення таблиці для збереження моніторингів
    c.execute('''CREATE TABLE IF NOT EXISTS monitors (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        url TEXT NOT NULL,
        text_fragment TEXT NOT NULL,
        last_seen TEXT,
        start_date TEXT NOT NULL,
        stop_date TEXT,
        article_id INTEGER NOT NULL UNIQUE
    )''')

    conn.commit()
    conn.close()

def check_text_fragment(url, text_fragment):
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        if text_fragment in soup.get_text():
            return True
    return False

def update_last_seen(monitor_id):
    conn = sqlite3.connect('news_aggregator.db')
    c = conn.cursor()
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    c.execute("UPDATE monitors SET last_seen = ? WHERE id = ?", (current_time, monitor_id))
    conn.commit()
    conn.close()

def update_stop_date(monitor_id):
    conn = sqlite3.connect('news_aggregator.db')
    c = conn.cursor()
    stop_date = time.strftime('%Y-%m-%d %H:%M:%S')
    c.execute("UPDATE monitors SET stop_date = ? WHERE id = ? AND stop_date IS NULL", (stop_date, monitor_id))
    conn.commit()
    conn.close()

def monitor_sites():
    conn = sqlite3.connect('news_aggregator.db')
    c = conn.cursor()
    c.execute("SELECT * FROM monitors")
    monitors = c.fetchall()
    
    for monitor in monitors:
        if check_text_fragment(monitor[2], monitor[3]):
            update_last_seen(monitor[0])
        else:
            update_stop_date(monitor[0])
    
    conn.close()

def add_monitor(name, url, text_fragment, article_id):
    if not url or not text_fragment or not article_id:
        return "Жодне поле не може бути порожніми"

    if not name:
        name = text_fragment

    conn = sqlite3.connect('news_aggregator.db')
    c = conn.cursor()

    c.execute("SELECT * FROM monitors WHERE text_fragment = ? AND last_seen IS NULL", (text_fragment,))
    existing_monitor = c.fetchone()
    
    if existing_monitor:
        return "Цей фрагмент вже раніше додано до моніторингу!"

    c.execute("SELECT * FROM monitors WHERE article_id = ?", (article_id,))
    existing_article_id = c.fetchone()
    
    if existing_article_id:
        return "Цифровий ідентифікатор вже використовується!"

    start_date = time.strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT INTO monitors (name, url, text_fragment, start_date, article_id) VALUES (?, ?, ?, ?, ?)", (name, url, text_fragment, start_date, article_id))
    
    conn.commit()
    conn.close()
    
    return "Моніторинг додано!"

def update_monitor(name, url, text_fragment, article_id):
    if not name or not url or not text_fragment or not article_id:
        return "Жодне поле не може бути порожніми"

    conn = sqlite3.connect('news_aggregator.db')
    c = conn.cursor()

    c.execute("SELECT * FROM monitors WHERE text_fragment = ? AND last_seen IS NULL AND name != ?", (text_fragment, name))
    existing_monitor = c.fetchone()
    
    if existing_monitor:
        return "Цей фрагмент вже раніше додано до моніторингу!"

    c.execute("SELECT * FROM monitors WHERE article_id = ? AND name != ?", (article_id, name))
    existing_article_id = c.fetchone()
    
    if existing_article_id:
        return "Цифровий ідентифікатор вже використовується!"

    c.execute("UPDATE monitors SET url = ?, text_fragment = ?, article_id = ? WHERE name = ?", (url, text_fragment, article_id, name))
    
    conn.commit()
    conn.close()
    
    return "Моніторинг оновлено!"

def get_monitors():
    conn = sqlite3.connect('news_aggregator.db')
    c = conn.cursor()
    
    c.execute("SELECT * FROM monitors")
    monitors = c.fetchall()
    
    conn.close()
    
    return monitors

def display_monitors():
    monitors = get_monitors()
    html_content = "<table border='1' style='border-collapse: collapse; width: 100%;'>"
    html_content += "<th>Текстовий фрагмент</th><th>Дата початку</th><th>Статус</th><th>Ідентифікатор статті</th></tr>"
    for monitor in monitors:
        if monitor[6] and monitor[6] !="Активний":
            status = f"<span style='color:red;'>Фрагмент перестав відображатися о {monitor[6]}</span>"
        else:
            status = "Активний"
        html_content += f"""
        <tr>
            <td>{monitor[3]}</td>
            <td>{monitor[5]}</td>
            <td>{status}</td>
            <td>{monitor[7]}</td>
        </tr>
        """
    html_content += "</table>"
    return html_content

def get_choices():
    monitors = get_monitors()
    return [monitor[1] for monitor in monitors] + ["Add new..."]

def add_or_update_monitor_interface(name, url, text_fragment, article_id):
    monitor_names = get_choices()
    if name in monitor_names:
        return update_monitor(name, url, text_fragment, article_id)
    else:
        return add_monitor(name, url, text_fragment, article_id)

def export_to_csv():
    monitors = get_monitors()
    with open('monitors_export.csv', 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['ID', 'Name', 'URL', 'Text Fragment', 'Last Seen', 'Start Date', 'Stop Date', 'Article ID']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for monitor in monitors:
            writer.writerow({
                'ID': monitor[0],
                'Name': monitor[1],
                'URL': monitor[2],
                'Text Fragment': monitor[3],
                'Last Seen': monitor[4] if monitor[4] else "Немає даних",
                'Start Date': monitor[5],
                'Stop Date': monitor[6] if monitor[6] else "Активний",
                'Article ID': monitor[7]
            })
    return "Експорт завершено!"

def import_from_csv(file):
    conn = sqlite3.connect('news_aggregator.db')
    c = conn.cursor()
    with open(file.name, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            stop_date = row.get('Stop Date', None)
            c.execute("SELECT * FROM monitors WHERE article_id = ?", (row['Article ID'],))
            existing_article_id = c.fetchone()
            if existing_article_id:
                continue
            c.execute("INSERT INTO monitors (name, url, text_fragment, last_seen, start_date, stop_date, article_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (row['Name'], row['URL'], row['Text Fragment'], row['Last Seen'], row['Start Date'], stop_date, row['Article ID']))
    conn.commit()
    conn.close()
    return "Імпорт завершено!"

def clear_database(confirm):
    if confirm == "Так":
        conn = sqlite3.connect('news_aggregator.db')
        c = conn.cursor()
        c.execute("DELETE FROM monitors")
        conn.commit()
        initialize_db()  # Переконатися, що таблиця буде створена знову
        conn.close()
        return "База даних очищена!"
    else:
        return "Очищення бази даних скасовано."

def delete_monitor(article_id):
    conn = sqlite3.connect('news_aggregator.db')
    c = conn.cursor()
    c.execute("DELETE FROM monitors WHERE article_id = ?", (article_id,))
    conn.commit()
    conn.close()
    return f"Моніторинг з ідентифікатором {article_id} видалено!"

# Ініціалізація бази даних
initialize_db()

# Головний інтерфейс Gradio
monitor_interface = gr.Interface(
fn=display_monitors,
inputs=[],
outputs=gr.HTML(label="Монітори")
)

add_monitor_interface = gr.Interface(
fn=add_or_update_monitor_interface,
inputs=[
gr.Dropdown(choices=get_choices(), label="Назва моніторингу"),
gr.Textbox(label="URL"),
gr.Textbox(label="Текстовий фрагмент"),
gr.Number(label="Ідентифікатор статті")
],
outputs="text"
)

export_interface = gr.Interface(
fn=export_to_csv,
inputs=[],
outputs="text"
)

import_interface = gr.Interface(
    fn=import_from_csv,
    inputs=[gr.File(label="Завантажте CSV файл")],
    outputs="text"
)

clear_db_interface = gr.Interface(
    fn=clear_database,
    inputs=[gr.Radio(choices=["Так", "Ні"], label="Ви впевнені, що хочете очистити базу даних?")],
    outputs="text"
)

delete_monitor_interface = gr.Interface(
    fn=delete_monitor,
    inputs=[gr.Number(label="Ідентифікатор статті для видалення")],
    outputs="text"
)

import threading

# Функція для автоматичного оновлення моніторингу
def auto_update_monitors(interval):
    while auto_update_flag:
        monitor_sites()
        time.sleep(interval * 60)

# Глобальна змінна для контролю автоматичного оновлення
auto_update_flag = False

def start_auto_update(interval):
    global auto_update_flag
    auto_update_flag = True
    threading.Thread(target=auto_update_monitors, args=(interval,), daemon=True).start()
    return "Автоматичне оновлення розпочато!"

def stop_auto_update():
    global auto_update_flag
    auto_update_flag = False
    return "Автоматичне оновлення зупинено!"

def toggle_auto_update(auto_update, interval):
    if auto_update:
        return start_auto_update(interval)
    else:
        return stop_auto_update()

# Інтерфейс для автоматичного оновлення моніторингу
auto_update_interface = gr.Interface(
    fn=toggle_auto_update,
    inputs=[
        gr.Checkbox(label="Оновлювати автоматично кожні..."),
        gr.Number(label="Інтервал оновлень (хвилин)", value=5)
    ],
    outputs="text"
)

gr.TabbedInterface(
    [monitor_interface, add_monitor_interface, export_interface, import_interface, clear_db_interface, delete_monitor_interface, auto_update_interface], 
    ["Монітори", "Додати/Оновити монітор", "Експорт даних", "Імпорт даних", "Очистити базу даних", "Видалити монітор", "Автоматичне оновлення"]
).launch(share=True)
