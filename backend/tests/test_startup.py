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
from app.space_api import (spaces, users, seats, assignments, end_assignment, EndIn,
                           move_assignment, MoveIn, deactivate_seat)


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

    def test_upgrade_003_preserves_data_and_history_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.db'
            migrations = Path(__file__).resolve().parents[1] / 'migrations'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE schema_migrations (version TEXT PRIMARY KEY)')
                for migration in sorted(migrations.glob('00[1-3]_*.sql')):
                    db.executescript(migration.read_text())
                    db.execute('INSERT INTO schema_migrations VALUES (?)', (migration.stem,))
                    db.commit()
                self.assertEqual(db.execute('SELECT count(*) FROM schema_migrations').fetchone(), (3,))
                db.executescript("""
                    INSERT INTO spaces VALUES (1,'synthetic',1,1);
                    INSERT INTO space_users (id,name) VALUES (1,'synthetic');
                    INSERT INTO seats VALUES (1,1,'A',1),(2,1,'B',1);
                    INSERT INTO assignments VALUES (1,1,1,1,'2020-01-01','2020-02-01'),
                        (2,1,1,2,'2020-02-01',NULL);
                    INSERT INTO operating_periods VALUES (1,1,'synthetic','2020-01-01','2021-01-01');
                    INSERT INTO time_slots VALUES (1,1,'synthetic','09:00','10:00');
                    INSERT INTO weekly_responses VALUES (1,1,0,'absent','synthetic');
                """)
                tables = ('spaces', 'space_users', 'seats', 'assignments',
                          'operating_periods', 'time_slots', 'weekly_responses')
                before = {table: db.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall() for table in tables}
            engine = create_engine(f'sqlite:///{path}')
            async def start():
                async with main.lifespan(main.app):
                    pass
            try:
                with patch.object(main, 'engine', engine):
                    asyncio.run(start())  # Upgrade existing 003 data to 004.
                    asyncio.run(start())  # Restart must preserve both data and protection.
                with sqlite3.connect(path) as db:
                    for table in tables:
                        self.assertEqual(db.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall(), before[table])
                    self.assertIsNotNone(db.execute("SELECT 1 FROM schema_migrations WHERE version='004_history_protection'").fetchone())
                    for sql, message in (
                        ('DELETE FROM assignments WHERE id=1', '배정 이력은 삭제'),
                        ("INSERT OR REPLACE INTO assignments VALUES (1,1,1,1,'2021-01-01','2021-02-01')", '기존 배정 이력을 덮어쓸'),
                        ('DELETE FROM seats WHERE id=1', '배정 이력이 있는 좌석')):
                        with self.assertRaisesRegex(sqlite3.IntegrityError, message):
                            db.execute(sql)
                    self.assertEqual(db.execute('SELECT * FROM assignments ORDER BY id').fetchall(), before['assignments'])
                with Session(engine) as db:
                    moved = move_assignment(2, MoveIn(space_id=1, seat_id=1, starts_on='2020-03-01'), db)['id']
                    self.assertNotIn(moved, (1, 2))
                    end_assignment(moved, EndIn(ends_on='2020-04-01'), db)
                    deactivate_seat(2, db)
                    self.assertEqual(db.execute(text('SELECT id,ends_on FROM assignments ORDER BY id')).all(),
                                     [(1,'2020-02-01'), (2,'2020-03-01'), (moved,'2020-04-01')])
                    self.assertEqual(db.execute(text('SELECT active FROM seats WHERE id=2')).scalar(), 0)
            finally:
                engine.dispose()
