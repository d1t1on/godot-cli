from __future__ import annotations

import os
import re
import tempfile
import uuid
from pathlib import Path


def isolated_godot_env(
    *,
    host: str = "127.0.0.1",
    port: int | str | None = 0,
    strict_port: bool = False,
    base_dir: str | Path | None = None,
    namespace: str = "godot",
) -> dict[str, str]:
    env = os.environ.copy()
    env["GODOT_PLAYWRIGHT_HOST"] = str(host)
    if port is not None:
        env["GODOT_PLAYWRIGHT_PORT"] = str(port)
    env["GODOT_PLAYWRIGHT_STRICT_PORT"] = "1" if strict_port else "0"

    runtime_root = _runtime_root(base_dir)
    runtime_home = runtime_root / f"{_safe_namespace(namespace)}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    xdg_data = runtime_home / "xdg-data"
    xdg_config = runtime_home / "xdg-config"
    xdg_cache = runtime_home / "xdg-cache"
    xdg_state = runtime_home / "xdg-state"
    xdg_runtime = runtime_home / "xdg-runtime"
    for path in (xdg_data, xdg_config, xdg_cache, xdg_state, xdg_runtime):
        path.mkdir(parents=True, exist_ok=True)
    try:
        xdg_runtime.chmod(0o700)
    except OSError:
        pass
    _link_existing_export_templates(xdg_data)

    env["XDG_DATA_HOME"] = str(xdg_data)
    env["XDG_CONFIG_HOME"] = str(xdg_config)
    env["XDG_CACHE_HOME"] = str(xdg_cache)
    env["XDG_STATE_HOME"] = str(xdg_state)
    env["XDG_RUNTIME_DIR"] = str(xdg_runtime)
    env["GODOT_PLAYWRIGHT_RUNTIME_DIR"] = str(runtime_home)
    return env


def _runtime_root(base_dir: str | Path | None) -> Path:
    if base_dir is None:
        return Path(tempfile.gettempdir()) / "godot-playwright-runtime"
    return Path(base_dir).expanduser().resolve()


def _safe_namespace(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-")
    return safe or "godot"


def _link_existing_export_templates(xdg_data: Path) -> None:
    source = _existing_export_templates_path()
    if source is None:
        return
    target = xdg_data / "godot" / "export_templates"
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.symlink_to(source, target_is_directory=True)
    except OSError:
        pass


def _existing_export_templates_path() -> Path | None:
    data_home = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    candidate = data_home / "godot" / "export_templates"
    return candidate if candidate.is_dir() else None
