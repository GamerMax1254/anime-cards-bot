# admin.py
"""
Админ-панель — работает ТОЛЬКО для ADMIN_ID.
FSM-состояния для пошагового создания/редактирования карточек.
"""

from aiogram import Router, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, Message
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_ID
from database import (
    get_session, Character, Anime, User, UserCard,
    AdminLog, RARITY_INFO
)

admin_router = Router()


# ============================================
# ФИЛЬТР — ТОЛЬКО АДМИН
# ============================================
def admin_only(func):
    """Декоратор: пропускает только ADMIN_ID"""
    async def wrapper(event, *args, **kwargs):
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id != ADMIN_ID:
            return  # Молча игнорируем

        return await func(event, *args, **kwargs)
    return wrapper


# ============================================
# FSM СОСТОЯНИЯ
# ============================================
class CreateCard(StatesGroup):
    anime_title = State()
    name_en = State()
    name_ru = State()
    name_jp = State()
    rarity = State()
    image_url = State()
    description = State()
    stats = State()
    confirm = State()


class EditCard(StatesGroup):
    select_card = State()
    choose_field = State()
    new_value = State()


class GiveCard(StatesGroup):
    select_user = State()
    select_card = State()
    confirm = State()


class GiveCoins(StatesGroup):
    select_user = State()
    amount = State()
    confirm = State()


# ============================================
# АДМИН МЕНЮ
# ============================================
@admin_router.message(Command("admin"))
@admin_only
async def admin_menu(message: Message):
    """Главное меню админки"""
    db = get_session()

    total_chars = db.query(Character).count()
    total_users = db.query(User).count()
    total_anime = db.query(Anime).count()

    # Статистика по редкостям
    rarity_stats = []
    for rarity, info in RARITY_INFO.items():
        count = db.query(Character).filter(Character.rarity == rarity).count()
        if count > 0:
            rarity_stats.append(f"  {info['emoji']} {info['name']}: {count}")

    stats_text = "\n".join(rarity_stats) if rarity_stats else "  Пусто"

    db.close()

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Создать карточку", callback_data="adm_create"))
    kb.row(InlineKeyboardButton(text="✏️ Редактировать карточку", callback_data="adm_edit"))
    kb.row(InlineKeyboardButton(text="📋 Список карточек", callback_data="adm_list"))
    kb.row(
        InlineKeyboardButton(text="🎴 Выдать карточку", callback_data="adm_give_card"),
        InlineKeyboardButton(text="💰 Выдать монеты", callback_data="adm_give_coins"),
    )
    kb.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="adm_users"))
    kb.row(InlineKeyboardButton(text="📊 Аниме-тайтлы", callback_data="adm_anime_list"))
    kb.row(InlineKeyboardButton(text="🗑 Удалить карточку", callback_data="adm_delete"))

    await message.answer(
        f"👑 **АДМИН-ПАНЕЛЬ**\n\n"
        f"📊 **Статистика:**\n"
        f"  🎴 Карточек: {total_chars}\n"
        f"  📺 Аниме: {total_anime}\n"
        f"  👥 Игроков: {total_users}\n\n"
        f"📈 **По редкостям:**\n{stats_text}",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )


# ============================================
# СОЗДАНИЕ КАРТОЧКИ — пошагово
# ============================================
@admin_router.callback_query(F.data == "adm_create")
@admin_only
async def create_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(CreateCard.anime_title)

    # Показываем существующие аниме для удобства
    db = get_session()
    anime_list = db.query(Anime).order_by(Anime.title_en).all()
    db.close()

    kb = InlineKeyboardBuilder()
    for anime in anime_list[:20]:  # Максимум 20
        display = anime.title_ru or anime.title_en
        kb.row(InlineKeyboardButton(
            text=f"📺 {display}",
            callback_data=f"adm_anime_{anime.id}"
        ))
    kb.row(InlineKeyboardButton(text="🆕 Новое аниме", callback_data="adm_anime_new"))
    kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="adm_cancel"))

    await callback.message.edit_text(
        "➕ **Создание карточки — Шаг 1/8**\n\n"
        "Выбери аниме или создай новое:",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )


