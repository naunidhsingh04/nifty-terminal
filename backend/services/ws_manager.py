import json
from typing import List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.clients: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.append(ws)
        print(f"🔌 Client connected. Total: {len(self.clients)}")

    def disconnect(self, ws: WebSocket):
        if ws in self.clients:
            self.clients.remove(ws)
        print(f"🔌 Client disconnected. Total: {len(self.clients)}")

    async def broadcast(self, data: dict):
        if not self.clients:
            return
        msg  = json.dumps(data)
        dead = []
        for client in self.clients:
            try:
                await client.send_text(msg)
            except Exception:
                dead.append(client)
        for d in dead:
            self.disconnect(d)

    async def send_to(self, ws: WebSocket, data: dict):
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            self.disconnect(ws)

manager = ConnectionManager()
