from __future__ import annotations
"""
Repository layer (доступ к БД и транзакции)

"""

import datetime
from decimal import Decimal
from typing import List, Optional
from datetime import datetime, UTC
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.logging_cfg import logger
from app.db.models import (
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

# =========================
# Пользователи
# =========================
class UserRepo:
    """Репозиторий пользователей."""

    @staticmethod
    async def get(session: AsyncSession, user_id: int) -> Optional[User]:
        """Получить пользователя по Telegram ID."""
        res = await session.execute(select(User).where(User.id == user_id))
        user = res.scalar_one_or_none()
        logger.debug("UserRepo.get: user_id=%s -> %s", user_id, bool(user))
        return user

    @staticmethod
    async def get_or_create(session: AsyncSession, *, user_id: int, full_name: str | None = None) -> User:
        """
        Гарантирует наличие пользователя:
        - если есть — возвращает;
        - если нет — создаёт запись c переданным full_name (может быть None).
        """
        res = await session.execute(select(User).where(User.id == user_id).limit(1))
        user = res.scalar_one_or_none()
        if user:
            logger.debug("UserRepo.get_or_create: found user_id=%s", user_id)
            return user

        user = User(id=user_id, full_name=full_name or "")
        session.add(user)
        await session.flush()
        logger.info("UserRepo.get_or_create: created user_id=%s full_name='%s'", user_id, full_name or "")
        return user


# =========================
# Категории / Товары
# =========================
class CategoryRepo:
    @staticmethod
    async def get(session: AsyncSession, category_id: int) -> Optional[Category]:
        """
        Получить категорию по id.
        Нужен для валидации шага FSM в админке при вводе ID категории.
        """
        res = await session.execute(select(Category).where(Category.id == category_id).limit(1))
        cat = res.scalar_one_or_none()
        logger.debug("CategoryRepo.get: id=%s -> %s", category_id, bool(cat))
        return cat

    @staticmethod
    async def list_root(session: AsyncSession) -> List[Category]:
        res = await session.execute(
            select(Category).where(Category.parent_id.is_(None)).order_by(Category.id)
        )
        rows = res.scalars().all()
        logger.debug("CategoryRepo.list_root: count=%s", len(rows))
        return rows

    @staticmethod
    async def list_children(session: AsyncSession, *, parent_id: int) -> List[Category]:
        res = await session.execute(
            select(Category).where(Category.parent_id == parent_id).order_by(Category.id)
        )
        rows = res.scalars().all()
        logger.debug("CategoryRepo.list_children: parent_id=%s count=%s", parent_id, len(rows))
        return rows


class ProductRepo:
    @staticmethod
    async def get(session: AsyncSession, product_id: int) -> Optional[Product]:
        """
        Вернуть товар по id вместе с изображениями.
        ВАЖНО: при joinedload коллекции нужен res.unique().
        """
        res = await session.execute(
            select(Product)
            .options(joinedload(Product.images))
            .where(Product.id == product_id)
            .limit(1)
        )
        product = res.unique().scalar_one_or_none()
        logger.debug("ProductRepo.get: product_id=%s -> %s", product_id, bool(product))
        return product

    @staticmethod
    async def list_by_category(
        session: AsyncSession,
        *,
        category_id: int | None,
        limit: int,
        offset: int,
    ) -> List[Product]:
        """Список активных товаров, опционально отфильтрованных по категории (пагинация)."""
        q = select(Product).where(Product.is_active.is_(True)).order_by(Product.id)
        if category_id is not None:
            q = q.where(Product.category_id == category_id)
        res = await session.execute(q.limit(limit).offset(offset))
        rows = res.scalars().all()
        logger.debug(
            "ProductRepo.list_by_category: category_id=%s limit=%s offset=%s -> %s",
            category_id, limit, offset, len(rows)
        )
        return rows

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
    ) -> Product:
        """
        Создать товар без изображений (изображения добавляются отдельно в ProductImage).
        """
        product = Product(
            title=title,
            description=description,
            price=price,
            currency=currency,
            category_id=category_id,
            is_active=is_active,
        )
        session.add(product)
        await session.flush()
        logger.info("ProductRepo.create: id=%s title=%r", product.id, product.title)
        return product

    @staticmethod
    async def update_fields(
            session,
            *,
            product_id: int,
            title: str | None = None,
            price: Decimal | None = None,
            category_id: int | None = None,
            description: str | None = None,
    ):
        """Обновить указанные поля товара."""
        from sqlalchemy import select
        from app.db.models import Product

        res = await session.execute(select(Product).where(Product.id == product_id).limit(1))
        product = res.scalar_one_or_none()
        if not product:
            return None

        if title is not None:
            product.title = title
        if price is not None:
            product.price = price
        if description is not None or description is None:
            product.description = description
        if category_id is not None or category_id is None:
            product.category_id = category_id

        await session.flush()
        return product

    @staticmethod
    async def replace_images(session, *, product_id: int, telegram_file_ids: list[str]) -> None:
        """
        Полная замена набора изображений товара. Старые удаляются, новые вставляются
        с последовательным sort_order.
        """

        await session.execute(delete(ProductImage).where(ProductImage.product_id == product_id))
        for idx, file_id in enumerate(telegram_file_ids):
            session.add(ProductImage(product_id=product_id, telegram_file_id=file_id, sort_order=idx))
        await session.flush()
        logger.info("ProductRepo.replace_images: product_id=%s images=%s", product_id, len(telegram_file_ids))



