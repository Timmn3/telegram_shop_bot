"""
Редактирование товаров (админ): выбор товара и изменение полей через FSM.

"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional, List

from aiogram import Router, F
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message, ContentType

from app.core.config import settings
from app.core.logging_cfg import logger
from app.db.session import AsyncSessionFactory
from app.db.repository import ProductRepo, CategoryRepo
from app.db.models import ProductImage
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
    """Пропускает только Telegram ID из settings.ADMIN_ID_LIST."""
    async def __call__(self, obj: Message | CallbackQuery) -> bool:
        uid = obj.from_user.id if obj.from_user else None
        return bool(uid and uid in settings.ADMIN_ID_LIST)


# ─────────────────────────── FSM состояния ─────────────────────────── #

class EditProductSG(StatesGroup):
    """Состояния FSM редактирования товара."""
    wait_product_id = State()
    menu = State()

    # поля
    title = State()
    price = State()
    category_id = State()
    description = State()
    active = State()

    # замена фото — буфер
    photos = State()


# ─────────────────────────── Старт редактирования ─────────────────────────── #

@admin_edit_router.callback_query(AdminOnly(), F.data == "admin:cmd:edit")
async def edit_product_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Запуск потока редактирования из админ-меню."""
    await state.clear()
    await state.set_state(EditProductSG.wait_product_id)
    await callback.message.answer(
        "✏️ Введите ID товара, который хотите редактировать:",
        reply_markup=build_edit_back_cancel_kb(include_back=True),
    )
    await callback.answer()


@admin_edit_router.callback_query(AdminOnly(), F.data == EDIT_CANCEL_CB)
async def edit_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Глобальная отмена редактирования."""
    await state.clear()
    await callback.message.answer("❌ Редактирование отменено.", reply_markup=build_admin_menu_kb())
    await callback.answer()


@admin_edit_router.callback_query(AdminOnly(), F.data == EDIT_BACK_CB)
async def edit_back(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Кнопка «Назад». Поведение:
      - из меню полей → запросить ID товара заново
      - из любых шагов ввода поля → вернуться в меню полей
      - из шага ввода ID → вернуться в главное админ-меню
    """
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
        EditProductSG.active.state,
        EditProductSG.photos.state,
    }:
        pid = data.get("product_id")
        if not pid:
            await state.set_state(EditProductSG.wait_product_id)
            await callback.message.answer(
                "✏️ Введите ID товара для редактирования:",
                reply_markup=build_edit_back_cancel_kb(include_back=True),
            )
            await callback.answer()
            return
        # вернёмся в меню полей
        await _show_product_menu(callback.message, product_id=int(pid), state=state)
        await callback.answer()
        return

    # дефолт
    await edit_cancel(callback, state)


# ─────────────────────────── Ввод ID товара ─────────────────────────── #

@admin_edit_router.message(AdminOnly(), EditProductSG.wait_product_id)
async def input_product_id(message: Message, state: FSMContext) -> None:
    """Получить ID товара и открыть меню полей."""
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


# ─────────────────────────── Меню полей ─────────────────────────── #

async def _show_product_menu(msg_or_cbmsg: Message, *, product_id: int, state: FSMContext) -> None:
    """Показать краткую карточку товара и инлайн-меню полей."""
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
        f"Активен: <b>{'Да' if product.is_active else 'Нет'}</b>\n"
        f"Фото: {len(product.images or [])} шт.\n\n"
        f"{product.description or '—'}"
    )
    kb = build_edit_menu_kb(product_id=product.id)
    await state.set_state(EditProductSG.menu)
    await msg_or_cbmsg.answer(text, reply_markup=kb)


# ─────────────────────────── Колбэки меню полей ─────────────────────────── #

