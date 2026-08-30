#!/usr/bin/env python3
"""WebSocket transport layer for broadcasting observations."""

import asyncio
import json
import websockets

WS_PORT = 8091


class TransportLayer:
    def __init__(self, port=WS_PORT):
        self.port = port
        self.clients = set()

    async def broadcast(self, msg):
        if not self.clients:
            return
        data = json.dumps(msg)
        dead = set()
        for ws in self.clients:
            try:
                await ws.send(data)
            except Exception:
                dead.add(ws)
        self.clients -= dead

    async def handler(self, websocket, path=None):
        self.clients.add(websocket)
        try:
            async for msg in websocket:
                pass
        finally:
            self.clients.discard(websocket)

    async def start(self):
        server = await websockets.serve(
            self.handler, '0.0.0.0', self.port,
            ping_interval=None, ping_timeout=None
        )
        return server
