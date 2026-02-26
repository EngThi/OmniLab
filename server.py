from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json
import asyncio

app = FastAPI()

# Armazena conexões ativas do HUD
hud_connections = []

@app.get(\"/\")
async def get():
    return HTMLResponse(\"\"\"
    <!DOCTYPE html>
    <html>
        <head>
            <title>OmniLab HUD</title>
            <script src=\"https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js\"></script>
            <style>
                body { margin: 0; overflow: hidden; background: #000; font-family: 'Courier New', monospace; }
                #ui-layer {
                    position: absolute; top: 0; left: 0; width: 100%; height: 100%;
                    pointer-events: none; color: #00f2ff; padding: 20px;
                    text-shadow: 0 0 10px #00f2ff;
                }
                .scanline {
                    width: 100%; height: 2px; background: rgba(0, 242, 245, 0.1);
                    position: absolute; animation: scan 4s linear infinite;
                }
                @keyframes scan { from {top: 0;} to {top: 100%;} }
                #voice-status {
                    margin-top: 10px;
                    color: #ff00ff;
                    font-weight: bold;
                }
                #voice-transcript {
                    margin-top: 5px;
                    color: #fff;
                    font-size: 0.9em;
                    max-width: 600px;
                }
            </style>
        </head>
        <body>
            <div id=\"ui-layer\">
                <div class=\"scanline\"></div>
                <h2> OMNILAB OS // CORE_V1</h2>
                <div id=\"status\">INITIATING...</div>
                <div id=\"debug\"></div>
                <div id=\"voice-status\">MIC: INITIALIZING...</div>
                <div id=\"voice-transcript\"></div>
            </div>

            <script>
                // --- 1. SETUP THREE.JS ---
                const scene = new THREE.Scene();
                const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
                const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true});
                renderer.setSize(window.innerWidth, window.innerHeight);
                document.body.appendChild(renderer.domElement);

                // --- 2. ELEMENTOS HOLOGRÁFICOS ---
                // Cursor 3D (Anéis concêntricos)
                const cursorGroup = new THREE.Group();
                const ringMat = new THREE.MeshBasicMaterial({ color: 0x00f2ff, transparent: true, opacity: 0.8, side: THREE.DoubleSide });
                const innerRing = new THREE.Mesh(new THREE.RingGeometry(0.8, 1, 32), ringMat);
                const outerRing = new THREE.Mesh(new THREE.RingGeometry(1.2, 1.3, 4, 1), ringMat); // Formato diamante
                cursorGroup.add(innerRing, outerRing);
                scene.add(cursorGroup);

                // Grade de Fundo (Grid)
                const grid = new THREE.GridHelper(100, 40, 0x00f2ff, 0x002222);
                grid.rotation.x = Math.PI / 2;
                grid.position.z = -20;
                scene.add(grid);

                camera.position.z = 15;

                // --- 3. CONEXÃO WEBSOCKET ---
                const statusEl = document.getElementById('status');
                const debugEl = document.getElementById('debug');
                const ws = new WebSocket(`ws://${window.location.host}/ws/hud`);
                
                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    if (data.type === 'gesture') {
                        // Mapear 0-1 para coordenadas no Three.js
                        // X vai de -15 a 15, Y vai de -10 a 10
                        const targetX = (data.x - 0.5) * 30;
                        const targetY = (0.5 - data.y) * 20;

                        // Interpolação suave (Lerp) para não tremer
                        cursorGroup.position.x += (targetX - cursorGroup.position.x) * 0.3;
                        cursorGroup.position.y += (targetY - cursorGroup.position.y) * 0.3;
                        
                        // Paralaxe na grade
                        grid.position.x = cursorGroup.position.x * -0.1;
                        grid.position.y = cursorGroup.position.y * -0.1;

                        if (data.pinch) {
                            ringMat.color.setHex(0x00ff00); // Verde no pinch
                            cursorGroup.scale.set(0.8, 0.8, 0.8); // Pulsa para baixo
                            statusEl.innerText = \"ACTION: PINCH_DETECTED\"; 
                        } else {
                            ringMat.color.setHex(0x00f2ff); // Azul padrão
                            cursorGroup.scale.set(1, 1, 1);
                            statusEl.innerText = \"SYSTEM: TRACKING_ACTIVE\";
                        }
                        debugEl.innerText = `X: ${data.x.toFixed(2)} | Y: ${data.y.toFixed(2)}`;
                    }
                };

                // --- 4. WEB SPEECH API (RECONHECIMENTO DE VOZ) ---
                const voiceStatusEl = document.getElementById('voice-status');
                const voiceTranscriptEl = document.getElementById('voice-transcript');
                
                // Verifica suporte no navegador
                window.SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                
                if (window.SpeechRecognition) {
                    const recognition = new SpeechRecognition();
                    recognition.continuous = true; // Continua ouvindo
                    recognition.interimResults = true; // Mostra resultados enquanto fala
                    recognition.lang = 'pt-BR'; // Pode mudar para 'en-US' depois se preferir

                    recognition.onstart = function() {
                        voiceStatusEl.innerText = \"MIC: LISTENING_MODE\";
                        voiceStatusEl.style.color = \"#00ff00\";
                    };

                    recognition.onresult = function(event) {
                        let interimTranscript = '';
                        let finalTranscript = '';

                        for (let i = event.resultIndex; i < event.results.length; ++i) {
                            if (event.results[i].isFinal) {
                                finalTranscript += event.results[i][0].transcript;
                                
                                // ONDE A MÁGICA ACONTECE: Analisando comandos de voz
                                const cmd = finalTranscript.toLowerCase().trim();
                                if (cmd.includes(\"analisar\") || cmd.includes(\"analyze\")) {
                                    statusEl.innerText = \"SYSTEM: ANALYZING ENVIRONMENT...\";
                                    ringMat.color.setHex(0xff00ff); // Muda cor do cursor pra roxo
                                } else if (cmd.includes(\"desativar\") || cmd.includes(\"deactivate\")) {
                                    statusEl.innerText = \"SYSTEM: STANDBY\";
                                    ringMat.color.setHex(0xff0000); // Vermelho
                                }
                                
                            } else {
                                interimTranscript += event.results[i][0].transcript;
                            }
                        }
                        
                        // Mostra o que está entendendo na tela
                        if (finalTranscript) {
                            voiceTranscriptEl.innerHTML = `> ${finalTranscript}`;
                        } else {
                            voiceTranscriptEl.innerHTML = `<i>${interimTranscript}</i>`;
                        }
                    };

                    recognition.onerror = function(event) {
                        voiceStatusEl.innerText = \"MIC: ERROR_\" + event.error.toUpperCase();
                        voiceStatusEl.style.color = \"#ff0000\";
                    };

                    recognition.onend = function() {
                        // Reinicia automaticamente se parar (modo always-on)
                        voiceStatusEl.innerText = \"MIC: RESTARTING...\";
                        setTimeout(() => recognition.start(), 1000);
                    };

                    // Pede permissão e inicia
                    try {
                        recognition.start();
                    } catch(e) {
                        voiceStatusEl.innerText = \"MIC: PERMISSION_DENIED\";
                    }
                } else {
                    voiceStatusEl.innerText = \"MIC: API_NOT_SUPPORTED\";
                    voiceStatusEl.style.color = \"#ff0000\";
                }

                // --- 5. LOOP DE ANIMAÇÃO ---
                function animate() {
                    requestAnimationFrame(animate);
                    innerRing.rotation.z += 0.05;
                    outerRing.rotation.z -= 0.02;
                    renderer.render(scene, camera);
                }
                animate();

                window.onresize = () => {
                    camera.aspect = window.innerWidth / window.innerHeight;
                    camera.updateProjectionMatrix();
                    renderer.setSize(window.innerWidth, window.innerHeight);
                };
            </script>
        </body>
    </html>
    \"\"\")


@app.websocket(\"/ws/hud\")
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
@app.post(\"/ingest/gesture\")
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
            
    return {\"status\": \"sent\"}
