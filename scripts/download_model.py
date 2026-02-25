#!/usr/bin/env python3
"""
Baixa o modelo MediaPipe Hand Landmarker.
Rode uma vez antes de usar o vision.py:
    python scripts/download_model.py

O arquivo .task NÃO vai pro Git (está no .gitignore).
"""
import urllib.request
import os
import sys

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODEL_PATH = "hand_landmarker.task"

def _progress(count, block_size, total_size):
    if total_size > 0:
        percent = min(int(count * block_size * 100 / total_size), 100)
        bar = '#' * (percent // 5) + '-' * (20 - percent // 5)
        sys.stdout.write(f"\r   [{bar}] {percent}%")
        sys.stdout.flush()

def download_model():
    if os.path.exists(MODEL_PATH):
        print(f"✅ Modelo já existe: {MODEL_PATH} — nada a fazer.")
        return

    print(f"⬇️  Baixando Hand Landmarker (~7.8MB)...")
    print(f"   Fonte: {MODEL_URL}")
    print()

    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH, reporthook=_progress)
    print(f"\n\n✅ Salvo em: {MODEL_PATH}")
    print("   Pode rodar agora: python vision.py")

if __name__ == "__main__":
    download_model()
