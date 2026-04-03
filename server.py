import hashlib
import time
import asyncio
import base64
import os
import io
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Carregar variáveis de ambiente e configurar Gemini
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    client = genai.Client(api_key=api_key)
    model_id = 'gemini-2.0-flash' # Atualizado para a versão estável mais rápida
else:
    client = None

app = FastAPI()

# Servir arquivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── OTIMIZAÇÃO 2: Estruturas de Dados Eficientes (O(1)) ──
hud_connections: set[WebSocket] = set()
vision_connections: set[WebSocket] = set()

# ── OTIMIZAÇÃO 1: Application-level Caching (MD5) ──
_cache: dict[str, tuple[str, float]] = {}
CACHE_TTL = 30  # Tempo de vida do cache em segundos

def _cache_get(key: str) -> str | None:
    if key in _cache:
        val, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return val
        del _cache[key]
    return None

def _cache_set(key: str, val: str):
    if len(_cache) > 200:   # Evict oldest if cache grows too large
        oldest = min(_cache, key=lambda k: _cache[k][1])
        del _cache[oldest]
    _cache[key] = (val, time.time())

# ── OTIMIZAÇÃO 3: Optimize Asset Sizes (Redimensionamento) ──
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
async def websocket_hud(websocket: WebSocket):
    await websocket.accept()
    hud_connections.add(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "command":
                # Fazemos uma cópia da lista para iterar com segurança
                for vision in list(vision_connections):
                    try:
                        await vision.send_json(data)
                    except:
                        vision_connections.discard(vision)
    except WebSocketDisconnect:
        hud_connections.discard(websocket)

@app.websocket("/ws/vision")
async def websocket_vision(websocket: WebSocket):
    await websocket.accept()
    vision_connections.add(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            for hud in list(hud_connections):
                try:
                    await hud.send_json(data)
                except:
                    hud_connections.discard(hud)
    except WebSocketDisconnect:
        vision_connections.discard(websocket)

@app.post("/analyze")
async def analyze_frame(request: AnalyzeRequest):
    if not client:
        return {"error": "Gemini API key not configured", "text": "IA indisponível", "cached": False}
    
    try:
        image_bytes = base64.b64decode(request.image)
        
        # OTM 3: Reduz tamanho do payload antes de processar/enviar
        optimized_image = _resize_image(image_bytes)
        img_hash = hashlib.md5(optimized_image).hexdigest()

        # OTM 1: Verifica cache antes de chamar a API dispendiosa
        cached_response = _cache_get(img_hash)
        if cached_response:
            return {
                "status": "success", 
                "text": cached_response, 
                "cached": True, 
                "cache_hit": img_hash[:8]
            }

        # Configuração de Pensamento (removido para gemini-2.0-flash padrão para maior velocidade)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_id,
            contents=[
                types.Content(role="user", parts=[
                    types.Part.from_bytes(mime_type="image/jpeg", data=optimized_image),
                    types.Part.from_text(text="Descreva o que você vê nesta imagem de forma curta e técnica para um HUD de assistente IA.")
                ])
            ]
        )
        
        result_text = response.text
        _cache_set(img_hash, result_text)
        
        return {"status": "success", "text": result_text, "cached": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest/gesture")
async def ingest_gesture(data: dict):
    disconnected = set()
    for connection in list(hud_connections):
        try:
            await connection.send_json(data)
        except:
            disconnected.add(connection)
    
    for conn in disconnected:
        hud_connections.discard(conn)
            
    return {"status": "sent", "active_connections": len(hud_connections)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
