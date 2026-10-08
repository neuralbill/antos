#!/usr/bin/env python3
"""Cloudflare tunnel management for public WebSocket access."""

import asyncio
import re


async def start_tunnel(port):
    """Start cloudflared quick tunnel, return (process, wss_url)."""
    proc = await asyncio.create_subprocess_exec(
        'cloudflared', 'tunnel', '--url', f'http://localhost:{port}',
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
                return proc, wss
    return proc, None