@admin_router.callback_query(F.data.startswith("adm_anime_"), CreateCard.anime_title)
@admin_only
async def create_select_anime(callback: CallbackQuery, state: FSMContext):
    if callback.data == "adm_anime_new":
        await callback.message.edit_text(
            "📺 **Новое аниме**\n\n"
            "Отправь название (англ).\n"
            "Формат: `English Title`\n\n"
            "Или с русским: `English Title | Русское название`",
            parse_mode="Markdown",
        )
        await state.set_state(CreateCard.anime_title)
        await state.update_data(anime_id=None, anime_new=True)
        return

    anime_id = int(callback.data.replace("adm_anime_", ""))
    db = get_session()
    anime = db.query(Anime).get(anime_id)

    await state.update_data(
        anime_id=anime_id,
        anime_title=anime.title_en,
        anime_new=False,
    )
    db.close()

    await callback.message.edit_text(
        f"✅ Аниме: **{anime.title_ru or anime.title_en}**\n\n"
        f"**Шаг 2/8** — Отправь **английское имя** персонажа:",
        parse_mode="Markdown",
    )
    await state.set_state(CreateCard.name_en)


@admin_router.message(CreateCard.anime_title)
@admin_only
async def create_anime_new(message: Message, state: FSMContext):
    """Создание нового аниме"""
    text = message.text.strip()
    parts = text.split("|")
    title_en = parts[0].strip()
    title_ru = parts[1].strip() if len(parts) > 1 else None

    db = get_session()
    # Проверяем, нет ли уже
    existing = db.query(Anime).filter(Anime.title_en == title_en).first()
    if existing:
        await state.update_data(anime_id=existing.id, anime_title=title_en, anime_new=False)
        anime_display = existing.title_ru or existing.title_en
    else:
        anime = Anime(title_en=title_en, title_ru=title_ru)
        db.add(anime)
        db.commit()
        await state.update_data(anime_id=anime.id, anime_title=title_en, anime_new=False)
        anime_display = title_ru or title_en
    db.close()

    await message.answer(
        f"✅ Аниме: **{anime_display}**\n\n"
        f"**Шаг 2/8** — Отправь **английское имя** персонажа:",
        parse_mode="Markdown",
    )
    await state.set_state(CreateCard.name_en)


@admin_router.message(CreateCard.name_en)
@admin_only
async def create_name_en(message: Message, state: FSMContext):
    await state.update_data(name_en=message.text.strip())
    await message.answer(
        "**Шаг 3/8** — **Русское имя** персонажа:\n\n"
        "Или отправь `-` чтобы пропустить.",
        parse_mode="Markdown",
    )
    await state.set_state(CreateCard.name_ru)


@admin_router.message(CreateCard.name_ru)
@admin_only
async def create_name_ru(message: Message, state: FSMContext):
    value = message.text.strip()
    await state.update_data(name_ru=value if value != "-" else None)

    await message.answer(
        "**Шаг 4/8** — **Японское имя** (кана/кандзи):\n\n"
        "Или `-` чтобы пропустить.",
        parse_mode="Markdown",
    )
    await state.set_state(CreateCard.name_jp)


