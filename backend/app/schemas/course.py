from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from app.schemas.task import TaskResponse


class CourseCreate(BaseModel):
    title: str
    description: str


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class CourseResponse(BaseModel):
    id: int
    title: str
    description: str
    teacher_id: int
    created_at: datetime
    is_enrolled: Optional[bool] = False
    progress_status: Optional[str] = None
    progress_label: Optional[str] = None

    class Config:
        from_attributes = True


class CourseDetailResponse(CourseResponse):
    tasks: List[TaskResponse] = []
    students_count: Optional[int] = 0
