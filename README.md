# OmniLab: Visual Research HUD

OmniLab is a browser-based command HUD for turning a live camera view into useful research. It combines local hand tracking, Gemini visual analysis, voice/gesture controls, and Perplexity-powered web research in a single Three.js interface.

The main workflow is:

1. Open the deployed HUD.
2. Activate the camera.
3. Run an environment scan or hold a thumbs-up gesture.
4. Gemini analyzes the current frame and suggests a search target.
5. Say "yes", say "search", pinch, or press **EXECUTE RESEARCH**.
6. OmniLab sends the query to Perplexity Search and renders a visual answer with clickable source links.
7. The result is saved locally in the browser's **ARTIFACTS** panel, where it can be reopened or deleted.

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
*   **Clickable sources:** The visual answer is paired with source chips that open in a new tab or can be copied.
*   **Session continuity:** Follow-up searches can continue the same Perplexity conversation. The browser preserves the OmniLab session ID across reloads so users can return to the same research thread while backend session memory is still active.
*   **Generated image assets:** Image-generation requests use the Perplexity file/app model, then OmniLab asks the same conversation for the direct generated asset URL and renders it when available.
*   **Local artifact library:** Searches, scan frames, result screenshots, source links, and generated image URLs are stored in the user's browser IndexedDB with individual delete and delete-all controls.
*   **Watchtower monitoring:** Turn any URL into a live monitor for uptime/content changes directly inside the HUD.
*   **Hands-light operation:** Thumbs-up scans the environment, pinch confirms suggested research, and voice commands can trigger scan/search/purge.

## Data Handling and Security

OmniLab handles camera and search data deliberately. There is no database and no analytics pipeline in this project.

| Data | Where It Is Processed | Persistence |
| --- | --- | --- |
| Hand landmarks | Browser, through MediaPipe Tasks for Web | Not stored |
| Camera frame for scan | One JPEG frame is sent to the FastAPI backend, then to Gemini for analysis | Not written to disk |
| Suggested search query | Backend RAM and browser UI state | Cleared on purge/reload unless saved as a local artifact |
| Perplexity conversation UUID/read-write token | Backend RAM for the active OmniLab session | Cleared by **SHUTDOWN SYSTEM** or service restart |
| Browser session ID | Browser `localStorage` | Persists across reloads until reset/purged |
| Search/result artifacts | Browser IndexedDB | User-controlled: delete individual items or **DELETE ALL** |
| Generated image URLs | Browser IndexedDB when returned by provider | User-controlled: delete individual items or **DELETE ALL** |
| Perplexity account token/API keys | Server environment/config files | Required secret for production search |
| Watchtower monitor snapshots | Backend RAM and browser log | Cleared when stopped, purged, disconnected, or restarted |
| Optional Playwright cookies/profile | Server filesystem, only if configured by the deployer | Used only for authorized browser-session fallback |

Security behavior:

*   **No camera recording:** The app captures only the current frame when a scan is requested.
*   **No server project database:** Frames, gesture data, search queries, and answers are not saved to a server DB.
*   **Local artifact control:** The browser can save user artifacts locally for convenience. The **ARTIFACTS** panel supports per-item deletion and full deletion.
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
7. Use the **SOURCE LINKS** chips above the visual answer to open sources in a new tab.
8. Open **TOOLS -> ARTIFACTS** to confirm the search was saved locally and can be reopened or deleted.

Manual fallback path:

1. Type any real query in **TARGET_IDENTIFIER**.
2. Press **EXECUTE RESEARCH**.
3. The HUD should open a source-backed answer without needing camera access.
4. The result should appear in **ARTIFACTS** with its screenshot and source links.

Generated image path:

1. Type a prompt such as `Generate an image of a clean futuristic lab interface with no text`.
2. Press **EXECUTE RESEARCH** with **SEARCH** selected.
3. The HUD should report that it is resolving a generated asset URL.
4. When the provider returns a public image URL, OmniLab renders it above the result and stores it in **ARTIFACTS**.

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

### Artifact Library
*   **ARTIFACTS:** Opens the local browser library of searches, scans, sources, result screenshots, and generated image URLs.
*   **OPEN:** Restores a saved artifact into the HUD.
*   **OPEN IMAGE / OPEN SOURCE:** Opens saved generated images or source links in a new browser tab.
*   **DELETE:** Removes one artifact from browser IndexedDB.
*   **DELETE ALL:** Clears all locally saved OmniLab artifacts in that browser.

## Core Architecture
*   **Vision analysis:** Gemini analyzes explicit scan frames and returns a short tactical summary plus `[search: term]`.
*   **Web research:** Perplexity Web MCP is the primary search engine and returns real answers with sources.
*   **Asset workflow:** Image-generation prompts are routed through Perplexity's file/app model. OmniLab then uses the same conversation to resolve the generated asset URL and display it in the HUD.
*   **Local artifacts:** Browser IndexedDB stores user-controlled artifacts. The backend does not persist these artifacts.
*   **Automation:** Watchtower runs an in-memory async monitor that checks URL status, latency, title, and content hash on an interval.
*   **Fallback search:** Google Programmable Search, Brave Search, DuckDuckGo HTML, Yahoo/browser fallback, depending on configured keys and provider availability.
*   **Visual framework:** Three.js renders the HUD and MediaPipe Tasks for Web tracks hands locally in the browser.
*   **Backend:** FastAPI WebSockets coordinate HUD events, scan analysis, search sessions, and screenshot/result rendering.

## Current Boundaries

These are intentional constraints, not hidden demo behavior:

*   Camera permission is required for environment scans. Manual research works without camera access.
*   Perplexity/LLM/search providers require valid server-side credentials and may consume quota.
*   Generated image URLs depend on the provider returning a public asset URL. If no URL is returned, OmniLab still stores the textual/visual research result.
*   Local artifacts are browser-local. They do not follow the user to another browser/device unless the browser itself syncs site data.
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

The frontend also stores the OmniLab session ID in browser `localStorage` and user artifacts in IndexedDB. These are client-side only and can be cleared from the in-app **ARTIFACTS** panel.

---

**Status:** Operational // **Mode:** Real search, no demo fallback
**Developer:** EngThi / OmniLab Core
