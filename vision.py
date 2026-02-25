
import cv2
import mediapipe as mp
import numpy as np
import math
import time
import json
import requests
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Configuração do servidor
SERVER_URL = "http://localhost:8000/ingest/gesture"

def send_gesture_to_hud(x, y, pinch_active):
    try:
        payload = {
            "type": "gesture",
            "x": x, # Normalizado 0-1
            "y": y, # Normalizado 0-1
            "pinch": pinch_active
        }
        # Envia para servidor local (timeout curto para não travar vídeo)
        requests.post(SERVER_URL, json=payload, timeout=0.05)
    except:
        pass # Ignora erros de conexão para não travar o loop

def draw_landmarks_on_image(rgb_image, detection_result):
    annotated_image = np.copy(rgb_image)
    h, w, _ = annotated_image.shape

    if detection_result.hand_landmarks:
        for hand_landmarks_list in detection_result.hand_landmarks:
            for landmark in hand_landmarks_list:
                cx, cy = int(landmark.x * w), int(landmark.y * h)
                cv2.circle(annotated_image, (cx, cy), 5, (0, 0, 255), cv2.FILLED) 
            
    return annotated_image

# Opções do Hand Landmarker
base_options = python.BaseOptions(model_asset_path='OmniLab/hand_landmarker.task')
options = vision.HandLandmarkerOptions(base_options=base_options,
                                       running_mode=vision.RunningMode.VIDEO,
                                       num_hands=1, # Focando em 1 mão para controle preciso
                                       min_hand_detection_confidence=0.5,
                                       min_hand_presence_confidence=0.5,
                                       min_tracking_confidence=0.5)

# Criar o detector
detector = vision.HandLandmarker.create_from_options(options)

# Iniciar a webcam
cap = cv2.VideoCapture(0)

print("Iniciando o olho OmniLab... Pressione Q para sair.")

while cap.isOpened():
    success, img = cap.read()
    if not success:
        print("Câmera não encontrada!")
        break

    # Espelhar movimento
    img = cv2.flip(img, 1)
    
    # Converter para RGB
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
    
    timestamp = int(time.time() * 1000)
    detection_result = detector.detect_for_video(mp_image, timestamp)

    annotated_image = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

    if detection_result.hand_landmarks:
        # Desenhar a malha
        annotated_image = draw_landmarks_on_image(annotated_image, detection_result)

        for hand_landmarks in detection_result.hand_landmarks:
            h, w, _ = annotated_image.shape
            
            # Pontos normalizados (0.0 a 1.0) para envio
            norm_x = hand_landmarks[8].x 
            norm_y = hand_landmarks[8].y

            # Pontos em pixel para desenho local
            x1, y1 = int(hand_landmarks[4].x * w), int(hand_landmarks[4].y * h)
            x2, y2 = int(hand_landmarks[8].x * w), int(hand_landmarks[8].y * h)
            
            length = math.hypot(x2 - x1, y2 - y1)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            
            cv2.line(annotated_image, (x1, y1), (x2, y2), (255, 0, 255), 3)

            is_pinch = length < 40
            
            if is_pinch:
                cv2.circle(annotated_image, (cx, cy), 15, (0, 255, 0), cv2.FILLED)
            else:
                cv2.circle(annotated_image, (cx, cy), 10, (255, 0, 255), cv2.FILLED)

            # Envia dados para o HUD via FastAPI
            send_gesture_to_hud(norm_x, norm_y, is_pinch)

    cv2.imshow("OmniLab Vision", annotated_image)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
