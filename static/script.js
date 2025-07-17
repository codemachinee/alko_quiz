var store = {
    riddle: null,
    score: 0,
    rooms: [],
    currentRoom: null,
    messages: [],
    playerName: "" // Добавляем хранилище для имени
};

app_pages = {
    standby: {},
    showriddle: {},
    showresult: {},
    disconnected: {}
}

document.addEventListener('DOMContentLoaded', function () {

    app = new Lariska({
        store: store,
        container: "#app",
        pages: app_pages,
        url: window.location.host
    });

    // Обработчик для создания игры
    app.addHandler("start_game", () => {
        app.go("create_lobby");

        // Валидация полей формы
        const inputs = document.querySelectorAll('#create_lobby input');
        inputs.forEach(input => {
            input.addEventListener('input', () => {
                const allFilled = Array.from(inputs).every(i => i.value.trim() !== '');
                document.getElementById('create_btn').disabled = !allFilled;
            });
        });
    });

    // Обработчик для выбора игры
    app.addHandler("choice_game", () => {
        app.go("choose_lobby");
        app.emit("get_rooms");
    });

    // Новый обработчик для установки имени
    app.addHandler("set_name", () => {
        const nameInput = document.getElementById('player_name');
        if (nameInput.value.trim() === "") {
            alert("Пожалуйста, введите имя");
            return;
        }

        store.playerName = nameInput.value.trim();

        // Если мы создавали комнату
        if (store.creatingRoom) {
            app.emit("create_room", store.roomData);
        }
        // Если присоединялись к существующей
        else if (store.joiningRoomId) {
            app.emit("join_room", { room_id: store.joiningRoomId });
        }
    });

    // Модифицируем обработчик создания комнаты
    app.addHandler("create_room", () => {
        store.roomData = {
            name: document.getElementById('room_name').value,
            questions_count: document.getElementById('questions_count').value,
            context: document.getElementById('questions_context').value
        };
        store.creatingRoom = true;
        app.go("enter_name"); // Переходим к вводу имени
    });

    // Модифицируем обработчик выбора комнаты
    app.on("rooms_list", "#choose_lobby", (data) => {
        store.rooms = data.rooms;
        const roomsList = document.getElementById('rooms_list');
        roomsList.innerHTML = '';

        data.rooms.forEach(room => {
            const roomElement = document.createElement('div');
            roomElement.className = 'room-item';
            roomElement.textContent = `${room.name} (${room.players.length}/${room.max_players})`;
            roomElement.onclick = () => {
                store.joiningRoomId = room.id;
                store.creatingRoom = false;
                app.go("enter_name"); // Переходим к вводу имени
            };
            roomsList.appendChild(roomElement);
        });
    });


    app.addHandler("next", () => {
        app.emit("next")
    })

    app.addHandler("answer", () => {
        user_answer = document.querySelector("textarea#answer").value
        app.emit("answer", {text: user_answer})
    })

    // Получена загадка с сервера
    app.on("riddle", "#showriddle", (data) => {
        console.log(data)
        app.store.riddle = data
    })

    // Получен ответ с сервера
    app.on("result", "#showanswer", (data) => {
        console.log(data)
        app.store.riddle = data
    })

    // Получен сигнал "обновлен счет" с сервера
    app.on("score", null, (data) => {
        console.log(data)
        app.store.score = data.value
    })

    // Получен сигнал "Игра завершена"
    app.on("over", "#over", (data) => {
        console.log(data)
    })

    app.go("standby");
})
