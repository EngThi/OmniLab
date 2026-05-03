# OmniLab: Visual Research HUD

OmniLab is a browser-based command HUD for turning a live camera view into useful research. It combines local hand tracking, Gemini visual analysis, voice/gesture controls, and Perplexity-powered web research in a single Three.js interface.

The main workflow is:

1. Open the deployed HUD.
2. Activate the camera.
3. Run an environment scan or hold a thumbs-up gesture.
4. Gemini analyzes the current frame and suggests a search target.
5. Say "yes", say "search", pinch, or press **EXECUTE RESEARCH**.
6. OmniLab sends the query to Perplexity Search and renders a visual answer with sources.

The operational automation workflow is:

1. Put a URL in **TARGET_IDENTIFIER**.
2. Press **WATCH TARGET**.
3. OmniLab repeatedly checks the target for availability and content changes.
4. The HUD reports status, latency, title, and content-change events.
5. Press **STOP WATCH** or **SHUTDOWN SYSTEM** to stop monitoring.

## What It Is Useful For

OmniLab is not a static demo page. It is built around real workflows that are useful when your hands or attention are busy:

*   **Visual research:** Point the camera at an object, text, hardware, a book, or a setup, then search what it is or what to do next.
*   **Troubleshooting:** Scan an error screen, device, wiring setup, or tool and turn the visual context into a focused web query.
*   **Source-backed answers:** Manual search and scan-generated search both return Perplexity answers with citations instead of placeholder browser images.
*   **Session continuity:** Follow-up searches can continue the same Perplexity conversation, so "what is this?" can become "how do I fix it?" without losing context.
*   **Watchtower monitoring:** Turn any URL into a live monitor for uptime/content changes directly inside the HUD.
*   **Hands-light operation:** Thumbs-up scans the environment, pinch confirms suggested research, and voice commands can trigger scan/search/purge.

## Data Handling and Security

OmniLab handles camera and search data deliberately. There is no database and no analytics pipeline in this project.

| Data | Where It Is Processed | Persistence |
| --- | --- | --- |
| Hand landmarks | Browser, through MediaPipe Tasks for Web | Not stored |
| Camera frame for scan | One JPEG frame is sent to the FastAPI backend, then to Gemini for analysis | Not written to disk |
| Suggested search query | Backend RAM and browser UI state | Cleared on purge/reload |
| Perplexity conversation UUID/read-write token | Backend RAM for the active OmniLab session | Cleared by **SHUTDOWN SYSTEM** or service restart |
| Perplexity account token/API keys | Server environment/config files | Required secret for production search |
| Watchtower monitor snapshots | Backend RAM and browser log | Cleared when stopped, purged, disconnected, or restarted |
| Optional Playwright cookies/profile | Server filesystem, only if configured by the deployer | Used only for authorized browser-session fallback |

Security behavior:

*   **No camera recording:** The app captures only the current frame when a scan is requested.
*   **No project database:** Frames, gesture data, search queries, and answers are not saved to a DB.
*   **Purge clears runtime memory:** **SHUTDOWN SYSTEM** clears Gemini context and Perplexity session state held in backend RAM.
*   **Watchtower is ephemeral:** URL checks run as an in-memory task tied to the active WebSocket session.
*   **Real providers only:** Search uses Perplexity first, then configured search APIs/fallback providers. It does not fabricate demo results.
*   **Transparent fallback:** If a browser provider requires verification, OmniLab reports that state or reroutes to another real provider instead of hiding it behind fake content.
*   **Secrets stay server-side:** Perplexity tokens, Gemini keys, Brave keys, cookies, and proxy credentials are never sent to the browser.

## Reviewer Test Path

Fastest way to test the real functionality:

1. Press **ACTIVATE CAMERA** and grant camera permission.
2. Show an object, printed text, screen, or hardware setup to the camera.
3. Press **ENVIRONMENT SCAN** or use thumbs-up.
4. Wait for the suggested query to appear in the target field.
5. Press **EXECUTE RESEARCH** or say "yes/search".
6. Confirm that the HUD opens a visual Perplexity answer with sources.

