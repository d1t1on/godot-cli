from __future__ import annotations

import importlib.util
import inspect
import json
import mimetypes
import re
import shutil
import signal
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter
from contextvars import ContextVar
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from html import escape
from io import StringIO
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from .client import (
    Godot,
    GodotClient,
    expect,
    expect_engine,
    expect_editor,
    expect_filesystem,
    expect_inspector,
    expect_audio,
    expect_log,
    expect_navigation,
    expect_node_class,
    expect_physics2d,
    expect_physics3d,
    expect_project,
    expect_project_scene,
    expect_resource,
    expect_resource_class,
    expect_runtime_scene,
    expect_script,
    expect_script_class,
    expect_signal,
    expect_trace,
    expect_viewport,
)
from .install import install_addon
from .checks import expect_script_file
from .scene import expect_scene_file
from .visual import expect_scene

_CURRENT_STEP_RECORDER: ContextVar["_StepRecorder | None"] = ContextVar("godot_playwright_step_recorder", default=None)


class TestRunnerError(RuntimeError):
    pass


class TestTimeoutError(TimeoutError):
    pass


class TestSkipped(Exception):
    pass


class UnexpectedPassError(AssertionError):
    pass


class SoftAssertionError(AssertionError):
    pass


class _StepRecorder:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []
        self.stack: list[int] = []

    def start(self, title: str) -> int:
        index = len(self.steps)
        self.steps.append(
            {
                "title": str(title),
                "status": "running",
                "depth": len(self.stack),
                "duration_ms": 0,
                "error": None,
            }
        )
        self.stack.append(index)
        return index

    def finish(self, index: int, *, started: float, error: BaseException | None = None) -> None:
        step = self.steps[index]
        step["duration_ms"] = round((time.monotonic() - started) * 1000, 3)
        if error is None:
            step["status"] = "passed"
        elif isinstance(error, TestSkipped):
            step["status"] = "skipped"
            step["error"] = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": "",
            }
        else:
            step["status"] = "failed"
            step["error"] = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
            }
        if self.stack and self.stack[-1] == index:
            self.stack.pop()
        elif index in self.stack:
            self.stack.remove(index)


class _StepContext:
    def __init__(self, recorder: _StepRecorder, title: str):
        self.recorder = recorder
        self.title = title
        self.index = -1
        self.started = 0.0

    def __enter__(self) -> "_StepContext":
        self.started = time.monotonic()
        self.index = self.recorder.start(self.title)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        self.recorder.finish(
            self.index,
            started=self.started,
            error=exc if isinstance(exc, BaseException) else None,
        )
        return False


class TestInfo:
    def __init__(
        self,
        test: "DiscoveredTest",
        *,
        project_path: Path,
        artifacts_dir: Path,
        artifact_id: str,
        attempt: int,
        mode: str,
    ):
        self.test = test
        self.id = test.id
        self.file = test.file
        self.name = test.name
        self.project_path = project_path
        self.artifacts_dir = artifacts_dir
        self.artifact_id = artifact_id
        self.attempt = attempt
        self.mode = mode
        self.output_dir = artifacts_dir / f"{artifact_id}-attachments"
        self.attachments: list[dict[str, Any]] = []

    def output_path(self, *parts: str | Path) -> Path:
        if not parts:
            raise TestRunnerError("output_path requires at least one path part")
        path = self.output_dir.joinpath(*(str(part) for part in parts))
        resolved = path.resolve()
        output_root = self.output_dir.resolve()
        if resolved != output_root and output_root not in resolved.parents:
            raise TestRunnerError("output_path must stay inside the test output directory")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    def attach(
        self,
        name: str,
        *,
        path: str | Path | None = None,
        body: str | bytes | dict[str, Any] | list[Any] | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        if (path is None) == (body is None):
            raise TestRunnerError("attach requires exactly one of path or body")
        index = len(self.attachments)
        if path is not None:
            source = Path(path).expanduser().resolve()
            if not source.is_file():
                raise TestRunnerError(f"Attachment path does not exist or is not a file: {source}")
            target = self.output_path(_attachment_filename(name, index, source.suffix))
            if source != target:
                shutil.copyfile(source, target)
            resolved_content_type = content_type or mimetypes.guess_type(str(source))[0] or "application/octet-stream"
        else:
            assert body is not None
            payload, suffix, inferred_type = _attachment_body_payload(body)
            target = self.output_path(_attachment_filename(name, index, suffix))
            target.write_bytes(payload)
            resolved_content_type = content_type or inferred_type

        attachment = {
            "name": str(name),
            "path": str(target),
            "content_type": resolved_content_type,
            "bytes": target.stat().st_size,
        }
        self.attachments.append(attachment)
        return attachment

    def skip(self, reason: str = "") -> None:
        raise TestSkipped(str(reason))


class _SoftAssertions:
    def __init__(self) -> None:
        self.failures: list[dict[str, Any]] = []

    def expect(self, target: Any) -> "_SoftExpect":
        return _SoftExpect(expect(target), self)

    def record(self, method: str, error: AssertionError) -> None:
        self.failures.append(
            {
                "index": len(self.failures) + 1,
                "method": method,
                "type": type(error).__name__,
                "message": str(error),
                "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
            }
        )

    def assert_all(self) -> None:
        if self.failures:
            raise SoftAssertionError(self.summary())

    def summary(self) -> str:
        lines = [f"{len(self.failures)} soft assertion failure(s):"]
        for failure in self.failures:
            lines.append(
                f"{failure.get('index', 0)}. {failure.get('method', 'expect')}: "
                f"{failure.get('message', '')}"
            )
        return "\n".join(lines)


class _SoftExpect:
    def __init__(self, hard_expect: Any, assertions: _SoftAssertions) -> None:
        self._hard_expect = hard_expect
        self._assertions = assertions

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._hard_expect, name)
        if not callable(attribute):
            return attribute

        def soft_call(*args: Any, **kwargs: Any) -> Any:
            try:
                return attribute(*args, **kwargs)
            except AssertionError as exc:
                self._assertions.record(name, exc)
                return None

        return soft_call


_POLL_UNSET = object()


class PollExpect:
    def __init__(self, action: Callable[[], Any], *, description: str = "") -> None:
        if not callable(action):
            raise TestRunnerError("expect_poll requires a callable")
        self.action = action
        self.description = description or getattr(action, "__name__", "") or "callable"

    def to_equal(self, expected: Any, *, timeout: float = 5.0, interval: float = 0.05) -> Any:
        return self._poll(
            lambda value: value == expected,
            f"to equal {_short_repr(expected)}",
            timeout=timeout,
            interval=interval,
        )

    def to_be(self, expected: Any, *, timeout: float = 5.0, interval: float = 0.05) -> Any:
        return self.to_equal(expected, timeout=timeout, interval=interval)

    def not_to_equal(self, unexpected: Any, *, timeout: float = 5.0, interval: float = 0.05) -> Any:
        return self._poll(
            lambda value: value != unexpected,
            f"not to equal {_short_repr(unexpected)}",
            timeout=timeout,
            interval=interval,
        )

    def not_to_be(self, unexpected: Any, *, timeout: float = 5.0, interval: float = 0.05) -> Any:
        return self.not_to_equal(unexpected, timeout=timeout, interval=interval)

    def to_be_truthy(self, *, timeout: float = 5.0, interval: float = 0.05) -> Any:
        return self._poll(bool, "to be truthy", timeout=timeout, interval=interval)

    def to_be_falsy(self, *, timeout: float = 5.0, interval: float = 0.05) -> Any:
        return self._poll(lambda value: not bool(value), "to be falsy", timeout=timeout, interval=interval)

    def to_satisfy(
        self,
        predicate: Callable[[Any], bool],
        description: str = "to satisfy predicate",
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> Any:
        if not callable(predicate):
            raise TestRunnerError("to_satisfy requires a callable predicate")
        return self._poll(predicate, description, timeout=timeout, interval=interval)

    def _poll(
        self,
        matcher: Callable[[Any], bool],
        expectation: str,
        *,
        timeout: float,
        interval: float,
    ) -> Any:
        if timeout < 0:
            raise TestRunnerError("expect_poll timeout must be non-negative")
        if interval <= 0:
            raise TestRunnerError("expect_poll interval must be greater than 0")
        deadline = time.monotonic() + timeout
        last_value: Any = _POLL_UNSET
        last_error: BaseException | None = None
        while True:
            try:
                value = self.action()
                last_value = value
                last_error = None
                if matcher(value):
                    return value
            except TestSkipped:
                raise
            except Exception as exc:
                last_error = exc

            if time.monotonic() >= deadline:
                raise AssertionError(
                    _poll_failure_message(
                        self.description,
                        expectation,
                        timeout=timeout,
                        last_value=last_value,
                        last_error=last_error,
                    )
                )
            time.sleep(interval)


def expect_poll(action: Callable[[], Any], *, description: str = "") -> PollExpect:
    return PollExpect(action, description=description)


@dataclass(frozen=True)
class DiscoveredTest:
    file: Path
    name: str
    function: Callable[..., Any]

    @property
    def id(self) -> str:
        return f"{self.file.as_posix()}::{self.name}"


def skip(reason: str | Callable[..., Any] = "") -> Callable[..., Any]:
    return _annotation_decorator("skip", reason)


def expected_failure(reason: str | Callable[..., Any] = "") -> Callable[..., Any]:
    return _annotation_decorator("expected_failure", reason)


xfail = expected_failure


def before_each(function: Callable[..., Any]) -> Callable[..., Any]:
    return _hook_decorator("before_each", function)


def after_each(function: Callable[..., Any]) -> Callable[..., Any]:
    return _hook_decorator("after_each", function)


def _annotation_decorator(kind: str, reason: str | Callable[..., Any]) -> Callable[..., Any]:
    if callable(reason):
        return _annotate_test(reason, kind, "")

    def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
        return _annotate_test(function, kind, str(reason))

    return decorator


def _annotate_test(function: Callable[..., Any], kind: str, reason: str) -> Callable[..., Any]:
    annotations = list(getattr(function, "__godot_playwright_annotations__", []))
    annotations = [item for item in annotations if not (isinstance(item, dict) and item.get("type") == kind)]
    annotations.append({"type": kind, "reason": reason})
    setattr(function, "__godot_playwright_annotations__", annotations)
    return function


def _hook_decorator(kind: str, function: Callable[..., Any]) -> Callable[..., Any]:
    setattr(function, "__godot_playwright_hook__", kind)
    return function


def _test_hooks(test: DiscoveredTest, kind: str) -> list[Callable[..., Any]]:
    hooks = [
        value
        for value in test.function.__globals__.values()
        if inspect.isfunction(value) and getattr(value, "__godot_playwright_hook__", "") == kind
    ]
    return sorted(hooks, key=lambda function: (function.__code__.co_firstlineno, function.__name__))


def discover_tests(paths: list[str | Path]) -> list[DiscoveredTest]:
    files: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if path.is_dir():
            files.extend(sorted(path.rglob("test_*.py")))
        elif path.is_file():
            files.append(path)
        else:
            raise TestRunnerError(f"Test path does not exist: {path}")

    tests: list[DiscoveredTest] = []
    for file in sorted(dict.fromkeys(files)):
        module = _load_module(file)
        for name, value in sorted(vars(module).items()):
            if name.startswith("test_") and inspect.isfunction(value):
                tests.append(DiscoveredTest(file=file, name=name, function=value))
    return tests


def select_tests(
    tests: list[DiscoveredTest],
    *,
    grep: str | list[str] | None = None,
    grep_invert: bool = False,
    shard: str | tuple[int, int] | None = None,
) -> tuple[list[DiscoveredTest], dict[str, Any]]:
    patterns = _compile_grep_patterns(grep)
    if patterns:
        grep_filtered = [test for test in tests if _test_matches_grep(test, patterns) != grep_invert]
    else:
        grep_filtered = list(tests)

    shard_spec = _parse_shard(shard)
    if shard_spec is None:
        selected = grep_filtered
        shard_report = None
    else:
        current, total = shard_spec
        selected = [test for index, test in enumerate(grep_filtered) if index % total == current - 1]
        shard_report = {
            "current": current,
            "total": total,
            "before_shard": len(grep_filtered),
        }

    return selected, {
        "discovered": len(tests),
        "grep": grep,
        "grep_invert": grep_invert,
        "after_grep": len(grep_filtered),
        "shard": shard_report,
        "selected": len(selected),
    }


def _compile_grep_patterns(grep: str | list[str] | None) -> list[re.Pattern[str]]:
    if grep is None:
        return []
    raw_patterns = [grep] if isinstance(grep, str) else list(grep)
    patterns = [pattern for pattern in raw_patterns if pattern]
    compiled = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern))
        except re.error as exc:
            raise TestRunnerError(f"Invalid --grep pattern {pattern!r}: {exc}") from exc
    return compiled


