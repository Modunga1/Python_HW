import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/orders_db")


engine = create_engine(DATABASE_URL, echo=False, future=True)

SessionLocal = sessionmaker(bind=engine, future=True)

# Простейшая инициализация таблицы orders
def init_db():
    with engine.connect() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            item_name VARCHAR(255) NOT NULL,
            status VARCHAR(50) NOT NULL
        )
        """))
        conn.commit()
