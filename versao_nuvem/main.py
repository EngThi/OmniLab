
import cv2
import mediapipe as mp
import numpy as np
import math
import base64
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

app = FastAPI()

html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>OmniLab Nuvem Teste</title>
    <style>
        body { margin: 0; background: #111; color: #0f0; font-family: monospace; display: flex; flex-direction: column; align-items: center; }
        #videoElement { display: none; } /* Esconde o video puro, vamos mostrar so o q volta do backend */
        #canvasOutput { border: 2px solid #333; margin-top: 20px; max-width: 100%; }
        #status { margin-top: 10px; font-size: 1.2em; }
        #cursor { 
            position: fixed; width: 20px; height: 20px; 
            border: 2px solid #0f0; border-radius: 50%; 
            pointer-events: none; transform: translate(-50%, -50%);
            transition: all 0.05s linear; z-index: 9999;
        }
        .active { background: rgba(0, 255, 0, 0.5); border-color: #fff !important; transform: translate(-50%, -50%) scale(1.5); }
    </style>
</head>
<body>
    <h2>OmniLab - Teste na VM do Google</h2>
    <p>O seu navegador filma, manda pro backend na nuvem e o backend devolve tudo processado.</p>
    <div id="status">Aguardando câmera...</div>
    
    <video id="videoElement" autoplay playsinline></video>
    <canvas id="hiddenCanvas" style="display:none;"></canvas>
    
    <!-- Imagem que volta do servidor com os desenhos do MediaPipe -->
    <img id="outputImg" style="margin-top: 20px; width: 640px; height: 480px; object-fit: contain;" />
    
    <div id="cursor"></div>

    <script>
        const video = document.getElementById('videoElement');
        const hiddenCanvas = document.getElementById('hiddenCanvas');
        const ctx = hiddenCanvas.getContext('2d');
        const outputImg = document.getElementById('outputImg');
        const status = document.getElementById('status');
        const cursor = document.getElementById('cursor');

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

        ws.onopen = () => {
            status.innerText = "Conectado no Backend! Liberando a câmera...";
            startCamera();
        };

        ws.onclose = () => { status.innerText = "Caiu a conexão com o servidor. ☠️"; status.style.color = "red"; };

        async function startCamera() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
                video.srcObject = stream;
                
                video.onplay = () => {
                    hiddenCanvas.width = video.videoWidth;
                    hiddenCanvas.height = video.videoHeight;
                    status.innerText = "Câmera ON. Mandando frames lá pra VM...";
                    sendFrames();
                };
            } catch (err) {
                status.innerText = "Deu ruim na câmera (tá em HTTP invés de HTTPS?): " + err;
                status.style.color = "red";
            }
        }

        function sendFrames() {
            if (ws.readyState === WebSocket.OPEN) {
                ctx.drawImage(video, 0, 0, hiddenCanvas.width, hiddenCanvas.height);
                // Manda como JPEG comprimido pra não bugar a rede da VM
                const dataUrl = hiddenCanvas.toDataURL('image/jpeg', 0.5);
                ws.send(dataUrl);
            }
            // Chama a cada ~60ms (uns 15 FPS ta bom pra teste de rede)
            setTimeout(sendFrames, 60); 
        }

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            // Atualiza a imagem com o retorno do backend
            if (data.image) {
                outputImg.src = "data:image/jpeg;base64," + data.image;
            }

            // Atualiza o cursor do HUD local
            if (data.x !== null && data.y !== null) {
                const x = data.x * window.innerWidth;
                const y = data.y * window.innerHeight;
                cursor.style.left = x + 'px';
                cursor.style.top = y + 'px';
                
                if (data.pinch) {
                    cursor.classList.add('active');
                    status.innerText = `PINÇA! X: ${data.x.toFixed(2)}`;
                } else {
                    cursor.classList.remove('active');
                    status.innerText = "Rastreando de boa...";
                }
            } else {
                status.innerText = "Mão não encontrada.";
            }
        };
    </script>
</body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html_content)

def init_model():
    # Tenta achar o modelo em pastas diferentes dependendo de onde o comando for rodado
    model_path = 'hand_landmarker.task'
    if not os.path.exists(model_path):
        model_path = '../hand_landmarker.task'
        
    base_options = python.BaseOptions(model_asset_path=model_path)
    # Usando IMAGE no lugar de VIDEO para evitar erro de timestamp maluco via rede
    options = vision.HandLandmarkerOptions(base_options=base_options,
                                           running_mode=vision.RunningMode.IMAGE, 
                                           num_hands=1,
                                           min_hand_detection_confidence=0.5)
    return vision.HandLandmarker.create_from_options(options)

detector = None

@app.on_event("startup")
def startup_event():
    global detector
    try:
        detector = init_model()
        print("Modelo da IA subiu liso!")
    except Exception as e:
        print(f"Putz, erro no modelo. Baixou na raiz? Erro: {e}")

def process_frame(frame_bytes):
    # Transforma os bytes em imagem q o opencv entende
    np_arr = np.frombuffer(frame_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        return None, None, None, False

    img = cv2.flip(img, 1)
    h, w, _ = img.shape
    
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
    
    # Processa (aqui gasta CPU da VM)
    detection_result = detector.detect(mp_image)

    norm_x, norm_y, is_pinch = None, None, False

    if detection_result.hand_landmarks:
        for hand_landmarks in detection_result.hand_landmarks:
            for landmark in hand_landmarks:
                cx, cy = int(landmark.x * w), int(landmark.y * h)
                cv2.circle(img, (cx, cy), 3, (0, 0, 255), cv2.FILLED)

            norm_x = hand_landmarks[8].x 
            norm_y = hand_landmarks[8].y

            x1, y1 = int(hand_landmarks[4].x * w), int(hand_landmarks[4].y * h)
            x2, y2 = int(hand_landmarks[8].x * w), int(hand_landmarks[8].y * h)
            length = math.hypot(x2 - x1, y2 - y1)
            
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            cv2.line(img, (x1, y1), (x2, y2), (255, 0, 255), 2)

            is_pinch = length < 40
            if is_pinch:
                cv2.circle(img, (cx, cy), 15, (0, 255, 0), cv2.FILLED)
            else:
                cv2.circle(img, (cx, cy), 10, (255, 0, 255), cv2.FILLED)

    # Comprime a imagem desenhada pra mandar de volta pro seu PC
    _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 60])
    b64_img = base64.b64encode(buffer).decode('utf-8')

    return b64_img, norm_x, norm_y, is_pinch

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # Tira o cabeçalho base64 do JS
            if "," in data:
                b64_str = data.split(",")[1]
                frame_bytes = base64.b64decode(b64_str)
                
                if detector:
                    b64_img, x, y, pinch = process_frame(frame_bytes)
                    if b64_img:
                        await websocket.send_json({
                            "image": b64_img,
                            "x": x,
                            "y": y,
                            "pinch": pinch
                        })
    except WebSocketDisconnect:
        pass