@admin_router.message(CreateCard.name_jp)
@admin_only
async def create_name_jp(message: Message, state: FSMContext):
    value = message.text.strip()
    await state.update_data(name_jp=value if value != "-" else "")

    # Выбор редкости
    kb = InlineKeyboardBuilder()
    for rarity, info in RARITY_INFO.items():
        kb.row(InlineKeyboardButton(
            text=f"{info['emoji']} {info['name']} ({info['stars']}⭐)",
            callback_data=f"adm_rarity_{rarity}",
        ))

    await message.answer(
        "**Шаг 5/8** — Выбери **редкость**:",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await state.set_state(CreateCard.rarity)


@admin_router.callback_query(F.data.startswith("adm_rarity_"), CreateCard.rarity)
@admin_only
async def create_rarity(callback: CallbackQuery, state: FSMContext):
    rarity = callback.data.replace("adm_rarity_", "")
    info = RARITY_INFO[rarity]

    await state.update_data(rarity=rarity)

    await callback.message.edit_text(
        f"✅ Редкость: {info['emoji']} **{info['name']}**\n\n"
        f"**Шаг 6/8** — Отправь **картинку** (URL) или **фото**.\n\n"
        f"Или `-` чтобы пропустить.",
        parse_mode="Markdown",
    )
    await state.set_state(CreateCard.image_url)


@admin_router.message(CreateCard.image_url)
@admin_only
async def create_image(message: Message, state: FSMContext):
    image_url = None

    if message.photo:
        # Берём самое большое фото, получаем file_id
        # В реальности нужно будет скачать и захостить
        photo = message.photo[-1]
        image_url = f"tg://photo/{photo.file_id}"
    elif message.text and message.text.strip() != "-":
        image_url = message.text.strip()

    await state.update_data(image_url=image_url)

    await message.answer(
        "**Шаг 7/8** — **Описание** персонажа:\n\n"
        "Или `-` чтобы пропустить.",
        parse_mode="Markdown",
    )
    await state.set_state(CreateCard.description)


@admin_router.message(CreateCard.description)
@admin_only
async def create_description(message: Message, state: FSMContext):
    value = message.text.strip()
    await state.update_data(description=value if value != "-" else None)

    await message.answer(
        "**Шаг 8/8** — **Статы** (power, defense, speed):\n\n"
        "Формат: `85 70 90`\n\n"
        "Или `-` для стандартных (50 50 50).",
        parse_mode="Markdown",
    )
    await state.set_state(CreateCard.stats)


@admin_router.message(CreateCard.stats)
@admin_only
async def create_stats(message: Message, state: FSMContext):
    text = message.text.strip()

    if text == "-":
        power, defense, speed = 50, 50, 50
    else:
        try:
            parts = text.split()
            power = int(parts[0])
            defense = int(parts[1]) if len(parts) > 1 else 50
            speed = int(parts[2]) if len(parts) > 2 else 50
        except (ValueError, IndexError):
            await message.answer("❌ Неверный формат. Попробуй: `85 70 90`", parse_mode="Markdown")
            return

    await state.update_data(power=power, defense=defense, speed=speed)

    # Превью
    data = await state.get_data()
    rarity_info = RARITY_INFO[data["rarity"]]
    stars = "⭐" * rarity_info["stars"]

    preview = (
        f"🔍 **ПРЕВЬЮ КАРТОЧКИ:**\n\n"
        f"{rarity_info['emoji']} {rarity_info['name']} {stars}\n"
        f"🇬🇧 {data['name_en']}\n"
        f"🇷🇺 {data.get('name_ru') or '—'}\n"
        f"🇯🇵 {data.get('name_jp') or '—'}\n"
        f"📺 {data.get('anime_title', '?')}\n"
        f"⚔️ ATK: {power} | 🛡 DEF: {defense} | 💨 SPD: {speed}\n"
        f"📝 {data.get('description') or '—'}\n"
        f"🖼 {'Есть' if data.get('image_url') else 'Нет'}\n"
    )

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Создать", callback_data="adm_confirm_create"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="adm_cancel"),
    )

    await message.answer(preview, reply_markup=kb.as_markup(), parse_mode="Markdown")
    await state.set_state(CreateCard.confirm)


