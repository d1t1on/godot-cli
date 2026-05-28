from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .checks import check_project_resources, check_project_scripts
from .inventory import inspect_project
from .probe import probe_project_scenes
from .scene import inspect_project_scenes


class ProjectValidationError(RuntimeError):
    def __init__(self, report: dict[str, Any]):
        self.report = report
        super().__init__(_project_validation_error_message(report))


def validate_project(
    project: str | Path,
    paths: list[str | Path] | None = None,
    *,
    exclude: list[str] | None = None,
    executable: str = "godot",
    headless: bool = True,
    timeout: float = 60.0,
    artifacts_dir: str | Path = "godot-playwright-report",
    frames: int = 5,
    extra_args: list[str] | None = None,
    ensure_import_cache: bool = True,
    allow_runtime_errors: bool = False,
    skip_scripts: bool = False,
    skip_inventory: bool = False,
    skip_resources: bool = False,
    skip_scene_inspect: bool = False,
    skip_runtime: bool = False,
    check: bool = False,
) -> dict[str, Any]:
    project_path = Path(project).expanduser().resolve()
    started = time.monotonic()
    selected_paths = paths or []
    exclude_patterns = exclude or []
    checks: dict[str, dict[str, Any]] = {}

    if not skip_inventory:
        checks["inventory"] = inspect_project(
            project_path,
            exclude=exclude_patterns,
            include_settings=False,
        )
    if not skip_scripts:
        checks["scripts"] = check_project_scripts(
            project_path,
            selected_paths,
            exclude=exclude_patterns,
            executable=executable,
            headless=headless,
            timeout=timeout,
            artifacts_dir=artifacts_dir,
            extra_args=extra_args,
            ensure_import_cache=ensure_import_cache,
        )
    if not skip_resources:
        checks["resources"] = check_project_resources(
            project_path,
            selected_paths,
            exclude=exclude_patterns,
        )
    if not skip_scene_inspect:
        checks["scene_inspect"] = inspect_project_scenes(
            project_path,
            selected_paths,
            exclude=exclude_patterns,
        )
    if not skip_runtime:
        checks["runtime"] = probe_project_scenes(
            project_path,
            selected_paths,
            exclude=exclude_patterns,
            executable=executable,
            headless=headless,
            frames=frames,
            timeout=timeout,
            artifacts_dir=artifacts_dir,
            extra_args=extra_args,
            allow_errors=allow_runtime_errors,
        )

    failed_checks = [name for name, report in checks.items() if not report.get("ok")]
    diagnostics = _collect_diagnostics(checks)
    scale = _validation_scale_summary(checks)
    report = {
        "project": str(project_path),
        "ok": not failed_checks,
        "check_count": len(checks),
        "passed": len(checks) - len(failed_checks),
        "failed": len(failed_checks),
        "failed_checks": failed_checks,
        "checks": checks,
        "scale": scale,
        "diagnostics": diagnostics,
        "diagnostic_count": len(diagnostics),
        "artifacts_dir": str(_resolve_artifacts_dir(artifacts_dir)),
        "duration_ms": round((time.monotonic() - started) * 1000.0, 3),
    }
    if check and not report["ok"]:
        raise ProjectValidationError(report)
    return report


def _collect_diagnostics(checks: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for check_name, report in checks.items():
        for diagnostic in report.get("diagnostics", []):
            merged = dict(diagnostic)
            merged["check"] = check_name
            diagnostics.append(merged)
        if report.get("ok", True):
            continue
        if report.get("diagnostics"):
            continue
        diagnostics.append(_summary_diagnostic(check_name, report))
    return diagnostics


def _validation_scale_summary(checks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    inventory = checks.get("inventory", {})
    if not isinstance(inventory, dict):
        return {}
    files = inventory.get("files", {})
    if not isinstance(files, dict):
        return {}
    scale = files.get("scale", {})
    if not isinstance(scale, dict):
        return {}
    return {
        "file_count": scale.get("file_count", files.get("count", 0)),
        "directory_count": scale.get("directory_count", 0),
        "total_bytes": scale.get("total_bytes", files.get("total_bytes", 0)),
        "average_file_bytes": scale.get("average_file_bytes", 0),
        "largest_file_bytes": scale.get("largest_file_bytes", 0),
        "max_path_depth": scale.get("max_path_depth", 0),
        "category_counts": scale.get("category_counts", {}),
        "category_bytes": scale.get("category_bytes", {}),
        "top_extensions": scale.get("top_extensions", []),
        "top_directories": scale.get("top_directories", []),
    }


def _summary_diagnostic(check_name: str, report: dict[str, Any]) -> dict[str, Any]:
    if check_name == "scripts":
        return {
            "check": check_name,
            "severity": "error",
            "kind": "SCRIPT_CHECK_FAILED",
            "message": f"{report.get('failed')} of {report.get('script_count')} scripts failed",
        }
    if check_name == "resources":
        return {
            "check": check_name,
            "severity": "error",
            "kind": "RESOURCE_CHECK_FAILED",
            "message": f"{report.get('failed')} of {report.get('resource_count')} resources failed",
        }
    if check_name == "inventory":
        return {
            "check": check_name,
            "severity": "error",
            "kind": "PROJECT_INVENTORY_FAILED",
            "message": "Project inventory reported structural errors",
        }
    if check_name == "scene_inspect":
        return {
            "check": check_name,
            "severity": "error",
            "kind": "SCENE_INSPECT_FAILED",
            "message": f"{report.get('failed')} of {report.get('scene_count')} scenes failed inspection",
        }
    if check_name == "runtime":
        return {
            "check": check_name,
            "severity": "error",
            "kind": "RUNTIME_PROBE_FAILED",
            "message": f"{report.get('failed')} of {report.get('scene_count')} scenes failed runtime probe",
        }
    return {
        "check": check_name,
        "severity": "error",
        "kind": "CHECK_FAILED",
        "message": f"Project validation check failed: {check_name}",
    }


def _resolve_artifacts_dir(artifacts_dir: str | Path) -> Path:
    artifacts = Path(artifacts_dir)
    if not artifacts.is_absolute():
        artifacts = Path.cwd() / artifacts
    return artifacts.resolve()


def _project_validation_error_message(report: dict[str, Any]) -> str:
    lines = [
        "Godot project validation failed: "
        f"{report.get('failed')} of {report.get('check_count')} checks failed"
    ]
    for diagnostic in report.get("diagnostics", [])[:12]:
        location = ""
        if diagnostic.get("path"):
            location = f" {diagnostic.get('path')}:{diagnostic.get('line', '')}".rstrip(":")
        elif diagnostic.get("scene"):
            location = f" {diagnostic.get('scene')}"
        elif diagnostic.get("script"):
            location = f" {diagnostic.get('script')}"
        elif diagnostic.get("resource"):
            location = f" {diagnostic.get('resource')}"
        lines.append(
            f"{diagnostic.get('check')}: {diagnostic.get('kind')}: {diagnostic.get('message')}{location}"
        )
    return "\n".join(lines)
