import asyncio
import base64
import os
import json
import re
import random
import textwrap
import io
import subprocess
import shutil
import uuid
import hashlib
import time
from html.parser import HTMLParser
from html import unescape
from urllib.parse import urlparse, parse_qs, urlunparse
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from google import genai
from google.genai import types
from playwright.async_api import async_playwright

load_dotenv()

# ── CONFIG ──
api_key = os.getenv("GEMINI_API_KEY")
COOKIE_FILE = os.path.expanduser(os.getenv("COOKIE_FILE", "~/arq.json"))
PLAYWRIGHT_USER_DATA_DIR = os.path.expanduser(os.getenv("PLAYWRIGHT_USER_DATA_DIR", "~/.playwright_data"))
GOOGLE_CSE_API_KEY = os.getenv("GOOGLE_CSE_API_KEY")
GOOGLE_CSE_CX = os.getenv("GOOGLE_CSE_CX")
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY")
SEARCH_PROXY_FILE = os.path.expanduser(os.getenv("SEARCH_PROXY_FILE", ""))
PWM_COMMAND = os.path.expanduser(os.getenv("PWM_COMMAND", "/home/ubuntu/.local/bin/pwm"))
PWM_PYTHON = os.path.expanduser(os.getenv("PWM_PYTHON", "/home/ubuntu/.local/share/pipx/venvs/perplexity-web-mcp-cli/bin/python"))
PERPLEXITY_TOKEN_FILE = os.path.expanduser(os.getenv("PERPLEXITY_TOKEN_FILE", "~/.config/perplexity-web-mcp/token"))
PERPLEXITY_SESSION_TURNS = int(os.getenv("PERPLEXITY_SESSION_TURNS", "4"))
WATCH_INTERVAL_SECONDS = int(os.getenv("WATCH_INTERVAL_SECONDS", "45"))
WATCH_TIMEOUT_SECONDS = int(os.getenv("WATCH_TIMEOUT_SECONDS", "12"))
COOKIE_FILE_CANDIDATES = [
    COOKIE_FILE,
    os.path.expanduser("~/arq.json"),
    os.path.expanduser("~/cookiesFI.json"),
    os.path.expanduser("~/cookies.json"),
]

if not api_key:
    print("⚠️ [System] GEMINI_API_KEY NOT FOUND!")
else:
    print(f"✅ [System] V15.15 Active (Purple Dot). API Key detected: {api_key[:4]}...{api_key[-4:]}")

client = genai.Client(api_key=api_key) if api_key else None

# MODELOS 2026: PROTOCOLO GEMINI 3.1
MODEL_LIST = ["gemini-3.1-flash-lite-preview", "gemini-3.1-flash-preview", "gemini-3.1-pro-preview"]
BOT_CHECK_PATTERNS = [
    "detected unusual traffic",
    "google.com/sorry",
    "challenge-page",
    "checking if the site connection is secure",
    "verify you are human",
    "cf-challenge",
    "cf-turnstile",
    "cloudflare",
    "captcha",
]

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root(): return FileResponse("static/index.html")

@app.head("/")
async def root_head(): return Response(status_code=200)

cognitive_memory = []
hud_connections: set[WebSocket] = set()
perplexity_sessions = {}
watch_tasks: dict[WebSocket, asyncio.Task] = {}

class AnalyzeRequest(BaseModel):
    image: str

async def send_ws_json(ws: WebSocket, payload: dict) -> bool:
    try:
        await ws.send_json(payload)
        return True
    except (WebSocketDisconnect, RuntimeError):
        return False

def page_has_bot_check(content: str, url: str) -> bool:
    haystack = f"{url}\n{content}".lower()
    return any(pattern in haystack for pattern in BOT_CHECK_PATTERNS)

def normalize_watch_target(raw_target: str) -> str:
    target = (raw_target or "").strip()
    if not target:
        raise ValueError("missing watch target")
    if not re.match(r"^https?://", target, re.I):
        if not re.match(r"^([a-z0-9-]+\.)+[a-z]{2,}(:\d+)?(/.*)?$", target, re.I) and not target.startswith("localhost"):
            raise ValueError("watch target needs a real URL, for example https://example.com")
        target = "https://" + target
    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("watch target must be a valid http(s) URL")
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.params, parsed.query, ""))

def extract_page_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if not match:
        return ""
    return re.sub(r"\s+", " ", unescape(match.group(1))).strip()[:140]

def summarize_change(previous: dict | None, current: dict) -> str:
    if not previous:
        return "BASELINE_CAPTURED"
    changes = []
    if previous.get("status_code") != current.get("status_code"):
        changes.append(f"STATUS {previous.get('status_code')}->{current.get('status_code')}")
    if previous.get("title") != current.get("title") and current.get("title"):
        changes.append("TITLE_CHANGED")
    if previous.get("content_hash") != current.get("content_hash"):
        delta = current.get("content_length", 0) - previous.get("content_length", 0)
        changes.append(f"CONTENT_CHANGED ({delta:+d} bytes)")
    return " // ".join(changes) if changes else "NO_CHANGE"

