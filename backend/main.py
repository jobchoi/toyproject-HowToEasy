from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
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
    db_student = Student(**student.model_dump())
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student