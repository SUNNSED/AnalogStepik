from pydantic import BaseModel
from typing import Optional, List
from typing import Optional
from datetime import datetime

# 1. Схемы для создания и отображения одного теста
class TestCaseCreate(BaseModel):
    input_data: Optional[str] = "" # Optional, так как для простых задач ввода может не быть
    expected_output: str
    is_hidden: bool = False

class TestCaseResponse(BaseModel):
    id: int
    input_data: Optional[str] = ""
    expected_output: str
    is_hidden: bool

    class Config:
        from_attributes = True

# 2. Схемы для задачи
class TaskCreate(BaseModel):
    title: str
    description: str
    test_cases: List[TestCaseCreate]  # Вместо test_input/output теперь список тестов
    course_id: Optional[int] = None

class TaskResponse(BaseModel):
    id: int
    title: str
    description: str
    test_cases: List[TestCaseResponse] # При возврате задачи тоже отдаем список тестов
    course_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True