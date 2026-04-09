# ============================================================
# TeraScrap - Main Application
# Developer: @Hamza3895
# Copyright © Dr. Dev || Dr. Hamza 2026 - All Rights Reserved
# ============================================================

import os, re, time, threading, logging, json, asyncio
from flask import Flask, request, jsonify, render_template_string
from curl_cffi import requests as cf_requests
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── CONFIG ────────────────────────────────────────────────────
BOT_TOKEN = "8762330219:AAE019vA-rM_jh4oISBjgVjNphaJgvOz2yk"
WEBAPP_URL = "https://terabox-video-downloader-and-stream.onrender.com"
PORT = 5000

COOKIE_FILES = [
    "cookies1.txt",
    "cookies2.txt",
    "cookies3.txt",
    "cookies4.txt",
    "cookies5.txt"
]
current_cookie_index = 0

PROXIES = [
    "http://ayxvpdzm:mhdlody0d0x6@31.59.20.176:6754",
    "http://ayxvpdzm:mhdlody0d0x6@198.23.239.134:6540",
    "http://ayxvpdzm:mhdlody0d0x6@45.38.107.97:6014",
    "http://ayxvpdzm:mhdlody0d0x6@107.172.163.27:6543",
    "http://ayxvpdzm:mhdlody0d0x6@198.105.121.200:6462",
    "http://ayxvpdzm:mhdlody0d0x6@216.10.27.159:6837",
    "http://ayxvpdzm:mhdlody0d0x6@142.111.67.146:5611",
    "http://ayxvpdzm:mhdlody0d0x6@191.96.254.138:6185",
    "http://ayxvpdzm:mhdlody0d0x6@31.58.9.4:6077",
    "http://ayxvpdzm:mhdlody0d0x6@198.46.161.42:5092"
]
current_proxy_index = 0

# 🔥 FIXED: Bulletproof Windows Chrome 124 Headers to match impersonate="chrome124"
WINDOWS_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": WINDOWS_UA,
}

API_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": "https://iteraplay.com",
    "referer": "https://iteraplay.com/",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": WINDOWS_UA,
}

