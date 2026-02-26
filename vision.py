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
    model = genai.GenerativeModel('gemini-1.5-flash')
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

async def vision_loop():
    uri = "ws://localhost:8000/ws/vision"
    
    while True: # Loop de reconexão
        try:
            async with websockets.connect(uri) as websocket:
                print("OmniLab Vision Conectada via WebSocket!")
                cap = cv2.VideoCapture(0)
                
                if not cap.isOpened():
                    print("Erro: Câmera não encontrada!")
                    return

                last_frame = None

                while cap.isOpened():
                    success, img = cap.read()
                    if not success:
                        break

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

                    # Verificar comandos (Não-bloqueante)
                    try:
                        msg = await asyncio.wait_for(websocket.recv(), timeout=0.001)
                        data = json.loads(msg)
                        
                        if data.get("command") == "analyze" and model:
                            print("Comando de análise recebido! Chamando Gemini...")
                            _, buffer = cv2.imencode('.jpg', last_frame)
                            
                            # Rodar Gemini em thread separada para não travar o loop de vídeo
                            loop = asyncio.get_event_loop()
                            response = await loop.run_in_executor(None, lambda: model.generate_content([
                                "Descreva o que você vê nesta imagem de forma curta e técnica para um HUD de assistente IA.",
                                {"mime_type": "image/jpeg", "data": buffer.tobytes()}
                            ]))
                            
                            print("Análise concluída.")
                            await websocket.send(json.dumps({
                                "type": "analysis_result",
                                "text": response.text
                            }))
                    except asyncio.TimeoutError:
                        pass
                    except Exception as e:
                        print(f"Erro no comando: {e}")

                    cv2.imshow("OmniLab Vision", annotated_image)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        cap.release()
                        cv2.destroyAllWindows()
                        return

                cap.release()
                cv2.destroyAllWindows()

        except websockets.exceptions.ConnectionClosed:
            print("Conexão com servidor perdida. Tentando reconectar em 3s...")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"Erro na conexão: {e}. Tentando reconectar em 3s...")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(vision_loop())
