# bot.py
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, WebAppInfo, MenuButtonWebApp, BotCommand
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, WEBAPP_URL, ADMIN_ID
from database import get_session
from gacha import GachaService

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Подключаем админку только если файл есть
try:
    from admin import admin_router
    dp.include_router(admin_router)
    print("✅ Админ-роутер подключён")
except ImportError as e:
    print(f"⚠️ Админка не загружена: {e}")
except Exception as e:
    print(f"⚠️ Ошибка админки: {e}")


@dp.callback_query(F.data.startswith("coll_page_"))
async def coll_page_callback(callback: types.CallbackQuery):
    """Пагинация коллекции"""
    try:
        page = int(callback.data.split("_")[-1])
    except:
        await callback.answer("❌ Ошибка страницы")
        return

    await show_collection_page(callback, page=page, edit=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("view_card_"))
async def view_card_callback(callback: types.CallbackQuery):
    """Показать детали карточки через inline-кнопку"""
    try:
        card_id = int(callback.data.split("_")[-1])
    except:
        await callback.answer("❌ Ошибка ID")
        return

    # Получаем данные
    db = get_session()
    try:
        from database import Character, User, UserCard

        char = db.query(Character).get(card_id)
        if not char:
            await callback.answer("❌ Карточка не найдена", show_alert=True)
            return

        user_card = db.query(UserCard).filter(
            UserCard.user_id == callback.from_user.id,
            UserCard.character_id == card_id,
        ).first()

        total_users = db.query(User).count()
        owners_count = db.query(UserCard).filter(
            UserCard.character_id == card_id,
        ).distinct(UserCard.user_id).count()
        percentage = round((owners_count / total_users * 100), 2) if total_users > 0 else 0

    finally:
        db.close()

    # Формируем текст
    info = char.rarity_info
    stars = "⭐" * info["stars"]

    text = (
        f"🎴 <b>Информация о персонаже</b>\n\n"
        f"🆔 <b>ID:</b> <code>{char.id}</code>\n"
        f"👤 <b>Имя:</b> {char.display_name}"
    )

    if char.name_en and char.name_en != char.display_name:
        text += f" (<i>{char.name_en}</i>)"

    text += f"\n📺 <b>Тайтл:</b> {char.anime_title}\n"
    text += f"💎 <b>Редкость:</b> {info['emoji']} {info['name']} {stars}\n"
    text += f"⚔️ <b>Статы:</b> ATK {char.power} | DEF {char.defense} | SPD {char.speed}\n"

    if char.description:
        text += f"\n📖 <i>{char.description}</i>\n"

    text += "\n━━━━━━━━━━━━━━━━━━\n"

    if user_card:
        fav = " ⭐" if user_card.is_favorite else ""
        text += f"\n✅ <b>Есть у вас:</b> {user_card.count} шт.{fav}"
    else:
        text += f"\n❌ <b>У вас нет этой карточки</b>"

    text += f"\n🌍 <b>Владельцев:</b> {owners_count} ({percentage}% игроков)"

    # Кнопки
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="⬅️ Назад к коллекции",
        callback_data="coll_page_1",
    ))

    if callback.message.chat.type == "private":
        add_game_button(kb, True, text="🎴 Открыть в приложении")

    # Пытаемся отредактировать (если было сообщение с текстом)
    # Или отправляем новое (если было с фото)
    try:
        # Если картинка есть — отправляем новое сообщение
        if char.image_url and char.image_url.startswith(("http://", "https://")):
            await callback.message.answer_photo(
                photo=char.image_url,
                caption=text,
                reply_markup=kb.as_markup(),
                parse_mode="HTML",
            )
        else:
            await callback.message.edit_text(
                text,
                reply_markup=kb.as_markup(),
                parse_mode="HTML",
            )
    except Exception as e:
        # Fallback — просто отправить
        await callback.message.answer(
            text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )

    await callback.answer()


@dp.callback_query(F.data == "noop")
async def noop_callback(callback: types.CallbackQuery):
    """Заглушка для нективных кнопок"""
    await callback.answer()


@dp.callback_query(F.data.startswith("coll_filter_"))
async def coll_filter_callback(callback: types.CallbackQuery):
    """Фильтр коллекции по редкости"""
    rarity = callback.data.replace("coll_filter_", "")
    if rarity == "all":
        rarity = None
    await show_collection_page(callback, page=1, edit=True, rarity=rarity)
    await callback.answer(f"Фильтр: {rarity or 'все'}")


def is_private_chat(message: types.Message) -> bool:
    """Проверка что чат приватный (не группа)"""
    return message.chat.type == "private"



