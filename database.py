# database.py
from sqlalchemy import (
    create_engine, Column, Integer, String,
    Boolean, DateTime, ForeignKey, Text, BigInteger
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from config import DATABASE_URL

Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

RARITY_INFO = {
    "common":    {"stars": 1, "emoji": "⬜", "name": "Обычная",     "color": "#9e9e9e", "order": 1},
    "uncommon":  {"stars": 2, "emoji": "🟩", "name": "Необычная",   "color": "#4caf50", "order": 2},
    "rare":      {"stars": 3, "emoji": "🟦", "name": "Редкая",      "color": "#2196f3", "order": 3},
    "epic":      {"stars": 4, "emoji": "🟪", "name": "Эпическая",   "color": "#9c27b0", "order": 4},
    "legendary": {"stars": 5, "emoji": "🟨", "name": "Легендарная",  "color": "#ff9800", "order": 5},
    "mythical":  {"stars": 6, "emoji": "🟥", "name": "Мифическая",  "color": "#f44336", "order": 6},
    "secret":    {"stars": 7, "emoji": "💠", "name": "Секретная",   "color": "#00e5ff", "order": 7},
    "unique":    {"stars": 8, "emoji": "👑", "name": "Уникальная",  "color": "#ff00ff", "order": 8},
}


class Anime(Base):
    __tablename__ = "anime"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title_en = Column(String(300), nullable=False, unique=True)
    title_ru = Column(String(300), nullable=True)
    genre = Column(String(200), nullable=True)
    characters = relationship("Character", back_populates="anime", cascade="all, delete-orphan")


class Character(Base):
    __tablename__ = "characters"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name_en = Column(String(200), nullable=False)
    name_ru = Column(String(200), nullable=True)
    name_jp = Column(String(200), nullable=True, default="")
    anime_id = Column(Integer, ForeignKey("anime.id"), nullable=True)
    rarity = Column(String(20), nullable=False, default="common")
    image_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    tags = Column(String(500), nullable=True)
    power = Column(Integer, default=50)
    defense = Column(Integer, default=50)
    speed = Column(Integer, default=50)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    anime = relationship("Anime", back_populates="characters")

    @property
    def display_name(self):
        return self.name_ru or self.name_en

    @property
    def anime_title(self):
        return (self.anime.title_ru or self.anime.title_en) if self.anime else "?"

    @property
    def rarity_info(self):
        return RARITY_INFO.get(self.rarity, RARITY_INFO["common"])


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    coins = Column(Integer, default=0)
    gems = Column(Integer, default=0)
    last_claim = Column(DateTime, nullable=True)
    total_pulls = Column(Integer, default=0)
    pulls_since_pity = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    cards = relationship("UserCard", back_populates="user", cascade="all, delete-orphan")

    @property
    def total_cards(self):
        return len(self.cards)


class UserCard(Base):
    __tablename__ = "user_cards"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    count = Column(Integer, default=1)
    level = Column(Integer, default=1)
    is_favorite = Column(Boolean, default=False)
    obtained_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="cards")
    character = relationship("Character")


class AdminLog(Base):
    __tablename__ = "admin_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    target_user_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Suggestion(Base):
    """Предложенные пользователями карточки"""
    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    user_name = Column(String(100), nullable=True)

    # Данные карточки
    name_en = Column(String(200), nullable=False)
    name_ru = Column(String(200), nullable=True)
    name_jp = Column(String(200), nullable=True)
    anime_title = Column(String(300), nullable=False)
    rarity_suggested = Column(String(20), nullable=True)  # что предложил юзер
    image_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    power = Column(Integer, default=50)
    defense = Column(Integer, default=50)
    speed = Column(Integer, default=50)

    # Статус: pending / approved / rejected
    status = Column(String(20), default="pending", index=True)
    admin_comment = Column(Text, nullable=True)  # причина отказа/комментарий
    reviewed_by = Column(BigInteger, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    # Если одобрено — ссылка на созданную карточку
    created_character_id = Column(Integer, ForeignKey("characters.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(engine)
    print("✅ БД инициализирована")

def get_session():
    return SessionLocal()