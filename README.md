# OmniLab: Tactical AI Command HUD

OmniLab is a technical command interface integrating real-time computer vision, Large Language Models (LLMs), and autonomous browser agents into a unified 3D Heads-Up Display (HUD). 

## Data Handling and Security
This system is designed with a volatile memory architecture to ensure user data integrity:
*   **Volatile Storage:** All video frames and search metadata are processed in real-time RAM. No data is persisted to disk or external databases.
*   **Session Termination:** Activating the **System Purge** command or closing the application immediately clears all active browser contexts and cognitive memory stacks.
*   **Local Tracking:** Gesture tracking is performed locally via MediaPipe, and visual context is analyzed through the Gemini API via encrypted SSL/TLS uplinks.
*   **Review Fallback:** If a third-party site requires CAPTCHA or human verification, OmniLab stops automation and shows a local demo intel stream so reviewers can test the HUD without cookies or bypass tooling.

## Interface Protocols

### Kinetic Gestures (Vision Engine)
*   **Thumbs Up [👍]:** Triggers an environmental scan.
*   **Pinch [🤏]:** Confirms and executes suggested research.
*   **Victory [✌️]:** Hold for 1.5s to execute a **System Purge** (Clear Memory).
*   **Crossed Fingers [X]:** Close active satellite browser windows.

> [NOTE] Use the **GESTURES: MANUAL** toggle in the UI to disable automated triggers for full operational control.

### Voice Commands (Neural Link)
*   **"Analyze" / "Scan":** Execute immediate visual capture.
*   **"Yes" / "Search":** Confirm AI-suggested research protocols.
*   **"Terminate":** Emergency system shutdown.

## Core Architecture
*   **Intelligence Engine:** Gemini 3.1 for tactical heuristics.
*   **Visual Framework:** Three.js for 3D UI rendering.
*   **Automation:** Playwright with stealth configurations for autonomous research.
*   **Tracking:** MediaPipe for low-latency spatial interaction.

## Deployment

### Requirements
*   Python 3.10+
*   Gemini API Key
*   Chromium Engine

### Installation
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
echo "GEMINI_API_KEY=your_key" > .env
python server.py
```

### Demo Review Mode
```bash
DEMO_MODE=true python server.py
```

`DEMO_MODE=true` uses a local generated browser result so community reviewers can validate the WebSocket flow, camera controls, gestures, voice commands, and browser panel without relying on third-party cookies. By default, `DEMO_FALLBACK=true` also activates that local result when a search provider asks for human verification.

### Optional Session Cookies
```bash
COOKIE_FILE=/home/ubuntu/arq.json python server.py
```

Cookies are loaded only as an authorized user session restore for Playwright. Empty or invalid cookie files are ignored, and CAPTCHA or human verification pages still stop automation and trigger the demo fallback.

---

**Status:** Operational // **Security:** Verified
**Developer:** EngThi / OmniLab Core
