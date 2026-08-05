"""
Импорт персонажей из AniList API (GraphQL).
Использование:
    python import_anilist.py
"""

import requests
import time
import uuid
from pathlib import Path
from database import get_session, Character, Anime, RARITY_INFO

# ============================================
# НАСТРОЙКИ
# ============================================
ANILIST_API = "https://graphql.anilist.co"

IMAGES_DIR = Path("frontend/uploads/cards")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

DELAY = 1.0  # AniList: 90 req/min = 1.5/sec
MAX_RETRIES = 3


# ============================================
# API HELPERS
# ============================================

def api_query(query: str, variables: dict, max_retries: int = MAX_RETRIES):
    """GraphQL запрос с retry"""
    for attempt in range(max_retries):
        try:
            r = requests.post(
                ANILIST_API,
                json={"query": query, "variables": variables},
                timeout=30,
            )

            if r.status_code == 200:
                data = r.json()
                if "errors" in data:
                    print(f"    ⚠️ GraphQL error: {data['errors']}")
                    return None
                return data.get("data")

            if r.status_code == 429:
                wait = 60
                print(f"    ⏸ Rate limit, жду {wait}сек...")
                time.sleep(wait)
                continue

            if r.status_code >= 500:
                wait = 5 * (attempt + 1)
                print(f"    ⚠️ Ошибка {r.status_code}, ретрай через {wait}сек...")
                time.sleep(wait)
                continue

            print(f"    ❌ Ошибка {r.status_code}: {r.text[:200]}")
            return None

        except requests.exceptions.Timeout:
            print(f"    ⏰ Таймаут ({attempt+1}/{max_retries})")
            time.sleep(3)
        except Exception as e:
            print(f"    ❌ Ошибка: {e}")
            time.sleep(3)

    return None


def search_anime(query: str, limit: int = 5):
    """Поиск аниме"""
    print(f"\n🔍 Ищу '{query}'...")

    gql = """
    query ($search: String, $perPage: Int) {
      Page(perPage: $perPage) {
        media(search: $search, type: ANIME, sort: [POPULARITY_DESC]) {
          id
          title {
            romaji
            english
            native
          }
          format
          startDate {
            year
          }
          averageScore
          popularity
          coverImage {
            large
          }
          genres
        }
      }
    }
    """

    data = api_query(gql, {"search": query, "perPage": limit})
    time.sleep(DELAY)

    if not data:
        return []

    return data["Page"]["media"]


def get_anime_with_characters(anime_id: int, chars_limit: int = 25):
    """Получить аниме + всех персонажей одним запросом"""
    print(f"📥 Загружаю персонажей аниме #{anime_id}...")

    gql = """
    query ($id: Int, $perPage: Int) {
      Media(id: $id, type: ANIME) {
        id
        title {
          romaji
          english
          native
        }
        genres
        characters(sort: [FAVOURITES_DESC, ROLE], perPage: $perPage) {
          edges {
            role
            node {
              id
              name {
                full
                native
                alternative
              }
              image {
                large
              }
              description
              gender
              favourites
              age
            }
          }
        }
      }
    }
    """

    data = api_query(gql, {"id": anime_id, "perPage": chars_limit})
    time.sleep(DELAY)

    if not data:
        return None

    return data["Media"]


# ============================================
# ЛОГИКА
# ============================================

def determine_rarity(favourites: int, role: str) -> str:
    """Определение редкости по популярности"""
    if role == "MAIN":
        if favourites >= 15000:
            return "secret"
        if favourites >= 5000:
            return "mythical"
        if favourites >= 1500:
            return "legendary"
        if favourites >= 300:
            return "epic"
        return "epic"  # минимум для главных
    else:
        # SUPPORTING / BACKGROUND
        if favourites >= 8000:
            return "legendary"
        if favourites >= 2000:
            return "epic"
        if favourites >= 400:
            return "rare"
        if favourites >= 50:
            return "uncommon"
        return "common"


def calculate_stats(favourites: int, rarity: str) -> dict:
    """Автоматические статы"""
    import random

    base = {
        "common": 40,
        "uncommon": 55,
        "rare": 65,
        "epic": 75,
        "legendary": 85,
        "mythical": 92,
        "secret": 97,
    }.get(rarity, 50)

    return {
        "power": max(1, min(100, base + random.randint(-5, 10))),
        "defense": max(1, min(100, base + random.randint(-8, 8))),
        "speed": max(1, min(100, base + random.randint(-8, 8))),
    }


def normalize_gender(gender: str) -> str:
    """Нормализуем пол"""
    if not gender:
        return None
    g = gender.lower()
    if g in ("male", "мужской"):
        return "male"
    if g in ("female", "женский"):
        return "female"
    if g in ("non-binary", "other"):
        return "other"
    return None


