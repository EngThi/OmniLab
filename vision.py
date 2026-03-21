import cv2
import mediapipe as mp
import numpy as np
import time
import math
import json
import asyncio
import websockets
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
import io
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Carregar variáveis de ambiente e configurar Gemini
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    client = genai.Client(api_key=api_key)
    model_id = 'gemini-3-flash-preview' 
else:
    print("AVISO: GEMINI_API_KEY não encontrada no .env. Análise de imagem não funcionará.")
    client = None

def draw_landmarks_on_image(rgb_image, detection_result):
    annotated_image = np.copy(rgb_image)
    h, w, _ = annotated_image.shape
    if detection_result.hand_landmarks:
        for hand_landmarks_list in detection_result.hand_landmarks:
            for landmark in hand_landmarks_list:
                cx, cy = int(landmark.x * w), int(landmark.y * h)
                cv2.circle(annotated_image, (cx, cy), 5, (0, 0, 255), cv2.FILLED) 
    return annotated_image

# Configuração do Hand Landmarker
base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    num_hands=1,
    min_hand_detection_confidence=0.5,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.5
)
detector = vision.HandLandmarker.create_from_options(options)

def validate_frame(frame):
    if frame is None or not isinstance(frame, np.ndarray):
        raise ValueError("Frame inválido")
    if frame.size == 0:
        raise ValueError("Frame vazio")
    return True

SCAN_INTERVAL = 60000 # 1 minuto para scans automáticos agora
PINCH_THRESHOLD_MS = 1500 # Tempo segurando a pinça para disparar scan

async def vision_loop():
    uri = "ws://localhost:8000/ws/vision"
    last_scan_time = int(time.time() * 1000)
    pinch_start_time = None
    is_analyzing = False
    
    # Telemetria
    fps_start_time = time.time()
    fps_counter = 0
    fps = 0

    thinking_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(include_thoughts=True)
    )
    
    while True: 
        try:
            async with websockets.connect(uri) as websocket:
                print("[\033[92mSUCCESS\033[0m] OmniLab Vision Ativa!")
                cap = cv2.VideoCapture(0)
                
                while cap.isOpened():
                    success, img = cap.read()
                    if not success: break

                    fps_counter += 1
                    if (time.time() - fps_start_time) > 1:
                        fps = fps_counter
                        fps_counter = 0
                        fps_start_time = time.time()

                    img = cv2.flip(img, 1)
                    last_frame = img.copy()
                    
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
                    timestamp = int(time.time() * 1000)
                    detection_result = detector.detect_for_video(mp_image, timestamp)

                    annotated_image = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
                    gesture_data = {"type": "gesture", "x": 0.5, "y": 0.5, "pinch": False, "fps": fps, "pinch_progress": 0}

                    if detection_result.hand_landmarks:
                        annotated_image = draw_landmarks_on_image(annotated_image, detection_result)
                        for hand_landmarks in detection_result.hand_landmarks:
                            h, w, _ = annotated_image.shape
                            norm_x, norm_y = hand_landmarks[8].x, hand_landmarks[8].y
                            x1, y1 = int(hand_landmarks[4].x * w), int(hand_landmarks[4].y * h)
                            x2, y2 = int(hand_landmarks[8].x * w), int(hand_landmarks[8].y * h)
                            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                            length = math.hypot(x2 - x1, y2 - y1)
                            
                            is_pinching = length < 40
                            pinch_progress = 0

                            if is_pinching:
                                if pinch_start_time is None:
                                    pinch_start_time = timestamp
                                else:
                                    elapsed = timestamp - pinch_start_time
                                    pinch_progress = min(elapsed / PINCH_THRESHOLD_MS, 1.0)
                                    
                                    # DISPARO POR GESTO (Tony Stark Style)
                                    if elapsed >= PINCH_THRESHOLD_MS and not is_analyzing:
                                        is_analyzing = True
                                        asyncio.create_task(trigger_scan(websocket, last_frame, client, model_id, thinking_config))
                                        pinch_start_time = timestamp # Reset para não disparar em loop
                            else:
                                pinch_start_time = None
                                is_analyzing = False

                            cv2.line(annotated_image, (x1, y1), (x2, y2), (255, 0, 255), 2)
                            color = (0, 255, 0) if is_pinching else (255, 0, 255)
                            cv2.circle(annotated_image, (cx, cy), int(10 + (pinch_progress * 10)), color, cv2.FILLED)
                            
                            gesture_data = {
                                "type": "gesture", "x": norm_x, "y": norm_y, 
                                "pinch": is_pinching, "fps": fps, "pinch_progress": pinch_progress
                            }

                    await websocket.send(json.dumps(gesture_data))

                    # Comandos de Voz (Mantidos para redundância)
                    try:
                        msg = await asyncio.wait_for(websocket.recv(), timeout=0.001)
                        data = json.loads(msg)
                        if data.get("command") == "analyze" and client:
                            asyncio.create_task(trigger_scan(websocket, last_frame, client, model_id, thinking_config))
                    except asyncio.TimeoutError: pass

                    cv2.imshow("OmniLab Vision", annotated_image)
                    if cv2.waitKey(1) & 0xFF == ord('q'): break

                cap.release()
                cv2.destroyAllWindows()
                break 

        except Exception as e:
            print(f"[\033[91mERROR\033[0m] Vision error: {e}")
            await asyncio.sleep(3)

async def trigger_scan(websocket, frame, client, model_id, config):
    print(f"[\033[94mINFO\033[0m] Gesto/Voz detectado. Iniciando Deep Scan...")
    await websocket.send(json.dumps({"type": "status_update", "message": "INITIATING_GESTURE_SCAN"}))
    _, buffer = cv2.imencode('.jpg', frame)
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_id,
            contents=[
                types.Content(role="user", parts=[
                    types.Part.from_bytes(mime_type="image/jpeg", data=buffer.tobytes()),
                    types.Part.from_text(text="Relatório tático do que você vê. Máximo 12 palavras.")
                ])
            ],
            config=config
        )
        await websocket.send(json.dumps({
            "type": "analysis_result",
            "text": response.text.strip().upper()
        }))
    except Exception as e:
        print(f"[\033[91mERROR\033[0m] Scan error: {e}")

if __name__ == "__main__":
    asyncio.run(vision_loop())
