"""
Редактирование товаров (админ)

"""
from __future__ import annotations

from decimal import Decimal
from typing import List

from aiogram import Router, F
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message, ContentType

from app.core.config import settings
from app.db.session import AsyncSessionFactory
from app.db.repository import ProductRepo, CategoryRepo
from app.bot.keyboards.admin_keyboard import build_admin_menu_kb
from app.bot.keyboards.admin_edit_keyboard import (
    build_edit_menu_kb,
    build_edit_back_cancel_kb,
    EDIT_BACK_CB,
    EDIT_CANCEL_CB,
)

admin_edit_router = Router(name="admin_edit")


# ─────────────────────────── Фильтр «только админы» ─────────────────────────── #

class AdminOnly(BaseFilter):
    """Пропускает только пользователей из списка админов."""

    async def __call__(self, obj: Message | CallbackQuery) -> bool:
        uid = obj.from_user.id if obj.from_user else None
        return bool(uid and uid in settings.ADMIN_ID_LIST)


# ──────────────────────────────── FSM состояния ─────────────────────────────── #

class EditProductSG(StatesGroup):
    """Состояния редактирования товара."""
    wait_product_id = State()
    menu = State()
    title = State()
    price = State()
    category_id = State()
    description = State()
    photos = State()


# ───────────────────────────── Старт редактирования ─────────────────────────── #

@admin_edit_router.callback_query(AdminOnly(), F.data == "admin:cmd:edit")
async def edit_product_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало сценария: запросить ID товара."""
    await state.clear()
    await state.set_state(EditProductSG.wait_product_id)
    await callback.message.answer(
        "✏️ Введите ID товара для редактирования:",
        reply_markup=build_edit_back_cancel_kb(include_back=True),
    )
    await callback.answer()


@admin_edit_router.callback_query(AdminOnly(), F.data == EDIT_CANCEL_CB)
async def edit_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена редактирования."""
    await state.clear()
    await callback.message.answer("❌ Редактирование отменено.", reply_markup=build_admin_menu_kb())
    await callback.answer()


