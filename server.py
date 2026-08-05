# server.py
from fastapi import FastAPI, Query, UploadFile, File, Form, HTTPException, Request, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil
import uuid
import hashlib
import hmac
from urllib.parse import parse_qsl
from database import Suggestion
from datetime import datetime

from database import get_session, RARITY_INFO, Character, Anime, User, UserCard, AdminLog
from gacha import GachaService
from config import SERVER_HOST, SERVER_PORT, ADMIN_ID, BOT_TOKEN

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Папки
UPLOAD_DIR = Path("frontend/uploads/cards")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory="frontend"), name="static")
app.mount("/uploads", StaticFiles(directory="frontend/uploads"), name="uploads")


# ============================================
# АВТОРИЗАЦИЯ АДМИНА
# ============================================
def verify_admin(x_admin_key: str = Header(None)):
    """Простая проверка админ-ключа"""
    # Ключ = хэш от токена бота
    expected = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32]
    if x_admin_key != expected:
        raise HTTPException(403, "Forbidden")
    return True


def get_admin_key():
    """Возвращает ключ для использования в JS"""
    return hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32]


# ============================================
# СТРАНИЦЫ
# ============================================
@app.get("/")
async def root():
    return FileResponse("frontend/index.html")


@app.get("/admin")
async def admin_page():
    return FileResponse("frontend/admin.html")


@app.get("/api/admin/key/{telegram_id}")
async def get_key(telegram_id: int):
    """Выдаёт ключ ТОЛЬКО админу"""
    if telegram_id != ADMIN_ID:
        raise HTTPException(403, "Not admin")
    return {"key": get_admin_key()}


# ============================================
# ЮЗЕР API
# ============================================
@app.get("/api/user/{telegram_id}")
async def api_user(telegram_id: int):
    db = get_session()
    try:
        gacha = GachaService(db)
        info = gacha.get_user_info(telegram_id)

        # Добавляем избранную карточку для профиля
        fav = db.query(UserCard).filter(
            UserCard.user_id == telegram_id,
            UserCard.is_favorite == True,
        ).first()

        info["profile_card"] = None
        if fav and fav.character:
            info["profile_card"] = {
                "id": fav.character.id,
                "name": fav.character.display_name,
                "anime": fav.character.anime_title,
                "image_url": fav.character.image_url,
                "rarity": fav.character.rarity,
                "rarity_info": fav.character.rarity_info,
            }

        return info
    finally:
        db.close()


@app.post("/api/claim/{telegram_id}")
async def api_claim(telegram_id: int):
    db = get_session()
    try:
        return GachaService(db).claim_coins(telegram_id)
    finally:
        db.close()


@app.post("/api/pull/{telegram_id}")
async def api_pull(telegram_id: int):
    db = get_session()
    try:
        return GachaService(db).single_pull(telegram_id)
    finally:
        db.close()


@app.post("/api/pull10/{telegram_id}")
async def api_pull10(telegram_id: int):
    db = get_session()
    try:
        return GachaService(db).multi_pull(telegram_id)
    finally:
        db.close()


@app.get("/api/collection/{telegram_id}")
async def api_collection(telegram_id: int, page: int = 1, per_page: int = 50, rarity: str = None):
    db = get_session()
    try:
        return GachaService(db).get_collection(telegram_id, rarity=rarity, page=page, per_page=per_page)
    finally:
        db.close()


@app.get("/api/characters")
async def api_characters(page: int = 1, per_page: int = 50):
    db = get_session()
    try:
        return GachaService(db).get_all_characters(page=page, per_page=per_page)
    finally:
        db.close()


@app.get("/api/rarities")
async def api_rarities():
    return RARITY_INFO


# ============================================
# ИЗБРАННОЕ (для фона профиля)
# ============================================
@app.post("/api/favorite/{telegram_id}/{character_id}")
async def toggle_favorite(telegram_id: int, character_id: int):
    db = get_session()
    try:
        card = db.query(UserCard).filter(
            UserCard.user_id == telegram_id,
            UserCard.character_id == character_id,
        ).first()

        if not card:
            raise HTTPException(404, "Карточка не в коллекции")

        # Сбрасываем все избранные (одна активная)
        db.query(UserCard).filter(
            UserCard.user_id == telegram_id,
            UserCard.is_favorite == True,
        ).update({"is_favorite": False})

        # Переключаем текущую
        card.is_favorite = not card.is_favorite
        db.commit()

        return {"is_favorite": card.is_favorite}
    finally:
        db.close()


