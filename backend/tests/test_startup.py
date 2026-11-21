import asyncio
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from app.space_api import spaces, users, seats, assignments


class StartupTest(unittest.TestCase):
    def test_fresh_and_legacy_database_start_twice(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'study_room.db'
                if legacy:
                    with sqlite3.connect(path) as db:
                        db.execute('CREATE TABLE students (id INTEGER PRIMARY KEY, seat_number INTEGER NOT NULL, student_id TEXT NOT NULL, name TEXT NOT NULL, gender TEXT NOT NULL, room_type TEXT NOT NULL)')
                        db.execute("INSERT INTO students VALUES (1, 1, 'synthetic', 'test', '남', '일반')")
                engine = create_engine(f'sqlite:///{path}')
                async def start():
                    async with main.lifespan(main.app):
                        pass
                with patch.object(main, 'engine', engine):
                    asyncio.run(start())
                    with Session(engine) as db:
                        for endpoint in (spaces, users, seats, assignments):
                            self.assertEqual(endpoint(db), [])
                        db.execute(text("INSERT INTO spaces (name, uses_seats) VALUES ('test', 0)"))
                        db.commit()
                    asyncio.run(start())
                with sqlite3.connect(path) as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM spaces').fetchone()[0], 1)
                    self.assertEqual({r[0] for r in db.execute('SELECT version FROM schema_migrations')}, {'001_space_utilization', '002_weekly_responses', '003_auth', '004_history_protection'})
                    if legacy:
                        self.assertEqual(db.execute('SELECT student_id FROM students').fetchone()[0], 'synthetic')
                engine.dispose()

    def test_partial_untracked_schema_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.db'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE spaces (id INTEGER PRIMARY KEY)')
            engine = create_engine(f'sqlite:///{path}')
            with self.assertRaises(Exception):
                main.initialize_database(engine)
            with sqlite3.connect(path) as db:
                self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='space_users'").fetchone())
            engine.dispose()
