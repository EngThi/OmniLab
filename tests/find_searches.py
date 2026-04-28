import sqlite3
import os
from datetime import datetime, timedelta

def find_search_terms():
    history_path = "/home/engthi/.gemini/antigravity-browser-profile/Default/History"
    if not os.path.exists(history_path):
        return

    epoch_start = datetime(1601, 1, 1)
    target_time = datetime(2026, 4, 20, 20, 0, 0)
    target_timestamp = int((target_time - epoch_start).total_seconds() * 1000000)

    try:
        temp_path = "/tmp/h_search"
        import shutil
        shutil.copy2(history_path, temp_path)
        
        conn = sqlite3.connect(temp_path)
        cursor = conn.cursor()
        
        # Buscar termos de busca e URLs relacionadas
        query = """
        SELECT term, url, last_visit_time
        FROM keyword_search_terms
        JOIN urls ON keyword_search_terms.url_id = urls.id
        WHERE last_visit_time >= ?
        ORDER BY last_visit_time DESC
        """
        cursor.execute(query, (target_timestamp,))
        rows = cursor.fetchall()
        
        print("--- SEARCH TERMS FROM YESTERDAY NIGHT ---")
        for term, url, timestamp in rows:
            visit_time = epoch_start + timedelta(microseconds=timestamp)
            print(f"🕒 {visit_time} | Term: {term} | URL: {url}")
            
        conn.close()
        os.remove(temp_path)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_search_terms()
