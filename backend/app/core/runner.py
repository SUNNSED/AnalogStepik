import io
import json
import os
import tarfile
from typing import Any, Dict, Sequence

import docker
import requests


RUNNER_IMAGE = "python:3.11-slim"
PER_TEST_TIMEOUT_SECONDS = 5
TOTAL_TIMEOUT_SECONDS = 60
MAX_OUTPUT_CHARS = 4000
RUNNER_RUNTIME = os.getenv("RUNNER_RUNTIME", "").strip()

RUNNER_SCRIPT = r"""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PER_TEST_TIMEOUT = float(sys.argv[1])
TOTAL_TIMEOUT = float(sys.argv[2])
MAX_OUTPUT_CHARS = int(sys.argv[3])


def trim(value):
    text = value if value is not None else ""
    text = str(text)
    if len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS] + "\n... output truncated ..."
    return text


def normalize(value):
    return (value or "").strip()


def main():
    tests = json.loads(Path("/tests.json").read_text(encoding="utf-8"))
    deadline = time.monotonic() + TOTAL_TIMEOUT
    results = []
    passed = 0
    stopped_by_total_timeout = False

    for index, test in enumerate(tests, start=1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            stopped_by_total_timeout = True
            break

        input_data = test.get("input_data") or ""
        if not input_data.endswith("\n"):
            input_data += "\n"

        expected_output = normalize(test.get("expected_output") or "")
        is_hidden = bool(test.get("is_hidden"))

        try:
            with tempfile.TemporaryDirectory(prefix="case-") as workdir:
                completed = subprocess.run(
                    [sys.executable, "/solution.py"],
                    input=input_data,
                    text=True,
                    capture_output=True,
                    cwd=workdir,
                    timeout=min(PER_TEST_TIMEOUT, max(0.1, remaining)),
                )
        except subprocess.TimeoutExpired:
            results.append({
                "index": index,
                "status": "timeout",
                "is_hidden": is_hidden,
            })
            continue

        actual_output = normalize(completed.stdout)

        if completed.returncode != 0:
            error_output = normalize(completed.stderr) or actual_output
            item = {
                "index": index,
                "status": "runtime_error",
                "is_hidden": is_hidden,
            }
            if not is_hidden:
                item["actual_output"] = trim(error_output)
            results.append(item)
            continue

        if actual_output == expected_output:
            passed += 1
            results.append({
                "index": index,
                "status": "passed",
                "is_hidden": is_hidden,
            })
            continue

        item = {
            "index": index,
            "status": "wrong_answer",
            "is_hidden": is_hidden,
        }
        if not is_hidden:
            item["expected_output"] = trim(expected_output)
            item["actual_output"] = trim(actual_output)
        results.append(item)

    statuses = [item["status"] for item in results]
    if stopped_by_total_timeout or "timeout" in statuses:
        status = "Time Limit Exceeded"
    elif "runtime_error" in statuses:
        status = "Runtime Error"
    elif passed == len(tests):
        status = "Correct"
    else:
        status = "Wrong Answer"

    print(json.dumps({
        "status": status,
        "passed": passed,
        "total": len(tests),
        "results": results,
        "stopped_by_total_timeout": stopped_by_total_timeout,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
"""


try:
    client = docker.from_env()
except Exception as error:
    print(f"Ошибка подключения к Docker: {error}")
    client = None

_runner_image_ready = False


def _add_text_file(tar: tarfile.TarFile, name: str, content: str) -> None:
    data = content.encode("utf-8")
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def _ensure_runner_image() -> None:
    global _runner_image_ready

    if _runner_image_ready or client is None:
        return

    try:
        client.images.get(RUNNER_IMAGE)
    except docker.errors.ImageNotFound:
        client.images.pull(RUNNER_IMAGE)

    _runner_image_ready = True


