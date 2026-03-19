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

SCAN_INTERVAL = 45000 

async def vision_loop():
    uri = "ws://localhost:8000/ws/vision"
    last_scan_time = int(time.time() * 1000)
    
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
                print("[\033[92mSUCCESS\033[0m] OmniLab Vision Conectada via WebSocket!")
                cap = cv2.VideoCapture(0)
                
                if not cap.isOpened():
                    print("[\033[91mERROR\033[0m] Câmera não encontrada ou ocupada!")
                    await asyncio.sleep(5)
                    continue

                last_frame = None

                while cap.isOpened():
                    success, img = cap.read()
                    if not success: break

                    # FPS Calculation
                    fps_counter += 1
                    if (time.time() - fps_start_time) > 1:
                        fps = fps_counter
                        fps_counter = 0
                        fps_start_time = time.time()

                    try: validate_frame(img)
                    except ValueError: continue

                    img = cv2.flip(img, 1)
                    last_frame = img.copy()
                    
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
                    timestamp = int(time.time() * 1000)
                    detection_result = detector.detect_for_video(mp_image, timestamp)

                    annotated_image = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
                    gesture_data = {"type": "gesture", "x": 0.5, "y": 0.5, "pinch": False, "fps": fps}

                    if detection_result.hand_landmarks:
                        annotated_image = draw_landmarks_on_image(annotated_image, detection_result)
                        for hand_landmarks in detection_result.hand_landmarks:
                            h, w, _ = annotated_image.shape
                            norm_x, norm_y = hand_landmarks[8].x, hand_landmarks[8].y
                            x1, y1 = int(hand_landmarks[4].x * w), int(hand_landmarks[4].y * h)
                            x2, y2 = int(hand_landmarks[8].x * w), int(hand_landmarks[8].y * h)
                            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                            length = math.hypot(x2 - x1, y2 - y1)
                            is_pinch = length < 40
                            
                            cv2.line(annotated_image, (x1, y1), (x2, y2), (255, 0, 255), 2)
                            cv2.circle(annotated_image, (cx, cy), 15 if is_pinch else 10, (0, 255, 0) if is_pinch else (255, 0, 255), cv2.FILLED)
                            
                            gesture_data = {"type": "gesture", "x": norm_x, "y": norm_y, "pinch": is_pinch, "fps": fps}

                    await websocket.send(json.dumps(gesture_data))

                    # Periodic scan logic
                    current_time = int(time.time() * 1000)
                    if client and (current_time - last_scan_time > SCAN_INTERVAL):
                        last_scan_time = current_time
                        print(f"[\033[94mINFO\033[0m] Routine scan...")
                        _, buffer = cv2.imencode('.jpg', last_frame)
                        try:
                            response = await asyncio.to_thread(
                                client.models.generate_content,
                                model=model_id,
                                contents=[
                                    types.Content(role="user", parts=[
                                        types.Part.from_bytes(mime_type="image/jpeg", data=buffer.tobytes()),
                                        types.Part.from_text(text="Tactical report (10 words max):")
                                    ])
                                ],
                                config=thinking_config
                            )
                            await websocket.send(json.dumps({
                                "type": "environmental_observation",
                                "text": response.text.strip().upper()
                            }))
                        except Exception as e: print(f"[\033[91mERROR\033[0m] Routine scan error: {e}")

                    # Commands handling
                    try:
                        msg = await asyncio.wait_for(websocket.recv(), timeout=0.001)
                        data = json.loads(msg)
                        if data.get("command") == "analyze" and client:
                            print(f"[\033[94mINFO\033[0m] Deep Analysis...")
                            await websocket.send(json.dumps({"type": "status_update", "message": "DEEP_SCAN_IN_PROGRESS"}))
                            _, buffer = cv2.imencode('.jpg', last_frame)
                            try:
                                response = await asyncio.to_thread(
                                    client.models.generate_content,
                                    model=model_id,
                                    contents=[
                                        types.Content(role="user", parts=[
                                            types.Part.from_bytes(mime_type="image/jpeg", data=buffer.tobytes()),
                                            types.Part.from_text(text="Você é o OMNILAB OS. Analise a imagem com precisão tática. Máximo 12 palavras.")
                                        ])
                                    ],
                                    config=thinking_config
                                )
                                await websocket.send(json.dumps({
                                    "type": "analysis_result",
                                    "text": response.text.strip().upper()
                                }))
                            except Exception as e: print(f"[\033[91mERROR\033[0m] Deep Analysis error: {e}")
                    except asyncio.TimeoutError: pass

                    cv2.imshow("OmniLab Vision", annotated_image)
                    if cv2.waitKey(1) & 0xFF == ord('q'): break

                cap.release()
                cv2.destroyAllWindows()
                break 

        except Exception as e:
            print(f"[\033[91mERROR\033[0m] Connection error: {e}")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(vision_loop())
