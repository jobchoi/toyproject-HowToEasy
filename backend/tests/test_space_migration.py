"""공간 스키마 검증. 모든 데이터는 메모리 SQLite에만 생성한다."""
import pathlib
import sqlite3
import unittest

MIGRATION = pathlib.Path(__file__).resolve().parents[1] / 'migrations' / '001_space_utilization.sql'


class SpaceSchemaTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT); INSERT INTO students VALUES (1, "synthetic");')
        self.db.executescript(MIGRATION.read_text())
        self.db.executescript("""
            INSERT INTO spaces VALUES (1, '자습실', 1, 1), (2, '작업실', 0, 0), (3, '다른 방', 1, 0);
            INSERT INTO space_users (id, name) VALUES (1, '가상1'), (2, '가상2');
            INSERT INTO seats (id, space_id, number) VALUES (1, 1, '1'), (2, 1, '2'), (3, 3, '1');
        """)

    def tearDown(self):
        self.db.close()

    def test_students_preserved_and_space_unique_seats(self):
        self.assertEqual(self.db.execute('SELECT name FROM students').fetchone(), ('synthetic',))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO seats (space_id, number) VALUES (1, '1')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO seats (space_id, number) VALUES (2, '1')")

    def test_assignment_overlap_and_adjacent_move(self):
        self.db.execute("INSERT INTO assignments VALUES (1, 1, 1, 1, '2026-01-01', '2026-02-01')")
        for values in [(2, 2, 1, 1, '2026-01-31', None), (2, 1, 1, 2, '2026-01-31', None)]:
            with self.assertRaises(sqlite3.IntegrityError):
                self.db.execute('INSERT INTO assignments VALUES (?, ?, ?, ?, ?, ?)', values)
        self.db.execute("INSERT INTO assignments VALUES (2, 1, 1, 2, '2026-02-01', NULL)")
        self.assertEqual(self.db.execute('SELECT seat_id FROM assignments WHERE user_id = 1 ORDER BY starts_on').fetchall(), [(1,), (2,)])
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE assignments SET ends_on = '2026-02-02' WHERE id = 1")

    def test_seatless_and_deactivation(self):
        self.db.execute("INSERT INTO assignments VALUES (1, 1, 2, NULL, '2099-01-01', NULL)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO assignments VALUES (2, 2, 2, 1, '2099-01-01', NULL)")
        self.db.execute("INSERT INTO assignments VALUES (2, 2, 1, 1, '2099-01-01', NULL)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute('UPDATE seats SET active = 0 WHERE id = 1')
        self.db.execute("UPDATE assignments SET ends_on = '2099-02-01' WHERE id = 2")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute('UPDATE seats SET active = 0 WHERE id = 1')
        self.db.execute("UPDATE assignments SET starts_on = starts_on WHERE id = 2")
        self.db.execute('UPDATE seats SET active = 0 WHERE id = 2')
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO assignments VALUES (3, 2, 1, 2, '2100-01-01', NULL)")

    def test_period_and_slot_constraints(self):
        self.db.execute("INSERT INTO operating_periods VALUES (1, 1, '봄', '2026-03-01', '2026-04-01')")
        self.db.execute("INSERT INTO time_slots VALUES (1, 1, '오전', '09:00', '12:00')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO operating_periods VALUES (2, 1, '오류', '2026-04-01', '2026-03-01')")


if __name__ == '__main__':
    unittest.main()
