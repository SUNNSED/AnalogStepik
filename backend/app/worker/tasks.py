from celery.exceptions import SoftTimeLimitExceeded

from app.core.celery_app import celery_app
from app.core.runner_client import run_python_tests
from app.db.database import SessionLocal
from app.db.models import Submission, Task, TestCase


def serialize_submission_result(submission: Submission) -> dict:
    return {
        "submission_id": submission.id,
        "status": submission.status,
        "output": submission.output,
    }


@celery_app.task(name="evaluate_code")
def evaluate_code(submission_id: int, task_id: int, code_text: str):
    db = SessionLocal()
    submission = None
    try:
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        task = db.query(Task).filter(Task.id == task_id).first()

        if not submission or not task:
            return {
                "submission_id": submission_id,
                "status": "not_found",
                "output": "Submission or task was not found",
            }

        tests = db.query(TestCase).filter(TestCase.task_id == task_id).order_by(TestCase.id).all()
        if not tests:
            submission.status = "Error"
            submission.output = "Ошибка: У задачи нет тестов для проверки"
            db.commit()
            return serialize_submission_result(submission)

        tests_payload = [
            {
                "input_data": test.input_data or "",
                "expected_output": test.expected_output or "",
                "is_hidden": bool(test.is_hidden),
            }
            for test in tests
        ]

        result = run_python_tests(code_text, tests_payload)
        submission.status = result.get("status", "Error")
        submission.output = result.get("output", "Ошибка проверки")
        db.commit()
        return serialize_submission_result(submission)

    except SoftTimeLimitExceeded:
        db.rollback()
        if submission:
            submission.status = "Time Limit Exceeded"
            submission.output = "Проверка остановлена по лимиту времени Celery"
            db.commit()
            return serialize_submission_result(submission)
        raise
    except Exception as error:
        db.rollback()
        print(f"Error in worker: {error}")
        raise
    finally:
        db.close()
