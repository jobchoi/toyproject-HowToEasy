from sqlalchemy import Column, Integer, String
from app.database.db import Base

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    seat_number = Column(Integer, nullable=False)
    student_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    gender = Column(String, nullable=False)
    room_type = Column(String, nullable=False)