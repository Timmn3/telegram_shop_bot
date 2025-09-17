# tg_shop_bot — Project skeleton

Это минимальный скелет проекта Telegram E-COMMERCE бота.

Структура:
- app/ : исходники бота (handlers, services, db, core)
- migrations/ : alembic миграции (пустая)
- tests/ : заглушки для тестов
- docker-compose.yml, Dockerfile, .env.example, requirements.txt

Инструкция:
1. Скопируйте `.env.example` в `.env` и заполните значения.
2. Запустите контейнеры через docker-compose или установите зависимости и запустите локально.
3. Запустите бота: `python -m app.bot.main` (пример).

Дальше: после ваших проверок пришлю модули по очереди (models, repos, services, handlers...).
