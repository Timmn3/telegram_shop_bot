"""
Фикстуры для тестов с PostgreSQL.

Особенности:
- Используется реальная тестовая БД PostgreSQL (DATABASE_URL берётся из settings).
- Перед каждым тестом дропается и пересоздаётся схема, чтобы обеспечить чистое состояние.
- Используется AsyncSession через async_sessionmaker.
"""
# --- путь к корню проекта, чтобы работали импорты вида `from app...`
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import asyncio
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from app.core.config import settings
from app.db.models import Base


@pytest.fixture(scope="session")
def event_loop():
    """Глобальный event loop для pytest-asyncio (scope=session)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture  # <-- ВАЖНО: асинхронная фикстура
async def async_session() -> AsyncSession:
    """
    Возвращает новую асинхронную сессию PostgreSQL.
    Перед каждым тестом схема пересоздаётся (drop + create).
    """
    engine = create_async_engine(
        settings.DATABASE_URL,  # должен быть формата postgresql+asyncpg://...
        future=True,
        echo=False,
    )

    # Пересоздаём схему public, чтобы тесты были изолированными
    async with engine.begin() as conn:

        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    async with Session() as session:
        yield session

    await engine.dispose()
