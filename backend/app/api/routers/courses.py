from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from typing import List

from app.db.database import get_db
from app.db.models import Course, User, Enrollment, Task, Submission
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse, CourseDetailResponse
from app.api.deps import get_current_user, get_current_teacher

router = APIRouter(prefix="/courses", tags=["Courses"])


TASK_PROGRESS_LABELS = {
    "not_started": "не выполнено",
    "wrong": "выполнено неверно",
    "correct": "выполнено верно",
}

COURSE_PROGRESS_LABELS = {
    "not_started": "нерешен",
    "partial": "решен неполностью",
    "complete": "решен полностью",
}


def resolve_task_progress(statuses: list[str]) -> tuple[str, str]:
    normalized = [str(status or "").lower() for status in statuses]

    if "correct" in normalized:
        return "correct", TASK_PROGRESS_LABELS["correct"]

    if statuses:
        return "wrong", TASK_PROGRESS_LABELS["wrong"]

    return "not_started", TASK_PROGRESS_LABELS["not_started"]


def resolve_course_progress(
    task_ids: list[int],
    progress_map: dict[int, tuple[str, str]],
) -> tuple[str, str]:
    if not task_ids:
        return "not_started", COURSE_PROGRESS_LABELS["not_started"]

    statuses = [
        progress_map.get(task_id, ("not_started", TASK_PROGRESS_LABELS["not_started"]))[0]
        for task_id in task_ids
    ]

    if statuses and all(status == "correct" for status in statuses):
        return "complete", COURSE_PROGRESS_LABELS["complete"]

    if any(status != "not_started" for status in statuses):
        return "partial", COURSE_PROGRESS_LABELS["partial"]

    return "not_started", COURSE_PROGRESS_LABELS["not_started"]


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


async def annotate_courses_with_progress(
    db: AsyncSession,
    current_user: User,
    courses: list[Course],
) -> None:
    if not courses:
        return

    course_ids = [course.id for course in courses]
    tasks_result = await db.execute(
        select(Task.id, Task.course_id).where(Task.course_id.in_(course_ids))
    )

    task_ids: list[int] = []
    tasks_by_course: dict[int, list[int]] = defaultdict(list)
    for task_id, course_id in tasks_result.all():
        task_ids.append(task_id)
        tasks_by_course[course_id].append(task_id)

    progress_map = await get_task_progress_map(db, current_user, task_ids)

    for course in courses:
        progress = resolve_course_progress(tasks_by_course.get(course.id, []), progress_map)
        course.progress_status = progress[0]
        course.progress_label = progress[1]


