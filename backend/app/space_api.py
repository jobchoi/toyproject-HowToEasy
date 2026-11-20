from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.db import get_db

router = APIRouter(prefix='/api')

class SpaceIn(BaseModel):
    name: str
    uses_seats: bool
    study_room: bool = False

    @field_validator('name')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('이름을 입력하세요')
        return value.strip()

class UserIn(BaseModel):
    name: str
    identifier: Optional[str] = None
    student_id: Optional[str] = None
    gender: Optional[str] = None

    @field_validator('name')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('이름을 입력하세요')
        return value.strip()

class SeatIn(BaseModel):
    space_id: int
    number: str

    @field_validator('number')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('좌석번호를 입력하세요')
        return value.strip()

class AssignmentIn(BaseModel):
    user_id: int
    space_id: int
    seat_id: Optional[int] = None
    starts_on: date
    ends_on: Optional[date] = None

class MoveIn(BaseModel):
    space_id: int
    seat_id: Optional[int] = None
    starts_on: date
    ends_on: Optional[date] = None

class EndIn(BaseModel):
    ends_on: date

def rows(db, sql, params=None):
    return [dict(row) for row in db.execute(text(sql), params or {}).mappings()]

def save(db, sql, params):
    try:
        result = db.execute(text(sql), params)
        db.commit()
        return {'id': result.lastrowid}
    except IntegrityError as exc:
        db.rollback()
        message = str(exc.orig)
        if 'UNIQUE constraint failed: seats' in message:
            message = '이미 사용된 좌석번호입니다'
        elif 'FOREIGN KEY constraint failed' in message:
            message = '존재하지 않는 공간, 좌석 또는 이용자입니다'
        elif 'CHECK constraint failed' in message:
            message = '입력값 또는 배정 기간을 확인하세요'
        raise HTTPException(400, message) from exc

@router.get('/spaces')
def spaces(db: Session = Depends(get_db)):
    return rows(db, 'SELECT * FROM spaces ORDER BY id')

@router.post('/spaces')
def create_space(value: SpaceIn, db: Session = Depends(get_db)):
    return save(db, 'INSERT INTO spaces (name, uses_seats, study_room) VALUES (:name, :uses_seats, :study_room)', value.model_dump())

@router.get('/users')
def users(db: Session = Depends(get_db)):
    return rows(db, 'SELECT * FROM space_users ORDER BY id')

@router.post('/users')
def create_user(value: UserIn, db: Session = Depends(get_db)):
    return save(db, 'INSERT INTO space_users (name, identifier, student_id, gender) VALUES (:name, :identifier, :student_id, :gender)', value.model_dump())

@router.put('/users/{user_id}')
def update_user(user_id: int, value: UserIn, db: Session = Depends(get_db)):
    result = db.execute(text('UPDATE space_users SET name=:name, identifier=:identifier, student_id=:student_id, gender=:gender WHERE id=:id'), {**value.model_dump(), 'id': user_id})
    if not result.rowcount:
        raise HTTPException(404, '이용자를 찾을 수 없습니다')
    db.commit()
    return {'id': user_id}

@router.get('/seats')
def seats(db: Session = Depends(get_db)):
    return rows(db, 'SELECT * FROM seats ORDER BY space_id, number')

@router.post('/seats')
def create_seat(value: SeatIn, db: Session = Depends(get_db)):
    return save(db, 'INSERT INTO seats (space_id, number) VALUES (:space_id, :number)', value.model_dump())

@router.post('/seats/{seat_id}/deactivate')
def deactivate_seat(seat_id: int, db: Session = Depends(get_db)):
    try:
        result = db.execute(text('UPDATE seats SET active=0 WHERE id=:id'), {'id': seat_id})
        if not result.rowcount:
            raise HTTPException(404, '좌석을 찾을 수 없습니다')
        db.commit()
        return {'id': seat_id}
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(400, str(exc.orig)) from exc

@router.get('/assignments')
def assignments(db: Session = Depends(get_db)):
    return rows(db, 'SELECT * FROM assignments ORDER BY starts_on DESC, id DESC')

@router.post('/assignments')
def create_assignment(value: AssignmentIn, db: Session = Depends(get_db)):
    return save(db, 'INSERT INTO assignments (user_id, space_id, seat_id, starts_on, ends_on) VALUES (:user_id, :space_id, :seat_id, :starts_on, :ends_on)', value.model_dump(mode='json'))

@router.post('/assignments/{assignment_id}/end')
def end_assignment(assignment_id: int, value: EndIn, db: Session = Depends(get_db)):
    try:
        result = db.execute(text('UPDATE assignments SET ends_on=:end WHERE id=:id AND (ends_on IS NULL OR ends_on > :end)'), {'end': value.ends_on.isoformat(), 'id': assignment_id})
        if not result.rowcount:
            raise HTTPException(400, '배정을 찾을 수 없거나 이미 종료되었습니다')
        db.commit()
        return {'id': assignment_id}
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(400, '종료일은 시작일 이후여야 합니다') from exc

@router.post('/assignments/{assignment_id}/move')
def move_assignment(assignment_id: int, value: MoveIn, db: Session = Depends(get_db)):
    try:
        old = db.execute(text('SELECT * FROM assignments WHERE id=:id'), {'id': assignment_id}).mappings().first()
        if not old or (old['ends_on'] and old['ends_on'] <= value.starts_on.isoformat()):
            raise HTTPException(400, '이동일에 유효한 배정이 없습니다')
        db.execute(text('UPDATE assignments SET ends_on=:end WHERE id=:id'), {'end': value.starts_on.isoformat(), 'id': assignment_id})
        result = db.execute(text('INSERT INTO assignments (user_id, space_id, seat_id, starts_on, ends_on) VALUES (:user_id, :space_id, :seat_id, :starts_on, :ends_on)'), {**value.model_dump(mode='json'), 'user_id': old['user_id']})
        db.commit()
        return {'id': result.lastrowid}
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(400, str(exc.orig)) from exc
