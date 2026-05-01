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
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from google import genai
from google.genai import types
from playwright.async_api import async_playwright
from contextlib import asynccontextmanager, AsyncExitStack

load_dotenv()

# ── FORCED DEMO MODE & KEY CHECK ──
api_key = os.getenv("GEMINI_API_KEY")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
DEMO_FALLBACK = os.getenv("DEMO_FALLBACK", "true").lower() == "true"
COOKIE_FILE = os.path.expanduser(os.getenv("COOKIE_FILE", "~/arq.json"))
COOKIE_FILE_CANDIDATES = [
    COOKIE_FILE,
    os.path.expanduser("~/arq.json"),
    os.path.expanduser("~/cookiesFI.json"),
    os.path.expanduser("~/cookies.json"),
]

if not api_key:
    print("⚠️ [System] GEMINI_API_KEY NOT FOUND!")
    DEMO_MODE = True
else:
    print(f"✅ [System] V15.12 Active (Purple Dot). API Key detected: {api_key[:4]}...{api_key[-4:]}")

client = genai.Client(api_key=api_key) if api_key else None

# MODELOS 2026: PROTOCOLO GEMINI 3.1
MODEL_LIST = ["gemini-3.1-flash-lite-preview", "gemini-3.1-flash-preview", "gemini-3.1-pro-preview"]
BOT_CHECK_PATTERNS = [
    "detected unusual traffic",
    "google.com/sorry",
    "challenge-page",
    "checking if the site connection is secure",
    "verify you are human",
    "cf-challenge",
    "cf-turnstile",
    "cloudflare",
    "captcha",
]

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root(): return FileResponse("static/index.html")

@app.head("/")
async def root_head(): return Response(status_code=200)

cognitive_memory = []
hud_connections: set[WebSocket] = set()

class AnalyzeRequest(BaseModel):
    image: str

async def send_ws_json(ws: WebSocket, payload: dict) -> bool:
    try:
        await ws.send_json(payload)
        return True
    except (WebSocketDisconnect, RuntimeError):
        return False

def page_has_bot_check(content: str, url: str) -> bool:
    haystack = f"{url}\n{content}".lower()
    return any(pattern in haystack for pattern in BOT_CHECK_PATTERNS)

def create_demo_screenshot(query: str, engine: str, reason: str = "DEMO_FALLBACK") -> str:
    width, height = 1280, 800
    image = Image.new("RGB", (width, height), "#02070a")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    for y in range(0, height, 40):
        color = (0, 45 + (y % 80), 50)
        draw.line((0, y, width, y), fill=color)
    for x in range(0, width, 64):
        draw.line((x, 0, x, height), fill=(0, 24, 28))

    draw.rectangle((70, 70, width - 70, height - 70), outline="#00f2ff", width=2)
    draw.rectangle((90, 110, width - 90, 180), outline="#00ffaa", width=1)
    draw.text((110, 130), "OMNILAB DEMO INTEL STREAM", fill="#ffffff", font=font)
    draw.text((110, 158), f"ENGINE: {engine.upper()} // STATUS: {reason}", fill="#00ffaa", font=font)

    lines = [
        f"QUERY: {query}",
        "",
        "Live third-party automation was paused because the target required human verification.",
        "This demo fallback lets reviewers validate the OmniLab HUD, WebSocket flow, browser panel,",
        "voice/gesture controls, and volatile memory behavior without cookies or CAPTCHA bypass.",
        "",
        "Recommended production path: use official search/provider APIs or require an explicit user",
        "session for sites that allow authenticated automation under their terms.",
    ]
    y = 235
    for line in lines:
        draw.text((110, y), line, fill="#00f2ff" if line else "#ffffff", font=font)
        y += 34

    draw.rectangle((110, height - 155, width - 110, height - 110), fill="#071418", outline="#00ffaa")
    draw.text((130, height - 142), "REVIEW MODE: PASSABLE WITHOUT COOKIES // NO CAPTCHA SOLVING USED", fill="#00ffaa", font=font)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def load_cookie_file():
    cookie_file = next((p for p in COOKIE_FILE_CANDIDATES if os.path.exists(p) and os.path.getsize(p) > 0), None)
    if not cookie_file:
        return []
    try:
        with open(cookie_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"⚠️ [Cookies] Could not read cookie file: {e}")
        return []

    raw_cookies = data.get("cookies") if isinstance(data, dict) else data
    if not isinstance(raw_cookies, list):
        print("⚠️ [Cookies] Unsupported cookie file format.")
        return []

    cookies = []
    for cookie in raw_cookies:
        if not isinstance(cookie, dict) or not cookie.get("name") or not cookie.get("value"):
            continue
        normalized = {k: v for k, v in cookie.items() if k in {
            "name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite", "url"
        }}
        if not normalized.get("domain") and not normalized.get("url"):
            continue
        normalized.setdefault("path", "/")
        if normalized.get("sameSite") not in {"Strict", "Lax", "None"}:
            normalized.pop("sameSite", None)
        cookies.append(normalized)
    return cookies

