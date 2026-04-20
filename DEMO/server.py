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
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

# ── FORCED DEMO MODE & KEY CHECK ──
api_key = os.getenv("GEMINI_API_KEY")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

if not api_key:
    print("⚠️ [System] GEMINI_API_KEY not found. FORCING DEMO_MODE=True")
    DEMO_MODE = True

DEMO_RESPONSES = [
    "TACTICAL ANALYSIS: SUBJECT IDENTIFIED. NEURAL LINK STABLE. [search: robotics automation]",
    "GESTURE RECOGNITION ACTIVE: PINCH DETECTED. LOADING DEEP SCAN. [search: hand tracking tech]",
    "ENVIRONMENT SCAN COMPLETE: NO ANOMALIES DETECTED. [search: cybersecurity threats]",
    "SYSTEM STATUS: ALL CORE MODULES OPERATING NORMALLY. [search: linux server performance]",
]
_response_cycle = itertools.cycle(DEMO_RESPONSES)

client = genai.Client(api_key=api_key) if api_key and not DEMO_MODE else None
MODEL_LIST = ["gemini-3.1-flash-lite-preview", "gemini-3-flash-preview", "gemini-3.1-pro-preview"]
model_id = MODEL_LIST[0]

# ── MCP BRIDGE ──
class McpAgentBridge:
    def __init__(self):
        self.session: ClientSession = None
        self._active = False
        self._task = None

    async def _run_engine(self):
        env = os.environ.copy()
        env["HEADLESS"] = "true"
        server_params = StdioServerParameters(command="npx", args=["-y", "@playwright/mcp@latest"], env=env)
        async with AsyncExitStack() as stack:
            try:
                read_stream, write_stream = await stack.enter_async_context(stdio_client(server_params))
                self.session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
                await self.session.initialize()
                self._active = True
                while True: await asyncio.sleep(1)
            except Exception: self._active = False

    async def start(self):
        if self._active: return
        self._task = asyncio.create_task(self._run_engine())
        for _ in range(5):
            if self._active: break
            await asyncio.sleep(0.5)

    async def stop(self):
        if self._task: self._task.cancel(); self._task = None
        self._active = False

mcp_bridge = McpAgentBridge()

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await mcp_bridge.stop()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root(): return FileResponse("static/index.html")

cognitive_memory = []
last_analysis_result = "technology"
hud_connections: set[WebSocket] = set()
vision_connections: set[WebSocket] = set()

def _resize_image(data: bytes, max_size: int = 512) -> bytes:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue()

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
                if cmd == "analyze_and_search" and query:
                    await ws.send_json({"type": "status_update", "message": "AGENT: INITIATING_RESEARCH"})
                    try:
                        import urllib.parse
                        url = f"https://duckduckgo.com/?q={urllib.parse.quote(query)}&ia=web"
                        img_data = await capture_screenshot(url)
                        await ws.send_json({"type": "browser_screenshot", "data": img_data})
                    except Exception as e:
                        await ws.send_json({"type": "status_update", "message": f"ERROR: {str(e)[:20]}"})
                elif cmd == "close_browser":
                    # KILL SESSION: Limpa memória e MCP
                    cognitive_memory = []
                    await mcp_bridge.stop()
                    await ws.send_json({"type": "status_update", "message": "SYSTEM_CORE: MEMORY_PURGED"})
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
    except WebSocketDisconnect:
        vision_connections.discard(ws)

async def capture_screenshot(url: str) -> str:
    from playwright_stealth import Stealth
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            context = await browser.new_context(viewport={'width': 1280, 'height': 720})
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(2)
            screenshot_bytes = await page.screenshot(type="jpeg", quality=60, full_page=True)
            return base64.b64encode(screenshot_bytes).decode('utf-8')
        finally:
            await browser.close()

async def _call_ai(image_bytes, history):
    for m_id in MODEL_LIST:
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=m_id,
                contents=[types.Content(role="user", parts=[
                    types.Part.from_bytes(mime_type="image/jpeg", data=image_bytes),
                    types.Part.from_text(text=(
                        f"CONTEXT: {history}\n"
                        "TASK: Tactical analysis. Short plain text. NO MARKDOWN. "
                        "Suggest search query in brackets: [search: term]."
                    ))
                ])]
            )
            return response.text
        except Exception: continue
    return "ANALYSIS_FAILED. [search: error recovery]"

@app.post("/analyze")
async def analyze_frame(request: AnalyzeRequest):
    global last_analysis_result, cognitive_memory
    if DEMO_MODE:
        text = next(_response_cycle)
    else:
        try:
            img_bytes = base64.b64decode(request.image)
            opt = _resize_image(img_bytes)
            text = await _call_ai(opt, " | ".join(cognitive_memory[-2:]))
            cognitive_memory.append(text)
            if len(cognitive_memory) > 5: cognitive_memory.pop(0)
        except Exception as e: return {"status": "error", "message": str(e)}
    
    m = re.search(r'\[search:\s*(.*?)\]', text)
    query = m.group(1) if m else text[:30]
    last_analysis_result = query
    return {"status": "success", "text": text, "suggested_query": query}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
