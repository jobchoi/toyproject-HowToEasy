"""Create the first operator interactively, without exposing a password in arguments."""
import getpass
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database.db import engine, initialize_database
from app.models.student import Student  # register the existing model
from app.auth import hash_password


def main():
    initialize_database(engine)
    username = input('운영자 아이디: ').strip()
    if not username or len(username) > 100:
        raise SystemExit('아이디를 확인하세요')
    password = getpass.getpass('비밀번호 (8자 이상): ')
    if len(password) < 8 or len(password) > 1024 or password != getpass.getpass('비밀번호 확인: '):
        raise SystemExit('비밀번호가 유효하지 않거나 일치하지 않습니다')
    with Session(engine) as db:
        # A write lock prevents two initializers from creating operators concurrently.
        db.execute(text('BEGIN IMMEDIATE'))
        if db.execute(text('SELECT 1 FROM staff_accounts LIMIT 1')).first():
            raise SystemExit('이미 담당자 계정이 있습니다')
        db.execute(text("INSERT INTO staff_accounts (username, password_hash, role) VALUES (:name, :password, 'admin')"),
                   {'name': username, 'password': hash_password(password)})
        db.commit()
    print('최초 운영자를 생성했습니다')


if __name__ == '__main__':
    main()
