"""
Сервис каталога.

Задачи:
- Чтение дерева категорий (корневые/дети).
- Список товаров по категории (с пагинацией).
- Получение карточки товара.

"""
from __future__ import annotations

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Category, Product
from app.db.repository import CategoryRepo, ProductRepo


async def list_root_categories(session: AsyncSession) -> List[Category]:
    """Вернуть список корневых категорий (parent_id IS NULL)."""
    return await CategoryRepo.list_root(session)


async def list_child_categories(session: AsyncSession, parent_id: int) -> List[Category]:
    """Вернуть список подкатегорий по parent_id."""
    return await CategoryRepo.list_children(session, parent_id=parent_id)


async def list_products(
    session: AsyncSession,
    *,
    category_id: int | None,
    limit: int = 20,
    offset: int = 0,
) -> List[Product]:
    """
    Вернуть список активных товаров, опционально отфильтрованных по категории.

    :param category_id: id категории или None для всех
    :param limit: размер страницы
    :param offset: смещение
    """
    return await ProductRepo.list_by_category(session, category_id=category_id, limit=limit, offset=offset)


async def get_product(session: AsyncSession, product_id: int) -> Optional[Product]:
    """Вернуть товар по id (или None)."""
    return await ProductRepo.get(session, product_id)
