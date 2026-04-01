from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import json, asyncio

app = FastAPI()

# Хранилище игровых комнат
rooms = {}

class Room:
    def __init__(self, room_id):
        self.room_id = room_id
        self.players = {}       # {name: websocket}
        self.marker = {"x": 400, "y": 300}
        self.drawing = True
        self.word = ""

    async def broadcast(self, data):
        dead = []
        for name, ws in self.players.items():
            try:
                await ws.send_text(json.dumps(data))
            except:
                dead.append(name)
        for name in dead:
            del self.players[name]

    def state(self):
        return {
            "type": "state",
            "marker": self.marker,
            "players": list(self.players.keys()),
            "drawing": self.drawing,
            "word": self.word
        }

@app.get("/")
async def root():
    return FileResponse("index.html")

@app.websocket("/ws/{room_id}/{player_name}")
async def websocket_endpoint(ws: WebSocket, room_id: str, player_name: str):
    await ws.accept()

    # Создаём комнату если нет
    if room_id not in rooms:
        rooms[room_id] = Room(room_id)
    room = rooms[room_id]
    room.players[player_name] = ws

    # Отправляем текущее состояние новому игроку
    await ws.send_text(json.dumps(room.state()))
    # Уведомляем всех о новом игроке
    await room.broadcast({"type": "players", "players": list(room.players.keys())})

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg["type"] == "vector":
                # Игрок тянет свою верёвку
                vx = msg.get("x", 0)
                vy = msg.get("y", 0)
                speed = 3
                room.marker["x"] = max(4, min(796, room.marker["x"] + vx * speed))
                room.marker["y"] = max(4, min(596, room.marker["y"] + vy * speed))
                await room.broadcast({
                    "type": "marker",
                    "x": room.marker["x"],
                    "y": room.marker["y"],
                    "drawing": room.drawing,
                    "player": player_name
                })

            elif msg["type"] == "penup":
                room.drawing = False
                await room.broadcast({"type": "penup"})

            elif msg["type"] == "pendown":
                room.drawing = True
                await room.broadcast({"type": "pendown"})

            elif msg["type"] == "clear":
                room.marker = {"x": 400, "y": 300}
                room.drawing = True
                await room.broadcast({"type": "clear"})

            elif msg["type"] == "word":
                room.word = msg.get("word", "")
                await room.broadcast({"type": "word", "word": room.word})

    except WebSocketDisconnect:
        if player_name in room.players:
            del room.players[player_name]
        await room.broadcast({"type": "players", "players": list(room.players.keys())})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
