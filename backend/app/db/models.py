from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy import func
from app.db.database import Base
from sqlalchemy.orm import relationship


#Класс для пользователя
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_teacher = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

#Класс для проверки заданий
class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), index=True) #ID самой задачки, позже, после создания таблицы (например, "Task"), надо будет изменить параметры на "ForeignKey("task_id")" ПОДРУЖИЛИ!
    user_id = Column(Integer, ForeignKey("users.id"))
    code_text = Column(Text, nullable=False)
    language = Column(String(50), nullable=False) #Не знаю, зачем добавил, пока что всё-равно только питон будет. Мб позже плюсы добавим
    status = Column(String(50), default="pending")
    output = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

#Класс для тасков
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    test_cases = relationship("TestCase", back_populates="task", cascade="all, delete-orphan")
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), index=True)
    input_data = Column(Text, default="")
    expected_output = Column(Text)
    is_hidden = Column(Boolean, default=False)
    task = relationship("Task", back_populates="test_cases")

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now())