@admin_router.callback_query(F.data == "adm_confirm_create", CreateCard.confirm)
@admin_only
async def create_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    db = get_session()

    try:
        char = Character(
            name_en=data["name_en"],
            name_ru=data.get("name_ru"),
            name_jp=data.get("name_jp", ""),
            anime_id=data.get("anime_id"),
            rarity=data["rarity"],
            image_url=data.get("image_url"),
            description=data.get("description"),
            power=data.get("power", 50),
            defense=data.get("defense", 50),
            speed=data.get("speed", 50),
        )
        db.add(char)

        # Лог
        db.add(AdminLog(
            action="create_character",
            details=f"Created: {data['name_en']} [{data['rarity']}]",
        ))

        db.commit()

        info = RARITY_INFO[data["rarity"]]
        await callback.message.edit_text(
            f"✅ **Карточка создана!**\n\n"
            f"ID: `{char.id}`\n"
            f"{info['emoji']} **{char.display_name}** — {info['name']}\n"
            f"📺 {char.anime_title}",
            parse_mode="Markdown",
        )
    except Exception as e:
        db.rollback()
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    finally:
        db.close()

    await state.clear()


# ============================================
# ОТМЕНА
# ============================================
@admin_router.callback_query(F.data == "adm_cancel")
@admin_only
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Отменено.")


# ============================================
# СПИСОК КАРТОЧЕК
# ============================================
@admin_router.callback_query(F.data == "adm_list")
@admin_only
async def list_cards(callback: CallbackQuery):
    await _show_cards_list(callback.message, page=1, edit=True)


@admin_router.callback_query(F.data.startswith("adm_list_page_"))
@admin_only
async def list_cards_page(callback: CallbackQuery):
    page = int(callback.data.replace("adm_list_page_", ""))
    await _show_cards_list(callback.message, page=page, edit=True)