# =========================
# Корзина
# =========================
class CartRepo:
    """Операции с корзиной пользователя."""

    @staticmethod
    async def get_or_create_active_cart(session: AsyncSession, *, user_id: int) -> Cart:
        # гарантируем пользователя (лениво)
        user = await UserRepo.get_or_create(session, user_id=user_id)

        res = await session.execute(
            select(Cart)
            .where(Cart.user_id == user.id, Cart.status == CartStatus.ACTIVE)
            .limit(1)
        )
        cart = res.scalar_one_or_none()
        if cart:
            logger.debug("CartRepo.get_or_create_active_cart: user_id=%s -> cart_id=%s", user_id, cart.id)
            return cart

        cart = Cart(user_id=user.id, status=CartStatus.ACTIVE)
        session.add(cart)
        await session.flush()
        logger.info("CartRepo.get_or_create_active_cart: created cart_id=%s for user_id=%s", cart.id, user_id)
        return cart

    @staticmethod
    async def add_item(session: AsyncSession, *, user_id: int, product_id: int, quantity: int = 1) -> CartItem:
        """
        Добавить позицию в корзину (или увеличить количество).
        Бросает ValueError, если товар не существует или не активен.
        """
        cart = await CartRepo.get_or_create_active_cart(session, user_id=user_id)

        # Проверка существования/активности товара
        res_prod = await session.execute(select(Product).where(Product.id == product_id).limit(1))
        product = res_prod.scalar_one_or_none()
        if not product or not product.is_active:
            logger.warning("CartRepo.add_item: product invalid/disabled product_id=%s", product_id)
            raise ValueError("Товар недоступен")

        # Ищем существующую позицию
        res = await session.execute(
            select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id).limit(1)
        )
        item = res.scalar_one_or_none()
        if item:
            old = item.quantity
            item.quantity = old + quantity
            await session.flush()
            logger.info("CartRepo.add_item: INC item_id=%s %s -> %s", item.id, old, item.quantity)
            return item

        # Создаём новую позицию
        item = CartItem(
            cart_id=cart.id,
            product_id=product_id,
            quantity=quantity,
            price_at_added=product.price,
        )
        session.add(item)
        await session.flush()
        logger.info("CartRepo.add_item: cart_id=%s product_id=%s qty=%s CREATED", cart.id, product_id, quantity)
        return item

    @staticmethod
    async def set_quantity(session: AsyncSession, *, user_id: int, product_id: int, quantity: int) -> Optional[CartItem]:
        cart = await CartRepo.get_or_create_active_cart(session, user_id=user_id)
        res = await session.execute(
            select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id).limit(1)
        )
        item = res.scalar_one_or_none()
        if not item:
            logger.debug("CartRepo.set_quantity: no item cart_id=%s product_id=%s", cart.id, product_id)
            return None

        if quantity <= 0:
            await session.execute(delete(CartItem).where(CartItem.id == item.id))
            await session.flush()
            logger.info("CartRepo.set_quantity: DELETE item_id=%s (qty<=0)", item.id)
            return None

        old = item.quantity
        item.quantity = quantity
        await session.flush()
        logger.info("CartRepo.set_quantity: item_id=%s qty %s -> %s", item.id, old, item.quantity)
        return item

    @staticmethod
    async def remove_item(session: AsyncSession, *, user_id: int, product_id: int) -> None:
        cart = await CartRepo.get_or_create_active_cart(session, user_id=user_id)
        res = await session.execute(
            select(CartItem.id).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id).limit(1)
        )
        item_id = res.scalar_one_or_none()
        if item_id is None:
            logger.debug("CartRepo.remove_item: nothing to delete cart_id=%s product_id=%s", cart.id, product_id)
            return
        await session.execute(delete(CartItem).where(CartItem.id == item_id))
        await session.flush()
        logger.info("CartRepo.remove_item: deleted item_id=%s", item_id)

    @staticmethod
    async def clear(session: AsyncSession, *, user_id: int) -> None:
        cart = await CartRepo.get_or_create_active_cart(session, user_id=user_id)
        deleted = await session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        await session.flush()
        logger.info("CartRepo.clear: cart_id=%s cleared (rowcount=%s)", cart.id, deleted.rowcount)

    @staticmethod
    async def get_items(session: AsyncSession, *, user_id: int) -> List[CartItem]:
        cart = await CartRepo.get_or_create_active_cart(session, user_id=user_id)
        res = await session.execute(
            select(CartItem)
            .options(joinedload(CartItem.product))
            .where(CartItem.cart_id == cart.id)
            .order_by(CartItem.id)
        )
        items = res.scalars().all()
        logger.debug("CartRepo.get_items: cart_id=%s items=%s", cart.id, len(items))
        return items

    @staticmethod
    async def subtotal(session: AsyncSession, *, user_id: int) -> Decimal:
        cart = await CartRepo.get_or_create_active_cart(session, user_id=user_id)
        res = await session.execute(
            select(func.coalesce(func.sum(CartItem.quantity * CartItem.price_at_added), 0)).where(
                CartItem.cart_id == cart.id
            )
        )
        total = Decimal(res.scalar_one() or 0)
        logger.debug("CartRepo.subtotal: cart_id=%s total=%s", cart.id, total)
        return total


