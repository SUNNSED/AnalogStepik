from pydantic import BaseModel, EmailStr

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
    token_type: str