# ── COOKIE / SESSION ──────────────────────────────────────────
def load_netscape_cookies(cookie_file: str) -> dict:
    cookies = {}
    try:
        with open(cookie_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    cookies[parts[5]] = parts[6]
    except FileNotFoundError:
        logger.warning(f"Cookie file not found: {cookie_file}")
    return cookies

def create_session(cookie_file: str, proxy_url: str) -> cf_requests.Session:
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    session = cf_requests.Session(impersonate="chrome124", proxies=proxies)
    try:
        session.get("https://iteraplay.com/", headers=HEADERS, timeout=30)
        time.sleep(0.5)
        if os.path.exists(cookie_file):
            all_cookies = load_netscape_cookies(cookie_file)
            inject = {k: v for k, v in all_cookies.items()
                      if k in ("login_token", "remember_me")}
            for name, value in inject.items():
                session.cookies.set(name, value, domain="iteraplay.com")
            session.get("https://iteraplay.com/", headers=HEADERS, timeout=30)
    except Exception as e:
        logger.error(f"Session warmup error: {e}")
    return session

SESSIONS = {}

# ── VIDEO FETCHER ──────────────────────────────────────────────
def fetch_video_info(url: str) -> dict:
    global current_cookie_index, current_proxy_index
    max_attempts = len(PROXIES) * len(COOKIE_FILES)
    attempts = 0
    last_error = None
    
    while attempts < max_attempts:
        c_idx = current_cookie_index % len(COOKIE_FILES)
        p_idx = current_proxy_index % len(PROXIES)
        
        session_key = f"{c_idx}_{p_idx}"
        if session_key not in SESSIONS:
            SESSIONS[session_key] = create_session(COOKIE_FILES[c_idx], PROXIES[p_idx])
        session = SESSIONS[session_key]
        
        try:
            resp = session.post(
                "https://iteraplay.com/api/download",
                headers=API_HEADERS,
                json={"url": url},
                timeout=30
            )
            
            # Rate limited -> Rotate Cookie
            if resp.status_code == 429:
                logger.warning(f"Cookie {c_idx+1} rate limited. Switching cookie...")
                current_cookie_index = (current_cookie_index + 1) % len(COOKIE_FILES)
                if session_key in SESSIONS:
                    del SESSIONS[session_key]
                attempts += 1
                continue
                
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("status") != "success":
                raise ValueError(f"API error: {data.get('status')}")
                
            files = data.get("list", [])
            if not files:
                raise ValueError("No files returned")
                
            file_info = files[0]
            name = file_info.get("name", "")
            
            # Token expired -> Rotate Cookie
            if any(kw in name for kw in ("Token", "token", "expired", "mismatch", "Cookie")):
                logger.warning(f"Session error with cookie {c_idx+1}: {name}. Switching cookie...")
                current_cookie_index = (current_cookie_index + 1) % len(COOKIE_FILES)
                if session_key in SESSIONS:
                    del SESSIONS[session_key]
                attempts += 1
                continue
                
            return file_info
            
        except Exception as e:
            # Proxy error / 403 Forbidden -> Rotate Proxy
            last_error = e
            logger.error(f"Proxy {p_idx+1} failed: {e}. Switching proxy...")
            current_proxy_index = (current_proxy_index + 1) % len(PROXIES)
            if session_key in SESSIONS:
                del SESSIONS[session_key]
            attempts += 1
            
    raise RuntimeError(f"All proxies and cookies failed. Last error: {last_error}")

# ── FLASK APP ──────────────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/ping")
def ping():
    return "OK", 200

@flask_app.route("/api/fetch", methods=["POST"])
def api_fetch():
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL required"}), 400
    try:
        info = fetch_video_info(url)
        streams = info.get("fast_stream_url", {})
        safe_info = {
            "name": info.get("name", "Video"),
            "size": info.get("size_formatted", "N/A"),
            "quality": info.get("quality", "N/A"),
            "duration": info.get("duration", "N/A"),
            "qualities": list(streams.keys()) if isinstance(streams, dict) else [],
            "_streams": streams  # hidden from direct display
        }
        return jsonify({"status": "success", "info": safe_info})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@flask_app.route("/api/stream", methods=["POST"])
def api_stream():
    data = request.json or {}
    url = data.get("url", "").strip()
    quality = data.get("quality", "")
    if not url:
        return jsonify({"error": "URL required"}), 400
    try:
        info = fetch_video_info(url)
        streams = info.get("fast_stream_url", {})
        if not isinstance(streams, dict) or not streams:
            return jsonify({"error": "No streams available"}), 404
        qualities = sorted(streams.keys(), key=lambda q: int(q.replace("p", "")))
        if quality not in streams:
            quality = qualities[-1]
        m3u8_url = streams[quality]
        return jsonify({"status": "success", "stream_url": m3u8_url, "quality": quality, "qualities": qualities})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@flask_app.route("/watch")
def watch_page():
    return render_template_string(WATCH_HTML)

@flask_app.route("/download")
def download_page():
    return render_template_string(DOWNLOAD_HTML)

@flask_app.route("/")
def index():
    return render_template_string(INDEX_HTML)

# ── HTML TEMPLATES ─────────────────────────────────────────────
INDEX_HTML = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>TeraScrap – Terabox Video Fetcher</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;400;600;700&display=swap" rel="stylesheet"/>
<style>
  :root[data-theme="dark"] {
    --bg: #050510;
    --surface: #0a0a20;
    --card: #0f0f2a;
    --border: #1a1a4a;
    --accent: #7b2fff;
    --accent2: #00d4ff;
    --accent3: #ff2d78;
    --text: #e8e8ff;
    --muted: #6666aa;
    --glow: rgba(123,47,255,0.4);
    --glow2: rgba(0,212,255,0.3);
  }
  :root[data-theme="light"] {
    --bg: #f0f0ff;
    --surface: #ffffff;
    --card: #f8f8ff;
    --border: #ccccee;
    --accent: #6b1fef;
    --accent2: #0099cc;
    --accent3: #cc1155;
    --text: #111133;
    --muted: #5555aa;
    --glow: rgba(107,31,239,0.2);
    --glow2: rgba(0,153,204,0.2);
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Rajdhani', sans-serif;
    min-height: 100vh;
    overflow-x: hidden;
    transition: background 0.4s, color 0.4s;
  }
  /* Animated background */
  body::before {
    content: '';
    position: fixed; inset: 0; z-index: 0;
    background:
      radial-gradient(ellipse at 20% 20%, rgba(123,47,255,0.15) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 80%, rgba(0,212,255,0.1) 0%, transparent 50%),
      radial-gradient(ellipse at 50% 50%, rgba(255,45,120,0.05) 0%, transparent 70%);
    animation: bgPulse 8s ease-in-out infinite alternate;
    pointer-events: none;
  }
  @keyframes bgPulse {
    0% { opacity: 0.6; }
    100% { opacity: 1; }
  }
  /* Grid overlay */
  body::after {
    content: '';
    position: fixed; inset: 0; z-index: 0;
    background-image:
      linear-gradient(rgba(123,47,255,0.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(123,47,255,0.05) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
  }
  .container { position: relative; z-index: 1; max-width: 900px; margin: 0 auto; padding: 20px; }

  /* Header */
  header { text-align: center; padding: 50px 0 30px; }
  .logo-wrap { display: inline-block; position: relative; }
  .logo {
    font-family: 'Orbitron', monospace;
    font-size: clamp(2.5rem, 8vw, 5rem);
    font-weight: 900;
    background: linear-gradient(135deg, var(--accent), var(--accent2), var(--accent3));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: 4px;
    animation: logoGlow 3s ease-in-out infinite;
    filter: drop-shadow(0 0 30px var(--glow));
  }
  @keyframes logoGlow {
    0%, 100% { filter: drop-shadow(0 0 20px var(--glow)); }
    50% { filter: drop-shadow(0 0 50px var(--glow)) drop-shadow(0 0 80px var(--glow2)); }
  }
  .tagline {
    color: var(--muted);
    font-size: 1.1rem;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-top: 8px;
    animation: fadeInUp 1s ease 0.3s both;
  }
  .badge {
    display: inline-block;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    color: #fff;
    font-size: 0.7rem;
    padding: 3px 10px;
    border-radius: 20px;
    letter-spacing: 2px;
    margin-top: 10px;
    font-family: 'Orbitron', monospace;
  }

  /* Theme toggle */
  .theme-btn {
    position: fixed; top: 20px; right: 20px; z-index: 100;
    background: var(--card);
    border: 1px solid var(--border);
    color: var(--text);
    width: 44px; height: 44px;
    border-radius: 50%;
    cursor: pointer;
    font-size: 1.2rem;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.3s;
    box-shadow: 0 0 20px var(--glow);
  }
  .theme-btn:hover { transform: scale(1.1); box-shadow: 0 0 30px var(--glow); }

  /* Input card */
  .input-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 30px;
    margin: 30px 0;
    box-shadow: 0 0 60px var(--glow), inset 0 1px 0 rgba(255,255,255,0.05);
    animation: fadeInUp 0.8s ease 0.2s both;
    position: relative;
    overflow: hidden;
  }
  .input-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--accent), var(--accent2), var(--accent3));
    animation: scanLine 3s linear infinite;
  }
  @keyframes scanLine {
    0% { background-position: -100% 0; }
    100% { background-position: 200% 0; }
  }
  .input-label {
    font-family: 'Orbitron', monospace;
    font-size: 0.75rem;
    color: var(--accent2);
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 12px;
    display: block;
  }
  .url-row { display: flex; gap: 12px; }
  .url-input {
    flex: 1;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 18px;
    color: var(--text);
    font-family: 'Rajdhani', sans-serif;
    font-size: 1rem;
    outline: none;
    transition: all 0.3s;
  }
  .url-input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 20px var(--glow);
  }
  .url-input::placeholder { color: var(--muted); }
  .fetch-btn {
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    border: none;
    border-radius: 12px;
    padding: 14px 28px;
    color: #fff;
    font-family: 'Orbitron', monospace;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.3s;
    white-space: nowrap;
    position: relative;
    overflow: hidden;
  }
  .fetch-btn::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(255,255,255,0.2), transparent);
    opacity: 0;
    transition: opacity 0.3s;
  }
  .fetch-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 30px var(--glow); }
  .fetch-btn:hover::after { opacity: 1; }
  .fetch-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

  /* Loader */
  .loader { display: none; text-align: center; padding: 30px; }
  .spinner {
    width: 50px; height: 50px;
    border: 3px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 15px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .loader-text {
    color: var(--muted);
    font-family: 'Orbitron', monospace;
    font-size: 0.8rem;
    letter-spacing: 2px;
    animation: blink 1.2s ease-in-out infinite;
  }
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }

  /* Result card */
  .result-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 25px;
    margin: 20px 0;
    display: none;
    animation: slideIn 0.5s ease;
    box-shadow: 0 0 40px var(--glow2);
  }
  @keyframes slideIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .file-info { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 20px; }
  .info-item {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px;
    transition: all 0.3s;
  }
  .info-item:hover { border-color: var(--accent); box-shadow: 0 0 15px var(--glow); }
  .info-label { font-size: 0.7rem; color: var(--muted); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 5px; }
  .info-value { font-size: 1.1rem; font-weight: 600; color: var(--text); word-break: break-word; }

  /* Action buttons */
  .actions { display: flex; gap: 12px; flex-wrap: wrap; }
  .action-btn {
    flex: 1; min-width: 140px;
    padding: 16px 20px;
    border: none;
    border-radius: 14px;
    font-family: 'Orbitron', monospace;
    font-size: 0.8rem;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s;
    display: flex; align-items: center; justify-content: center; gap: 8px;
    letter-spacing: 1px;
    position: relative;
    overflow: hidden;
  }
  .watch-btn {
    background: linear-gradient(135deg, #7b2fff, #00d4ff);
    color: #fff;
  }
  .watch-btn:hover { transform: translateY(-3px); box-shadow: 0 10px 30px rgba(123,47,255,0.5); }
  .download-btn {
    background: linear-gradient(135deg, #ff2d78, #ff8c00);
    color: #fff;
  }
  .download-btn:hover { transform: translateY(-3px); box-shadow: 0 10px 30px rgba(255,45,120,0.5); }

  /* Quality selector */
  .quality-panel {
    display: none;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px;
    margin-top: 15px;
    animation: slideIn 0.3s ease;
  }
  .quality-label { font-family: 'Orbitron', monospace; font-size: 0.75rem; color: var(--accent2); letter-spacing: 2px; margin-bottom: 12px; display: block; }
  .quality-grid { display: flex; gap: 10px; flex-wrap: wrap; }
  .q-btn {
    padding: 10px 18px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text);
    font-family: 'Orbitron', monospace;
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.2s;
  }
  .q-btn:hover, .q-btn.active {
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    border-color: transparent;
    color: #fff;
    box-shadow: 0 4px 15px var(--glow);
  }
  .start-dl-btn {
    width: 100%;
    margin-top: 12px;
    padding: 13px;
    background: linear-gradient(135deg, #ff2d78, #ff8c00);
    border: none;
    border-radius: 10px;
    color: #fff;
    font-family: 'Orbitron', monospace;
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.3s;
    display: none;
  }
  .start-dl-btn:hover { box-shadow: 0 6px 20px rgba(255,45,120,0.5); }

  /* Video player */
  .player-panel {
    display: none;
    margin-top: 15px;
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid var(--border);
    animation: slideIn 0.4s ease;
  }
  #videoPlayer {
    width: 100%;
    max-height: 450px;
    background: #000;
    display: block;
  }

  /* Error */
  .error-box {
    background: rgba(255,45,120,0.1);
    border: 1px solid rgba(255,45,120,0.4);
    border-radius: 12px;
    padding: 16px;
    color: #ff6699;
    display: none;
    margin-top: 15px;
    font-size: 0.95rem;
  }

  /* Footer */
  footer {
    text-align: center;
    padding: 40px 0 20px;
    color: var(--muted);
    font-size: 0.85rem;
    letter-spacing: 1px;
  }
  footer span { color: var(--accent); }

  /* Particles */
  .particles { position: fixed; inset: 0; pointer-events: none; z-index: 0; overflow: hidden; }
  .particle {
    position: absolute;
    border-radius: 50%;
    animation: floatUp linear infinite;
    opacity: 0;
  }
  @keyframes floatUp {
    0% { transform: translateY(100vh) scale(0); opacity: 0; }
    10% { opacity: 0.6; }
    90% { opacity: 0.3; }
    100% { transform: translateY(-10vh) scale(1); opacity: 0; }
  }

  @keyframes fadeInUp {
    from { opacity: 0; transform: translateY(30px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* Responsive */
  @media(max-width:600px) {
    .url-row { flex-direction: column; }
    .logo { font-size: 2.2rem; }
  }
</style>
</head>
<body>
<div class="particles" id="particles"></div>
<button class="theme-btn" onclick="toggleTheme()" title="Toggle Theme">🌙</button>
<div class="container">
  <header>
    <div class="logo-wrap">
      <div class="logo">TERASCRAP</div>
    </div>
    <div class="tagline">⚡ Terabox Ultra Video Fetcher ⚡</div>
    <div class="badge">POWERED BY AI COOKIES 🍪</div>
  </header>

  <div class="input-card">
    <label class="input-label">🔗 Paste Terabox / 1024terabox URL</label>
    <div class="url-row">
      <input class="url-input" id="urlInput" type="url" placeholder="https://1024terabox.com/s/..." />
      <button class="fetch-btn" id="fetchBtn" onclick="fetchInfo()">⚡ FETCH</button>
    </div>
    <div class="loader" id="loader">
      <div class="spinner"></div>
      <div class="loader-text">FETCHING VIDEO DATA...</div>
    </div>
    <div class="error-box" id="errorBox"></div>
  </div>

  <div class="result-card" id="resultCard">
    <div class="file-info" id="fileInfo"></div>
    <div class="actions">
      <button class="action-btn watch-btn" onclick="toggleWatch()">▶ WATCH NOW</button>
      <button class="action-btn download-btn" onclick="toggleDownload()">⬇ DOWNLOAD</button>
    </div>
    <div class="quality-panel" id="qualityPanel">
      <span class="quality-label">🎬 SELECT QUALITY</span>
      <div class="quality-grid" id="qualityGrid"></div>
      <button class="start-dl-btn" id="startDlBtn" onclick="startDownload()">⬇ START DOWNLOAD</button>
    </div>
    <div class="player-panel" id="playerPanel">
      <video id="videoPlayer" controls playsinline></video>
    </div>
  </div>
</div>

<footer>
  <p>Copyright &copy; <span>Dr. Dev || Dr. Hamza</span> 2026 — All Rights Reserved</p>
  <p style="margin-top:6px; font-size:0.75rem; letter-spacing:2px;">TERASCRAP — BUILT WITH 💜 FOR THE COMMUNITY</p>
</footer>

<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<script>
let videoInfo = null;
let selectedQuality = null;
let currentUrl = '';
let hlsInstance = null;
let watchOpen = false;
let dlOpen = false;

// Particles
(function(){
  const container = document.getElementById('particles');
  const colors = ['#7b2fff','#00d4ff','#ff2d78','#ffffff'];
  for(let i=0;i<25;i++){
    const p = document.createElement('div');
    p.className = 'particle';
    const size = Math.random()*4+2;
    p.style.cssText = `
      width:${size}px; height:${size}px;
      left:${Math.random()*100}%;
      background:${colors[Math.floor(Math.random()*colors.length)]};
      animation-duration:${Math.random()*15+10}s;
      animation-delay:${Math.random()*10}s;
    `;
    container.appendChild(p);
  }
})();

function toggleTheme(){
  const html = document.documentElement;
  const isDark = html.getAttribute('data-theme') === 'dark';
  html.setAttribute('data-theme', isDark ? 'light' : 'dark');
  document.querySelector('.theme-btn').textContent = isDark ? '🌙' : '☀️';
}

async function fetchInfo(){
  const url = document.getElementById('urlInput').value.trim();
  if(!url){ showError('Please paste a valid Terabox URL! 🔗'); return; }
  currentUrl = url;
  document.getElementById('fetchBtn').disabled = true;
  document.getElementById('loader').style.display = 'block';
  document.getElementById('errorBox').style.display = 'none';
  document.getElementById('resultCard').style.display = 'none';
  hideWatch(); hideDl();

  try {
    const resp = await fetch('/api/fetch', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({url})
    });
    const data = await resp.json();
    if(data.error) throw new Error(data.error);
    videoInfo = data.info;
    showResult();
  } catch(e) {
    showError('❌ ' + e.message);
  } finally {
    document.getElementById('loader').style.display = 'none';
    document.getElementById('fetchBtn').disabled = false;
  }
}

function showResult(){
  const card = document.getElementById('resultCard');
  card.style.display = 'block';
  document.getElementById('fileInfo').innerHTML = `
    <div class="info-item"><div class="info-label">📄 File Name</div><div class="info-value">${videoInfo.name}</div></div>
    <div class="info-item"><div class="info-label">📦 Size</div><div class="info-value">${videoInfo.size}</div></div>
    <div class="info-item"><div class="info-label">🎞 Quality</div><div class="info-value">${videoInfo.quality}</div></div>
    <div class="info-item"><div class="info-label">⏱ Duration</div><div class="info-value">${videoInfo.duration}</div></div>
  `;
  // Populate quality grid
  const grid = document.getElementById('qualityGrid');
  grid.innerHTML = '';
  videoInfo.qualities.forEach(q => {
    const btn = document.createElement('button');
    btn.className = 'q-btn'; btn.textContent = q;
    btn.onclick = () => { selectedQuality = q; document.querySelectorAll('.q-btn').forEach(b=>b.classList.remove('active')); btn.classList.add('active'); document.getElementById('startDlBtn').style.display='block'; };
    grid.appendChild(btn);
  });
}

function showError(msg){
  const box = document.getElementById('errorBox');
  box.style.display = 'block';
  box.textContent = msg;
}

function toggleWatch(){
  if(watchOpen){ hideWatch(); return; }
  hideDl(); watchOpen = true;
  const panel = document.getElementById('playerPanel');
  panel.style.display = 'block';
  loadStream();
}

async function loadStream(){
  try {
    const resp = await fetch('/api/stream', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({url: currentUrl, quality: selectedQuality || ''})
    });
    const data = await resp.json();
    if(data.error) throw new Error(data.error);
    const video = document.getElementById('videoPlayer');
    if(hlsInstance){ hlsInstance.destroy(); hlsInstance = null; }
    if(Hls.isSupported()){
      hlsInstance = new Hls();
      hlsInstance.loadSource(data.stream_url);
      hlsInstance.attachMedia(video);
      hlsInstance.on(Hls.Events.MANIFEST_PARSED, ()=>video.play());
    } else if(video.canPlayType('application/vnd.apple.mpegurl')){
      video.src = data.stream_url;
      video.play();
    }
  } catch(e) { showError('Stream error: ' + e.message); }
}

function hideWatch(){
  watchOpen = false;
  document.getElementById('playerPanel').style.display = 'none';
  const video = document.getElementById('videoPlayer');
  video.pause();
  if(hlsInstance){ hlsInstance.destroy(); hlsInstance = null; }
  video.src = '';
}

function toggleDownload(){
  if(dlOpen){ hideDl(); return; }
  hideWatch(); dlOpen = true;
  document.getElementById('qualityPanel').style.display = 'block';
}

function hideDl(){
  dlOpen = false;
  document.getElementById('qualityPanel').style.display = 'none';
  document.getElementById('startDlBtn').style.display = 'none';
  selectedQuality = null;
  document.querySelectorAll('.q-btn').forEach(b=>b.classList.remove('active'));
}

async function startDownload(){
  if(!selectedQuality){ showError('Please select a quality first! 🎬'); return; }
  try {
    const resp = await fetch('/api/stream', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({url: currentUrl, quality: selectedQuality})
    });
    const data = await resp.json();
    if(data.error) throw new Error(data.error);
    const a = document.createElement('a');
    a.href = data.stream_url;
    a.download = videoInfo.name + '_' + selectedQuality + '.m3u8';
    a.target = '_blank';
    a.click();
  } catch(e) { showError('Download error: ' + e.message); }
}

document.getElementById('urlInput').addEventListener('keydown', e => { if(e.key==='Enter') fetchInfo(); });
</script>
</body>
</html>"""

WATCH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0,user-scalable=no"/>
<title>TeraScrap Player</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body { width:100%; height:100%; background:#000; overflow:hidden; }
  #player { width:100vw; height:100vh; display:block; }
  #loader {
    position:fixed; inset:0; background:#000;
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    font-family:monospace; color:#7b2fff; z-index:10;
  }
  .ld-ring {
    width:60px; height:60px;
    border:3px solid #1a1a4a;
    border-top-color:#7b2fff;
    border-radius:50%;
    animation:spin 0.8s linear infinite;
    margin-bottom:15px;
  }
  @keyframes spin{to{transform:rotate(360deg)}}
  #loader p { font-size:0.8rem; letter-spacing:3px; animation:blink 1.2s infinite; }
  @keyframes blink{0%,100%{opacity:1}50%{opacity:0.3}}
  #errorMsg {
    position:fixed; inset:0; background:#000;
    display:none; flex-direction:column; align-items:center; justify-content:center;
    font-family:monospace; color:#ff2d78; text-align:center; padding:20px;
  }
</style>
</head>
<body>
<div id="loader"><div class="ld-ring"></div><p>LOADING STREAM...</p></div>
<div id="errorMsg"></div>
<video id="player" controls playsinline autoplay></video>

<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<script>
const params = new URLSearchParams(location.search);
const streamUrl = params.get('url');
const loader = document.getElementById('loader');
const errorMsg = document.getElementById('errorMsg');

if(!streamUrl){
  loader.style.display='none';
  errorMsg.style.display='flex';
  errorMsg.innerHTML='<h2>❌ No stream URL</h2><p>Please provide a stream URL.</p>';
} else {
  const video = document.getElementById('player');
  if(Hls.isSupported()){
    const hls = new Hls();
    hls.loadSource(streamUrl);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, ()=>{
      loader.style.display='none';
      video.play();
    });
    hls.on(Hls.Events.ERROR, (e,d)=>{
      if(d.fatal){
        loader.style.display='none';
        errorMsg.style.display='flex';
        errorMsg.innerHTML='<h2>❌ Stream Error</h2><p>'+d.type+'</p>';
      }
    });
  } else if(video.canPlayType('application/vnd.apple.mpegurl')){
    video.src = streamUrl;
    video.addEventListener('canplay',()=>{ loader.style.display='none'; video.play(); });
  }
}

// Auto fullscreen + screen rotation
document.addEventListener('click', ()=>{
  const el = document.getElementById('player');
  if(el.requestFullscreen) el.requestFullscreen();
  if(screen.orientation && screen.orientation.lock){
    screen.orientation.lock('landscape').catch(()=>{});
  }
}, {once:true});
</script>
</body>
</html>"""

DOWNLOAD_HTML = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>TeraScrap – Download</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@400;600&display=swap" rel="stylesheet"/>
<style>
  :root { --bg:#050510; --card:#0f0f2a; --border:#1a1a4a; --accent:#7b2fff; --accent2:#00d4ff; --accent3:#ff2d78; --text:#e8e8ff; --muted:#6666aa; }
  *{margin:0;padding:0;box-sizing:border-box;}
  body { background:var(--bg); color:var(--text); font-family:'Rajdhani',sans-serif; min-height:100vh; display:flex; align-items:center; justify-content:center; padding:20px; }
  .wrap { max-width:600px; width:100%; }
  h1 { font-family:'Orbitron',monospace; font-size:1.8rem; background:linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:25px; text-align:center; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:16px; padding:25px; margin-bottom:20px; }
  label { font-family:'Orbitron',monospace; font-size:0.7rem; color:var(--accent2); letter-spacing:2px; display:block; margin-bottom:8px; }
  input { width:100%; background:#050510; border:1px solid var(--border); border-radius:10px; padding:12px 16px; color:var(--text); font-family:'Rajdhani',sans-serif; font-size:1rem; outline:none; margin-bottom:15px; }
  input:focus { border-color:var(--accent); }
  .q-grid { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:15px; }
  .q-btn { padding:10px 18px; background:#0a0a20; border:1px solid var(--border); border-radius:10px; color:var(--text); font-family:'Orbitron',monospace; font-size:0.75rem; cursor:pointer; transition:all 0.2s; }
  .q-btn.active { background:linear-gradient(135deg,var(--accent),var(--accent2)); border-color:transparent; color:#fff; }
  .dl-btn { width:100%; padding:14px; background:linear-gradient(135deg,#ff2d78,#ff8c00); border:none; border-radius:12px; color:#fff; font-family:'Orbitron',monospace; font-size:0.85rem; cursor:pointer; transition:all 0.3s; }
  .dl-btn:hover { box-shadow:0 8px 25px rgba(255,45,120,0.5); }
  .status { text-align:center; padding:12px; border-radius:10px; font-size:0.9rem; display:none; margin-top:12px; }
  .status.loading { background:rgba(123,47,255,0.15); color:var(--accent2); display:block; }
  .status.error { background:rgba(255,45,120,0.15); color:#ff6699; display:block; }
  .progress { height:4px; background:var(--border); border-radius:2px; overflow:hidden; margin-top:10px; display:none; }
  .progress-bar { height:100%; background:linear-gradient(90deg,var(--accent),var(--accent2)); animation:progress 2s ease-in-out infinite; }
  @keyframes progress { 0%{width:0%} 50%{width:70%} 100%{width:100%} }
</style>
</head>
<body>
<div class="wrap">
  <h1>⬇ TERASCRAP<br/>DOWNLOADER</h1>
  <div class="card">
    <label>🔗 TERABOX URL</label>
    <input id="urlIn" type="url" placeholder="https://1024terabox.com/s/..."/>
    <label>🎬 SELECT QUALITY</label>
    <div id="qGrid" class="q-grid"><p style="color:var(--muted);font-size:0.9rem;">Fetch URL first to see qualities</p></div>
    <button class="dl-btn" onclick="doFetchThenDownload()">⬇ FETCH & DOWNLOAD</button>
    <div class="status" id="status"></div>
    <div class="progress" id="prog"><div class="progress-bar"></div></div>
  </div>
</div>
<script>
let selectedQ = null;
let lastUrl = '';
let streamData = null;

async function doFetchThenDownload(){
  const url = document.getElementById('urlIn').value.trim();
  if(!url){ showStatus('Please enter a URL!','error'); return; }
  showStatus('Fetching video info...','loading');
  document.getElementById('prog').style.display='block';
  try {
    const r = await fetch('/api/fetch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})});
    const d = await r.json();
    if(d.error) throw new Error(d.error);
    lastUrl = url;
    const qualities = d.info.qualities;
    const grid = document.getElementById('qGrid');
    grid.innerHTML='';
    qualities.forEach(q=>{
      const b=document.createElement('button');b.className='q-btn';b.textContent=q;
      b.onclick=()=>{selectedQ=q;document.querySelectorAll('.q-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');};
      grid.appendChild(b);
    });
    if(qualities.length>0){selectedQ=qualities[qualities.length-1]; grid.lastChild.classList.add('active');}
    showStatus('Quality selected! Click again to download.','loading');
    document.getElementById('prog').style.display='none';
  } catch(e){
    showStatus('Error: '+e.message,'error');
    document.getElementById('prog').style.display='none';
  }
}

async function doFetchThenDownload(){
  const url = document.getElementById('urlIn').value.trim();
  if(!url){ showStatus('Please enter a URL!','error'); return; }
  if(lastUrl !== url || !streamData){
    showStatus('Fetching video info...','loading');
    document.getElementById('prog').style.display='block';
    try{
      const r=await fetch('/api/fetch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})});
      const d=await r.json();
      if(d.error) throw new Error(d.error);
      lastUrl=url;
      const grid=document.getElementById('qGrid'); grid.innerHTML='';
      d.info.qualities.forEach(q=>{
        const b=document.createElement('button');b.className='q-btn';b.textContent=q;
        b.onclick=()=>{selectedQ=q;document.querySelectorAll('.q-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');};
        grid.appendChild(b);
      });
      if(d.info.qualities.length>0){selectedQ=d.info.qualities[d.info.qualities.length-1];grid.lastChild.classList.add('active');}
      document.getElementById('prog').style.display='none';
      showStatus('✅ Select quality & click again to download','loading');
      return;
    }catch(e){showStatus('Error: '+e.message,'error');document.getElementById('prog').style.display='none';return;}
  }
  // Actually download
  showStatus('Getting stream URL...','loading');
  document.getElementById('prog').style.display='block';
  try{
    const r=await fetch('/api/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,quality:selectedQ})});
    const d=await r.json();
    if(d.error) throw new Error(d.error);
    window.open(d.stream_url,'_blank');
    showStatus('✅ Stream opened! Use a download manager for best results.','loading');
  }catch(e){showStatus('Error: '+e.message,'error');}
  document.getElementById('prog').style.display='none';
  lastUrl='';
}

function showStatus(msg,type){
  const s=document.getElementById('status');
  s.className='status '+type; s.textContent=msg;
}
</script>
</body>
</html>"""

# ── TELEGRAM BOT ───────────────────────────────────────────────
GREETING = """🌟✨ *TeraScrap Bot mein aapka swagat hai!* ✨🌟

━━━━━━━━━━━━━━━━━━━━━━
🎬 *Mein kya kar sakta hoon?*
━━━━━━━━━━━━━━━━━━━━━━

🔥 Terabox ya 1024terabox ka koi bhi video URL bhejo — mein turant:
   • 📊 Video ki full info fetch karunga
   • ▶️ *Watch* ka option dunga — seedha Telegram mein play
   • ⬇️ *Download* ka option dunga — quality choose karo

━━━━━━━━━━━━━━━━━━━━━━
📌 *Kaise use karein?*
━━━━━━━━━━━━━━━━━━━━━━

1️⃣ Koi bhi Terabox video link copy karo
2️⃣ Yahan paste karo aur send karo
3️⃣ Watch ya Download choose karo
4️⃣ Quality select karo — ho gaya! 🎉

━━━━━━━━━━━━━━━━━━━━━━
💡 *Supported Links:*
• `1024terabox.com`
• `terabox.com`
• `teraboxapp.com`
━━━━━━━━━━━━━━━━━━━━━━

👨‍💻 *Developer:* @Hamza3895
💜 _TeraScrap — Built with love for the community_"""

PROCESSING_MSG = "⚡ *Processing your link...*\n\n🔄 Fetching video info, thoda wait karo bhai! 🙏"

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        GREETING,
        parse_mode="Markdown"
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not re.match(r'https?://', url):
        await update.message.reply_text(
            "❌ *Yaar, ye toh valid URL nahi hai!*\n\nTerabox ka link bhejo bhai 🙏",
            parse_mode="Markdown"
        )
        return

    processing = await update.message.reply_text(PROCESSING_MSG, parse_mode="Markdown")

    try:
        info = await asyncio.get_event_loop().run_in_executor(None, fetch_video_info, url)
        streams = info.get("fast_stream_url", {})
        qualities = sorted(streams.keys(), key=lambda q: int(q.replace("p",""))) if isinstance(streams, dict) else []

        text = f"""✅ *Video Found!* 🎬

📄 *Name:* `{info.get('name','N/A')[:50]}`
📦 *Size:* `{info.get('size_formatted','N/A')}`
🎞 *Quality:* `{info.get('quality','N/A')}`
⏱ *Duration:* `{info.get('duration','N/A')}`
🎯 *Streams:* `{', '.join(qualities) if qualities else 'N/A'}`

━━━━━━━━━━━━━━━━━━━━━
_Ab kya karna chahte ho?_ 👇"""

        # Build buttons
        watch_url = f"{WEBAPP_URL}/watch?url={url}"
        dl_url = f"{WEBAPP_URL}/download?url={url}"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("▶️ Watch Now", web_app=WebAppInfo(url=watch_url)),
                InlineKeyboardButton("⬇️ Download", web_app=WebAppInfo(url=dl_url))
            ],
            [
                InlineKeyboardButton("🌐 Open WebApp", web_app=WebAppInfo(url=f"{WEBAPP_URL}/?url={url}"))
            ]
        ])

        await processing.delete()
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

    except Exception as e:
        await processing.edit_text(
            f"❌ *Error aa gaya bhai!*\n\n`{str(e)[:200]}`\n\n_Thodi der baad dobara try karo_ 🙏",
            parse_mode="Markdown"
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

def run_bot():
    async def _run():
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start_cmd))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
        app.add_handler(CallbackQueryHandler(handle_callback))
        logger.info("🤖 Telegram bot starting...")
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("✅ Bot is running!")
        # Keep alive
        while True:
            await asyncio.sleep(60)

    asyncio.run(_run())

# ── ENTRY POINT ────────────────────────────────────────────────
if __name__ == "__main__":
    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    logger.info(f"🌐 Starting Flask on port {PORT}...")
    flask_app.run(host="0.0.0.0", port=PORT, debug=False)
