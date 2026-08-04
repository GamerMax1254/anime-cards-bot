# gacha.py
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import Character, User, UserCard, RARITY_INFO
from config import *


class GachaService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_user(self, telegram_id, username=None, first_name=None):
        user = self.db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                coins=CLAIM_AMOUNT,
            )
            self.db.add(user)
            self.db.commit()
        else:
            # Обновляем данные при каждом визите (может юзер сменил имя)
            changed = False
            if username and user.username != username:
                user.username = username
                changed = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                changed = True
            if changed:
                self.db.commit()
        return user

    def get_user_info(self, telegram_id):
        user = self.get_or_create_user(telegram_id)
        return {
            "telegram_id": user.telegram_id,
            "coins": user.coins, "gems": user.gems,
            "total_cards": user.total_cards,
            "total_pulls": user.total_pulls,
            "pulls_since_pity": user.pulls_since_pity,
            "last_claim": user.last_claim.isoformat() if user.last_claim else None,
        }

    def claim_coins(self, telegram_id):
        user = self.get_or_create_user(telegram_id)
        now = datetime.utcnow()
        interval = timedelta(hours=CLAIM_INTERVAL_HOURS)

        if user.last_claim and (now - user.last_claim) < interval:
            remaining = (user.last_claim + interval) - now
            h = int(remaining.total_seconds() // 3600)
            m = int((remaining.total_seconds() % 3600) // 60)
            s = int(remaining.total_seconds() % 60)
            return {
                "success": False,
                "message": f"⏰ Через {h}ч {m}мин {s}сек",
                "remaining_seconds": remaining.total_seconds(),
                "coins": user.coins,
            }

        user.coins += CLAIM_AMOUNT
        user.last_claim = now
        self.db.commit()
        return {"success": True, "message": f"💰 +{CLAIM_AMOUNT}",
                "claimed": CLAIM_AMOUNT, "coins": user.coins}

    def single_pull(self, telegram_id):
        user = self.get_or_create_user(telegram_id)
        if user.coins < SINGLE_PULL_COST:
            return {"success": False,
                    "message": f"Нужно {SINGLE_PULL_COST}💰, у тебя {user.coins}💰",
                    "coins": user.coins}

        user.coins -= SINGLE_PULL_COST
        result = self._do_pull(user)
        self.db.commit()
        return {"success": True, "card": self._fmt(result), "coins": user.coins}

    def multi_pull(self, telegram_id):
        user = self.get_or_create_user(telegram_id)
        if user.coins < MULTI_PULL_COST:
            return {"success": False,
                    "message": f"Нужно {MULTI_PULL_COST}💰, у тебя {user.coins}💰",
                    "coins": user.coins}

        user.coins -= MULTI_PULL_COST
        results = [self._do_pull(user) for _ in range(MULTI_PULL_COUNT)]
        self.db.commit()
        return {
            "success": True,
            "cards": [self._fmt(r) for r in results],
            "coins": user.coins,
            "new_count": sum(1 for r in results if r["is_new"]),
        }

    def get_collection(self, telegram_id, rarity=None, page=1, per_page=20):
        query = self.db.query(UserCard).join(Character).filter(UserCard.user_id == telegram_id)
        if rarity:
            query = query.filter(Character.rarity == rarity)

        total = query.count()
        cards = query.offset((page - 1) * per_page).limit(per_page).all()
        total_chars = self.db.query(Character).filter(Character.is_active == True).count()
        all_user = self.db.query(UserCard).filter(UserCard.user_id == telegram_id).count()

        return {
            "total_collected": all_user,
            "total_characters": total_chars,
            "completion": round(all_user / max(total_chars, 1) * 100, 1),
            "page": page,
            "cards": [{
                "character_id": c.character.id,
                "name": c.character.display_name,
                "name_en": c.character.name_en,
                "anime": c.character.anime_title,
                "rarity": c.character.rarity,
                "rarity_info": c.character.rarity_info,
                "image_url": c.character.image_url,
                "count": c.count, "level": c.level,
                "is_favorite": c.is_favorite,
                "power": c.character.power,
                "defense": c.character.defense,
                "speed": c.character.speed,
            } for c in cards],
        }

    def get_all_characters(self, page=1, per_page=50):
        query = self.db.query(Character).filter(Character.is_active == True)
        total = query.count()
        chars = query.offset((page - 1) * per_page).limit(per_page).all()
        return {
            "total": total, "page": page,
            "characters": [{
                "id": c.id, "name": c.display_name,
                "name_en": c.name_en, "anime": c.anime_title,
                "rarity": c.rarity, "rarity_info": c.rarity_info,
                "image_url": c.image_url,
            } for c in chars],
        }

    def _do_pull(self, user):
        user.total_pulls += 1
        user.pulls_since_pity += 1

        rarity = self._roll_rarity(user)
        chars = self.db.query(Character).filter(
            Character.rarity == rarity, Character.is_active == True).all()
        if not chars:
            chars = self.db.query(Character).filter(
                Character.rarity != "unique", Character.is_active == True).all()

        character = random.choice(chars)

        if RARITY_INFO[rarity]["order"] >= RARITY_INFO["legendary"]["order"]:
            user.pulls_since_pity = 0

        existing = self.db.query(UserCard).filter(
            UserCard.user_id == user.telegram_id,
            UserCard.character_id == character.id).first()

        is_new = existing is None
        dupe_coins = 0
        if existing:
            existing.count += 1
            dupe_coins = DUPLICATE_COINS.get(rarity, 5)
            user.coins += dupe_coins
        else:
            self.db.add(UserCard(user_id=user.telegram_id, character_id=character.id))

        return {"character": character, "is_new": is_new, "duplicate_coins": dupe_coins}

    def _roll_rarity(self, user):
        weights = dict(RARITY_WEIGHTS)
        pity = user.pulls_since_pity
        if pity >= HARD_PITY:
            return random.choice(["legendary", "mythical"])
        if pity >= SOFT_PITY:
            bonus = (pity - SOFT_PITY) * 2.0
            weights["legendary"] = weights.get("legendary", 4) + bonus
            weights["mythical"] = weights.get("mythical", 0.9) + bonus * 0.3
        return random.choices(list(weights.keys()), list(weights.values()), k=1)[0]

    def _fmt(self, result):
        c = result["character"]
        info = c.rarity_info
        return {
            "id": c.id, "name": c.display_name, "name_en": c.name_en,
            "name_jp": c.name_jp, "anime": c.anime_title,
            "rarity": c.rarity, "rarity_name": info["name"],
            "emoji": info["emoji"], "stars": info["stars"], "color": info["color"],
            "image_url": c.image_url, "description": c.description,
            "power": c.power, "defense": c.defense, "speed": c.speed,
            "is_new": result["is_new"], "duplicate_coins": result["duplicate_coins"],
        }