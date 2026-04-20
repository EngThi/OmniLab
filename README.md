# [SYSTEM_OVERVIEW]: OMNILAB // TACTICAL_HUD_OS

OmniLab is an advanced command interface integrating high-frequency computer vision, neural-link LLMs, and autonomous browser agents into a unified 3D Heads-Up Display. Designed for real-time environment analysis and decentralized research.

**[ACTIVE_DEMO_LINK]: https://dialog-fighting-numerical-geographic.trycloudflare.com/**
*Protocol: Initialize sensors via [START_SENSORS] and activate [VOICE: OFFLINE] to begin session.*

## [COGNITIVE_ARCHITECTURE]

The system operates on a distributed neural-link framework to maximize performance and evade detection protocols:

- **Primary Processor:** Gemini 3.1 Flash-Lite (Real-time visual & tactical heuristics).
- **Inference Node:** Hack Club Nest (Remote Command Center - Finland).
- **Stealth Agent:** Playwright-based autonomous browser with DuckDuckGo fallback and cookie-masking.

## [INPUT_PROTOCOLS]

### 1. KINETIC_GESTURES (Vision Engine)
- **THUMBS_UP [👍]**: Triggers automatic environment scan and frame analysis.
- **FIST [✊]**: HOLD FOR 1.5s to initiate **SYSTEM_PURGE**. Resets memory and kills sessions.
- **PINCH [🤏]**: HOLD TO CHARGE suggested research queries. Completes energy ring to execute.

### 2. NEURAL_VOICE (STT Stream)
- **"ANALYZE / SCAN"**: Executes immediate visual capture for AI processing.
- **"YES / SEARCH"**: Manual confirmation for agent research protocols.
- **"TERMINATE / RESET"**: Emergency kill-switch for all active remote processes.

## [DEPLOYMENT_SPECIFICATIONS]

### REQUIREMENTS
- Python 3.10+
- Chromium Engine (Managed via Playwright)
- Valid GEMINI_API_KEY (Defined in .env)

### INITIALIZATION_SEQUENCE
```bash
# 1. Prepare Environment
python -m venv venv && source venv/bin/activate

# 2. Synchronize Dependencies
pip install -r requirements.txt
python -m playwright install chromium

# 3. Boot Core System
python server.py
```

## [NETWORK_LAYER]
Current telemetry is routed via **Cloudflare Zero-Trust Tunneling**, providing a secure uplink to the Finland-based datacenter.

---
**[STATUS]: OPERATIONAL_LEVEL_100**
**[AUTHOR]: EngThi // OmniLab_Core**