@admin_edit_router.callback_query(AdminOnly(), F.data == EDIT_BACK_CB)
async def edit_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Кнопка «Назад» — возврат в предыдущее состояние/меню."""
    current = await state.get_state()
    data = await state.get_data()

    if current == EditProductSG.wait_product_id.state:
        await state.clear()
        await callback.message.answer("⚙️ Админ-панель:", reply_markup=build_admin_menu_kb())
        await callback.answer()
        return

    if current in {
        EditProductSG.menu.state,
        EditProductSG.title.state,
        EditProductSG.price.state,
        EditProductSG.category_id.state,
        EditProductSG.description.state,
        EditProductSG.photos.state,
    }:
        pid = data.get("product_id")
        if pid:
            await _show_product_menu(callback.message, product_id=int(pid), state=state)
        else:
            await state.set_state(EditProductSG.wait_product_id)
            await callback.message.answer(
                "✏️ Введите ID товара:",
                reply_markup=build_edit_back_cancel_kb(include_back=True),
            )
        await callback.answer()
        return

    await edit_cancel(callback, state)


# ─────────────────────────────── Ввод ID товара ─────────────────────────────── #

@admin_edit_router.message(AdminOnly(), EditProductSG.wait_product_id)
async def input_product_id(message: Message, state: FSMContext) -> None:
    """Обработка ввода ID товара."""
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer(
            "ID должен быть числом. Повторите ввод:",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
        return
    product_id = int(raw)

    async with AsyncSessionFactory() as session:
        product = await ProductRepo.get(session, product_id)
    if not product:
        await message.answer(
            "Товар не найден. Введите другой ID:",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
        return

    await state.update_data(product_id=product_id)
    await _show_product_menu(message, product_id=product_id, state=state)


# ─────────────────────────────── Меню полей товара ──────────────────────────── #

async def _show_product_menu(msg_or_cbmsg: Message, *, product_id: int, state: FSMContext) -> None:
    """Показать сводку и клавиатуру выбора поля для редактирования."""
    async with AsyncSessionFactory() as session:
        product = await ProductRepo.get(session, product_id)

    if not product:
        await state.set_state(EditProductSG.wait_product_id)
        await msg_or_cbmsg.answer(
            "Товар не найден. Введите ID снова:",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
        return

    text = (
        f"🛍 <b>{product.title}</b>\n"
        f"ID: <code>{product.id}</code>\n"
        f"Цена: <b>{product.price} {product.currency}</b>\n"
        f"Категория ID: <b>{product.category_id or '—'}</b>\n"
        f"Фото: {len(product.images or [])} шт.\n\n"
        f"{product.description or '—'}"
    )
    kb = build_edit_menu_kb(product_id=product.id)
    await state.set_state(EditProductSG.menu)
    await msg_or_cbmsg.answer(text, reply_markup=kb)


# ───────────────────────────── Колбэки из меню полей ────────────────────────── #

@admin_edit_router.callback_query(AdminOnly(), F.data.startswith("admin:edit:field:"))
async def edit_field_entry(callback: CallbackQuery, state: FSMContext) -> None:
    """Переход в ввод конкретного поля (title/price/category/description/photos)."""
    try:
        _, _, _, field, pid = callback.data.split(":")
        product_id = int(pid)
    except Exception:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    await state.update_data(product_id=product_id)

    if field == "title":
        await state.set_state(EditProductSG.title)
        await callback.message.answer(
            "✏️ Введите новое название:",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
    elif field == "price":
        await state.set_state(EditProductSG.price)
        await callback.message.answer(
            "💰 Введите новую цену:",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
    elif field == "category":
        await state.set_state(EditProductSG.category_id)
        await callback.message.answer(
            "📁 Введите ID категории (0 — убрать):",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
    elif field == "description":
        await state.set_state(EditProductSG.description)
        await callback.message.answer(
            "📝 Введите новое описание ('-' — очистить):",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
    elif field == "photos":
        await state.set_state(EditProductSG.photos)
        await state.update_data(_photos=[])
        await callback.message.answer(
            "🖼 Пришлите новые фото. Когда закончите — отправьте 'готово'.",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
    else:
        await callback.answer("Неизвестное поле", show_alert=True)
        return

    await callback.answer()


# ───────────────────────────── Обработчики значений ─────────────────────────── #

@admin_edit_router.message(AdminOnly(), EditProductSG.title)
async def edit_set_title(message: Message, state: FSMContext) -> None:
    """Сохранить новое название товара."""
    new_title = (message.text or "").strip()
    if not new_title:
        await message.answer(
            "Пустое значение. Введите название ещё раз:",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
        return

    data = await state.get_data()
    pid = int(data["product_id"])

    async with AsyncSessionFactory() as session:
        async with session.begin():
            await ProductRepo.update_fields(session, product_id=pid, title=new_title)

    await _show_product_menu(message, product_id=pid, state=state)


@admin_edit_router.message(AdminOnly(), EditProductSG.price)
async def edit_set_price(message: Message, state: FSMContext) -> None:
    """Сохранить новую цену товара."""
    raw = (message.text or "").replace(",", ".").strip()
    try:
        price = Decimal(raw)
    except Exception:
        await message.answer(
            "Некорректная цена. Пример: 1999.99",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
        return

    data = await state.get_data()
    pid = int(data["product_id"])

    async with AsyncSessionFactory() as session:
        async with session.begin():
            await ProductRepo.update_fields(session, product_id=pid, price=price)

    await _show_product_menu(message, product_id=pid, state=state)


@admin_edit_router.message(AdminOnly(), EditProductSG.category_id)
async def edit_set_category(message: Message, state: FSMContext) -> None:
    """Сохранить новую категорию товара (0 — убрать категорию)."""
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer(
            "ID категории должен быть числом. Введите снова:",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
        return

    cid = int(raw)
    new_category_id = None if cid == 0 else cid

    # (Необязательно) Можно проверить существование категории:
    if new_category_id is not None:
        async with AsyncSessionFactory() as session:
            category = await CategoryRepo.get(session, new_category_id)
        if not category:
            await message.answer(
                "Категория не найдена. Введите корректный ID или 0 для удаления.",
                reply_markup=build_edit_back_cancel_kb(include_back=True),
            )
            return

    data = await state.get_data()
    pid = int(data["product_id"])

    async with AsyncSessionFactory() as session:
        async with session.begin():
            await ProductRepo.update_fields(session, product_id=pid, category_id=new_category_id)

    await _show_product_menu(message, product_id=pid, state=state)


@admin_edit_router.message(AdminOnly(), EditProductSG.description)
async def edit_set_description(message: Message, state: FSMContext) -> None:
    """Сохранить новое описание ('-' — очистить)."""
    desc = None if (message.text or "").strip() == "-" else (message.text or "").strip()

    data = await state.get_data()
    pid = int(data["product_id"])

    async with AsyncSessionFactory() as session:
        async with session.begin():
            await ProductRepo.update_fields(session, product_id=pid, description=desc)

    await _show_product_menu(message, product_id=pid, state=state)


# ─────────────────────────────── Замена фотографий ───────────────────────────── #

@admin_edit_router.message(AdminOnly(), EditProductSG.photos, F.text)
async def edit_photos_text(message: Message, state: FSMContext) -> None:
    """
    Текст в режиме загрузки фото:
    — 'готово'/'done' применяет собранные фото к товару (полная замена).
    """
    txt = (message.text or "").strip().lower()
    if txt in {"готово", "done"}:
        data = await state.get_data()
        files: List[str] = list(data.get("_photos", []))
        pid = int(data["product_id"])

        async with AsyncSessionFactory() as session:
            async with session.begin():
                await ProductRepo.replace_images(session, product_id=pid, telegram_file_ids=files)

        await state.update_data(_photos=[])
        await _show_product_menu(message, product_id=pid, state=state)
        return

    await message.answer(
        "Пришлите фото или 'готово' для применения.",
        reply_markup=build_edit_back_cancel_kb(include_back=True),
    )


@admin_edit_router.message(AdminOnly(), EditProductSG.photos, F.content_type == ContentType.PHOTO)
async def edit_photos_collect(message: Message, state: FSMContext) -> None:
    """Копит file_id фотографий для последующей замены."""
    file_id = message.photo[-1].file_id
    data = await state.get_data()
    photos: List[str] = list(data.get("_photos", []))
    photos.append(file_id)
    await state.update_data(_photos=photos)
    await message.answer(f"Фото принято ✅ (всего: {len(photos)}). Пришлите ещё или 'готово'.")