def add_game_button(kb, is_private: bool, text: str = "🎴 Открыть игру"):
    """
    Универсальная кнопка открытия игры.
    В ЛС — WebApp внутри Telegram
    В группе — ссылка в ЛС бота
    """
    if not WEBAPP_URL or not WEBAPP_URL.startswith("https"):
        return

    if is_private:
        kb.row(InlineKeyboardButton(
            text=text,
            web_app=WebAppInfo(url=WEBAPP_URL),
        ))
    else:
        if BOT_USERNAME:
            kb.row(InlineKeyboardButton(
                text=f"{text} (в ЛС)",
                url=f"https://t.me/{BOT_USERNAME}",
            ))
        
BOT_USERNAME = None

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    db = get_session()
    try:
        gacha = GachaService(db)
        gacha.get_or_create_user(
            message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
    finally:
        db.close()

    is_private = is_private_chat(message)
    kb = InlineKeyboardBuilder()

    # Универсальная кнопка игры (сама разберётся ЛС/группа)
    add_game_button(kb, is_private)

    if is_private:
        # Callback-кнопки работают только в ЛС нормально
        kb.row(
            InlineKeyboardButton(text="💰 Забрать (6ч)", callback_data="claim"),
        )
        kb.row(
            InlineKeyboardButton(text="🎰 x1 (300💰)", callback_data="pull1"),
            InlineKeyboardButton(text="🎰 x3 (810💰)", callback_data="pull10"),
        )
        kb.row(InlineKeyboardButton(text="🎴 Коллекция", callback_data="my_collection"))
        kb.row(InlineKeyboardButton(text="💼 Баланс", callback_data="balance"))

        if message.from_user.id == ADMIN_ID:
            kb.row(InlineKeyboardButton(text="👑 Админ-панель", callback_data="admin_menu"))

    await message.answer(
        "🎴 <b>Аниме Карточки</b>\n\n"
        "Собирай карточки любимых персонажей!\n\n"
        "💰 Обычный сбор — каждые 6 часов\n"
        "🎰 Крути гачу и собирай!\n\n"
        + ("Выбери действие 👇" if is_private else "Нажми чтобы играть 👇"),
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )


@dp.message(Command("myid"))
async def cmd_myid(message: types.Message):
    await message.answer(f"Твой Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


@dp.message(Command("бонус", "bonus", "claim"))
async def cmd_claim(message: types.Message):
    """Быстрый сбор монет (каждые 6 часов)"""
    db = get_session()
    try:
        gacha = GachaService(db)
        result = gacha.claim_coins(message.from_user.id)
    finally:
        db.close()

    if result["success"]:
        await message.answer(
            f"💰 <b>+{result['claimed']} монет!</b>\n\n"
            f"💼 Баланс: <b>{result['coins']}</b>\n"
            f"⏰ Следующий сбор через 6 часов",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"⏰ <b>Рано!</b>\n\n"
            f"{result['message']}\n\n"
            f"💰 Баланс: <b>{result['coins']}</b>",
            parse_mode="HTML",
        )


@dp.callback_query(F.data == "claim")
async def claim_callback(callback: types.CallbackQuery):
    db = get_session()
    try:
        gacha = GachaService(db)
        result = gacha.claim_coins(callback.from_user.id)
    finally:
        db.close()
    await callback.answer(result["message"], show_alert=True)


@dp.callback_query(F.data == "pull1")
async def pull1_callback(callback: types.CallbackQuery):
    db = get_session()
    try:
        gacha = GachaService(db)
        result = gacha.single_pull(callback.from_user.id)
    finally:
        db.close()

    if not result["success"]:
        await callback.answer(result["message"], show_alert=True)
        return

    card = result["card"]
    if "error" in card:
        await callback.answer(card["error"], show_alert=True)
        return

    stars = "⭐" * card["stars"]
    new_mark = "🆕 НОВАЯ!" if card["is_new"] else "🔄 Дубликат"

    text = (
        f"🎰 <b>Результат:</b>\n\n"
        f"{card['emoji']} <b>{card['name']}</b>\n"
        f"{stars} {card['rarity_name']}\n"
        f"📺 {card['anime']}\n"
        f"⚔️{card['power']} 🛡{card['defense']} 💨{card['speed']}\n\n"
        f"{new_mark}\n"
        f"💰 Баланс: {result['coins']}"
    )

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🎰 Ещё x1", callback_data="pull1"),
        InlineKeyboardButton(text="🎰 x10", callback_data="pull10"),
    )

    await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "pull10")
