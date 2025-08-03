from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI
import socketio
from pydantic import BaseModel, field_validator
import uvicorn

# Настройка сервера
app = FastAPI()
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
socket_app = socketio.ASGIApp(
    sio, app, static_files={"/": "static/index.html", "/static": "./static"}
)

# Хранилище данных
rooms: Dict[str, Dict] = {}
players: Dict[str, Dict] = {}


class Player(BaseModel):
    sid: str
    name: str
    room_id: str

class Room(BaseModel):
    id: str
    name: str
    questions_count: int
    context: str
    players: List[Player]
    created_at: str = datetime.now().isoformat()


# Обработчики подключений
@sio.event
async def connect(sid, environ):
    await sio.save_session(sid, {"connected_at": datetime.now().isoformat()})
    players[sid] = {"sid": sid, "name": None}


@sio.event
async def disconnect(sid):
    if sid in players:
        player = players[sid]
        if "room_id" in player:
            room_id = player["room_id"]
            if room_id in rooms:
                rooms[room_id]["players"] = [
                    p for p in rooms[room_id]["players"] if p["sid"] != sid
                ]
                if len(rooms[room_id]["players"]) == 0:
                    del rooms[room_id]
                    await sio.emit(
                        "rooms_list",
                        {
                            "rooms": [
                                {
                                    "id": r["id"],
                                    "name": r["name"],
                                    "context": r["context"],
                                    "players": r["players"],
                                    "created_at": r["created_at"],
                                }
                                for r in rooms.values()
                            ]
                        },
                    )
                else:
                    await sio.emit(
                        "update_players",
                        {"players": rooms[room_id]["players"]},
                        room=room_id,
                    )
        del players[sid]


# Обработчики комнат
@sio.on("create_room")
async def handle_create_room(sid, data):
    try:
        room_id = f"room_{len(rooms) + 1}"
        player = Player(sid=sid, name=data["player_name"], room_id=room_id)

        room = Room(
            id=room_id,
            name=data["name"],
            questions_count=data["questions_count"],
            context=data["context"],
            players=[player],
        )

        rooms[room_id] = room.model_dump()
        print(rooms)
        players[sid] = player.model_dump()
        print(players)
        await sio.enter_room(sid, data["name"])
        print(f"группы пользователя: {sio.rooms(sid)}")
        # await handle_join_room(sid, {"room_id": room_id, "player_name": data["player_name"]})
        # players[sid]["name"] = data["player_name"]
        # players[sid]["room_id"] = room_id

        await sio.save_session(
            sid, {"room_id": room_id, "player_name": data["player_name"]}
        )

        await sio.emit("room_created", {"room": room.model_dump()}, to=sid)
        await sio.emit(
            "rooms_list",
            {
                "rooms": [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "context": r["context"],
                        "players": r["players"],
                        "created_at": r["created_at"],
                    }
                    for r in rooms.values()
                ]
            },
        )

    except Exception as e:
        await sio.emit(
            "creation_error", {"message": f"Ошибка создания комнаты: {str(e)}"}, to=sid
        )


@sio.on("get_rooms")
async def handle_get_rooms(sid, environ):
    await sio.emit(
        "rooms_list",
        {
            "rooms": [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "context": r["context"],
                    "players": r["players"],
                    "created_at": r["created_at"],
                }
                for r in rooms.values()
            ]
        },
        to=sid,
    )


@sio.on("join_room")
async def handle_join_room(sid, data):
    try:
        room = rooms.get(data["room_id"])
        if not room:
            return await sio.emit(
                "join_error", {"message": "Комната не найдена"}, to=sid
            )

        player = Player(sid=sid, name=data["player_name"], room_id=data["room_id"])
        room["players"].append(player.model_dump())
        players[sid]["name"] = data["player_name"]
        players[sid]["room_id"] = data["room_id"]

        await sio.save_session(
            sid, {"room_id": data["room_id"], "player_name": data["player_name"]}
        )

        await sio.emit("update_players", {"players": room["players"]}, room=data["room_id"])
        await sio.emit("room_joined", {"room": room}, to=sid)

    except Exception as e:
        await sio.emit(
            "join_error", {"message": f"Ошибка присоединения: {str(e)}"}, to=sid
        )


# Чат
@sio.on("send_message")
async def handle_send_message(sid, data):
    session = await sio.get_session(sid)
    if "room_id" not in session:
        return

    await sio.emit(
        "new_message",
        {
            "sender": session["player_name"],
            "text": data["text"],
            "timestamp": datetime.now().isoformat(),
        },
        room=session["room_id"],
    )

if __name__ == '__main__':
    uvicorn.run(socket_app, host='0.0.0.0', port=8001)