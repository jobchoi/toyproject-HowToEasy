"""V1 remaining features: synthetic data in temporary files only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
import sqlite3
from threading import Barrier

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.db import initialize_database
from app.space_api import (report, WeeklyResponseIn, put_weekly_response,
                           create_assignment, AssignmentIn)
from fastapi import HTTPException


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'synthetic.db'
    engine = create_engine(f'sqlite:///{path}')
    initialize_database(engine)
    with sqlite3.connect(path) as db:
        db.executescript("""
            PRAGMA foreign_keys=ON;
            INSERT INTO spaces VALUES (1,'합성 자습실',1,1),(2,'합성 작업실',0,0);
            INSERT INTO space_users (id,name) VALUES (1,'합성 가'),(2,'합성 나');
            INSERT INTO seats VALUES (1,1,'A',1),(2,1,'B',1),(3,1,'C',1);
            INSERT INTO operating_periods VALUES
                (1,1,'합성 1월','2090-01-01','2090-02-01'),
                (2,2,'합성 작업','2090-01-01','2090-02-01');
            INSERT INTO time_slots VALUES (1,1,'오전','09:00','10:00'),
                (2,1,'오후','13:00','14:00'),(3,2,'작업','09:00','10:00');
            INSERT INTO assignments VALUES (1,1,1,1,'2090-01-01','2090-01-15'),
                (2,1,1,2,'2090-01-15',NULL);
        """)
    yield engine, path
    engine.dispose()


def test_weekly_report_period_boundary_and_clear(database):
    engine, _ = database
    with Session(engine) as db:
        on = date(2090, 1, 2)
        put_weekly_response(WeeklyResponseIn(user_id=1, slot_id=1, weekday=on.weekday(), status='absent', reason='합성 사유'), db)
        for day in (on, date(2090, 1, 9)):
            result = report(1, day, db)
            assert result['assignments'][0]['responses'] == [
                {'slot_id': 1, 'status': 'absent', 'reason': '합성 사유'},
                {'slot_id': 2, 'status': None, 'reason': None}]
        assert report(1, date(2090, 1, 3), db)['assignments'][0]['responses'][0]['status'] is None
        assert report(1, date(2090, 1, 14), db)['assignments'][0]['seat_id'] == 1
        assert report(1, date(2090, 1, 15), db)['assignments'][0]['seat_id'] == 2
        assert report(1, on, db)['seats'][2]['assignment'] is None
        put_weekly_response(WeeklyResponseIn(user_id=1, slot_id=1, weekday=on.weekday()), db)
        assert report(1, on, db)['assignments'][0]['responses'][0]['status'] is None
        for day in (date(2089, 12, 31), date(2090, 2, 1)):
            with pytest.raises(HTTPException) as error:
                report(1, day, db)
            assert error.value.status_code == 400
        with pytest.raises(HTTPException):
            report(999, on, db)


def test_seatless_report_and_period_isolation(database):
    engine, _ = database
    with Session(engine) as db:
        create_assignment(AssignmentIn(user_id=2, space_id=2, starts_on='2090-01-01'), db)
        result = report(2, date(2090, 1, 2), db)
        assert result['seats'] == []
        assert [s['id'] for s in result['slots']] == [3]
        assert result['assignments'][0]['seat_id'] is None
        assert result['assignments'][0]['responses'][0]['status'] is None


def test_history_cannot_be_deleted_or_replaced(database):
    _, path = database
    with sqlite3.connect(path) as db:
        for sql in ('DELETE FROM assignments WHERE id=1',
                    "INSERT OR REPLACE INTO assignments VALUES (1,2,1,3,'2091-01-01',NULL)",
                    'DELETE FROM seats WHERE id=1'):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
        assert db.execute('SELECT seat_id FROM assignments WHERE id=1').fetchone() == (1,)


@pytest.mark.parametrize('same_user', [False, True])
def test_concurrent_assignment_conflict(database, same_user):
    _, path = database
    barrier = Barrier(2)
    def write(index):
        with sqlite3.connect(path, timeout=10) as db:
            db.execute('PRAGMA foreign_keys=ON')
            barrier.wait(timeout=5)
            try:
                db.execute('INSERT INTO assignments (user_id,space_id,seat_id,starts_on) VALUES (?,1,?,?)',
                           (2 if same_user else index + 1, index + 1 if same_user else 3, '2100-01-01'))
                db.commit()
                return 'saved'
            except sqlite3.IntegrityError:
                db.rollback()
                return 'conflict'
    # End the seeded assignment before the competing interval.
    with sqlite3.connect(path) as db:
        db.execute("UPDATE assignments SET ends_on='2090-02-01' WHERE id=2")
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, range(2))) == ['conflict', 'saved']
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM assignments WHERE starts_on='2100-01-01'").fetchone()[0] == 1
