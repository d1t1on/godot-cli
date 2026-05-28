from __future__ import annotations

import os


def isolated_godot_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("GODOT_PLAYWRIGHT_HOST", "127.0.0.1")
    env["GODOT_PLAYWRIGHT_PORT"] = "0"
    return env