async def pull10_callback(callback: types.CallbackQuery):
    db = get_session()
    try:
        gacha = GachaService(db)
        result = gacha.multi_pull(callback.from_user.id)
    finally:
        db.close()

    if not result["success"]:
        await callback.answer(result["message"], show_alert=True)
        return

    text = "🎰 <b>Результат x3:</b>\n\n"
    for card in result["cards"]:
        if "error" in card:
            continue
        new_mark = "🆕" if card["is_new"] else "🔄"
        text += f"{new_mark} {card['emoji']} <b>{card['name']}</b> — {card['rarity_name']}\n"

    text += f"\n✨ Новых: {result['new_count']}/3"
    text += f"\n💰 Баланс: {result['coins']}"

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🎰 Ещё x1", callback_data="pull1"),
        InlineKeyboardButton(text="🎰 Ещё x3", callback_data="pull10"),
    )

    await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "balance")
async def balance_callback(callback: types.CallbackQuery):
    db = get_session()
    try:
        gacha = GachaService(db)
        info = gacha.get_user_info(callback.from_user.id)
    finally:
        db.close()

    await callback.message.answer(
        f"💼 <b>Профиль</b>\n\n"
        f"💰 Монеты: <b>{info['coins']}</b>\n"
        f"🎴 Карточек: <b>{info['total_cards']}</b>\n"
        f"🎰 Круток: <b>{info['total_pulls']}</b>\n"
        f"🎯 Pity: <b>{info['pulls_since_pity']}/90</b>",
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data == "my_collection")
async def collection_callback(callback: types.CallbackQuery):
    db = get_session()
    try:
        gacha = GachaService(db)
        result = gacha.get_collection(callback.from_user.id, page=1, per_page=10)
    finally:
        db.close()

    if not result["cards"]:
        await callback.message.answer("🎴 Коллекция пуста! Начни крутить 🎰")
        await callback.answer()
        return

    text = f"🎴 <b>Коллекция</b> — {result['completion']}%\n\n"
    for card in result["cards"]:
        info = card["rarity_info"]
        stars = "⭐" * info["stars"]
        text += f"{info['emoji']} <b>{card['name']}</b> x{card['count']} {stars}\n"

    text += f"\n📊 {result['total_collected']}/{result['total_characters']}"

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


# ============================================
# КОМАНДЫ ДЛЯ /
# ============================================

@dp.message(Command("помощь", "help"))
async def cmd_help(message: types.Message):
    text = (
        "ℹ️ <b>Команды бота</b>\n\n"

        "🎴 <b>Основные:</b>\n"
        "/start — главное меню\n"
        "/bonus или /бонус — забрать монеты (6ч)\n"
        "/pull или /крутить — крутка x1 (300💰)\n"
        "/pull3 или /крутить3 — крутка x3 (810💰)\n\n"

        "🎴 <b>Коллекция:</b>\n"
        "/collection или /коллекция — мои карточки\n"
        "/card ID или /карта ID — <b>показать карточку</b>\n"
        "/profile или /профиль — статистика\n\n"

        "💡 <b>Другое:</b>\n"
        "/suggest или /предложка — предложить карточку\n"
        "/help или /помощь — этот список\n"
    )

    if message.from_user.id == ADMIN_ID:
        text += "\n👑 <b>Админ:</b>\n/admin — админ-панель\n"

    await message.answer(text, parse_mode="HTML")

@dp.message(Command("бонус", "bonus", "claim"))
async def cmd_claim(message: types.Message):
    """Быстрый сбор монет (каждые 6 часов)"""
    db = get_session()
    try:
        gacha = GachaService(db)
        result = gacha.claim_coins(message.from_user.id)
    finally:
        db.close()

    if result["success"]:
        await message.answer(
            f"💰 <b>+{result['claimed']} монет!</b>\n\n"
            f"💼 Баланс: <b>{result['coins']}</b>\n"
            f"⏰ Следующий сбор через 6 часов",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"⏰ <b>Рано!</b>\n\n"
            f"{result['message']}\n\n"
            f"💰 Баланс: <b>{result['coins']}</b>",
            parse_mode="HTML",
        )


