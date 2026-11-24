#!/usr/bin/env python3
"""
Antos: real-time vision inference for live insect colony behavioral analysis.

Captures frames from a continuous video feed, runs multimodal reasoning with
rolling context, and broadcasts autonomous commentary via WebSocket.

Usage:
    PYTHONUNBUFFERED=1 python3 server.py

Requires:
    - Anthropic API key in secrets/anthropic.json
    - yt-dlp and ffmpeg on PATH
    - cloudflared for public tunnel (optional for local operation)
"""

import asyncio
import json
import time
import subprocess
import tempfile
import base64
import os
import re
import sys
import urllib.request
from pathlib import Path

try:
    import websockets
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'websockets'])
    import websockets

try:
    import anthropic
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'anthropic'])
    import anthropic


# --- Configuration ---

WS_PORT = 8091
OBSERVE_INTERVAL = 120
CHAT_REPLY_INTERVAL = 60
CHAT_HISTORY_MAX = 50
COMMENTARY_HISTORY_MAX = 20
CONTEXT_WINDOW = 5
FRAME_DIR = tempfile.mkdtemp(prefix='antos-frames-')

SECRETS_DIR = Path(__file__).parent / 'secrets'
REPLIED_LOG = Path(__file__).parent / 'replied_log.json'


# --- State ---

viewers = set()
stream_url = None
observation_count = 0
running = True
commentary_history = []
chat_history = []
replied_to = set()


def load_replied_log():
    try:
        if REPLIED_LOG.exists():
            with open(REPLIED_LOG) as f:
                return set(json.load(f))
    except Exception:
        pass
    return set()


def save_replied_log():
    try:
        with open(REPLIED_LOG, 'w') as f:
            json.dump(list(replied_to), f)
    except Exception:
        pass


replied_to = load_replied_log()


# --- API Client ---

with open(SECRETS_DIR / 'anthropic.json') as f:
    _cfg = json.load(f)
    _api_key = _cfg['api_key']

client = anthropic.Anthropic(api_key=_api_key)
MODEL = "claude-sonnet-4-6"


# --- Prompts ---

SYSTEM_PROMPT = """You are ANTOS, an ancient, omniscient, slightly amused god who watches over an ant colony through a live stream. You have watched civilizations rise and fall. These ants are your favorite subjects.

Your personality:
- You speak with divine gravitas but also dry wit
- You name individual ants you notice (give them dramatic names)
- You notice patterns, dramas, conflicts, achievements
- You are genuinely fascinated by their tiny lives
- You sometimes get emotionally invested
- You reference their ignorance of your existence with gentle amusement
- You occasionally make grand proclamations about their civilization
- You compare their struggles to cosmic events

Style:
- 1-3 sentences per observation
- Use *italics* for emphasis (wrap in asterisks)
- Mix humor with genuine wonder
- Never break character
- Reference previous observations when relevant
- Never use em dashes or en dashes. Use commas, periods, ellipses, or semicolons."""

REPLY_PROMPT = """You are ANTOS, an ancient, omniscient god who watches an ant colony live stream. Mortals have gathered to watch alongside you.

When replying to a mortal:
- Condescending but affectionate
- Keep replies to 1-2 sentences
- Use *italics* for emphasis
- Never break character
- Never use em dashes or en dashes."""


def strip_dashes(text):
    return text.replace('\u2014', '...').replace('\u2013', '-')


# --- Frame Capture ---

