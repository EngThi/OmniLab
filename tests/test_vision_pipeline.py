import asyncio
import websockets
import json
import base64
import cv2
import numpy as np

async def test_vision_pipeline():
    uri = "ws://localhost:8000/ws/hud"
    print("🚀 Simulando Browser enviando frame para o HUD...")
    
    # Cria um frame preto com um ponto branco (simulando uma mão)
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(img, (320, 240), 50, (255, 255, 255), -1)
    _, buffer = cv2.imencode('.jpg', img)
    img_base64 = base64.b64encode(buffer).decode('utf-8')

    try:
        async with websockets.connect(uri) as ws:
            # Envia o frame
            payload = {"type": "frame", "image": img_base64}
            await ws.send(json.dumps(payload))
            print("📤 Frame enviado para /ws/hud")
            
            # Aguarda a resposta do vision.py (que o server repassa para o HUD)
            print("⏳ Aguardando coordenada de volta do Vision Engine...")
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                data = json.loads(msg)
                if data.get("type") == "gesture":
                    print(f"✅ SUCESSO! Recebi coordenada: x={data['x']}, y={data['y']}, gesture={data['gesture']}")
                    break
    except Exception as e:
        print(f"❌ Erro no pipeline: {e}")

if __name__ == "__main__":
    asyncio.run(test_vision_pipeline())
