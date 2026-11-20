from pathlib import Path
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./study_room.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

@event.listens_for(engine, "connect")
def enable_foreign_keys(connection, _record):
    connection.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialize_database(target_engine):
    """Prepare the schema once; an incomplete or untracked migration fails safely."""
    Base.metadata.create_all(bind=target_engine)
    migrations = sorted((Path(__file__).resolve().parents[2] / "migrations").glob("*.sql"))
    connection = target_engine.raw_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)")
        for migration in migrations:
            version = migration.stem
            if cursor.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (version,)).fetchone():
                continue
            statement = ""
            for line in migration.read_text(encoding="utf-8").splitlines(keepends=True):
                statement += line
                if sqlite3.complete_statement(statement):
                    sql = statement.strip()
                    if not any(sql.endswith(command) for command in ("PRAGMA foreign_keys = ON;", "BEGIN;", "COMMIT;")):
                        cursor.execute(statement)
                    statement = ""
            if statement.strip():
                raise ValueError(f"불완전한 마이그레이션: {version}")
            cursor.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
