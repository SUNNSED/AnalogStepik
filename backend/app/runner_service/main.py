from typing import Any, List

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.core.runner import PER_TEST_TIMEOUT_SECONDS, TOTAL_TIMEOUT_SECONDS, run_python_tests


app = FastAPI(title="AnalogStepik Runner")


class RunnerTest(BaseModel):
    input_data: str = ""
    expected_output: str = ""
    is_hidden: bool = False


class RunnerRequest(BaseModel):
    code_text: str
    tests: List[RunnerTest] = Field(default_factory=list)
    per_test_timeout: int = PER_TEST_TIMEOUT_SECONDS
    total_timeout: int = TOTAL_TIMEOUT_SECONDS


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run")
def run_submission(payload: RunnerRequest) -> dict[str, Any]:
    return run_python_tests(
        payload.code_text,
        [test.model_dump() for test in payload.tests],
        per_test_timeout=payload.per_test_timeout,
        total_timeout=payload.total_timeout,
    )
