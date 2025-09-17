"""
Repository layer (доступ к БД и транзакции) для tg_shop_bot.

Покрывает:
- Категории и товары (чтение/CRUD).
- Корзину (создание/получение активной, позиции, подсчёт суммы).
- Заказ (создание из корзины) с генерацией order_number.

Примечания:
- Все операции рассчитаны на использование с AsyncSession.
- Денежные суммы считаются через Decimal.
- Генерация номера заказа: ORDER-YYYYMMDD-<SEQ:id>

"""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Iterable, List, Optional

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import (
    Base,
    User,
    Category,
    Product,
    ProductImage,
    Cart,
    CartItem,
    Order,
    OrderItem,
    CartStatus,
    OrderStatus,
)


# -------- Category --------
class CategoryRepo:
    """Репозиторий категорий товаров."""

    @staticmethod
    async def list_root(session: AsyncSession) -> List[Category]:
        """Список корневых категорий (parent_id IS NULL)."""
        stmt = select(Category).where(Category.parent_id.is_(None)).order_by(Category.title.asc())
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def list_children(session: AsyncSession, parent_id: int) -> List[Category]:
        """Список подкатегорий по parent_id."""
        stmt = select(Category).where(Category.parent_id == parent_id).order_by(Category.title.asc())
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get(session: AsyncSession, category_id: int) -> Optional[Category]:
        """Получить категорию по id."""
        result = await session.execute(select(Category).where(Category.id == category_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(session: AsyncSession, *, title: str, slug: str | None = None,
                     parent_id: int | None = None) -> Category:
        """Создать категорию."""
        obj = Category(title=title, slug=slug, parent_id=parent_id)
        session.add(obj)
        await session.flush()
        return obj

    @staticmethod
    async def update(session: AsyncSession, category_id: int, **fields) -> Optional[Category]:
        """Обновить категорию по id, вернуть обновлённый объект или None."""
        await session.execute(update(Category).where(Category.id == category_id).values(**fields))
        await session.flush()
        return await CategoryRepo.get(session, category_id)

    @staticmethod
    async def delete(session: AsyncSession, category_id: int) -> None:
        """Удалить категорию по id."""
        await session.execute(delete(Category).where(Category.id == category_id))
        await session.flush()


# -------- Product --------
class ProductRepo:
    """Репозиторий товаров."""

    @staticmethod
    async def get(session: AsyncSession, product_id: int) -> Optional[Product]:
        """Получить товар по id (с изображениями)."""
        stmt = (
            select(Product)
            .where(Product.id == product_id)
            .options(joinedload(Product.images))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_category(session: AsyncSession, *, category_id: int | None, limit: int = 20, offset: int = 0) -> \
    List[Product]:
        """Список активных товаров по категории (или без фильтра, если category_id=None)."""
        stmt = select(Product).where(Product.is_active.is_(True))
        if category_id is not None:
            stmt = stmt.where(Product.category_id == category_id)
        stmt = stmt.order_by(Product.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def create(
            session: AsyncSession,
            *,
            title: str,
            price: Decimal,
            currency: str = "EUR",
            category_id: int | None = None,
            description: str | None = None,
            is_active: bool = True,
            image_urls: Iterable[str] | None = None,
    ) -> Product:
        """Создать товар и, при необходимости, изображения."""
        obj = Product(
            title=title,
            description=description,
            price=price,
            currency=currency,
            category_id=category_id,
            is_active=is_active,
        )
        session.add(obj)
        await session.flush()

        if image_urls:
            for i, url in enumerate(image_urls):
                session.add(ProductImage(product_id=obj.id, url=str(url), sort_order=i))
            await session.flush()

        return obj

    @staticmethod
    async def update(session: AsyncSession, product_id: int, **fields) -> Optional[Product]:
        """Обновить товар и вернуть объект."""
        await session.execute(update(Product).where(Product.id == product_id).values(**fields))
        await session.flush()
        return await ProductRepo.get(session, product_id)

    @staticmethod
    async def delete(session: AsyncSession, product_id: int) -> None:
        """Удалить товар по id."""
        await session.execute(delete(Product).where(Product.id == product_id))
        await session.flush()


# -------- Cart --------
class CartRepo:
    """Репозиторий корзины пользователя."""

    @staticmethod
    async def get_or_create_active_cart(session: AsyncSession, user_id: int) -> Cart:
        """
        Получить активную корзину пользователя или создать новую.

        Важно:
        - Допускается ровно одна активная корзина на пользователя.
        """
        stmt = select(Cart).where(Cart.user_id == user_id, Cart.status == CartStatus.ACTIVE)
        result = await session.execute(stmt)
        cart = result.scalar_one_or_none()
        if cart is None:
            cart = Cart(user_id=user_id, status=CartStatus.ACTIVE)
            session.add(cart)
            await session.flush()
        return cart

    @staticmethod
    async def add_item(session: AsyncSession, *, user_id: int, product_id: int, quantity: int = 1) -> CartItem:
        """
        Добавить позицию в корзину (или увеличить количество, если уже есть).

        Правила:
        - Цена фиксируется по текущей цене товара (price_at_added).
        """
        cart = await CartRepo.get_or_create_active_cart(session, user_id=user_id)
        product = await ProductRepo.get(session, product_id)
        if product is None or not product.is_active:
            raise ValueError("Товар не найден или неактивен")

        # Есть ли уже такая позиция?
        stmt = select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id)
        result = await session.execute(stmt)
        item = result.scalar_one_or_none()

        if item:
            item.quantity += quantity
        else:
            item = CartItem(
                cart_id=cart.id,
                product_id=product_id,
                quantity=quantity,
                price_at_added=product.price,  # фиксируем текущую цену
            )
            session.add(item)

        await session.flush()
        return item

    @staticmethod
    async def set_quantity(session: AsyncSession, *, user_id: int, product_id: int, quantity: int) -> Optional[
        CartItem]:
        """Установить точное количество позиции (quantity >= 0). Если 0 — удалить позицию."""
        cart = await CartRepo.get_or_create_active_cart(session, user_id=user_id)
        stmt = select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id)
        result = await session.execute(stmt)
        item = result.scalar_one_or_none()
        if item is None:
            return None
        if quantity <= 0:
            await session.delete(item)
            await session.flush()
            return None
        item.quantity = quantity
        await session.flush()
        return item

    @staticmethod
    async def remove_item(session: AsyncSession, *, user_id: int, product_id: int) -> None:
        """Удалить позицию из корзины."""
        cart = await CartRepo.get_or_create_active_cart(session, user_id=user_id)
        await session.execute(
            delete(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id)
        )
        await session.flush()

    @staticmethod
    async def clear(session: AsyncSession, *, user_id: int) -> None:
        """Очистить корзину целиком."""
        cart = await CartRepo.get_or_create_active_cart(session, user_id=user_id)
        await session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        await session.flush()

    @staticmethod
    async def get_items(session: AsyncSession, *, user_id: int) -> List[CartItem]:
        """Вернуть список позиций активной корзины пользователя."""
        cart = await CartRepo.get_or_create_active_cart(session, user_id=user_id)
        stmt = (
            select(CartItem)
            .where(CartItem.cart_id == cart.id)
            .options(joinedload(CartItem.product))
            .order_by(CartItem.id.asc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def subtotal(session: AsyncSession, *, user_id: int) -> Decimal:
        """
        Посчитать сумму корзины: sum(quantity * price_at_added).

        Возвращает Decimal с точностью БД.
        """
        cart = await CartRepo.get_or_create_active_cart(session, user_id=user_id)
        stmt = select(func.coalesce(func.sum(CartItem.quantity * CartItem.price_at_added), 0)).where(
            CartItem.cart_id == cart.id
        )
        result = await session.execute(stmt)
        total = result.scalar_one()
        # SQLAlchemy может вернуть Decimal или Numeric; явно приводим к Decimal
        return Decimal(total)


# -------- Order --------
class OrderRepo:
    """Репозиторий заказов и создание заказа из корзины."""

    @staticmethod
    async def generate_order_number(order_id: int, created_at: datetime.datetime | None = None) -> str:
        """Сформировать номер заказа в формате ORDER-YYYYMMDD-<id>."""
        created_at = created_at or datetime.datetime.utcnow()
        return f"ORDER-{created_at.strftime('%Y%m%d')}-{order_id}"

    @staticmethod
    async def create_from_cart(
            session: AsyncSession,
            *,
            user_id: int,
            contact_name: str,
            contact_phone: str,
            address: str | None,
            delivery_type: str | None,
            currency: str = "EUR",
    ) -> Order:
        """
        Создать заказ из текущей активной корзины пользователя.

        Алгоритм:
        - Получить активную корзину и её позиции.
        - Посчитать сумму.
        - Создать Order (без order_number), flush() -> получить id.
        - Проставить order_number и создать OrderItem по каждой позиции.
        - Очистить корзину и перевести её статус в ORDERED.
        """
        # 1) Корзина и позиции
        cart = await CartRepo.get_or_create_active_cart(session, user_id=user_id)
        items = await CartRepo.get_items(session, user_id=user_id)
        if not items:
            raise ValueError("Корзина пуста")

        # 2) Сумма
        total = await CartRepo.subtotal(session, user_id=user_id)

        # 3) Создаём заказ
        order = Order(
            user_id=user_id,
            status=OrderStatus.NEW,
            total_amount=total,
            currency=currency,
            contact_name=contact_name,
            contact_phone=contact_phone,
            address=address,
            delivery_type=delivery_type,
            created_at=datetime.datetime.utcnow(),
        )
        session.add(order)
        await session.flush()  # получаем order.id

        order.order_number = await OrderRepo.generate_order_number(order.id, order.created_at)

        # 4) Позиции заказа
        for ci in items:
            oi = OrderItem(
                order_id=order.id,
                product_id=ci.product_id,
                quantity=ci.quantity,
                item_price=ci.price_at_added,
            )
            session.add(oi)

        # 5) Очистка корзины и смена статуса
        await session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        cart.status = CartStatus.ORDERED
        await session.flush()

        return order

    @staticmethod
    async def get(session: AsyncSession, order_id: int) -> Optional[Order]:
        """Получить заказ по id (с позициями)."""
        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(joinedload(Order.items).joinedload(OrderItem.product))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_admin(session: AsyncSession, *, limit: int = 50, offset: int = 0) -> List[Order]:
        """Список заказов (для админ-панели)."""
        stmt = (
            select(Order)
            .order_by(Order.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def set_status(session: AsyncSession, order_id: int, status: OrderStatus) -> Optional[Order]:
        """Изменить статус заказа и вернуть обновлённый объект."""
        stmt = update(Order).where(Order.id == order_id).values(status=status)
        await session.execute(stmt)
        await session.flush()
        return await OrderRepo.get(session, order_id)
