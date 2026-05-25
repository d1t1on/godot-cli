# Release And Operations

Last updated: 2026-05-24

This document records the supported bootstrap and validation path for shipping
or operating Godot Playwright.

## Supported Environment

- OS used for validation: Arch Linux.
- Godot used for validation: Godot 4.6.2 stable from the local `godot`
  executable.
- Python package requirement: Python 3.11 or newer.
- Network model: local loopback HTTP JSON-RPC, default
  `127.0.0.1:9777`.
- Package shape: the Python package includes
  `godot_playwright/bundled_addons/godot_playwright`, so installed console
  scripts can initialize or install projects without importing from the source
  checkout.

## Clean Install Smoke

Use this when checking that an agent can bootstrap from a clean Python
environment:

```sh
python -m venv /tmp/godot-playwright-venv
/tmp/godot-playwright-venv/bin/python -m pip install /path/to/godot-cli
cd /tmp

/tmp/godot-playwright-venv/bin/godot-playwright init /tmp/agent-game --name AgentGame
/tmp/godot-playwright-venv/bin/godot-playwright smoke /tmp/agent-game --mode runtime
/tmp/godot-playwright-venv/bin/godot-playwright smoke /tmp/agent-game --mode editor
/tmp/godot-playwright-venv/bin/godot-playwright validate /tmp/agent-game --exclude "addons/**"
```

The import path and bundled addon path should resolve inside the virtual
environment's `site-packages`, not the repository checkout.

## Release Validation

Run these from the repository root before treating a build as releasable:

```sh
python -m py_compile godot_playwright/*.py tests/test_*.py
godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd
python -m unittest tests.test_codegen
python -m unittest discover -s tests
python -m godot_playwright.cli install examples/basic --autoload
python -m godot_playwright.cli install examples/agent_workspace --autoload
python -m godot_playwright.cli validate examples/basic --exclude "addons/**" --frames 3 --artifacts-dir godot-playwright-report-basic
python -m godot_playwright.cli validate examples/agent_workspace --exclude "addons/**" --frames 3 --artifacts-dir godot-playwright-report-agent
```

After validation, remove generated reports/caches and confirm no generated
Godot files or processes remain:

```sh
rm -rf godot-playwright-report godot-playwright-report-basic godot-playwright-report-agent
find . -type d -name __pycache__ -prune -exec rm -rf {} +
find examples -type d -name .godot -prune -exec rm -rf {} +
rg --files -uu -g '*egg-info/**' -g 'build/**' -g 'dist/**' -g '*.uid' -g '**/.godot/**' -g '**/__pycache__/**' -g '**/.codex_*' -g 'extension_api.json'
ps -eo pid=,comm=,args= | awk '$2 == "godot" {print}'
```

The last two commands should print no project-generated files and no lingering
Godot process.

## Common Failures

- `Bundled add-on not found`: package data is missing. Verify
  `pyproject.toml` includes `godot_playwright = ["bundled_addons/godot_playwright/*"]`
  and that `godot_playwright.install.bundled_addon_path()` resolves inside the
  installed package.
- `Failed to listen on 127.0.0.1:9777`: another Godot Playwright server is
  already running. Stop the other Godot process or set a different
  `GODOT_PLAYWRIGHT_PORT` for manual Godot launches.
- Runtime probe reports Godot log errors: inspect the per-scene `*-probe.log`
  in the artifacts directory; validation reports surface the scene path and log
  path for each diagnostic.
- `MAIN_SCENE_NOT_CONFIGURED`: set `application/run/main_scene` in
  `project.godot` or pass explicit scene paths to probe/validate commands.
- Editor smoke changes a project: run editor smoke on a temporary copy unless
  generated `res://scenes/godot_playwright_smoke.tscn`,
  `res://scripts/godot_playwright_smoke_tool.gd`, and
  `res://data/godot_playwright_smoke_resource.tres` are intended.

## Release Checklist

- Version in `pyproject.toml` matches the intended release.
- `README.md`, `docs/protocol.md`, `docs/completion-audit.md`, and this file
  match the current protocol/test evidence.
- Source addon, bundled package addon, and example addon copies match.
- Full validation commands above pass.
- Generated reports, caches, `.godot`, `.uid`, build, and egg-info output are
  removed before handing the tree to another agent or packaging step.
