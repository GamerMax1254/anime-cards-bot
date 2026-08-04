# bot.py
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
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


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Стартовая команда"""
    print(f"📨 /start от {message.from_user.id} ({message.from_user.first_name})")

    # Регистрируем пользователя
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

    # Клавиатура
    kb = InlineKeyboardBuilder()

    # Кнопка Mini App
    if WEBAPP_URL and WEBAPP_URL.startswith("https"):
        kb.row(InlineKeyboardButton(
            text="🎴 Открыть игру",
            web_app=WebAppInfo(url=WEBAPP_URL),
        ))

    # Обычные кнопки (работают даже без Mini App)
    kb.row(InlineKeyboardButton(text="💰 Забрать монеты", callback_data="claim"))
    kb.row(
        InlineKeyboardButton(text="🎰 x1 (100💰)", callback_data="pull1"),
        InlineKeyboardButton(text="🎰 x3 (810💰)", callback_data="pull10"),
    )
    kb.row(InlineKeyboardButton(text="🎴 Коллекция", callback_data="my_collection"))
    kb.row(InlineKeyboardButton(text="💼 Баланс", callback_data="balance"))

    # Админка — только для тебя
    if message.from_user.id == ADMIN_ID:
        kb.row(InlineKeyboardButton(text="👑 Админ-панель", callback_data="admin_menu"))

    await message.answer(
        "🎴 <b>Аниме Карточки</b>\n\n"
        "Собирай карточки любимых персонажей!\n\n"
        "💰 Монеты каждые 6 часов\n"
        "🎰 Крути гачу\n"
        "⭐ Собери полную коллекцию!\n\n"
        "Выбери действие 👇",
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
    try:
        if WEBAPP_URL and WEBAPP_URL.startswith("https"):
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="🎴 Играть",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            )
            print("✅ Menu button установлена")
    except Exception as e:
        print(f"⚠️ Menu button error: {e}")

    # Команды бота
    from aiogram.types import BotCommand
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="🎴 Главное меню"),
            BotCommand(command="бонус", description="💰 Забрать монеты"),
            BotCommand(command="balance", description="💼 Мой баланс"),
        ])
        print("✅ Команды установлены")
    except Exception as e:
        print(f"⚠️ Commands error: {e}")


dp.startup.register(on_startup)
