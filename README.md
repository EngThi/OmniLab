# OmniLab: HOMES OS HUD

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**OmniLab** is a gesture-controlled AI HUD ("HOMES OS") that bridges computer vision, generative AI, and browser automation into a seamless 3D interface.

**[Live demo (frontend only)](https://EngThi.github.io/OmniLab/)**
*No webcam needed for demo mode — mouse controls the cursor, buttons run mocked responses with speech synthesis.*

## 🚀 Why a Backend?
While the HUD is a web interface, the **Python Backend** is the "Brain":
- **Vision Engine:** MediaPipe hand tracking processed in real-time.
- **AI Agent Router:** A robust fallback system that switches between Gemini 2.0 and 1.5 models to ensure 100% uptime even under high demand.
- **Stealth Browser:** Playwright agent that performs real-time research based on visual analysis, using stealth flags to bypass bot detection.

## 💎 Features
- **Hand Tracking:** ~60 FPS via MediaPipe (Vision Hub).
- **Pinch-to-Scan:** Trigger deep visual analysis with a gesture.
- **AI Model Router:** Automatically retries analysis using fallback models if the primary API is busy.
- **Stealth Agent:** Playwright Chromium automation with server-side stability flags (`--no-sandbox`).
- **Voice Commands:** Integrated recognition for "analyze", "search", and "terminate".
- **Dynamic HUD:** Three.js 3D interface that follows gestures in 3D space.

## 🛠️ Tech Stack
| Layer | Technology |
|---|---|
| **HUD (UI)** | Three.js + Vanilla JS + WebSockets |
| **Vision** | OpenCV + MediaPipe Tasks |
| **AI** | Gemini 3.0 Flash (Preview) with 3.1 Fallback |
| **Automation** | Playwright (Chromium) |
| **Backend** | Python + FastAPI + WebSocket |

## 📦 Setup & Run
```bash
# Clone and install
git clone https://github.com/EngThi/OmniLab.git
cd OmniLab
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium

# Config keys
cp .env.example .env   # Add GEMINI_API_KEY

# Run the Brain
python server.py  # Terminal 1
python vision.py  # Terminal 2
```
Open `http://localhost:8000` to start the experience.
