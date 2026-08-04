# config.example.py — этот файл заливается на GitHub

BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"  # От @BotFather
ADMIN_ID = 123456789                      # Твой Telegram ID

WEBAPP_URL = "https://your-url.ngrok-free.app"

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8080

DATABASE_URL = "sqlite:///anime_cards.db"

CLAIM_INTERVAL_HOURS = 6
CLAIM_AMOUNT = 150

SINGLE_PULL_COST = 100
MULTI_PULL_COST = 270
MULTI_PULL_COUNT = 3

SOFT_PITY = 50
HARD_PITY = 90

DUPLICATE_COINS = {
    "common": 5,
    "uncommon": 10,
    "rare": 25,
    "epic": 50,
    "legendary": 100,
    "mythical": 250,
    "secret": 500,
    "unique": 0,
}

RARITY_WEIGHTS = {
    "common": 45.0,
    "uncommon": 25.0,
    "rare": 15.0,
    "epic": 10.0,
    "legendary": 4.0,
    "mythical": 0.9,
    "secret": 0.1,
}