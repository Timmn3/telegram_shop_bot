from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.core.config import settings

"""
Конфигурация асинхронного подключения к базе данных с использованием SQLAlchemy Async.

Содержит:
- engine: асинхронный движок для работы с базой.
- AsyncSessionFactory: фабрика сессий.
- get_session: утилита для получения новой сессии.
"""

# Создание асинхронного движка
# poolclass=NullPool — без пулов
engine = create_async_engine(
    settings.DATABASE_URL,
    future=True,
    echo=False,  # True для отладки SQL-запросов
    poolclass=NullPool,
)

# Фабрика асинхронных сессий
AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


def get_session() -> AsyncSession:
    """
    Возвращает новую асинхронную сессию (AsyncSession).

    Пример использования в зависимостях FastAPI:

        async with get_session() as session:
            ...
    """
    return AsyncSessionFactory()
