from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_teacher, get_current_user
from app.db.database import get_db
from app.db.models import Course, Enrollment, Submission, Task, TestCase, User
from app.schemas.user import (
    CourseProgressResponse,
    StudentProgressResponse,
    UserListResponse,
    UserProfileResponse,
    UserStatsResponse,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["Users"])


async def build_user_profile(db: AsyncSession, user: User) -> dict:
    result = await db.execute(
        select(Course)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .where(Enrollment.user_id == user.id)
    )
    enrolled_courses = result.scalars().all()

    for course in enrolled_courses:
        course.is_enrolled = True

    return {
        "id": user.id,
        "email": user.email,
        "is_active": user.is_active,
        "is_teacher": user.is_teacher,
        "is_admin": user.is_admin,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "group_number": user.group_number,
        "created_at": user.created_at,
        "enrolled_courses": enrolled_courses,
    }


@router.get("/", response_model=List[UserListResponse])
async def list_users(
    query: Optional[str] = Query(default=None),
    group_number: Optional[str] = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    stmt = select(User).offset(skip).limit(limit).order_by(User.id.desc())

    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                User.email.ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
            )
        )

    if group_number:
        stmt = stmt.where(User.group_number == group_number)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await build_user_profile(db, current_user)


@router.put("/me", response_model=UserProfileResponse)
async def update_my_profile(
    profile_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    for field in ("first_name", "last_name", "group_number"):
        value = getattr(profile_in, field)
        if value is not None:
            setattr(current_user, field, value.strip() or None)

    await db.commit()
    await db.refresh(current_user)
    return await build_user_profile(db, current_user)


@router.get("/me/stats", response_model=UserStatsResponse)
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(
        select(func.count()).select_from(Submission).where(Submission.user_id == current_user.id)
    )
    total_submissions = total_result.scalar() or 0

    correct_result = await db.execute(
        select(func.count()).select_from(Submission).where(
            Submission.user_id == current_user.id,
            Submission.status == "Correct",
        )
    )
    correct_submissions = correct_result.scalar() or 0

    courses_result = await db.execute(
        select(func.count()).select_from(Enrollment).where(Enrollment.user_id == current_user.id)
    )
    courses_enrolled = courses_result.scalar() or 0

    accuracy = (correct_submissions / total_submissions * 100) if total_submissions > 0 else 0

    return {
        "total_submissions": total_submissions,
        "correct_submissions": correct_submissions,
        "accuracy": round(accuracy, 2),
        "courses_enrolled": courses_enrolled,
    }


@router.get("/students/progress", response_model=List[StudentProgressResponse])
async def get_students_progress(
    query: Optional[str] = Query(default=None),
    group_number: Optional[str] = Query(default=None),
    student_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    courses_stmt = select(Course).order_by(Course.id)
    if not current_user.is_admin:
        courses_stmt = courses_stmt.where(Course.teacher_id == current_user.id)

    courses_result = await db.execute(courses_stmt)
    courses = courses_result.scalars().all()

    if not courses:
        return []

    course_ids = [course.id for course in courses]
    courses_by_id = {course.id: course for course in courses}

    students_stmt = select(User).where(User.is_admin.is_(False), User.is_teacher.is_(False)).order_by(User.id)
    if student_id:
        students_stmt = students_stmt.where(User.id == student_id)
    if query:
        pattern = f"%{query}%"
        students_stmt = students_stmt.where(
            or_(
                User.email.ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
            )
        )
    if group_number:
        students_stmt = students_stmt.where(User.group_number == group_number)

    students_result = await db.execute(students_stmt)
    students = students_result.scalars().all()

    if not students:
        return []

    tasks_result = await db.execute(select(Task.id, Task.course_id).where(Task.course_id.in_(course_ids)))
    task_rows = tasks_result.all()
    tasks_by_course = {course.id: [] for course in courses}
    task_course_by_id = {}

    for task_id, course_id in task_rows:
        tasks_by_course.setdefault(course_id, []).append(task_id)
        task_course_by_id[task_id] = course_id

    all_task_ids = list(task_course_by_id.keys())
    reports = []

    for student in students:
        enrollment_result = await db.execute(
            select(Enrollment.course_id).where(
                Enrollment.user_id == student.id,
                Enrollment.course_id.in_(course_ids),
            )
        )
        enrolled_course_ids = {row[0] for row in enrollment_result.all()}
        visible_enrolled_course_ids = [
            course.id for course in courses if course.id in enrolled_course_ids
        ]

        if not visible_enrolled_course_ids:
            continue

        enrolled_task_ids = [
            task_id
            for task_id, course_id in task_course_by_id.items()
            if course_id in visible_enrolled_course_ids
        ]

        solved_task_ids = set()
        if enrolled_task_ids:
            solved_result = await db.execute(
                select(distinct(Submission.task_id)).where(
                    Submission.user_id == student.id,
                    Submission.status == "Correct",
                    Submission.task_id.in_(enrolled_task_ids),
                )
            )
            solved_task_ids = {row[0] for row in solved_result.all()}

        submissions_by_course = {course_id: 0 for course_id in visible_enrolled_course_ids}
        if enrolled_task_ids:
            submissions_result = await db.execute(
                select(Submission.task_id, func.count(Submission.id))
                .where(
                    Submission.user_id == student.id,
                    Submission.task_id.in_(enrolled_task_ids),
                )
                .group_by(Submission.task_id)
            )
            for task_id, submissions_count in submissions_result.all():
                course_id = task_course_by_id.get(task_id)
                if course_id is not None:
                    submissions_by_course[course_id] += submissions_count

        course_progress = []
        for course_id in visible_enrolled_course_ids:
            course = courses_by_id[course_id]
            course_task_ids = tasks_by_course.get(course.id, [])
            total_tasks = len(course_task_ids)
            solved_tasks = len(set(course_task_ids) & solved_task_ids)
            progress_percent = (solved_tasks / total_tasks * 100) if total_tasks else 0
            course_progress.append(
                CourseProgressResponse(
                    course_id=course.id,
                    title=course.title,
                    total_tasks=total_tasks,
                    solved_tasks=solved_tasks,
                    progress_percent=round(progress_percent, 2),
                    submissions_count=submissions_by_course.get(course.id, 0),
                    is_enrolled=True,
                )
            )

        reports.append(
            StudentProgressResponse(
                user=student,
                courses=course_progress,
            )
        )

    return reports


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return await build_user_profile(db, user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    teacher_courses_result = await db.execute(select(Course.id).where(Course.teacher_id == user_id))
    teacher_course_ids = [row[0] for row in teacher_courses_result.all()]

    if teacher_course_ids:
        teacher_tasks_result = await db.execute(select(Task.id).where(Task.course_id.in_(teacher_course_ids)))
        teacher_task_ids = [row[0] for row in teacher_tasks_result.all()]

        if teacher_task_ids:
            await db.execute(delete(TestCase).where(TestCase.task_id.in_(teacher_task_ids)))
            await db.execute(delete(Submission).where(Submission.task_id.in_(teacher_task_ids)))
            await db.execute(delete(Task).where(Task.id.in_(teacher_task_ids)))

        await db.execute(delete(Enrollment).where(Enrollment.course_id.in_(teacher_course_ids)))
        await db.execute(delete(Course).where(Course.id.in_(teacher_course_ids)))

    await db.execute(delete(Submission).where(Submission.user_id == user_id))
    await db.execute(delete(Enrollment).where(Enrollment.user_id == user_id))
    await db.delete(user)
    await db.commit()

    return {"message": "User deleted", "user_id": user_id}