# ============================================
# АДМИН API (защищено ключом)
# ============================================

# --- Загрузка картинки ---
@app.post("/api/admin/upload")
async def admin_upload(file: UploadFile = File(...), _: bool = Depends(verify_admin)):
    """Загрузка картинки"""
    # Проверяем формат
    ext = file.filename.split(".")[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
        raise HTTPException(400, "Только jpg/png/webp/gif")

    # Уникальное имя
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = UPLOAD_DIR / filename

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"url": f"/uploads/cards/{filename}"}


# --- CRUD Персонажи ---
@app.get("/api/admin/characters")
async def admin_list_chars(_: bool = Depends(verify_admin)):
    db = get_session()
    try:
        chars = db.query(Character).order_by(Character.id.desc()).all()
        return [{
            "id": c.id, "name_en": c.name_en, "name_ru": c.name_ru,
            "name_jp": c.name_jp, "anime_id": c.anime_id,
            "anime_title": c.anime_title, "rarity": c.rarity,
            "rarity_info": c.rarity_info, "image_url": c.image_url,
            "description": c.description, "power": c.power,
            "defense": c.defense, "speed": c.speed,
            "is_active": c.is_active,
        } for c in chars]
    finally:
        db.close()


@app.post("/api/admin/characters")
async def admin_create_char(data: dict, _: bool = Depends(verify_admin)):
    db = get_session()
    try:
        char = Character(
            name_en=data["name_en"],
            name_ru=data.get("name_ru"),
            name_jp=data.get("name_jp", ""),
            anime_id=data.get("anime_id"),
            rarity=data.get("rarity", "common"),
            image_url=data.get("image_url"),
            description=data.get("description"),
            power=data.get("power", 50),
            defense=data.get("defense", 50),
            speed=data.get("speed", 50),
            is_active=data.get("is_active", True),
        )
        db.add(char)
        db.add(AdminLog(action="create_char", details=f"Created {data['name_en']}"))
        db.commit()
        return {"id": char.id, "success": True}
    finally:
        db.close()


@app.put("/api/admin/characters/{char_id}")
async def admin_update_char(char_id: int, data: dict, _: bool = Depends(verify_admin)):
    db = get_session()
    try:
        char = db.query(Character).get(char_id)
        if not char:
            raise HTTPException(404, "Not found")

        for key in ["name_en", "name_ru", "name_jp", "anime_id", "rarity",
                    "image_url", "description", "power", "defense", "speed", "is_active"]:
            if key in data:
                setattr(char, key, data[key])

        db.add(AdminLog(action="edit_char", details=f"Edited #{char_id}"))
        db.commit()
        return {"success": True}
    finally:
        db.close()


@app.delete("/api/admin/characters/{char_id}")
async def admin_delete_char(char_id: int, _: bool = Depends(verify_admin)):
    db = get_session()
    try:
        char = db.query(Character).get(char_id)
        if not char:
            raise HTTPException(404, "Not found")
        name = char.name_en
        db.delete(char)
        db.add(AdminLog(action="delete_char", details=f"Deleted {name}"))
        db.commit()
        return {"success": True}
    finally:
        db.close()


# --- CRUD Аниме ---
@app.get("/api/admin/anime")
async def admin_list_anime(_: bool = Depends(verify_admin)):
    db = get_session()
    try:
        return [{
            "id": a.id, "title_en": a.title_en, "title_ru": a.title_ru,
            "genre": a.genre, "chars_count": len(a.characters),
        } for a in db.query(Anime).order_by(Anime.title_en).all()]
    finally:
        db.close()


@app.post("/api/admin/anime")
async def admin_create_anime(data: dict, _: bool = Depends(verify_admin)):
    db = get_session()
    try:
        anime = Anime(
            title_en=data["title_en"],
            title_ru=data.get("title_ru"),
            genre=data.get("genre"),
        )
        db.add(anime)
        db.commit()
        return {"id": anime.id, "success": True}
    finally:
        db.close()


# --- Пользователи ---
@app.get("/api/admin/users")
async def admin_list_users(_: bool = Depends(verify_admin)):
    db = get_session()
    try:
        return [{
            "telegram_id": u.telegram_id, "username": u.username,
            "first_name": u.first_name, "coins": u.coins,
            "total_cards": u.total_cards, "total_pulls": u.total_pulls,
        } for u in db.query(User).order_by(User.created_at.desc()).all()]
    finally:
        db.close()