async def fetch_watch_snapshot(target: str) -> dict:
    headers = {
        "User-Agent": "OmniLab-Watchtower/1.0 (+https://github.com/EngThi/OmniLab)",
        "Accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.8",
    }
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=WATCH_TIMEOUT_SECONDS, follow_redirects=True) as http:
        response = await http.get(target, headers=headers)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    text = response.text[:1_000_000]
    normalized_text = re.sub(r"\s+", " ", text).strip()
    return {
        "url": str(response.url),
        "status_code": response.status_code,
        "ok": 200 <= response.status_code < 400,
        "elapsed_ms": elapsed_ms,
        "title": extract_page_title(text),
        "content_length": len(response.content),
        "content_hash": hashlib.sha256(normalized_text.encode("utf-8", errors="ignore")).hexdigest()[:16],
        "checked_at": int(time.time()),
    }

async def watch_target_loop(ws: WebSocket, target: str):
    previous = None
    await send_ws_json(ws, {"type": "watch_update", "status": "started", "target": target, "message": f"WATCHING {target}"})
    while True:
        try:
            current = await fetch_watch_snapshot(target)
            summary = summarize_change(previous, current)
            current["change"] = summary
            current["target"] = target
            current["status"] = "changed" if previous and summary != "NO_CHANGE" else "ok"
            if not await send_ws_json(ws, {"type": "watch_update", **current}):
                return
            previous = current
        except asyncio.CancelledError:
            raise
        except Exception as e:
            message = str(e)
            if "Name or service not known" in message or "nodename nor servname" in message:
                message = "Could not resolve that host. WATCH TARGET needs a public URL, not a search term."
            if not await send_ws_json(ws, {
                "type": "watch_update",
                "status": "error",
                "target": target,
                "message": message[:180],
                "checked_at": int(time.time()),
            }):
                return
        await asyncio.sleep(WATCH_INTERVAL_SECONDS)