# =========================
# Заказы
# =========================
class OrderRepo:
    @staticmethod
    async def generate_order_number(*, order_id: int, created_at: datetime.datetime) -> str:
        # ORDER-YYYYMMDD-<id>
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
        Создать заказ из активной корзины пользователя.
        Обходит NOT NULL у orders.order_number через временный уникальный номер, затем
        после flush() пересчитывает финальный номер ORDER-YYYYMMDD-<id>.
        """
        # активная корзина и позиции
        cart = await CartRepo.get_or_create_active_cart(session, user_id=user_id)
        items = await CartRepo.get_items(session, user_id=user_id)
        if not items:
            logger.warning("OrderRepo.create_from_cart: empty cart user_id=%s", user_id)
            raise ValueError("Корзина пуста")

        # сумма
        total = await CartRepo.subtotal(session, user_id=user_id)

        temp_number = f"TEMP-{int(datetime.now(UTC).timestamp() * 1000)}-{user_id}"

        order = Order(
            order_number=temp_number,
            user_id=user_id,
            status=OrderStatus.NEW,
            total_amount=total,
            currency=currency,
            contact_name=contact_name,
            contact_phone=contact_phone,
            address=address,
            delivery_type=delivery_type,
        )
        session.add(order)
        await session.flush()  # теперь есть order.id/created_at

        # финальный номер
        final_number = await OrderRepo.generate_order_number(
            order_id=order.id, created_at=order.created_at  # type: ignore[arg-type]
        )
        order.order_number = final_number
        await session.flush()

        # перенос позиций корзины в order_items
        for it in items:
            session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=it.product_id,
                    quantity=it.quantity,
                    item_price=it.price_at_added,
                )
            )

        # пометить корзину и очистить её
        cart.status = CartStatus.ORDERED
        await session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        await session.flush()

        logger.info(
            "OrderRepo.create_from_cart: order_id=%s user_id=%s items=%s total=%s %s",
            order.id, user_id, len(items), total, currency
        )
        return order

    @staticmethod
    async def get(session: AsyncSession, order_id: int) -> Optional[Order]:
        res = await session.execute(
            select(Order)
            .options(joinedload(Order.items).joinedload(OrderItem.product))
            .where(Order.id == order_id)
            .limit(1)
        )
        order = res.unique().scalar_one_or_none()
        logger.debug("OrderRepo.get: order_id=%s -> %s", order_id, bool(order))
        return order

    @staticmethod
    async def list_for_admin(session: AsyncSession, *, limit: int = 50, offset: int = 0) -> List[Order]:
        res = await session.execute(
            select(Order).order_by(Order.id.desc()).limit(limit).offset(offset)
        )
        rows = res.scalars().all()
        logger.debug("OrderRepo.list_for_admin: limit=%s offset=%s -> %s", limit, offset, len(rows))
        return rows

    @staticmethod
    async def set_status(session: AsyncSession, order_id: int, status: OrderStatus) -> Optional[Order]:
        order = await OrderRepo.get(session, order_id)
        if not order:
            logger.warning("OrderRepo.set_status: order not found order_id=%s", order_id)
            return None
        old = order.status
        order.status = status
        await session.flush()
        logger.info("OrderRepo.set_status: order_id=%s %s -> %s", order_id, old.value, status.value)
        return order
