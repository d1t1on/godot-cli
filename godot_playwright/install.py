from __future__ import annotations

import re
import shutil
from pathlib import Path


ADDON_NAME = "godot_playwright"
PLUGIN_PATH = "res://addons/godot_playwright/plugin.cfg"
AUTOLOAD_NAME = "GodotPlaywright"
AUTOLOAD_PATH = "*res://addons/godot_playwright/runtime_autoload.gd"


class InstallError(RuntimeError):
    pass


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def package_root() -> Path:
    return Path(__file__).resolve().parent


def bundled_addon_path() -> Path:
    candidates = [
        repository_root() / "addons" / ADDON_NAME,
        package_root() / "bundled_addons" / ADDON_NAME,
    ]
    for addon in candidates:
        if addon.exists():
            return addon
    checked = ", ".join(str(path) for path in candidates)
    raise InstallError(f"Bundled add-on not found. Checked: {checked}")


def install_addon(
    project_path: str | Path,
    *,
    enable: bool = True,
    autoload: bool = False,
    force: bool = True,
) -> Path:
    project_dir = Path(project_path).expanduser().resolve()
    project_file = project_dir / "project.godot"
    if not project_file.exists():
        raise InstallError(f"Godot project not found: {project_file}")

    source = bundled_addon_path()
    target = project_dir / "addons" / ADDON_NAME
    if target.exists():
        if not force:
            raise InstallError(f"Add-on already exists: {target}")
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)

    if enable or autoload:
        text = project_file.read_text(encoding="utf-8")
        if enable:
            text = enable_editor_plugin(text, PLUGIN_PATH)
        if autoload:
            text = enable_autoload(text, AUTOLOAD_NAME, AUTOLOAD_PATH)
        project_file.write_text(text, encoding="utf-8")

    return target


def enable_editor_plugin(text: str, plugin_path: str = PLUGIN_PATH) -> str:
    text = _ensure_trailing_newline(text)
    section = _find_section(text, "editor_plugins")
    if section is None:
        return (
            text
            + "\n[editor_plugins]\n\n"
            + f'enabled=PackedStringArray("{plugin_path}")\n'
        )

    start, end = section
    body = text[start:end]
    match = re.search(r"(?m)^enabled\s*=\s*PackedStringArray\((.*?)\)\s*$", body)
    if match is None:
        insert = start
        return text[:insert] + f'enabled=PackedStringArray("{plugin_path}")\n' + text[insert:]

    existing = re.findall(r'"([^"]+)"', match.group(1))
    if plugin_path in existing:
        return text

    existing.append(plugin_path)
    value = ", ".join(f'"{item}"' for item in existing)
    body_start = start + match.start()
    body_end = start + match.end()
    return text[:body_start] + f"enabled=PackedStringArray({value})" + text[body_end:]


def enable_autoload(
    text: str,
    name: str = AUTOLOAD_NAME,
    path: str = AUTOLOAD_PATH,
) -> str:
    text = _ensure_trailing_newline(text)
    section = _find_section(text, "autoload")
    line = f'{name}="{path}"'
    if section is None:
        return text + "\n[autoload]\n\n" + line + "\n"

    start, end = section
    body = text[start:end]
    pattern = re.compile(rf"(?m)^{re.escape(name)}\s*=.*$")
    if pattern.search(body):
        return text[:start] + pattern.sub(line, body) + text[end:]
    return text[:start] + line + "\n" + text[start:]


def _ensure_trailing_newline(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


def _find_section(text: str, name: str) -> tuple[int, int] | None:
    header = re.search(rf"(?m)^\[{re.escape(name)}\]\s*$", text)
    if header is None:
        return None
    body_start = header.end()
    next_header = re.search(r"(?m)^\[[^\]]+\]\s*$", text[body_start:])
    body_end = len(text) if next_header is None else body_start + next_header.start()
    return body_start, body_end
