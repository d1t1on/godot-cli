from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from .inventory import inspect_export_presets
from .process import isolated_godot_env
from .probe import summarize_godot_output


class ExportError(RuntimeError):
    def __init__(self, report: dict[str, Any]):
        self.report = report
        super().__init__(_export_error_message(report))


def export_project(
    project: str | Path,
    preset: str,
    output_path: str | Path,
    *,
    mode: str = "release",
    executable: str = "godot",
    headless: bool = True,
    timeout: float = 300.0,
    log_path: str | Path | None = None,
    create_dirs: bool = True,
    patches: list[str | Path] | None = None,
    extra_args: list[str] | None = None,
    check: bool = False,
) -> dict[str, Any]:
    project_path = Path(project).expanduser().resolve()
    output = Path(output_path)
    if not output.is_absolute():
        output = project_path / output
    output = output.resolve()
    if create_dirs:
        output.parent.mkdir(parents=True, exist_ok=True)
    if log_path is None:
        log = output.with_suffix(output.suffix + ".log")
    else:
        log = Path(log_path)
        if not log.is_absolute():
            log = project_path / log
        log = log.resolve()
        if create_dirs:
            log.parent.mkdir(parents=True, exist_ok=True)

    export_presets = inspect_export_presets(project_path, include_settings=False)
    preset_state = _find_export_preset(export_presets, preset)
    output_before = _artifact_state(output)
    cmd = _export_command(
        executable,
        project_path,
        preset,
        output,
        mode=mode,
        headless=headless,
        patches=patches,
        extra_args=extra_args,
    )
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
    output_after = _artifact_state(output)
    output_exists = bool(output_after["exists"])
    output_relative_path = _project_relative_path(project_path, output)
    preset_export_path = _preset_export_path(preset_state)
    preset_output = _resolve_preset_output_path(project_path, preset_export_path)
    preset_output_state = _artifact_state(preset_output) if preset_output is not None else None
    report = {
        "project": str(project_path),
        "preset": preset,
        "mode": mode,
        "export_presets": export_presets,
        "preset_found": preset_state is not None,
        "preset_state": preset_state,
        "preset_export_path": preset_export_path,
        "preset_output_path": "" if preset_output is None else str(preset_output),
        "preset_output_state": preset_output_state,
        "output_path": str(output),
        "output_relative_path": output_relative_path,
        "output_matches_preset": None if preset_output is None else _same_path(output, preset_output),
        "output_exists": output_exists,
        "output_bytes": output_after["bytes"],
        "output_preexisting": output_before["exists"],
        "output_mtime_before_ns": output_before["mtime_ns"],
        "output_mtime_after_ns": output_after["mtime_ns"],
        "output_changed": _artifact_changed(output_before, output_after),
        "log_path": str(log),
        "command": cmd,
        "exit_code": exit_code,
        "ok": exit_code == 0 and output_exists and not timed_out,
        "timed_out": timed_out,
        "duration_ms": duration_ms,
        "stdout_tail": _tail(stdout),
        "log_summary": log_summary,
        "diagnostics": log_summary["diagnostics"],
        "diagnostic_count": len(log_summary["diagnostics"]),
    }
    if check and not report["ok"]:
        raise ExportError(report)
    return report


def _export_command(
    executable: str,
    project_path: Path,
    preset: str,
    output: Path,
    *,
    mode: str,
    headless: bool,
    patches: list[str | Path] | None,
    extra_args: list[str] | None,
) -> list[str]:
    export_flag = {
        "release": "--export-release",
        "debug": "--export-debug",
        "pack": "--export-pack",
        "patch": "--export-patch",
    }.get(mode)
    if export_flag is None:
        raise ValueError("mode must be one of: release, debug, pack, patch")
    cmd = [executable]
    if headless:
        cmd.append("--headless")
    cmd.extend(["--path", str(project_path), export_flag, preset, str(output)])
    if mode == "patch" and patches:
        cmd.extend(["--patches", ",".join(str(Path(patch)) for patch in patches)])
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def _find_export_preset(export_presets: dict[str, Any], name: str) -> dict[str, Any] | None:
    for preset in export_presets.get("presets", []):
        if isinstance(preset, dict) and preset.get("name") == name:
            return dict(preset)
    return None


def _preset_export_path(preset_state: dict[str, Any] | None) -> str:
    if not isinstance(preset_state, dict):
        return ""
    return str(preset_state.get("export_path") or "")


def _resolve_preset_output_path(project_path: Path, preset_export_path: str) -> Path | None:
    if not preset_export_path:
        return None
    output = Path(preset_export_path)
    if not output.is_absolute():
        output = project_path / output
    return output.resolve()


def _project_relative_path(project_path: Path, output: Path) -> str:
    try:
        return output.relative_to(project_path).as_posix()
    except ValueError:
        return ""


def _same_path(first: Path, second: Path) -> bool:
    return first.resolve() == second.resolve()


def _artifact_state(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {"exists": False, "bytes": 0, "mtime_ns": None}
    return {"exists": True, "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _artifact_changed(before: dict[str, Any], after: dict[str, Any]) -> bool:
    if bool(before.get("exists")) != bool(after.get("exists")):
        return True
    if not bool(after.get("exists")):
        return False
    return before.get("bytes") != after.get("bytes") or before.get("mtime_ns") != after.get("mtime_ns")


def _tail(text: str, *, max_lines: int = 80) -> list[str]:
    lines = text.splitlines()
    return lines[-max_lines:]


def _export_error_message(report: dict[str, Any]) -> str:
    detail = "\n".join(str(line) for line in report.get("stdout_tail", [])[-12:])
    return (
        f"Godot export failed for preset {report.get('preset')!r} "
        f"with exit code {report.get('exit_code')}; log={report.get('log_path')}\n{detail}"
    ).rstrip()
