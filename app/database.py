import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# --- Строка подключения ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:rootpassword@localhost:5432/org_db")

# --- Создание движка ---
engine = create_engine(DATABASE_URL)

# --- Настройка сессий ---
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Базовый класс для моделей ---
Base = declarative_base()

# --- Зависимость для FastAPI ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()