def clean_description(desc: str) -> str:
    """Очищает описание от HTML/BBCode тегов"""
    if not desc:
        return None

    import re
    # Убираем HTML теги
    desc = re.sub(r'<[^>]+>', '', desc)
    # Убираем BBCode теги
    desc = re.sub(r'\[/?[^\]]+\]', '', desc)
    # Убираем множественные пробелы/переносы
    desc = re.sub(r'\s+', ' ', desc).strip()

    # Обрезаем до 500 символов
    if len(desc) > 500:
        desc = desc[:497] + "..."

    return desc if desc else None


def download_image(url: str, char_id: int) -> str:
    """Скачивает картинку"""
    if not url:
        return None

    try:
        ext = url.split(".")[-1].split("?")[0].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"

        filename = f"al_{char_id}_{uuid.uuid4().hex[:8]}.{ext}"
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
                    time.sleep(2)
                else:
                    print(f"    ⚠️ Не удалось скачать: {e}")
                    return None
    except Exception as e:
        print(f"    ⚠️ Ошибка: {e}")
        return None


def import_anime(anime_data: dict, chars_limit: int = 20, download_images: bool = True, filter_gender: str = None):
    """
    Импорт аниме и персонажей.

    filter_gender: None, "male", "female" — фильтр по полу
    """
    db = get_session()

    try:
        # Название
        title = anime_data["title"]
        title_en = title.get("english") or title["romaji"]
        title_jp = title.get("native")

        # Проверка на существующее
        existing = db.query(Anime).filter(Anime.title_en == title_en).first()
        if existing:
            print(f"✅ Аниме '{title_en}' уже в БД (#{existing.id})")
            anime = existing
        else:
            anime = Anime(
                title_en=title_en,
                title_ru=None,
                genre=",".join([g.lower() for g in anime_data.get("genres", [])]),
            )
            db.add(anime)
            db.commit()
            print(f"✅ Добавлено аниме: {title_en}")

        # Загружаем персонажей
        full_data = get_anime_with_characters(anime_data["id"], chars_limit=chars_limit + 10)
        if not full_data:
            print("❌ Не удалось загрузить персонажей")
            return 0

        edges = full_data["characters"]["edges"]

        # Фильтр по полу
        if filter_gender:
            edges = [e for e in edges if normalize_gender(e["node"].get("gender")) == filter_gender]

        # Лимит
        edges = edges[:chars_limit]

        print(f"📊 Импортирую {len(edges)} персонажей...")

        added = 0
        skipped = 0

        for i, edge in enumerate(edges, 1):
            char = edge["node"]
            role = edge["role"]

            name_en = char["name"]["full"]
            gender = normalize_gender(char.get("gender"))
            favourites = char.get("favourites", 0)

            # Проверка на существующего
            existing_char = db.query(Character).filter(
                Character.name_en == name_en,
                Character.anime_id == anime.id,
            ).first()

            if existing_char:
                print(f"  [{i}/{len(edges)}] ⏭ {name_en}")
                skipped += 1
                continue

            # Определяем редкость
            rarity = determine_rarity(favourites, role)
            stats = calculate_stats(favourites, rarity)

            # Картинка
            image_url = None
            if download_images and char.get("image", {}).get("large"):
                image_url = download_image(char["image"]["large"], char["id"])

            # Описание
            description = clean_description(char.get("description"))

            # Создаём
            new_char_data = {
                "name_en": name_en,
                "name_jp": char["name"].get("native", ""),
                "anime_id": anime.id,
                "rarity": rarity,
                "image_url": image_url,
                "description": description,
                "power": stats["power"],
                "defense": stats["defense"],
                "speed": stats["speed"],
                "is_active": True,
            }

            # Добавляем gender если поле есть в модели
            try:
                new_char_data["gender"] = gender
                new_char = Character(**new_char_data)
            except TypeError:
                # Поля gender нет — создаём без него
                new_char_data.pop("gender", None)
                new_char = Character(**new_char_data)

            db.add(new_char)
            db.commit()

            info = RARITY_INFO[rarity]
            gender_icon = {"male": "♂️", "female": "♀️", "other": "⚧"}.get(gender, "")
            img_icon = "🖼" if image_url else "  "

            print(f"  [{i}/{len(edges)}] ✅ {info['emoji']} {name_en} {gender_icon} | ⚔{stats['power']} 🛡{stats['defense']} 💨{stats['speed']} {img_icon}")

            added += 1

        print(f"\n✅ Импорт: добавлено {added}, пропущено {skipped}")
        return added

    finally:
        db.close()


# ============================================
# ИНТЕРАКТИВНОЕ МЕНЮ
# ============================================

