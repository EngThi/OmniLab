
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json
import asyncio

app = FastAPI()

# Armazena conexões ativas do HUD
hud_connections = []

@app.get("/")
async def get():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
        <head>
            <title>OmniLab HUD</title>
            <style>
                body { margin: 0; overflow: hidden; background: #000; color: #0f0; font-family: monospace; }
                #status { position: absolute; top: 10px; left: 10px; z-index: 100; }
                #cursor { 
                    position: absolute; width: 20px; height: 20px; 
                    border: 2px solid #0f0; border-radius: 50%; 
                    transform: translate(-50%, -50%); pointer-events: none;
                    transition: all 0.1s ease-out;
                }
                .active { background: rgba(0, 255, 0, 0.3); border-color: #fff !important; }
            </style>
        </head>
        <body>
            <div id="status">OmniLab HUD: Disconnected</div>
            <div id="cursor"></div>
            
            <script>
                const status = document.getElementById('status');
                const cursor = document.getElementById('cursor');
                const ws = new WebSocket(`ws://${window.location.host}/ws/hud`);

                ws.onopen = () => {
                    status.innerText = "OmniLab HUD: Connected";
                    status.style.color = "#0f0";
                };

                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'gesture') {
                        // Mapeia coordenadas normalizadas (0-1) para tela
                        const x = data.x * window.innerWidth;
                        const y = data.y * window.innerHeight;
                        
                        cursor.style.left = x + 'px';
                        cursor.style.top = y + 'px';
                        
                        if (data.pinch) {
                            cursor.classList.add('active');
                            status.innerText = `PINCH ACTIVE | X: ${Math.round(x)} Y: ${Math.round(y)}`;
                        } else {
                            cursor.classList.remove('active');
                            status.innerText = `Tracking | X: ${Math.round(x)} Y: ${Math.round(y)}`;
                        }
                    }
                };

                ws.onclose = () => {
                    status.innerText = "OmniLab HUD: Disconnected";
                    status.style.color = "#f00";
                };
            </script>
        </body>
    </html>
    """)

@app.websocket("/ws/hud")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    hud_connections.append(websocket)
    try:
        while True:
            # Mantém conexão viva
            await websocket.receive_text()
    except WebSocketDisconnect:
        hud_connections.remove(websocket)

# Endpoint interno para o vision.py enviar dados
@app.post("/ingest/gesture")
async def ingest_gesture(data: dict):
    # Broadcast para todos HUDs conectados
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