async def apply_user_cookies(browser_context):
    cookies = load_cookie_file()
    if not cookies:
        return
    try:
        await browser_context.add_cookies(cookies)
        domains = sorted({c.get("domain") or c.get("url", "") for c in cookies})
        print(f"✅ [Cookies] Loaded {len(cookies)} cookies for {len(domains)} domains.")
    except Exception as e:
        print(f"⚠️ [Cookies] Could not apply cookies: {e}")

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
                    if not await send_ws_json(ws, {"type": "status_update", "message": f"AGENT: RESEARCHING_{engine.upper()}"}):
                        break
                    try:
                        if DEMO_MODE:
                            img_data, is_blocked = create_demo_screenshot(query, engine, "DEMO_MODE"), False
                        else:
                            img_data, is_blocked = await capture_screenshot(engine, query)
                        if is_blocked and engine == "google":
                            if not await send_ws_json(ws, {"type": "status_update", "message": "WARN: GOOGLE_BLOCK_DETECTED"}):
                                break
                            if not await send_ws_json(ws, {"type": "status_update", "message": "SYS: REROUTING_VIA_GEMINI..."}):
                                break
                            await asyncio.sleep(2)
                            img_data, _ = await capture_screenshot("gemini", query)
                            if _ and DEMO_FALLBACK:
                                if not await send_ws_json(ws, {"type": "status_update", "message": "SYS: DEMO_FALLBACK_ACTIVE"}):
                                    break
                                img_data = create_demo_screenshot(query, "gemini", "VERIFICATION_REQUIRED")
                        elif is_blocked:
                            if not await send_ws_json(ws, {"type": "status_update", "message": "WARN: VERIFICATION_REQUIRED"}):
                                break
                            if DEMO_FALLBACK:
                                if not await send_ws_json(ws, {"type": "status_update", "message": "SYS: DEMO_FALLBACK_ACTIVE"}):
                                    break
                                img_data = create_demo_screenshot(query, engine, "VERIFICATION_REQUIRED")
                        if not await send_ws_json(ws, {"type": "browser_screenshot", "data": img_data}):
                            break
                    except Exception as e:
                        print(f"❌ [Error] Research failed: {e}")
                        if not await send_ws_json(ws, {"type": "status_update", "message": f"ERROR: {str(e)[:100]}"}):
                            break
                elif cmd == "close_browser":
                    cognitive_memory = []
                    if not await send_ws_json(ws, {"type": "status_update", "message": "SYSTEM_CORE: MEMORY_PURGED"}):
                        break
    except WebSocketDisconnect:
        hud_connections.discard(ws)
    finally:
        hud_connections.discard(ws)

@app.websocket("/ws/vision")
async def websocket_vision(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            for h in list(hud_connections):
                if not await send_ws_json(h, data):
                    hud_connections.discard(h)
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
    
    # Configuração de Proxy (Webshare)
    proxy_config = {
        "server": "http://31.59.20.176:6754",
        "username": "pmlsrcds",
        "password": "u6rstatz1o8x"
    }

    async with async_playwright() as p:
        stealth_params = {
            "user_agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            "locale": 'pt-BR',
            "timezone_id": 'America/Sao_Paulo',
            "geolocation": {'latitude': -23.5505, 'longitude': -46.6333},
            "permissions": ['geolocation'],
            "viewport": {'width': 1280, 'height': 800},
            "proxy": proxy_config
        }

        chromium_args = [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--ignore-certificate-errors",
        ]

        print(f"🚀 [Browser] Starting {engine.upper()} instance...")
        try:
            if engine in ["google", "perplexity", "gemini", "chatgpt"]:
                print(f"📦 [Browser] Launching Persistent Context for {engine}...")
                browser_context = await p.chromium.launch_persistent_context(
                    user_data_dir, headless=True, args=chromium_args, **stealth_params
                )
            else:
                print(f"📦 [Browser] Launching Standard Context for {engine}...")
                browser = await p.chromium.launch(headless=True, args=chromium_args)
                browser_context = await browser.new_context(**stealth_params)
        except Exception as e:
            print(f"❌ [Browser] Launch FAILED: {e}")
            raise
        
        print(f"✅ [Browser] Context ready. Injecting session...")
        try:
            page = browser_context.pages[0] if browser_context.pages else await browser_context.new_page()
            await apply_user_cookies(browser_context)
            await Stealth().apply_stealth_async(page)
            
            # Aquecimento rápido
            print(f"🔥 [Browser] Warming up mouse/stealth...")
            await page.mouse.move(400, 400)
            await asyncio.sleep(random.uniform(1.0, 2.0))

            target_url = ""
            if engine == "google": target_url = f"https://www.google.com/search?q={quoted}&hl=pt-BR"
            elif engine == "perplexity": target_url = f"https://www.perplexity.ai/search?q={quoted}"
            elif engine == "gemini": target_url = "https://gemini.google.com/app"
            elif engine == "chatgpt": target_url = "https://chatgpt.com/"
            else: target_url = f"https://duckduckgo.com/html/?q={quoted}"
            
            print(f"🔎 [Browser] Navigating to {target_url}...")
            
            try:
                # 60s timeout para proxies lentos
                await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                print(f"📸 [Browser] Navigation finished. Capturing...")
            except Exception as e:
                print(f"⚠️ [Nav] Timeout or error: {e}. Attempting capture anyway...")

            try:
                if page_has_bot_check(await page.content(), page.url):
                    print(f"⚠️ [Verification] Bot check detected on {engine.upper()}; stopping automation.")
                    screenshot_bytes = await page.screenshot(type="jpeg", quality=75, full_page=True)
                    return base64.b64encode(screenshot_bytes).decode('utf-8'), True
            except Exception as e:
                print(f"⚠️ [Verification] Detection failed: {e}")

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
            is_blocked = page_has_bot_check(content, page.url)
            
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
