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
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ─────────────────────────── Общий миксин ─────────────────────────── #

class TimestampMixin:
    """
    Единые временные метки с поддержкой таймзоны.
    created_at задаётся при вставке, updated_at обновляется при изменении.
    """
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


# ─────────────────────────── Enum-ы ─────────────────────────── #

class OrderStatus(enum.Enum):
    NEW = "new"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class CartStatus(enum.Enum):
    ACTIVE = "active"
    ORDERED = "ordered"


# ─────────────────────────── Модели ─────────────────────────── #

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)  # Telegram user id
    full_name = Column(String(255), nullable=True)
    phone = Column(String(64), nullable=True)

    carts = relationship("Cart", back_populates="user", cascade="all,delete-orphan")
    orders = relationship("Order", back_populates="user", cascade="all,delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.full_name!r}>"


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=True, unique=True)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    parent = relationship("Category", remote_side=[id], backref="children")

    def __repr__(self) -> str:
        return f"<Category id={self.id} title={self.title!r}>"


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(8), default="RUB", nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    category = relationship("Category", backref="products")
    images = relationship("ProductImage", back_populates="product", cascade="all,delete-orphan")

    def __repr__(self) -> str:
        return f"<Product id={self.id} title={self.title!r} price={self.price}>"


class ProductImage(Base):
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


class Cart(Base, TimestampMixin):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(CartStatus), default=CartStatus.ACTIVE, nullable=False)

    user = relationship("User", back_populates="carts")
    items = relationship("CartItem", back_populates="cart", cascade="all,delete-orphan")

    def __repr__(self) -> str:
        return f"<Cart id={self.id} user_id={self.user_id} status={self.status.value}>"


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    price_at_added = Column(Numeric(10, 2), nullable=False)

    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")

    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", name="uq_cart_product"),
    )

    def __repr__(self) -> str:
        return f"<CartItem id={self.id} cart_id={self.cart_id} product_id={self.product_id} qty={self.quantity}>"


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    order_number = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.NEW, nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(8), default="RUB", nullable=False)

    contact_name = Column(String(255), nullable=False)
    contact_phone = Column(String(64), nullable=False)
    address = Column(Text, nullable=True)
    delivery_type = Column(String(64), nullable=True)

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all,delete-orphan")

    def __repr__(self) -> str:
        return f"<Order id={self.id} order_number={self.order_number} total={self.total_amount}>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    item_price = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")

    def __repr__(self) -> str:
        return f"<OrderItem id={self.id} order_id={self.order_id} product_id={self.product_id} qty={self.quantity}>"
