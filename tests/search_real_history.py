import sqlite3
import os
from datetime import datetime, timedelta

def search_real_history():
    history_path = "/home/engthi/.gemini/antigravity-browser-profile/Default/History"
    if not os.path.exists(history_path):
        print(f"❌ History file not found: {history_path}")
        return

    epoch_start = datetime(1601, 1, 1)
    target_time = datetime(2026, 4, 20, 20, 0, 0)
    target_timestamp = int((target_time - epoch_start).total_seconds() * 1000000)

    try:
        temp_path = "/tmp/history_real"
        import shutil
        shutil.copy2(history_path, temp_path)
        
        conn = sqlite3.connect(temp_path)
        cursor = conn.cursor()
        
        query = """
        SELECT url, title, last_visit_time 
        FROM urls 
        WHERE last_visit_time >= ?
        ORDER BY last_visit_time DESC
        """
        
        cursor.execute(query, (target_timestamp,))
        rows = cursor.fetchall()
        
        if not rows:
            print("📭 No URLs found in REAL history after 8 PM yesterday.")
        else:
            print("--- REAL HISTORY FROM ANTIGRAVITY PROFILE ---")
            for url, title, timestamp in rows:
                visit_time = epoch_start + timedelta(microseconds=timestamp)
                print(f"🕒 {visit_time} | {title} | {url}")
            
        conn.close()
        os.remove(temp_path)
        
    except Exception as e:
        print(f"❌ Error reading history: {e}")

if __name__ == "__main__":
    search_real_history()
