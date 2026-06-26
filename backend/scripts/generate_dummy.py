import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database.db import engine, SessionLocal, Base
from app.models.student import Student
import random

# 테이블 생성
Base.metadata.create_all(bind=engine)

# 더미 데이터 설정
LAST_NAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임"]
FIRST_NAMES = ["민준", "서연", "도윤", "서윤", "시우", "지우", "주원", "하은", "지호", "지민"]
ROOM_TYPES = ["정독", "일반"]
GENDERS = ["남", "여"]

def generate_students(count=50):
    db = SessionLocal()
    try:
        # 기존 데이터 초기화
        db.query(Student).delete()

        students = []
        for i in range(1, count + 1):
            student = Student(
                seat_number=i,
                student_id=f"2024{str(i).zfill(3)}",
                name=random.choice(LAST_NAMES) + random.choice(FIRST_NAMES),
                gender=random.choice(GENDERS),
                room_type=random.choice(ROOM_TYPES)
            )
            students.append(student)

        db.add_all(students)
        db.commit()
        print(f"✅ 학생 {count}명 생성 완료")

        # 결과 확인
        result = db.query(Student).all()
        print(f"\n📊 정독실: {sum(1 for s in result if s.room_type == '정독')}명")
        print(f"📊 일반실: {sum(1 for s in result if s.room_type == '일반')}명")

    finally:
        db.close()

if __name__ == "__main__":
    generate_students()