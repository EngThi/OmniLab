from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
import asyncio
import base64
import os
import io
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Carregar variáveis de ambiente e configurar Gemini
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    client = genai.Client(api_key=api_key)
    model_id = 'gemini-3-flash-preview'
else:
    client = None

app = FastAPI()

# Servir arquivos estáticos (CSS, JS, Imagens se necessário)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Listas de conexões ativas
hud_connections = []
vision_connections = []

class AnalyzeRequest(BaseModel):
    image: str # base64 string

@app.get("/")
async def get():
    return FileResponse("static/index.html")


@app.websocket("/ws/hud")
async def websocket_hud(websocket: WebSocket):
    await websocket.accept()
    hud_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "command":
                for vision in vision_connections:
                    await vision.send_json(data)
    except WebSocketDisconnect:
        hud_connections.remove(websocket)

@app.websocket("/ws/vision")
async def websocket_vision(websocket: WebSocket):
    await websocket.accept()
    vision_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            for hud in hud_connections:
                await hud.send_json(data)
    except WebSocketDisconnect:
        vision_connections.remove(websocket)

@app.post("/analyze")
async def analyze_frame(request: AnalyzeRequest):
    if not client:
        return {"error": "Gemini API key not configured", "text": "IA indisponível"}
    
    try:
        image_data = base64.b64decode(request.image)
        
        # Configuração de Pensamento
        thinking_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(include_thoughts=True)
        )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_id,
            contents=[
                types.Content(role="user", parts=[
                    types.Part.from_bytes(mime_type="image/jpeg", data=image_data),
                    types.Part.from_text(text="Descreva o que você vê nesta imagem de forma curta e técnica para um HUD de assistente IA.")
                ])
            ],
            config=thinking_config
        )
        return {"status": "success", "text": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest/gesture")
async def ingest_gesture(data: dict):
    disconnected = []
    for connection in hud_connections:
        try:
            await connection.send_json(data)
        except:
            disconnected.append(connection)
    
    for conn in disconnected:
        if conn in hud_connections:
            hud_connections.remove(conn)
            
    return {"status": "sent"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