def _test_matches_grep(test: DiscoveredTest, patterns: list[re.Pattern[str]]) -> bool:
    haystack = f"{test.id}\n{test.file.as_posix()}\n{test.name}"
    return any(pattern.search(haystack) is not None for pattern in patterns)


def _parse_shard(shard: str | tuple[int, int] | None) -> tuple[int, int] | None:
    if shard is None:
        return None
    if isinstance(shard, tuple):
        current, total = shard
    else:
        parts = str(shard).split("/", 1)
        if len(parts) != 2:
            raise TestRunnerError("Shard must use current/total format, for example 1/3")
        try:
            current = int(parts[0])
            total = int(parts[1])
        except ValueError as exc:
            raise TestRunnerError("Shard current and total must be integers") from exc
    if total <= 0:
        raise TestRunnerError("Shard total must be greater than 0")
    if current <= 0 or current > total:
        raise TestRunnerError("Shard current must be between 1 and total")
    return current, total


def _test_annotations(test_or_result: DiscoveredTest | dict[str, Any]) -> list[dict[str, str]]:
    if isinstance(test_or_result, dict):
        annotations = test_or_result.get("annotations", [])
    else:
        annotations = getattr(test_or_result.function, "__godot_playwright_annotations__", [])
    return [
        {"type": str(item.get("type", "")), "reason": str(item.get("reason", ""))}
        for item in annotations
        if isinstance(item, dict) and item.get("type")
    ]


def _annotation_reason(test_or_result: DiscoveredTest | dict[str, Any], kind: str) -> str | None:
    for annotation in _test_annotations(test_or_result):
        if annotation.get("type") == kind:
            return annotation.get("reason", "")
    return None


def _skip_reason(test: DiscoveredTest) -> str | None:
    return _annotation_reason(test, "skip")


def _expected_failure_reason(test_or_result: DiscoveredTest | dict[str, Any]) -> str | None:
    return _annotation_reason(test_or_result, "expected_failure")


def run_tests(
    project_path: str | Path,
    test_paths: list[str | Path],
    *,
    mode: str = "runtime",
    executable: str = "godot",
    headless: bool = True,
    timeout: float = 20.0,
    artifacts_dir: str | Path = "godot-playwright-report",
    trace: str = "retain-on-failure",
    update_snapshots: bool = False,
    reuse_godot: bool = False,
    grep: str | list[str] | None = None,
    grep_invert: bool = False,
    shard: str | tuple[int, int] | None = None,
    list_only: bool = False,
    retries: int = 0,
    test_timeout: float = 0.0,
    workers: int = 1,
    screenshots: str = "off",
    max_failures: int = 0,
    junit_xml: str | Path | None = None,
) -> dict[str, Any]:
    if retries < 0:
        raise TestRunnerError("retries must be non-negative")
    if test_timeout < 0:
        raise TestRunnerError("test_timeout must be non-negative")
    if workers < 1:
        raise TestRunnerError("workers must be greater than 0")
    if max_failures < 0:
        raise TestRunnerError("max_failures must be non-negative")
    if reuse_godot and workers != 1:
        raise TestRunnerError("workers cannot be greater than 1 when reuse_godot is enabled")
    if max_failures and reuse_godot:
        raise TestRunnerError("max_failures is not supported when reuse_godot is enabled")
    if max_failures and workers != 1:
        raise TestRunnerError("max_failures is not supported with multiple workers")
    if screenshots not in {"off", "on", "only-on-failure"}:
        raise TestRunnerError("screenshots must be one of: off, on, only-on-failure")
    discovered_tests = discover_tests(test_paths)
    tests, selection = select_tests(discovered_tests, grep=grep, grep_invert=grep_invert, shard=shard)
    artifacts = Path(artifacts_dir).expanduser().resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    junit_path = Path(junit_xml).expanduser().resolve() if junit_xml else None
    if junit_path is not None:
        junit_path.parent.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "project": str(Path(project_path).expanduser().resolve()),
        "mode": mode,
        "total": len(tests),
        "discovered": len(discovered_tests),
        "passed": 0,
        "failed": 0,
        "flaky": 0,
        "skipped": 0,
        "interrupted": 0,
        "expected_failed": 0,
        "unexpected_passed": 0,
        "soft_assertion_failures": 0,
        "duration_ms": 0,
        "artifacts_dir": str(artifacts),
        "results_json": str(artifacts / "results.json"),
        "report_html": str(artifacts / "report.html"),
        "junit_xml": str(junit_path) if junit_path is not None else "",
        "reuse_godot": reuse_godot,
        "list_only": list_only,
        "retries": retries,
        "test_timeout": test_timeout,
        "workers": workers,
        "screenshots": screenshots,
        "max_failures": max_failures,
        "stopped_early": False,
        "selection": selection,
        "tests": [],
    }

    started = time.monotonic()
    if list_only:
        for test in tests:
            report["tests"].append(_listed_test_result(test))
        report["duration_ms"] = round((time.monotonic() - started) * 1000, 3)
        _write_html_report(report)
        _write_junit_report_if_requested(report)
        Path(report["results_json"]).write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return report

    if reuse_godot:
        reuse_log_path = artifacts / "godot-reuse.log"
        reuse_attempts: list[list[dict[str, Any]] | dict[str, Any]] = []
        runnable_tests = [test for test in tests if _skip_reason(test) is None]
        if runnable_tests:
            with reuse_log_path.open("w", encoding="utf-8") as log_file:
                with Godot(
                    project_path,
                    mode=mode,
                    executable=executable,
                    headless=headless,
                    timeout=timeout,
                    stdout=log_file,
                ) as godot:
                    for test in tests:
                        skip_reason = _skip_reason(test)
                        if skip_reason is not None:
                            reuse_attempts.append(_skipped_test_result(test, skip_reason))
                            continue
                        attempts = _run_one_test_attempts(
                            godot,
                            test,
                            project_path=Path(project_path).expanduser().resolve(),
                            artifacts_dir=artifacts,
                            trace=trace,
                            mode=mode,
                            executable=executable,
                            headless=headless,
                            update_snapshots=update_snapshots,
                            retries=retries,
                            test_timeout=test_timeout,
                            expected_failure_reason=_expected_failure_reason(test),
                            screenshots=screenshots,
                        )
                        reuse_attempts.append(attempts)
        else:
            reuse_attempts = [_skipped_test_result(test, _skip_reason(test) or "") for test in tests]
        for attempts in reuse_attempts:
            if isinstance(attempts, dict):
                _record_result(report, attempts)
                continue
            for attempt_result in attempts:
                _attach_godot_log(attempt_result, reuse_log_path)
            expected_reason = _expected_failure_reason(attempts[0])
            _record_result(report, _finalize_attempt_results(attempts, retries, expected_failure_reason=expected_reason))
    elif workers == 1:
        for index, test in enumerate(tests):
            if _max_failures_reached(report, max_failures):
                _record_interrupted_tests(report, tests[index:], reason=f"Stopped after {max_failures} failure(s)")
                break
            _record_result(
                report,
                _run_one_test_isolated(
                    test,
                    project_path=Path(project_path).expanduser().resolve(),
                    mode=mode,
                    executable=executable,
                    headless=headless,
                    timeout=timeout,
                    artifacts_dir=artifacts,
                    trace=trace,
                    update_snapshots=update_snapshots,
                    retries=retries,
                    test_timeout=test_timeout,
                    install=True,
                    screenshots=screenshots,
                ),
            )
    else:
        results = _run_tests_parallel(
            tests,
            project_path=Path(project_path).expanduser().resolve(),
            mode=mode,
            executable=executable,
            headless=headless,
            timeout=timeout,
            artifacts_dir=artifacts,
            trace=trace,
            update_snapshots=update_snapshots,
            retries=retries,
            test_timeout=test_timeout,
            workers=workers,
            screenshots=screenshots,
        )
        for result in results:
            _record_result(report, result)

    report["duration_ms"] = round((time.monotonic() - started) * 1000, 3)
    _write_html_report(report)
    _write_junit_report_if_requested(report)
    Path(report["results_json"]).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return report


