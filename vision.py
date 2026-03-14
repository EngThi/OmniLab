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
import google.generativeai as genai
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Carregar variáveis de ambiente e configurar Gemini
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-3-flash-preview')
else:
    print("AVISO: GEMINI_API_KEY não encontrada no .env. Análise de imagem não funcionará.")
    model = None

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

async def vision_loop():
    uri = "ws://localhost:8000/ws/vision"
    
    while True: # Loop de reconexão
        try:
            async with websockets.connect(uri) as websocket:
                print("OmniLab Vision Conectada via WebSocket!")
                cap = cv2.VideoCapture(0)
                
                if not cap.isOpened():
                    print("Erro: Câmera não encontrada!")
                    await asyncio.sleep(5)
                    continue

                last_frame = None

                while cap.isOpened():
                    success, img = cap.read()
                    if not success:
                        break

                    try:
                        validate_frame(img)
                    except ValueError as e:
                        print(f"Erro de validação: {e}")
                        continue

                    # Espelhar e processar frame
                    img = cv2.flip(img, 1)
                    last_frame = img.copy()
                    
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
                    
                    timestamp = int(time.time() * 1000)
                    detection_result = detector.detect_for_video(mp_image, timestamp)

                    annotated_image = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

                    gesture_data = {"type": "gesture", "x": 0.5, "y": 0.5, "pinch": False}

                    if detection_result.hand_landmarks:
                        annotated_image = draw_landmarks_on_image(annotated_image, detection_result)
                        
                        for hand_landmarks in detection_result.hand_landmarks:
                            h, w, _ = annotated_image.shape
                            
                            # Pontos para controle (Dedo indicador)
                            norm_x = hand_landmarks[8].x 
                            norm_y = hand_landmarks[8].y

                            # Pontos em pixel para pinch (Polegar e Indicador)
                            x1, y1 = int(hand_landmarks[4].x * w), int(hand_landmarks[4].y * h)
                            x2, y2 = int(hand_landmarks[8].x * w), int(hand_landmarks[8].y * h)
                            
                            length = math.hypot(x2 - x1, y2 - y1)
                            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                            
                            cv2.line(annotated_image, (x1, y1), (x2, y2), (255, 0, 255), 2)
                            
                            is_pinch = length < 40
                            if is_pinch:
                                cv2.circle(annotated_image, (cx, cy), 15, (0, 255, 0), cv2.FILLED)
                            else:
                                cv2.circle(annotated_image, (cx, cy), 10, (255, 0, 255), cv2.FILLED)

                            gesture_data = {
                                "type": "gesture",
                                "x": norm_x,
                                "y": norm_y,
                                "pinch": is_pinch
                            }

                    # Enviar dados de gesto
                    await websocket.send(json.dumps(gesture_data))

                    # Periodic environmental scan
                    current_time = int(time.time() * 1000)
                    if model and (current_time - last_scan_time > SCAN_INTERVAL):
                        print(f"[\033[94mINFO\033[0m] Performing periodic environmental scan...")
                        await websocket.send(json.dumps({
                            "type": "status_update",
                            "message": "SCANNING... ANALYZING PHOTONS"
                        }))
                        
                        _, buffer = cv2.imencode('.jpg', last_frame)
                        try:
                            loop = asyncio.get_event_loop()
                            prompt = (
                                "You are OMNILAB OS, a tactical AI assistant. "
                                "Provide a brief, technical, HUD-style observation of the current environment (e.g., lighting, notable objects, potential anomalies). "
                                "Keep it under 15 words."
                            )
                            response = await loop.run_in_executor(None, lambda: model.generate_content([prompt, {"mime_type": "image/jpeg", "data": buffer.tobytes()}]))
                            observation_text = response.text.strip().upper()
                            await websocket.send(json.dumps({
                                "type": "environmental_observation",
                                "text": observation_text
                            }))
                            last_scan_time = current_time # Update scan time only on success
                        except Exception as e:
                            print(f"[\033[91mERROR\033[0m] Periodic scan failed: {e}")
                            await websocket.send(json.dumps({
                                "type": "status_update",
                                "message": "SCAN FAILED"
                            }))
                    
                    # Verificar comandos (Não-bloqueante)
                    try:
                        msg = await asyncio.wait_for(websocket.recv(), timeout=0.001)
                        data = json.loads(msg)
                        
                        if data.get("command") == "analyze":
                            if model:
                                print(f"[\033[94mINFO\033[0m] Comando de análise recebido. Capturando frame...")
                                # Notificar HUD que a análise começou
                                await websocket.send(json.dumps({
                                    "type": "status_update",
                                    "message": "SCANNING... ANALYZING PHOTONS"
                                }))
                                
                                _, buffer = cv2.imencode('.jpg', last_frame)
                                
                                # Rodar Gemini em thread separada com prompt aprimorado
                                try:
                                    loop = asyncio.get_event_loop()
                                    prompt = (
                                        "Você é o OMNILAB OS, um sistema de IA tático. "
                                        "Analise a imagem e forneça uma descrição técnica, concisa (máximo 15 palavras) "
                                        "e em tom de relatório militar/HUD. Foque em objetos, iluminação e pessoas."
                                    )
                                    response = await loop.run_in_executor(None, lambda: model.generate_content([
                                        prompt,
                                        {"mime_type": "image/jpeg", "data": buffer.tobytes()}
                                    ]))
                                    analysis_text = response.text.strip().upper()
                                except Exception as e:
                                    print(f"[\033[91mERROR\033[0m] Gemini failed: {e}")
                                    analysis_text = "ERROR: AI_MODULE_OFFLINE"
                            else:
                                print(f"[\033[93mWARN\033[0m] Gemini API Key missing.")
                                analysis_text = "ERROR: API_KEY_NOT_CONFIGURED"

                            print("Análise concluída.")
                            await websocket.send(json.dumps({
                                "type": "analysis_result",
                                "text": analysis_text
                            }))
                    except asyncio.TimeoutError:
                        pass
                    except Exception as e:
                        print(f"[\033[91mERROR\033[0m] Command processing error: {e}")
