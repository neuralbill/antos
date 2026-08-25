#!/usr/bin/env python3
"""Continuous observation loop. Capture + analyze at interval."""

import asyncio
import time
import tempfile
import os
import base64
import json
from pathlib import Path

try:
    import anthropic
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'anthropic'])
    import anthropic

SECRETS_DIR = Path(__file__).parent / 'secrets'
INTERVAL = 60

with open(SECRETS_DIR / 'anthropic.json') as f:
    cfg = json.load(f)
    client = anthropic.Anthropic(api_key=cfg['api_key'])

MODEL = "claude-sonnet-4-6"


async def capture_frame(url):
    proc = await asyncio.create_subprocess_exec(
        'yt-dlp', '-g', '-f', 'best[height<=720]', url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    if proc.returncode != 0:
        return None

    stream_url = stdout.decode().strip().split('\n')[0]
    frame_path = tempfile.mktemp(suffix='.jpg', prefix='antos_')

    proc2 = await asyncio.create_subprocess_exec(
        'ffmpeg', '-y', '-i', stream_url,
        '-frames:v', '1', '-q:v', '2', frame_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await asyncio.wait_for(proc2.communicate(), timeout=15)

    if os.path.exists(frame_path) and os.path.getsize(frame_path) > 100:
        return frame_path
    return None


def analyze(frame_path):
    with open(frame_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()

    resp = client.messages.create(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe what you see in this frame."},
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/jpeg", "data": b64
                }}
            ]
        }],
        max_tokens=300
    )
    return resp.content[0].text


async def run(url):
    count = 0
    while True:
        frame = await capture_frame(url)
        if frame:
            text = analyze(frame)
            count += 1
            print(f"[{count}] {text}")
            try:
                os.remove(frame)
            except:
                pass
        else:
            print("frame capture failed, retrying...")
        await asyncio.sleep(INTERVAL)


if __name__ == '__main__':
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else None
    if not url:
        print("usage: observer.py <youtube_url>")
        sys.exit(1)
    asyncio.run(run(url))
