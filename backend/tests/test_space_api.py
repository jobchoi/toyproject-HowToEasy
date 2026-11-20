import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from app.database.db import initialize_database
from app.models.student import Student  # register the legacy model
from app.space_api import (SpaceIn, UserIn, SeatIn, AssignmentIn, MoveIn, create_space,
    create_user, create_seat, create_assignment, move_assignment, assignments,
    deactivate_seat, update_user)

class SpaceApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / 'test.db'
        self.engine = create_engine(f'sqlite:///{path}')
        event.listen(self.engine, 'connect', lambda connection, _: connection.execute('PRAGMA foreign_keys=ON'))
        initialize_database(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tmp.cleanup()

    def test_assign_move_and_rollback(self):
        sp = create_space(SpaceIn(name='합성 공간', uses_seats=True), self.db)['id']
        user = create_user(UserIn(name='합성 이용자'), self.db)['id']
        seat1 = create_seat(SeatIn(space_id=sp, number='1'), self.db)['id']
        seat2 = create_seat(SeatIn(space_id=sp, number='2'), self.db)['id']
        with self.assertRaises(HTTPException):
            create_seat(SeatIn(space_id=sp, number='1'), self.db)
        aid = create_assignment(AssignmentIn(user_id=user, space_id=sp, seat_id=seat1, starts_on='2090-01-01'), self.db)['id']
        with self.assertRaises(HTTPException):
            deactivate_seat(seat1, self.db)
        with self.assertRaises(HTTPException):
            move_assignment(aid, MoveIn(space_id=sp, seat_id=999, starts_on='2090-02-01'), self.db)
        self.assertIsNone(assignments(self.db)[0]['ends_on'])
        move_assignment(aid, MoveIn(space_id=sp, seat_id=seat2, starts_on='2090-02-01'), self.db)
        history = assignments(self.db)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[1]['ends_on'], '2090-02-01')
        with self.assertRaises(HTTPException):
            create_assignment(AssignmentIn(user_id=user, space_id=sp, seat_id=seat1, starts_on='2090-02-02'), self.db)
        update_user(user, UserIn(name='수정 이용자'), self.db)

    def test_seatless(self):
        sp = create_space(SpaceIn(name='공용', uses_seats=False), self.db)['id']
        user = create_user(UserIn(name='합성'), self.db)['id']
        with self.assertRaises(HTTPException):
            create_seat(SeatIn(space_id=sp, number='1'), self.db)
        create_assignment(AssignmentIn(user_id=user, space_id=sp, starts_on='2020-01-01', ends_on='2020-02-01'), self.db)
        self.assertIsNone(assignments(self.db)[0]['seat_id'])
