from __future__ import annotations

import re
import subprocess
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Any


TEXT_RESOURCE_EXTENSIONS = {".tscn", ".tres"}
EXT_RESOURCE_PATTERN = re.compile(r"^\s*\[ext_resource\b(?P<body>[^\]]*)\]")
RESOURCE_ATTRIBUTE_PATTERN = re.compile(r'([A-Za-z0-9_./-]+)="((?:[^"\\]|\\.)*)"')
SCRIPT_EXTENDS_PATTERN = re.compile(r"^\s*extends\s+(?P<extends>[^\s#]+)", re.MULTILINE)
SCRIPT_CLASS_NAME_PATTERN = re.compile(r"^\s*class_name\s+(?P<class_name>[A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)


class ScriptCheckError(RuntimeError):
    def __init__(self, report: dict[str, Any]):
        self.report = report
        super().__init__(_script_check_error_message(report))


class ResourceCheckError(RuntimeError):
    def __init__(self, report: dict[str, Any]):
        self.report = report
        super().__init__(_resource_check_error_message(report))


def check_project_resources(
    project: str | Path,
    paths: list[str | Path] | None = None,
    *,
    exclude: list[str] | None = None,
    check: bool = False,
) -> dict[str, Any]:
    project_path = Path(project).expanduser().resolve()
    started = time.monotonic()
    resources = _discover_resources(project_path, paths or [], exclude or [])
    reports = [check_resource_dependencies(project_path, resource) for resource in resources]
    failed_reports = [report for report in reports if not report.get("ok")]
    diagnostics = []
    for report in failed_reports:
        for diagnostic in report.get("diagnostics", []):
            merged = dict(diagnostic)
            merged["resource"] = report.get("resource")
            diagnostics.append(merged)
    report = {
        "project": str(project_path),
        "ok": not failed_reports,
        "resource_count": len(reports),
        "passed": len(reports) - len(failed_reports),
        "failed": len(failed_reports),
        "resources": reports,
        "diagnostics": diagnostics,
        "diagnostic_count": len(diagnostics),
        "duration_ms": round((time.monotonic() - started) * 1000.0, 3),
    }
    if check and not report["ok"]:
        raise ResourceCheckError(report)
    return report


def check_resource_dependencies(
    project: str | Path,
    resource_path: str | Path,
    *,
    check: bool = False,
) -> dict[str, Any]:
    project_path = Path(project).expanduser().resolve()
    started = time.monotonic()
    resource = _resource_res_path(project_path, resource_path)
    global_path = _resource_global_path(project_path, resource)
    diagnostics: list[dict[str, Any]] = []
    dependencies: list[dict[str, Any]] = []
    exists = global_path.is_file()
    if not exists:
        diagnostics.append(
            {
                "severity": "error",
                "kind": "RESOURCE_NOT_FOUND",
                "message": f"Resource file not found: {resource}",
                "path": resource,
                "line": None,
                "global_path": str(global_path),
            }
        )
    else:
        try:
            text = global_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            diagnostics.append(
                {
                    "severity": "error",
                    "kind": "RESOURCE_READ_ERROR",
                    "message": f"Resource is not UTF-8 text: {exc}",
                    "path": resource,
                    "line": None,
                    "global_path": str(global_path),
                }
            )
        else:
            dependencies = _parse_text_resource_dependencies(project_path, resource, global_path, text)
            for dependency in dependencies:
                if dependency.get("checked") and not dependency.get("exists"):
                    diagnostics.append(
                        {
                            "severity": "error",
                            "kind": "MISSING_RESOURCE_DEPENDENCY",
                            "message": f"Missing external resource: {dependency.get('path')}",
                            "path": dependency.get("path"),
                            "line": dependency.get("line"),
                            "global_path": dependency.get("global_path"),
                            "source": resource,
                            "source_global_path": str(global_path),
                            "raw_path": dependency.get("raw_path"),
                            "type": dependency.get("type", ""),
                            "uid": dependency.get("uid", ""),
                            "id": dependency.get("id", ""),
                        }
                    )
    missing_count = sum(1 for dependency in dependencies if dependency.get("checked") and not dependency.get("exists"))
    report = {
        "project": str(project_path),
        "resource": resource,
        "resource_path": str(global_path),
        "exists": exists,
        "ok": exists and not diagnostics,
        "dependency_count": len(dependencies),
        "missing_count": missing_count,
        "dependencies": dependencies,
        "diagnostics": diagnostics,
        "diagnostic_count": len(diagnostics),
        "duration_ms": round((time.monotonic() - started) * 1000.0, 3),
    }
    if check and not report["ok"]:
        raise ResourceCheckError(report)
    return report


def check_project_scripts(
    project: str | Path,
    paths: list[str | Path] | None = None,
    *,
    exclude: list[str] | None = None,
    executable: str = "godot",
    headless: bool = True,
    timeout: float = 60.0,
    artifacts_dir: str | Path = "godot-playwright-report",
    extra_args: list[str] | None = None,
    check: bool = False,
) -> dict[str, Any]:
    project_path = Path(project).expanduser().resolve()
    started = time.monotonic()
    scripts = _discover_scripts(project_path, paths or [], exclude or [])
    reports = [
        check_script(
            project_path,
            script,
            executable=executable,
            headless=headless,
            timeout=timeout,
            artifacts_dir=artifacts_dir,
            extra_args=extra_args,
        )
        for script in scripts
    ]
    failed_reports = [report for report in reports if not report.get("ok")]
    diagnostics = []
    for report in failed_reports:
        for diagnostic in report.get("diagnostics", []):
            merged = dict(diagnostic)
            merged["script"] = report.get("script")
            merged["log_path"] = report.get("log_path")
            diagnostics.append(merged)
    report = {
        "project": str(project_path),
        "ok": not failed_reports,
        "script_count": len(reports),
        "passed": len(reports) - len(failed_reports),
        "failed": len(failed_reports),
        "scripts": reports,
        "diagnostics": diagnostics,
        "diagnostic_count": len(diagnostics),
        "duration_ms": round((time.monotonic() - started) * 1000.0, 3),
    }
    if check and not report["ok"]:
        raise ScriptCheckError(report)
    return report


def check_script(
    project: str | Path,
    script_path: str | Path,
    *,
    executable: str = "godot",
    headless: bool = True,
    timeout: float = 60.0,
    artifacts_dir: str | Path = "godot-playwright-report",
    log_path: str | Path | None = None,
    extra_args: list[str] | None = None,
    check: bool = False,
) -> dict[str, Any]:
    project_path = Path(project).expanduser().resolve()
    script_arg = _script_argument(project_path, script_path)
    artifacts = Path(artifacts_dir)
    if not artifacts.is_absolute():
        artifacts = Path.cwd() / artifacts
    artifacts.mkdir(parents=True, exist_ok=True)
    if log_path is None:
        log = artifacts / f"{_safe_name(str(script_path))}-check.log"
    else:
        log = Path(log_path)
        if not log.is_absolute():
            log = project_path / log
        log.parent.mkdir(parents=True, exist_ok=True)

    cmd = [executable]
    if headless:
        cmd.append("--headless")
    cmd.extend(["--path", str(project_path), "--check-only", "--script", script_arg])
    if extra_args:
        cmd.extend(extra_args)

    started = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            cwd=project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        timed_out = False
        exit_code = int(completed.returncode)
        stdout = completed.stdout or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = -1
        stdout_value = exc.stdout if exc.stdout is not None else ""
        if isinstance(stdout_value, bytes):
            stdout = stdout_value.decode("utf-8", errors="replace")
        else:
            stdout = str(stdout_value)
    duration_ms = round((time.monotonic() - started) * 1000.0, 3)
    log.write_text(stdout, encoding="utf-8")
    diagnostics = _parse_godot_diagnostics(stdout)
    report = {
        "project": str(project_path),
        "script": str(script_path),
        "script_arg": script_arg,
        "script_path": _script_global_path(project_path, script_path),
        "log_path": str(log),
        "command": cmd,
        "exit_code": exit_code,
        "ok": exit_code == 0 and not timed_out,
        "timed_out": timed_out,
        "duration_ms": duration_ms,
        "diagnostics": diagnostics,
        "diagnostic_count": len(diagnostics),
        "stdout_tail": _tail(stdout),
    }
    if check and not report["ok"]:
        raise ScriptCheckError(report)
    return report


class ScriptFileExpect:
    def __init__(
        self,
        project: str | Path,
        script_path: str | Path,
        *,
        executable: str = "godot",
        headless: bool = True,
        check_timeout: float = 60.0,
        artifacts_dir: str | Path = "godot-playwright-report",
        extra_args: list[str] | None = None,
    ):
        self.project = Path(project).expanduser().resolve()
        self.script_path = script_path
        self.executable = executable
        self.headless = headless
        self.check_timeout = check_timeout
        self.artifacts_dir = artifacts_dir
        self.extra_args = extra_args or []

    def to_exist(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for_source(
            lambda source, path: path.is_file(),
            lambda _source, path: f"Expected script file {self.script_path!r} to exist at {path}",
            timeout=timeout,
            interval=interval,
            transform=lambda source, path: {
                "script": _resource_res_path(self.project, self.script_path),
                "script_path": str(path),
                "exists": path.is_file(),
                "source": source,
            },
        )

    def to_contain_source(self, text: str, *, timeout: float = 5.0, interval: float = 0.05) -> str:
        return self._wait_for_source(
            lambda source, _path: text in source,
            lambda _source, _path: f"Expected script file {self.script_path!r} source to contain {text!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_extend(self, base_class: str, *, timeout: float = 5.0, interval: float = 0.05) -> str:
        return self._wait_for_source(
            lambda source, _path: _script_source_extends(source) == base_class,
            lambda source, _path: (
                f"Expected script file {self.script_path!r} to extend {base_class!r}, "
                f"got {_script_source_extends(source)!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda source, _path: _script_source_extends(source),
        )

    def to_have_class_name(self, class_name: str, *, timeout: float = 5.0, interval: float = 0.05) -> str:
        return self._wait_for_source(
            lambda source, _path: _script_source_class_name(source) == class_name,
            lambda source, _path: (
                f"Expected script file {self.script_path!r} class_name {class_name!r}, "
                f"got {_script_source_class_name(source)!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda source, _path: _script_source_class_name(source),
        )

    def to_define_function(self, name: str, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for_source(
            lambda source, _path: _script_source_function(source, name) is not None,
            lambda source, _path: (
                f"Expected script file {self.script_path!r} to define function {name!r}; "
                f"functions={_script_source_function_names(source)!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda source, _path: _script_source_function(source, name) or {},
        )

    def to_pass_godot_check(self, *, timeout: float = 60.0, interval: float = 0.5) -> dict[str, Any]:
        return self._wait_for_check(
            lambda report: bool(report.get("ok")),
            lambda report: (
                f"Expected script file {self.script_path!r} to pass Godot check; "
                f"exit_code={report.get('exit_code')} diagnostics={report.get('diagnostics', [])!r} "
                f"log={report.get('log_path')!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_be_valid(self, *, timeout: float = 60.0, interval: float = 0.5) -> dict[str, Any]:
        return self.to_pass_godot_check(timeout=timeout, interval=interval)

    def to_have_diagnostic(
        self,
        text: str | None = None,
        *,
        kind: str | None = None,
        severity: str | None = None,
        path: str | None = None,
        line: int | None = None,
        timeout: float = 60.0,
        interval: float = 0.5,
    ) -> dict[str, Any]:
        def match(report: dict[str, Any]) -> dict[str, Any] | None:
            for diagnostic in report.get("diagnostics", []):
                if isinstance(diagnostic, dict) and _script_diagnostic_matches(
                    diagnostic,
                    text=text,
                    kind=kind,
                    severity=severity,
                    path=path,
                    line=line,
                ):
                    return diagnostic
            return None

        return self._wait_for_check(
            lambda report: match(report) is not None,
            lambda report: (
                f"Expected script file {self.script_path!r} diagnostic "
                f"{_script_diagnostic_filter_summary(text=text, kind=kind, severity=severity, path=path, line=line)}; "
                f"diagnostics={report.get('diagnostics', [])!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda report: match(report) or {},
        )

    def not_to_have_diagnostic(
        self,
        text: str | None = None,
        *,
        kind: str | None = None,
        severity: str | None = None,
        path: str | None = None,
        line: int | None = None,
        timeout: float = 60.0,
        interval: float = 0.5,
    ) -> dict[str, Any]:
        return self._wait_for_check(
            lambda report: not any(
                isinstance(diagnostic, dict)
                and _script_diagnostic_matches(
                    diagnostic,
                    text=text,
                    kind=kind,
                    severity=severity,
                    path=path,
                    line=line,
                )
                for diagnostic in report.get("diagnostics", [])
            ),
            lambda report: (
                f"Expected script file {self.script_path!r} not to have diagnostic "
                f"{_script_diagnostic_filter_summary(text=text, kind=kind, severity=severity, path=path, line=line)}; "
                f"diagnostics={report.get('diagnostics', [])!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def _wait_for_source(
        self,
        predicate: Any,
        message: Any,
        *,
        timeout: float,
        interval: float,
        transform: Any = None,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last_source = ""
        path = _resource_global_path(self.project, _resource_res_path(self.project, self.script_path))
        while True:
            if path.is_file():
                try:
                    last_source = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    last_source = ""
            if predicate(last_source, path):
                return transform(last_source, path) if transform is not None else last_source
            if time.monotonic() >= deadline:
                raise AssertionError(message(last_source, path))
            time.sleep(interval)

    def _wait_for_check(
        self,
        predicate: Any,
        message: Any,
        *,
        timeout: float,
        interval: float,
        transform: Any = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = check_script(
                self.project,
                self.script_path,
                executable=self.executable,
                headless=self.headless,
                timeout=self.check_timeout,
                artifacts_dir=self.artifacts_dir,
                extra_args=list(self.extra_args),
            )
            if predicate(last):
                return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last))
            time.sleep(interval)


def expect_script_file(
    project: str | Path,
    script_path: str | Path,
    *,
    executable: str = "godot",
    headless: bool = True,
    check_timeout: float = 60.0,
    artifacts_dir: str | Path = "godot-playwright-report",
    extra_args: list[str] | None = None,
) -> ScriptFileExpect:
    return ScriptFileExpect(
        project,
        script_path,
        executable=executable,
        headless=headless,
        check_timeout=check_timeout,
        artifacts_dir=artifacts_dir,
        extra_args=extra_args,
    )


def _discover_resources(project_path: Path, paths: list[str | Path], exclude: list[str]) -> list[str]:
    discovered: list[str] = []
    roots = paths or ["res://"]
    for raw in roots:
        for path in _expand_resource_path(project_path, raw):
            if _is_excluded(path, exclude):
                continue
            discovered.append(path)
    return sorted(dict.fromkeys(discovered))


def _expand_resource_path(project_path: Path, raw: str | Path) -> list[str]:
    raw_text = str(raw)
    if raw_text.startswith("res://"):
        local = project_path / raw_text.removeprefix("res://")
        prefix = raw_text.rstrip("/")
    else:
        local = Path(raw)
        if not local.is_absolute():
            local = project_path / local
        local = local.resolve()
        try:
            prefix = "res://" + local.relative_to(project_path).as_posix()
        except ValueError:
            prefix = str(local)
    if local.is_file():
        return [prefix] if local.suffix in TEXT_RESOURCE_EXTENSIONS else []
    if not local.is_dir():
        return []
    resources = []
    for resource in local.rglob("*"):
        if resource.suffix not in TEXT_RESOURCE_EXTENSIONS or not resource.is_file():
            continue
        if _is_ignored_project_path(project_path, resource):
            continue
        try:
            resources.append("res://" + resource.resolve().relative_to(project_path).as_posix())
        except ValueError:
            resources.append(str(resource.resolve()))
    return resources


def _parse_text_resource_dependencies(
    project_path: Path,
    resource: str,
    resource_global_path: Path,
    text: str,
) -> list[dict[str, Any]]:
    dependencies: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        match = EXT_RESOURCE_PATTERN.match(line)
        if not match:
            continue
        attrs = {
            key: _unescape_godot_string(value)
            for key, value in RESOURCE_ATTRIBUTE_PATTERN.findall(match.group("body"))
        }
        raw_path = attrs.get("path", "")
        if raw_path == "":
            continue
        dependencies.append(
            _resource_dependency_report(
                project_path,
                resource,
                resource_global_path,
                raw_path,
                line_number,
                attrs,
            )
        )
    return dependencies


def _resource_dependency_report(
    project_path: Path,
    resource: str,
    resource_global_path: Path,
    raw_path: str,
    line_number: int,
    attrs: dict[str, str],
) -> dict[str, Any]:
    checked = not raw_path.startswith("uid://")
    path = raw_path
    global_path = ""
    exists: bool | None = None
    if checked:
        dependency_global_path = _dependency_global_path(project_path, resource_global_path, raw_path)
        exists = dependency_global_path.is_file()
        global_path = str(dependency_global_path)
        path = _dependency_resource_path(project_path, dependency_global_path, raw_path)
    return {
        "source": resource,
        "line": line_number,
        "raw_path": raw_path,
        "path": path,
        "global_path": global_path,
        "exists": exists,
        "checked": checked,
        "type": attrs.get("type", ""),
        "uid": attrs.get("uid", ""),
        "id": attrs.get("id", ""),
    }


def _dependency_global_path(project_path: Path, resource_global_path: Path, raw_path: str) -> Path:
    if raw_path.startswith("res://"):
        return (project_path / raw_path.removeprefix("res://")).resolve()
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve()
    return (resource_global_path.parent / path).resolve()


def _dependency_resource_path(project_path: Path, global_path: Path, raw_path: str) -> str:
    if raw_path.startswith("res://"):
        return raw_path
    try:
        return "res://" + global_path.relative_to(project_path).as_posix()
    except ValueError:
        return str(global_path)


def _resource_res_path(project_path: Path, resource_path: str | Path) -> str:
    resource = str(resource_path)
    if resource.startswith("res://"):
        return resource
    path = Path(resource_path)
    if not path.is_absolute():
        path = project_path / path
    path = path.resolve()
    try:
        return "res://" + path.relative_to(project_path).as_posix()
    except ValueError:
        return str(path)


def _resource_global_path(project_path: Path, resource_path: str) -> Path:
    if resource_path.startswith("res://"):
        return (project_path / resource_path.removeprefix("res://")).resolve()
    return Path(resource_path).expanduser().resolve()


def _unescape_godot_string(value: str) -> str:
    return value.replace(r"\"", '"').replace(r"\\", "\\")


def _discover_scripts(project_path: Path, paths: list[str | Path], exclude: list[str]) -> list[str]:
    discovered: list[str] = []
    roots = paths or ["res://"]
    for raw in roots:
        for path in _expand_script_path(project_path, raw):
            if _is_excluded(path, exclude):
                continue
            discovered.append(path)
    return sorted(dict.fromkeys(discovered))


def _expand_script_path(project_path: Path, raw: str | Path) -> list[str]:
    raw_text = str(raw)
    if raw_text.startswith("res://"):
        local = project_path / raw_text.removeprefix("res://")
        prefix = raw_text.rstrip("/")
    else:
        local = Path(raw)
        if not local.is_absolute():
            local = project_path / local
        local = local.resolve()
        try:
            prefix = "res://" + local.relative_to(project_path).as_posix()
        except ValueError:
            prefix = str(local)
    if local.is_file():
        return [prefix] if local.suffix == ".gd" else []
    if not local.is_dir():
        return []
    scripts = []
    for script in local.rglob("*.gd"):
        if _is_ignored_script_path(project_path, script):
            continue
        try:
            scripts.append("res://" + script.resolve().relative_to(project_path).as_posix())
        except ValueError:
            scripts.append(str(script.resolve()))
    return scripts


def _is_ignored_script_path(project_path: Path, path: Path) -> bool:
    return _is_ignored_project_path(project_path, path)


def _is_ignored_project_path(project_path: Path, path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(project_path)
    except ValueError:
        relative = path
    return any(part in {".godot", "__pycache__"} for part in relative.parts)


def _is_excluded(path: str, patterns: list[str]) -> bool:
    return any(fnmatch(path, pattern) or fnmatch(path.removeprefix("res://"), pattern) for pattern in patterns)


def _script_argument(project_path: Path, script_path: str | Path) -> str:
    script = str(script_path)
    if script.startswith("res://"):
        return script
    path = Path(script_path)
    if path.is_absolute():
        return str(path)
    return str(path)


def _script_global_path(project_path: Path, script_path: str | Path) -> str:
    script = str(script_path)
    if script.startswith("res://"):
        return str((project_path / script.removeprefix("res://")).resolve())
    path = Path(script_path)
    if path.is_absolute():
        return str(path)
    return str((project_path / path).resolve())


def _script_source_extends(source: str) -> str:
    match = SCRIPT_EXTENDS_PATTERN.search(source)
    return "" if match is None else match.group("extends")


def _script_source_class_name(source: str) -> str:
    match = SCRIPT_CLASS_NAME_PATTERN.search(source)
    return "" if match is None else match.group("class_name")


def _script_source_function(source: str, name: str) -> dict[str, Any] | None:
    pattern = re.compile(
        rf"^(?P<indent>\s*)(?P<static>static\s+)?func\s+{re.escape(name)}\s*\(",
        re.MULTILINE,
    )
    match = pattern.search(source)
    if match is None:
        return None
    return {
        "name": name,
        "line": source.count("\n", 0, match.start()) + 1,
        "static": bool(match.group("static")),
        "indent": len(match.group("indent").replace("\t", "    ")),
    }


def _script_source_function_names(source: str) -> list[str]:
    return re.findall(r"^\s*(?:static\s+)?func\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", source, re.MULTILINE)


def _script_diagnostic_matches(
    diagnostic: dict[str, Any],
    *,
    text: str | None = None,
    kind: str | None = None,
    severity: str | None = None,
    path: str | None = None,
    line: int | None = None,
) -> bool:
    if kind is not None and diagnostic.get("kind") != kind:
        return False
    if severity is not None and diagnostic.get("severity") != severity:
        return False
    if path is not None and diagnostic.get("path") != path:
        return False
    if line is not None and diagnostic.get("line") != line:
        return False
    if text is not None:
        haystack = f"{diagnostic.get('message', '')}\n{diagnostic.get('source', '')}"
        if text not in haystack:
            return False
    return True


def _script_diagnostic_filter_summary(
    *,
    text: str | None = None,
    kind: str | None = None,
    severity: str | None = None,
    path: str | None = None,
    line: int | None = None,
) -> str:
    filters = []
    if text is not None:
        filters.append(f"text={text!r}")
    if kind is not None:
        filters.append(f"kind={kind!r}")
    if severity is not None:
        filters.append(f"severity={severity!r}")
    if path is not None:
        filters.append(f"path={path!r}")
    if line is not None:
        filters.append(f"line={line!r}")
    return ", ".join(filters) if filters else "any diagnostic"


def _parse_godot_diagnostics(output: str) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in output.splitlines():
        match = re.match(r"^(SCRIPT ERROR|ERROR|WARNING):\s*(.*)$", line.strip())
        if match:
            current = {
                "severity": "warning" if match.group(1) == "WARNING" else "error",
                "kind": match.group(1),
                "message": match.group(2),
            }
            diagnostics.append(current)
            continue
        location = re.match(r"^(?:at:|At:)\s*(.*?)\s*(?:\((.*?)(?::(\d+))?\))?$", line.strip())
        if current is not None and location:
            source = location.group(1).strip()
            path = location.group(2) or ""
            line_number = location.group(3)
            current["source"] = source
            if path:
                current["path"] = path
            if line_number is not None:
                current["line"] = int(line_number)
    return diagnostics


def _tail(text: str, *, max_lines: int = 80) -> list[str]:
    lines = text.splitlines()
    return lines[-max_lines:]


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return safe or "script"


def _script_check_error_message(report: dict[str, Any]) -> str:
    if "scripts" in report:
        lines = [
            f"Godot project script check failed: {report.get('failed')} of {report.get('script_count')} scripts failed"
        ]
        for diagnostic in report.get("diagnostics", [])[:8]:
            lines.append(
                f"{diagnostic.get('kind')}: {diagnostic.get('message')} "
                f"{diagnostic.get('path', diagnostic.get('script', ''))}:{diagnostic.get('line', '')}".rstrip(":")
            )
        return "\n".join(lines)
    diagnostics = report.get("diagnostics", [])
    if diagnostics:
        details = "\n".join(
            f"{item.get('kind')}: {item.get('message')} {item.get('path', '')}:{item.get('line', '')}".rstrip(":")
            for item in diagnostics[:6]
        )
    else:
        details = "\n".join(str(line) for line in report.get("stdout_tail", [])[-12:])
    return (
        f"Godot script check failed for {report.get('script')!r} "
        f"with exit code {report.get('exit_code')}; log={report.get('log_path')}\n{details}"
    ).rstrip()


def _resource_check_error_message(report: dict[str, Any]) -> str:
    if "resources" in report:
        lines = [
            "Godot project resource dependency check failed: "
            f"{report.get('failed')} of {report.get('resource_count')} resources failed"
        ]
        for diagnostic in report.get("diagnostics", [])[:8]:
            lines.append(
                f"{diagnostic.get('kind')}: {diagnostic.get('message')} "
                f"{diagnostic.get('resource', diagnostic.get('source', ''))}:{diagnostic.get('line', '')}".rstrip(":")
            )
        return "\n".join(lines)
    diagnostics = report.get("diagnostics", [])
    details = "\n".join(
        f"{item.get('kind')}: {item.get('message')} {item.get('path', '')}:{item.get('line', '')}".rstrip(":")
        for item in diagnostics[:8]
    )
    return f"Godot resource dependency check failed for {report.get('resource')!r}\n{details}".rstrip()
