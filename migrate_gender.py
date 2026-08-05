# migrate_gender.py
from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE characters ADD COLUMN gender VARCHAR(20)"))
        conn.commit()
        print("✅ Колонка gender добавлена")
    except Exception as e:
        print(f"⚠️ {e}")