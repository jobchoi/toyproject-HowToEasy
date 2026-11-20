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
from app.backups import RestoreIn, backup, list_backups, restore
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

if __name__ == '__main__':
    unittest.main()
