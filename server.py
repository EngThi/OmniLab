import hashlib
import time
import asyncio
import base64
import os
import io
import json
import itertools
import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types
from playwright.async_api import async_playwright
import playwright_stealth
from contextlib import asynccontextmanager, AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

class AnalyzeRequest(BaseModel): image: str

# ── CONFIGURAÇÃO DE IA ──
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None
MODEL_LIST = ["gemini-3.1-flash-lite-preview", "gemini-3-flash-preview", "gemini-2.5-flash-lite-preview"]

# ── AGENTE MCP BRIDGE ──
class McpAgentBridge:
    def __init__(self):
        self.session = None
        self._active = False
        self._task = None

    async def _run_engine(self):
        print("🚀 [MCP] Initializing Agent Core...")
        env = os.environ.copy()
        env["HEADLESS"] = os.getenv("HEADLESS", "true")
        server_params = StdioServerParameters(command="npx", args=["-y", "@playwright/mcp@latest"], env=env)
        async with AsyncExitStack() as stack:
            try:
                read_stream, write_stream = await stack.enter_async_context(stdio_client(server_params))
                self.session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
                await self.session.initialize()
                self._active = True
                print("✅ [MCP] Agent Ready")
                while True: await asyncio.sleep(1)
            except Exception as e: print(f"❌ [MCP Error] {e}")
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
        if not self._active or not self.session: await self.start()
        if self.session: return await self.session.call_tool(name, arguments)
        return None

    async def stop(self):
        if self._task: self._task.cancel()
        self._active = False

mcp_bridge = McpAgentBridge()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp_bridge.start()
    yield
    await mcp_bridge.stop()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root(): return FileResponse("static/index.html")

@app.post("/debug/log")
async def debug_log(data: dict):
    with open("client_debug.log", "a") as f:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{ts}] {data.get('level', 'INFO')}: {data.get('message')}\n")
    return {"status": "logged"}

hud_connections: set[WebSocket] = set()
vision_connections: set[WebSocket] = set()
last_analysis_result = "technology"

async def capture_screenshot(url: str) -> str:
    is_headless = os.getenv("HEADLESS", "true").lower() == "true"
    print(f"🖥️ [Agent] Launching Browser (Headless: {is_headless})")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=is_headless, args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            context = await browser.new_context(viewport={'width': 1280, 'height': 720}, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
            page = await context.new_page()
            
            try:
                st_func = getattr(playwright_stealth, 'stealth_async', getattr(playwright_stealth, 'stealth', None))
                if st_func: await st_func(page)
            except: pass

            cookies_path = "cookies.json"
            if os.path.exists(cookies_path):
                with open(cookies_path, 'r') as f:
                    try:
                        raw = json.load(f)
                        clean = []
                        for c in raw:
                            if not isinstance(c, dict): continue
                            nc = {"name": str(c.get("name", "")), "value": str(c.get("value", "")), "domain": str(c.get("domain", "")), "path": str(c.get("path", "/")), "secure": bool(c.get("secure", True)), "httpOnly": bool(c.get("httpOnly", False))}
                            if "expirationDate" in c: nc["expires"] = int(float(c["expirationDate"]))
                            ss = str(c.get("sameSite", "Lax")).lower()
                            nc["sameSite"] = ss.capitalize() if ss in ["strict", "lax", "none"] else "Lax"
                            if ss == "no_restriction": nc["sameSite"] = "None"
                            clean.append(nc)
                        await context.add_cookies(clean)
                    except Exception as ce: print(f"⚠️ [Agent] Cookies error: {ce}")

            print(f"📡 [Agent] Navigating to: {url}")
            # 'load' evita timeouts infinitos do networkidle
            await page.goto(url, wait_until="load", timeout=45000)
            await asyncio.sleep(4) # Espera humana
            await page.evaluate("window.scrollTo({top: 400, behavior: 'smooth'})")
            await asyncio.sleep(2)
            
            img = await page.screenshot(type="jpeg", quality=75)
            return base64.b64encode(img).decode('utf-8')
        except Exception as e:
            print(f"❌ [Agent Error] {e}")
            raise
        finally: await browser.close()

@app.websocket("/ws/hud")
async def websocket_hud(ws: WebSocket):
    await ws.accept()
    hud_connections.add(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "frame":
                for v in list(vision_connections): await v.send_json(data)
            elif data.get("type") == "command":
                cmd = data.get("command")
                if cmd == "analyze_and_search":
                    query = data.get("query") or last_analysis_result
                    await ws.send_json({"type": "status_update", "message": "AGENT: SEARCHING"})
                    try:
                        img_data = await capture_screenshot(query if query.startswith("http") else f"https://www.google.com/search?q={query.replace(' ', '+')}")
                        await ws.send_json({"type": "browser_screenshot", "data": img_data})
                    except Exception as e: await ws.send_json({"type": "status_update", "message": f"ERROR: {str(e)[:25]}"})
    except: pass
    finally: hud_connections.discard(ws)

@app.websocket("/ws/vision")
async def websocket_vision(ws: WebSocket):
    await ws.accept()
    vision_connections.add(ws)
    try:
        while True:
            data = await ws.receive_json()
            for h in list(hud_connections): await h.send_json(data)
    except: pass
    finally: vision_connections.discard(ws)

@app.post("/analyze")
async def analyze_frame(request: AnalyzeRequest):
    global last_analysis_result
    if not client: return {"error": "AI offline"}
    try:
        image_bytes = base64.b64decode(request.image)
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((512, 512))
        buf = io.BytesIO(); img.save(buf, format="JPEG", quality=70); optimized = buf.getvalue()
        for m_id in MODEL_LIST:
            try:
                res = await asyncio.to_thread(client.models.generate_content, model=m_id, contents=[types.Content(role="user", parts=[types.Part.from_bytes(mime_type="image/jpeg", data=optimized), types.Part.from_text(text="Analyze image. TACTICAL SHORT PLAIN TEXT ONLY. Suggest [search: query].")])])
                text = res.text
                import re
                m = re.search(r'\[search:\s*(.*?)\]', text)
                last_analysis_result = m.group(1) if m else text[:50]
                return {"status": "success", "text": text}
            except: continue
        return {"error": "All models busy"}
    except Exception as e: return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
