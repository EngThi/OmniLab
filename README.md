# OmniLab 🧪

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

OmniLab is an Iron Man-inspired **Tactical AI HUD** that merges local Computer Vision with the deep reasoning of **Gemini 3.1**. It's designed to be the invisible interface between thought and digital execution.

> "The bridge between physical gestures and autonomous actions."

## 🚀 Live Demo (Frontend Only)
**[View HUD Interface on GitHub Pages](https://EngThi.github.io/OmniLab/)**
*(Note: AI Analysis and Browser Agent require the local Python server to be running).*

## 🌟 Key Features

*   **Autonomous Browser Agent:** Integrated with **Playwright**. Trigger a real browser to search the web based on what the AI sees.
*   **AI Thinking Mode:** Powered by **Gemini 3.1 Flash**. The system "reasons" about the visual context before delivering tactical reports.
*   **Zero-Latency Vision:** Local hand tracking using **MediaPipe Tasks API**, ensuring the HUD follows your movements at 60 FPS.
*   **Tactical Interaction:** Control the system via **Voice Commands** ("Jarvis, search this"), **Gestures** (Pinch-to-Scan), or the **Manual Control Panel**.
*   **Automatic Fallback:** No webcam? No problem. The system enters an **Auto-Orbit Demo Mode** for reviewers.

## 🛠️ Quick Start

### 1. Prerequisites
- Python 3.10+
- A working Webcam (for local mode)
- Gemini API Key (Optional for Demo Mode)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/EngThi/OmniLab.git
cd OmniLab

# Set up virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt
python -m playwright install chromium
```

### 3. Configuration
Rename `.env.example` to `.env` and add your keys:
```bash
GEMINI_API_KEY=your_key_here
DEMO_MODE=false # Set to true to test without a webcam/API key
```

### 4. Run the System
```bash
# Terminal 1: Start the HUD Server & Agent
python server.py

# Terminal 2: Start the Vision Loop
python vision.py
```

## 🧠 How it works
1.  **Webcam**: Captures real-time frames via OpenCV.
2.  **MediaPipe**: Processes hand landmarks locally for instant interaction.
3.  **Gemini 3.1**: Analyzes visual data when a "Deep Scan" is triggered.
4.  **Playwright Agent**: Opens a headless (or visible) browser to execute tasks based on AI insights.
5.  **HUD**: A Three.js immersive interface rendered in your browser.

## 🚀 Deployment (GitHub Pages)
The HUD frontend can be hosted on GitHub Pages. To deploy:
1. Go to **Settings > Pages** in your repo.
2. Select the `main` branch and the `/static` folder (or use the provided deploy script).

---
*OmniLab - Building the future of human-AI interaction.*
