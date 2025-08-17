from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import socketio
from pydantic import BaseModel, field_validator
import uvicorn

# Настройка сервера
app = FastAPI()

# Middleware для добавления CSP заголовков
@app.middleware("http")
async def add_csp_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' 'nonce-handlebars-check' https://cdn.socket.io https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' https:; "
        "connect-src 'self' ws: wss:; "
        "frame-src 'self';"
    )
    return response

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
    messages: List[Dict] = []
    created_at: str = datetime.now().isoformat()


# Обработчики подключений
@sio.event
async def connect(sid, environ):
    await sio.save_session(sid, {"connected_at": datetime.now().isoformat()})
    players[sid] = {"sid": sid, "name": None, "room_id": None}


@sio.event
async def disconnect(sid):
    if sid in players:
        player = players[sid]
        if "room_id" in player and player["room_id"]:
            room_id = player["room_id"]
            if room_id in rooms:
                # Удаляем игрока из комнаты
                rooms[room_id]["players"] = [
                    p for p in rooms[room_id]["players"] if p["sid"] != sid
                ]
                
                # Отправляем уведомление в чат о выходе игрока
                await sio.emit(
                    "new_message",
                    {
                        "sender": "Система",
                        "text": f"Игрок {player.get('name', 'Неизвестный')} покинул комнату",
                        "timestamp": datetime.now().isoformat(),
                    },
                    room=room_id,
                )
                
                # Если комната пуста, удаляем её
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
                    # Обновляем список игроков для оставшихся
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
            messages=[],
        )

        rooms[room_id] = room.model_dump()
        print(rooms)
        players[sid] = player.model_dump()
        print(players)
        
        # Входим в комнату Socket.IO
        await sio.enter_room(sid, room_id)
        print(f"группы пользователя: {sio.rooms(sid)}")

        await sio.save_session(
            sid, {"room_id": room_id, "player_name": data["player_name"]}
        )

        # Отправляем уведомление о создании комнаты
        system_message = {
            "sender": "Система",
            "text": f"Комната '{data['name']}' создана игроком {data['player_name']}",
            "timestamp": datetime.now().isoformat(),
        }
        rooms[room_id]["messages"].append(system_message)
        print(f"💬 Системное сообщение добавлено в историю: {system_message}")
        
        # Отправляем системное сообщение в комнату (теперь пользователь уже в комнате)
        await sio.emit(
            "new_message",
            system_message,
            room=room_id,
        )
        print(f"📤 Системное сообщение отправлено в комнату {room_id}")

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

        # Входим в комнату Socket.IO
        await sio.enter_room(sid, data["room_id"])

        await sio.save_session(
            sid, {"room_id": data["room_id"], "player_name": data["player_name"]}
        )

        # Отправляем уведомление о присоединении игрока
        system_message = {
            "sender": "Система",
            "text": f"Игрок {data['player_name']} присоединился к комнате",
            "timestamp": datetime.now().isoformat(),
        }
        room["messages"].append(system_message)
        print(f"💬 Системное сообщение о присоединении добавлено в историю: {system_message}")
        
        # Отправляем системное сообщение в комнату (теперь пользователь уже в комнате)
        await sio.emit(
            "new_message",
            system_message,
            room=data["room_id"],
        )
        print(f"📤 Системное сообщение о присоединении отправлено в комнату {data['room_id']}")

        await sio.emit("update_players", {"players": room["players"]}, room=data["room_id"])
        await sio.emit("room_joined", {"room": room}, to=sid)

        # 👇 Отправляем историю сообщений новому игроку
        await sio.emit("chat_history", {"messages": room["messages"]}, to=sid)

    except Exception as e:
        await sio.emit(
            "join_error", {"message": f"Ошибка присоединения: {str(e)}"}, to=sid
        )


# Чат
@sio.on("send_message")
async def handle_send_message(sid, data):
    print(f"📨 Получено сообщение от {sid}: {data}")
    
    session = await sio.get_session(sid)
    print(f"📋 Сессия пользователя {sid}: {session}")
    
    if "room_id" not in session:
        print(f"❌ У пользователя {sid} нет room_id в сессии")
        return

    message = {
        "sender": session["player_name"],
        "text": data["text"],
        "timestamp": datetime.now().isoformat(),
    }
    
    print(f"💬 Создано сообщение: {message}")

    # 👇 сохраняем в истории комнаты
    room_id = session["room_id"]
    if room_id in rooms:
        rooms[room_id]["messages"].append(message)
        print(f"💾 Сообщение сохранено в истории комнаты {room_id}")
        print(f"📚 Всего сообщений в комнате: {len(rooms[room_id]['messages'])}")
    else:
        print(f"❌ Комната {room_id} не найдена")

    # Отправляем сообщение в комнату
    await sio.emit(
        "new_message",
        message,
        room=room_id,
    )
    print(f"📤 Сообщение отправлено в комнату {room_id}")

# Обработка выхода из комнаты
@sio.on("leave_room")
async def handle_leave_room(sid, data):
    try:
        room_id = data.get("room_id")
        if room_id and room_id in rooms:
            room = rooms[room_id]
            player = players.get(sid, {})
            player_name = player.get("name", "Неизвестный")
            is_creator = False
            
            # Проверяем, является ли игрок создателем комнаты
            if room["players"] and room["players"][0]["sid"] == sid:
                is_creator = True
            
            # Удаляем игрока из комнаты
            room["players"] = [
                p for p in room["players"] if p["sid"] != sid
            ]
            
            # Если это создатель комнаты, удаляем всю комнату
            if is_creator:
                # Уведомляем всех игроков о том, что лобби удалено
                await sio.emit(
                    "lobby_deleted",
                    {"message": "Создатель лобби покинул комнату. Лобби удалено."},
                    room=room_id,
                )
                
                # Удаляем комнату
                del rooms[room_id]
                
                # Обновляем общий список комнат
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
                # Если это обычный игрок, отправляем уведомление о выходе
                await sio.emit(
                    "new_message",
                    {
                        "sender": "Система",
                        "text": f"Игрок {player_name} покинул комнату",
                        "timestamp": datetime.now().isoformat(),
                    },
                    room=room_id,
                )
                
                # Обновляем список игроков для оставшихся
                await sio.emit(
                    "update_players",
                    {"players": room["players"]},
                    room=room_id,
                )
            
            # Очищаем данные игрока
            if sid in players:
                players[sid]["room_id"] = None
                players[sid]["name"] = None
            
            # Выходим из комнаты Socket.IO
            await sio.leave_room(sid, room_id)
            
    except Exception as e:
        print(f"Ошибка при выходе из комнаты: {e}")

if __name__ == '__main__':
    uvicorn.run(socket_app, host='0.0.0.0', port=8001)