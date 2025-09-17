"""
Посев демо-данных в БД: категории, товары, картинки.

Запуск:
    python -m scripts.seed_demo_data --cats 5 --per-cat 20 --images 2

Параметры:
    --cats <N>        - сколько корневых категорий создать
    --per-cat <M>     - сколько товаров на каждую категорию
    --images <K>      - макс. кол-во изображений на товар (0..K, случайно)
    --currency EUR|RUB|... (по умолчанию: EUR)

Примечания:
- Цены генерируются как Decimal, описания — небольшие тексты.
- Изображения добавляются как заглушки: url = https://picsum.photos/seed/<uuid>/800/600
- Если категории уже есть, можно использовать флаг --use-existing, чтобы накинуть товары в существующие root-категории.
"""
from __future__ import annotations

import argparse
import asyncio
import random
import string
import uuid
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionFactory
from app.db.repository import CategoryRepo, ProductRepo
from app.core.logging_cfg import setup_logging, logger


WORDS = [
    "Pro", "Ultra", "Max", "Mini", "Lite", "Plus", "Air", "Edge", "Prime",
    "Studio", "X", "S", "One", "Go", "Neo", "Note", "Flex", "Core", "Zoom"
]


def random_title(kind: str = "Товар") -> str:
    """Сгенерировать короткое название."""
    base = random.choice(["Alpha", "Omega", "Nova", "Aero", "Pixel", "Quantum", "Nimbus", "Vertex", "Orion", "Atlas"])
    suf = random.choice(WORDS)
    return f"{kind} {base} {suf}"


def random_slug(title: str) -> str:
    """Сгенерировать slug из названия."""
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in title)
    slug = "-".join(filter(None, slug.split("-")))
    # немного случайности, чтобы избежать коллизий
    tail = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{slug}-{tail}"


def random_desc() -> str:
    """Короткое описание."""
    lines = [
        "Высокая производительность и надёжность.",
        "Отличное соотношение цена/качество.",
        "Новая модель с улучшенными характеристиками.",
        "Компактный дизайн и удобство использования.",
        "Поддержка новейших технологий.",
    ]
    random.shuffle(lines)
    return " ".join(lines[: random.randint(2, 4)])


def random_price() -> Decimal:
    """Цена в диапазоне 9.90..1999.90 с шагом 0.10."""
    cents = random.randint(99, 199990)  # в центах/копейках
    return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.10"))


def make_image_urls(max_images: int) -> List[str]:
    """
    Вернуть список из 0..max_images URL-картинок (picsum).
    Порядок важен — будет сохранён в sort_order.
    """
    if max_images <= 0:
        return []
    k = random.randint(0, max_images)
    urls = []
    for _ in range(k):
        seed = uuid.uuid4().hex
        urls.append(f"https://picsum.photos/seed/{seed}/800/600")
    return urls


async def seed_categories(session: AsyncSession, *, count: int) -> List[int]:
    """
    Создать count корневых категорий. Вернёт список их id.
    """
    ids: List[int] = []
    for _ in range(count):
        title = random_title("Категория")
        cat = await CategoryRepo.create(session, title=title, slug=random_slug(title), parent_id=None)
        ids.append(cat.id)
    await session.commit()
    logger.info("Создано категорий: %s", len(ids))
    return ids


async def seed_products_for_category(
    session: AsyncSession,
    *,
    category_id: Optional[int],
    count: int,
    max_images: int,
    currency: str,
) -> int:
    """
    Создать товары для одной категории (или без категории, если category_id=None).
    Возвращает количество созданных.
    """
    created = 0
    for _ in range(count):
        title = random_title("Товар")
        price = random_price()
        desc = random_desc()
        image_urls = make_image_urls(max_images)
        await ProductRepo.create(
            session,
            title=title,
            price=price,
            currency=currency,
            category_id=category_id,
            description=desc,
            is_active=True,
            image_urls=image_urls,
        )
        created += 1
    return created


async def main_async(args) -> None:
    setup_logging()
    logger.info(
        "Запуск посева: cats=%s per_cat=%s images<=%s currency=%s use_existing=%s",
        args.cats, args.per_cat, args.images, args.currency, args.use_existing
    )

    async with AsyncSessionFactory() as session:
        category_ids: List[int] = []

        if args.use_existing:
            # Берём уже существующие корневые категории
            roots = await CategoryRepo.list_root(session)
            category_ids = [c.id for c in roots]
            logger.info("Найдено существующих корневых категорий: %s", len(category_ids))

        if not category_ids:
            category_ids = await seed_categories(session, count=args.cats)

        total_products = 0
        for cid in category_ids:
            created = await seed_products_for_category(
                session,
                category_id=cid,
                count=args.per_cat,
                max_images=args.images,
                currency=args.currency,
            )
            total_products += created
            await session.commit()
            logger.info("Категория %s: создано товаров %s", cid, created)

        logger.info("Готово. Всего категорий: %s, товаров: %s", len(category_ids), total_products)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed demo data for Telegram Shop Bot")
    p.add_argument("--cats", type=int, default=5, help="Сколько создать корневых категорий (если нет существующих)")
    p.add_argument("--per-cat", type=int, default=20, help="Сколько товаров на категорию")
    p.add_argument("--images", type=int, default=2, help="Максимум изображений на товар (0..K)")
    p.add_argument("--currency", type=str, default="EUR", help="Валюта цены")
    p.add_argument("--use-existing", action="store_true", help="Использовать существующие корневые категории")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main_async(parse_args()))
