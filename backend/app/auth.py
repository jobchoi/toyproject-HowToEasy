import hashlib
import hmac
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database.db import get_db

router = APIRouter(prefix='/api/auth')
ITERATIONS = 600_000


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f'pbkdf2_sha256${ITERATIONS}${salt}${digest}'


def verify_password(password, encoded):
    try:
        algorithm, iterations, salt, digest = encoded.split('$')
        if algorithm != 'pbkdf2_sha256':
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


def token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(request: Request, db: Session = Depends(get_db)):
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        raise HTTPException(401, '로그인이 필요합니다')
    token = header[7:]
    account = db.execute(text('''SELECT a.id, a.username, a.role FROM staff_accounts a
        JOIN staff_sessions s ON s.account_id=a.id WHERE s.token_hash=:token AND s.expires_at>:now'''),
        {'token': token_digest(token), 'now': int(time.time())}).mappings().first()
    if not account:
        raise HTTPException(401, '세션이 만료되었거나 유효하지 않습니다')
    return dict(account)


def admin(user=Depends(current_user)):
    if user['role'] != 'admin':
        raise HTTPException(403, '운영자 권한이 필요합니다')
    return user


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=1024)


class AccountIn(Credentials):
    role: str = 'staff'


@router.post('/login')
def login(value: Credentials, db: Session = Depends(get_db)):
    account = db.execute(text('SELECT * FROM staff_accounts WHERE username=:name'), {'name': value.username}).mappings().first()
    if not account or not verify_password(value.password, account['password_hash']):
        raise HTTPException(401, '아이디 또는 비밀번호가 올바르지 않습니다')
    token = secrets.token_urlsafe(32)
    db.execute(text('DELETE FROM staff_sessions WHERE expires_at <= :now'), {'now': int(time.time())})
    db.execute(text('INSERT INTO staff_sessions VALUES (:token, :account, :expires)'),
               {'token': token_digest(token), 'account': account['id'], 'expires': int(time.time()) + 12 * 3600})
    db.commit()
    return {'token': token, 'username': account['username'], 'role': account['role']}


@router.get('/me')
def me(user=Depends(current_user)):
    return user


@router.post('/logout')
def logout(request: Request, user=Depends(current_user), db: Session = Depends(get_db)):
    db.execute(text('DELETE FROM staff_sessions WHERE token_hash=:token'), {'token': token_digest(request.headers['Authorization'][7:])})
    db.commit()
    return {'ok': True}


@router.post('/accounts')
def create_account(value: AccountIn, user=Depends(admin), db: Session = Depends(get_db)):
    if value.role not in ('admin', 'staff') or not value.username.strip() or value.username != value.username.strip():
        raise HTTPException(400, '아이디 또는 역할을 확인하세요')
    try:
        db.execute(text('INSERT INTO staff_accounts (username, password_hash, role) VALUES (:name, :password, :role)'),
                   {'name': value.username, 'password': hash_password(value.password), 'role': value.role})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(400, '이미 사용 중인 아이디입니다') from exc
    return {'ok': True}
