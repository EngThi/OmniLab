import hashlib
import time
import asyncio
import base64
import os
import io
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None
model_id = 'gemini-2.0-flash'

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── BROWSER AGENT BRIDGE ──
class OmniBrowser:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.active = False

    async def start(self):
        if self.active: return
        self.playwright = await async_playwright().start()
        # Usamos user_data_dir para persistir sessão (cookies, login)
        self.browser = await self.playwright.chromium.launch(headless=True) # Mudar para False se quiser ver
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        self.page = await self.context.new_page()
        await stealth_async(self.page)
        self.active = True
        print("🌐 [OmniBrowser] Agent Started Successfully")

    async def navigate(self, url: str):
        if not self.active: await self.start()
        await self.page.goto(url, wait_until="networkidle")
        return await self.page.title()

    async def get_screenshot(self):
        if not self.page: return None
        return await self.page.screenshot(type="jpeg", quality=60)

    async def stop(self):
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()
        self.active = False

browser_agent = OmniBrowser()

# Conexões
hud_connections: set[WebSocket] = set()
vision_connections: set[WebSocket] = set()

# Cache
_cache: dict[str, tuple[str, float]] = {}
CACHE_TTL = 30 

def _cache_get(key: str) -> str | None:
    if key in _cache:
        val, ts = _cache[key]
        if time.time() - ts < CACHE_TTL: return val
        del _cache[key]
    return None

def _cache_set(key: str, val: str):
    if len(_cache) > 200:
        oldest = min(_cache, key=lambda k: _cache[k][1])
        del _cache[oldest]
    _cache[key] = (val, time.time())

def _resize_image(data: bytes, max_size: int = 512) -> bytes:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70, optimize=True)
    return buf.getvalue()

@app.get("/")
async def get():
    return FileResponse("static/index.html")

@app.websocket("/ws/hud")
async def websocket_hud(ws: WebSocket):
    await ws.accept()
    hud_connections.add(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "command":
                for v in list(vision_connections):
                    try: await v.send_json(data)
                    except: vision_connections.discard(v)
    except WebSocketDisconnect:
        hud_connections.discard(ws)

@app.websocket("/ws/vision")
async def websocket_vision(ws: WebSocket):
    await ws.accept()
    vision_connections.add(ws)
    try:
        while True:
            data = await ws.receive_json()
            # Broadcast para o HUD
            for h in list(hud_connections):
                try: await h.send_json(data)
                except: hud_connections.discard(h)
            
            # ── LÓGICA DE AÇÃO DISPARADA POR GESTO ──
            if data.get("type") == "action":
                await handle_agent_action(data["action"], h)
    except WebSocketDisconnect:
        vision_connections.discard(ws)

async def handle_agent_action(action: str, ws_target: WebSocket):
    print(f"🎬 [Action] Triggered: {action}")
    if action == "BROWSER_SEARCH_RECIPE":
        title = await browser_agent.navigate("https://www.google.com/search?q=receitas+rapidas+homes")
        await ws_target.send_json({"type": "status_update", "message": f"SEARCHING: {title}"})
    elif action == "HOMES_SYNC":
        # Gatilho para o seu HOMES-Engine
        pass

@app.post("/analyze")
async def analyze_frame(request: any):
    if not client: return {"error": "IA indisponível"}
    image_bytes = base64.b64decode(request.image)
    optimized = _resize_image(image_bytes)
    img_hash = hashlib.md5(optimized).hexdigest()
    
    cached = _cache_get(img_hash)
    if cached: return {"status": "success", "text": cached, "cached": True}

    response = await asyncio.to_thread(
        client.models.generate_content,
        model=model_id,
        contents=[types.Content(role="user", parts=[
            types.Part.from_bytes(mime_type="image/jpeg", data=optimized),
            types.Part.from_text(text="Descreva a imagem de forma técnica e curta.")
        ])]
    )
    _cache_set(img_hash, response.text)
    return {"status": "success", "text": response.text, "cached": False}

@app.on_event("startup")
async def startup_event():
    # Inicia o browser no startup para aquecer
    asyncio.create_task(browser_agent.start())

@app.on_event("shutdown")
async def shutdown_event():
    await browser_agent.stop()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
