# 🎴 Anime Cards Bot

Telegram-бот для коллекционирования аниме-карточек с Mini App.

## Установка

```bash
git clone https://github.com/USERNAME/anime-cards-bot
cd anime-cards-bot

python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

pip install -r requirements.txt

# Настройка
cp config.example.py config.py
nano config.py  # вставь BOT_TOKEN, ADMIN_ID, WEBAPP_URL

# Запуск ngrok (в отдельном терминале)
ngrok http 127.0.0.1:8080

# Запуск бота
python run.py
```

## Возможности

- 🎰 Гача-система с 8 редкостями
- 💰 Экономика с ежедневными наградами
- 🎴 Коллекция и альбом персонажей
- 👑 Веб-админка
- 💡 Система предложений от пользователей
- 🖼 Загрузка картинок

## Технологии

- Python 3.9+
- Aiogram 3.x
- FastAPI
- SQLAlchemy
- Telegram Mini App
```

---

## 📋 Порядок действий

```
1. Создай .gitignore (код выше)
2. Создай config.example.py (шаблон без секретов)
3. Убедись что config.py — В gitignore
4. Проверь: git status → config.py НЕ должно быть в списке
5. Инициализируй git:
   git init
   git add .
   git commit -m "Initial commit"
6. Создай репо на GitHub (можно приватный!)
7. git remote add origin URL_РЕПО
   git branch -M main
   git push -u origin main
```