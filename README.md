# OmniLab

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Gesture-controlled AI HUD. Hand tracking runs locally via MediaPipe, a Python
backend sends frames to Gemini for analysis, and a Three.js interface in the
browser renders the result in real time. Pinch gesture triggers a deep scan;
the AI describes what it sees and optionally fires a Playwright browser agent
to search the web.

**[Live demo (frontend only)](https://EngThi.github.io/OmniLab/)**
No webcam needed — mouse controls the cursor, buttons run mocked responses
with speech synthesis.

## Features

- Hand tracking at ~60 FPS via MediaPipe Tasks API (runs fully local)
- Gemini Flash for visual analysis on pinch-to-scan trigger
- Playwright agent opens a real browser to act on AI output
- Voice commands: say "analyze", "search", or "terminate"
- Auto demo mode when server is offline — no broken screen for reviewers

## Setup

```bash
git clone https://github.com/EngThi/OmniLab.git
cd OmniLab
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env   # add GEMINI_API_KEY
```

## Run

```bash
# Terminal 1
python server.py

# Terminal 2
python vision.py
```

Open `http://localhost:8000` and allow camera access.

## Stack

| Layer | Tech |
|---|---|
| Vision | OpenCV + MediaPipe Tasks |
| AI | Gemini 1.5 Flash |
| Browser agent | Playwright (Chromium) |
| Backend | Python + FastAPI + WebSocket |
| Frontend | Three.js + vanilla JS |