@dp.message(Command("крутить", "pull", "roll"))
async def cmd_pull(message: types.Message):
    db = get_session()
    try:
        gacha = GachaService(db)
        result = gacha.single_pull(message.from_user.id)
    finally:
        db.close()

    if not result["success"]:
        await message.answer(f"❌ {result['message']}", parse_mode="HTML")
        return

    card = result["card"]
    stars = "⭐" * card["stars"]
    new_mark = "🆕 <b>НОВАЯ!</b>" if card["is_new"] else "🔄 Дубликат"

    text = (
        f"🎰 <b>Результат:</b>\n\n"
        f"{card['emoji']} <b>{card['name']}</b>\n"
        f"{stars} {card['rarity_name']}\n"
        f"📺 {card['anime']}\n"
        f"⚔️{card['power']} 🛡{card['defense']} 💨{card['speed']}\n\n"
        f"{new_mark}\n"
    )

    if not card["is_new"]:
        text += f"💰 Компенсация: +{card['duplicate_coins']}💰\n"

    text += f"\n💰 Баланс: {result['coins']}"

    kb = InlineKeyboardBuilder()

    # В ЛС — интерактивные кнопки для повтора
    if is_private_chat(message):
        kb.row(
            InlineKeyboardButton(text="🎰 Ещё x1", callback_data="pull1"),
            InlineKeyboardButton(text="🎰 x3", callback_data="pull10"),
        )

    await message.answer(
        text,
        reply_markup=kb.as_markup() if kb.export() else None,
        parse_mode="HTML",
    )


@dp.message(Command("крутить3", "pull3", "roll3", "multi"))
async def cmd_pull3(message: types.Message):
    """Крутка x3"""
    db = get_session()
    try:
        gacha = GachaService(db)
        result = gacha.multi_pull(message.from_user.id)
    finally:
        db.close()

    if not result["success"]:
        await message.answer(f"❌ {result['message']}", parse_mode="HTML")
        return

    text = "🎰 <b>Результат x3:</b>\n\n"
    for card in result["cards"]:
        if "error" in card:
            continue
        new_mark = "🆕" if card["is_new"] else "🔄"
        text += f"{new_mark} {card['emoji']} <b>{card['name']}</b> — {card['rarity_name']}\n"

    text += f"\n✨ Новых: {result['new_count']}/3"
    text += f"\n💰 Баланс: {result['coins']}"

    await message.answer(text, parse_mode="HTML")


@dp.message(Command("card", "карта", "карточка"))
async def cmd_card(message: types.Message, command: CommandObject = None):
    """Показать подробную информацию о карточке по ID"""

    # Получаем аргументы команды
    if not command or not command.args:
        await message.answer(
            "🎴 <b>Просмотр карточки</b>\n\n"
            "Использование: <code>/card ID</code>\n"
            "Пример: <code>/card 5</code>\n\n"
            "ID карточки можно узнать в коллекции.",
            parse_mode="HTML",
        )
        return

    # Парсим ID
    try:
        card_id = int(command.args.strip())
    except ValueError:
        await message.answer("❌ ID должен быть числом. Пример: <code>/card 5</code>", parse_mode="HTML")
        return

    # Получаем данные из БД
    db = get_session()
    try:
        from database import Character, User, UserCard

        char = db.query(Character).get(card_id)
        if not char:
            await message.answer(f"❌ Карточка #{card_id} не найдена")
            return

        # У текущего пользователя
        user_card = db.query(UserCard).filter(
            UserCard.user_id == message.from_user.id,
            UserCard.character_id == card_id,
        ).first()

        # Статистика
        total_users = db.query(User).count()
        owners_count = db.query(UserCard).filter(
            UserCard.character_id == card_id,
        ).distinct(UserCard.user_id).count()

        percentage = round((owners_count / total_users * 100), 2) if total_users > 0 else 0

    finally:
        db.close()

    # Формируем текст
    info = char.rarity_info
    stars = "⭐" * info["stars"]

    text = (
        f"🎴 <b>Информация о персонаже</b>\n\n"
        f"🆔 <b>ID:</b> <code>{char.id}</code>\n"
        f"👤 <b>Имя:</b> {char.display_name}"
    )

    if char.name_en and char.name_en != char.display_name:
        text += f" (<i>{char.name_en}</i>)"

    text += f"\n📺 <b>Тайтл:</b> {char.anime_title}\n"
    text += f"💎 <b>Редкость:</b> {info['emoji']} {info['name']} {stars}\n"
    text += f"⚔️ <b>Статы:</b> ATK {char.power} | DEF {char.defense} | SPD {char.speed}\n"

    if char.description:
        text += f"\n📖 <i>{char.description}</i>\n"

    text += "\n━━━━━━━━━━━━━━━━━━\n\n"

    # У вас
    if user_card:
        fav = " ⭐" if user_card.is_favorite else ""
        text += f"✅ <b>Есть у вас:</b> {user_card.count} шт.{fav}\n"
    else:
        text += f"❌ <b>У вас нет этой карточки</b>\n"

    text += f"🌍 <b>Владельцев:</b> {owners_count} ({percentage}% игроков)\n"

    # Кнопки
    kb = InlineKeyboardBuilder()

    # В ЛС — кнопка открыть в приложении
    if is_private_chat(message):
        add_game_button(kb, True, text="🎴 Открыть в приложении")

    # Отправка с картинкой если есть
    if char.image_url and char.image_url.startswith(("http://", "https://")):
        try:
            await message.answer_photo(
                photo=char.image_url,
                caption=text,
                reply_markup=kb.as_markup() if kb.buttons else None,
                parse_mode="HTML",
            )
            return
        except Exception as e:
            # Если картинка не загрузилась — отправляем без неё
            print(f"⚠️ Не удалось отправить картинку: {e}")

    # Без картинки
    await message.answer(
        text,
        reply_markup=kb.as_markup() if kb.buttons else None,
        parse_mode="HTML",
    )


