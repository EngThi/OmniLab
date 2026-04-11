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
from contextlib import asynccontextmanager, AsyncExitStack

# MCP Imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

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

# ── OMNI-AGENT MCP BRIDGE ──
class McpAgentBridge:
    def __init__(self):
        self.session: ClientSession = None
        self._active = False
        self._task = None

    async def _run_engine(self):
        """Tarefa de fundo que mantém a conexão MCP viva."""
        print("🚀 [MCP] Initializing Playwright MCP Server (HEADED MODE)...")
        env = os.environ.copy()
        env["HEADLESS"] = "false"
        
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@playwright/mcp@latest"],
            env=env
        )

        async with AsyncExitStack() as stack:
            try:
                print("⏳ [MCP] Connecting to stdio...")
                read_stream, write_stream = await stack.enter_async_context(stdio_client(server_params))
                print("⏳ [MCP] Initializing ClientSession...")
                self.session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
                await self.session.initialize()
                
                # Listar ferramentas para depuração
                tools = await self.session.list_tools()
                print(f"🛠️ [MCP] Available tools: {[t.name for t in tools.tools]}")
                
                self._active = True
                print("✅ [MCP] Agent Connected and Ready")
                
                # Mantém a tarefa viva até ser cancelada
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                print("🛑 [MCP] Shutdown Signal Received")
            except Exception as e:
                print(f"❌ [MCP] Engine Error: {e}")
            finally:
                self._active = False
                self.session = None
                print("👋 [MCP] Agent Disconnected")

    async def start(self):
        if self._active: return
        self._task = asyncio.create_task(self._run_engine())
        # Espera inicialização básica
        for _ in range(10):
            if self._active: break
            await asyncio.sleep(0.5)

    async def call_tool(self, name: str, arguments: dict):
        if not self._active or not self.session: 
            await self.start()
        print(f"🛠️ [MCP] Executing: {name}")
        return await self.session.call_tool(name, arguments)

    async def stop(self):
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        self._active = False

mcp_bridge = McpAgentBridge()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Inicia o MCP Bridge
    await mcp_bridge.start()
    yield
    # Shutdown
    await mcp_bridge.stop()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Memória HOMES
cognitive_memory = []
last_analysis_result = "technology and automation"

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
                if cmd == "close_browser":
                    await mcp_bridge.stop()
                elif cmd == "analyze_and_search":
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
    
    if action == "HOMES_SEARCH_BROWSER":
        await ws_target.send_json({"type": "status_update", "message": "AGENT: STARTING_BROWSER"})
        try:
            res = await mcp_bridge.call_tool("browser_navigate", {
                "url": f"https://www.google.com/search?q={last_analysis_result.replace(' ', '+')}"
            })
            await ws_target.send_json({"type": "status_update", "message": "AGENT: SEARCH_COMPLETE"})
        except Exception as e:
            await ws_target.send_json({"type": "status_update", "message": f"AGENT_ERROR: {str(e)[:20]}"})

    elif action == "HOMES_EMERGENCY_STOP":
        await ws_target.send_json({"type": "status_update", "message": "EMERGENCY_STOP: KILLING_AGENT"})
        await mcp_bridge.stop()

@app.post("/analyze")
async def analyze_frame(request: AnalyzeRequest):
    global cognitive_memory, _response_cycle, last_analysis_result
    
    if DEMO_MODE:
        await asyncio.sleep(0.6)
        mock_text = next(_response_cycle)
        last_analysis_result = mock_text
        return {"status": "success", "text": mock_text, "cached": False, "demo": True}

    if not client: return {"error": "IA indisponível"}
    try:
        image_bytes = base64.b64decode(request.image)
        optimized = _resize_image(image_bytes)
        img_hash = hashlib.md5(optimized).hexdigest()
        
        cached = _cache_get(img_hash)
        if cached: return {"status": "success", "text": cached, "cached": True}

        history_context = " | ".join(cognitive_memory[-3:]) if cognitive_memory else "None"
        
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_id,
            contents=[types.Content(role="user", parts=[
                types.Part.from_bytes(mime_type="image/jpeg", data=optimized),
                types.Part.from_text(text=f"Past context: {history_context}. Analyze image and describe in max 8 words for a HUD report.")
            ])]
        )
        
        analysis = response.text.strip()
        cognitive_memory.append(analysis)
        if len(cognitive_memory) > 5: cognitive_memory.pop(0)
        last_analysis_result = analysis
        
        _cache_set(img_hash, analysis)
        return {"status": "success", "text": analysis, "cached": False}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/ingest/gesture")
async def ingest_gesture(data: dict):
    disconnected = set()
    for connection in list(hud_connections):
        try: await connection.send_json(data)
        except: disconnected.add(connection)
    for conn in disconnected: hud_connections.discard(conn)
    return {"status": "sent", "active_connections": len(hud_connections)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
