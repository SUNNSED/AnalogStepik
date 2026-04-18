from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy import func
from backend.app.db.database import Base

#Класс для пользователя
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

#Класс для проверки заданий
class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, index=True) #ID самой задачки, позже, после создания таблицы (например, "Task"), надо будет изменить параметры на "ForeignKey("task_id")"
    user_id = Column(Integer, ForeignKey("users.id"))
    code_text = Column(Text, nullable=False)
    language = Column(String(50), nullable=False) #Не знаю, зачем добавил, пока что всё-равно только питон будет. Мб позже плюсы добавим
    status = Column(String(50), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
