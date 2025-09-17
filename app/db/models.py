from __future__ import annotations

"""
Модели SQLAlchemy для простого магазина с корзиной и заказами.

Содержит:
- Пользователей (User)
- Категории товаров (Category) — древовидная структура
- Товары (Product) и их изображения (ProductImage)
- Корзины (Cart) и элементы корзины (CartItem)
- Заказы (Order) и позиции заказа (OrderItem)
- Перечисления статусов заказа и корзины

"""

import datetime
import enum
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Numeric,
    Boolean,
    ForeignKey,
    DateTime,
    Enum,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class OrderStatus(enum.Enum):
    """
    Статусы заказа.

    Значения хранятся в БД как строки:
      - "new" — новый
      - "processing" — в обработке
      - "shipped" — отправлен
      - "delivered" — доставлен
      - "cancelled" — отменён
    """
    NEW = "new"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class CartStatus(enum.Enum):
    """
    Статусы корзины.
    """
    ACTIVE = "active"
    ORDERED = "ordered"


class User(Base):
    """
    Пользователь Telegram.

    Поля:
        id: Telegram user id (BigInteger, PK).
        full_name: Полное имя пользователя.
        phone: Номер телефона.
        created_at: Дата и время создания записи (UTC).
    Отношения:
        carts: список корзин пользователя.
        orders: список заказов пользователя.
    """
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)  # telegram user id
    full_name = Column(String(255), nullable=True)
    phone = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Связи: пользователь -> корзины, пользователь -> заказы
    carts = relationship("Cart", back_populates="user", cascade="all,delete-orphan")
    orders = relationship("Order", back_populates="user", cascade="all,delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.full_name!r}>"


class Category(Base):
    """
    Категория товара (может быть вложенной — дерево).

    Поля:
        id: PK
        title: Название категории.
        slug: Уникальный slug (опционально).
        parent_id: Ссылка на родительскую категорию (self-referential FK).
    Отношения:
        parent: ссылка на родителя.
        children: обратная связь — список дочерних категорий.
    """
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=True, unique=True)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # remote_side необходим для self-referential relationship
    parent = relationship("Category", remote_side=[id], backref="children")

    def __repr__(self) -> str:
        return f"<Category id={self.id} title={self.title!r}>"


class Product(Base):
    """
    Товар.

    Поля:
        id: PK
        title: Название товара.
        description: Описание товара.
        price: Цена (фиксированная точность).
        currency: Валюта (по умолчанию "RUB").
        category_id: FK на категорию.
        is_active: Флаг доступности товара.
        created_at, updated_at: метки времени.
    Отношения:
        category: категория товара.
        images: список изображений товара.
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(8), default="RUB", nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    # backref "products" добавляет Category.products
    category = relationship("Category", backref="products")
    images = relationship("ProductImage", back_populates="product", cascade="all,delete-orphan")

    def __repr__(self) -> str:
        return f"<Product id={self.id} title={self.title!r} price={self.price}>"


class ProductImage(Base):
    """
    Изображение товара.

    Поля:
        id: PK
        product_id: FK на products.id (CASCADE при удалении товара).
        url: URL изображения (опционально).
        telegram_file_id: telegram file_id (опционально).
        sort_order: порядок отображения изображений для товара.
    Индексы/ограничения:
        Уникальное сочетание (product_id, sort_order) — порядок уникален в рамках товара.
    """
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    url = Column(Text, nullable=True)
    telegram_file_id = Column(String(255), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)

    product = relationship("Product", back_populates="images")

    __table_args__ = (
        UniqueConstraint("product_id", "sort_order", name="uq_product_image_order"),
    )

    def __repr__(self) -> str:
        return f"<ProductImage id={self.id} product_id={self.product_id}>"


class Cart(Base):
    """
    Корзина пользователя.

    Поля:
        id: PK
        user_id: FK на пользователя.
        status: Статус корзины (CartStatus).
        created_at, updated_at: метки времени.
    Отношения:
        user: владелец корзины.
        items: элементы корзины (CartItem).
    """
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(CartStatus), default=CartStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    user = relationship("User", back_populates="carts")
    items = relationship("CartItem", back_populates="cart", cascade="all,delete-orphan")

    def __repr__(self) -> str:
        # .value даёт человекочитаемое значение enum-а
        return f"<Cart id={self.id} user_id={self.user_id} status={self.status.value}>"


class CartItem(Base):
    """
    Элемент корзины.

    Поля:
        id: PK
        cart_id: FK на корзину (CASCADE при удалении корзины).
        product_id: FK на товар.
        quantity: Количество.
        price_at_added: Цена товара на момент добавления в корзину (фиксируем).
    Ограничения:
        Уникальность (cart_id, product_id) — один товар в корзине хранится одной записью.
    """
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    price_at_added = Column(Numeric(10, 2), nullable=False)  # фиксируем цену на момент добавления

    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")

    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", name="uq_cart_product"),
    )

    def __repr__(self) -> str:
        return f"<CartItem id={self.id} cart_id={self.cart_id} product_id={self.product_id} qty={self.quantity}>"


class Order(Base):
    """
    Заказ.

    Поля:
        id: PK
        order_number: Уникальный номер заказа (строка).
        user_id: FK на пользователя (покупателя).
        status: Статус заказа (OrderStatus).
        total_amount: Общая сумма заказа.
        currency: Валюта суммы (по умолчанию "RUB").
        contact_name, contact_phone: Контактные данные получателя.
        address: Адрес доставки (опционально).
        delivery_type: Тип доставки (опционально).
        created_at, updated_at: метки времени.
    Отношения:
        user: покупатель (User).
        items: позиции заказа (OrderItem).
    """
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    order_number = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.NEW, nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(8), default="RUB", nullable=False)

    # Контактные данные / доставка
    contact_name = Column(String(255), nullable=False)
    contact_phone = Column(String(64), nullable=False)
    address = Column(Text, nullable=True)
    delivery_type = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all,delete-orphan")

    def __repr__(self) -> str:
        return f"<Order id={self.id} order_number={self.order_number} total={self.total_amount}>"


class OrderItem(Base):
    """
    Позиция в заказе.

    Поля:
        id: PK
        order_id: FK на заказ (CASCADE при удалении заказа).
        product_id: FK на товар.
        quantity: Количество единиц товара.
        item_price: Цена за единицу на момент покупки.
    """
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    item_price = Column(Numeric(10, 2), nullable=False)  # цена за единицу на момент покупки

    order = relationship("Order", back_populates="items")
    product = relationship("Product")

    def __repr__(self) -> str:
        return f"<OrderItem id={self.id} order_id={self.order_id} product_id={self.product_id} qty={self.quantity}>"