def _record_result(report: dict[str, Any], result: dict[str, Any]) -> None:
    report["tests"].append(result)
    report["soft_assertion_failures"] += len(_result_soft_assertions(result))
    if result["status"] == "passed":
        report["passed"] += 1
        if result.get("flaky"):
            report["flaky"] += 1
        if result.get("outcome") == "expected_failed":
            report["expected_failed"] += 1
    elif result["status"] == "skipped":
        report["skipped"] += 1
    elif result["status"] == "interrupted":
        report["interrupted"] += 1
    else:
        report["failed"] += 1
        if result.get("outcome") == "unexpected_passed":
            report["unexpected_passed"] += 1


def _max_failures_reached(report: dict[str, Any], max_failures: int) -> bool:
    return max_failures > 0 and int(report.get("failed", 0)) >= max_failures


def _record_interrupted_tests(report: dict[str, Any], tests: list[DiscoveredTest], *, reason: str) -> None:
    if not tests:
        return
    report["stopped_early"] = True
    for test in tests:
        _record_result(report, _interrupted_test_result(test, reason))


def format_report(report: dict[str, Any]) -> str:
    if report.get("list_only"):
        return _format_list_report(report)
    lines = []
    for result in report["tests"]:
        marker = _result_marker(result)
        lines.append(f"{marker} {result['id']} ({result['duration_ms']} ms)")
        if result.get("annotation_reason"):
            lines.append(f"  reason: {result.get('annotation_reason')}")
        for step in result.get("steps", []):
            if not isinstance(step, dict):
                continue
            indent = "  " + "  " * int(step.get("depth", 0))
            marker = _step_marker(step)
            lines.append(f"{indent}{marker} {step.get('title', '')} ({step.get('duration_ms', 0)} ms)")
            error = step.get("error")
            if isinstance(error, dict) and error.get("message"):
                lines.append(f"{indent}  {error.get('message')}")
        for attachment in result.get("attachments", []):
            if not isinstance(attachment, dict):
                continue
            lines.append(
                f"  attachment {attachment.get('name', '')}: {attachment.get('path', '')} "
                f"({attachment.get('content_type', '')}, {attachment.get('bytes', 0)} bytes)"
            )
        for failure in _result_soft_assertions(result):
            lines.append(
                f"  soft assertion {failure.get('index', 0)} "
                f"({failure.get('method', 'expect')}): {failure.get('message', '')}"
            )
        for stream_name, stream in _result_output_streams(result):
            lines.append(
                f"  {stream_name}: {stream.get('path', '')} "
                f"({stream.get('line_count', 0)} lines, {stream.get('bytes', 0)} bytes)"
            )
        if result.get("retry_count", 0):
            lines.append(
                f"  attempts: {result.get('attempt_count')} "
                f"(retries used: {result.get('retry_count')}/{result.get('max_retries')})"
            )
        if result.get("error"):
            lines.append(f"  {result['error']['message']}")
        for name, path in result.get("artifacts", {}).items():
            lines.append(f"  {name}: {path}")
    lines.append(
        f"{report['passed']} passed, {report['failed']} failed, "
        f"{report.get('flaky', 0)} flaky, {report.get('skipped', 0)} skipped, "
        f"{report.get('interrupted', 0)} interrupted, "
        f"{report.get('expected_failed', 0)} expected failed, "
        f"{report.get('unexpected_passed', 0)} unexpected passed, "
        f"{report.get('soft_assertion_failures', 0)} soft assertion failures, "
        f"{report['total']} total ({report['duration_ms']} ms)"
    )
    if report.get("workers", 1) != 1:
        lines.append(f"workers: {report.get('workers')}")
    lines.append(f"results: {report.get('results_json', Path(report['artifacts_dir']) / 'results.json')}")
    lines.append(f"report: {report.get('report_html', Path(report['artifacts_dir']) / 'report.html')}")
    if report.get("junit_xml"):
        lines.append(f"junit: {report.get('junit_xml')}")
    return "\n".join(lines)


def _result_marker(result: dict[str, Any]) -> str:
    if result.get("outcome") == "expected_failed":
        return "EXPECTED-FAIL"
    if result.get("outcome") == "unexpected_passed":
        return "UNEXPECTED-PASS"
    if result.get("flaky"):
        return "FLAKY"
    if result.get("status") == "skipped":
        return "SKIP"
    if result.get("status") == "interrupted":
        return "INTERRUPTED"
    return "PASS" if result.get("status") == "passed" else "FAIL"


def _step_marker(step: dict[str, Any]) -> str:
    status = step.get("status")
    if status == "passed":
        return "STEP"
    if status == "skipped":
        return "STEP-SKIP"
    return "STEP-FAIL"


def _result_output_streams(result: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    output = result.get("output", {})
    if not isinstance(output, dict):
        return []
    streams = []
    for name in ("stdout", "stderr"):
        stream = output.get(name)
        if isinstance(stream, dict) and int(stream.get("bytes", 0)) > 0:
            streams.append((name, stream))
    return streams


def _result_soft_assertions(result: dict[str, Any]) -> list[dict[str, Any]]:
    failures = result.get("soft_assertions", [])
    if not isinstance(failures, list):
        return []
    return [failure for failure in failures if isinstance(failure, dict)]


def _short_repr(value: Any, *, max_length: int = 500) -> str:
    text = repr(value)
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def _poll_failure_message(
    description: str,
    expectation: str,
    *,
    timeout: float,
    last_value: Any,
    last_error: BaseException | None,
) -> str:
    message = f"Expected poll {description!r} {expectation} within {timeout} seconds"
    if last_error is not None:
        return f"{message}; last error was {type(last_error).__name__}: {last_error}"
    if last_value is _POLL_UNSET:
        return f"{message}; callable did not return a value"
    return f"{message}; last value was {_short_repr(last_value)}"


def _format_list_report(report: dict[str, Any]) -> str:
    selection = report.get("selection", {})
    lines = [
        (
            f"LIST {report.get('total', 0)} selected / "
            f"{selection.get('discovered', report.get('discovered', 0))} discovered"
        )
    ]
    if selection.get("grep"):
        lines.append(f"  grep: {selection.get('grep')}")
    if selection.get("grep_invert"):
        lines.append("  grep_invert: true")
    shard = selection.get("shard")
    if isinstance(shard, dict):
        lines.append(f"  shard: {shard.get('current')}/{shard.get('total')} from {shard.get('before_shard')} filtered")
    for result in report.get("tests", []):
        lines.append(f"  {result.get('id')}")
    lines.append(f"results: {report.get('results_json', Path(report['artifacts_dir']) / 'results.json')}")
    lines.append(f"report: {report.get('report_html', Path(report['artifacts_dir']) / 'report.html')}")
    if report.get("junit_xml"):
        lines.append(f"junit: {report.get('junit_xml')}")
    return "\n".join(lines)


def _listed_test_result(test: DiscoveredTest) -> dict[str, Any]:
    return {
        "id": test.id,
        "file": str(test.file),
        "name": test.name,
        "status": "listed",
        "annotations": _test_annotations(test),
        "attempt": 0,
        "artifact_id": _attempt_safe_id(test, 0),
        "attempt_count": 0,
        "retry_count": 0,
        "max_retries": 0,
        "flaky": False,
        "runtime_skip": False,
        "outcome": "listed",
        "duration_ms": 0,
        "error": None,
        "steps": [],
        "attachments": [],
        "soft_assertions": [],
        "output": _empty_output_summary(),
        "trace_summary": None,
        "artifacts": {},
        "diagnostics": None,
        "diagnostic_errors": [],
    }


def _skipped_test_result(test: DiscoveredTest, reason: str) -> dict[str, Any]:
    return {
        "id": test.id,
        "file": str(test.file),
        "name": test.name,
        "status": "skipped",
        "annotations": _test_annotations(test),
        "annotation_reason": reason,
        "attempt": 0,
        "artifact_id": _attempt_safe_id(test, 0),
        "attempt_count": 0,
        "retry_count": 0,
        "max_retries": 0,
        "flaky": False,
        "runtime_skip": False,
        "outcome": "skipped",
        "duration_ms": 0,
        "error": None,
        "steps": [],
        "attachments": [],
        "soft_assertions": [],
        "output": _empty_output_summary(),
        "trace_summary": None,
        "artifacts": {},
        "diagnostics": None,
        "diagnostic_errors": [],
    }


def _interrupted_test_result(test: DiscoveredTest, reason: str) -> dict[str, Any]:
    return {
        "id": test.id,
        "file": str(test.file),
        "name": test.name,
        "status": "interrupted",
        "annotations": _test_annotations(test),
        "annotation_reason": reason,
        "attempt": 0,
        "artifact_id": _attempt_safe_id(test, 0),
        "attempt_count": 0,
        "retry_count": 0,
        "max_retries": 0,
        "flaky": False,
        "runtime_skip": False,
        "outcome": "interrupted",
        "duration_ms": 0,
        "error": None,
        "steps": [],
        "attachments": [],
        "soft_assertions": [],
        "output": _empty_output_summary(),
        "trace_summary": None,
        "artifacts": {},
        "diagnostics": None,
        "diagnostic_errors": [],
    }


def _run_tests_parallel(
    tests: list[DiscoveredTest],
    *,
    project_path: Path,
    mode: str,
    executable: str,
    headless: bool,
    timeout: float,
    artifacts_dir: Path,
    trace: str,
    update_snapshots: bool,
    retries: int,
    test_timeout: float,
    workers: int,
    screenshots: str,
) -> list[dict[str, Any]]:
    ordered_results: list[dict[str, Any] | None] = [None] * len(tests)
    runnable: list[tuple[int, DiscoveredTest]] = []
    for index, test in enumerate(tests):
        skip_reason = _skip_reason(test)
        if skip_reason is not None:
            ordered_results[index] = _skipped_test_result(test, skip_reason)
        else:
            runnable.append((index, test))

    if not runnable:
        return [result for result in ordered_results if result is not None]

    # Install once before worker processes start so concurrent launches do not
    # race while copying add-on files into the same project directory.
    install_addon(project_path, enable=mode == "editor", autoload=mode == "runtime")

    config = {
        "project_path": str(project_path),
        "mode": mode,
        "executable": executable,
        "headless": headless,
        "timeout": timeout,
        "artifacts_dir": str(artifacts_dir),
        "trace": trace,
        "update_snapshots": update_snapshots,
        "retries": retries,
        "test_timeout": test_timeout,
        "screenshots": screenshots,
    }
    max_workers = min(workers, len(runnable))
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_run_test_worker, str(test.file), test.name, config): index
            for index, test in runnable
        }
        for future in as_completed(futures):
            ordered_results[futures[future]] = future.result()
    return [result for result in ordered_results if result is not None]


