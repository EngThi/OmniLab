# OmniLab: Tactical AI Command HUD

OmniLab is a high-performance 3D command interface that bridges real-time computer vision, Large Language Models (LLMs), and autonomous browser agents into a unified Heads-Up Display (HUD). 

Designed for **FlavorTown Hackers**, it provides a cinematic, hands-free way to research and analyze your environment.

---

## 🛡️ Privacy & Security Protocol (Zero-Knowledge Design)
We take your data safety seriously. OmniLab was built with the following security heuristics:
*   **Volatile Memory:** No images, video frames, or search histories are stored on the server. All processing happens in real-time RAM and is purged upon session termination.
*   **Encrypted Uplink:** The system uses SSL/TLS (via Caddy & DuckDNS) for all remote communications.
*   **Transparency:** Camera access is used exclusively for local gesture tracking (MediaPipe) and context analysis (Gemini API). 
*   **Privacy Shield:** The "System Purge" command (`Victory [✌️]` gesture or button) instantly clears all active browser sessions and cognitive memory.

## 🎮 Interface Protocols

### Kinetic Gestures (Vision Engine)
*   **Thumbs Up [👍]:** Triggers an environmental scan.
*   **Pinch [🤏]:** Confirms and executes suggested research.
*   **Victory [✌️]:** Hold for 1.5s to **System Purge** (Clear Memory).
*   **Crossed Fingers [X]:** Close active browser windows.

> [TIP] Use the **GESTURES: MANUAL** toggle in the UI if you want full control without automatic triggers.

### Voice Commands (Neural Link)
*   **"Analyze" / "Scan":** Execute immediate capture.
*   **"Yes" / "Search":** Confirm AI suggestions.
*   **"Terminate":** Emergency shutdown.

---

## ⚙️ Core Architecture
*   **Intelligence:** Gemini 3.1 (Flash/Pro) for tactical heuristics.
*   **Visuals:** Three.js 3D environment with parallax starfields.
*   **Automation:** Playwright with Stealth Mode for autonomous intelligence gathering.
*   **Tracking:** MediaPipe for low-latency spatial interaction.

## 🚀 Deployment

### Requirements
*   Python 3.10+
*   Gemini API Key
*   Chromium Engine

### Quick Start
```bash
# 1. Setup Environment
python -m venv venv
source venv/bin/activate

# 2. Install Dependencies
pip install -r requirements.txt
python -m playwright install chromium

# 3. Configure .env
echo "GEMINI_API_KEY=your_key" > .env

# 4. Launch
python server.py
```

---

**Status:** Operational // **Security:** Verified
**Developer:** EngThi / OmniLab Core
