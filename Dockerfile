# Используем образ с uv для сборщика
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости в рабочую директорию
COPY pyproject.toml uv.lock ./

# синхронизируем зависимости, удаляем лишнее
RUN uv sync && \
    rm -rf /root/.cache && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Копируем остальные файлы проекта в рабочую директорию
COPY . .

# Запускаем бота
CMD ["uv","run","python", "main.py"]