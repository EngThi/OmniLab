# OmniLab: Tactical AI Command HUD

OmniLab is an advanced command interface that integrates real-time computer vision, Large Language Models (LLMs), and autonomous browser agents into a unified 3D Heads-Up Display (HUD). Built for high-performance environment analysis and decentralized research, it leverages Gemini 3.1 to provide tactical heuristics.

## Core Architecture

OmniLab operates on a distributed framework designed for speed, intelligence, and stealth:

*   **Intelligence Engine:** Powered by Gemini 3.1 Flash-Lite for real-time visual analysis and tactical suggestions.
*   **3D Visualization:** A dynamic Three.js HUD with parallax movement, starfields, and reative UI elements.
*   **Autonomous Research:** Playwright-based browser agents capable of searching via Google, Perplexity, and ChatGPT, with automatic DuckDuckGo fallback and advanced stealth/camouflage protocols.
*   **Spatial Interaction:** Real-time gesture recognition via MediaPipe for hands-free control.

## Interface Protocols

### Kinetic Gestures (Vision Engine)
*   **Thumbs Up [👍]:** Triggers an environmental scan and AI frame analysis.
*   **Victory [✌️]:** Hold for 1.5s to execute a **System Purge**, clearing memory and active sessions.
*   **Pinch [🤏]:** Hold to confirm and execute suggested research queries.
*   **Crossed Fingers [X]:** Close active satellite feed windows (Dual-hand gesture).

### Voice Commands (Neural Link)
*   **"Analyze" / "Scan":** Executes immediate visual capture for AI processing.
*   **"Yes" / "Search":** Confirms research protocols suggested by the AI.
*   **"Terminate" / "Close":** Emergency shutdown for active browser feeds.

## Deployment Specifications

### Requirements
*   Python 3.10+
*   Chromium Engine (Playwright)
*   Gemini API Key (configured in `.env`)

### Installation
```bash
# 1. Clone the repository and prepare the environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Configure Credentials (CRITICAL)
# Create a .env file in the root directory and add your key:
echo "GEMINI_API_KEY=your_api_key_here" > .env

# 3. Install dependencies
pip install -r requirements.txt
python -m playwright install chromium

# 4. Launch the system
python server.py
```

## Troubleshooting: API KEY ERROR
If the system displays "API KEY ERROR" during scans, ensure:
1. The `.env` file exists in the root directory.
2. The variable name is exactly `GEMINI_API_KEY`.
3. Your Gemini API key is valid and has not expired.


## Network & Connectivity
The system is optimized for remote deployment using **Cloudflare Zero-Trust Tunnels**, ensuring a secure and stable uplink even on mobile or restricted networks.

---

**Status:** Operational
**Developer:** EngThi / OmniLab Core
