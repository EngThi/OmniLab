import hashlib
import time
import asyncio
import base64
import os
import io
import json
import itertools
import re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types
from playwright.async_api import async_playwright
from contextlib import asynccontextmanager, AsyncExitStack

load_dotenv()

# ── FORCED DEMO MODE & KEY CHECK ──
api_key = os.getenv("GEMINI_API_KEY")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

if not api_key:
    print("⚠️ [System] GEMINI_API_KEY NOT FOUND! Check your .env file.")
    DEMO_MODE = True
else:
    print(f"✅ [System] V15 Active. API Key detected: {api_key[:4]}...{api_key[-4:]}")

client = genai.Client(api_key=api_key) if api_key else None

# MODELOS 2026: PROTOCOLO GEMINI 3.1
MODEL_LIST = [
    "gemini-3.1-flash-lite-preview", 
    "gemini-3.1-flash-preview", 
    "gemini-3.1-pro-preview"
]

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root(): return FileResponse("static/index.html")

cognitive_memory = []
hud_connections: set[WebSocket] = set()

class AnalyzeRequest(BaseModel):
    image: str

@app.websocket("/ws/hud")
async def websocket_hud(ws: WebSocket):
    global cognitive_memory
    await ws.accept()
    hud_connections.add(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "command":
                cmd = data.get("command")
                query = data.get("query")
                engine = data.get("engine", "google")
                if cmd == "analyze_and_search" and query:
                    await ws.send_json({"type": "status_update", "message": f"AGENT: RESEARCHING_{engine.upper()}"})
                    try:
                        img_data, is_blocked = await capture_screenshot(engine, query)
                        if is_blocked and engine == "google":
                            await ws.send_json({"type": "status_update", "message": "WARN: GOOGLE_BLOCK_DETECTED"})
                            await asyncio.sleep(2)
                            img_data, _ = await capture_screenshot("duckduckgo", query)
                        await ws.send_json({"type": "browser_screenshot", "data": img_data})
                    except Exception as e:
                        print(f"❌ [Error] Research failed: {e}")
                        await ws.send_json({"type": "status_update", "message": f"ERROR: {str(e)[:20]}"})
                elif cmd == "close_browser":
                    cognitive_memory = []
                    await ws.send_json({"type": "status_update", "message": "SYSTEM_CORE: MEMORY_PURGED"})
    except WebSocketDisconnect:
        hud_connections.discard(ws)

@app.websocket("/ws/vision")
async def websocket_vision(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            for h in list(hud_connections):
                try: await h.send_json(data)
                except: hud_connections.discard(h)
    except WebSocketDisconnect: pass

async def capture_screenshot(engine: str, query: str):
    from playwright_stealth import stealth_async
    import urllib.parse
    quoted = urllib.parse.quote(query)
    user_data_dir = os.path.expanduser("~/.playwright_data") # Usa o perfil transferido na raiz da home
    
    async with async_playwright() as p:
        stealth_params = {
            "user_agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            "locale": 'pt-BR',
            "timezone_id": 'America/Sao_Paulo',
            "geolocation": {'latitude': -23.5505, 'longitude': -46.6333},
            "permissions": ['geolocation'],
            "viewport": {'width': 1280, 'height': 800}
        }

        if engine in ["google", "perplexity", "gemini", "chatgpt"]:
            browser_context = await p.chromium.launch_persistent_context(
                user_data_dir,
                headless=True,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
                **stealth_params
            )
        else:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            browser_context = await browser.new_context(**stealth_params)
        
        try:
            page = browser_context.pages[0] if browser_context.pages else await browser_context.new_page()
            await stealth_async(page)
            
            target_url = ""
            if engine == "google": target_url = f"https://www.google.com/search?q={quoted}&hl=pt-BR"
            elif engine == "perplexity": target_url = f"https://www.perplexity.ai/search?q={quoted}"
            elif engine == "gemini": target_url = "https://gemini.google.com/app"
            elif engine == "chatgpt": target_url = "https://chatgpt.com/"
            else: target_url = f"https://duckduckgo.com/html/?q={quoted}"
            
            print(f"🕵️‍♂️ [Stealth] Targeting {engine.upper()} as SP Resident (Gemini 3.1 Intel)...")
            await page.goto(target_url, wait_until="load", timeout=90000)
            
            if engine == "gemini":
                try:
                    input_selector = "div[contenteditable='true']"
                    await page.wait_for_selector(input_selector, timeout=15000)
                    await page.fill(input_selector, query)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(12) 
                except: pass
            elif engine == "chatgpt":
                try:
                    input_selector = "textarea#prompt-textarea"
                    await page.wait_for_selector(input_selector, timeout=15000)
                    await page.fill(input_selector, query)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(12)
                except: pass
            elif engine == "perplexity":
                await page.mouse.move(100, 100)
                await asyncio.sleep(8)
            else:
                await asyncio.sleep(5)
            
            content = await page.content()
            is_blocked = "detected unusual traffic" in content.lower() or "google.com/sorry" in page.url or "challenge-page" in content.lower()
            screenshot_bytes = await page.screenshot(type="jpeg", quality=75, full_page=True)
            return base64.b64encode(screenshot_bytes).decode('utf-8'), is_blocked
        finally:
            await browser_context.close()

async def _call_ai(image_bytes, history):
    if not client:
        return "ERROR: NO_API_KEY"
        
    for m_id in MODEL_LIST:
        try:
            print(f"🧠 [AI] Initiating neural analysis with {m_id}...")
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=m_id,
                contents=[types.Content(role="user", parts=[
                    types.Part.from_bytes(mime_type="image/jpeg", data=image_bytes),
                    types.Part.from_text(text=(
                        f"CONTEXT: {history}\n"
                        "TASK: Tactical analysis. Short plain text. Suggest search query in brackets: [search: term]."
                    ))
                ])]
            )
            print(f"✅ [AI] Analysis successful via {m_id}")
            return response.text
        except Exception as e:
            print(f"⚠️ [AI] Model {m_id} failed: {e}")
            continue
    return "ANALYSIS_FAILED."

@app.post("/analyze")
async def analyze_frame(request: AnalyzeRequest):
    global cognitive_memory
    try:
        img_bytes = base64.b64decode(request.image)
        text = await _call_ai(img_bytes, " | ".join(cognitive_memory[-2:]))
        cognitive_memory.append(text)
        if len(cognitive_memory) > 5: cognitive_memory.pop(0)
    except Exception as e: 
        print(f"❌ [Analyze Post] Error: {e}")
        return {"status": "error", "message": str(e)}
    
    m = re.search(r'\[search:\s*(.*?)\]', text)
    query = m.group(1) if m else text[:30]
    return {"status": "success", "text": text, "suggested_query": query}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
