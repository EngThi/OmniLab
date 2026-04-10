import hashlib
import time
import asyncio
import base64
import os
import io
import json
import itertools
import subprocess
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

# MCP Imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

# ── CONFIGURAÇÃO DE DEMO / MOCKS ──
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

DEMO_RESPONSES = [
    "HAND DETECTED. INDEX FINGER EXTENDED — GESTURE: POINT. CONFIDENCE: 94%",
    "CLOSED FIST DETECTED — GESTURE: STOP. ACTIVATING NEURAL LOCK.",
    "OPEN PALM DETECTED — GESTURE: OPEN. SYSTEM STANDBY.",
    "TWO FINGERS EXTENDED — GESTURE: PEACE. HUD MODE: CREATIVE.",
]
_response_cycle = itertools.cycle(DEMO_RESPONSES)

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key and not DEMO_MODE else None
model_id = 'gemini-3.1-flash-lite-preview'

from playwright_stealth import Stealth

# ── OMNI-AGENT MCP BRIDGE (Sprint Jr 2h) ──
class McpAgentBridge:
    def __init__(self):
        self.session: ClientSession = None
        self.exit_stack = None
        self._active = False

    async def start(self):
        if self._active: return
        print("🚀 [MCP] Initializing Playwright MCP Server...")
        
        # Parâmetros para rodar o servidor oficial da Microsoft
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@playwright/mcp@latest"],
            env=os.environ.copy()
        )
        
        # Usamos um contexto assíncrono para manter a conexão stdio viva
        self.exit_stack = asyncio.ExitStack()
        read_stream, write_stack = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stack))
        
        # Inicializa o protocolo
        await self.session.initialize()
        self._active = True
        print("✅ [MCP] Agent Connected to Playwright Tools")

    async def list_tools(self):
        if not self._active: await self.start()
        tools = await self.session.list_tools()
        return tools

    async def call_tool(self, name: str, arguments: dict):
        if not self._active: await self.start()
        print(f"🛠️ [MCP] Executing: {name} with {arguments}")
        result = await self.session.call_tool(name, arguments)
        return result

    async def stop(self):
        if self.exit_stack:
            await self.exit_stack.aclose()
        self._active = False

mcp_bridge = McpAgentBridge()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Inicia o browser e o MCP Bridge
    asyncio.create_task(mcp_bridge.start())
    yield
    # Shutdown
    await mcp_bridge.stop()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Variável global para memória de curto prazo
last_analysis_result = "tecnologia e automação"
cognitive_memory = []

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
                if cmd == "analyze_and_search":
                    for v in list(vision_connections):
                        await v.send_json({"type": "command", "command": "analyze", "auto_search": True})
                else:
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
            for h in list(hud_connections):
                try: await h.send_json(data)
                except: hud_connections.discard(h)
            
            if data.get("type") == "action":
                for hud in list(hud_connections):
                    await handle_agent_action(data["action"], hud)
    except WebSocketDisconnect:
        vision_connections.discard(ws)

async def handle_agent_action(action: str, ws_target: WebSocket):
    global last_analysis_result
    print(f"🎬 [Action] Triggered: {action}")
    
    # ── INTEGRAÇÃO MCP REAL ──
    if action == "BROWSER_SEARCH_RECIPE":
        await ws_target.send_json({"type": "status_update", "message": "AGENT: STARTING_MCP_BROWSER"})
        try:
            # Chama a ferramenta de navegação do MCP
            res = await mcp_bridge.call_tool("playwright_navigate", {
                "url": "https://www.google.com/search?q=receitas+rapidas+homes"
            })
            await ws_target.send_json({"type": "status_update", "message": "AGENT: PAGE_LOADED"})
        except Exception as e:
            await ws_target.send_json({"type": "status_update", "message": f"AGENT_ERROR: {str(e)[:20]}"})

    elif action == "HOMES_EMERGENCY_STOP":
        await ws_target.send_json({"type": "status_update", "message": "EMERGENCY_STOP: KILLING_AGENT"})
        # Futura implementação: Parar tasks do MCP

# Buffer de Memória Cognitiva
@app.post("/analyze")
async def analyze_frame(request: AnalyzeRequest):
    global cognitive_memory, _response_cycle
    
    if DEMO_MODE:
        await asyncio.sleep(0.6)
        mock_text = next(_response_cycle)
        return {"status": "success", "text": mock_text, "cached": False, "demo": True}

    if not client: return {"error": "IA indisponível"}
    try:
        image_bytes = base64.b64decode(request.image)
        optimized = _resize_image(image_bytes)
    except:
        return {"error": "Formato de imagem inválido"}

    img_hash = hashlib.md5(optimized).hexdigest()
    cached = _cache_get(img_hash)
    if cached: return {"status": "success", "text": cached, "cached": True}

    history_context = " | ".join(cognitive_memory[-3:]) if cognitive_memory else "Nenhum dado anterior."
    
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_id,
            contents=[types.Content(role="user", parts=[
                types.Part.from_bytes(mime_type="image/jpeg", data=optimized),
                types.Part.from_text(text=f"Contexto anterior: {history_context}. Analise a imagem atual e descreva-a de forma tática (máximo 8 palavras).")
            ])]
        )
        
        analysis = response.text.strip()
        cognitive_memory.append(analysis)
        if len(cognitive_memory) > 5: cognitive_memory.pop(0)
        
        _cache_set(img_hash, analysis)
        return {"status": "success", "text": analysis, "cached": False}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
