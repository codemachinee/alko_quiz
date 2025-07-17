from typing import Optional

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
        logger.error(f"Ошибка в next_event:", f'{e}')


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
