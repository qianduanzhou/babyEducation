import os
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


settings = get_settings()

if settings.database_url.startswith("sqlite:///"):
    db_path = settings.database_url.replace("sqlite:///", "", 1)
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def migrate_database() -> None:
    """Apply the small SQLite migration needed by existing local installs."""
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "ai_configs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("ai_configs")}
    image_columns = {
        "image_model": "VARCHAR(160) NOT NULL DEFAULT 'gpt-image-2'",
        "image_base_url": "VARCHAR(500) NOT NULL DEFAULT ''",
        "image_api_key": "TEXT NOT NULL DEFAULT ''",
        "image_headers": "TEXT NOT NULL DEFAULT '{}'",
    }
    with engine.begin() as connection:
        for name, definition in image_columns.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE ai_configs ADD COLUMN {name} {definition}"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