async def _show_cards_list(message: Message, page: int = 1, edit: bool = False):
    db = get_session()
    per_page = 15
    total = db.query(Character).count()
    total_pages = max(1, (total + per_page - 1) // per_page)

    chars = (
        db.query(Character)
        .order_by(Character.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    db.close()

    if not chars:
        text = "📋 Карточек пока нет."
    else:
        lines = []
        for c in chars:
            info = c.rarity_info
            active = "✅" if c.is_active else "🚫"
            lines.append(
                f"`{c.id:>4}` {info['emoji']} **{c.display_name}** — {c.anime_title} {active}"
            )
        text = f"📋 **Карточки** (стр. {page}/{total_pages}, всего {total}):\n\n" + "\n".join(lines)

    kb = InlineKeyboardBuilder()
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"adm_list_page_{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"adm_list_page_{page + 1}"))
    kb.row(*nav_buttons)
    kb.row(InlineKeyboardButton(text="🔙 Меню", callback_data="adm_back_menu"))

    if edit:
        await message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=kb.as_markup(), parse_mode="Markdown")


@admin_router.callback_query(F.data == "adm_back_menu")
@admin_only
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    # Удаляем старое сообщение и вызываем меню
    await callback.message.delete()
    await admin_menu(callback.message)


# ============================================
# РЕДАКТИРОВАНИЕ КАРТОЧКИ
# ============================================
@admin_router.callback_query(F.data == "adm_edit")
@admin_only
async def edit_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "✏️ **Редактирование**\n\n"
        "Отправь **ID карточки** (число).\n"
        "Посмотреть ID можно в 📋 Список.",
        parse_mode="Markdown",
    )
    await state.set_state(EditCard.select_card)


@admin_router.message(EditCard.select_card)
@admin_only
async def edit_select(message: Message, state: FSMContext):
    try:
        card_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Отправь число — ID карточки.")
        return

    db = get_session()
    char = db.query(Character).get(card_id)
    db.close()

    if not char:
        await message.answer(f"❌ Карточка #{card_id} не найдена.")
        return

    await state.update_data(card_id=card_id)
    info = char.rarity_info

    kb = InlineKeyboardBuilder()
    fields = [
        ("name_en", f"🇬🇧 Англ. имя: {char.name_en}"),
        ("name_ru", f"🇷🇺 Рус. имя: {char.name_ru or '—'}"),
        ("name_jp", f"🇯🇵 Яп. имя: {char.name_jp or '—'}"),
        ("rarity", f"{info['emoji']} Редкость: {info['name']}"),
        ("image_url", f"🖼 Картинка: {'Есть' if char.image_url else 'Нет'}"),
        ("description", f"📝 Описание: {'Есть' if char.description else 'Нет'}"),
        ("power", f"⚔️ ATK: {char.power}"),
        ("defense", f"🛡 DEF: {char.defense}"),
        ("speed", f"💨 SPD: {char.speed}"),
        ("is_active", f"{'✅ Активна' if char.is_active else '🚫 Отключена'}"),
    ]

    for field_key, label in fields:
        kb.row(InlineKeyboardButton(
            text=label,
            callback_data=f"adm_editf_{field_key}",
        ))
    kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="adm_cancel"))

    await message.answer(
        f"✏️ **Редактирование: {char.display_name}** (#{card_id})\n\n"
        f"Выбери поле для изменения:",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await state.set_state(EditCard.choose_field)


@admin_router.callback_query(F.data.startswith("adm_editf_"), EditCard.choose_field)
@admin_only
async def edit_choose_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.replace("adm_editf_", "")
    await state.update_data(edit_field=field)

    # Для is_active — сразу переключаем
    if field == "is_active":
        data = await state.get_data()
        db = get_session()
        char = db.query(Character).get(data["card_id"])
        char.is_active = not char.is_active
        db.commit()
        status = "✅ Активирована" if char.is_active else "🚫 Отключена"
        db.close()
        await callback.message.edit_text(f"{status} карточка #{data['card_id']}")
        await state.clear()
        return

    # Для rarity — показываем кнопки
    if field == "rarity":
        kb = InlineKeyboardBuilder()
        for rarity, info in RARITY_INFO.items():
            kb.row(InlineKeyboardButton(
                text=f"{info['emoji']} {info['name']}",
                callback_data=f"adm_setrarity_{rarity}",
            ))
        await callback.message.edit_text(
            "Выбери новую редкость:",
            reply_markup=kb.as_markup(),
        )
        await state.set_state(EditCard.new_value)
        return

    await callback.message.edit_text(
        f"✏️ Отправь новое значение для **{field}**:\n\n"
        f"Или `-` для сброса.",
        parse_mode="Markdown",
    )
    await state.set_state(EditCard.new_value)


@admin_router.callback_query(F.data.startswith("adm_setrarity_"), EditCard.new_value)
@admin_only
async def edit_set_rarity(callback: CallbackQuery, state: FSMContext):
    rarity = callback.data.replace("adm_setrarity_", "")
    data = await state.get_data()

    db = get_session()
    char = db.query(Character).get(data["card_id"])
    char.rarity = rarity
    db.add(AdminLog(action="edit_character", details=f"#{data['card_id']} rarity -> {rarity}"))
    db.commit()

    info = RARITY_INFO[rarity]
    await callback.message.edit_text(
        f"✅ Редкость изменена на {info['emoji']} **{info['name']}**",
        parse_mode="Markdown",
    )
    db.close()
    await state.clear()


@admin_router.message(EditCard.new_value)
@admin_only
async def edit_apply(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data["edit_field"]
    value = message.text.strip()

    db = get_session()
    char = db.query(Character).get(data["card_id"])

    if value == "-":
        value = None

    # Применяем изменение
    try:
        if field in ("power", "defense", "speed"):
            value = int(value) if value else 50
        setattr(char, field, value)

        db.add(AdminLog(
            action="edit_character",
            details=f"#{data['card_id']} {field} -> {value}",
        ))
        db.commit()

        await message.answer(f"✅ **{field}** обновлено для #{data['card_id']}!", parse_mode="Markdown")
    except Exception as e:
        db.rollback()
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        db.close()
        await state.clear()


# ============================================
# УДАЛЕНИЕ КАРТОЧКИ
# ============================================
@admin_router.callback_query(F.data == "adm_delete")
@admin_only
async def delete_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🗑 **Удаление карточки**\n\n"
        "Отправь ID карточки для удаления.\n"
        "⚠️ Также удалится из коллекций всех игроков!",
        parse_mode="Markdown",
    )
    await state.set_state(EditCard.select_card)
    await state.update_data(delete_mode=True)


# ============================================
# ВЫДАТЬ КАРТОЧКУ ИГРОКУ
# ============================================
@admin_router.callback_query(F.data == "adm_give_card")
@admin_only
async def give_card_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🎴 **Выдать карточку**\n\n"
        "Отправь **Telegram ID** пользователя\n"
        "или **@username**:",
        parse_mode="Markdown",
    )
    await state.set_state(GiveCard.select_user)


