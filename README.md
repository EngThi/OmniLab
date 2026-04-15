# OmniLab: HOMES OS HUD

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

OmniLab is a gesture-controlled HUD interface that integrates computer vision, LLMs, and browser automation. 

**[Live demo (frontend only)](https://EngThi.github.io/OmniLab/)**
*Demo mode uses mouse control and mocked responses.*

## Architecture
The Python backend manages the core logic:
- **Vision Engine:** MediaPipe hand tracking processed server-side.
- **AI Router:** Fallback system using Gemini 3.0/3.1 models for high availability.
- **Automation:** Playwright agent for real-time research with stealth configuration.

## Features
- Hand tracking via MediaPipe (~60 FPS).
- PINCH gesture triggers visual analysis.
- Automatic model fallback on API quota/demand errors.
- Stealth browser automation with server-side flags.
- Voice command recognition (analyze, search, terminate).
- 3D interface using Three.js.

## Tech Stack
| Layer | Technology |
|---|---|
| HUD | Three.js, Vanilla JS, WebSockets |
| Vision | OpenCV, MediaPipe |
| AI | Gemini 3.0 Flash / 3.1 |
| Automation | Playwright (Chromium) |
| Backend | Python, FastAPI, WebSockets |

## Installation
```bash
git clone https://github.com/EngThi/OmniLab.git
cd OmniLab
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium

cp .env.example .env # Add GEMINI_API_KEY
```

## Running
```bash
python server.py  # Terminal 1
python vision.py  # Terminal 2
```
Access `http://localhost:8000`.