def _run_test_worker(test_file: str, test_name: str, config: dict[str, Any]) -> dict[str, Any]:
    test = _load_discovered_test(Path(test_file), test_name)
    return _run_one_test_isolated(
        test,
        project_path=Path(str(config["project_path"])),
        mode=str(config["mode"]),
        executable=str(config["executable"]),
        headless=bool(config["headless"]),
        timeout=float(config["timeout"]),
        artifacts_dir=Path(str(config["artifacts_dir"])),
        trace=str(config["trace"]),
        update_snapshots=bool(config["update_snapshots"]),
        retries=int(config["retries"]),
        test_timeout=float(config["test_timeout"]),
        install=False,
        screenshots=str(config["screenshots"]),
    )


def _load_discovered_test(file: Path, name: str) -> DiscoveredTest:
    module = _load_module(file)
    value = getattr(module, name, None)
    if not inspect.isfunction(value):
        raise TestRunnerError(f"Could not load test {file}::{name}")
    return DiscoveredTest(file=file, name=name, function=value)


def _run_one_test_isolated(
    test: DiscoveredTest,
    *,
    project_path: Path,
    mode: str,
    executable: str,
    headless: bool,
    timeout: float,
    artifacts_dir: Path,
    trace: str,
    update_snapshots: bool,
    retries: int,
    test_timeout: float,
    install: bool,
    screenshots: str,
) -> dict[str, Any]:
    skip_reason = _skip_reason(test)
    if skip_reason is not None:
        return _skipped_test_result(test, skip_reason)

    attempts: list[dict[str, Any]] = []
    expected_reason = _expected_failure_reason(test)
    for attempt in range(retries + 1):
        safe_id = _attempt_safe_id(test, attempt)
        log_path = artifacts_dir / f"{safe_id}-godot.log"
        with log_path.open("w", encoding="utf-8") as log_file:
            with Godot(
                project_path,
                mode=mode,
                executable=executable,
                headless=headless,
                timeout=timeout,
                stdout=log_file,
                install=install,
            ) as godot:
                attempt_result = _run_one_test(
                    godot,
                    test,
                    project_path=project_path,
                    artifacts_dir=artifacts_dir,
                    trace=trace,
                    mode=mode,
                    executable=executable,
                    headless=headless,
                    update_snapshots=update_snapshots,
                    attempt=attempt,
                    test_timeout=test_timeout,
                    screenshots=screenshots,
                )
        _attach_godot_log(attempt_result, log_path)
        attempts.append(attempt_result)
        if (
            attempt_result["status"] in {"passed", "skipped"}
            or (expected_reason is not None and attempt_result["status"] == "failed")
        ):
            break
    return _finalize_attempt_results(attempts, retries, expected_failure_reason=expected_reason)


def _run_one_test_attempts(
    godot: GodotClient,
    test: DiscoveredTest,
    *,
    project_path: Path,
    artifacts_dir: Path,
    trace: str,
    mode: str,
    executable: str,
    headless: bool,
    update_snapshots: bool,
    retries: int,
    test_timeout: float,
    expected_failure_reason: str | None = None,
    screenshots: str = "off",
) -> list[dict[str, Any]]:
    attempts = []
    for attempt in range(retries + 1):
        result = _run_one_test(
            godot,
            test,
            project_path=project_path,
            artifacts_dir=artifacts_dir,
            trace=trace,
            mode=mode,
            executable=executable,
            headless=headless,
            update_snapshots=update_snapshots,
            attempt=attempt,
            test_timeout=test_timeout,
            screenshots=screenshots,
        )
        attempts.append(result)
        if (
            result["status"] in {"passed", "skipped"}
            or (expected_failure_reason is not None and result["status"] == "failed")
        ):
            break
    return attempts


def _finalize_attempt_results(
    attempts: list[dict[str, Any]],
    max_retries: int,
    *,
    expected_failure_reason: str | None = None,
) -> dict[str, Any]:
    if not attempts:
        raise TestRunnerError("Cannot finalize an empty attempt result list")
    final = dict(attempts[-1])
    retry_count = len(attempts) - 1
    flaky = final.get("status") == "passed" and any(attempt.get("status") == "failed" for attempt in attempts[:-1])
    final["attempt_count"] = len(attempts)
    final["retry_count"] = retry_count
    final["max_retries"] = max_retries
    final["flaky"] = flaky

    if final.get("status") == "skipped":
        final["flaky"] = False
        final["outcome"] = "skipped"
    elif expected_failure_reason is not None:
        final["expected_failure"] = True
        final["annotation_reason"] = expected_failure_reason
        final["flaky"] = False
        if final.get("status") == "failed":
            final["status"] = "passed"
            final["outcome"] = "expected_failed"
        else:
            reason = f": {expected_failure_reason}" if expected_failure_reason else ""
            final["status"] = "failed"
            final["outcome"] = "unexpected_passed"
            final["error"] = {
                "type": "UnexpectedPassError",
                "message": f"Expected failure passed unexpectedly{reason}",
                "traceback": "",
            }
    else:
        final["outcome"] = "flaky" if flaky else "passed" if final.get("status") == "passed" else "failed"

    if len(attempts) > 1:
        final["attempts"] = attempts
    return final


