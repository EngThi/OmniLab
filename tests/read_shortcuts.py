import sqlite3
import os

def read_shortcuts():
    path = ".playwright_data/Default/Shortcuts"
    if not os.path.exists(path):
        print("❌ Shortcuts file not found.")
        return

    temp_path = "/tmp/s_temp"
    import shutil
    shutil.copy2(path, temp_path)
    
    conn = sqlite3.connect(temp_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT text, fill_into_edit, url FROM shortcuts ORDER BY last_access_time DESC LIMIT 20")
        rows = cursor.fetchall()
        print("--- CHROMIUM SHORTCUTS (SEARCH QUERIES) ---")
        for text, fill, url in rows:
            print(f"Query: {text} | URL: {url}")
    except Exception as e:
        print(f"Error: {e}")
    
    conn.close()
    os.remove(temp_path)

if __name__ == "__main__":
    read_shortcuts()