@admin_router.message(GiveCard.select_user)
@admin_only
async def give_card_user(message: Message, state: FSMContext):
    text = message.text.strip()
    db = get_session()

    if text.startswith("@"):
        user = db.query(User).filter(User.username == text[1:]).first()
    else:
        try:
            tid = int(text)
            user = db.query(User).filter(User.telegram_id == tid).first()
        except ValueError:
            await message.answer("❌ Неверный формат. Отправь ID или @username.")
            db.close()
            return

    if not user:
        await message.answer("❌ Пользователь не найден. Он должен сначала написать /start боту.")
        db.close()
        return

    await state.update_data(target_user_id=user.telegram_id, target_name=user.first_name or user.username)
    db.close()

    await message.answer(
        f"👤 Пользователь: **{user.first_name or user.username}** (`{user.telegram_id}`)\n\n"
        f"Теперь отправь **ID карточки** для выдачи:",
        parse_mode="Markdown",
    )
    await state.set_state(GiveCard.select_card)


@admin_router.message(GiveCard.select_card)
@admin_only
async def give_card_select(message: Message, state: FSMContext):
    try:
        card_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Отправь число — ID карточки.")
        return

    db = get_session()
    char = db.query(Character).get(card_id)
    db.close()

    if not char:
        await message.answer(f"❌ Карточка #{card_id} не найдена.")
        return

    data = await state.get_data()
    info = char.rarity_info

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Выдать", callback_data="adm_confirm_give_card"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="adm_cancel"),
    )

    await state.update_data(give_card_id=card_id)
    await message.answer(
        f"🎴 **Подтверждение выдачи:**\n\n"
        f"Карточка: {info['emoji']} **{char.display_name}** — {info['name']}\n"
        f"Кому: **{data['target_name']}** (`{data['target_user_id']}`)",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await state.set_state(GiveCard.confirm)


@admin_router.callback_query(F.data == "adm_confirm_give_card", GiveCard.confirm)
@admin_only
async def give_card_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    db = get_session()

    try:
        # Проверяем, есть ли уже
        existing = db.query(UserCard).filter(
            UserCard.user_id == data["target_user_id"],
            UserCard.character_id == data["give_card_id"],
        ).first()

        if existing:
            existing.count += 1
        else:
            db.add(UserCard(
                user_id=data["target_user_id"],
                character_id=data["give_card_id"],
            ))

        db.add(AdminLog(
            action="give_card",
            details=f"Card #{data['give_card_id']} -> User {data['target_user_id']}",
            target_user_id=data["target_user_id"],
        ))

        db.commit()
        char = db.query(Character).get(data["give_card_id"])
        await callback.message.edit_text(
            f"✅ **Выдана карточка:**\n"
            f"{char.rarity_info['emoji']} **{char.display_name}** → {data['target_name']}",
            parse_mode="Markdown",
        )
    except Exception as e:
        db.rollback()
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    finally:
        db.close()
        await state.clear()


# ============================================
# ВЫДАТЬ МОНЕТЫ
# ============================================
@admin_router.callback_query(F.data == "adm_give_coins")
@admin_only
async def give_coins_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "💰 **Выдать монеты**\n\n"
        "Отправь **Telegram ID** или **@username**:",
        parse_mode="Markdown",
    )
    await state.set_state(GiveCoins.select_user)


