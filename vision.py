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

# Configurações do Ecossistema HOMES
HOMES_API_URL = os.getenv("HOMES_API_URL", "http://localhost:5000")

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    client = genai.Client(api_key=api_key)
    model_id = 'gemini-3.1-flash-lite-preview' 
else:
    print("AVISO: GEMINI_API_KEY não encontrada no .env. Análise de imagem não funcionará.")
    client = None

# Filas para comunicação entre threads
frame_queue: queue.Queue = queue.Queue(maxsize=5)
gesture_queue: queue.Queue = queue.Queue(maxsize=10)
running = True

# MediaPipe Setup
base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    num_hands=1,
    min_hand_detection_confidence=0.5,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.5
)

# Constantes de Calibração
PINCH_THRESHOLD_MS = 1500
SWIPE_THRESHOLD = 0.15
GESTURE_COOLDOWN = 0.8

def detect_gesture_type(landmarks, prev_landmarks):
    if not landmarks: return "none", 0.0, 0.5, 0.5
    wrist = landmarks[0]
    thumb_tip = landmarks[4]
    index_tip = landmarks[8]
    middle_tip = landmarks[12]
    ring_tip = landmarks[16]
    pinky_tip = landmarks[20]

    dist_pinch = math.hypot(thumb_tip.x - index_tip.x, thumb_tip.y - index_tip.y) * 1000
    is_pinching = dist_pinch < 45
    is_thumbs_up = (thumb_tip.y < index_tip.y - 0.1 and thumb_tip.y < middle_tip.y - 0.1 and index_tip.x > middle_tip.x)
    dists = [math.hypot(f.x - wrist.x, f.y - wrist.y) for f in [index_tip, middle_tip, ring_tip, pinky_tip]]
    is_fist = all(d < 0.25 for d in dists)

    gesture = "none"
    if prev_landmarks:
        dx = index_tip.x - prev_landmarks[8].x
        if abs(dx) > SWIPE_THRESHOLD:
            gesture = "swipe_right" if dx > 0 else "swipe_left"

    if is_fist: gesture = "fist"
    elif is_thumbs_up: gesture = "thumbs_up"
    elif is_pinching: gesture = "pinch"
    return gesture, dist_pinch, index_tip.x, index_tip.y

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
    pinch_start_time = None
    last_gesture_time = 0
    prev_landmarks = None
    fps_start_time = time.time()
    fps_counter = 0
    fps = 0

    with vision.HandLandmarker.create_from_options(options) as landmarker:
        while running and cap.isOpened():
            success, frame = cap.read()
            if not success: break
            fps_counter += 1
            if (time.time() - fps_start_time) > 1:
                fps, fps_counter, fps_start_time = fps_counter, 0, time.time()

            frame = cv2.flip(frame, 1)
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            timestamp = int(time.time() * 1000)
            results = landmarker.detect_for_video(mp_image, timestamp)

            gesture_name, pinch_progress, x, y = "none", 0.0, 0.5, 0.5
            if results.hand_landmarks:
                landmarks = results.hand_landmarks[0]
                gesture_name, dist, x, y = detect_gesture_type(landmarks, prev_landmarks)
                prev_landmarks = landmarks
                if gesture_name == "pinch":
                    if pinch_start_time is None: pinch_start_time = timestamp
                    else: pinch_progress = min((timestamp - pinch_start_time) / PINCH_THRESHOLD_MS, 1.0)
                else:
                    pinch_start_time = None
                    if gesture_name in ["swipe_left", "swipe_right", "thumbs_up", "fist"] and time.time() - last_gesture_time < GESTURE_COOLDOWN:
                        gesture_name = "none"
                    elif gesture_name != "none": last_gesture_time = time.time()

            payload = {"type": "gesture", "gesture": gesture_name, "x": float(x), "y": float(y), "pinch_progress": float(pinch_progress), "fps": fps, "timestamp": timestamp}
            try:
                if not gesture_queue.full(): gesture_queue.put_nowait(payload)
                if not frame_queue.full(): frame_queue.put_nowait(frame.copy())
            except: pass

            if os.getenv("SHOW_VISION") == "true":
                cv2.putText(frame, f"GESTURE: {gesture_name.upper()}", (10, 30), 1, 1.5, (0,255,0), 2)
                cv2.imshow("OmniLab Vision", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'): running = False

    cap.release()
    cv2.destroyAllWindows()

async def main():
    uri = "ws://localhost:8000/ws/vision"
    thinking_config = types.GenerateContentConfig(thinking_config=types.ThinkingConfig(include_thoughts=True))
    while running:
        try:
            async with websockets.connect(uri) as websocket:
                print("[\033[92mONLINE\033[0m] OmniLab Master Core Ativo")
                while running:
                    try:
                        data = gesture_queue.get_nowait()
                        await websocket.send(json.dumps(data))
                        if data["pinch_progress"] >= 1.0:
                            frame = None
                            try:
                                while not frame_queue.empty(): frame = frame_queue.get_nowait()
                            except: pass
                            if frame is not None: asyncio.create_task(trigger_analysis(websocket, frame, thinking_config))
                        if data["gesture"] == "thumbs_up":
                            await websocket.send(json.dumps({"type": "action", "action": "BROWSER_SEARCH_RECIPE"}))
                        elif data["gesture"] == "fist":
                            await websocket.send(json.dumps({"type": "action", "action": "HOMES_EMERGENCY_STOP"}))
                    except queue.Empty: pass
                    try:
                        msg = await asyncio.wait_for(websocket.recv(), timeout=0.001)
                        cmd = json.loads(msg)
                        if cmd.get("command") == "analyze":
                            frame = None
                            try:
                                while not frame_queue.empty(): frame = frame_queue.get_nowait()
                            except: pass
                            if frame is not None: asyncio.create_task(trigger_analysis(websocket, frame, thinking_config))
                    except asyncio.TimeoutError: pass
                    await asyncio.sleep(0.01)
        except Exception as e:
            print(f"[\033[91mOFFLINE\033[0m] Aguardando servidor... ({e})")
            await asyncio.sleep(2)

async def trigger_analysis(websocket, frame, config):
    if not client: return
    await websocket.send(json.dumps({"type": "status_update", "message": "DEEP_SCAN_HOMES"}))
    _, buf = cv2.imencode('.jpg', frame)
    try:
        response = await asyncio.to_thread(client.models.generate_content, model=model_id,
            contents=[types.Content(role="user", parts=[
                types.Part.from_bytes(mime_type="image/jpeg", data=buf.tobytes()),
                types.Part.from_text(text="Relatório tático. Identifique objetos e sugira integração no ecossistema HOMES.")
            ])], config=config)
        await websocket.send(json.dumps({"type": "analysis_result", "text": response.text.strip().upper()}))
    except: pass

if __name__ == "__main__":
    threading.Thread(target=vision_loop, daemon=True).start()
    asyncio.run(main())
