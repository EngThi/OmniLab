import hashlib
import time
import asyncio
import base64
import os
import io
import json
import itertools
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types
from playwright.async_api import async_playwright
from contextlib import asynccontextmanager

load_dotenv()

# ── CONFIGURAÇÃO DE DEMO / MOCKS ──
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

DEMO_RESPONSES = [
    "TACTICAL ANALYSIS: SUBJECT IDENTIFIED. NEURAL LINK STABLE.",
    "GESTURE RECOGNITION ACTIVE: PINCH DETECTED. LOADING DEEP SCAN.",
    "ENVIRONMENT SCAN COMPLETE: NO ANOMALIES DETECTED in THE VISUAL FIELD.",
    "SYSTEM STATUS: ALL CORE MODULES OPERATING WITHIN NOMINAL PARAMETERS.",
    "THREAT ASSESSMENT: ZERO EXTERNAL RISKS DETECTED. STANDBY MODE.",
]
_response_cycle = itertools.cycle(DEMO_RESPONSES)

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key and not DEMO_MODE else None
model_id = 'gemini-3.1-flash-lite-preview'

from playwright_stealth import Stealth

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Inicia o browser para aquecer
    asyncio.create_task(browser_agent.start())
    yield
    # Shutdown: Para o browser
    await browser_agent.stop()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Variável global para memória de curto prazo
last_analysis_result = "tecnologia e automação"

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
        # MUDANÇA TÁTICA: headless=False para você ver o browser abrindo
        self.browser = await self.playwright.chromium.launch(headless=False) 
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        self.page = await self.context.new_page()
        await Stealth().apply_stealth_async(self.page)
        self.active = True
        print("🌐 [OmniBrowser] Agent Started and Visible")

    async def navigate(self, url: str):
        if not self.active: await self.start()
        try:
            await self.page.goto(url, wait_until="networkidle", timeout=15000)
            return await self.page.title()
        except:
            return "Navigation Timeout"

    async def stop(self):
        try:
            if self.browser: await self.browser.close()
            if self.playwright: await self.playwright.stop()
        except: pass
        self.active = False
        print("🛑 [OmniBrowser] Agent Stopped")

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

class AnalyzeRequest(BaseModel):
    image: str # base64 string

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
                cmd = data.get("command")
                # Novos comandos de voz via HUD
                if cmd == "close_browser":
                    await browser_agent.stop()
                elif cmd == "analyze_and_search":
                    # Este comando pede para a visão analisar e depois pesquisar
                    # Reencaminhamos para a visão com uma flag de busca
                    for v in list(vision_connections):
                        await v.send_json({"type": "command", "command": "analyze", "auto_search": True})
                else:
                    # Comandos padrão (analyze, etc)
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
            
            # REMOVIDO: Gatilhos automáticos por Thumbs Up / Fist para evitar acidentes
            # O sistema agora só age por comando de voz explícito
    except WebSocketDisconnect:
        vision_connections.discard(ws)

async def handle_agent_action(action: str, ws_target: WebSocket):
    global last_analysis_result
    print(f"🎬 [Action] Triggered: {action}")
    
    if action == "HOMES_EXECUTE_TASK":
        # Gesto: Thumbs Up -> Pesquisa contextual baseada no que a IA viu
        search_query = last_analysis_result.replace(" ", "+")
        url = f"https://www.google.com/search?q={search_query}"
        await ws_target.send_json({"type": "status_update", "message": f"AGENT_SEARCHING: {last_analysis_result}"})
        title = await browser_agent.navigate(url)
        print(f"🔍 [Agent] Found: {title}")
        
    elif action == "HOMES_EMERGENCY_STOP":
        # Gesto: Fist -> Fecha tudo
        await ws_target.send_json({"type": "status_update", "message": "EMERGENCY_STOP: CLOSING_BROWSER"})
        await browser_agent.stop()
    
    elif action == "BROWSER_SEARCH_RECIPE":
        title = await browser_agent.navigate("https://www.google.com/search?q=receitas+rapidas+homes")
        await ws_target.send_json({"type": "status_update", "message": f"SEARCHING: {title}"})

# Buffer de Memória Cognitiva (Contexto Jarvis)
cognitive_memory = []

@app.post("/analyze")
async def analyze_frame(request: AnalyzeRequest):
    global cognitive_memory, _response_cycle, last_analysis_result
    
    # ── LÓGICA DE MOCK / DEMO ──
    if DEMO_MODE:
        await asyncio.sleep(0.6) # Simulate thinking
        mock_text = next(_response_cycle)
        last_analysis_result = mock_text # Update memory for browser search
        return {
            "status": "success", 
            "text": mock_text, 
            "cached": False, 
            "demo": True
        }

    if not client: return {"error": "IA indisponível"}
    try:
        image_bytes = base64.b64decode(request.image)
        optimized = _resize_image(image_bytes)
    except:
        return {"error": "Formato de imagem inválido"}

    img_hash = hashlib.md5(optimized).hexdigest()
    cached = _cache_get(img_hash)
    if cached: return {"status": "success", "text": cached, "cached": True}

    # Construir o contexto histórico para a IA
    history_context = " | ".join(cognitive_memory[-3:]) if cognitive_memory else "Nenhum dado anterior."
    
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_id,
            contents=[types.Content(role="user", parts=[
                types.Part.from_bytes(mime_type="image/jpeg", data=optimized),
                types.Part.from_text(text=f"Contexto anterior: {history_context}. Analise a imagem atual e descreva-a de forma tática (máximo 8 palavras). Se for o mesmo objeto de antes, confirme a presença.")
            ])]
        )
        
        analysis = response.text.strip()
        # Atualiza memória
        cognitive_memory.append(analysis)
        if len(cognitive_memory) > 5: cognitive_memory.pop(0) # Mantém as últimas 5
        
        _cache_set(img_hash, analysis)
        return {"status": "success", "text": analysis, "cached": False}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
