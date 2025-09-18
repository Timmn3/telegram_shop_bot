from __future__ import annotations
"""
Создание async-движка и фабрики сессий.

Подсказки:
- Включить подробные SQL-трассировки можно, установив echo=True ниже
  (или подняв уровень 'sqlalchemy.engine' в setup_logging()).
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.logging_cfg import logger

# Создание асинхронного движка
engine = create_async_engine(
    settings.DATABASE_URL,
    future=True,
    echo=False,           # True для отладки SQL-запросов
    poolclass=NullPool,   # без пула, прозрачно для тестов/скриптов
)
logger.info("DB engine created (echo=%s, pool=%s)", False, "NullPool")

# Фабрика асинхронных сессий
AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)
logger.debug("AsyncSessionFactory initialized (expire_on_commit=%s)", False)


def get_session() -> AsyncSession:
    """
    Вернуть новую асинхронную сессию (AsyncSession).

    Пример:

        async with get_session() as session:
            ...
    """
    logger.debug("get_session() called")
    return AsyncSessionFactory()