def interactive_menu():
    print("\n" + "=" * 50)
    print("🎴 ИМПОРТ ПЕРСОНАЖЕЙ ИЗ ANILIST")
    print("=" * 50)

    while True:
        print("\n📋 Что делаем?")
        print("  1. Найти и импортировать аниме")
        print("  2. Массовый импорт из списка")
        print("  3. Топ популярных аниме")
        print("  0. Выход")

        choice = input("\n> ").strip()

        if choice == "0":
            break
        elif choice == "1":
            single_anime()
        elif choice == "2":
            batch_anime()
        elif choice == "3":
            top_anime()
        else:
            print("❌ Неверный выбор")


def ask_options():
    """Спросить общие настройки импорта"""
    limit_str = input("📊 Персонажей на аниме (по умолчанию 15): ").strip()
    chars_limit = int(limit_str) if limit_str else 15

    print("\n👤 Фильтр по полу:")
    print("  1. Все")
    print("  2. Только ♂️ мужской")
    print("  3. Только ♀️ женский")
    gender_choice = input("> ").strip() or "1"

    gender_map = {"1": None, "2": "male", "3": "female"}
    filter_gender = gender_map.get(gender_choice)

    imgs = input("🖼 Скачивать картинки? (y/n) [y]: ").strip().lower()
    download_images = imgs != "n"

    return chars_limit, filter_gender, download_images


def single_anime():
    query = input("\n🔍 Название аниме: ").strip()
    if not query:
        return

    results = search_anime(query, limit=5)
    if not results:
        print("❌ Ничего не найдено")
        return

    print(f"\n📋 Найдено {len(results)} результатов:")
    for i, anime in enumerate(results, 1):
        title = anime["title"].get("english") or anime["title"]["romaji"]
        year = anime.get("startDate", {}).get("year") or "?"
        score = anime.get("averageScore") or "?"
        print(f"  {i}. {title} ({year}) ⭐ {score}")

    idx = input("\n> Выбери номер (0 для отмены): ").strip()
    try:
        idx = int(idx) - 1
        if idx < 0 or idx >= len(results):
            return
    except:
        return

    anime = results[idx]

    chars_limit, filter_gender, download_images = ask_options()

    import_anime(
        anime,
        chars_limit=chars_limit,
        download_images=download_images,
        filter_gender=filter_gender,
    )


def batch_anime():
    print("\n📝 Введи аниме через ; (точка с запятой)")
    print("   Пример: Naruto; One Piece; Bleach")
    text = input("\n> ").strip()

    if not text:
        return

    titles = [t.strip() for t in text.split(";") if t.strip()]
    print(f"\n📊 Будет обработано {len(titles)} аниме")

    chars_limit, filter_gender, download_images = ask_options()

    total_added = 0
    for i, title in enumerate(titles, 1):
        print(f"\n[{i}/{len(titles)}] === {title} ===")
        results = search_anime(title, limit=1)
        if not results:
            print(f"❌ Не найдено")
            continue

        added = import_anime(
            results[0],
            chars_limit=chars_limit,
            download_images=download_images,
            filter_gender=filter_gender,
        )
        total_added += added

    print(f"\n🎉 ГОТОВО! Добавлено персонажей: {total_added}")


def top_anime():
    """Топ популярных аниме"""
    count_str = input("\n📊 Сколько аниме взять из топа? [10]: ").strip()
    top_count = int(count_str) if count_str else 10

    chars_limit, filter_gender, download_images = ask_options()

    confirm = input(f"\n⚠️ Займёт ~{top_count * 5} сек. Продолжить? (y/n) [y]: ").lower()
    if confirm == "n":
        return

    # GraphQL для топа
    gql = """
    query ($perPage: Int) {
      Page(perPage: $perPage) {
        media(type: ANIME, sort: [POPULARITY_DESC]) {
          id
          title {
            romaji
            english
            native
          }
          genres
          startDate { year }
        }
      }
    }
    """

    data = api_query(gql, {"perPage": min(top_count, 50)})
    if not data:
        print("❌ Не удалось загрузить топ")
        return

    top_list = data["Page"]["media"]
    print(f"\n📋 Топ {len(top_list)} аниме готовы")

    total_added = 0
    for i, anime in enumerate(top_list, 1):
        title = anime["title"].get("english") or anime["title"]["romaji"]
        print(f"\n[{i}/{len(top_list)}] === {title} ===")
        added = import_anime(
            anime,
            chars_limit=chars_limit,
            download_images=download_images,
            filter_gender=filter_gender,
        )
        total_added += added

    print(f"\n🎉 ГОТОВО! Добавлено: {total_added}")


# ============================================
# ЗАПУСК
# ============================================
if __name__ == "__main__":
    try:
        interactive_menu()
    except KeyboardInterrupt:
        print("\n\n👋 Прервано")