async def stop_watch(ws: WebSocket, reason: str = "STOPPED"):
    task = watch_tasks.pop(ws, None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await send_ws_json(ws, {"type": "watch_update", "status": "stopped", "message": reason})

def load_proxy_config():
    if not SEARCH_PROXY_FILE or not os.path.exists(SEARCH_PROXY_FILE):
        return None
    try:
        with open(SEARCH_PROXY_FILE, "r", encoding="utf-8") as f:
            rows = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
    except Exception as e:
        print(f"⚠️ [Proxy] Could not read proxy file: {e}")
        return None
    if not rows:
        return None
    try:
        host, port, username, password = random.choice(rows).split(":", 3)
    except ValueError:
        print("⚠️ [Proxy] Expected proxy format host:port:username:password")
        return None
    print(f"🌐 [Proxy] Using search proxy {host}:{port}")
    return {
        "server": f"http://{host}:{port}",
        "username": username,
        "password": password,
    }

def render_search_results(query: str, provider: str, items: list[dict]) -> str:
    width, height = 1280, 900
    image = Image.new("RGB", (width, height), "#051014")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    accent = "#00f2ff"
    green = "#00ffaa"
    muted = "#8fb6bd"

    draw.rectangle((0, 0, width, height), fill="#051014")
    for y in range(0, height, 48):
        draw.line((0, y, width, y), fill="#08262c")
    draw.rectangle((50, 45, width - 50, 130), outline=accent, width=2)
    draw.text((75, 68), "OMNILAB WEB SEARCH", fill="#ffffff", font=font)
    draw.text((75, 95), f"PROVIDER: {provider.upper()} // QUERY: {query}", fill=green, font=font)

    y = 165
    if not items:
        draw.text((75, y), "NO RESULTS RETURNED BY SEARCH PROVIDER.", fill="#ff5577", font=font)
    for idx, item in enumerate(items[:8], start=1):
        title = item.get("title") or "Untitled result"
        link = item.get("link") or item.get("formattedUrl") or ""
        snippet = item.get("snippet") or ""
        draw.text((75, y), f"{idx}. {title[:145]}", fill="#ffffff", font=font)
        y += 24
        if link:
            draw.text((95, y), link[:160], fill=green, font=font)
            y += 22
        for line in textwrap.wrap(snippet, width=150)[:3]:
            draw.text((95, y), line, fill=muted, font=font)
            y += 20
        y += 18
        if y > height - 90:
            break

    draw.rectangle((50, height - 70, width - 50, height - 35), outline="#13444d", width=1)
    draw.text((75, height - 58), "DATA SOURCE: REAL SEARCH PROVIDER // NO PLACEHOLDER CONTENT", fill=accent, font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def render_perplexity_result(query: str, answer: str, citations: list[str], routing: dict, session_id: str, continued: bool) -> str:
    width = 1280
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    bold_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]

    def load_font(size: int, bold: bool = False):
        for path in (bold_paths if bold else font_paths):
            if os.path.exists(path):
                return ImageFont.truetype(path, size=size)
        return ImageFont.load_default()

    title_font = load_font(30, True)
    subtitle_font = load_font(17)
    section_font = load_font(20, True)
    body_font = load_font(18)
    body_bold = load_font(18, True)
    small_font = load_font(14)
    source_font = load_font(15)

    ink = "#172026"
    muted = "#63707a"
    faint = "#e6ebef"
    card = "#ffffff"
    teal = "#127c87"
    teal_soft = "#e5f7f8"
    blue = "#2557a7"

    def md_clean(text: str) -> str:
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
        text = re.sub(r"(\*\*|__|\*|`)", "", text)
        return re.sub(r"\s+", " ", text).strip()

    def line_kind(raw: str):
        line = raw.strip()
        if not line:
            return "blank", "", ""
        if line.startswith("#"):
            return "heading", "", md_clean(line.lstrip("#").strip())
        bullet = re.match(r"^[-*]\s+(.+)$", line)
        if bullet:
            return "bullet", "•", md_clean(bullet.group(1))
        numbered = re.match(r"^(\d+)[.)]\s+(.+)$", line)
        if numbered:
            return "bullet", f"{numbered.group(1)}.", md_clean(numbered.group(2))
        if line.startswith(">"):
            return "quote", "", md_clean(line.lstrip(">").strip())
        return "body", "", md_clean(line)

    def wrap_parts(text: str, max_chars: int):
        return textwrap.wrap(text, width=max_chars) or [""]

    def build_answer_blocks(text: str):
        blocks = []
        clean = re.sub(r"\n{3,}", "\n\n", text or "").strip()
        for raw in clean.splitlines():
            kind, prefix, value = line_kind(raw)
            if kind == "blank":
                blocks.append({"kind": kind, "height": 12})
            elif kind == "heading":
                parts = wrap_parts(value, 76)
                blocks.append({"kind": kind, "text": value, "height": 6 + len(parts) * 28 + 10})
            elif kind == "bullet":
                parts = wrap_parts(value, 102)
                blocks.append({"kind": kind, "prefix": prefix, "text": value, "height": len(parts) * 25 + 5})
            elif kind == "quote":
                parts = wrap_parts(value, 96)
                blocks.append({"kind": kind, "text": value, "height": len(parts) * 25 + 8})
            else:
                lead_match = re.match(r"^([^:]{3,48}):\s+(.+)$", value)
                if lead_match:
                    label, rest = lead_match.groups()
                    parts = wrap_parts(rest, 104)
                    blocks.append({"kind": "lead", "label": label, "text": rest, "height": 26 + len(parts) * 25 + 10})
                else:
                    parts = wrap_parts(value, 108)
                    blocks.append({"kind": kind, "text": value, "height": len(parts) * 25 + 10})
        return blocks

    def draw_wrapped(text: str, x: int, y: int, max_chars: int, font, fill: str, line_height: int, prefix: str = ""):
        first_prefix = prefix
        next_prefix = " " * len(prefix)
        for idx, part in enumerate(wrap_parts(text, max_chars)):
            draw.text((x, y), (first_prefix if idx == 0 else next_prefix) + part, fill=fill, font=font)
            y += line_height
        return y

    answer_blocks = build_answer_blocks(answer)
    answer_top = 266
    answer_height = min(max(360, sum(block["height"] for block in answer_blocks) + 96), 1750)
    answer_bottom = answer_top + answer_height
    source_top = answer_bottom + 26
    source_rows = min(len(citations), 6) if citations else 1
    source_bottom = source_top + 92 + source_rows * 50
    height = source_bottom + 64
    image = Image.new("RGB", (width, height), "#f6f8fb")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((44, 36, width - 44, 150), radius=18, fill=card, outline=faint, width=2)
    draw.rounded_rectangle((70, 60, 210, 92), radius=16, fill=teal_soft)
    draw.text((90, 67), "SOURCED ANSWER", fill=teal, font=small_font)
    draw.text((70, 103), "Web Research", fill=ink, font=title_font)
    session_text = "continued session" if continued else "new session"
    draw.text((width - 240, 72), session_text, fill=muted, font=small_font)

    query_text = md_clean(query)
    draw.rounded_rectangle((44, 170, width - 44, 238), radius=14, fill="#eef5ff", outline="#d7e4f5", width=1)
    draw.text((70, 190), "Query", fill=blue, font=small_font)
    draw_wrapped(query_text, 132, 188, 120, subtitle_font, ink, 24)

    draw.rounded_rectangle((44, answer_top, width - 44, answer_bottom), radius=18, fill=card, outline=faint, width=2)
    draw.text((70, answer_top + 26), "Answer", fill=teal, font=section_font)

    y = answer_top + 66
    for block in answer_blocks:
        if y + block["height"] > answer_bottom - 30:
            draw.text((70, y), "Response continues in the Perplexity session; ask a follow-up or narrow the query.", fill=muted, font=body_font)
            break
        kind = block["kind"]
        if kind == "blank":
            y += 12
            continue
        if kind == "heading":
            y += 6
            y = draw_wrapped(block["text"], 70, y, 76, section_font, ink, 28)
            y += 10
        elif kind == "bullet":
            y = draw_wrapped(block["text"], 92, y, 102, body_font, ink, 25, prefix=f"{block['prefix']} ")
            y += 5
        elif kind == "quote":
            draw.rectangle((70, y, 76, y + max(28, block["height"] - 8)), fill="#d7e4f5")
            y = draw_wrapped(block["text"], 92, y, 96, body_font, muted, 25)
            y += 8
        elif kind == "lead":
            draw.text((70, y), f"{block['label']}:", fill=ink, font=body_bold)
            y = draw_wrapped(block["text"], 70, y + 26, 104, body_font, ink, 25)
            y += 10
        else:
            y = draw_wrapped(block["text"], 70, y, 108, body_font, ink, 25)
            y += 10

    draw.rounded_rectangle((44, source_top, width - 44, source_bottom), radius=18, fill=card, outline=faint, width=2)
    draw.text((70, source_top + 24), "Sources", fill=teal, font=section_font)
    y = source_top + 62
    if citations:
        for idx, url in enumerate(citations[:6], start=1):
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "") or url
            draw.rounded_rectangle((70, y - 3, 118, y + 21), radius=10, fill=teal_soft)
            draw.text((88, y), str(idx), fill=teal, font=source_font)
            draw.text((132, y - 2), domain[:48], fill=ink, font=source_font)
            draw.text((132, y + 18), url[:135], fill=muted, font=small_font)
            y += 50
            if y > source_bottom - 38:
                break
    else:
        draw.text((70, y), "No sources returned by provider.", fill=muted, font=source_font)

    footer = "real web answer · source-backed · no placeholder content"
    draw.text((70, height - 34), footer, fill=muted, font=small_font)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=92)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def pwm_binary_available() -> bool:
    return os.path.exists(PWM_COMMAND) or shutil.which("pwm") is not None

