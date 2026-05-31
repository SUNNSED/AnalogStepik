from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_teacher, get_current_user
from app.db.database import get_db
from app.db.models import Course, Enrollment, Task, TestCase, User
from app.schemas.task import TaskCreate, TaskResponse

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("/", response_model=TaskResponse)
async def create_task(
    task_in: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    if task_in.course_id is not None:
        course_result = await db.execute(select(Course).where(Course.id == task_in.course_id))
        course = course_result.scalar_one_or_none()

        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        if course.teacher_id != current_user.id and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Only course author or admin can add tasks")

    new_task = Task(
        title=task_in.title,
        description=task_in.description,
        course_id=task_in.course_id,
    )

    db.add(new_task)
    await db.flush()

    db_test_cases = [
        TestCase(
            task_id=new_task.id,
            input_data=test.input_data,
            expected_output=test.expected_output,
            is_hidden=test.is_hidden,
        )
        for test in task_in.test_cases
    ]

    db.add_all(db_test_cases)
    await db.commit()

    stmt = select(Task).filter(Task.id == new_task.id).options(selectinload(Task.test_cases))
    result = await db.execute(stmt)
    db_task = result.scalars().first()

    return db_task


@router.get("/", response_model=list[TaskResponse])
async def get_tasks(
    course_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Task).options(selectinload(Task.test_cases)).order_by(Task.id.desc())

    if current_user.is_admin:
        stmt = stmt.where(Task.course_id.is_not(None))
    elif current_user.is_teacher:
        stmt = stmt.join(Course, Course.id == Task.course_id).where(Course.teacher_id == current_user.id)
    else:
        stmt = (
            stmt.join(Enrollment, Enrollment.course_id == Task.course_id)
            .where(Enrollment.user_id == current_user.id)
        )

    if course_id is not None:
        stmt = stmt.where(Task.course_id == course_id)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Task).filter(Task.id == task_id).options(selectinload(Task.test_cases))
    result = await db.execute(stmt)
    task = result.scalars().first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.is_admin:
        return task

    if task.course_id is None:
        if current_user.is_teacher:
            return task
        raise HTTPException(status_code=403, detail="Task is not available")

    course_result = await db.execute(select(Course).where(Course.id == task.course_id))
    course = course_result.scalar_one_or_none()

    if current_user.is_teacher:
        if course and course.teacher_id == current_user.id:
            return task
        raise HTTPException(status_code=403, detail="Only course author or admin can open this task by id")

    enrollment_result = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == current_user.id,
            Enrollment.course_id == task.course_id,
        )
    )

    if not enrollment_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You are not enrolled in this task course")

    return task
