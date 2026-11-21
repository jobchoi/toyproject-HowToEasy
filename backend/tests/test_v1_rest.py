"""V1 remaining features: synthetic data in temporary files only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
import sqlite3
from threading import Barrier

import pytest
from sqlalchemy import create_engine, text
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
    engine, path = database
    with Session(engine) as db:
        assert report(1, date(2090, 1, 1), db)['assignments'][0]['starts_on'] == '2090-01-01'
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
        with sqlite3.connect(path) as check:
            assert check.execute('SELECT count(*) FROM weekly_responses').fetchone() == (0,)
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
        # Store a real response for this same user in another period.
        put_weekly_response(WeeklyResponseIn(user_id=2, slot_id=1, weekday=date(2090, 1, 2).weekday(), status='absent', reason='other period'), db)
        assert db.execute(text('SELECT user_id,slot_id,status,reason FROM weekly_responses')).all() == [
            (2, 1, 'absent', 'other period')]
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


def test_weekday_contract_independent_of_report_calculation(database):
    engine, path = database
    # 2026-01-05 is a known Monday; 2026-01-11 is Sunday.
    # Persist literal weekday numbers, without using date.weekday() to seed expectations.
    with sqlite3.connect(path) as db:
        db.executescript("""
            INSERT INTO operating_periods VALUES (3,2,'calendar','2026-01-05','2026-01-12');
            INSERT INTO time_slots VALUES (4,3,'calendar','09:00','10:00');
            INSERT INTO assignments VALUES (3,2,2,NULL,'2026-01-05',NULL);
            INSERT INTO weekly_responses VALUES
                (2,4,0,'attending','Monday'), (2,4,6,'absent','Sunday');
        """)
    with Session(engine) as db:
        assert report(3, date(2026, 1, 5), db)['assignments'][0]['responses'] == [
            {'slot_id': 4, 'status': 'attending', 'reason': 'Monday'}]
        assert report(3, date(2026, 1, 11), db)['assignments'][0]['responses'] == [
            {'slot_id': 4, 'status': 'absent', 'reason': 'Sunday'}]
        assert report(3, date(2026, 1, 6), db)['assignments'][0]['responses'][0]['status'] is None


def test_inactive_seat_keeps_historical_assignment(database):
    engine, _ = database
    with Session(engine) as db:
        # End in the past so deactivation is allowed for the historical seat.
        db.execute(text("INSERT INTO assignments VALUES (3,2,1,3,'2020-01-01','2020-02-01')"))
        db.execute(text("INSERT INTO operating_periods VALUES (3,1,'history','2020-01-01','2020-03-01')"))
        db.execute(text('UPDATE seats SET active=0 WHERE id=3'))
        db.commit()
        historical = report(3, date(2020, 1, 15), db)
        seat = next(s for s in historical['seats'] if s['id'] == 3)
        assert seat['active'] == 0
        assert seat['assignment']['id'] == 3
        assert seat['assignment']['user_id'] == 2
        assert all(s['id'] != 3 for s in report(3, date(2020, 2, 1), db)['seats'])