def perplexity_library_available() -> bool:
    return os.path.exists(PWM_PYTHON) and os.path.exists(PERPLEXITY_TOKEN_FILE)

def wants_generated_image(query: str) -> bool:
    text = (query or "").lower()
    image_terms = [
        "generate an image", "create an image", "make an image", "draw an image",
        "image of", "picture of", "visual asset", "gerar imagem", "gere uma imagem",
        "crie uma imagem", "criar imagem", "desenhe", "imagem de",
    ]
    return any(term in text for term in image_terms)

async def perplexity_web_screenshot(query: str, session_id: str, continue_session: bool):
    if perplexity_library_available():
        return await perplexity_library_screenshot(query, session_id, continue_session)

    if not pwm_binary_available():
        return None

    history = perplexity_sessions.get(session_id, [])
    effective_query = query
    if continue_session and history:
        context_lines = []
        for turn in history[-PERPLEXITY_SESSION_TURNS:]:
            context_lines.append(f"User: {turn['query']}")
            context_lines.append(f"Previous answer: {turn['answer'][:900]}")
        effective_query = (
            "Continue the same research session. Use the context below only to preserve continuity, "
            "then answer the new request with current web search and citations.\n\n"
            + "\n".join(context_lines)
            + f"\n\nNew request: {query}"
        )

    command = [PWM_COMMAND if os.path.exists(PWM_COMMAND) else "pwm", "ask", effective_query, "--json", "--source", "web"]
    env = os.environ.copy()
    home = os.path.expanduser("~")
    env["PATH"] = f"{home}/.local/bin:" + env.get("PATH", "")

    print(f"🚀 [Perplexity] Querying session={session_id} continue={continue_session}: {query}")
    proc = await asyncio.to_thread(
        subprocess.run,
        command,
        capture_output=True,
        text=True,
        timeout=90,
        env=env,
        cwd=home,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"pwm failed: {stderr[:300]}")

    data = json.loads(proc.stdout)
    answer = data.get("answer") or ""
    citations = data.get("citations") or []
    routing = data.get("routing") or {}
    if not answer:
        return None

    history.append({"query": query, "answer": answer, "citations": citations})
    perplexity_sessions[session_id] = history[-PERPLEXITY_SESSION_TURNS:]
    return render_perplexity_result(query, answer, citations, routing, session_id, continue_session), False

