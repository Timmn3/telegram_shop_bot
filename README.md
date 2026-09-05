# Telegram Shop Bot - E-commerce Telegram Bot (Aiogram 3, PostgreSQL, Redis)

> Полнофункциональный бот интернет-магазина для Telegram с цепочкой **каталог → корзина → заказ** и **админ-панелью**. Поддержаны многофото в карточке товара, back-навигация в checkout FSM, список заказов и смена статуса для админов, тесты (5+).

---

## Возможности

- **Каталог**
  - Дерево категорий: корневые и дочерние категории, переходы по inline-кнопкам.  
  - Списки товаров с пагинацией (восстановление страницы при возврате).
  - Карточка товара: **альбом из нескольких фото** (media group) с подписью на первом снимке.
- **Корзина**
  - Добавить / увеличить / уменьшить / удалить позицию, очистить корзину.
  - Подсчёт суммы корзины (Decimal).
- **Оформление заказа (FSM)**
  - Шаги: **имя → телефон → адрес → доставка → подтверждение**.
  - Кнопка **«Назад»** на каждом шаге, данные сохраняются при возврате.
  - Создание заказа, уникальный номер `ORDER-YYYYMMDD-<id>`, уведомления админам.
- **Админ-панель**
  - `/admin` меню (добавить/редактировать товары, заказы).
  - Добавление товара через FSM, **несколько фото** с завершением по слову «готово».
  - **Редактирование товара**: изменение названия, цены, категории, описания и фото.
  - Список заказов с пагинацией и **сменой статуса**.
- **Тесты**
  - 5+ юнит-тестов: корзина, создание заказа, генерация номера, удаление позиции, смена статуса, пустая корзина.
- **Инфраструктура**
  - Python 3.12 + **Aiogram 3**, PostgreSQL (**SQLAlchemy + Alembic**), **Redis** для FSM, Docker + docker-compose, логирование в файл и консоль.

> Реализация опирается на текущие файлы проекта: точка входа бота `app/bot/main.py`, роутеры `app/bot/handlers/*`, клавиатуры `app/bot/keyboards/*`, конфиг `app/core/config.py`, модели `app/db/models.py`, слои сервисов/репозиториев и пр. См. дерево проекта ниже.

---

## Технологии и архитектура