@contextmanager
def _test_timeout(test: DiscoveredTest, timeout: float):
    if timeout <= 0:
        yield
        return
    if not hasattr(signal, "setitimer"):
        raise TestRunnerError("Per-test timeout requires signal.setitimer support")

    def _handle_timeout(signum: int, frame: Any) -> None:
        raise TestTimeoutError(f"Timed out after {timeout} seconds while running {test.id}")

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handle_timeout)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer != (0.0, 0.0):
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def _run_one_test(
    godot: GodotClient,
    test: DiscoveredTest,
    *,
    project_path: Path,
    artifacts_dir: Path,
    trace: str,
    mode: str,
    executable: str,
    headless: bool,
    update_snapshots: bool,
    attempt: int = 0,
    test_timeout: float = 0.0,
    screenshots: str = "off",
) -> dict[str, Any]:
    started = time.monotonic()
    status = "passed"
    error: dict[str, Any] | None = None
    skip_reason: str | None = None
    artifact_paths: dict[str, str] = {}
    diagnostics: dict[str, Any] | None = None
    diagnostic_errors: list[dict[str, str]] = []
    safe_id = _attempt_safe_id(test, attempt)
    step_recorder = _StepRecorder()
    soft_assertions = _SoftAssertions()
    stdout_buffer = StringIO()
    stderr_buffer = StringIO()
    test_info = TestInfo(
        test,
        project_path=project_path,
        artifacts_dir=artifacts_dir,
        artifact_id=safe_id,
        attempt=attempt,
        mode=mode,
    )

    trace_enabled = trace != "off"
    if trace_enabled:
        godot.trace_start(clear=True, max_events=5000)

    step_token = _CURRENT_STEP_RECORDER.set(step_recorder)
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            with _test_timeout(test, test_timeout):
                _call_test(
                    test,
                    godot,
                    project_path,
                    artifacts_dir,
                    mode,
                    executable,
                    headless,
                    test_info,
                    soft_assertions,
                    update_snapshots=update_snapshots,
                )
    except TestSkipped as exc:
        status = "skipped"
        skip_reason = str(exc)
    except BaseException as exc:
        status = "failed"
        error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        }
        diagnostics = _collect_failure_diagnostics(
            godot,
            test,
            mode=mode,
            artifacts_dir=artifacts_dir,
            safe_id=safe_id,
            artifact_paths=artifact_paths,
            diagnostic_errors=diagnostic_errors,
        )
    finally:
        _CURRENT_STEP_RECORDER.reset(step_token)

    output_summary = _capture_python_output(
        stdout_buffer.getvalue(),
        stderr_buffer.getvalue(),
        artifacts_dir=artifacts_dir,
        safe_id=safe_id,
        artifact_paths=artifact_paths,
    )

    if _should_capture_screenshot(screenshots, status):
        _capture_attempt_screenshot(
            godot,
            artifacts_dir=artifacts_dir,
            safe_id=safe_id,
            artifact_paths=artifact_paths,
            diagnostic_errors=diagnostic_errors,
        )

    if trace_enabled:
        godot.trace_stop()
        events = godot.trace_events(clear=True)
        trace_summary = _trace_summary(events)
        if trace == "on" or status == "failed":
            trace_file = artifacts_dir / f"{safe_id}-trace.json"
            trace_file.write_text(
                json.dumps(events, indent=2, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            artifact_paths["trace"] = str(trace_file)
    else:
        trace_summary = None

    return {
        "id": test.id,
        "file": str(test.file),
        "name": test.name,
        "status": status,
        "annotations": _test_annotations(test),
        "annotation_reason": skip_reason,
        "attempt": attempt,
        "artifact_id": safe_id,
        "attempt_count": 1,
        "retry_count": 0,
        "max_retries": 0,
        "test_timeout": test_timeout,
        "flaky": False,
        "runtime_skip": status == "skipped",
        "outcome": "skipped" if status == "skipped" else "passed" if status == "passed" else "failed",
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
        "error": error,
        "steps": step_recorder.steps,
        "attachments": test_info.attachments,
        "soft_assertions": soft_assertions.failures,
        "output": output_summary,
        "trace_summary": trace_summary,
        "artifacts": artifact_paths,
        "diagnostics": diagnostics,
        "diagnostic_errors": diagnostic_errors,
    }


def _call_test(
    test: DiscoveredTest,
    godot: GodotClient,
    project_path: Path,
    artifacts_dir: Path,
    mode: str,
    executable: str,
    headless: bool,
    test_info: TestInfo,
    soft_assertions: _SoftAssertions,
    *,
    update_snapshots: bool,
) -> None:
    before_hooks = _test_hooks(test, "before_each")
    after_hooks = _test_hooks(test, "after_each")
    snapshots_dir = test.file.parent / "__snapshots__"
    scene_expect = expect_scene(
        godot,
        snapshots_dir=snapshots_dir,
        artifacts_dir=artifacts_dir,
        update=update_snapshots,
    )

    def soft_expect(target: Any) -> _SoftExpect:
        return soft_assertions.expect(target)

    available = {
        "godot": godot,
        "expect": expect,
        "expect_engine": expect_engine(godot),
        "expect_poll": expect_poll,
        "soft_expect": soft_expect,
        "expect_scene": scene_expect,
        "expect_scene_file": lambda path: expect_scene_file(project_path, path),
        "expect_editor": expect_editor(godot),
        "expect_log": expect_log(godot),
        "expect_physics2d": expect_physics2d(godot),
        "expect_physics3d": expect_physics3d(godot),
        "expect_audio": expect_audio(godot),
        "expect_navigation": expect_navigation(godot),
        "expect_project": expect_project(godot),
        "expect_project_scene": lambda path: expect_project_scene(godot, path),
        "expect_resource": lambda path: expect_resource(godot, path),
        "expect_resource_class": lambda class_name: expect_resource_class(godot, class_name),
        "expect_node_class": lambda class_name: expect_node_class(godot, class_name),
        "expect_runtime_scene": expect_runtime_scene(godot),
        "expect_script_class": lambda class_name: expect_script_class(godot, class_name),
        "expect_signal": lambda selector=None, signal=None, root=None, watch_id=None, once=False: expect_signal(
            godot,
            selector,
            signal,
            root=root,
            watch_id=watch_id,
            once=once,
        ),
        "expect_trace": expect_trace(godot),
        "expect_viewport": expect_viewport(godot),
        "get_by_role": lambda role, name=None, name_contains=None, root=None: godot.get_by_role(
            role,
            name=name,
            name_contains=name_contains,
            root=root,
        ),
        "get_by_test_id": lambda test_id, key="test_id", root=None: godot.get_by_test_id(
            test_id,
            key=key,
            root=root,
        ),
        "editor_locator": lambda selector, root=None: godot.editor_locator(selector, root=root),
        "editor_get_by_role": lambda role, name=None, name_contains=None, root=None: godot.editor_get_by_role(
            role,
            name=name,
            name_contains=name_contains,
            root=root,
        ),
        "editor_get_by_test_id": lambda test_id, key="test_id", root=None: godot.editor_get_by_test_id(
            test_id,
            key=key,
            root=root,
        ),
        "expect_inspector": expect_inspector,
        "expect_script": lambda path: expect_script(godot, path),
        "expect_script_file": lambda path: expect_script_file(
            project_path,
            path,
            executable=executable,
            headless=headless,
            artifacts_dir=artifacts_dir,
        ),
        "expect_filesystem": lambda path="res://": expect_filesystem(godot, path),
        "project_path": project_path,
        "artifacts_dir": artifacts_dir,
        "snapshots_dir": snapshots_dir,
        "mode": mode,
        "step": _test_step,
        "test_info": test_info,
        "attach": test_info.attach,
    }

    primary_error: BaseException | None = None
    try:
        for hook in before_hooks:
            _call_fixture_function(hook, hook.__name__, available)
        _call_fixture_function(test.function, test.name, available)
    except BaseException as exc:
        primary_error = exc

    after_errors: list[BaseException] = []
    for hook in after_hooks:
        try:
            _call_fixture_function(hook, hook.__name__, available)
        except BaseException as exc:
            after_errors.append(exc)

    if after_errors:
        if primary_error is None or isinstance(primary_error, TestSkipped):
            raise _combine_hook_errors("after_each", after_errors) from after_errors[0]
        _add_hook_error_notes(primary_error, "after_each", after_errors)

    if primary_error is not None:
        raise primary_error

    soft_assertions.assert_all()


def _call_fixture_function(function: Callable[..., Any], name: str, available: dict[str, Any]) -> None:
    signature = inspect.signature(function)
    kwargs: dict[str, Any] = {}
    for parameter in signature.parameters.values():
        if parameter.kind not in (parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY):
            raise TestRunnerError(f"Unsupported parameter in {name}: {parameter.name}")
        if parameter.name not in available:
            raise TestRunnerError(f"Unknown fixture for {name}: {parameter.name}")
        kwargs[parameter.name] = available[parameter.name]
    function(**kwargs)


def _combine_hook_errors(kind: str, errors: list[BaseException]) -> BaseException:
    if len(errors) == 1:
        return errors[0]
    message = "; ".join(f"{type(error).__name__}: {error}" for error in errors)
    return TestRunnerError(f"Multiple {kind} hooks failed: {message}")


def _add_hook_error_notes(error: BaseException, kind: str, hook_errors: list[BaseException]) -> None:
    add_note = getattr(error, "add_note", None)
    if not callable(add_note):
        return
    for hook_error in hook_errors:
        add_note(f"{kind} hook failed: {type(hook_error).__name__}: {hook_error}")


def _test_step(title: str, action: Callable[[], Any] | None = None) -> Any:
    recorder = _CURRENT_STEP_RECORDER.get()
    if recorder is None:
        raise TestRunnerError("step fixture is only available while a test is running")
    context = _StepContext(recorder, title)
    if action is None:
        return context
    with context:
        return action()


def _load_module(file: Path) -> ModuleType:
    module_name = f"godot_playwright_user_test_{abs(hash(file))}"
    spec = importlib.util.spec_from_file_location(module_name, file)
    if spec is None or spec.loader is None:
        raise TestRunnerError(f"Could not load test module: {file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException as exc:
        raise TestRunnerError(f"Failed to import {file}: {exc}") from exc
    return module


def _safe_test_id(test: DiscoveredTest) -> str:
    raw = f"{test.file.stem}-{test.name}"
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in raw)


def _attempt_safe_id(test: DiscoveredTest, attempt: int) -> str:
    safe_id = _safe_test_id(test)
    return safe_id if attempt == 0 else f"{safe_id}-retry{attempt}"


def _attachment_filename(name: str, index: int, suffix: str = "") -> str:
    safe_name = "".join(char if char.isalnum() or char in "._-" else "_" for char in str(name)).strip("._")
    safe_name = safe_name or "attachment"
    extension = suffix if suffix.startswith(".") else f".{suffix}" if suffix else ""
    if extension and safe_name.endswith(extension):
        return f"{index:02d}-{safe_name}"
    return f"{index:02d}-{safe_name}{extension}"


def _attachment_body_payload(body: str | bytes | dict[str, Any] | list[Any]) -> tuple[bytes, str, str]:
    if isinstance(body, bytes):
        return body, ".bin", "application/octet-stream"
    if isinstance(body, (dict, list)):
        return (
            json.dumps(body, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8"),
            ".json",
            "application/json",
        )
    return str(body).encode("utf-8"), ".txt", "text/plain"


def _safe_result_id(result: dict[str, Any]) -> str:
    if result.get("artifact_id"):
        return str(result["artifact_id"])
    raw = f"{Path(str(result.get('file', 'test'))).stem}-{result.get('name', 'test')}"
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in raw)


def _empty_output_summary() -> dict[str, Any]:
    return {
        "stdout": _stream_output_summary("", None),
        "stderr": _stream_output_summary("", None),
    }


def _capture_python_output(
    stdout_text: str,
    stderr_text: str,
    *,
    artifacts_dir: Path,
    safe_id: str,
    artifact_paths: dict[str, str],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name, text in (("stdout", stdout_text), ("stderr", stderr_text)):
        output_path: Path | None = None
        if text:
            output_path = artifacts_dir / f"{safe_id}-{name}.txt"
            output_path.write_text(text, encoding="utf-8")
            artifact_paths[f"python_{name}"] = str(output_path)
        output[name] = _stream_output_summary(text, output_path)
    return output


def _stream_output_summary(text: str, path: Path | None, *, tail_lines: int = 80) -> dict[str, Any]:
    lines = text.splitlines()
    return {
        "bytes": len(text.encode("utf-8")),
        "line_count": len(lines),
        "tail": lines[-tail_lines:],
        "path": str(path) if path is not None else "",
    }


def _should_capture_screenshot(screenshots: str, status: str) -> bool:
    if screenshots == "on":
        return True
    if screenshots == "only-on-failure":
        return status == "failed"
    return False


def _capture_attempt_screenshot(
    godot: GodotClient,
    *,
    artifacts_dir: Path,
    safe_id: str,
    artifact_paths: dict[str, str],
    diagnostic_errors: list[dict[str, str]],
) -> None:
    screenshot_path = artifacts_dir / f"{safe_id}-screenshot.png"
    try:
        godot.screenshot(screenshot_path)
    except BaseException as exc:
        diagnostic_errors.append(
            {
                "source": "viewport.screenshot",
                "type": type(exc).__name__,
                "message": str(exc),
            }
        )
        return
    if screenshot_path.exists():
        artifact_paths["screenshot"] = str(screenshot_path)


def _collect_failure_diagnostics(
    godot: GodotClient,
    test: DiscoveredTest,
    *,
    mode: str,
    artifacts_dir: Path,
    safe_id: str,
    artifact_paths: dict[str, str],
    diagnostic_errors: list[dict[str, str]],
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "id": test.id,
        "mode": mode,
        "captured_at_ms": round(time.time() * 1000),
        "engine": _diagnostic_rpc("engine.info", lambda: godot.rpc("engine.info"), diagnostic_errors),
        "scene": _diagnostic_rpc("scene.current", godot.current_scene, diagnostic_errors),
        "live_log": _diagnostic_rpc(
            "log.events",
            lambda: {
                "events": godot.log_events(),
                "error_count": len(godot.log_events(severity="error")),
                "warning_count": len(godot.log_events(severity="warning")),
            },
            diagnostic_errors,
        ),
    }
    if mode == "editor":
        diagnostics["editor"] = _diagnostic_rpc("editor.status", godot.editor_status, diagnostic_errors)

    snapshot = _diagnostic_rpc(
        "tree.snapshot",
        lambda: godot.snapshot(max_depth=5, include_properties=True),
        diagnostic_errors,
    )
    if isinstance(snapshot, dict):
        snapshot_file = artifacts_dir / f"{safe_id}-failure-scene.json"
        snapshot_file.write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        artifact_paths["failure_scene"] = str(snapshot_file)
        diagnostics["scene_snapshot"] = _snapshot_summary(snapshot)
        diagnostics["scene_snapshot_artifact"] = str(snapshot_file)
    return diagnostics


def _diagnostic_rpc(
    label: str,
    action: Callable[[], Any],
    diagnostic_errors: list[dict[str, str]],
) -> Any:
    try:
        return action()
    except BaseException as exc:
        diagnostic_errors.append(
            {
                "source": label,
                "type": type(exc).__name__,
                "message": str(exc),
            }
        )
        return None


def _snapshot_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": snapshot.get("name", ""),
        "class": snapshot.get("class", ""),
        "path": snapshot.get("path", ""),
        "child_count": snapshot.get("child_count", 0),
        "tree_node_count": _count_snapshot_nodes(snapshot),
    }


def _count_snapshot_nodes(snapshot: Any) -> int:
    if not isinstance(snapshot, dict):
        return 0
    total = 1
    for child in snapshot.get("children", []):
        total += _count_snapshot_nodes(child)
    return total


def _trace_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    type_counts = Counter(str(event.get("type", "")) for event in events if isinstance(event, dict))
    preview = []
    for event in events[:20]:
        if not isinstance(event, dict):
            continue
        preview.append(
            {
                "type": str(event.get("type", "")),
                "ts_ms": event.get("ts_ms"),
                "uptime_ms": event.get("uptime_ms"),
                "data": event.get("data", {}),
            }
        )
    return {
        "event_count": len(events),
        "top_types": [{"type": event_type, "count": count} for event_type, count in type_counts.most_common(8)],
        "preview": preview,
    }


def _attach_godot_log(result: dict[str, Any], log_path: Path) -> None:
    artifacts = result.setdefault("artifacts", {})
    artifacts["godot_log"] = str(log_path)
    result["godot_log_summary"] = _godot_log_summary(log_path)
    _write_diagnostics_if_failed(result, log_path.parent)


def _godot_log_summary(log_path: Path, *, tail_lines: int = 80) -> dict[str, Any]:
    if not log_path.exists():
        return {
            "bytes": 0,
            "line_count": 0,
            "error_count": 0,
            "warning_count": 0,
            "tail": [],
        }
    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    error_markers = ("ERROR:", "SCRIPT ERROR", "ERR_", "Failed", "Traceback")
    warning_markers = ("WARNING:", "WARN_", "Warning")
    return {
        "bytes": log_path.stat().st_size,
        "line_count": len(lines),
        "error_count": sum(1 for line in lines if any(marker in line for marker in error_markers)),
        "warning_count": sum(1 for line in lines if any(marker in line for marker in warning_markers)),
        "tail": lines[-tail_lines:],
    }


def _write_diagnostics_if_failed(result: dict[str, Any], artifacts_dir: Path) -> None:
    if result.get("status") != "failed":
        result.pop("diagnostics", None)
        result.pop("diagnostic_errors", None)
        return
    diagnostics = result.get("diagnostics")
    if not isinstance(diagnostics, dict):
        diagnostics = {
            "id": result.get("id", ""),
            "mode": "",
            "captured_at_ms": round(time.time() * 1000),
        }
    diagnostics["status"] = result.get("status")
    diagnostics["duration_ms"] = result.get("duration_ms")
    diagnostics["error"] = result.get("error")
    diagnostics["steps"] = result.get("steps", [])
    diagnostics["attachments"] = result.get("attachments", [])
    diagnostics["soft_assertions"] = result.get("soft_assertions", [])
    diagnostics["output"] = result.get("output", _empty_output_summary())
    diagnostics["trace_summary"] = result.get("trace_summary")
    diagnostics["godot_log_summary"] = result.get("godot_log_summary")
    diagnostics["artifacts"] = result.get("artifacts", {})
    diagnostics["diagnostic_errors"] = result.get("diagnostic_errors", [])
    diagnostics["summary"] = _diagnostics_summary(diagnostics)

    diagnostics_file = artifacts_dir / f"{_safe_result_id(result)}-diagnostics.json"
    diagnostics_file.write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    result["diagnostics"] = diagnostics["summary"]
    result["artifacts"]["diagnostics"] = str(diagnostics_file)


def _diagnostics_summary(diagnostics: dict[str, Any]) -> dict[str, Any]:
    log_summary = diagnostics.get("godot_log_summary", {})
    trace_summary = diagnostics.get("trace_summary", {})
    snapshot_summary = diagnostics.get("scene_snapshot", {})
    return {
        "error_type": (diagnostics.get("error") or {}).get("type", ""),
        "error_message": (diagnostics.get("error") or {}).get("message", ""),
        "trace_events": trace_summary.get("event_count", 0) if isinstance(trace_summary, dict) else 0,
        "godot_log_errors": log_summary.get("error_count", 0) if isinstance(log_summary, dict) else 0,
        "godot_log_warnings": log_summary.get("warning_count", 0) if isinstance(log_summary, dict) else 0,
        "scene_root": snapshot_summary.get("name", "") if isinstance(snapshot_summary, dict) else "",
        "scene_nodes": snapshot_summary.get("tree_node_count", 0) if isinstance(snapshot_summary, dict) else 0,
        "soft_assertion_failures": len(diagnostics.get("soft_assertions", [])),
        "diagnostic_error_count": len(diagnostics.get("diagnostic_errors", [])),
    }


def _write_html_report(report: dict[str, Any]) -> Path:
    artifacts_dir = Path(report["artifacts_dir"])
    html_path = Path(report.get("report_html", artifacts_dir / "report.html"))
    html_path.write_text(_render_html_report(report, html_path.parent), encoding="utf-8")
    return html_path


def _write_junit_report_if_requested(report: dict[str, Any]) -> Path | None:
    raw_path = report.get("junit_xml")
    if not raw_path:
        return None
    path = Path(str(raw_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_junit_report(report, path)
    return path


def _write_junit_report(report: dict[str, Any], path: Path) -> None:
    tests = [result for result in report.get("tests", []) if isinstance(result, dict)]
    skipped_count = sum(1 for result in tests if result.get("status") in {"skipped", "interrupted", "listed"})
    failure_count = int(report.get("failed", 0))
    suite_attrs = {
        "name": "godot-playwright",
        "tests": str(len(tests)),
        "failures": str(failure_count),
        "errors": "0",
        "skipped": str(skipped_count),
        "time": _junit_seconds(report.get("duration_ms", 0)),
    }
    root = ET.Element("testsuites", suite_attrs)
    suite = ET.SubElement(root, "testsuite", suite_attrs)
    suite_properties = ET.SubElement(suite, "properties")
    for name in (
        "project",
        "mode",
        "workers",
        "screenshots",
        "max_failures",
        "soft_assertion_failures",
        "results_json",
        "report_html",
    ):
        if name in report:
            ET.SubElement(suite_properties, "property", {"name": name, "value": str(report.get(name, ""))})

    for result in tests:
        testcase = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": _junit_classname(result),
                "name": str(result.get("name", result.get("id", ""))),
                "file": str(result.get("file", "")),
                "time": _junit_seconds(result.get("duration_ms", 0)),
            },
        )
        properties = ET.SubElement(testcase, "properties")
        for name in ("id", "status", "outcome", "annotation_reason", "artifact_id"):
            if result.get(name) not in (None, ""):
                ET.SubElement(properties, "property", {"name": name, "value": str(result.get(name, ""))})
        soft_assertions = _result_soft_assertions(result)
        if soft_assertions:
            ET.SubElement(
                properties,
                "property",
                {"name": "soft_assertion_failures", "value": str(len(soft_assertions))},
            )
            for failure in soft_assertions:
                ET.SubElement(
                    properties,
                    "property",
                    {
                        "name": f"soft_assertion.{failure.get('index', 0)}",
                        "value": f"{failure.get('method', 'expect')}: {failure.get('message', '')}",
                    },
                )
        artifacts = result.get("artifacts", {})
        if isinstance(artifacts, dict):
            for artifact_name, artifact_path in sorted(artifacts.items()):
                ET.SubElement(
                    properties,
                    "property",
                    {"name": f"artifact.{artifact_name}", "value": str(artifact_path)},
                )
        if result.get("status") == "failed":
            error = result.get("error") if isinstance(result.get("error"), dict) else {}
            failure = ET.SubElement(
                testcase,
                "failure",
                {
                    "type": str(error.get("type", "Failure")),
                    "message": str(error.get("message", "")),
                },
            )
            failure.text = str(error.get("traceback", error.get("message", "")))
        elif result.get("status") in {"skipped", "interrupted", "listed"}:
            ET.SubElement(
                testcase,
                "skipped",
                {
                    "type": str(result.get("status", "skipped")),
                    "message": str(result.get("annotation_reason", result.get("outcome", ""))),
                },
            )
        stdout_text = _junit_stream_text(result, "stdout")
        stderr_text = _junit_stream_text(result, "stderr")
        if stdout_text:
            ET.SubElement(testcase, "system-out").text = stdout_text
        if stderr_text:
            ET.SubElement(testcase, "system-err").text = stderr_text

    tree = ET.ElementTree(root)
    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _junit_seconds(milliseconds: Any) -> str:
    try:
        return f"{float(milliseconds) / 1000.0:.6f}"
    except (TypeError, ValueError):
        return "0.000000"


def _junit_classname(result: dict[str, Any]) -> str:
    raw_file = str(result.get("file", ""))
    if not raw_file:
        return "godot_playwright"
    return Path(raw_file).with_suffix("").as_posix().replace("/", ".").strip(".") or "godot_playwright"


def _junit_stream_text(result: dict[str, Any], stream_name: str) -> str:
    output = result.get("output", {})
    if not isinstance(output, dict):
        return ""
    stream = output.get(stream_name, {})
    if not isinstance(stream, dict) or int(stream.get("bytes", 0)) <= 0:
        return ""
    tail = stream.get("tail", [])
    if isinstance(tail, list):
        return "\n".join(str(line) for line in tail)
    return str(tail)


def _render_html_report(report: dict[str, Any], report_dir: Path) -> str:
    summary_cards = [
        ("Project", report["project"]),
        ("Mode", report["mode"]),
        ("Discovered", str(report.get("discovered", report["total"]))),
        ("Total", str(report["total"])),
        ("Passed", str(report["passed"])),
        ("Failed", str(report["failed"])),
        ("Flaky", str(report.get("flaky", 0))),
        ("Skipped", str(report.get("skipped", 0))),
        ("Interrupted", str(report.get("interrupted", 0))),
        ("Expected Failed", str(report.get("expected_failed", 0))),
        ("Unexpected Passed", str(report.get("unexpected_passed", 0))),
        ("Soft Assertions", str(report.get("soft_assertion_failures", 0))),
        ("Duration", f"{report['duration_ms']} ms"),
        ("Reuse Godot", "yes" if report.get("reuse_godot") else "no"),
        ("List Only", "yes" if report.get("list_only") else "no"),
        ("Retries", str(report.get("retries", 0))),
        ("Workers", str(report.get("workers", 1))),
        ("Test Timeout", f"{report.get('test_timeout', 0)} s" if report.get("test_timeout") else "off"),
        ("Screenshots", str(report.get("screenshots", "off"))),
        ("Max Failures", str(report.get("max_failures", 0)) if report.get("max_failures") else "off"),
        ("Stopped Early", "yes" if report.get("stopped_early") else "no"),
    ]
    tests_html = "\n".join(_render_test_card(result, report_dir) for result in report.get("tests", []))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Godot Playwright Report</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0f1115;
      --panel: #151922;
      --panel-2: #11151d;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --border: #2a3140;
      --accent: #7dd3fc;
      --pass: #34d399;
      --fail: #f87171;
      --warn: #fbbf24;
      --mono: SFMono-Regular, Consolas, "Liberation Mono", monospace;
      --sans: Verdana, Geneva, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: var(--sans);
      line-height: 1.45;
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    header {{
      padding: 24px 28px 18px;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(180deg, #131722 0%, #0f1115 100%);
    }}
    .eyebrow {{
      margin: 0 0 6px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    h1 {{
      margin: 0;
      font-size: 28px;
      line-height: 1.1;
    }}
    .subhead {{
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 14px;
    }}
    main {{
      padding: 20px 28px 28px;
      max-width: 1400px;
      margin: 0 auto;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    .metric {{
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: 6px;
      padding: 14px 16px;
    }}
    .metric .label {{
      display: block;
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 6px;
    }}
    .metric .value {{
      font-size: 18px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin: 18px 0 14px;
    }}
    .toolbar input {{
      flex: 1 1 280px;
      min-width: 220px;
      border: 1px solid var(--border);
      background: var(--panel-2);
      color: var(--text);
      border-radius: 6px;
      padding: 10px 12px;
      font: inherit;
    }}
    .pill {{
      border: 1px solid var(--border);
      background: var(--panel);
      color: var(--text);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 13px;
      cursor: pointer;
    }}
    .pill[aria-pressed="true"] {{
      border-color: var(--accent);
      color: var(--accent);
    }}
    .tests {{
      display: grid;
      gap: 12px;
    }}
    details.test {{
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--panel);
      overflow: clip;
    }}
    details.test[open] {{
      box-shadow: 0 0 0 1px rgba(125, 211, 252, 0.08) inset;
    }}
    summary {{
      list-style: none;
      cursor: pointer;
      display: grid;
      grid-template-columns: 132px 1fr auto;
      gap: 14px;
      align-items: center;
      padding: 14px 16px;
    }}
    summary::-webkit-details-marker {{ display: none; }}
    .status {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 112px;
      padding: 5px 10px;
      border-radius: 999px;
      font-size: 12px;
      letter-spacing: 0.04em;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .status.pass {{ background: rgba(52, 211, 153, 0.12); color: var(--pass); }}
    .status.fail {{ background: rgba(248, 113, 113, 0.12); color: var(--fail); }}
    .status.flaky {{ background: rgba(251, 191, 36, 0.12); color: var(--warn); }}
    .status.list {{ background: rgba(125, 211, 252, 0.12); color: var(--accent); }}
    .status.skip {{ background: rgba(156, 163, 175, 0.12); color: var(--muted); }}
    .status.interrupted {{ background: rgba(251, 191, 36, 0.12); color: var(--warn); }}
    .status.expected-fail {{ background: rgba(251, 191, 36, 0.12); color: var(--warn); }}
    .status.unexpected-pass {{ background: rgba(248, 113, 113, 0.12); color: var(--fail); }}
    .test-title {{
      min-width: 0;
    }}
    .test-title .id {{
      display: block;
      font-family: var(--mono);
      font-size: 13px;
      color: var(--text);
      overflow-wrap: anywhere;
    }}
    .test-title .meta {{
      display: block;
      margin-top: 3px;
      font-size: 12px;
      color: var(--muted);
    }}
    .duration {{
      font-family: var(--mono);
      font-size: 12px;
      color: var(--muted);
      white-space: nowrap;
    }}
    .body {{
      border-top: 1px solid var(--border);
      padding: 14px 16px 16px;
      display: grid;
      gap: 14px;
    }}
    .block {{
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--panel-2);
      padding: 12px;
    }}
    .block h2 {{
      margin: 0 0 10px;
      font-size: 13px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .screenshot-preview {{
      display: block;
      width: 100%;
      max-width: 720px;
      height: auto;
      border: 1px solid var(--border);
      border-radius: 4px;
      background: #05070a;
    }}
    pre {{
      margin: 0;
      font-family: var(--mono);
      font-size: 12px;
      line-height: 1.5;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: #dbe4f0;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      text-align: left;
      padding: 6px 0;
      border-bottom: 1px solid rgba(42, 49, 64, 0.6);
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 8px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.04);
      color: var(--text);
      font-size: 12px;
      font-family: var(--mono);
    }}
    .empty {{
      color: var(--muted);
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <header>
    <p class="eyebrow">Godot Playwright</p>
    <h1>Test Report</h1>
    <p class="subhead">Project {escape(str(report["project"]))}</p>
  </header>
  <main>
    <section class="metrics">
      {''.join(_render_metric(label, value) for label, value in summary_cards)}
    </section>
    <section class="toolbar">
      <input id="search" type="search" placeholder="Filter tests, artifacts, or errors">
      <button class="pill" data-filter="all" aria-pressed="true">All</button>
      <button class="pill" data-filter="passed" aria-pressed="false">Passed</button>
      <button class="pill" data-filter="flaky" aria-pressed="false">Flaky</button>
      <button class="pill" data-filter="failed" aria-pressed="false">Failed</button>
      <button class="pill" data-filter="skipped" aria-pressed="false">Skipped</button>
      <button class="pill" data-filter="interrupted" aria-pressed="false">Interrupted</button>
      <button class="pill" data-filter="expected_failed" aria-pressed="false">Expected Failed</button>
      <button class="pill" data-filter="unexpected_passed" aria-pressed="false">Unexpected Passed</button>
      <button class="pill" data-filter="listed" aria-pressed="false">Listed</button>
    </section>
    <section class="tests" id="tests">
      {tests_html if tests_html else '<div class="empty">No tests discovered.</div>'}
    </section>
  </main>
  <script>
    const search = document.getElementById('search');
    const buttons = Array.from(document.querySelectorAll('[data-filter]'));
    const tests = Array.from(document.querySelectorAll('details.test'));
    let activeFilter = 'all';

    function applyFilters() {{
      const query = search.value.trim().toLowerCase();
      for (const test of tests) {{
        const status = test.dataset.status;
        const haystack = test.innerText.toLowerCase();
        const matchesQuery = !query || haystack.includes(query);
        const matchesStatus = activeFilter === 'all' || status === activeFilter;
        test.style.display = matchesQuery && matchesStatus ? '' : 'none';
      }}
    }}

    search.addEventListener('input', applyFilters);
    for (const button of buttons) {{
      button.addEventListener('click', () => {{
        activeFilter = button.dataset.filter;
        for (const other of buttons) other.setAttribute('aria-pressed', other === button ? 'true' : 'false');
        applyFilters();
      }});
    }}
  </script>
</body>
</html>
"""


def _render_metric(label: str, value: str) -> str:
    return (
        '<div class="metric">'
        f'<span class="label">{escape(label)}</span>'
        f'<span class="value">{escape(value)}</span>'
        "</div>"
    )


def _render_test_card(result: dict[str, Any], report_dir: Path) -> str:
    status = str(result.get("status", "unknown"))
    outcome = str(result.get("outcome", status))
    if outcome == "expected_failed":
        marker_class = "expected-fail"
        label = "expected fail"
        filter_status = "expected_failed"
    elif outcome == "unexpected_passed":
        marker_class = "unexpected-pass"
        label = "unexpected pass"
        filter_status = "unexpected_passed"
    elif result.get("flaky"):
        marker_class = "flaky"
        label = "flaky"
        filter_status = "flaky"
    elif status == "passed":
        marker_class = "pass"
        label = "passed"
        filter_status = "passed"
    elif status == "failed":
        marker_class = "fail"
        label = "failed"
        filter_status = "failed"
    elif status == "skipped":
        marker_class = "skip"
        label = "skipped"
        filter_status = "skipped"
    elif status == "interrupted":
        marker_class = "interrupted"
        label = "interrupted"
        filter_status = "interrupted"
    else:
        marker_class = "list"
        label = status
        filter_status = "listed" if status == "listed" else status
    artifacts = result.get("artifacts", {})
    artifact_rows = []
    for name, raw_path in artifacts.items():
        path = Path(raw_path)
        href = _relative_path(path, report_dir)
        artifact_rows.append(
            "<tr>"
            f"<td><a href=\"{escape(href)}\">{escape(name)}</a></td>"
            f"<td><code>{escape(str(path))}</code></td>"
            "</tr>"
        )
    empty_artifact_row = '<tr><td colspan="2" class="empty">No artifacts.</td></tr>'
    artifact_table = (
        "<table>"
        "<thead><tr><th>Artifact</th><th>Path</th></tr></thead>"
        f"<tbody>{''.join(artifact_rows) if artifact_rows else empty_artifact_row}</tbody>"
        "</table>"
        )

    screenshot_html = ""
    if isinstance(artifacts, dict) and artifacts.get("screenshot"):
        screenshot_path = Path(str(artifacts["screenshot"]))
        href = _relative_path(screenshot_path, report_dir)
        screenshot_html = (
            '<div class="block">'
            "<h2>Screenshot</h2>"
            f"<a href=\"{escape(href)}\"><img class=\"screenshot-preview\" src=\"{escape(href)}\" alt=\"Test screenshot\"></a>"
            "</div>"
        )

    annotation_html = ""
    annotations = result.get("annotations", [])
    if isinstance(annotations, list) and annotations:
        chips = []
        for annotation in annotations:
            if not isinstance(annotation, dict):
                continue
            kind = str(annotation.get("type", ""))
            reason = str(annotation.get("reason", ""))
            label_text = kind if not reason else f"{kind}: {reason}"
            chips.append(f"<span class=\"chip\">{escape(label_text)}</span>")
        empty_annotation = '<span class="empty">No annotations.</span>'
        annotation_html = (
            '<div class="block">'
            "<h2>Annotations</h2>"
            f"<div class=\"chips\">{''.join(chips) if chips else empty_annotation}</div>"
            "</div>"
        )

    reason_html = ""
    if result.get("annotation_reason"):
        reason_html = (
            '<div class="block">'
            "<h2>Reason</h2>"
            f"<pre>{escape(str(result.get('annotation_reason', '')))}</pre>"
            "</div>"
        )

    steps_html = ""
    steps = result.get("steps", [])
    if isinstance(steps, list) and steps:
        rows = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            error = step.get("error")
            error_text = ""
            if isinstance(error, dict) and error.get("message"):
                error_text = f"{error.get('type', 'Error')}: {error.get('message', '')}"
            depth = max(0, int(step.get("depth", 0)))
            empty_error = '<span class="empty">none</span>'
            rows.append(
                "<tr>"
                f"<td><code>{escape(str(step.get('status', '')))}</code></td>"
                f"<td style=\"padding-left:{12 + depth * 18}px\">{escape(str(step.get('title', '')))}</td>"
                f"<td><code>{escape(str(step.get('duration_ms', 0)))}</code></td>"
                f"<td>{escape(error_text) if error_text else empty_error}</td>"
                "</tr>"
            )
        steps_html = (
            '<div class="block">'
            "<h2>Steps</h2>"
            "<table>"
            "<thead><tr><th>Status</th><th>Title</th><th>Duration</th><th>Error</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
            "</div>"
        )

    attachments_html = ""
    attachments = result.get("attachments", [])
    if isinstance(attachments, list) and attachments:
        rows = []
        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue
            raw_path = attachment.get("path", "")
            path = Path(str(raw_path))
            href = _relative_path(path, report_dir)
            rows.append(
                "<tr>"
                f"<td><a href=\"{escape(href)}\">{escape(str(attachment.get('name', '')))}</a></td>"
                f"<td><code>{escape(str(attachment.get('content_type', '')))}</code></td>"
                f"<td><code>{escape(str(attachment.get('bytes', 0)))}</code></td>"
                f"<td><code>{escape(str(path))}</code></td>"
                "</tr>"
            )
        attachments_html = (
            '<div class="block">'
            "<h2>Attachments</h2>"
            "<table>"
            "<thead><tr><th>Name</th><th>Content Type</th><th>Bytes</th><th>Path</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
            "</div>"
        )

    soft_assertions_html = ""
    soft_assertions = _result_soft_assertions(result)
    if soft_assertions:
        rows = []
        for failure in soft_assertions:
            rows.append(
                "<tr>"
                f"<td><code>{escape(str(failure.get('index', 0)))}</code></td>"
                f"<td><code>{escape(str(failure.get('method', 'expect')))}</code></td>"
                f"<td>{escape(str(failure.get('type', 'AssertionError')))}</td>"
                f"<td>{escape(str(failure.get('message', '')))}</td>"
                "</tr>"
            )
        soft_assertions_html = (
            '<div class="block">'
            "<h2>Soft Assertions</h2>"
            "<table>"
            "<thead><tr><th>#</th><th>Method</th><th>Type</th><th>Message</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
            "</div>"
        )

    error_html = ""
    if result.get("error"):
        error = result["error"]
        error_html = (
            '<div class="block">'
            "<h2>Error</h2>"
            f"<pre>{escape(str(error.get('type', 'Error')) + ': ' + str(error.get('message', '')))}</pre>"
            f"<pre>{escape(str(error.get('traceback', '')))}</pre>"
            "</div>"
        )

    trace_html = ""
    trace_summary = result.get("trace_summary")
    if isinstance(trace_summary, dict):
        chips = "".join(
            f"<span class=\"chip\">{escape(str(item.get('type', '')))} {escape(str(item.get('count', '')))}</span>"
            for item in trace_summary.get("top_types", [])
        )
        preview_items = []
        for event in trace_summary.get("preview", []):
            if not isinstance(event, dict):
                continue
            preview_items.append(
                "<tr>"
                f"<td><code>{escape(str(event.get('type', '')))}</code></td>"
                f"<td><code>{escape(json.dumps(event.get('data', {}), ensure_ascii=False, sort_keys=True))}</code></td>"
                f"<td><code>{escape(str(event.get('uptime_ms', '')))}</code></td>"
                "</tr>"
            )
        empty_event_types = '<span class="empty">No event types.</span>'
        empty_preview_events = '<tr><td colspan="3" class="empty">No preview events.</td></tr>'
        trace_html = (
            '<div class="block">'
            "<h2>Trace</h2>"
            f"<p class=\"subhead\" style=\"margin:0 0 10px\">{escape(str(trace_summary.get('event_count', 0)))} events</p>"
            f"<div class=\"chips\">{chips or empty_event_types}</div>"
            "<table style=\"margin-top:10px\">"
            "<thead><tr><th>Type</th><th>Data</th><th>Uptime</th></tr></thead>"
            f"<tbody>{''.join(preview_items) if preview_items else empty_preview_events}</tbody>"
            "</table>"
            "</div>"
        )

    log_html = ""
    log_summary = result.get("godot_log_summary")
    if isinstance(log_summary, dict):
        log_tail = "\n".join(str(line) for line in log_summary.get("tail", []))
        log_html = (
            '<div class="block">'
            "<h2>Godot Log</h2>"
            "<div class=\"chips\">"
            f"<span class=\"chip\">{escape(str(log_summary.get('line_count', 0)))} lines</span>"
            f"<span class=\"chip\">{escape(str(log_summary.get('error_count', 0)))} errors</span>"
            f"<span class=\"chip\">{escape(str(log_summary.get('warning_count', 0)))} warnings</span>"
            f"<span class=\"chip\">{escape(str(log_summary.get('bytes', 0)))} bytes</span>"
            "</div>"
            f"<pre style=\"margin-top:10px\">{escape(log_tail) if log_tail else 'Log is empty.'}</pre>"
            "</div>"
        )

    diagnostics_html = ""
    diagnostics = result.get("diagnostics")
    if isinstance(diagnostics, dict):
        diagnostics_html = (
            '<div class="block">'
            "<h2>Diagnostics</h2>"
            "<div class=\"chips\">"
            f"<span class=\"chip\">trace {escape(str(diagnostics.get('trace_events', 0)))}</span>"
            f"<span class=\"chip\">log errors {escape(str(diagnostics.get('godot_log_errors', 0)))}</span>"
            f"<span class=\"chip\">log warnings {escape(str(diagnostics.get('godot_log_warnings', 0)))}</span>"
            f"<span class=\"chip\">scene nodes {escape(str(diagnostics.get('scene_nodes', 0)))}</span>"
            f"<span class=\"chip\">soft assertions {escape(str(diagnostics.get('soft_assertion_failures', 0)))}</span>"
            f"<span class=\"chip\">capture errors {escape(str(diagnostics.get('diagnostic_error_count', 0)))}</span>"
            "</div>"
            f"<pre style=\"margin-top:10px\">{escape(str(diagnostics.get('error_type', '')) + ': ' + str(diagnostics.get('error_message', '')))}</pre>"
            "</div>"
        )

    output_html = ""
    output_rows = []
    for stream_name, stream in _result_output_streams(result):
        path = str(stream.get("path", ""))
        href = _relative_path(Path(path), report_dir) if path else ""
        tail = "\n".join(str(line) for line in stream.get("tail", []))
        link = f"<a href=\"{escape(href)}\">{escape(path)}</a>" if href else '<span class="empty">not written</span>'
        output_rows.append(
            '<div class="block">'
            f"<h2>Python {escape(stream_name)}</h2>"
            "<div class=\"chips\">"
            f"<span class=\"chip\">{escape(str(stream.get('line_count', 0)))} lines</span>"
            f"<span class=\"chip\">{escape(str(stream.get('bytes', 0)))} bytes</span>"
            "</div>"
            f"<p class=\"subhead\" style=\"margin:10px 0\">{link}</p>"
            f"<pre>{escape(tail) if tail else 'Output is empty.'}</pre>"
            "</div>"
        )
    if output_rows:
        output_html = "".join(output_rows)

    attempts_html = ""
    attempts = result.get("attempts", [])
    if isinstance(attempts, list) and attempts:
        rows = []
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            attempt_artifacts = attempt.get("artifacts", {})
            artifact_links = []
            if isinstance(attempt_artifacts, dict):
                for name, raw_path in attempt_artifacts.items():
                    href = _relative_path(Path(raw_path), report_dir)
                    artifact_links.append(f"<a href=\"{escape(href)}\">{escape(name)}</a>")
            empty_artifacts = '<span class="empty">none</span>'
            rows.append(
                "<tr>"
                f"<td><code>{escape(str(attempt.get('attempt', 0)))}</code></td>"
                f"<td>{escape(str(attempt.get('status', '')))}</td>"
                f"<td><code>{escape(str(attempt.get('duration_ms', 0)))}</code></td>"
                f"<td>{', '.join(artifact_links) if artifact_links else empty_artifacts}</td>"
                "</tr>"
            )
        attempts_html = (
            '<div class="block">'
            "<h2>Attempts</h2>"
            "<table>"
            "<thead><tr><th>Attempt</th><th>Status</th><th>Duration</th><th>Artifacts</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
            "</div>"
        )

    return (
        f'<details class="test" data-status="{escape(filter_status)}">'
        "<summary>"
        f'<span class="status {marker_class}">{escape(label)}</span>'
        '<div class="test-title">'
        f'<span class="id">{escape(result.get("id", ""))}</span>'
        f'<span class="meta">{escape(result.get("file", ""))}</span>'
        "</div>"
        f'<span class="duration">{escape(str(result.get("duration_ms", 0)))} ms</span>'
        "</summary>"
        '<div class="body">'
        f'{annotation_html}'
        f'{reason_html}'
        f'{steps_html}'
        f'{attachments_html}'
        f'{soft_assertions_html}'
        f'{screenshot_html}'
        f'<div class="block"><h2>Artifacts</h2>{artifact_table}</div>'
        f'{error_html}'
        f'{attempts_html}'
        f'{diagnostics_html}'
        f'{output_html}'
        f'{log_html}'
        f'{trace_html}'
        "</div>"
        "</details>"
    )


def _relative_path(path: Path, report_dir: Path) -> str:
    try:
        return path.relative_to(report_dir).as_posix()
    except ValueError:
        return path.as_posix()