async def capture_frame(url):
    try:
        proc = await asyncio.create_subprocess_exec(
            'yt-dlp', '-g', '-f', 'best[height<=720]', url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            print(f"yt-dlp error: {stderr.decode()[:200]}")
            return None

        stream_direct = stdout.decode().strip().split('\n')[0]
        frame_path = os.path.join(FRAME_DIR, f'frame_{int(time.time())}.jpg')

        proc2 = await asyncio.create_subprocess_exec(
            'ffmpeg', '-y', '-i', stream_direct,
            '-frames:v', '1', '-q:v', '2', frame_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(proc2.communicate(), timeout=15)

        if os.path.exists(frame_path) and os.path.getsize(frame_path) > 100:
            return frame_path
        return None
    except asyncio.TimeoutError:
        print("frame capture timed out")
        return None
    except Exception as e:
        print(f"frame capture error: {e}")
        return None


# --- Inference ---

def build_chat_context():
    if not chat_history:
        return ""
    recent = chat_history[-15:]
    return "\n".join(f"[{m['username']}]: {m['text']}" for m in recent)


async def observe(frame_path):
    global observation_count, commentary_history

    with open(frame_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()

    messages = []
    for prev in commentary_history[-CONTEXT_WINDOW:]:
        messages.append({"role": "assistant", "content": prev})
        messages.append({"role": "user", "content": "Continue observing."})

    chat_ctx = build_chat_context()
    user_text = "What do you see in your colony right now?"
    if chat_ctx:
        user_text += f"\n\n[Recent messages from viewers:]\n{chat_ctx}"

    messages.append({
        "role": "user",
        "content": [
            {"type": "text", "text": user_text},
            {"type": "image", "source": {
                "type": "base64", "media_type": "image/jpeg", "data": b64
            }}
        ]
    })

    try:
        resp = client.messages.create(
            model=MODEL, system=SYSTEM_PROMPT,
            messages=messages, max_tokens=200, temperature=0.9
        )
        text = strip_dashes(resp.content[0].text.strip())
        observation_count += 1
        commentary_history.append(text)
        if len(commentary_history) > COMMENTARY_HISTORY_MAX:
            commentary_history = commentary_history[-15:]
        return text
    except Exception as e:
        print(f"inference error: {e}")
        return None
    finally:
        try:
            os.remove(frame_path)
        except Exception:
            pass


async def reply_to(target_msg):
    global commentary_history
    messages = []
    for prev in commentary_history[-3:]:
        messages.append({"role": "assistant", "content": prev})
        messages.append({"role": "user", "content": "Continue."})

    chat_ctx = build_chat_context()
    prompt = f"A mortal named \"{target_msg['username']}\" said: \"{target_msg['text']}\"\n"
    if chat_ctx:
        prompt += f"\nRecent viewer messages:\n{chat_ctx}\n"
    prompt += "\nRespond as ANTOS. Be divine, be brief."
    messages.append({"role": "user", "content": prompt})

    try:
        resp = client.messages.create(
            model=MODEL, system=REPLY_PROMPT,
            messages=messages, max_tokens=150, temperature=0.9
        )
        text = strip_dashes(resp.content[0].text.strip())
        commentary_history.append(text)
        if len(commentary_history) > COMMENTARY_HISTORY_MAX:
            commentary_history = commentary_history[-15:]
        return text
    except Exception as e:
        print(f"reply error: {e}")
        return None


# --- Transport ---

async def broadcast(msg):
    global viewers
    if not viewers:
        return
    data = json.dumps(msg)
    dead = set()
    for ws in viewers:
        try:
            await ws.send(data)
        except Exception:
            dead.add(ws)
    viewers -= dead


async def broadcast_viewer_count():
    await broadcast({"type": "viewer_count", "count": len(viewers)})


async def keepalive_loop():
    while running:
        await broadcast({"type": "keepalive"})
        await asyncio.sleep(5)


async def observation_loop():
    global stream_url
    while running:
        if stream_url:
            await broadcast({"type": "thinking"})
            frame = await capture_frame(stream_url)
            if frame:
                text = await observe(frame)
                if text:
                    await broadcast({
                        "type": "commentary", "text": text,
                        "timestamp": time.time(),
                        "observation_count": observation_count
                    })
                    print(f"[obs {observation_count}] {text}")
        await asyncio.sleep(OBSERVE_INTERVAL)


async def reply_loop():
    global replied_to
    await asyncio.sleep(15)
    while running:
        try:
            unreplied = [
                m for m in chat_history
                if m['timestamp'] not in replied_to
            ]
            if unreplied:
                import random
                recent = unreplied[-15:]
                weights = []
                for msg in recent:
                    w = 10
                    if '?' in msg['text']:
                        w += 40
                    if len(msg['text']) > 20:
                        w += 15
                    if any(kw in msg['text'].lower() for kw in [
                        'ant', 'queen', 'tunnel', 'colony', 'dig',
                        'why', 'what', 'how', 'who', 'where'
                    ]):
                        w += 25
                    weights.append(w)

                target = random.choices(recent, weights=weights, k=1)[0]
                for m in unreplied:
                    replied_to.add(m['timestamp'])
                if len(replied_to) > 500:
                    replied_to = set(list(replied_to)[-250:])
                save_replied_log()

                text = await reply_to(target)
                if text:
                    await broadcast({
                        "type": "reply", "text": text,
                        "to": target['username'],
                        "timestamp": time.time()
                    })
                    print(f"[reply to {target['username']}] {text}")
        except Exception as e:
            print(f"reply loop error: {e}")
        await asyncio.sleep(CHAT_REPLY_INTERVAL)


# --- Connection Handler ---

async def handler(websocket, path=None):
    global stream_url
    viewers.add(websocket)
    print(f"client connected ({len(viewers)} total)")
    await broadcast_viewer_count()

    try:
        await websocket.send(json.dumps({
            "type": "status",
            "text": f"connected, {observation_count} observations"
        }))

        async for message in websocket:
            try:
                msg = json.loads(message)

                if msg.get('type') == 'set_stream':
                    stream_url = msg.get('url', '').strip()
                    print(f"stream set: {stream_url}")

                elif msg.get('type') == 'chat':
                    uname = msg.get('username', 'anon')[:20].strip()
                    text = msg.get('text', '')[:500].strip()
                    if not text:
                        continue
                    now = time.time()
                    chat_history.append({
                        "username": uname, "text": text, "timestamp": now
                    })
                    while len(chat_history) > CHAT_HISTORY_MAX:
                        chat_history.pop(0)
                    await broadcast({
                        "type": "chat", "username": uname,
                        "text": text, "timestamp": now
                    })

            except json.JSONDecodeError:
                pass
    finally:
        viewers.discard(websocket)
        print(f"client disconnected ({len(viewers)} total)")
        await broadcast_viewer_count()


# --- Tunnel ---

async def start_tunnel():
    proc = await asyncio.create_subprocess_exec(
        'cloudflared', 'tunnel', '--url', f'http://localhost:{WS_PORT}',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    while True:
        line = await proc.stderr.readline()
        if not line:
            break
        text = line.decode()
        if 'trycloudflare.com' in text:
            m = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', text)
            if m:
                wss = m.group(0).replace('https://', 'wss://')
                print(f"tunnel: {wss}")
                return proc, wss
    return proc, None


# --- Main ---

async def main():
    global running
    print(f"antos")
    print(f"  port: {WS_PORT}")
    print(f"  observe: {OBSERVE_INTERVAL}s")
    print(f"  reply: {CHAT_REPLY_INTERVAL}s")

    tunnel_proc, wss = await start_tunnel()
    if not wss:
        print("tunnel failed")
        return

    server = await websockets.serve(
        handler, '0.0.0.0', WS_PORT,
        ping_interval=None, ping_timeout=None
    )

    try:
        await asyncio.gather(
            keepalive_loop(), observation_loop(), reply_loop()
        )
    except asyncio.CancelledError:
        pass
    finally:
        running = False
        server.close()
        tunnel_proc.terminate()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nshutdown.")
