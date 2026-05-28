from __future__ import annotations

import re
import subprocess
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from .process import isolated_godot_env


class ProbeError(RuntimeError):
    def __init__(self, report: dict[str, Any]):
        self.report = report
        super().__init__(_probe_error_message(report))


def probe_project(
    project: str | Path,
    *,
    scene: str = "",
    executable: str = "godot",
    headless: bool = True,
    frames: int = 5,
    timeout: float = 30.0,
    artifacts_dir: str | Path = "godot-playwright-report",
    log_path: str | Path | None = None,
    extra_args: list[str] | None = None,
    allow_errors: bool = False,
    check: bool = False,
) -> dict[str, Any]:
    project_path = Path(project).expanduser().resolve()
    artifacts = Path(artifacts_dir)
    if not artifacts.is_absolute():
        artifacts = Path.cwd() / artifacts
    artifacts.mkdir(parents=True, exist_ok=True)
    if log_path is None:
        log = artifacts / f"{_safe_name(scene or 'main')}-probe.log"
    else:
        log = Path(log_path)
        if not log.is_absolute():
            log = project_path / log
        log.parent.mkdir(parents=True, exist_ok=True)

    cmd = [executable]
    if headless:
        cmd.append("--headless")
    cmd.extend(["--path", str(project_path), "--quit-after", str(max(1, int(frames)))])
    if scene:
        cmd.extend(["--scene", scene])
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
            env=isolated_godot_env(),
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
    log_summary = summarize_godot_output(stdout)
    report = {
        "project": str(project_path),
        "scene": scene,
        "frames": max(1, int(frames)),
        "log_path": str(log),
        "command": cmd,
        "exit_code": exit_code,
        "ok": exit_code == 0 and not timed_out and (allow_errors or log_summary["error_count"] == 0),
        "timed_out": timed_out,
        "duration_ms": duration_ms,
        "log_summary": log_summary,
    }
    if check and not report["ok"]:
        raise ProbeError(report)
    return report


def probe_project_scenes(
    project: str | Path,
    scenes: list[str | Path] | None = None,
    *,
    exclude: list[str] | None = None,
    executable: str = "godot",
    headless: bool = True,
    frames: int = 5,
    timeout: float = 30.0,
    artifacts_dir: str | Path = "godot-playwright-report",
    extra_args: list[str] | None = None,
    allow_errors: bool = False,
    check: bool = False,
) -> dict[str, Any]:
    project_path = Path(project).expanduser().resolve()
    artifacts = Path(artifacts_dir)
    if not artifacts.is_absolute():
        artifacts = Path.cwd() / artifacts
    artifacts.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    scene_paths = _discover_scenes(project_path, scenes or [], exclude or [])
    reports = [
        probe_project(
            project_path,
            scene=scene,
            executable=executable,
            headless=headless,
            frames=frames,
            timeout=timeout,
            artifacts_dir=artifacts,
            extra_args=extra_args,
            allow_errors=allow_errors,
        )
        for scene in scene_paths
    ]
    failed_reports = [report for report in reports if not report.get("ok")]
    diagnostics = []
    for report in reports:
        summary = report.get("log_summary", {})
        if not isinstance(summary, dict):
            continue
        for diagnostic in summary.get("diagnostics", []):
            merged = dict(diagnostic)
            merged["scene"] = report.get("scene")
            merged["log_path"] = report.get("log_path")
            diagnostics.append(merged)
    report = {
        "project": str(project_path),
        "ok": not failed_reports,
        "scene_count": len(reports),
        "passed": len(reports) - len(failed_reports),
        "failed": len(failed_reports),
        "scenes": reports,
        "diagnostics": diagnostics,
        "diagnostic_count": len(diagnostics),
        "artifacts_dir": str(artifacts),
        "duration_ms": round((time.monotonic() - started) * 1000.0, 3),
    }
    if check and not report["ok"]:
        raise ProbeError(report)
    return report