@dp.message(Command("коллекция", "collection", "cards"))
async def cmd_collection(message: types.Message):
    """Показать коллекцию с группировкой"""
    await show_collection_page(message, page=1)


async def show_collection_page(
    message_or_callback,
    page: int = 1,
    edit: bool = False,
    rarity_filter: str = None,
    sort_by: str = "rarity_desc",
):
    """
    Универсальная функция показа страницы коллекции.
    """
    from sqlalchemy.orm import joinedload
    from sqlalchemy import case

    # Получаем user_id
    if isinstance(message_or_callback, types.CallbackQuery):
        user_id = message_or_callback.from_user.id
        user_name = message_or_callback.from_user.first_name or "Игрок"
        chat_type = message_or_callback.message.chat.type
    else:
        user_id = message_or_callback.from_user.id
        user_name = message_or_callback.from_user.first_name or "Игрок"
        chat_type = message_or_callback.chat.type

    is_pv = chat_type == "private"

    # Получаем данные и СРАЗУ конвертируем в dict внутри сессии
    db = get_session()
    try:
        from database import Character, UserCard, User, Anime, RARITY_INFO

        # joinedload — загружаем character сразу вместе с UserCard
        query = db.query(UserCard).join(Character).options(
            joinedload(UserCard.character).joinedload(Character.anime)
        ).filter(UserCard.user_id == user_id)

        # Фильтр по редкости
        if rarity_filter and rarity_filter != "all":
            query = query.filter(Character.rarity == rarity_filter)

        # Сортировка
        if sort_by == "rarity_desc":
            rarity_order = case(
                {r: info["order"] for r, info in RARITY_INFO.items()},
                value=Character.rarity,
                else_=0,
            )
            query = query.order_by(rarity_order.desc(), Character.anime_id, Character.name_en)
        elif sort_by == "rarity_asc":
            rarity_order = case(
                {r: info["order"] for r, info in RARITY_INFO.items()},
                value=Character.rarity,
                else_=0,
            )
            query = query.order_by(rarity_order.asc(), Character.anime_id, Character.name_en)
        elif sort_by == "name":
            query = query.order_by(Character.name_en)
        elif sort_by == "anime":
            query = query.order_by(Character.anime_id, Character.rarity.desc())
        elif sort_by == "count":
            query = query.order_by(UserCard.count.desc(), Character.rarity.desc())
        else:
            query = query.order_by(Character.name_en)

        # Счётчики
        total_filtered = query.count()
        per_page = 15
        total_pages = max(1, (total_filtered + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))

        # Получаем страницу
        cards_raw = query.offset((page - 1) * per_page).limit(per_page).all()

        # ============ КОНВЕРТИРУЕМ В DICT ВНУТРИ СЕССИИ ============
        cards = []
        for c in cards_raw:
            char = c.character
            cards.append({
                "id": char.id,
                "name": char.display_name,
                "anime": char.anime_title,
                "rarity": char.rarity,
                "rarity_info": char.rarity_info,
                "count": c.count,
                "is_favorite": c.is_favorite,
            })

        # Общая статистика
        total_chars = db.query(Character).filter(Character.is_active == True).count()
        all_user_cards = db.query(UserCard).filter(UserCard.user_id == user_id).count()
        total_animes = db.query(Anime).count()
        user_animes = db.query(Character.anime_id).join(UserCard).filter(
            UserCard.user_id == user_id,
        ).distinct().count()

    finally:
        db.close()

    # Дальше работаем ТОЛЬКО с dict — сессия уже не нужна

    # ============ ПРОВЕРКА ПУСТОЙ ============
    if not cards:
        if rarity_filter and rarity_filter != "all":
            filter_name = RARITY_INFO.get(rarity_filter, {}).get("name", rarity_filter)
            text = f"🎴 <b>Нет карточек редкости «{filter_name}»</b>\n\nПопробуй убрать фильтр."
        else:
            text = "🎴 <b>Коллекция пуста!</b>\n\nНачни крутить: /pull"

        kb = InlineKeyboardBuilder()
        if rarity_filter and rarity_filter != "all":
            kb.row(InlineKeyboardButton(
                text="🔄 Показать все",
                callback_data="coll_filter_all_1",
            ))

        reply_markup = kb.as_markup() if kb.buttons else None

        if edit and isinstance(message_or_callback, types.CallbackQuery):
            try:
                await message_or_callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
            except:
                pass
        else:
            answer_method = (
                message_or_callback.answer
                if hasattr(message_or_callback, 'answer') and not isinstance(message_or_callback, types.CallbackQuery)
                else message_or_callback.message.answer
            )
            await answer_method(text, reply_markup=reply_markup, parse_mode="HTML")
        return

    # ============ ФОРМИРУЕМ ТЕКСТ ============
    text = f"🎴 <b>{user_name}, ваша коллекция</b> "
    text += f"<i>(стр. {page}/{total_pages})</i>\n"

    # Инфа о фильтрах
    filter_info = []
    if rarity_filter and rarity_filter != "all":
        info = RARITY_INFO.get(rarity_filter, {})
        filter_info.append(f"{info.get('emoji', '')} {info.get('name', rarity_filter)}")

    sort_names = {
        "rarity_desc": "по редкости ↓",
        "rarity_asc": "по редкости ↑",
        "name": "по имени",
        "anime": "по аниме",
        "count": "по количеству",
    }
    filter_info.append(sort_names.get(sort_by, "по имени"))
    text += f"⚙️ <i>{' • '.join(filter_info)}</i>\n\n"

    # Отображение карточек
    if sort_by in ("rarity_desc", "rarity_asc"):
        # Простой список (для сортировки по редкости)
        for card in cards:
            info = card["rarity_info"]
            fav = "⭐ " if card["is_favorite"] else ""
            count_badge = f" ×{card['count']}" if card["count"] > 1 else ""

            text += (
                f"{info['emoji']} <b>{card['name']}</b>{count_badge} "
                f"{fav}| id: <code>{card['id']}</code>\n"
            )
    else:
        # Группировка по аниме
        grouped = {}
        for card in cards:
            anime = card["anime"]
            if anime not in grouped:
                grouped[anime] = []
            grouped[anime].append(card)

        for anime_name, anime_cards in grouped.items():
            text += f"🌸 <b>{anime_name}:</b>\n"
            for card in anime_cards:
                info = card["rarity_info"]
                fav = "⭐ " if card["is_favorite"] else ""
                count_badge = f" ×{card['count']}" if card["count"] > 1 else ""

                text += (
                    f"  {info['emoji']} <b>{card['name']}</b>{count_badge} "
                    f"{fav}| id: <code>{card['id']}</code>\n"
                )
            text += "\n"

    # Статистика
    percent = round(all_user_cards / max(total_chars, 1) * 100, 1)
    anime_percent = round(user_animes / max(total_animes, 1) * 100, 1)

    text += "━━━━━━━━━━━━━━━━━━\n"
    text += f"📊 Найдено <b>{all_user_cards}</b> из {total_chars} ({percent}%)\n"
    text += f"📺 Тайтлов: <b>{user_animes}</b> из {total_animes} ({anime_percent}%)"

    if rarity_filter and rarity_filter != "all":
        text += f"\n🔍 По фильтру: <b>{total_filtered}</b>"

    # ============ КНОПКИ ============
    kb = InlineKeyboardBuilder()

    # 1) Кнопки быстрого просмотра карточек
    card_buttons = []
    for card in cards:
        card_buttons.append(InlineKeyboardButton(
            text=f"🔍 {card['id']}",
            callback_data=f"view_card_{card['id']}",
        ))

    for i in range(0, len(card_buttons), 4):
        kb.row(*card_buttons[i:i+4])

    # 2) Пагинация
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(
            text="◀️",
            callback_data=f"coll_filter_{rarity_filter or 'all'}_{page-1}",
        ))
    nav_row.append(InlineKeyboardButton(
        text=f"{page}/{total_pages}",
        callback_data="noop",
    ))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="▶️",
            callback_data=f"coll_filter_{rarity_filter or 'all'}_{page+1}",
        ))
    kb.row(*nav_row)

    # 3) Фильтры по редкости
    current_filter = rarity_filter or "all"

    row1 = [
        InlineKeyboardButton(
            text="🔄" + (" ✓" if current_filter == "all" else ""),
            callback_data="coll_filter_all_1",
        ),
    ]

    rarity_order_list = ["secret", "mythical", "legendary", "epic", "rare", "uncommon", "common", "unique"]

    filter_buttons = []
    for rarity_key in rarity_order_list:
        if rarity_key not in RARITY_INFO:
            continue
        info = RARITY_INFO[rarity_key]
        active = "✓" if current_filter == rarity_key else ""
        filter_buttons.append(InlineKeyboardButton(
            text=f"{info['emoji']}{active}",
            callback_data=f"coll_filter_{rarity_key}_1",
        ))

    kb.row(*(row1 + filter_buttons[:4]))
    if len(filter_buttons) > 4:
        kb.row(*filter_buttons[4:8])

    # 4) Сортировка
    sort_options = [
        ("rarity_desc", "💎↓"),
        ("rarity_asc", "💎↑"),
        ("name", "🔤"),
        ("anime", "📺"),
        ("count", "🔢"),
    ]

    sort_buttons = []
    for sort_key, sort_emoji in sort_options:
        active = "✓" if sort_by == sort_key else ""
        sort_buttons.append(InlineKeyboardButton(
            text=f"{sort_emoji}{active}",
            callback_data=f"coll_sort_{sort_key}_{rarity_filter or 'all'}_{page}",
        ))
    kb.row(*sort_buttons)

    # 5) Открыть в приложении (ЛС)
    if is_pv:
        add_game_button(kb, True, text="🎴 Открыть в приложении")

    # ============ ОТПРАВКА ============
    reply_markup = kb.as_markup() if kb.buttons else None

    if edit and isinstance(message_or_callback, types.CallbackQuery):
        try:
            await message_or_callback.message.edit_text(
                text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"⚠️ Edit failed: {e}")
    else:
        answer_method = (
            message_or_callback.answer
            if hasattr(message_or_callback, 'answer') and not isinstance(message_or_callback, types.CallbackQuery)
            else message_or_callback.message.answer
        )
        await answer_method(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )


