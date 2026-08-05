"""
Импорт персонажей из Jikan API (MyAnimeList).
Использование:
    python import_characters.py
"""

import requests
import time
import os
import sys
import uuid
from pathlib import Path
from database import get_session, Character, Anime, RARITY_INFO

# ============================================
# НАСТРОЙКИ
# ============================================

JIKAN_API = "https://api.jikan.moe/v4"
IMAGES_DIR = Path("frontend/uploads/cards")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
DELAY = 1.5  # с запасом
MAX_RETRIES = 3

# ============================================
# ФУНКЦИИ
# ============================================

def api_get(url: str, params: dict = None):
    """GET с retry"""
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=30)

            if r.status_code == 200:
                return r

            if r.status_code == 429:
                # Rate limit
                wait = 10
                print(f"    ⏸ Rate limit, жду {wait}сек...")
                time.sleep(wait)
                continue

            if r.status_code == 404:
                print(f"    ❌ Не найдено (404)")
                return None

            if r.status_code >= 500:
                # Серверная ошибка (504, 502, 503)
                wait = 5 * (attempt + 1)
                print(f"    ⚠️ Ошибка сервера {r.status_code}, ретрай через {wait}сек... (попытка {attempt+1}/{MAX_RETRIES})")
                time.sleep(wait)
                continue

            print(f"    ❌ Неожиданная ошибка {r.status_code}")
            return None

        except requests.exceptions.Timeout:
            print(f"    ⏰ Таймаут (попытка {attempt+1}/{MAX_RETRIES})")
            time.sleep(3)
        except requests.exceptions.ConnectionError as e:
            print(f"    🔌 Проблема с сетью: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"    ❌ Ошибка: {e}")
            time.sleep(3)

    print(f"    ❌ Не удалось после {MAX_RETRIES} попыток")
    return None

def search_anime(query: str, limit: int = 5):
    print(f"\n🔍 Ищу '{query}'...")
    r = api_get(f"{JIKAN_API}/anime", params={
        "q": query,
        "limit": limit,
        "order_by": "popularity",
        "sort": "asc",
    })
    time.sleep(DELAY)
    if not r:
        return []
    return r.json().get("data", [])


def get_anime_characters(anime_id: int):
    print(f"📥 Загружаю персонажей аниме #{anime_id}...")
    r = api_get(f"{JIKAN_API}/anime/{anime_id}/characters")
    time.sleep(DELAY)
    if not r:
        return []
    return r.json().get("data", [])


def get_character_details(char_id: int):
    r = api_get(f"{JIKAN_API}/characters/{char_id}/full")
    time.sleep(DELAY)
    if not r:
        return None
    return r.json().get("data")


def determine_rarity(favorites: int, role: str) -> str:
    """
    Определяем редкость по популярности:
    - favorites — сколько людей добавили в избранное на MAL
    - role — main или supporting
    """
    if role == "Main":
        # Главные персонажи всегда минимум epic
        if favorites >= 50000:
            return "secret"       # 💠 суперзвёзды
        if favorites >= 20000:
            return "mythical"     # 🟥
        if favorites >= 5000:
            return "legendary"    # 🟨
        if favorites >= 1000:
            return "epic"         # 🟪
        return "epic"             # минимум epic для главных
    else:
        # Второстепенные
        if favorites >= 10000:
            return "legendary"
        if favorites >= 2000:
            return "epic"
        if favorites >= 500:
            return "rare"
        if favorites >= 50:
            return "uncommon"
        return "common"


def calculate_stats(favorites: int, rarity: str) -> dict:
    """Автоматически рассчитываем статы"""
    import random

    # Базовые значения по редкости
    base = {
        "common": 40,
        "uncommon": 55,
        "rare": 65,
        "epic": 75,
        "legendary": 85,
        "mythical": 92,
        "secret": 97,
    }.get(rarity, 50)

    # Случайные вариации
    power = base + random.randint(-5, 10)
    defense = base + random.randint(-8, 8)
    speed = base + random.randint(-8, 8)

    # Ограничим 1-100
    return {
        "power": max(1, min(100, power)),
        "defense": max(1, min(100, defense)),
        "speed": max(1, min(100, speed)),
    }


def download_image(url: str, char_id: int) -> str:
    if not url:
        return None

    try:
        ext = url.split(".")[-1].split("?")[0].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"

        filename = f"mal_{char_id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = IMAGES_DIR / filename

        for attempt in range(3):
            try:
                r = requests.get(url, timeout=30, stream=True)
                r.raise_for_status()

                with open(filepath, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)

                return f"/uploads/cards/{filename}"
            except Exception as e:
                if attempt < 2:
                    print(f"    ⚠️ Ретрай картинки...")
                    time.sleep(2)
                else:
                    print(f"    ⚠️ Не удалось скачать картинку: {e}")
                    return None
    except Exception as e:
        print(f"    ⚠️ Ошибка: {e}")
        return None


def import_anime(anime_data: dict, char_limit: int = None, download_images: bool = True):
    """Импорт аниме и всех его персонажей"""
    db = get_session()

    try:
        # Проверяем есть ли уже аниме
        title_en = anime_data.get("title_english") or anime_data["title"]
        title_ru = None  # Jikan не даёт русские названия

        existing = db.query(Anime).filter(Anime.title_en == title_en).first()
        if existing:
            print(f"✅ Аниме '{title_en}' уже в БД (#{existing.id})")
            anime = existing
        else:
            anime = Anime(
                title_en=title_en,
                title_ru=title_ru,
                genre=",".join([g["name"].lower() for g in anime_data.get("genres", [])]),
            )
            db.add(anime)
            db.commit()
            print(f"✅ Добавлено аниме: {title_en} (#{anime.id})")

        # Получаем персонажей
        chars_data = get_anime_characters(anime_data["mal_id"])

        if not chars_data:
            print("❌ Нет персонажей")
            return 0

        # Сортируем по роли (Main первые) и лимитируем
        chars_data.sort(key=lambda x: 0 if x["role"] == "Main" else 1)
        if char_limit:
            chars_data = chars_data[:char_limit]

        print(f"📊 Найдено {len(chars_data)} персонажей, импортирую...")

        added = 0
        skipped = 0

        for i, char_entry in enumerate(chars_data, 1):
            char = char_entry["character"]
            role = char_entry["role"]

            char_id = char["mal_id"]
            name_en = char["name"]

            # Проверяем нет ли уже
            existing_char = db.query(Character).filter(
                Character.name_en == name_en,
                Character.anime_id == anime.id,
            ).first()

            if existing_char:
                print(f"  [{i}/{len(chars_data)}] ⏭  {name_en} — уже есть")
                skipped += 1
                continue

            # Детальная информация (для favorites)
            print(f"  [{i}/{len(chars_data)}] 📥 {name_en} ({role})...")
            details = get_character_details(char_id)

            favorites = details.get("favorites", 0) if details else 0

            # Автоопределение редкости
            rarity = determine_rarity(favorites, role)
            stats = calculate_stats(favorites, rarity)

            # Картинка
            image_url = None
            if download_images:
                img_url = char["images"]["jpg"].get("image_url")
                if img_url:
                    image_url = download_image(img_url, char_id)

            # Описание из about (если есть)
            description = None
            if details and details.get("about"):
                about = details["about"].strip()
                # Обрезаем до 500 символов
                if len(about) > 500:
                    about = about[:497] + "..."
                description = about

            # Создаём карточку
            new_char = Character(
                name_en=name_en,
                name_ru=None,  # русские имена вручную
                name_jp=char.get("name_kanji", ""),
                anime_id=anime.id,
                rarity=rarity,
                image_url=image_url,
                description=description,
                power=stats["power"],
                defense=stats["defense"],
                speed=stats["speed"],
                is_active=True,
            )
            db.add(new_char)
            db.commit()

            info = RARITY_INFO[rarity]
            print(f"       ✅ Добавлен: {info['emoji']} {info['name']} | ATK{stats['power']} DEF{stats['defense']} SPD{stats['speed']}")
            if image_url:
                print(f"       🖼 Картинка сохранена")

            added += 1

        print(f"\n✅ Импорт завершён: добавлено {added}, пропущено {skipped}")
        return added

    finally:
        db.close()


# ============================================
# ИНТЕРАКТИВНОЕ МЕНЮ
# ============================================

def interactive_menu():
    """Главное меню импорта"""
    print("\n" + "=" * 50)
    print("🎴 ИМПОРТ ПЕРСОНАЖЕЙ ИЗ MAL")
    print("=" * 50)

    while True:
        print("\n📋 Что делаем?")
        print("  1. Найти и импортировать аниме")
        print("  2. Массовый импорт из списка")
        print("  3. Импорт топ-100 аниме")
        print("  0. Выход")

        choice = input("\n> ").strip()

        if choice == "0":
            print("👋 Пока!")
            break

        elif choice == "1":
            single_anime_import()

        elif choice == "2":
            batch_import()

        elif choice == "3":
            top_anime_import()

        else:
            print("❌ Неверный выбор")


def single_anime_import():
    """Импорт одного аниме"""
    query = input("\n🔍 Название аниме: ").strip()
    if not query:
        return

    results = search_anime(query, limit=5)
    if not results:
        print("❌ Ничего не найдено")
        return

    print(f"\n📋 Найдено {len(results)} результатов:")
    for i, anime in enumerate(results, 1):
        title = anime.get("title_english") or anime["title"]
        year = anime.get("year") or "?"
        score = anime.get("score") or "?"
        print(f"  {i}. {title} ({year}) ⭐ {score}")

    idx = input("\n> Выбери номер (или 0 для отмены): ").strip()
    try:
        idx = int(idx) - 1
        if idx < 0 or idx >= len(results):
            return
    except:
        return

    anime = results[idx]

    # Настройки импорта
    limit_str = input(f"\n📊 Сколько персонажей импортировать? (Enter = все): ").strip()
    limit = int(limit_str) if limit_str else None

    imgs = input("🖼 Скачивать картинки? (y/n) [y]: ").strip().lower()
    download_images = imgs != "n"

    # Импортируем
    import_anime(anime, char_limit=limit, download_images=download_images)


def batch_import():
    """Массовый импорт из списка"""
    print("\n📝 Введи названия аниме через ; (точка с запятой)")
    print("   Пример: Naruto; One Piece; Bleach")
    text = input("\n> ").strip()

    if not text:
        return

    titles = [t.strip() for t in text.split(";") if t.strip()]
    print(f"\n📊 Будет импортировано {len(titles)} аниме")

    limit_str = input("📊 Персонажей на аниме (Enter = все): ").strip()
    limit = int(limit_str) if limit_str else None

    imgs = input("🖼 Скачивать картинки? (y/n) [y]: ").strip().lower()
    download_images = imgs != "n"

    total_added = 0
    for title in titles:
        results = search_anime(title, limit=1)
        if not results:
            print(f"❌ Не найдено: {title}")
            continue

        added = import_anime(results[0], char_limit=limit, download_images=download_images)
        total_added += added

    print(f"\n🎉 ГОТОВО! Всего добавлено персонажей: {total_added}")


def top_anime_import():
    """Импорт топ-100 популярных аниме"""
    print("\n📊 Загружаю топ аниме...")

    limit_str = input("📊 Сколько аниме взять из топа? (по умолчанию 20): ").strip()
    top_count = int(limit_str) if limit_str else 20

    char_limit_str = input("📊 Персонажей на аниме (по умолчанию 5): ").strip()
    char_limit = int(char_limit_str) if char_limit_str else 5

    imgs = input("🖼 Скачивать картинки? (y/n) [y]: ").strip().lower()
    download_images = imgs != "n"

    confirm = input(f"\n⚠️  Это займёт много времени (~{top_count * char_limit * 2} сек). Продолжить? (y/n): ").lower()
    if confirm != "y":
        return

    r = requests.get(f"{JIKAN_API}/top/anime", params={"limit": min(top_count, 25)})
    time.sleep(DELAY)

    if r.status_code != 200:
        print("❌ Ошибка загрузки топа")
        return

    top_anime = r.json().get("data", [])[:top_count]
    print(f"\n📋 Топ {len(top_anime)} аниме готовы к импорту")

    total_added = 0
    for i, anime in enumerate(top_anime, 1):
        title = anime.get("title_english") or anime["title"]
        print(f"\n[{i}/{len(top_anime)}] {title}")
        added = import_anime(anime, char_limit=char_limit, download_images=download_images)
        total_added += added

    print(f"\n🎉 ГОТОВО! Всего добавлено персонажей: {total_added}")


# ============================================
# ЗАПУСК
# ============================================
if __name__ == "__main__":
    try:
        interactive_menu()
    except KeyboardInterrupt:
        print("\n\n👋 Прервано пользователем")