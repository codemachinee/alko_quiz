from datetime import datetime
from fastapi import HTTPException
from typing import Optional, Dict, List

import socketio
from loguru import logger

from pydantic import BaseModel, field_validator

import uvicorn
from fastapi import FastAPI

from src.all_riddles import riddles

# Заставляем работать пути к статике
static_files = {'/': 'static/index.html', '/static': './static'}
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")
app = FastAPI()
socket_app = socketio.ASGIApp(sio, app, static_files)

# настройки логирования
logger.remove()
# Базовый лог
logger.debug("Это сообщение уровня DEBUG")
logger.info("Это информационное сообщение")
logger.warning("Предупреждение")
logger.error("Ошибка")
logger.critical("Критическая ошибка")

logger.add(
    "loggs.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    rotation="5 MB",  # Ротация файла каждые 10 MB
    retention="10 days",  # Хранить только 5 последних логов
    compression="zip",  # Сжимать старые логи в архив
    backtrace=True,     # Сохранение трассировки ошибок
    diagnose=True       # Подробный вывод
)


class Riddle(BaseModel):
    number: Optional[int] = None
    text: Optional[str] = None
    answer: Optional[str] = None

    # Валидация поля 'answers' с помощью field_validator
    @field_validator("answer", mode='before')
    def normalize_answers(v):
        if not v:
            return ""
        elif isinstance(v, list):
            return " ".join(str(item) for item in v)
        # Нормализуем все ответы: приводим к нижнему регистру и убираем лишние пробелы
        return v.strip().lower()


class Player(BaseModel):
    sid: str
    number_of_riddle: int
    score: int


# Глобальное хранилище комнат (в реальном проекте используйте БД)
rooms: Dict[str, Dict] = {}


class Room(BaseModel):
    id: str
    name: str
    questions_count: int
    context: str
    players: List[str]
    max_players: int = 4


# Новые обработчики
@sio.on("create_room")
async def create_room(sid, data):
    room_id = f"room_{len(rooms) + 1}"
    room = Room(
        id=room_id,
        name=data["name"],
        questions_count=data["questions_count"],
        context=data["context"],
        players=[sid],
    )
    rooms[room_id] = room.dict()
    await sio.save_session(sid, {"room_id": room_id, "player_name": data.get('player_name')})
    await sio.emit("room_created", {"room": room.dict()}, to=sid)


@sio.on("get_rooms")
async def get_rooms(sid):
    await sio.emit("rooms_list", {"rooms": list(rooms.values())}, to=sid)


@sio.on("join_room")
async def join_room(sid, data):
    room_id = data["room_id"]
    if room_id not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    room = rooms[room_id]
    if len(room["players"]) >= room["max_players"]:
        raise HTTPException(status_code=400, detail="Room is full")

    room["players"].append(sid)
    await sio.save_session(sid, {"room_id": room_id, "player_name": data.get('player_name')})
    await sio.emit("room_joined", {"room": room}, to=sid)
    await sio.emit("player_joined", {"player_id": sid}, room=room_id)


@sio.on("send_message")
async def send_message(sid, data):
    session = await sio.get_session(sid)
    room_id = session.get("room_id")
    if not room_id:
        return

    message = {
        "sender": sid[:6],  # Короткий ID для отображения
        "text": data["text"],
        "timestamp": datetime.now().isoformat(),
    }
    await sio.emit('message_received', {'message': message}, room=room_id)


# Обрабатываем подключение пользователя
@sio.event
async def connect(sid, environ):
    player = Player(sid=sid, number_of_riddle=0, score=0)
    await sio.save_session(sid=sid, session={'number_of_riddle': player.number_of_riddle,
                                             'score': player.score})
    logger.info(f"Пользователь {sid} подключился")


# Обрабатываем запрос очередного вопроса
@sio.on('next')
async def next_event(sid, data):
    try:
        session = await sio.get_session(sid)
        session['number_of_riddle'] = session.get('number_of_riddle') + 1
        player = Player(sid=sid, number_of_riddle=session.get('number_of_riddle'), score=session.get('score'))
        if player.number_of_riddle > len(riddles):
            await sio.save_session(sid, session={'number_of_riddle': 0, 'score': 0})
            await sio.emit('over', data={'content': 'игра завершена'}, to=sid)
            return
        else:
            riddle = Riddle(text=riddles[player.number_of_riddle - 1]["text"])
            await sio.emit('riddle', data={"text": f"{riddle.text}"}, to=sid)
            await sio.save_session(sid, session=session)
    except Exception as e:
        logger.error("Ошибка в next_event:", f'{e}')


# Обрабатываем отправку ответа
@sio.on('answer')
async def receive_answer(sid, data):
    session = await sio.get_session(sid)
    player = Player(sid=sid, number_of_riddle=session.get('number_of_riddle'), score=session.get('score'))
    riddle = Riddle(answer=data["text"])
    if riddle.answer in riddles[player.number_of_riddle - 1]["answer"]:
        session['score'] = player.score + 1
        await sio.save_session(sid, session)
        await sio.emit("result", data={"riddle": riddles[player.number_of_riddle - 1]["text"],
                                       "is_correct": True,
                                       "answer": riddles[player.number_of_riddle - 1]["answer"][0]},
                       to=sid)
        await sio.emit("score", data={"value": session["score"]}, to=sid)
    else:
        await sio.emit("result", data={"riddle": riddles[player.number_of_riddle - 1]["text"],
                                       "is_correct": False,
                                       "answer": riddles[player.number_of_riddle - 1]["answer"][0]},
                       to=sid)
        await sio.emit("score", data={"value": session["score"]}, to=sid)


# Обрабатываем отключение пользователя
@sio.event
async def disconnect(sid):
    logger.info(f"Пользователь {sid} отключился")


if __name__ == '__main__':
    uvicorn.run(socket_app, host='0.0.0.0', port=8001)
