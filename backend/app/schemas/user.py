from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import List, Optional
from app.schemas.course import CourseResponse

# Что мы ждем при регистрации
class UserCreate(BaseModel):
    email: EmailStr
    password: str

# Что мы отдаем при запросе данных профиля
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool

    class Config:
        from_attributes = True

# Формат ответа с токеном
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class RefreshToken(BaseModel):
    refresh_token: str


class UserProfileResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    is_teacher: bool
    created_at: datetime
    enrolled_courses: List[CourseResponse] = []

    class Config:
        from_attributes = True


class UserStatsResponse(BaseModel):
    total_submissions: int = 0
    correct_submissions: int = 0
    accuracy: float = 0.0
    courses_enrolled: int = 0