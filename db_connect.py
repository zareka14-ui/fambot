import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.shopping_item import Base

# Путь, где будет храниться файл базы данных (внутри папки data/)
DATABASE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'family_bot.db')
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

# Создаем папку data, если она не существует
os.makedirs(os.path.dirname(DATABASE_FILE), exist_ok=True)


def init_db():
    """
    Инициализирует подключение к базе данных SQLite и создает таблицы.
    """
    # 1. Создание Engine
    # connect_args={"check_same_thread": False} требуется для SQLite
    # при использовании его в асинхронной среде.
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
    
    # 2. Создание таблиц (если они еще не существуют)
    Base.metadata.create_all(bind=engine)
    
    # 3. Настройка сессии
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    return SessionLocal

# Глобальный объект для доступа к сессиям
SessionLocal = init_db()

def get_db():
    """
    Генератор для получения сессии базы данных. 
    Используется для dependency injection в асинхронных функциях.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()