@admin_edit_router.callback_query(AdminOnly(), F.data.startswith("admin:edit:field:"))
async def edit_field_entry(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработка выбора пункта меню: admin:edit:field:<name>:<product_id>.
    Поля: title | price | category | description | active | photos
    """
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
            "💰 Введите новую цену (пример: 1999.99):",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
    elif field == "category":
        await state.set_state(EditProductSG.category_id)
        await callback.message.answer(
            "📁 Введите ID категории (или 0 — чтобы убрать категорию):",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
    elif field == "description":
        await state.set_state(EditProductSG.description)
        await callback.message.answer(
            "📝 Введите новое описание (или '-' чтобы очистить):",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
    elif field == "active":
        await state.set_state(EditProductSG.active)
        await callback.message.answer(
            "⚙️ Активировать товар? Ответьте «да» или «нет».",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
    elif field == "photos":
        await state.set_state(EditProductSG.photos)
        await state.update_data(_photos=[])
        await callback.message.answer(
            "🖼 Пришлите новые фото (можно несколько подряд). Когда закончите — отправьте <b>«готово»</b>.\n"
            "Внимание: набор фото будет ПОЛНОСТЬЮ заменён.",
            reply_markup=build_edit_back_cancel_kb(include_back=True),
        )
    else:
        await callback.answer("Неизвестное поле", show_alert=True)
        return

    await callback.answer()


# ─────────────────────────── Обработчики ввода значений ─────────────────────────── #

@admin_edit_router.message(AdminOnly(), EditProductSG.title)
async def edit_set_title(message: Message, state: FSMContext) -> None:
    """Установить новое название товара."""
    new_title = (message.text or "").strip()
    if not new_title:
        await message.answer("Пустое значение. Введите название ещё раз:",
                             reply_markup=build_edit_back_cancel_kb(include_back=True))
        return

    data = await state.get_data()
    pid = int(data["product_id"])
    async with AsyncSessionFactory() as session:
        await ProductRepo.update_fields(session, product_id=pid, title=new_title)

    await _show_product_menu(message, product_id=pid, state=state)


@admin_edit_router.message(AdminOnly(), EditProductSG.price)
async def edit_set_price(message: Message, state: FSMContext) -> None:
    """Установить новую цену товара (Decimal)."""
    raw = (message.text or "").replace(",", ".").strip()
    try:
        price = Decimal(raw)
        if price < 0:
            raise InvalidOperation
    except Exception:
        await message.answer("Некорректная цена. Пример: 1999.99",
                             reply_markup=build_edit_back_cancel_kb(include_back=True))
        return

    data = await state.get_data()
    pid = int(data["product_id"])
    async with AsyncSessionFactory() as session:
        await ProductRepo.update_fields(session, product_id=pid, price=price)

    await _show_product_menu(message, product_id=pid, state=state)


@admin_edit_router.message(AdminOnly(), EditProductSG.category_id)
async def edit_set_category(message: Message, state: FSMContext) -> None:
    """Установить категорию по ID (или убрать, если 0)."""
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("ID категории должен быть числом. Введите снова:",
                             reply_markup=build_edit_back_cancel_kb(include_back=True))
        return
    cid = int(raw)
    if cid != 0:
        async with AsyncSessionFactory() as session:
            if not await CategoryRepo.get(session, cid):
                await message.answer("Категория не найдена. Введите другой ID или 0:",
                                     reply_markup=build_edit_back_cancel_kb(include_back=True))
                return

    data = await state.get_data()
    pid = int(data["product_id"])
    async with AsyncSessionFactory() as session:
        await ProductRepo.update_fields(session, product_id=pid, category_id=(None if cid == 0 else cid))

    await _show_product_menu(message, product_id=pid, state=state)


@admin_edit_router.message(AdminOnly(), EditProductSG.description)
async def edit_set_description(message: Message, state: FSMContext) -> None:
    """Установить новое описание (или очистить по '-')."""
    desc = None if (message.text or "").strip() == "-" else (message.text or "").strip()

    data = await state.get_data()
    pid = int(data["product_id"])
    async with AsyncSessionFactory() as session:
        await ProductRepo.update_fields(session, product_id=pid, description=desc)

    await _show_product_menu(message, product_id=pid, state=state)


@admin_edit_router.message(AdminOnly(), EditProductSG.active)
async def edit_set_active(message: Message, state: FSMContext) -> None:
    """Изменить активность товара (да/нет)."""
    txt = (message.text or "").strip().lower()
    is_active = txt in {"да", "yes", "y", "true", "1", "ага", "включить"}
    data = await state.get_data()
    pid = int(data["product_id"])
    async with AsyncSessionFactory() as session:
        await ProductRepo.update_fields(session, product_id=pid, is_active=is_active)

    await _show_product_menu(message, product_id=pid, state=state)


# ─────────────────────────── Полная замена фото ─────────────────────────── #

@admin_edit_router.message(AdminOnly(), EditProductSG.photos, F.text)
async def edit_photos_text_control(message: Message, state: FSMContext) -> None:
    """
    Управляющие ответы на шаге фото:
    - 'готово' → применить замену
    - любое другое текстовое — подсказка
    """
    txt = (message.text or "").strip().lower()
    if txt in {"готово", "done", "end", "finish"}:
        data = await state.get_data()
        files: List[str] = list(data.get("_photos", []))
        pid = int(data["product_id"])
        async with AsyncSessionFactory() as session:
            await session.begin()
            await ProductRepo.replace_images(session, product_id=pid, telegram_file_ids=files)
            await session.commit()
        await state.update_data(_photos=[])
        await _show_product_menu(message, product_id=pid, state=state)
        return

    await message.answer("Пришлите фото или «готово» для применения.",
                         reply_markup=build_edit_back_cancel_kb(include_back=True))


@admin_edit_router.message(AdminOnly(), EditProductSG.photos, F.content_type == ContentType.PHOTO)
async def edit_photos_collect(message: Message, state: FSMContext) -> None:
    """Копим новые фотографии для замены набора изображений."""
    if not message.photo:
        await message.answer("Не удалось получить фото. Пришлите ещё раз.",
                             reply_markup=build_edit_back_cancel_kb(include_back=True))
        return
    file_id = message.photo[-1].file_id
    data = await state.get_data()
    photos: List[str] = list(data.get("_photos", []))
    photos.append(file_id)
    await state.update_data(_photos=photos)
    await message.answer(f"Фото принято ✅ (всего: {len(photos)}). Пришлите ещё или «готово».")