def summarize_godot_output(text: str, *, tail_lines: int = 80) -> dict[str, Any]:
    lines = text.splitlines()
    diagnostics = _extract_log_diagnostics(lines)
    return {
        "line_count": len(lines),
        "bytes": len(text.encode("utf-8", errors="replace")),
        "error_count": sum(1 for item in diagnostics if item["severity"] == "error"),
        "warning_count": sum(1 for item in diagnostics if item["severity"] == "warning"),
        "diagnostics": diagnostics,
        "tail": lines[-tail_lines:],
    }


def _extract_log_diagnostics(lines: list[str]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in lines:
        stripped = line.strip()
        match = re.match(r"^(SCRIPT ERROR|USER ERROR|USER WARNING|ERROR|WARNING):\s*(.*)$", stripped)
        if match:
            kind = match.group(1)
            current = {
                "severity": "warning" if "WARNING" in kind else "error",
                "kind": kind,
                "message": match.group(2),
            }
            diagnostics.append(current)
            continue
        location = re.match(r"^(?:at:|At:)\s*(.*?)\s*(?:\((.*?)(?::(\d+))?\))?$", stripped)
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


def _discover_scenes(project_path: Path, scenes: list[str | Path], exclude: list[str]) -> list[str]:
    discovered: list[str] = []
    roots = scenes or ["res://"]
    for raw in roots:
        for scene in _expand_scene_path(project_path, raw):
            if _is_excluded(scene, exclude):
                continue
            discovered.append(scene)
    return sorted(dict.fromkeys(discovered))


def _expand_scene_path(project_path: Path, raw: str | Path) -> list[str]:
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
        return [prefix] if local.suffix in {".tscn", ".scn"} else []
    if not local.is_dir():
        return [prefix] if Path(raw_text).suffix in {".tscn", ".scn"} else []
    scene_paths = []
    for pattern in ("*.tscn", "*.scn"):
        for scene in local.rglob(pattern):
            if _is_ignored_scene_path(project_path, scene):
                continue
            try:
                scene_paths.append("res://" + scene.resolve().relative_to(project_path).as_posix())
            except ValueError:
                scene_paths.append(str(scene.resolve()))
    return scene_paths


def _is_ignored_scene_path(project_path: Path, path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(project_path)
    except ValueError:
        relative = path
    return any(part in {".godot", "__pycache__"} for part in relative.parts)


def _is_excluded(path: str, patterns: list[str]) -> bool:
    return any(fnmatch(path, pattern) or fnmatch(path.removeprefix("res://"), pattern) for pattern in patterns)


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return safe or "main"


def _probe_error_message(report: dict[str, Any]) -> str:
    if "scenes" in report:
        diagnostics = report.get("diagnostics", [])
        if diagnostics:
            detail = "\n".join(
                f"{item.get('scene')}: {item.get('kind')}: {item.get('message')} "
                f"{item.get('path', '')}:{item.get('line', '')}".rstrip(":")
                for item in diagnostics[:12]
            )
        else:
            failed = [scene for scene in report.get("scenes", []) if not scene.get("ok")]
            detail = "\n".join(
                f"{scene.get('scene')}: exit={scene.get('exit_code')} log={scene.get('log_path')}"
                for scene in failed[:12]
            )
        return (
            f"Godot scene probe failed for {report.get('failed')} of {report.get('scene_count')} scenes\n{detail}"
        ).rstrip()
    summary = report.get("log_summary", {})
    diagnostics = summary.get("diagnostics", []) if isinstance(summary, dict) else []
    if diagnostics:
        detail = "\n".join(
            f"{item.get('kind')}: {item.get('message')} {item.get('path', '')}:{item.get('line', '')}".rstrip(":")
            for item in diagnostics[:8]
        )
    else:
        tail = summary.get("tail", []) if isinstance(summary, dict) else []
        detail = "\n".join(str(line) for line in tail[-12:])
    return (
        f"Godot probe failed for scene {report.get('scene') or '<main>'!r} "
        f"with exit code {report.get('exit_code')}; log={report.get('log_path')}\n{detail}"
    ).rstrip()