# --- Выдача карточки/монет ---
@app.post("/api/admin/give_card")
async def admin_give_card(data: dict, _: bool = Depends(verify_admin)):
    db = get_session()
    try:
        user_id = data["user_id"]
        char_id = data["character_id"]

        existing = db.query(UserCard).filter(
            UserCard.user_id == user_id,
            UserCard.character_id == char_id,
        ).first()

        if existing:
            existing.count += 1
        else:
            db.add(UserCard(user_id=user_id, character_id=char_id))

        db.add(AdminLog(
            action="give_card",
            details=f"Card #{char_id} → User {user_id}",
            target_user_id=user_id,
        ))
        db.commit()
        return {"success": True}
    finally:
        db.close()


@app.post("/api/admin/give_coins")
async def admin_give_coins(data: dict, _: bool = Depends(verify_admin)):
    db = get_session()
    try:
        user = db.query(User).filter(User.telegram_id == data["user_id"]).first()
        if not user:
            raise HTTPException(404, "User not found")

        user.coins += data["amount"]
        if user.coins < 0:
            user.coins = 0

        db.add(AdminLog(
            action="give_coins",
            details=f"{data['amount']} coins → User {data['user_id']}",
            target_user_id=data["user_id"],
        ))
        db.commit()
        return {"success": True, "new_balance": user.coins}
    finally:
        db.close()


# --- Логи ---
@app.get("/api/admin/logs")
async def admin_logs(limit: int = 50, _: bool = Depends(verify_admin)):
    db = get_session()
    try:
        logs = db.query(AdminLog).order_by(AdminLog.created_at.desc()).limit(limit).all()
        return [{
            "id": l.id, "action": l.action, "details": l.details,
            "target_user_id": l.target_user_id,
            "created_at": l.created_at.isoformat(),
        } for l in logs]
    finally:
        db.close()

# ============================================
# ПРЕДЛОЖЕНИЯ (для пользователей)
# ============================================

# ============================================
# ОБНОВИ suggest_card — добавь image_url
# ============================================
@app.post("/api/suggest/{telegram_id}")
async def suggest_card(telegram_id: int, data: dict):
    db = get_session()
    try:
        pending = db.query(Suggestion).filter(
            Suggestion.user_id == telegram_id,
            Suggestion.status == "pending",
        ).count()

        if pending >= 3:
            raise HTTPException(400, "У тебя уже 3 предложения на рассмотрении.")

        if not data.get("name_en") or not data.get("anime_title"):
            raise HTTPException(400, "Заполни имя и аниме")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        user_name = (user.first_name or user.username) if user else None

        suggestion = Suggestion(
            user_id=telegram_id,
            user_name=user_name,
            name_en=data["name_en"][:200],
            name_ru=(data.get("name_ru") or "").strip()[:200] or None,
            name_jp=(data.get("name_jp") or "").strip()[:200] or None,
            anime_title=data["anime_title"][:300],
            rarity_suggested=data.get("rarity_suggested", "common"),
            description=(data.get("description") or "").strip()[:1000] or None,
            power=int(data.get("power", 50)),
            defense=int(data.get("defense", 50)),
            speed=int(data.get("speed", 50)),
            image_url=data.get("image_url"),  # ← НОВОЕ
        )
        db.add(suggestion)
        db.commit()

        # Уведомление админа
        try:
            from bot import notify_admin_new_suggestion
            import asyncio
            asyncio.create_task(notify_admin_new_suggestion(
                user_name or f"ID:{telegram_id}",
                suggestion.name_en,
                suggestion.anime_title,
            ))
        except Exception as e:
            print(f"⚠️ Notify admin failed: {e}")

        return {"success": True, "id": suggestion.id}
    finally:
        db.close()

@app.get("/api/suggestions/{telegram_id}")
async def get_my_suggestions(telegram_id: int):
    db = get_session()
    try:
        items = db.query(Suggestion).filter(
            Suggestion.user_id == telegram_id,
        ).order_by(Suggestion.created_at.desc()).limit(20).all()

        return [{
            "id": s.id,
            "name_en": s.name_en,
            "name_ru": s.name_ru,
            "anime_title": s.anime_title,
            "rarity_suggested": s.rarity_suggested,
            "status": s.status,
            "admin_comment": s.admin_comment,
            "image_url": s.image_url,  # ← НОВОЕ
            "created_at": s.created_at.isoformat(),
            "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None,
        } for s in items]
    finally:
        db.close()