@dp.message(Command("профиль", "profile", "balance", "me"))
async def cmd_profile(message: types.Message):
    """Профиль игрока"""
    db = get_session()
    try:
        gacha = GachaService(db)
        info = gacha.get_user_info(message.from_user.id)
    finally:
        db.close()

    name = message.from_user.first_name or "Игрок"

    text = (
        f"💼 <b>Профиль {name}</b>\n\n"
        f"💰 Монеты: <b>{info['coins']}</b>\n"
        f"💎 Гемы: <b>{info['gems']}</b>\n"
        f"🎴 Карточек: <b>{info['total_cards']}</b>\n"
        f"🎰 Круток: <b>{info['total_pulls']}</b>\n"
        f"🎯 Pity: <b>{info['pulls_since_pity']}/90</b>\n"
    )

    await message.answer(text, parse_mode="HTML")


@dp.message(Command("предложка", "suggest"))
async def cmd_suggest(message: types.Message):
    kb = InlineKeyboardBuilder()
    add_game_button(kb, is_private_chat(message), text="💡 Открыть форму")

    await message.answer(
        "💡 <b>Предложи персонажа!</b>\n\n"
        "Открой приложение → таб «💡 Предложка»\n"
        "Заполни форму → отправь\n"
        "За одобрение получишь <b>+500 💰</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )


@dp.message(Command("помощь", "help"))
async def cmd_help(message: types.Message):
    """Список всех команд"""
    text = (
        "ℹ️ <b>Команды бота</b>\n\n"
        "🎴 <b>Основные:</b>\n"
        "/start — главное меню\n"
        "/бонус — забрать монеты (раз в 6ч)\n"
        "/крутить — крутка x1 (300💰)\n"
        "/крутить3 — крутка x3 (810💰)\n\n"
        "🎴 <b>Коллекция:</b>\n"
        "/коллекция — мои карточки\n"
        "/профиль — статистика\n\n"
        "💡 <b>Другое:</b>\n"
        "/предложка — предложить новую карточку\n"
        "/помощь — этот список\n"
    )

    if message.from_user.id == ADMIN_ID:
        text += (
            "\n👑 <b>Админ:</b>\n"
            "/admin — админ-панель\n"
        )

    await message.answer(text, parse_mode="HTML")

# ===========

@dp.callback_query(F.data == "admin_menu")
async def admin_btn(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    try:
        from admin import admin_menu
        await admin_menu(callback.message)
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка админки: {e}")

@dp.message(Command("admin"))
async def cmd_admin_link(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    import hashlib
    key = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32]
    admin_url = f"{WEBAPP_URL}/admin?key={key}&uid={ADMIN_ID}"

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🌐 Открыть в браузере", url=admin_url))
    kb.row(InlineKeyboardButton(
        text="📱 Открыть здесь",
        web_app=WebAppInfo(url=admin_url),
    ))

    await message.answer(
        f"👑 <b>Админ-панель</b>\n\n"
        f"🔗 Ссылка (не делись!):\n"
        f"<code>{admin_url}</code>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )

async def notify_suggestion_result(user_id: int, status: str, comment: str = None,
                                    reward: int = 0, char_name: str = None):
    """Уведомление о результате рассмотрения"""
    try:
        if status == "approved":
            text = (
                f"✅ <b>Твоё предложение одобрено!</b>\n\n"
                f"🎴 Карточка <b>{char_name}</b> добавлена в игру!\n"
                f"💰 Награда: <b>+{reward} монет</b>\n"
            )
            if comment:
                text += f"\n💬 Комментарий админа:\n<i>{comment}</i>"
        else:
            text = (
                f"❌ <b>Твоё предложение отклонено</b>\n\n"
                f"💬 Причина:\n<i>{comment or 'Не указана'}</i>\n\n"
                f"Не расстраивайся, попробуй ещё! 💪"
            )

        await bot.send_message(user_id, text, parse_mode="HTML")
    except Exception as e:
        print(f"⚠️ Не смог уведомить {user_id}: {e}")


async def notify_admin_new_suggestion(user_name: str, char_name: str, anime: str):
    """Уведомление админу о новом предложении"""
    try:
        await bot.send_message(
            ADMIN_ID,
            f"📬 <b>Новое предложение карточки!</b>\n\n"
            f"👤 От: <b>{user_name}</b>\n"
            f"🎴 <b>{char_name}</b>\n"
            f"📺 {anime}\n\n"
            f"Открой /admin для рассмотрения",
            parse_mode="HTML",
        )
    except Exception as e:
        print(f"⚠️ Не смог уведомить админа: {e}")

async def on_startup(bot: Bot):
    """Инициализация при запуске бота"""
    global BOT_USERNAME

    me = await bot.get_me()
    BOT_USERNAME = me.username
    print(f"✅ Bot username: @{BOT_USERNAME}")

    # ========== 1. Menu Button ==========
    try:
        if WEBAPP_URL and WEBAPP_URL.startswith("https"):
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="🎴 Играть",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            )
            print(f"✅ Menu button установлена: {WEBAPP_URL}")
        else:
            print(f"⚠️ WEBAPP_URL некорректный: {WEBAPP_URL}")
    except Exception as e:
        print(f"❌ Menu button error: {e}")

    # ========== 2. Команды бота ==========
    from aiogram.types import (
        BotCommand,
        BotCommandScopeChat,
        BotCommandScopeAllPrivateChats,
        BotCommandScopeAllGroupChats,
    )

    # ⚠️ ВАЖНО: команды ТОЛЬКО на английском!
    # Русские алиасы (/бонус, /крутить) работают из кода,
    # но в меню Telegram их нельзя.
    commands = [
        BotCommand(command="start",      description="🎴 Главное меню"),
        BotCommand(command="bonus",      description="💰 Забрать монеты (6ч)"),
        BotCommand(command="pull",       description="🎰 Крутка x1 (300💰)"),
        BotCommand(command="pull3",      description="🎰 Крутка x3 (810💰)"),
        BotCommand(command="collection", description="🎴 Моя коллекция"),
        BotCommand(command="card",       description="🔍 Показать карточку по ID"),
        BotCommand(command="profile",    description="💼 Мой профиль"),
        BotCommand(command="suggest",    description="💡 Предложить карточку"),
        BotCommand(command="help",       description="ℹ️ Список команд"),
    ]

    try:
        # Сбрасываем старые команды
        await bot.delete_my_commands()

        # Ставим общие
        await bot.set_my_commands(commands)
        print(f"✅ Установлено команд: {len(commands)}")

        # Дополнительно для админа
        admin_commands = commands + [
            BotCommand(command="admin", description="👑 Админ-панель"),
        ]
        await bot.set_my_commands(
            admin_commands,
            scope=BotCommandScopeChat(chat_id=ADMIN_ID),
        )
        print(f"✅ У админа: {len(admin_commands)} команд")

    except Exception as e:
        print(f"❌ Commands error: {e}")


dp.startup.register(on_startup)
