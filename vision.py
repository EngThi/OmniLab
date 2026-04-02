import cv2
import mediapipe as mp
import numpy as np
import time
import math
import json
import asyncio
import websockets
import os
import threading
import queue
from typing import Optional
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

# Filas para comunicação entre threads
frame_queue: queue.Queue = queue.Queue(maxsize=5)
gesture_queue: queue.Queue = queue.Queue(maxsize=10)
running = True

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

PINCH_THRESHOLD_MS = 1500

def draw_landmarks_on_image(rgb_image, detection_result):
    annotated_image = np.copy(rgb_image)
    h, w, _ = annotated_image.shape
    if detection_result.hand_landmarks:
        for hand_landmarks_list in detection_result.hand_landmarks:
            for landmark in hand_landmarks_list:
                cx, cy = int(landmark.x * w), int(landmark.y * h)
                cv2.circle(annotated_image, (cx, cy), 5, (0, 0, 255), cv2.FILLED) 
    return annotated_image

def vision_loop():
    global running
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    pinch_start_time = None
    fps_start_time = time.time()
    fps_counter = 0
    fps = 0

    with vision.HandLandmarker.create_from_options(options) as landmarker:
        while running and cap.isOpened():
            success, frame = cap.read()
            if not success: break

            fps_counter += 1
            if (time.time() - fps_start_time) > 1:
                fps = fps_counter
                fps_counter = 0
                fps_start_time = time.time()

            frame = cv2.flip(frame, 1)
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
            timestamp = int(time.time() * 1000)
            results = landmarker.detect_for_video(mp_image, timestamp)

            pinch = False
            pinch_progress = 0.0
            x, y = 0.5, 0.5
            annotated = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

            if results.hand_landmarks:
                annotated = draw_landmarks_on_image(annotated, results)
                for hand_landmarks in results.hand_landmarks:
                    h, w, _ = annotated.shape
                    x, y = hand_landmarks[0][8].x, hand_landmarks[0][8].y # Landmark do dedo indicador
                    x1, y1 = int(hand_landmarks[0][4].x * w), int(hand_landmarks[0][4].y * h)
                    x2, y2 = int(hand_landmarks[0][8].x * w), int(hand_landmarks[0][8].y * h)
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    length = math.hypot(x2 - x1, y2 - y1)
                    
                    pinch = length < 40
                    if pinch:
                        if pinch_start_time is None:
                            pinch_start_time = timestamp
                        else:
                            elapsed = timestamp - pinch_start_time
                            pinch_progress = min(elapsed / PINCH_THRESHOLD_MS, 1.0)
                    else:
                        pinch_start_time = None

                    cv2.line(annotated, (x1, y1), (x2, y2), (255, 0, 255), 2)
                    color = (0, 255, 0) if pinch else (255, 0, 255)
                    cv2.circle(annotated, (cx, cy), int(10 + (pinch_progress * 10)), color, cv2.FILLED)

            payload = {
                "type": "gesture",
                "x": float(x),
                "y": float(y),
                "pinch": bool(pinch),
                "fps": int(fps),
                "pinch_progress": float(pinch_progress),
                "timestamp": timestamp
            }

            try:
                if not frame_queue.full():
                    frame_queue.put_nowait(frame.copy())
                if not gesture_queue.full():
                    gesture_queue.put_nowait(payload)
            except: pass

            cv2.putText(annotated, f"FPS: {fps}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("OmniLab Vision", annotated)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                running = False
                break

    cap.release()
    cv2.destroyAllWindows()

async def main():
    uri = "ws://localhost:8000/ws/vision"
    thinking_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(include_thoughts=True)
    )
    is_analyzing = False

    while running:
        try:
            async with websockets.connect(uri) as websocket:
                print("[\033[92mSUCCESS\033[0m] WS Client Conectado!")
                while running:
                    # Enviar gestos da fila
                    try:
                        while not gesture_queue.empty():
                            data = gesture_queue.get_nowait()
                            await websocket.send(json.dumps(data))
                            
                            # Lógica de disparo por pinch_progress no client side
                            if data["pinch_progress"] >= 1.0 and not is_analyzing:
                                is_analyzing = True
                                last_frame = None
                                try:
                                    while not frame_queue.empty():
                                        last_frame = frame_queue.get_nowait()
                                except: pass
                                
                                if last_frame is not None:
                                    asyncio.create_task(trigger_scan(websocket, last_frame, thinking_config))
                            elif data["pinch_progress"] == 0:
                                is_analyzing = False
                    except queue.Empty: pass

                    # Receber comandos
                    try:
                        msg = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                        cmd = json.loads(msg)
                        if cmd.get("command") == "analyze":
                            last_frame = None
                            try:
                                while not frame_queue.empty():
                                    last_frame = frame_queue.get_nowait()
                            except: pass
                            
                            if last_frame is not None:
                                asyncio.create_task(trigger_scan(websocket, last_frame, thinking_config))
                    except asyncio.TimeoutError: pass
                    
                    await asyncio.sleep(0.01)
        except Exception as e:
            print(f"WS Error: {e}")
            await asyncio.sleep(2)

async def trigger_scan(websocket, frame, config):
    if client is None: return
    print(f"[\033[94mINFO\033[0m] Iniciando Deep Scan...")
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
        print(f"Scan error: {e}")

if __name__ == "__main__":
    vision_thread = threading.Thread(target=vision_loop, daemon=True)
    vision_thread.start()
    asyncio.run(main())
