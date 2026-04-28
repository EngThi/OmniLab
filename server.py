import hashlib
import time
import asyncio
import base64
import os
import io
import json
import itertools
import re
import random
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
    print("⚠️ [System] GEMINI_API_KEY NOT FOUND!")
    DEMO_MODE = True
else:
    print(f"✅ [System] V15.10 Active (Yellow Dot). API Key detected: {api_key[:4]}...{api_key[-4:]}")

client = genai.Client(api_key=api_key) if api_key else None

# MODELOS 2026: PROTOCOLO GEMINI 3.1
MODEL_LIST = ["gemini-3.1-flash-lite-preview", "gemini-3.1-flash-preview", "gemini-3.1-pro-preview"]

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
                            await ws.send_json({"type": "status_update", "message": "SYS: REROUTING_VIA_DDG..."})
                            await asyncio.sleep(2)
                            img_data, _ = await capture_screenshot("duckduckgo", query)
                        await ws.send_json({"type": "browser_screenshot", "data": img_data})
                    except Exception as e:
                        print(f"❌ [Error] Research failed: {e}")
                        await ws.send_json({"type": "status_update", "message": f"ERROR: {str(e)[:100]}"})
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

async def type_human_like(page, selector, text, click_after=None):
    """Digita letra por letra com pausas, movimentos e clique forçado."""
    await page.wait_for_selector(selector, timeout=30000)
    await page.mouse.move(random.randint(100, 700), random.randint(100, 700))
    await page.click(selector)
    await asyncio.sleep(random.uniform(1.0, 2.0))
    for char in text:
        await page.keyboard.type(char, delay=random.randint(60, 200))
    await asyncio.sleep(random.uniform(2.0, 4.0)) 
    
    if click_after:
        try:
            btn = await page.wait_for_selector(click_after, timeout=10000)
            await btn.hover()
            await asyncio.sleep(random.uniform(0.5, 1.2))
            await btn.click(force=True)
            print(f"✅ [UI] Master force click on {click_after}")
        except:
            await page.keyboard.press("Enter")
    else:
        await page.keyboard.press("Enter")

async def capture_screenshot(engine: str, query: str):
    from playwright_stealth import Stealth
    import urllib.parse
    quoted = urllib.parse.quote(query)
    user_data_dir = os.path.expanduser("~/.playwright_data")
    
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
                user_data_dir, headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"], **stealth_params
            )
        else:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            browser_context = await browser.new_context(**stealth_params)
        
        try:
            page = browser_context.pages[0] if browser_context.pages else await browser_context.new_page()
            await Stealth().apply_stealth_async(page)
            
            # Aquecimento rápido
            await page.mouse.move(400, 400)
            await asyncio.sleep(random.uniform(1.0, 2.0))

            target_url = ""
            if engine == "google": target_url = f"https://www.google.com/search?q={quoted}&hl=pt-BR"
            elif engine == "perplexity": target_url = f"https://www.perplexity.ai/search?q={quoted}"
            elif engine == "gemini": target_url = "https://gemini.google.com/app"
            elif engine == "chatgpt": target_url = "https://chatgpt.com/"
            else: target_url = f"https://duckduckgo.com/html/?q={quoted}"
            
            print(f"🕵️‍♂️ [Stealth] Targeting {engine.upper()} (V15.10 Resilience)...")
            
            try:
                # Mudança estratégica: domcontentloaded é muito mais rápido que load
                await page.goto(target_url, wait_until="domcontentloaded", timeout=50000)
            except Exception as e:
                print(f"⚠️ [Nav] Timeout or error during load: {e}. Proceeding anyway...")

            # Verificação básica de Cloudflare
            try:
                content_lower = (await page.content()).lower()
                if "cloudflare" in content_lower or "challenge-page" in content_lower:
                    print("🛡️ [Cloudflare] Challenge detected. Bypass click...")
                    await page.mouse.click(640, 400)
                    await asyncio.sleep(6)
            except: pass

            if engine == "gemini":
                try:
                    gemini_send_btn = "button[aria-label*='Send'], .send-button-container button, div.send-button-container button"
                    input_selector = "div[contenteditable='true']"
                    await type_human_like(page, input_selector, query, click_after=gemini_send_btn)
                    await asyncio.sleep(25) 
                except Exception as e: print(f"⚠️ Gemini Error: {e}")
            
            elif engine == "chatgpt":
                try:
                    input_selector = "#prompt-textarea"
                    chatgpt_send_btn = "[data-testid='send-button']"
                    await type_human_like(page, input_selector, query, click_after=chatgpt_send_btn)
                    await asyncio.sleep(20) 
                except Exception as e: print(f"⚠️ ChatGPT Error: {e}")
            
            elif engine == "perplexity":
                await page.mouse.wheel(0, 500)
                await asyncio.sleep(12)
            
            else: await asyncio.sleep(5)
            
            content = await page.content()
            is_blocked = "detected unusual traffic" in content.lower() or "google.com/sorry" in page.url or "challenge-page" in content.lower()
            
            screenshot_bytes = await page.screenshot(type="jpeg", quality=75, full_page=True)
            return base64.b64encode(screenshot_bytes).decode('utf-8'), is_blocked
        finally:
            await browser_context.close()

async def _call_ai(image_bytes, history):
    if not client: return "API KEY ERROR"
    for m_id in MODEL_LIST:
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=m_id,
                contents=[types.Content(role="user", parts=[
                    types.Part.from_bytes(mime_type="image/jpeg", data=image_bytes),
                    types.Part.from_text(text=(f"CONTEXT: {history}\nTASK: Tactical analysis. Short plain text. Suggest search query in brackets: [search: term]."))
                ])]
            )
            return response.text
        except Exception: continue
    return "ANALYSIS_FAILED."

@app.post("/analyze")
async def analyze_frame(request: AnalyzeRequest):
    global cognitive_memory
    try:
        img_bytes = base64.b64decode(request.image)
        text = await _call_ai(img_bytes, " | ".join(cognitive_memory[-2:]))
        cognitive_memory.append(text)
        if len(cognitive_memory) > 5: cognitive_memory.pop(0)
    except Exception: return {"status": "error", "message": "IA_OFFLINE"}
    m = re.search(r'\[search:\s*(.*?)\]', text)
    query = m.group(1) if m else text[:30]
    return {"status": "success", "text": text, "suggested_query": query}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
