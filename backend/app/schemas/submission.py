from pydantic import BaseModel
from datetime import datetime

class SubmissionCreate(BaseModel):
    task_id: int
    code_text: str
    language: str

class SubmissionResponse(BaseModel):
    id: int
    task_id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True