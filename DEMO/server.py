import hashlib
import time
import asyncio
import base64
import os
import io
import json
import itertools
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
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

# ── DEMO MODE ──
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
DEMO_RESPONSES = [
    "TACTICAL ANALYSIS: SUBJECT IDENTIFIED. NEURAL LINK STABLE.",
    "GESTURE RECOGNITION ACTIVE: PINCH DETECTED. LOADING DEEP SCAN.",
    "ENVIRONMENT SCAN COMPLETE: NO ANOMALIES DETECTED IN THE VISUAL FIELD.",
    "SYSTEM STATUS: ALL CORE MODULES OPERATING WITHIN NOMINAL PARAMETERS.",
    "THREAT ASSESSMENT: ZERO EXTERNAL RISKS DETECTED. STANDBY MODE.",
]
_response_cycle = itertools.cycle(DEMO_RESPONSES)

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key and not DEMO_MODE else None

# ── MODELO GEMINI — família 3/3.1 (nomes oficiais da API) ──
MODEL_LIST = [
    "gemini-3.1-flash-lite-preview", # Prioridade 1: O mais rápido de 2026
    "gemini-3-flash-preview",       # Prioridade 2: O Flash original
    "gemini-2.5-flash-lite-preview", # Prioridade 3: Backup estável
    "gemini-3.1-pro-preview"        # Fallback de alta inteligência
]
model_id = MODEL_LIST[0]

from playwright_stealth import Stealth

# ── MCP BRIDGE (só local, sem Node no container) ──
class McpAgentBridge:
    def __init__(self):
        self.session: ClientSession = None
        self._active = False
        self._task = None

    async def _run_engine(self):
        print("🚀 [MCP] Initializing...")
        env = os.environ.copy()
        env["HEADLESS"] = "true"
        server_params = StdioServerParameters(command="npx", args=["-y", "@playwright/mcp@latest"], env=env)
        async with AsyncExitStack() as stack:
            try:
                read_stream, write_stream = await stack.enter_async_context(stdio_client(server_params))
                self.session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
                await self.session.initialize()
                tools = await self.session.list_tools()
                print(f"🛠️ [MCP] Tools: {[t.name for t in tools.tools]}")
                self._active = True
                print("✅ [MCP] Ready")
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                print("🛑 [MCP] Shutdown")
            except Exception as e:
                print(f"❌ [MCP] Error: {e}")
            finally:
                self._active = False
                self.session = None

    async def start(self):
        if self._active: return
        self._task = asyncio.create_task(self._run_engine())
        for _ in range(10):
            if self._active: break
            await asyncio.sleep(0.5)

    async def call_tool(self, name: str, arguments: dict):
        if not self._active or not self.session:
            await self.start()
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
    is_cloud = os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RENDER")
    if not is_cloud:
        print("🏠 [System] Local — MCP Bridge ON")
        await mcp_bridge.start()
    else:
        print("☁️ [System] Cloud — MCP Bridge OFF")
    yield
    if not is_cloud:
        await mcp_bridge.stop()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/health")
async def health():
    return JSONResponse({"status": "BRAIN_ACTIVE", "version": "3.1.0", "model": model_id})

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.post("/debug/log")
async def debug_log(data: dict):
    with open("client_debug.log", "a") as f:
        import datetime
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{ts}] {data.get('level', 'INFO')}: {data.get('message')}\n")
    return {"status": "logged"}

cognitive_memory = []
last_analysis_result = "technology and automation"
hud_connections: set[WebSocket] = set()
vision_connections: set[WebSocket] = set()
_cache: dict[str, tuple[str, float]] = {}
CACHE_TTL = 30

def _cache_get(key):
    if key in _cache:
        val, ts = _cache[key]
        if time.time() - ts < CACHE_TTL: return val
        del _cache[key]
    return None

def _cache_set(key, val):
    if len(_cache) > 200:
        del _cache[min(_cache, key=lambda k: _cache[k][1])]
    _cache[key] = (val, time.time())

def _resize_image(data: bytes, max_size: int = 512) -> bytes:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70, optimize=True)
    return buf.getvalue()

class AnalyzeRequest(BaseModel):
    image: str

