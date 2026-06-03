from typing import Any, Dict, Sequence

import requests

from app.core.config import settings


PER_TEST_TIMEOUT_SECONDS = 5
TOTAL_TIMEOUT_SECONDS = 60


def run_python_tests(
    code_text: str,
    tests: Sequence[dict[str, Any]],
    per_test_timeout: int = PER_TEST_TIMEOUT_SECONDS,
    total_timeout: int = TOTAL_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    try:
        response = requests.post(
            settings.RUNNER_URL,
            json={
                "code_text": code_text,
                "tests": list(tests),
                "per_test_timeout": per_test_timeout,
                "total_timeout": total_timeout,
            },
            timeout=total_timeout + 10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        return {
            "status": "Error",
            "output": f"Runner service is unavailable: {error}",
            "passed": 0,
            "total": len(tests),
        }
    except ValueError as error:
        return {
            "status": "Error",
            "output": f"Runner service returned invalid JSON: {error}",
            "passed": 0,
            "total": len(tests),
        }
