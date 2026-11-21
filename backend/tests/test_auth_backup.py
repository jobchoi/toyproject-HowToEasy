import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.auth import (Credentials, AccountIn, admin, create_account, current_user, hash_password,
                      login, logout, verify_password)
from app.backups import RestoreIn, backup, list_backups, restore, REQUIRED_HISTORY_TRIGGERS
from app.space_api import move_assignment, MoveIn, end_assignment, EndIn, deactivate_seat
from app.database.db import initialize_database
from app.models.student import Student


class AuthBackupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f'sqlite:///{self.tmp.name}/test.db')
        initialize_database(self.engine)
        self.db = Session(self.engine)
        for name, role in [('operator', 'admin'), ('worker', 'staff')]:
            self.db.execute(text('INSERT INTO staff_accounts (username,password_hash,role) VALUES (:n,:p,:r)'),
                            {'n': name, 'p': hash_password('synthetic-passphrase'), 'r': role})
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tmp.cleanup()

    def signed_in(self, username):
        result = login(Credentials(username=username, password='synthetic-passphrase'), self.db)
        request = SimpleNamespace(headers={'Authorization': 'Bearer ' + result['token']})
        return request, current_user(request, self.db)

    def test_authentication_and_roles(self):
        first, second = hash_password('synthetic-passphrase'), hash_password('synthetic-passphrase')
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password('synthetic-passphrase', first))
        self.assertFalse(verify_password('wrong', first))
        with self.assertRaises(HTTPException): current_user(SimpleNamespace(headers={}), self.db)
        with self.assertRaises(HTTPException): login(Credentials(username='worker', password='incorrect'), self.db)
        request, staff = self.signed_in('worker')
        with self.assertRaises(HTTPException) as error: admin(staff)
        self.assertEqual(error.exception.status_code, 403)
        _, operator = self.signed_in('operator')
        self.assertEqual(admin(operator)['role'], 'admin')
        create_account(AccountIn(username='new', password='synthetic-passphrase'), operator, self.db)
        logout(request, staff, self.db)
        with self.assertRaises(HTTPException): current_user(request, self.db)

    def test_backup_restore(self):
        request, operator = self.signed_in('operator')
        admin(operator)
        name = backup(self.db)['name']
        self.assertIn(name, list_backups(self.db))
        self.db.execute(text("INSERT INTO spaces (name, uses_seats) VALUES ('temporary', 0)"))
        self.db.commit()
        with self.assertRaises(HTTPException): restore(RestoreIn(name='../test.db'), self.db)
        result = restore(RestoreIn(name=name), self.db)
        self.assertTrue((Path(self.tmp.name) / 'backups' / result['pre_restore_backup']).exists())
        with self.assertRaises(HTTPException): current_user(request, self.db)
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM spaces')).scalar(), 0)
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM staff_accounts')).scalar(), 2)

    def test_restore_rejects_003_and_each_missing_history_trigger(self):
        for missing in (None, *REQUIRED_HISTORY_TRIGGERS):
            with self.subTest(missing=missing):
                name = backup(self.db)['name']
                path = Path(self.tmp.name) / 'backups' / name
                with sqlite3.connect(path) as db:
                    if missing is None:
                        # A genuine 003 schema, without the 004 version or triggers.
                        for trigger in REQUIRED_HISTORY_TRIGGERS:
                            db.execute(f'DROP TRIGGER {trigger}')
                        db.execute("DELETE FROM schema_migrations WHERE version='004_history_protection'")
                    else:
                        db.execute(f'DROP TRIGGER {missing}')
                self.db.execute(text("INSERT INTO spaces (name,uses_seats) VALUES ('preserve current',0)"))
                self.db.commit()
                before_count = self.db.execute(text('SELECT count(*) FROM spaces')).scalar()
                before_backups = list_backups(self.db)
                with self.assertRaises(HTTPException) as error:
                    restore(RestoreIn(name=name), self.db)
                self.assertEqual(error.exception.status_code, 400)
                self.assertEqual(self.db.execute(text('SELECT count(*) FROM spaces')).scalar(), before_count)
                self.assertEqual(list_backups(self.db), before_backups)

    def test_restore_preserves_history_protection_and_normal_operations(self):
        path = Path(self.tmp.name) / 'test.db'
        with sqlite3.connect(path) as db:
            db.executescript("""
                INSERT INTO spaces VALUES (1,'synthetic',1,1);
                INSERT INTO space_users (id,name) VALUES (1,'synthetic');
                INSERT INTO seats VALUES (1,1,'A',1),(2,1,'B',1);
                INSERT INTO assignments VALUES (1,1,1,1,'2020-01-01',NULL);
            """)
            actual = {r[0] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE '%_protect'")}
            self.assertEqual(actual, set(REQUIRED_HISTORY_TRIGGERS))
        name = backup(self.db)['name']
        self.db.execute(text("UPDATE assignments SET ends_on='2020-02-01' WHERE id=1"))
        self.db.commit()
        restore(RestoreIn(name=name), self.db)
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute('SELECT * FROM assignments').fetchall(),
                             [(1,1,1,1,'2020-01-01',None)])
            for sql, message in (
                ('DELETE FROM assignments WHERE id=1', '배정 이력은 삭제'),
                ("INSERT OR REPLACE INTO assignments VALUES (1,1,1,2,'2021-01-01',NULL)", '기존 배정 이력을 덮어쓸'),
                ('DELETE FROM seats WHERE id=1', '배정 이력이 있는 좌석')):
                with self.assertRaisesRegex(sqlite3.IntegrityError, message):
                    db.execute(sql)
        moved = move_assignment(1, MoveIn(space_id=1, seat_id=2, starts_on='2020-02-01'), self.db)['id']
        self.assertNotEqual(moved, 1)
        end_assignment(moved, EndIn(ends_on='2020-03-01'), self.db)
        deactivate_seat(1, self.db)
        self.assertEqual(self.db.execute(text('SELECT id,seat_id,ends_on FROM assignments ORDER BY id')).all(),
                         [(1,1,'2020-02-01'), (moved,2,'2020-03-01')])
        self.assertEqual(self.db.execute(text('SELECT active FROM seats WHERE id=1')).scalar(), 0)

if __name__ == '__main__':
    unittest.main()
