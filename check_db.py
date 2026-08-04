# check_db.py
from database import get_session, Suggestion
from sqlalchemy import inspect
from database import engine

inspector = inspect(engine)
tables = inspector.get_table_names()

print("📊 Таблицы в БД:")
for t in tables:
    print(f"  • {t}")

if "suggestions" not in tables:
    print("\n❌ ТАБЛИЦА suggestions НЕ СОЗДАНА!")
else:
    print("\n✅ Таблица suggestions есть")

    # Проверим количество записей
    db = get_session()
    try:
        count = db.query(Suggestion).count()
        pending = db.query(Suggestion).filter(Suggestion.status == "pending").count()
        print(f"\n📬 Всего предложений: {count}")
        print(f"⏳ На проверке: {pending}")

        # Покажем последние 5
        latest = db.query(Suggestion).order_by(Suggestion.id.desc()).limit(5).all()
        print("\n📝 Последние 5:")
        for s in latest:
            print(f"  #{s.id} | {s.status} | {s.name_en} | от user {s.user_id}")
    finally:
        db.close()

    # Проверим колонки
    columns = [col['name'] for col in inspector.get_columns('suggestions')]
    print(f"\n🔍 Колонки suggestions: {columns}")
    if 'image_url' not in columns:
        print("⚠️  Нет колонки image_url — нужно пересоздать БД")