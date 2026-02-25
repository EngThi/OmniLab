import cv2
import mediapipe as mp
import numpy as np
import math
import time

import mediapipe.solutions.drawing_utils as drawing_utils
import mediapipe.solutions.drawing_styles as drawing_styles

# Imports da nova API do MediaPipe
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

def draw_landmarks_on_image(rgb_image, detection_result):
    annotated_image = np.copy(rgb_image)
    h, w, _ = annotated_image.shape

    if detection_result.hand_landmarks:
        for hand_landmarks_list in detection_result.hand_landmarks:
            for landmark in hand_landmarks_list:
                cx, cy = int(landmark.x * w), int(landmark.y * h)
                cv2.circle(annotated_image, (cx, cy), 5, (0, 0, 255), cv2.FILLED) # Draw a red circle
            
    return annotated_image

# Opções do Hand Landmarker
base_options = python.BaseOptions(model_asset_path='OmniLab/hand_landmarker.task')
options = vision.HandLandmarkerOptions(base_options=base_options,
                                       running_mode=vision.RunningMode.VIDEO,
                                       num_hands=2,
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
    
    # Converter para a imagem do MediaPipe
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
    
    # Obter o timestamp para o modo de vídeo
    timestamp = int(time.time() * 1000)
    
    # Detectar landmarks
    detection_result = detector.detect_for_video(mp_image, timestamp)

    # Imagem para desenhar
    annotated_image = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

    # Se detectar mão
    if detection_result.hand_landmarks:
        # Desenhar a malha
        annotated_image = draw_landmarks_on_image(annotated_image, detection_result)

        # Loop através das mãos detectadas para a lógica da pinça
        for hand_landmarks in detection_result.hand_landmarks:
            h, w, _ = annotated_image.shape
            x1, y1 = int(hand_landmarks[4].x * w), int(hand_landmarks[4].y * h)
            x2, y2 = int(hand_landmarks[8].x * w), int(hand_landmarks[8].y * h)
            
            # Calcula a hipotenusa entre os duas pontas
            length = math.hypot(x2 - x1, y2 - y1)

            # Desenha uma linha entre os dedos com uma bolinha no centro
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            cv2.line(annotated_image, (x1, y1), (x2, y2), (255, 0, 255), 3)

            if length < 40:
                cv2.circle(annotated_image, (cx, cy), 15, (0, 255, 0), cv2.FILLED)
                # Saída que vou usar depois
                print(f" GESTURE_PINCH_ACTIVATE | X: {cx} | Y: {cy}")
            else:
                cv2.circle(annotated_image, (cx, cy), 10, (255, 0, 255), cv2.FILLED)

    cv2.imshow("OmniLab", annotated_image)

    # Espera 1ms e verifica se o 'q' foi apertado
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Limpa tudo no final
cap.release()
cv2.destroyAllWindows()