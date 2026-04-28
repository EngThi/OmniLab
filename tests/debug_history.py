import asyncio
import os
import sqlite3
from datetime import datetime, timedelta

def find_all_perplexity_urls():
    history_path = ".playwright_data/Default/History"
    if not os.path.exists(history_path):
        return

    epoch_start = datetime(1601, 1, 1)
    temp_path = "/tmp/h_temp"
    import shutil
    shutil.copy2(history_path, temp_path)
    
    conn = sqlite3.connect(temp_path)
    cursor = conn.cursor()
    
    # Buscar todas as URLs do Perplexity
    query = "SELECT url, title, last_visit_time FROM urls WHERE url LIKE '%perplexity.ai/search/%' ORDER BY last_visit_time DESC"
    cursor.execute(query)
    rows = cursor.fetchall()
    
    print("--- PERPLEXITY CHATS FOUND ---")
    for url, title, timestamp in rows:
        visit_time = epoch_start + timedelta(microseconds=timestamp)
        print(f"🕒 {visit_time} | {title} | {url}")
    
    conn.close()
    os.remove(temp_path)

if __name__ == "__main__":
    find_all_perplexity_urls()