async def perplexity_library_screenshot(query: str, session_id: str, continue_session: bool):
    session = perplexity_sessions.get(session_id) if continue_session else None
    payload = {
        "query": query,
        "session_id": session_id,
        "image_intent": wants_generated_image(query),
        "backend_uuid": session.get("backend_uuid") if session else None,
        "read_write_token": session.get("read_write_token") if session else None,
        "token_file": PERPLEXITY_TOKEN_FILE,
    }
    script = r"""
import json
import re
import sys
from pathlib import Path
from perplexity_web_mcp.core import Perplexity, ConversationConfig
from perplexity_web_mcp.enums import SourceFocus, SearchFocus, CitationMode
from perplexity_web_mcp.models import Models

payload = json.loads(sys.stdin.read())
session_token = Path(payload["token_file"]).read_text().strip()
client = Perplexity(session_token=session_token)
conv = client.create_conversation(ConversationConfig(
    source_focus=SourceFocus.WEB,
    search_focus=SearchFocus.WEB,
    citation_mode=CitationMode.CLEAN,
    save_to_library=False,
    language="pt-BR",
    timezone="America/Sao_Paulo",
))
if payload.get("backend_uuid") and payload.get("read_write_token"):
    conv._backend_uuid = payload["backend_uuid"]
    conv._read_write_token = payload["read_write_token"]

image_intent = bool(payload.get("image_intent"))
if image_intent:
    conv.ask(payload["query"], model=Models.CREATE_FILES_AND_APPS)
else:
    conv.ask(payload["query"])
primary_answer = conv.answer or ""
asset_urls = []
raw_data = getattr(conv, "_raw_data", None)
if raw_data:
    raw_text = json.dumps(raw_data, ensure_ascii=False)
    for url in re.findall(r"https?://user-gen-media-assets\.s3\.amazonaws\.com/[^\s\"'<>]+", raw_text):
        asset_urls.append(url.rstrip(".,);]*_`"))

if image_intent or re.search(r"Media generated", primary_answer, re.I):
    followup = (
        "In this same conversation, what is the public URL, S3 URL, CDN URL, or downloadable link "
        "for the image/media asset you just generated? Return only the direct image URL if available. "
        "If not available, say NO_URL."
    )
    conv.ask(followup, model=Models.CREATE_FILES_AND_APPS)
    for url in re.findall(r"https?://[^\s\"'<>]+", conv.answer or ""):
        clean_url = url.rstrip(".,);]*_`")
        if "user-gen-media-assets.s3.amazonaws.com" in clean_url or re.search(r"\.(png|jpg|jpeg|webp)(\?|$)", clean_url, re.I):
            asset_urls.append(clean_url)

search_results = []
for item in conv.search_results:
    search_results.append({
        "title": getattr(item, "title", None),
        "snippet": getattr(item, "snippet", None),
        "url": getattr(item, "url", None),
    })

print(json.dumps({
    "answer": primary_answer,
    "search_results": search_results,
    "asset_urls": list(dict.fromkeys(asset_urls)),
    "backend_uuid": conv._backend_uuid,
    "read_write_token": conv._read_write_token,
    "conversation_uuid": conv.uuid,
}, ensure_ascii=False))
client.close()
"""
    print(f"🚀 [PerplexityLib] Querying session={session_id} continue={continue_session}: {query}")
    proc = await asyncio.to_thread(
        subprocess.run,
        [PWM_PYTHON, "-c", script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=90,
        cwd=os.path.expanduser("~"),
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"perplexity library failed: {stderr[:300]}")

    data = json.loads(proc.stdout)
    answer = data.get("answer") or ""
    results = data.get("search_results") or []
    asset_urls = data.get("asset_urls") or []
    citations = [item.get("url") for item in results if item.get("url")]
    if not answer:
        return None

    perplexity_sessions[session_id] = {
        "backend_uuid": data.get("backend_uuid"),
        "read_write_token": data.get("read_write_token"),
        "answer": answer,
        "search_results": results,
        "asset_urls": asset_urls,
    }
    return render_perplexity_result(
        query,
        answer,
        citations,
        {"model_name": "perplexity_web", "search_type": "web"},
        session_id,
        continue_session,
    ), False

class DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self._field = None
        self._text = []
        self._pending_href = ""
        self._current_snippet_index = None

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        classes = set((attr.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            self._pending_href = self._normalize_href(attr.get("href", ""))
            self._field = "title"
            self._text = []
        elif tag in {"a", "div"} and "result__snippet" in classes and self.items:
            self._current_snippet_index = len(self.items) - 1
            self._field = "snippet"
            self._text = []

    def handle_data(self, data):
        if self._field:
            self._text.append(data)

    def handle_endtag(self, tag):
        if self._field == "title" and tag == "a":
            title = self._clean_text(" ".join(self._text))
            if title and self._pending_href and not self._is_ad_link(self._pending_href):
                self.items.append({"title": title, "link": self._pending_href, "snippet": ""})
            self._field = None
            self._text = []
            self._pending_href = ""
        elif self._field == "snippet" and tag in {"a", "div"}:
            snippet = self._clean_text(" ".join(self._text))
            if snippet and self._current_snippet_index is not None:
                self.items[self._current_snippet_index]["snippet"] = snippet
            self._field = None
            self._text = []
            self._current_snippet_index = None

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", unescape(value)).strip()

    @staticmethod
    def _normalize_href(href: str) -> str:
        href = unescape(href or "")
        if href.startswith("//"):
            href = "https:" + href
        parsed = urlparse(href)
        if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
            target = parse_qs(parsed.query).get("uddg", [""])[0]
            return target or href
        return href

    @staticmethod
    def _is_ad_link(href: str) -> bool:
        lowered = href.lower()
        return any(marker in lowered for marker in ["ad_domain=", "bing.com/aclick", "/y.js"])

async def brave_search_screenshot(query: str):
    if not BRAVE_SEARCH_API_KEY:
        return None
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
    }
    params = {
        "q": query,
        "count": 8,
        "country": "BR",
        "search_lang": "pt-br",
        "safesearch": "moderate",
    }
    async with httpx.AsyncClient(timeout=12) as http:
        response = await http.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
    items = []
    for result in data.get("web", {}).get("results", [])[:8]:
        snippets = [result.get("description", "")]
        snippets.extend(result.get("extra_snippets") or [])
        items.append({
            "title": result.get("title"),
            "link": result.get("url"),
            "snippet": " ".join(s for s in snippets if s),
        })
    return render_search_results(query, "brave_search_api", items), False

async def google_cse_screenshot(query: str):
    if not GOOGLE_CSE_API_KEY or not GOOGLE_CSE_CX:
        return None
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_CSE_API_KEY,
        "cx": GOOGLE_CSE_CX,
        "q": query,
        "num": 8,
    }
    async with httpx.AsyncClient(timeout=12) as http:
        response = await http.get(url, params=params)
        response.raise_for_status()
        data = response.json()
    items = data.get("items", [])
    return render_search_results(query, "google_programmable_search", items), False

async def duckduckgo_html_screenshot(query: str):
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as http:
        response = await http.get(url, params={"q": query, "kl": "br-pt"}, headers=headers)
        response.raise_for_status()
        parser = DuckDuckGoHTMLParser()
        parser.feed(response.text)
    if not parser.items:
        return None
    return render_search_results(query, "duckduckgo_html", parser.items), False

async def web_search_screenshot(query: str, session_id: str = "", continue_session: bool = False):
    providers = [
        ("perplexity_web", lambda q: perplexity_web_screenshot(q, session_id, continue_session)),
        ("google_programmable_search", google_cse_screenshot),
        ("brave_search_api", brave_search_screenshot),
        ("duckduckgo_html", duckduckgo_html_screenshot),
    ]
    for provider, fn in providers:
        try:
            result = await fn(query)
            if result:
                print(f"✅ [SearchAPI] {provider} returned real results.")
                return result
        except Exception as e:
            print(f"⚠️ [SearchAPI] {provider} failed: {e}")
    return None

def load_cookie_file():
    cookie_file = next((p for p in COOKIE_FILE_CANDIDATES if os.path.exists(p) and os.path.getsize(p) > 0), None)
    if not cookie_file:
        return []
    try:
        with open(cookie_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"⚠️ [Cookies] Could not read cookie file: {e}")
        return []

    raw_cookies = data.get("cookies") if isinstance(data, dict) else data
    if not isinstance(raw_cookies, list):
        print("⚠️ [Cookies] Unsupported cookie file format.")
        return []

    cookies = []
    for cookie in raw_cookies:
        if not isinstance(cookie, dict) or not cookie.get("name") or not cookie.get("value"):
            continue
        normalized = {k: v for k, v in cookie.items() if k in {
            "name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite", "url"
        }}
        if not normalized.get("domain") and not normalized.get("url"):
            continue
        normalized.setdefault("path", "/")
        if normalized.get("sameSite") not in {"Strict", "Lax", "None"}:
            normalized.pop("sameSite", None)
        cookies.append(normalized)
    return cookies

async def apply_user_cookies(browser_context):
    cookies = load_cookie_file()
    if not cookies:
        return
    try:
        await browser_context.add_cookies(cookies)
        domains = sorted({c.get("domain") or c.get("url", "") for c in cookies})
        print(f"✅ [Cookies] Loaded {len(cookies)} cookies for {len(domains)} domains.")
    except Exception as e:
        print(f"⚠️ [Cookies] Could not apply cookies: {e}")

@app.websocket("/ws/hud")
async def websocket_hud(ws: WebSocket):
    global cognitive_memory
    await ws.accept()
    hud_connections.add(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "command":
                cmd = data.get("command")
                query = data.get("query")
                engine = data.get("engine", "google")
                session_id = data.get("session_id") or str(uuid.uuid4())[:8]
                continue_session = bool(data.get("continue_session"))
                if cmd == "analyze_and_search" and query:
                    label = "WEB_SEARCH" if engine in {"google", "web"} else engine.upper()
                    if not await send_ws_json(ws, {"type": "status_update", "message": f"AGENT: RESEARCHING_{label}"}):
                        break
                    try:
                        if engine in {"google", "web"}:
                            if not await send_ws_json(ws, {"type": "status_update", "message": f"SESSION: {session_id} // {'CONTINUE' if continue_session else 'NEW'}"}):
                                break
                            image_intent = wants_generated_image(query)
                            if image_intent:
                                if not await send_ws_json(ws, {"type": "status_update", "message": "SYS: TRYING_IMAGE_ASSET"}):
                                    break
                                if not await send_ws_json(ws, {"type": "status_update", "message": "SYS: RESOLVING_GENERATED_ASSET_URL"}):
                                    break
                            api_result = await web_search_screenshot(query, session_id, continue_session)
                        else:
                            api_result = None

                        if api_result:
                            img_data, is_blocked = api_result
                        else:
                            img_data, is_blocked = await capture_screenshot(engine, query)

                        if is_blocked and engine in {"google", "web"}:
                            if not await send_ws_json(ws, {"type": "status_update", "message": "WARN: GOOGLE_BLOCK_DETECTED"}):
                                break
                            if not await send_ws_json(ws, {"type": "status_update", "message": "SYS: REROUTING_REAL_SEARCH..."}):
                                break
                            img_data, is_blocked = await capture_screenshot("yahoo", query)
                        elif is_blocked:
                            if not await send_ws_json(ws, {"type": "status_update", "message": "WARN: VERIFICATION_REQUIRED"}):
                                break
                        if not await send_ws_json(ws, {"type": "browser_screenshot", "data": img_data}):
                            break
                        if engine in {"google", "web"} and session_id in perplexity_sessions:
                            session_data = perplexity_sessions.get(session_id, {})
                            sources = session_data.get("search_results") or []
                            if sources:
                                if not await send_ws_json(ws, {"type": "research_sources", "sources": sources[:8]}):
                                    break
                            asset_urls = session_data.get("asset_urls") or []
                            if asset_urls:
                                if not await send_ws_json(ws, {"type": "generated_assets", "assets": asset_urls[:3]}):
                                    break
                                if not await send_ws_json(ws, {"type": "status_update", "message": "ASSET: GENERATED_IMAGE_READY"}):
                                    break
                    except Exception as e:
                        print(f"❌ [Error] Research failed: {e}")
                        if not await send_ws_json(ws, {"type": "status_update", "message": f"ERROR: {str(e)[:100]}"}):
                            break
                elif cmd == "start_watch" and query:
                    try:
                        target = normalize_watch_target(query)
                    except Exception as e:
                        if not await send_ws_json(ws, {"type": "status_update", "message": f"WATCH_ERROR: {str(e)[:80]}"}):
                            break
                        continue
                    await stop_watch(ws, "WATCH_REPLACED")
                    watch_tasks[ws] = asyncio.create_task(watch_target_loop(ws, target))
                    if not await send_ws_json(ws, {"type": "status_update", "message": f"WATCHTOWER: ACTIVE {target}"}):
                        break
                elif cmd == "stop_watch":
                    await stop_watch(ws, "WATCHTOWER: STOPPED")
                elif cmd == "close_browser":
                    cognitive_memory = []
                    perplexity_sessions.clear()
                    await stop_watch(ws, "WATCHTOWER: PURGED")
                    if not await send_ws_json(ws, {"type": "status_update", "message": "SYSTEM_CORE: MEMORY_PURGED"}):
                        break
    except WebSocketDisconnect:
        hud_connections.discard(ws)
    finally:
        await stop_watch(ws, "WATCHTOWER: DISCONNECTED")
        hud_connections.discard(ws)

@app.websocket("/ws/vision")
async def websocket_vision(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            for h in list(hud_connections):
                if not await send_ws_json(h, data):
                    hud_connections.discard(h)
    except WebSocketDisconnect: pass

async def type_human_like(page, selector, text, click_after=None):
    """Digita letra por letra com pausas, movimentos e clique forçado."""
    await page.wait_for_selector(selector, timeout=30000)
    await page.mouse.move(random.randint(100, 700), random.randint(100, 700))
    await page.click(selector)
    await asyncio.sleep(random.uniform(1.0, 2.0))
    for char in text:
        await page.keyboard.type(char, delay=random.randint(60, 200))
    await asyncio.sleep(random.uniform(2.0, 4.0)) 
    
    if click_after:
        try:
            btn = await page.wait_for_selector(click_after, timeout=10000)
            await btn.hover()
            await asyncio.sleep(random.uniform(0.5, 1.2))
            await btn.click(force=True)
            print(f"✅ [UI] Master force click on {click_after}")
        except:
            await page.keyboard.press("Enter")
    else:
        await page.keyboard.press("Enter")

async def capture_screenshot(engine: str, query: str):
    from playwright_stealth import Stealth
    import urllib.parse
    quoted = urllib.parse.quote(query)
    user_data_dir = PLAYWRIGHT_USER_DATA_DIR

    async with async_playwright() as p:
        stealth_params = {
            "user_agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            "locale": 'pt-BR',
            "timezone_id": 'America/Sao_Paulo',
            "geolocation": {'latitude': -23.5505, 'longitude': -46.6333},
            "permissions": ['geolocation'],
            "viewport": {'width': 1280, 'height': 800},
        }

        chromium_args = [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
        ]

        proxy = load_proxy_config() if engine in ["google", "web"] else None
        print(f"🚀 [Browser] Starting {engine.upper()} search for: {query}")
        if engine in ["google", "web", "gemini", "chatgpt", "perplexity"]:
            browser_context = await p.chromium.launch_persistent_context(
                user_data_dir, headless=True, args=chromium_args, proxy=proxy, **stealth_params
            )
        else:
            browser = await p.chromium.launch(headless=True, args=chromium_args, proxy=proxy)
            browser_context = await browser.new_context(**stealth_params)

        try:
            page = browser_context.pages[0] if browser_context.pages else await browser_context.new_page()
            if engine in ["google", "web", "gemini", "chatgpt", "perplexity"]:
                await apply_user_cookies(browser_context)
            await Stealth().apply_stealth_async(page)

            await page.mouse.move(400, 400)
            await asyncio.sleep(random.uniform(0.5, 1.5))

            if engine == "gemini": target_url = "https://gemini.google.com/app"
            elif engine == "chatgpt": target_url = "https://chatgpt.com/"
            elif engine == "perplexity": target_url = f"https://www.perplexity.ai/search?q={quoted}"
            elif engine == "duckduckgo": target_url = f"https://duckduckgo.com/html/?q={quoted}"
            elif engine == "yahoo": target_url = f"https://search.yahoo.com/search?p={quoted}"
            else: target_url = f"https://www.google.com/search?q={quoted}&hl=pt-BR"

            print(f"🔎 [Browser] Navigating to {target_url}...")
            try:
                await page.goto(target_url, wait_until="domcontentloaded", timeout=50000)
                print(f"✅ [Browser] Page loaded.")
            except Exception as e:
                print(f"⚠️ [Nav] Timeout or error during load: {e}. Capturing current page.")

            if engine == "gemini":
                try:
                    gemini_send_btn = "button[aria-label*='Send'], .send-button-container button, div.send-button-container button"
                    input_selector = "div[contenteditable='true']"
                    await type_human_like(page, input_selector, query, click_after=gemini_send_btn)
                    await asyncio.sleep(18)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    answer_selectors = [
                        "message-content",
                        ".markdown",
                        "div[role='presentation']",
                        "main",
                    ]
                    for selector in answer_selectors:
                        try:
                            await page.locator(selector).last.scroll_into_view_if_needed(timeout=4000)
                            break
                        except Exception:
                            continue
                    for _ in range(5):
                        await page.mouse.wheel(0, 900)
                        await asyncio.sleep(0.7)
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                except Exception as e: print(f"⚠️ Gemini Error: {e}")

            elif engine == "chatgpt":
                try:
                    input_selector = "#prompt-textarea"
                    chatgpt_send_btn = "[data-testid='send-button']"
                    await type_human_like(page, input_selector, query, click_after=chatgpt_send_btn)
                    await asyncio.sleep(20)
                except Exception as e: print(f"⚠️ ChatGPT Error: {e}")

            elif engine == "perplexity":
                await page.mouse.wheel(0, 500)
                await asyncio.sleep(12)

            else: await asyncio.sleep(5)

            content = await page.content()
            is_blocked = page_has_bot_check(content, page.url)

            screenshot_bytes = await page.screenshot(type="jpeg", quality=75, full_page=True)
            return base64.b64encode(screenshot_bytes).decode('utf-8'), is_blocked
        finally:
            await browser_context.close()

async def _call_ai(image_bytes, history):
    if not client: return "API KEY ERROR"
    for m_id in MODEL_LIST:
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=m_id,
                contents=[types.Content(role="user", parts=[
                    types.Part.from_bytes(mime_type="image/jpeg", data=image_bytes),
                    types.Part.from_text(text=(f"CONTEXT: {history}\nTASK: Tactical analysis. Short plain text. Suggest search query in brackets: [search: term]."))
                ])]
            )
            return response.text
        except Exception: continue
    return "ANALYSIS_FAILED."

@app.post("/analyze")
async def analyze_frame(request: AnalyzeRequest):
    global cognitive_memory
    try:
        img_bytes = base64.b64decode(request.image)
        text = await _call_ai(img_bytes, " | ".join(cognitive_memory[-2:]))
        cognitive_memory.append(text)
        if len(cognitive_memory) > 5: cognitive_memory.pop(0)
    except Exception: return {"status": "error", "message": "IA_OFFLINE"}
    m = re.search(r'\[search:\s*(.*?)\]', text)
    query = m.group(1) if m else text[:30]
    return {"status": "success", "text": text, "suggested_query": query}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