@admin_router.message(GiveCoins.select_user)
@admin_only
async def give_coins_user(message: Message, state: FSMContext):
    text = message.text.strip()
    db = get_session()

    if text.startswith("@"):
        user = db.query(User).filter(User.username == text[1:]).first()
    else:
        try:
            tid = int(text)
            user = db.query(User).filter(User.telegram_id == tid).first()
        except ValueError:
            await message.answer("❌ Неверный формат.")
            db.close()
            return

    if not user:
        await message.answer("❌ Пользователь не найден.")
        db.close()
        return

    await state.update_data(
        target_user_id=user.telegram_id,
        target_name=user.first_name or user.username,
        current_coins=user.coins,
    )
    db.close()

    await message.answer(
        f"👤 **{user.first_name or user.username}** (`{user.telegram_id}`)\n"
        f"💰 Текущий баланс: {user.coins}\n\n"
        f"Сколько монет выдать? (число, можно отрицательное для снятия)",
        parse_mode="Markdown",
    )
    await state.set_state(GiveCoins.amount)


@admin_router.message(GiveCoins.amount)
@admin_only
async def give_coins_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Отправь число.")
        return

    data = await state.get_data()
    await state.update_data(amount=amount)

    new_balance = data["current_coins"] + amount

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="adm_confirm_give_coins"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="adm_cancel"),
    )

    sign = "+" if amount >= 0 else ""
    await message.answer(
        f"💰 **Подтверждение:**\n\n"
        f"👤 {data['target_name']}\n"
        f"💰 {data['current_coins']} → {new_balance} ({sign}{amount})",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await state.set_state(GiveCoins.confirm)


@admin_router.callback_query(F.data == "adm_confirm_give_coins", GiveCoins.confirm)
@admin_only
async def give_coins_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    db = get_session()

    try:
        user = db.query(User).filter(User.telegram_id == data["target_user_id"]).first()
        user.coins += data["amount"]
        if user.coins < 0:
            user.coins = 0

        db.add(AdminLog(
            action="give_coins",
            details=f"{data['amount']} coins -> User {data['target_user_id']} (new: {user.coins})",
            target_user_id=data["target_user_id"],
        ))
        db.commit()

        sign = "+" if data["amount"] >= 0 else ""
        await callback.message.edit_text(
            f"✅ **Монеты выданы:**\n"
            f"👤 {data['target_name']}: {sign}{data['amount']}💰 (баланс: {user.coins}💰)",
            parse_mode="Markdown",
        )
    except Exception as e:
        db.rollback()
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    finally:
        db.close()
        await state.clear()


# ============================================
# СПИСОК ПОЛЬЗОВАТЕЛЕЙ
# ============================================
@admin_router.callback_query(F.data == "adm_users")
@admin_only
async def list_users(callback: CallbackQuery):
    db = get_session()
    users = db.query(User).order_by(User.created_at.desc()).limit(20).all()
    db.close()

    if not users:
        await callback.message.edit_text("👥 Пользователей пока нет.")
        return

    lines = []
    for u in users:
        name = u.first_name or u.username or "?"
        lines.append(
            f"`{u.telegram_id}` — **{name}** | 💰{u.coins} | 🎴{u.total_cards}"
        )

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Меню", callback_data="adm_back_menu"))

    await callback.message.edit_text(
        f"👥 **Пользователи** (последние 20):\n\n" + "\n".join(lines),
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )


# ============================================
# СПИСОК АНИМЕ
# ============================================
@admin_router.callback_query(F.data == "adm_anime_list")
@admin_only
async def list_anime(callback: CallbackQuery):
    db = get_session()
    anime_list = db.query(Anime).order_by(Anime.title_en).all()
    db.close()

    if not anime_list:
        await callback.message.edit_text("📊 Аниме-тайтлов пока нет.")
        return

    lines = []
    for a in anime_list:
        char_count = len(a.characters) if a.characters else 0
        display = a.title_ru or a.title_en
        lines.append(f"`{a.id:>3}` 📺 **{display}** — {char_count} персонажей")

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Меню", callback_data="adm_back_menu"))

    await callback.message.edit_text(
        "📊 **Аниме-тайтлы:**\n\n" + "\n".join(lines),
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )