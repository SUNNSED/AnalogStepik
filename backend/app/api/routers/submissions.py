from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import Submission, User
from app.schemas.submission import SubmissionCreate, SubmissionResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/submissions", tags=["Submissions"])

@router.post("/", response_model=SubmissionResponse)
async def create_submission(
        sub_in: SubmissionCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    #Формируем запись для базы данных
    new_sub = Submission(
        task_id=sub_in.task_id,
        user_id=current_user.id,
        code_text=sub_in.code_text,
        language=sub_in.language,
        status="pending"
    )

    #Сохраняем в PostgreSQL
    db.add(new_sub)
    await db.commit()
    await db.refresh(new_sub)

    # TODO: На следующем этапе архитектуры здесь будет вызов воркера Celery или прямое обращение к Kubernetes API для создания Job'а проверки

    return new_sub

@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
        submission_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    #Ищем решение в базе
    result = await db.execute(select(Submission).where(Submission.id == submission_id))
    submission = result.scalars().first()

    #Проверяем, существует ли оно
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    #Проверяем, принадлежит ли это решение текущему юзеру
    if submission.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this submission"
        )

    return submission