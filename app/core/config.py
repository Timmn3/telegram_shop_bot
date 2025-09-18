"""
  Загружает переменные окружения из .env.
  Предоставляет доступ к настройкам (токен бота, БД, Redis, список админов).
  Предоставляет типизированные свойства, удобные для кода (ADMIN_ID_LIST).
"""
from __future__ import annotations

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import BASE_DIR


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из окружения / .env."""
    BOT_TOKEN: str = Field(..., description="Токен Telegram-бота")
    DATABASE_URL: str = Field(..., description="URL подключения к БД (postgresql+asyncpg)")
    TEST_DATABASE_URL: str = Field(..., description="URL подключения к тестовой БД (postgresql+asyncpg)")
    ADMIN_IDS: str = Field("", description="Список Telegram ID админов через запятую")
    REDIS_URL: str | None = Field(default=None, description="URL Redis для FSM (опционально)")
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования: DEBUG/INFO/WARNING/ERROR")
    LOG_FILE_NAME: str = Field(default="bot.log", description="Имя файла логов в папке logs/")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def ADMIN_ID_LIST(self) -> List[int]:
        """Возвращает список ID админов как целых чисел."""
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip().isdigit()]


settings = Settings()