def task_payload_for_course(
    task: Task,
    include_hidden_tests: bool,
    progress: tuple[str, str] | None = None,
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


# ========== ЭНДПОИНТЫ ДЛЯ ВСЕХ ПОЛЬЗОВАТЕЛЕЙ ==========

@router.get("/", response_model=List[CourseResponse])
async def list_courses(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Список всех курсов"""

    # Получаем курсы
    result = await db.execute(
        select(Course).offset(skip).limit(limit)
    )
    courses = result.scalars().all()

    # Получаем ID курсов, на которые записан пользователь
    enrolled_result = await db.execute(
        select(Enrollment.course_id).where(Enrollment.user_id == current_user.id)
    )
    enrolled_ids = {row[0] for row in enrolled_result.fetchall()}

    # Добавляем флаг is_enrolled
    for course in courses:
        course.is_enrolled = course.id in enrolled_ids

    await annotate_courses_with_progress(db, current_user, courses)

    return courses


@router.get("/my", response_model=List[CourseResponse])
async def get_my_courses(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Курсы, на которые записан текущий пользователь"""

    result = await db.execute(
        select(Course)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .where(Enrollment.user_id == current_user.id)
    )
    courses = result.scalars().all()

    for course in courses:
        course.is_enrolled = True

    await annotate_courses_with_progress(db, current_user, courses)

    return courses


@router.get("/my/created", response_model=List[CourseResponse])
async def get_my_created_courses(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Курсы, созданные текущим пользователем (как учитель)"""

    result = await db.execute(
        select(Course) if current_user.is_admin else select(Course).where(Course.teacher_id == current_user.id)
    )
    courses = result.scalars().all()
    await annotate_courses_with_progress(db, current_user, courses)
    return courses


@router.get("/{course_id}", response_model=CourseDetailResponse)
async def get_course(
        course_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Детальная информация о курсе с задачами"""

    # Получаем курс
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Получаем задачи курса
    tasks_result = await db.execute(
        select(Task)
        .where(Task.course_id == course_id)
        .options(selectinload(Task.test_cases))
    )
    tasks = tasks_result.scalars().all()

    # Получаем количество студентов
    count_result = await db.execute(
        select(func.count()).select_from(Enrollment).where(Enrollment.course_id == course_id)
    )
    course.students_count = count_result.scalar() or 0

    # Проверяем, записан ли пользователь
    enrolled_result = await db.execute(
        select(Enrollment).where(
            and_(Enrollment.user_id == current_user.id, Enrollment.course_id == course_id)
        )
    )
    is_enrolled = enrolled_result.scalar_one_or_none() is not None
    include_hidden_tests = current_user.is_admin or (
        current_user.is_teacher and course.teacher_id == current_user.id
    )
    progress_map = await get_task_progress_map(db, current_user, [task.id for task in tasks])
    course_progress = resolve_course_progress([task.id for task in tasks], progress_map)

    return {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "teacher_id": course.teacher_id,
        "created_at": course.created_at,
        "is_enrolled": is_enrolled,
        "progress_status": course_progress[0],
        "progress_label": course_progress[1],
        "students_count": course.students_count,
        "tasks": [
            task_payload_for_course(
                task,
                include_hidden_tests=include_hidden_tests,
                progress=progress_map.get(task.id),
            )
            for task in tasks
        ],
    }


# ========== ЭНДПОИНТЫ ДЛЯ ЗАПИСИ НА КУРС ==========

@router.post("/{course_id}/enroll")
async def enroll_in_course(
        course_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Записаться на курс"""

    # Проверяем существование курса
    course_result = await db.execute(select(Course).where(Course.id == course_id))
    if not course_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Course not found")

    # Проверяем, не записан ли уже
    existing = await db.execute(
        select(Enrollment).where(
            and_(Enrollment.user_id == current_user.id, Enrollment.course_id == course_id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already enrolled")

    # Записываем
    enrollment = Enrollment(user_id=current_user.id, course_id=course_id)
    db.add(enrollment)
    await db.commit()

    return {"message": "Successfully enrolled", "course_id": course_id}


@router.post("/{course_id}/unenroll")
async def unenroll_from_course(
        course_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Отписаться от курса"""

    enrollment = await db.execute(
        select(Enrollment).where(
            and_(Enrollment.user_id == current_user.id, Enrollment.course_id == course_id)
        )
    )
    enrollment = enrollment.scalar_one_or_none()

    if not enrollment:
        raise HTTPException(status_code=404, detail="Not enrolled")

    await db.delete(enrollment)
    await db.commit()

    return {"message": "Successfully unenrolled", "course_id": course_id}


# ========== ЭНДПОИНТЫ ДЛЯ УЧИТЕЛЕЙ ==========

@router.post("/", response_model=CourseResponse, dependencies=[Depends(get_current_teacher)])
async def create_course(
        course_in: CourseCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_teacher),
):
    """Создать новый курс (только для учителей)"""

    new_course = Course(
        title=course_in.title,
        description=course_in.description,
        teacher_id=current_user.id,
    )

    db.add(new_course)
    await db.commit()
    await db.refresh(new_course)

    return new_course


@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
        course_id: int,
        course_in: CourseUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_teacher),
):
    """Обновить курс (только автор-учитель)"""

    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if course.teacher_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only author can update")

    if course_in.title is not None:
        course.title = course_in.title
    if course_in.description is not None:
        course.description = course_in.description

    await db.commit()
    await db.refresh(course)

    return course


@router.delete("/{course_id}")
async def delete_course(
        course_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_teacher),
):
    """Удалить курс (только автор-учитель)"""

    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if course.teacher_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only author can delete")

    await db.delete(course)
    await db.commit()

    return {"message": "Course deleted"}
