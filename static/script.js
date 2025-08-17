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
        // Инициализируем сообщения из комнаты, если они есть
        store.messages = data.room.messages || [];
        console.log("Создана комната, сообщения:", store.messages);
        
        app.go("lobby");
        // Ждем полной загрузки DOM перед рендерингом чата
        setTimeout(() => {
            console.log("Рендерим чат после создания комнаты");
            renderChat();
        }, 200);
    });

    // ✅ Успешно вошли в комнату → переходим в лобби
    app.on("room_joined", null, (data) => {
        store.currentRoom = data.room;
        // Инициализируем сообщения из комнаты, если они есть
        store.messages = data.room.messages || [];
        console.log("Присоединились к комнате, сообщения:", store.messages);
        
        app.go("lobby");
        // Ждем полной загрузки DOM перед рендерингом чата
        setTimeout(() => {
            console.log("Рендерим чат после присоединения к комнате");
            renderChat();
        }, 200);
    });

    // ✅ Отправка сообщения в чат
    app.addHandler("send_message", () => {
        const text = document.getElementById('message').value.trim();
        if (!text) return;

        console.log("📤 Отправляем сообщение:", text);
        console.log("Текущее состояние:", app.state);
        console.log("Текущая комната:", store.currentRoom);
        
        app.emit("send_message", { text: text });
        document.getElementById('message').value = "";
    });

    // ✅ Пришло сообщение в чат
    app.on("new_message", (data) => {
        console.log("📨 Получено новое сообщение:", data);
        
        // Проверяем структуру сообщения
        if (!data.sender || !data.text) {
            console.error("❌ Некорректная структура сообщения:", data);
            return;
        }
        
        store.messages.push(data);  // 👈 копим
        console.log("📚 Всего сообщений в store:", store.messages.length);
        
        // Проверяем, что мы находимся в лобби
        if (app.state === 'lobby') {
            console.log("Мы в лобби, обновляем чат");
            // Принудительно обновляем чат
            setTimeout(() => {
                renderChat();
            }, 50);
        } else {
            console.log("Мы не в лобби, состояние:", app.state);
        }
    });

    app.on("chat_history", (data) => {
        console.log("📚 Получена история чата:", data);
        store.messages = data.messages || [];
        console.log("📚 Загружено сообщений в store:", store.messages.length);
        renderChat();
    });

    // ✅ Обновление списка игроков в лобби
    app.on("update_players", null, (data) => {
        store.currentRoom.players = data.players;
        // Обновляем только список игроков, не весь экран
        const playersList = document.getElementById('players_list');
        if (playersList) {
            playersList.innerHTML = `
                <strong>Игроки:</strong>
                <ul>
                    ${data.players.map(player => `<li>${player.name}</li>`).join('')}
                </ul>
            `;
        }
        // Перерендериваем чат для отображения новых сообщений
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
    app.on("join_error", null, (data) => {
        alert(data.message);
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
        try {
            const chat = document.getElementById('chat');
            if (!chat) {
                console.log("Chat элемент не найден, возможно пользователь не в лобби");
                return;
            }
            
            console.log("Рендерим чат с сообщениями:", store.messages);
            console.log("Chat элемент найден:", chat);
            
            // Очищаем чат
            chat.innerHTML = '';
            
            if (!store.messages || store.messages.length === 0) {
                chat.innerHTML = '<div class="message" style="color: gray; font-style: italic;">Нет сообщений</div>';
                return;
            }
            
            // Добавляем каждое сообщение
            store.messages.forEach((msg, index) => {
                try {
                    const div = document.createElement('div');
                    div.className = 'message';
                    div.style.marginBottom = '5px';
                    div.style.padding = '5px';
                    div.style.borderBottom = '1px solid #eee';
                    
                    // подсветка системных сообщений
                    if (msg.sender === "Система") {
                        div.style.color = "gray";
                        div.style.fontStyle = "italic";
                        div.style.backgroundColor = "#f5f5f5";
                    }
                    
                    const time = msg.timestamp ? ` [${(new Date(msg.timestamp)).toLocaleTimeString()}]` : '';
                    div.textContent = `${msg.sender}:${time} ${msg.text}`;
                    
                    chat.appendChild(div);
                    console.log(`Добавлено сообщение ${index + 1}:`, msg);
                } catch (error) {
                    console.error(`Ошибка при добавлении сообщения ${index}:`, error, msg);
                }
            });
            
            // Прокручиваем к последнему сообщению
            chat.scrollTop = chat.scrollHeight;
            console.log("Чат обновлен, всего сообщений отображено:", store.messages.length);
        } catch (error) {
            console.error("Ошибка в функции renderChat:", error);
        }
    }

    // ▶️ Первый экран — главное меню
    app.go("standby");

});
