var store = {
    rooms: [],
    currentRoom: null,
    playerName: "",
    messages: [],
    roomData: null,
    joiningRoomId: null
};

app_pages = {
    standby: {},
    create_lobby: {},
    enter_name: {},
    choose_lobby: {},
    join_name: {},
    lobby: {},
    showriddle: {},
    showresult: {},
    disconnected: {}
};

document.addEventListener('DOMContentLoaded', function () {

    app = new Lariska({
        store: store,
        container: "#app",
        pages: app_pages,
        url: window.location.hostname + ":8001"
    });

    // ▶️ Кнопка "Создать игру"
    app.addHandler("start_game", () => {
        app.go("create_lobby");
    });

    // ▶️ Кнопка "Присоединиться к игре"
    app.addHandler("choice_game", () => {
        app.go("choose_lobby");
        app.emit("get_rooms");
    });

    // 🔙 Кнопка "Назад"
    app.addHandler("back", () => app.go("standby"));

    // ✅ Обработка кнопки "Создать"
    app.addHandler("create_room", () => {
        const name = document.getElementById('room_name').value.trim();
        const count = document.getElementById('questions_count').value.trim();
        const context = document.getElementById('questions_context').value.trim();
        const playerName = document.getElementById('creator_name').value.trim();

        if (!name || !count || !playerName) {
            alert("Пожалуйста, заполните все обязательные поля.");
            return;
        }

        const roomData = {
            name: name,
            questions_count: parseInt(count),
            context: context,
            player_name: playerName
        };

        store.playerName = playerName;
        store.roomData = roomData;

        app.emit("create_room", roomData);
    });

    // ✅ Пришёл список комнат
    app.on("rooms_list", null, (data) => {
        console.log("📥 Получен список комнат:", data.rooms);
        store.rooms = data.rooms;
        const renderRooms = () => {
        const list = document.getElementById('rooms_list');
        if (!list) {
            return;
        }

        console.log("✅ Найден элемент #rooms_list, начинаем отрисовку");
        list.innerHTML = '';

        if (data.rooms.length === 0) {
        list.innerHTML = "<p>Нет доступных комнат</p>";
        return;
        }

        data.rooms.forEach(function(room) {
            const div = document.createElement('div');
            div.className = 'room-item';
            div.textContent = `${room.name} (${room.players.length} игроков)`;

            div.addEventListener('click', function () {
                store.joiningRoomId = room.id;
                app.go("join_name");
            });

            list.appendChild(div);
        });
    };

    renderRooms();
});

    // ✅ Ввод имени при входе в комнату
    app.addHandler("join_room", () => {
        const nameInput = document.getElementById('joiner_name');
        const playerName = nameInput.value.trim();
        if (!playerName) {
            alert("Пожалуйста, введите ваше имя");
            return;
        }

        store.playerName = playerName;

        app.emit("join_room", {
            room_id: store.joiningRoomId,
            player_name: playerName
        });
    });

    // ✅ Комната успешно создана → переходим в лобби
    app.on("room_created", null, (data) => {
        store.currentRoom = data.room;
        store.messages = [];  // новый чат
        app.go("lobby");
        renderChat(); // чат сразу отрисуем
    });

    // ✅ Успешно вошли в комнату → переходим в лобби
    app.on("room_joined", null, (data) => {
        store.currentRoom = data.room;
        app.go("lobby");
        setTimeout(renderChat, 50);
    });

    // ✅ Отправка сообщения в чат
    app.addHandler("send_message", () => {
        const text = document.getElementById('message').value.trim();
        if (!text) return;

        app.emit("send_message", { text: text });
        document.getElementById('message').value = "";
    });

    // ✅ Пришло сообщение в чат
    app.on("new_message", (data) => {
        store.messages.push(data);  // 👈 копим
        renderChat();
    });

    app.on("chat_history", (data) => {
        store.messages = data.messages || [];
        renderChat();
    });

    // ✅ Обновление списка игроков в лобби
    app.on("update_players", null, (data) => {
        store.currentRoom.players = data.players;
        app.render("#lobby");
        renderChat();
    });

    // ✅ Уведомление о том, что лобби удалено
    app.on("lobby_deleted", null, (data) => {
        alert("Лобби было удалено создателем. Возвращаемся в главное меню.");
        store.currentRoom = null;
        store.roomData = null;
        store.playerName = "";
        app.go("standby");
    });

    // ✅ Обработчик для кнопки "Покинуть комнату"
    app.addHandler("leave_room", () => {
        if (store.currentRoom) {
            app.emit("leave_room", { room_id: store.currentRoom.id });
            store.currentRoom = null;
            store.roomData = null;
            store.playerName = "";
        }
        app.go("standby");
    });

    // ✅ Обработчик события "join_error"
    app.on("join_error", (data) => {
        alert(data['message']);
        store.currentRoom = null;
        store.roomData = null;
        store.playerName = "";
        app.go("standby");
    });

    // 🔹 Остальные игровые события пока не трогаем
    app.on("riddle", "#showriddle", null, (data) => {
        console.log("Получена загадка", data);
        app.store.riddle = data;
    });

    app.on("result", "#showanswer", null, (data) => {
        console.log("Результат", data);
        app.store.riddle = data;
    });

    app.on("score", null, (data) => {
        console.log("Счёт обновлён", data);
        app.store.score = data.value;
    });

    app.on("over", "#over", null, (data) => {
        console.log("Игра завершена", data);
    });

    function renderChat() {
        const chat = document.getElementById('chat');
        if (!chat) {
            // Chat элемент ещё не в DOM (пользователь не на лобби) — не ломаем ничего
            // Сообщения остаются в store.messages и отрисуются при заходе в лобби
            return;
        }
        chat.innerHTML = '';
        store.messages.forEach(msg => {
            const div = document.createElement('div');
            div.className = 'message';
            // подсветка системных сообщений
            if (msg.sender === "Система") {
                div.style.color = "gray";
                div.style.fontStyle = "italic";
            }
            const time = msg.timestamp ? ` [${(new Date(msg.timestamp)).toLocaleTimeString()}]` : '';
            div.textContent = `${msg.sender}:${time} ${msg.text}`;
            chat.appendChild(div);
        });
        chat.scrollTop = chat.scrollHeight;
    }

    // ▶️ Первый экран — главное меню
    app.go("standby");

});
