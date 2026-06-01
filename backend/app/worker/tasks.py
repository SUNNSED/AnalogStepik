from app.core.celery_app import celery_app
from app.core.runner import run_python_code
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
    # Прогоняет код по всем тестам задачи (Fail-fast).
    db = SessionLocal()
    try:
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        task = db.query(Task).filter(Task.id == task_id).first()

        if submission and task:
            # Получаем все тесты для этой задачи, отсортированные по ID
            tests = db.query(TestCase).filter(TestCase.task_id == task_id).order_by(TestCase.id).all()

            if not tests:
                submission.status = "Error"
                submission.output = "Ошибка: У задачи нет тестов для проверки"
                db.commit()
                return serialize_submission_result(submission)

            all_passed = True

            # Прогоняем код через каждый тест
            for i, test in enumerate(tests, start=1):
                # Достаем инпут для текущего теста
                input_to_send = test.input_data if test.input_data else ""

                # Запускаем Docker с конкретным вводом
                result = run_python_code(code_text, input_data=input_to_send)
                status = result.get("status")
                actual_output = result.get("output", "").strip()

                # Проверка на Time Limit
                if status == "timeout":
                    submission.status = "Time Limit Exceeded"
                    submission.output = f"Time Limit Exceeded на тесте {i}"
                    all_passed = False
                    break  # Прерываем проверку (Fail-fast)

                # Проверка на Runtime Error
                elif status == "error":
                    submission.status = "Runtime Error"
                    submission.output = f"Runtime Error на тесте {i}\n{actual_output}"
                    all_passed = False
                    break

                # Сверка правильного ответа
                expected_output = test.expected_output.strip() if test.expected_output else ""

                if actual_output != expected_output:
                    submission.status = "Wrong Answer"

                    # Логика скрытых тестов
                    if test.is_hidden:
                        submission.output = f"Wrong Answer на скрытом тесте {i}"
                    else:
                        submission.output = f"Wrong Answer на тесте {i}.\nОжидалось:\n{expected_output}\nВывод программы:\n{actual_output}"

                    all_passed = False
                    break

            if all_passed:
                submission.status = "Correct"
                submission.output = f"Все тесты пройдены успешно! (Проверено: {len(tests)})"

            db.commit()
            return serialize_submission_result(submission)

        return {
            "submission_id": submission_id,
            "status": "not_found",
            "output": "Submission or task was not found",
        }

    except Exception as e:
        db.rollback()
        print(f"Error in worker: {e}")
        raise e
    finally:
        db.close()