# ============================================
# ПРЕДЛОЖЕНИЯ (для админа)
# ============================================

@app.get("/api/admin/suggestions")
async def admin_list_suggestions(status: str = "pending", _: bool = Depends(verify_admin)):
    db = get_session()
    try:
        query = db.query(Suggestion)
        if status != "all":
            query = query.filter(Suggestion.status == status)

        items = query.order_by(Suggestion.created_at.desc()).all()

        return [{
            "id": s.id,
            "user_id": s.user_id,
            "user_name": s.user_name,
            "name_en": s.name_en,
            "name_ru": s.name_ru,
            "name_jp": s.name_jp,
            "anime_title": s.anime_title,
            "rarity_suggested": s.rarity_suggested,
            "rarity_info": RARITY_INFO.get(s.rarity_suggested, RARITY_INFO["common"]),
            "description": s.description,
            "image_url": s.image_url,  # ← НОВОЕ
            "power": s.power,
            "defense": s.defense,
            "speed": s.speed,
            "status": s.status,
            "admin_comment": s.admin_comment,
            "created_at": s.created_at.isoformat(),
            "created_character_id": s.created_character_id,
        } for s in items]
    finally:
        db.close()


@app.post("/api/admin/suggestions/{sid}/approve")
async def admin_approve(sid: int, data: dict, _: bool = Depends(verify_admin)):
    db = get_session()
    try:
        s = db.query(Suggestion).get(sid)
        if not s:
            raise HTTPException(404, "Not found")
        if s.status != "pending":
            raise HTTPException(400, "Уже обработано")

        anime = db.query(Anime).filter(Anime.title_en.ilike(s.anime_title)).first()
        if not anime:
            anime = Anime(title_en=s.anime_title)
            db.add(anime)
            db.flush()

        char = Character(
            name_en=data.get("name_en", s.name_en),
            name_ru=data.get("name_ru", s.name_ru),
            name_jp=data.get("name_jp", s.name_jp or ""),
            anime_id=anime.id,
            rarity=data.get("rarity", s.rarity_suggested or "common"),
            description=data.get("description", s.description),
            image_url=data.get("image_url") or s.image_url,  # ← юзерская если нет своей
            power=int(data.get("power", s.power)),
            defense=int(data.get("defense", s.defense)),
            speed=int(data.get("speed", s.speed)),
            is_active=True,
        )
        db.add(char)
        db.flush()

        s.status = "approved"
        s.admin_comment = data.get("comment")
        s.reviewed_by = ADMIN_ID
        s.reviewed_at = datetime.utcnow()
        s.created_character_id = char.id

        db.add(AdminLog(
            action="approve_suggestion",
            details=f"Suggestion #{sid} → Character #{char.id}",
            target_user_id=s.user_id,
        ))

        reward = 500
        user = db.query(User).filter(User.telegram_id == s.user_id).first()
        if user:
            user.coins += reward

        char_name = char.name_ru or char.name_en
        user_id = s.user_id
        comment = data.get("comment")

        db.commit()

        try:
            from bot import notify_suggestion_result
            import asyncio
            asyncio.create_task(notify_suggestion_result(
                user_id, "approved", comment, reward, char_name,
            ))
        except Exception as e:
            print(f"⚠️ Notify user failed: {e}")

        return {"success": True, "character_id": char.id, "reward": reward}
    finally:
        db.close()

@app.post("/api/admin/suggestions/{sid}/reject")
async def admin_reject(sid: int, data: dict, _: bool = Depends(verify_admin)):
    db = get_session()
    try:
        s = db.query(Suggestion).get(sid)
        if not s:
            raise HTTPException(404, "Not found")
        if s.status != "pending":
            raise HTTPException(400, "Уже обработано")

        s.status = "rejected"
        s.admin_comment = data.get("comment", "Отклонено")
        s.reviewed_by = ADMIN_ID
        s.reviewed_at = datetime.utcnow()

        db.add(AdminLog(
            action="reject_suggestion",
            details=f"Suggestion #{sid}: {s.admin_comment}",
            target_user_id=s.user_id,
        ))

        user_id = s.user_id
        comment = s.admin_comment
        db.commit()

        # Уведомляем автора
        try:
            from bot import notify_suggestion_result
            import asyncio
            asyncio.create_task(notify_suggestion_result(
                user_id, "rejected", comment,
            ))
        except Exception as e:
            print(f"⚠️ Notify user failed: {e}")

        return {"success": True}
    finally:
        db.close()


