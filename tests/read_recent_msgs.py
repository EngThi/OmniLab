import json
import os

def read_recent_messages():
    path = "/home/engthi/.gemini/tmp/omnilab/chats/session-2026-04-18T14-11-96a611f9.json"
    if not os.path.exists(path):
        print("❌ Session file not found.")
        return

    with open(path, 'r') as f:
        data = json.load(f)
        messages = data.get("messages", [])
        print(f"Total messages: {len(messages)}")
        for msg in messages[-5:]:
            role = msg.get("type", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                text = " ".join([c.get("text", "") for c in content if "text" in c])
            else:
                text = str(content)
            print(f"--- {role.upper()} ---")
            print(text[:500] + "..." if len(text) > 500 else text)

if __name__ == "__main__":
    read_recent_messages()
