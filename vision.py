import cv2
import mediapipe as mp
import math

# Inicializando o Mediapipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)
mp_draw = mp.solutions.drawing_utils

# Iniciar a webcam (Acho que vou usar o PC por agora)
cap =cv2.VideoCapture(0)

print("Iniciando o olho OmniLab... Presione Q para sair.")

while cap.isOpened():
    sucess, img = cap.read()
    if not sucess:
        print("Câmera não encontrada!")
        break

    # Espelhao movimento
    img = cv2.flip(img, 1)
    h, w, c = img.shape

    img_rgb = cv2.cvtColor(img, cv2.COLOR_GGR2RGB)
    results = hands.process(img_rgb)

    # Se detectar mão
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            # Malha cibernética na mão
            mp_draw.draw_landmarks(img, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            x1, y1 = int(hand_landmarks.landmark[4].x * w), int(hand_landmarks.landmark[4].y * h)
            x2, y2 = int(hand_landmarks.landmark[8].x * w), int(hand_landmarks.landmark[8].y * h)
            
            # Calcula a hipotenusa entre os duas pontas
            lenght = math.hypot(x2 - x1, y2 - y1)

            # Desenha uma linha entre os dedos com uma bolinha no centro
            cx, cy = (x1 + x2) // 2
            cv2.line(img, (x1, y1), (x2, y2), (255, 0, 255), 3)

            if lenght < 40:
                cv2.circle(img, (cx, cy), 15, (0, 255, 0), cv2.FILLED)

                # Saída que vou usar depois
                print(f" GESTURE_PINCH_ACTIVATE | X: {cx} | Y: {cy}")
            else:
                cv2.circle(img, cx, cy, 10, (255, 0, 255), cv2.FILLED)

    cv2.imshow("OmniLab", img)

    # Espera 1ms e verfica se o 'q' foi apertado
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Limpa tduo no final
cap.release()
cv2.destroyAllWindows()