@app.get("/api/admin/suggestions/count")
async def admin_suggestions_count(_: bool = Depends(verify_admin)):
    """Количество pending предложений"""
    db = get_session()
    try:
        count = db.query(Suggestion).filter(Suggestion.status == "pending").count()
        return {"pending": count}
    finally:
        db.close()


# Отдельная папка для юзерских картинок
SUGGEST_UPLOAD_DIR = Path("frontend/uploads/suggestions")
SUGGEST_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ============================================
# ЗАГРУЗКА КАРТИНКИ ДЛЯ ПРЕДЛОЖЕНИЯ (без ключа)
# ============================================
@app.post("/api/suggest/upload/{telegram_id}")
async def suggest_upload(telegram_id: int, file: UploadFile = File(...)):
    """Загрузка картинки от пользователя (для предложения)"""

    # Проверка формата
    ext = file.filename.split(".")[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        raise HTTPException(400, "Только jpg/png/webp")

    # Проверка размера (макс 5 МБ)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(400, "Файл больше 5 МБ")

    # Уникальное имя (с ID юзера в названии)
    filename = f"u{telegram_id}_{uuid.uuid4().hex[:12]}.{ext}"
    filepath = SUGGEST_UPLOAD_DIR / filename

    with open(filepath, "wb") as f:
        f.write(contents)

    return {"url": f"/uploads/suggestions/{filename}"}  

@app.get("/api/card/{telegram_id}/{character_id}")
async def api_card_details(telegram_id: int, character_id: int):
    """Детальная информация о карточке пользователя"""
    db = get_session()
    try:
        # Информация о персонаже
        char = db.query(Character).get(character_id)
        if not char:
            raise HTTPException(404, "Character not found")

        # Информация о карте пользователя
        user_card = db.query(UserCard).filter(
            UserCard.user_id == telegram_id,
            UserCard.character_id == character_id,
        ).first()

        # Статистика — у скольких юзеров есть эта карта
        total_users = db.query(User).count()
        owners_count = db.query(UserCard).filter(
            UserCard.character_id == character_id,
        ).distinct(UserCard.user_id).count()

        percentage = round((owners_count / total_users * 100), 2) if total_users > 0 else 0

        return {
            "character": {
                "id": char.id,
                "name": char.display_name,
                "name_en": char.name_en,
                "name_ru": char.name_ru,
                "name_jp": char.name_jp,
                "anime": char.anime_title,
                "rarity": char.rarity,
                "rarity_info": char.rarity_info,
                "image_url": char.image_url,
                "description": char.description,
                "power": char.power,
                "defense": char.defense,
                "speed": char.speed,
                "tags": char.tags,
            },
            "user_card": {
                "owned": user_card is not None,
                "count": user_card.count if user_card else 0,
                "level": user_card.level if user_card else 1,
                "is_favorite": user_card.is_favorite if user_card else False,
                "obtained_at": user_card.obtained_at.isoformat() if user_card else None,
            } if user_card else {
                "owned": False,
                "count": 0,
                "level": 0,
                "is_favorite": False,
                "obtained_at": None,
            },
            "stats": {
                "total_users": total_users,
                "owners_count": owners_count,
                "percentage": percentage,
            }
        }
    finally:
        db.close()


# Распылить дубликат в монеты
@app.post("/api/card/{telegram_id}/{character_id}/dust")
async def api_dust_card(telegram_id: int, character_id: int):
    """Распылить лишнюю копию карточки в монеты"""
    db = get_session()
    try:
        user_card = db.query(UserCard).filter(
            UserCard.user_id == telegram_id,
            UserCard.character_id == character_id,
        ).first()

        if not user_card or user_card.count <= 1:
            raise HTTPException(400, "Нельзя распылить последнюю копию")

        char = db.query(Character).get(character_id)
        from config import DUPLICATE_COINS
        dust_reward = DUPLICATE_COINS.get(char.rarity, 5) * 2  # x2 за распыление

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        user.coins += dust_reward
        user_card.count -= 1

        db.commit()

        return {
            "success": True,
            "dusted": dust_reward,
            "new_count": user_card.count,
            "new_balance": user.coins,
        }
    finally:
        db.close()