Manual fallback path:

1. Type any real query in **TARGET_IDENTIFIER**.
2. Press **EXECUTE RESEARCH**.
3. The HUD should open a source-backed answer without needing camera access.

Automation test path:

1. Type `https://omnilab1.duckdns.org/` or another public URL in **TARGET_IDENTIFIER**.
2. Press **WATCH TARGET**.
3. The HUD should log `WATCH ONLINE` with HTTP status, latency, and page title.
4. Press **STOP WATCH** to end the automation.

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

### Watchtower Automation
*   **WATCH TARGET:** Starts a real backend monitor for the URL in the target field.
*   **STOP WATCH:** Cancels the active monitor.
*   **SHUTDOWN SYSTEM:** Clears session memory and stops active monitoring.

## Core Architecture
*   **Vision analysis:** Gemini analyzes explicit scan frames and returns a short tactical summary plus `[search: term]`.
*   **Web research:** Perplexity Web MCP is the primary search engine and returns real answers with sources.
*   **Automation:** Watchtower runs an in-memory async monitor that checks URL status, latency, title, and content hash on an interval.
*   **Fallback search:** Google Programmable Search, Brave Search, DuckDuckGo HTML, Yahoo/browser fallback, depending on configured keys and provider availability.
*   **Visual framework:** Three.js renders the HUD and MediaPipe Tasks for Web tracks hands locally in the browser.
*   **Backend:** FastAPI WebSockets coordinate HUD events, scan analysis, search sessions, and screenshot/result rendering.

## Current Boundaries

These are intentional constraints, not hidden demo behavior:

*   Camera permission is required for environment scans. Manual research works without camera access.
*   Perplexity/LLM/search providers require valid server-side credentials and may consume quota.
*   Watchtower monitors public HTTP(S) targets only; it does not log into private dashboards or bypass access controls.
*   Browser automation is kept as fallback because datacenter IPs can trigger Google/Cloudflare verification.
*   The app does not click through arbitrary third-party websites on behalf of the user; it returns research answers and source links.
*   Voice recognition uses the browser's Web Speech API, so support depends on the reviewer's browser.

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

### Optional Session Cookies
```bash
COOKIE_FILE=/home/ubuntu/arq.json python server.py
```

Cookies are loaded only as an authorized user session restore for Playwright. The backend also reuses `PLAYWRIGHT_USER_DATA_DIR` as the persistent Chromium profile, so a VM can preserve an already-authorized search/account session. Empty or invalid cookie files are ignored.

### Optional Search Providers
```bash
GOOGLE_CSE_API_KEY=your_key
GOOGLE_CSE_CX=your_search_engine_id
BRAVE_SEARCH_API_KEY=your_brave_search_key
PWM_COMMAND=/home/ubuntu/.local/bin/pwm
PWM_PYTHON=/home/ubuntu/.local/share/pipx/venvs/perplexity-web-mcp-cli/bin/python
PERPLEXITY_TOKEN_FILE=/home/ubuntu/.config/perplexity-web-mcp/token
PERPLEXITY_SESSION_TURNS=4
WATCH_INTERVAL_SECONDS=45
WATCH_TIMEOUT_SECONDS=12
SEARCH_PROXY_FILE=/home/ubuntu/webshare_proxies.txt
```

For `WEB SEARCH`, OmniLab tries an authenticated Perplexity Web MCP library session first and renders the answer plus citations into the HUD. If that fails, it tries configured official search APIs, then DuckDuckGo HTML results without a key, then real browser search. The frontend can continue the same Perplexity conversation by preserving the backend UUID and read/write token for the OmniLab session, including searches generated from camera scans.

---

**Status:** Operational // **Mode:** Real search, no demo fallback
**Developer:** EngThi / OmniLab Core
