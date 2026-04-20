# OmniLab: Gesture-Controlled HUD Interface

OmniLab is a tactical HUD (Heads-Up Display) designed for real-time environment analysis and automated research using computer vision and large language models. The system integrates hand tracking, voice recognition, and browser automation into a unified 3D interface.

**[Live Demo (Cloudflare Tunnel)](https://bottle-wages-guestbook-floyd.trycloudflare.com/)**
*Note: Sensors must be initialized via the "START_SENSORS" button to enable hand tracking.*

## Core Architecture

The project is split into a Python-based backend and a Three.js frontend, communicating over low-latency WebSockets.

### Backend (Logic & Brain)
- **Host:** Hack Club Nest (Linux environment).
- **Vision Engine:** Utilizes MediaPipe Hand Landmarker for high-frequency coordinate tracking.
- **Cognitive Layer:** Powered by Gemini 3.1 Flash-Lite. It performs tactical analysis of captured frames and suggests follow-up research queries.
- **Automation:** A Playwright-based agent with stealth configurations. It performs real-time searches on DuckDuckGo to bypass datacenter IP restrictions and delivers visual results back to the HUD.

### Frontend (Interface)
- **3D Rendering:** Built with Three.js to provide a dynamic grid and interactive cursor elements.
- **Voice System:** Implements the Web Speech API for command recognition (Analyze, Search, Terminate).
- **Feedback Loop:** Includes visual cues like camera flashes for captures and color-coded state changes for hand gestures.

## Key Features

- **Interactive Gestures:**
  - **Thumbs Up:** Triggers an automatic environment scan.
  - **Fist:** Activates "Target Lock" mode, centering and scaling the cursor.
  - **Pinch:** Provides immediate UI feedback for precision tasks.
- **Voice Commands:** Supports natural language commands to initiate scans, confirm suggested research, or terminate remote browser sessions.
- **Resilient Search:** If primary search paths are blocked by CAPTCHAs, the system automatically routes traffic through privacy-focused search engines to ensure continuity.
- **Session Management:** The "Terminate" function performs a memory purge on the backend and resets the local state for a clean start.

## Local Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/EngThi/OmniLab.git
   cd OmniLab
   ```

2. **Setup environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python -m playwright install chromium
   ```

3. **Configure API Keys:**
   Create a `.env` file in the root directory and add your `GEMINI_API_KEY`.

4. **Execution:**
   ```bash
   # Start the server
   python server.py
   
   # For remote access, use a tunnel:
   ./cloudflared tunnel --url http://localhost:8000
   ```

## Technical Stack

| Component | Technology |
|---|---|
| Interface | Three.js / Vanilla JS / CSS |
| Backend | Python / FastAPI / WebSockets |
| Computer Vision | MediaPipe |
| AI Model | Gemini 3.1 Flash-Lite |
| Automation | Playwright / Playwright-Stealth |

License: MIT
