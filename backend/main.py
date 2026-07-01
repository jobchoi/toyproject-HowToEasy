from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from app.database.db import get_db, engine, Base
from app.models.student import Student

Base.metadata.create_all(bind=engine)

app = FastAPI()

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