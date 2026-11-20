from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from app.database.db import get_db, engine, initialize_database
from app.models.student import Student
from app.space_api import router as space_router
from app.auth import router as auth_router, current_user
from app.backups import router as backup_router
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session as AuthSession
import asyncio

@asynccontextmanager
async def lifespan(_app):
    initialize_database(engine)
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(space_router)
app.include_router(auth_router)
app.include_router(backup_router)

# Serialize full requests so a restore cannot overlap another in-process request.
class RequestGuard:
    def __init__(self, app):
        self.app = app
        self.lock = asyncio.Lock()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        async with self.lock:
            path = scope['path']
            protected = ((path.startswith('/api/') and path != '/api/auth/login' and
                          not path.startswith('/api/auth/') and not path.startswith('/api/backups'))
                         or path == '/students')
            if protected and scope['method'] != 'OPTIONS':
                with AuthSession(engine) as db:
                    try:
                        current_user(Request(scope), db)
                    except HTTPException as exc:
                        response = JSONResponse(status_code=exc.status_code, content={'detail': exc.detail})
                        return await response(scope, receive, send)
            await self.app(scope, receive, send)

app.add_middleware(RequestGuard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class StudentCreate(BaseModel):
    seat_number: int
    student_id: str
    name: str
    gender: str
    room_type: str
    
    @field_validator('name', 'student_id')
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('빈 값은 입력할 수 없습니다')
        return v

    @field_validator('gender')
    def valid_gender(cls, v):
        if v not in ['남', '여']:
            raise ValueError('성별은 남/여만 가능합니다')
        return v

    @field_validator('room_type')
    def valid_room_type(cls, v):
        if v not in ['정독', '일반']:
            raise ValueError('자습실 구분은 정독/일반만 가능합니다')
        return v
@app.get("/")
def root():
    return {"message": "자습실 관리 API 정상 동작"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/students")
def get_students(db: Session = Depends(get_db)):
    return db.query(Student).all()

@app.post("/students")
def create_student(student: StudentCreate, db: Session = Depends(get_db)):
    # 중복 좌석번호 체크
    existing = db.query(Student).filter(
        Student.seat_number == student.seat_number
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 사용 중인 좌석번호입니다")

    db_student = Student(**student.model_dump())
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student