- **Язык/библиотеки:** Python 3.12, [Aiogram 3.x](https://docs.aiogram.dev/), SQLAlchemy (async), Alembic, Redis (FSM).
- **Слои/разделение:**
  - `app/core`: конфиг, логирование, пути.
  - `app/db`: модели (`models.py`), репозитории (`repository.py`), сессия (`session.py`).
  - `app/services`: бизнес-логика (`cart_service.py`, `catalog_service.py`, `order_service.py`).
  - `app/bot`: обработчики (`handlers/*`), клавиатуры (`keyboards/*`), middleware.
  - `tests`: pytest-asyncio, конфтест с изоляцией схемы БД.
- **Хранилища:** PostgreSQL (данные), Redis (FSM), файловое логирование с ротацией (папка `logs/`).

### Структура репозитория (основное)

```
app/
  bot/
    handlers/
      admin.py          # админ-меню, добавление товара (несколько фото), заказы/статусы
      cart.py           # корзина: add/inc/dec/del/clear, checkout:start
      catalog.py        # категории/товары, карточка с альбомами фото
      checkout.py       # FSM: имя→телефон→адрес→доставка→подтверждение (+ back)
      common.py         # /start (создание User), /menu, noop
      __init__.py
    keyboards/
      admin_keyboard.py
      cart_keyboard.py
      checkout_keyboard.py
      inline_catalog.py
      __init__.py
    main.py             # инициализация логов, Bot/Dispatcher, storage, регистрация роутеров, polling
    middlewares.py      # логирование необработанных исключений
  core/
    config.py           # Settings (env), ADMIN_ID_LIST, LOG_LEVEL, LOG_FILE_NAME
    logging_cfg.py      # консоль+файл (RotatingFileHandler), настройка уровней
    paths.py            # BASE_DIR, LOG_DIR
  db/
    models.py           # SQLAlchemy модели и enum-ы
    repository.py       # слой репозиториев (User/Category/Product/Cart/Order)
    session.py          # движок и async_sessionmaker
  services/
    cart_service.py     # операции с корзиной (add, set_quantity, list, subtotal, ...)
    catalog_service.py  # категории, товары, карточка
    order_service.py    # создать заказ из корзины, статусы
  __init__.py
scripts/
  init_db.py            # простой create_all для локальной отладки
tests/
  conftest.py           # reset схемы public перед каждым тестом
  test_*.py
alembic.ini             # заготовка; подключите env.py к DATABASE_URL
docker-compose.yml      # postgres:15 + redis:7
Dockerfile              # билд приложения
.env.example            # пример env (создайте свой .env)
README.md               # этот файл
```

---

## ⚙ Установка и запуск

### 1) Подготовка окружения

Требуется: **Python 3.12**, Docker + docker-compose.

Склонировать репозиторий и создать виртуальное окружение:

```bash
git clone https://github.com/Timmn3/telegram-shop-bot
cd telegram-shop-bot

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 2) Настроить переменные окружения

Создайте `.env` в корне (рядом с `alembic.ini`) на основе примера. **Не коммитьте реальные токены/пароли.**

`.env` (пример):

```env
# Telegram
BOT_TOKEN=123456:REPLACE_ME

# БД (asyncpg)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/tg_shop

# Админы (через запятую)
ADMIN_IDS=111111111,222222222

# Redis для FSM (опционально)
REDIS_URL=redis://localhost:6379/0

# Логи
LOG_LEVEL=INFO
LOG_FILE_NAME=bot.log
```

### 3) Поднять инфраструктуру БД/Redis

В репозитории есть `docker-compose.yml`, который поднимает **PostgreSQL 15** и **Redis 7** (без приложения):

```bash
docker compose up -d  # поднимет db:5432 и redis:6379
```

> При необходимости измените логин/пароль/имя БД в `docker-compose.yml` и синхронизируйте `DATABASE_URL` в `.env`.

### 4) Инициализация схемы БД

**Вариант A (Alembic - рекомендовано):**

1. Настройте `alembic/env.py` так, чтобы он читал `DATABASE_URL` из `.env`/`app.core.config.settings`. Пример фрагмента `env.py`:

```python
# env.py (фрагмент)
from app.core.config import settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
```
2. Сгенерируйте/примените миграции:
```bash
alembic revision --autogenerate -m "init schema"
alembic upgrade head
```

**Вариант B (упрощённо для локальной отладки):**

```bash
python scripts/init_db.py  # создаст таблицы через Base.metadata.create_all
```

> В продакшене используйте Alembic-миграции.

### 5) Запуск бота (локально)

```bash
python -m app.bot.main
```

Бот запускается с HTML parse_mode по умолчанию и логирует в консоль + `logs/bot.log`.

### 6) Запуск бота в Docker

В репозитории есть `Dockerfile` для сборки приложения. Можно запустить так:

```bash
docker build -t tg-shop-bot:latest .
# App должен видеть БД/Redis (из compose). Передадим .env в контейнер:
docker run --rm --env-file .env --network host tg-shop-bot:latest
```

> Или добавьте в `docker-compose.yml` сервис `app`, зависящий от `db` и `redis`.

Пример блока для `docker-compose.yml`:

```yaml
  app:
    build: .
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - DATABASE_URL=${DATABASE_URL}
      - ADMIN_IDS=${ADMIN_IDS}
      - REDIS_URL=${REDIS_URL}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - LOG_FILE_NAME=${LOG_FILE_NAME:-bot.log}
    depends_on:
      - db
      - redis
```

---

## Пользовательские сценарии и команды

- `/start` - приветствие, **идемпотентное** создание `User` в БД, подсказки по навигации.
- `/menu` - показать корневые категории.
- `/cart` - открыть корзину.

**Inline-навигация:**
- Каталог → Категории → Список товаров (пагинация).
- Карточка товара: кнопки **«В корзину»** и **«Назад к товарам»** (возвращает на **ту же страницу** списка).
- Корзина: `➖ qty ➕`, `🗑 Удалить`, `🧹 Очистить`, `🛍 Оформить`.

**Checkout FSM:** имя → телефон → адрес → доставка → подтверждение (везде есть «⬅️ Назад», кроме первого шага - там «Отмена»).

**Админ:**
- `/admin` - главное меню («➕ Добавить товар», «✏️ Редактировать товар», «📦 Заказы»).
- **Добавление товара (FSM):
  На шаге *photos* можно прислать несколько изображений. Завершение - словом **«готово»** (или `-`, чтобы пропустить).  
- **Редактирование товара (FSM):** выбор ID → меню полей → изменение *title/price/category/description/photos*.  
  Фото можно заменить целиком: прислать новые и подтвердить **«готово»**.  
- **Заказы:** список с пагинацией, смена статуса.


---

## Протокол колбэков (Callback Data)

> Используются `aiogram.filters.callback_data.CallbackData` и «сырые» callback-строки.

- Каталог:
  - `cat:<cat_id>` - открыть категорию.
  - `plist:<cat_id>:<page>:<page_size>` - показать страницу товаров.
  - `prodo:<product_id>:<cat_id>:<page>:<page_size>` - открыть карточку с контекстом возврата.
  - `prod:<product_id>` - устаревший путь (без контекста).
- Корзина:
  - `cart:add:<product_id>`, `cart:inc:<product_id>`, `cart:dec:<product_id>`, `cart:del:<product_id>`
  - `cart:clear`, `cart:view`, `cart:back_to_menu`
- Checkout:
  - `checkout:start`, `checkout:back`, `checkout:cancel`, `checkout:confirm`
  - `delivery:courier|pickup|post`
- Админ:
  - `admin:cmd:add`, `admin:cmd:orders`
  - `admin:orders:page:<page>:<size>`
  - `admin:order:status:<order_id>:<status>`

---

## FSM-потоки (Mermaid)

### Checkout FSM

```mermaid
flowchart LR
    A[checkout:start] --> B[Имя]
    B -- ok --> C[Телефон]
    C -- ok --> D[Адрес]
    D -- ok --> E[Доставка]
    E -- выбрано --> F[Подтверждение]
    F -- confirm --> G[Создание заказа + уведомление]
    B -- back --> cancel[Отмена]
    C -- back --> B
    D -- back --> C
    E -- back --> D
    F -- back --> E
```

### Добавление товара (админ)

```mermaid
flowchart LR
    T[Title] --> P[Price] --> C[Category ID] --> D[Description]
    D --> PH{Photos loop}
    PH -- фото --> PH
    PH -- "готово" / "-" --> A[Active yes/no] --> CF[Confirm]
    CF -- yes --> CREATE[Создать Product + ProductImage*]
    CF -- no --> CANCEL[Отмена]
```

---

## Схема БД (ER-диаграмма)

Основные сущности: `User`, `Category` (дерево), `Product`, `ProductImage (sort_order)`, `Cart`/`CartItem`, `Order`/`OrderItem`, enum-ы `OrderStatus`, `CartStatus`.

```mermaid
erDiagram
    USER ||--o{ CART : has
    USER ||--o{ ORDER : places

    CATEGORY ||--o{ CATEGORY : parent_of
    CATEGORY ||--o{ PRODUCT : groups

    PRODUCT ||--o{ PRODUCT_IMAGE : has
    CART ||--o{ CART_ITEM : contains
    ORDER ||--o{ ORDER_ITEM : contains

    USER {
        BIGINT id PK
        STRING full_name
        STRING phone
        DATETIME created_at
    }

    CATEGORY {
        INT id PK
        STRING title
        STRING slug UNIQUE
        INT parent_id FK
    }

    PRODUCT {
        INT id PK
        STRING title
        TEXT description
        NUMERIC price
        STRING currency
        INT category_id FK
        BOOL is_active
        DATETIME created_at
        DATETIME updated_at
    }

    PRODUCT_IMAGE {
        INT id PK
        INT product_id FK
        TEXT url
        STRING telegram_file_id
        INT sort_order UNIQUE(product_id,sort_order)
    }

    CART {
        INT id PK
        BIGINT user_id FK
        ENUM status
        DATETIME created_at
        DATETIME updated_at
    }

    CART_ITEM {
        INT id PK
        INT cart_id FK
        INT product_id FK
        INT quantity
        NUMERIC price_at_added
        UNIQUE cart_id, product_id
    }

    ORDER {
        INT id PK
        STRING order_number UNIQUE
        BIGINT user_id FK
        ENUM status
        NUMERIC total_amount
        STRING currency
        STRING contact_name
        STRING contact_phone
        TEXT address
        STRING delivery_type
        DATETIME created_at
        DATETIME updated_at
    }

    ORDER_ITEM {
        INT id PK
        INT order_id FK
        INT product_id FK
        INT quantity
        NUMERIC item_price
    }
```

---

## Тестирование

- Команда:
  ```bash
  pytest -q
  ```
- `tests/conftest.py` пересоздаёт схему **public** перед каждым тестом (drop + create), используя `DATABASE_URL`. Убедитесь, что это **тестовая** БД.
- Покрытие включает:
  - Корзина: добавление и сумма, **удаление позиции**.
  - Заказ: создание из корзины, **пустая корзина → ValueError**, генерация номера, смена статуса админом.

---


## Логирование

- Консоль + файл `logs/<LOG_FILE_NAME>` с ротацией (5×5 МБ).
- Уровень управляется `LOG_LEVEL` (DEBUG/INFO/WARNING/ERROR).

---


## Лицензия

MIT