@app.websocket("/ws/hud")
async def websocket_hud(ws: WebSocket):
    await ws.accept()
    hud_connections.add(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "frame" and data.get("image"):
                for v in list(vision_connections):
                    try: await v.send_json(data)
                    except: vision_connections.discard(v)
                continue
            if data.get("type") == "command":
                cmd = data.get("command")
                query = data.get("query")
                if cmd == "close_browser":
                    await mcp_bridge.stop()
                elif cmd == "analyze_and_search":
                    if query:
                        await ws.send_json({"type": "status_update", "message": "AGENT: MANUAL_SEARCH_START"})
                        try:
                            url = query if query.startswith("http") else f"https://www.google.com/search?q={query.replace(' ', '+')}"
                            img_data = await capture_screenshot(url)
                            await ws.send_json({"type": "browser_screenshot", "data": img_data})
                            await ws.send_json({"type": "status_update", "message": "AGENT: CAPTURE_COMPLETE"})
                        except Exception as e:
                            await ws.send_json({"type": "status_update", "message": f"SEARCH_ERROR: {str(e)[:25]}"})
                    else:
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

async def capture_screenshot(url: str) -> str:
    from playwright_stealth import Stealth
    import json
    
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True, args=[
            "--no-sandbox", "--disable-setuid-sandbox",
            "--disable-dev-shm-usage", "--disable-gpu"
        ])
        try:
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            
            # Tenta carregar cookies de sessão para evitar CAPTCHA
            cookies_path = os.path.join(os.getcwd(), "cookies.json")
            if os.path.exists(cookies_path):
                print("🍪 [Playwright] Loading session cookies...")
                with open(cookies_path, 'r') as f:
                    cookies = json.load(f)
                    await context.add_cookies(cookies)
            
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(5)
            screenshot_bytes = await page.screenshot(type="jpeg", quality=60)
            return base64.b64encode(screenshot_bytes).decode('utf-8')
        except Exception as e:
            print(f"❌ [Playwright] Error: {e}")
            raise
        finally:
            await browser.close()

async def handle_agent_action(action: str, ws_target: WebSocket):
    global last_analysis_result
    if action == "HOMES_SEARCH_BROWSER":
        await ws_target.send_json({"type": "status_update", "message": "AGENT: STARTING_PLAYWRIGHT"})
        try:
            img_data = await capture_screenshot(f"https://www.google.com/search?q={last_analysis_result.replace(' ', '+')}")
            await ws_target.send_json({"type": "browser_screenshot", "data": img_data})
            await ws_target.send_json({"type": "status_update", "message": "AGENT: SEARCH_COMPLETE"})
        except Exception as e:
            await ws_target.send_json({"type": "status_update", "message": f"AGENT_ERROR: {str(e)[:25]}"})
    elif action == "HOMES_EMERGENCY_STOP":
        await ws_target.send_json({"type": "status_update", "message": "EMERGENCY_STOP: KILLING_AGENT"})
        await mcp_bridge.stop()

async def _call_gemini_with_fallback(optimized_image, prompt_parts):
    last_error = None
    for m_id in MODEL_LIST:
        try:
            print(f"🤖 [AI] Trying: {m_id}")
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=m_id,
                contents=[types.Content(role="user", parts=[
                    types.Part.from_bytes(mime_type="image/jpeg", data=optimized_image),
                    types.Part.from_text(text=(
                        f"CONTEXT: {prompt_parts}\n\n"
                        "TASK: Analyze the image. Identify people or objects. "
                        "Keep it tactical, short and use ONLY PLAIN TEXT. "
                        "NO MARKDOWN, NO ASTERISKS, NO DASHES. "
                        "At the end, suggest a SEARCH QUERY in square brackets, like [search: topic]."
                    ))
                ])]
            )
            return response.text, m_id
        except Exception as e:
            last_error = str(e)
            print(f"⚠️ [AI] {m_id} failed: {last_error[:60]}")
            if any(x in last_error for x in ["429", "quota", "demand", "overloaded"]):
                continue
            break
    raise Exception(f"All models failed: {last_error}")

@app.post("/analyze")
async def analyze_frame(request: AnalyzeRequest):
    global cognitive_memory, last_analysis_result
    if DEMO_MODE:
        await asyncio.sleep(0.6)
        mock_text = next(_response_cycle)
        last_analysis_result = mock_text
        return {"status": "success", "text": mock_text, "cached": False, "demo": True}
    if not client:
        return {"error": "AI unavailable — set GEMINI_API_KEY or enable DEMO_MODE=true"}
    try:
        image_bytes = base64.b64decode(request.image)
        optimized = _resize_image(image_bytes)
        img_hash = hashlib.md5(optimized).hexdigest()
        cached = _cache_get(img_hash)
        if cached: return {"status": "success", "text": cached, "cached": True}
        history_context = " | ".join(cognitive_memory[-3:]) if cognitive_memory else "None"
        text_result, used_model = await _call_gemini_with_fallback(optimized, history_context)
        cognitive_memory.append(text_result)
        if len(cognitive_memory) > 10: cognitive_memory.pop(0)
        _cache_set(img_hash, text_result)
        import re
        m = re.search(r'\[search:\s*(.*?)\]', text_result)
        last_analysis_result = m.group(1) if m else text_result[:50]
        return {"status": "success", "text": text_result, "cached": False, "model": used_model}
    except Exception as e:
        print(f"❌ [Analyze] {e}")
        return {"status": "error", "message": str(e)}

@app.post("/ingest/gesture")
async def ingest_gesture(data: dict):
    disconnected = set()
    for conn in list(hud_connections):
        try: await conn.send_json(data)
        except: disconnected.add(conn)
    for conn in disconnected: hud_connections.discard(conn)
    return {"status": "sent", "active_connections": len(hud_connections)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