def _format_failure(result: dict[str, Any]) -> str:
    index = result.get("index", "?")
    status = result.get("status")
    is_hidden = result.get("is_hidden")

    if status == "timeout":
        return f"Time Limit Exceeded на {'скрытом ' if is_hidden else ''}тесте {index}"

    if status == "runtime_error":
        if is_hidden:
            return f"Runtime Error на скрытом тесте {index}"
        return f"Runtime Error на тесте {index}\n{result.get('actual_output', '')}"

    if status == "wrong_answer":
        if is_hidden:
            return f"Wrong Answer на скрытом тесте {index}"
        return (
            f"Wrong Answer на тесте {index}.\n"
            f"Ожидалось:\n{result.get('expected_output', '')}\n"
            f"Вывод программы:\n{result.get('actual_output', '')}"
        )

    return f"Тест {index} завершился со статусом {status}"


def _format_output(result: dict[str, Any]) -> str:
    status = result.get("status")
    passed = result.get("passed", 0)
    total = result.get("total", 0)
    results = result.get("results") or []

    if status == "Correct":
        return f"Все тесты пройдены успешно! (Проверено: {total})"

    first_failure = next((item for item in results if item.get("status") != "passed"), None)
    summary = f"Пройдено тестов: {passed}/{total}"
    if result.get("stopped_by_total_timeout"):
        summary += "\nПроверка остановлена по общему лимиту времени"

    if first_failure:
        return f"{summary}\n\n{_format_failure(first_failure)}"

    return summary


def run_python_tests(
    code_text: str,
    tests: Sequence[dict[str, Any]],
    per_test_timeout: int = PER_TEST_TIMEOUT_SECONDS,
    total_timeout: int = TOTAL_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    if client is None:
        return {"status": "Error", "output": "Docker Desktop не запущен", "passed": 0, "total": len(tests)}

    container = None
    try:
        _ensure_runner_image()

        command = [
            "python",
            "/runner.py",
            str(per_test_timeout),
            str(total_timeout),
            str(MAX_OUTPUT_CHARS),
        ]
        container_options = {
            "image": RUNNER_IMAGE,
            "command": command,
            "mem_limit": "128m",
            "nano_cpus": 500000000,
            "network_disabled": True,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "pids_limit": 64,
            "tmpfs": {"/tmp": "rw,nosuid,nodev,size=16m,mode=1777"},
            "user": "65534:65534",
            "detach": True,
        }
        if RUNNER_RUNTIME:
            container_options["runtime"] = RUNNER_RUNTIME

        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            _add_text_file(tar, "solution.py", code_text)
            _add_text_file(tar, "runner.py", RUNNER_SCRIPT)
            _add_text_file(tar, "tests.json", json.dumps(list(tests), ensure_ascii=False))

        container = client.containers.create(**container_options)
        tar_stream.seek(0)
        container.put_archive("/", tar_stream)
        container.start()

        try:
            wait_result = container.wait(timeout=total_timeout + 5)
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
            container.kill()
            return {
                "status": "Time Limit Exceeded",
                "output": "Проверка остановлена по общему лимиту времени",
                "passed": 0,
                "total": len(tests),
            }

        logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace").strip()
        if wait_result.get("StatusCode", 0) != 0:
            return {
                "status": "Runtime Error",
                "output": logs or "Runner failed",
                "passed": 0,
                "total": len(tests),
            }

        parsed = json.loads(logs)
        parsed["output"] = _format_output(parsed)
        return parsed

    except json.JSONDecodeError as error:
        return {
            "status": "Runtime Error",
            "output": f"Runner returned invalid JSON: {error}",
            "passed": 0,
            "total": len(tests),
        }
    except Exception as error:
        if "timeout" in str(error).lower():
            if container:
                container.kill()
            return {
                "status": "Time Limit Exceeded",
                "output": "Проверка остановлена по таймауту",
                "passed": 0,
                "total": len(tests),
            }
        return {"status": "Runtime Error", "output": str(error), "passed": 0, "total": len(tests)}
    finally:
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass


def run_python_code(code_text: str, input_data: str = "", timeout: int = PER_TEST_TIMEOUT_SECONDS) -> Dict[str, str]:
    result = run_python_tests(
        code_text,
        [{"input_data": input_data, "expected_output": "", "is_hidden": False}],
        per_test_timeout=timeout,
        total_timeout=timeout + 5,
    )

    if result.get("status") == "Correct":
        return {"status": "success", "output": ""}
    if result.get("status") == "Time Limit Exceeded":
        return {"status": "timeout", "output": result.get("output", "")}
    return {"status": "error", "output": result.get("output", "")}
