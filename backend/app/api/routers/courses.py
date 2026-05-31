from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from typing import List

from app.db.database import get_db
from app.db.models import Course, User, Enrollment, Task
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse, CourseDetailResponse
from app.api.deps import get_current_user, get_current_teacher

router = APIRouter(prefix="/courses", tags=["Courses"])


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
    return result.scalars().all()


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
    course.tasks = tasks_result.scalars().all()

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
    course.is_enrolled = enrolled_result.scalar_one_or_none() is not None

    return course


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
