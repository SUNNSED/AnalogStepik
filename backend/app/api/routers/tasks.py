from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_teacher, get_current_user
from app.db.database import get_db
from app.db.models import Course, Enrollment, Submission, Task, TestCase, User
from app.schemas.task import TaskCreate, TaskResponse

router = APIRouter(prefix="/tasks", tags=["Tasks"])


TASK_PROGRESS_LABELS = {
    "not_started": "не выполнено",
    "wrong": "выполнено неверно",
    "correct": "выполнено верно",
}


def resolve_task_progress(statuses: list[str]) -> tuple[str, str]:
    normalized = [str(status or "").lower() for status in statuses]

    if "correct" in normalized:
        return "correct", TASK_PROGRESS_LABELS["correct"]

    if statuses:
        return "wrong", TASK_PROGRESS_LABELS["wrong"]

    return "not_started", TASK_PROGRESS_LABELS["not_started"]


async def get_task_progress_map(
    db: AsyncSession,
    current_user: User,
    task_ids: list[int],
) -> dict[int, tuple[str, str]]:
    if not task_ids:
        return {}

    result = await db.execute(
        select(Submission.task_id, Submission.status).where(
            Submission.user_id == current_user.id,
            Submission.task_id.in_(task_ids),
        )
    )

    statuses_by_task: dict[int, list[str]] = defaultdict(list)
    for task_id, status_value in result.all():
        statuses_by_task[task_id].append(status_value)

    return {
        task_id: resolve_task_progress(statuses_by_task.get(task_id, []))
        for task_id in task_ids
    }


def task_response_payload(
    task: Task,
    include_hidden_tests: bool,
    progress: Optional[tuple[str, str]] = None,
) -> dict:
    test_cases = task.test_cases if include_hidden_tests else [
        test for test in task.test_cases if not test.is_hidden
    ]

    payload = {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "test_cases": [
            {
                "id": test.id,
                "input_data": test.input_data,
                "expected_output": test.expected_output,
                "is_hidden": test.is_hidden,
            }
            for test in test_cases
        ],
        "course_id": task.course_id,
        "created_at": task.created_at,
    }

    if progress:
        payload["progress_status"] = progress[0]
        payload["progress_label"] = progress[1]

    return payload


async def ensure_course_can_be_edited(
    db: AsyncSession,
    course_id: Optional[int],
    current_user: User,
) -> None:
    if course_id is None:
        return

    course_result = await db.execute(select(Course).where(Course.id == course_id))
    course = course_result.scalar_one_or_none()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if course.teacher_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only course author or admin can edit tasks")


async def ensure_task_can_be_edited(
    db: AsyncSession,
    task: Task,
    current_user: User,
) -> None:
    if current_user.is_admin:
        return

    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teacher or admin can edit tasks")

    await ensure_course_can_be_edited(db, task.course_id, current_user)


@router.post("/", response_model=TaskResponse)
async def create_task(
    task_in: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    await ensure_course_can_be_edited(db, task_in.course_id, current_user)

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

    return task_response_payload(db_task, include_hidden_tests=True)


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
    include_hidden_tests = current_user.is_admin or current_user.is_teacher
    tasks = result.scalars().all()
    progress_map = await get_task_progress_map(db, current_user, [task.id for task in tasks])

    return [
        task_response_payload(
            task,
            include_hidden_tests=include_hidden_tests,
            progress=progress_map.get(task.id),
        )
        for task in tasks
    ]


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

    progress_map = await get_task_progress_map(db, current_user, [task.id])
    progress = progress_map.get(task.id)

    if current_user.is_admin:
        return task_response_payload(task, include_hidden_tests=True, progress=progress)

    if task.course_id is None:
        if current_user.is_teacher:
            return task_response_payload(task, include_hidden_tests=True, progress=progress)
        raise HTTPException(status_code=403, detail="Task is not available")

    course_result = await db.execute(select(Course).where(Course.id == task.course_id))
    course = course_result.scalar_one_or_none()

    if current_user.is_teacher:
        if course and course.teacher_id == current_user.id:
            return task_response_payload(task, include_hidden_tests=True, progress=progress)
        raise HTTPException(status_code=403, detail="Only course author or admin can open this task by id")

    enrollment_result = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == current_user.id,
            Enrollment.course_id == task.course_id,
        )
    )

    if not enrollment_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You are not enrolled in this task course")

    return task_response_payload(task, include_hidden_tests=False, progress=progress)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_in: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await ensure_task_can_be_edited(db, task, current_user)
    await ensure_course_can_be_edited(db, task_in.course_id, current_user)

    task.title = task_in.title
    task.description = task_in.description
    task.course_id = task_in.course_id

    await db.execute(delete(TestCase).where(TestCase.task_id == task.id))
    db.add_all([
        TestCase(
            task_id=task.id,
            input_data=test.input_data,
            expected_output=test.expected_output,
            is_hidden=test.is_hidden,
        )
        for test in task_in.test_cases
    ])

    await db.commit()

    stmt = select(Task).where(Task.id == task.id).options(selectinload(Task.test_cases))
    updated_result = await db.execute(stmt)
    updated_task = updated_result.scalars().first()
    return task_response_payload(updated_task, include_hidden_tests=True)


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await ensure_task_can_be_edited(db, task, current_user)

    await db.execute(delete(TestCase).where(TestCase.task_id == task.id))
    await db.execute(delete(Submission).where(Submission.task_id == task.id))
    await db.delete(task)
    await db.commit()

    return {"message": "Task deleted", "task_id": task_id}
