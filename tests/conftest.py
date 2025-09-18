"""
Фикстуры для тестов с PostgreSQL.
Создаёт чистую схему public перед каждым тестом.
"""
# --- путь к корню проекта, чтобы работали импорты вида `from app...`
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.models import Base


@pytest_asyncio.fixture
async def async_session() -> AsyncSession:
    """
    Новая асинхронная сессия БД для каждого теста.
    - Пересоздаёт схему public (DROP/CREATE).
    - Создаёт таблицы через Base.metadata.create_all.
    """
    engine = create_async_engine(
        settings.TEST_DATABASE_URL,   # postgresql+asyncpg://...
        future=True,
        echo=False,
        poolclass=NullPool,           # не держим соединения между тестами
    )

    # Чистая схема перед тестом
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    async with Session() as session:
        yield session

    await engine.dispose()
