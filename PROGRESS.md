# Godot Playwright Progress Log

Date: 2026-05-23
Last updated: 2026-05-24 23:52:28 CST

Objective: build a Godot automation layer for AI agents with Playwright-like development and testing control over Godot projects.

## Current Status

The project now has a Godot addon JSON-RPC server, a Python client, CLI runner,
example projects, integration tests, traces, an HTML report, release docs, and
human real-project corpus evidence. The completion gates defined for the broad
"Playwright for Godot" objective are satisfied for the current local Arch Linux
and Godot 4.6.2 environment.

Overall estimate: 100% for the current completion gates toward a serious
"Playwright for Godot" automation toolkit.

What is already strong: core runtime/editor RPC transport, Python automation client, locator/assertion patterns, input automation, live project health summaries, live project readiness doctor, project inventory with scale evidence, validation/reporting, richer import/export diagnostics/preflight evidence, import asset discovery, visual screenshot evidence helpers, trace-to-test replay coverage for common interactions/granular node authoring/editor workflows/resource graph authoring and schema discovery/resource class discovery/resource file discovery/node class discovery/node class property/method/signal typed schema discovery/project script class discovery/project script file describe/project scene file discovery/project configuration/runtime probes/signals, editor UI state/action control and ScriptEditor state evidence, live filesystem mutation/discovery/search/edit helpers, completion audit matrix, clean package bootstrap, multi-project validation evidence, external generated project scale/asset/export evidence, human real-project corpus evidence, release/operations docs, example project sync, and a passing automated test suite.

Remaining work is post-completion hardening: broader project corpus coverage,
more OS/Godot/Python version matrices, and long-tail editor/asset/export edge
cases.

Progress tracking rule: this file is updated when an increment starts, when validation completes, and when cleanup status changes, so the newest useful status is always near the top.

## Latest Completed Increment

Human real-project corpus validation is complete.

Planned delivery in this increment:

- Copy a non-generated local Godot project outside this repository instead of
  modifying the original project.
- Install the bundled addon into the copied project through the public CLI path.
- Run project inventory, validation, live doctor/runtime checks where feasible,
  and export preflight if presets are available.
- Record any remaining workflow, import, or export edge cases from a real
  human project.

Status:

- Broad objective completion gates are satisfied for the current local
  environment.
- Overall estimate moved from 99.995% to 100% for the current completion gates.
- Implementation started at 2026-05-24 23:18:41 CST.
- Selected `/home/nietkui/GodotProjects/ItsNotBug` as the first corpus target:
  744 files, 120 scripts, 47 scenes, 20 resources, 180 assets, and
  `export_presets.cfg` present.
- `ItsNotBug` surfaced a real inventory gap: `application/run/main_scene` can
  use `uid://...` instead of `res://...`. Added UID-to-resource resolution from
  `.uid` sidecars and text resource headers, with regression coverage.
- `ItsNotBug` inventory then passed on the copied project with 714 files,
  107 scripts, 45 scenes, 20 resources, 183 assets, 11 autoloads, 3 export
  presets, UID main scene resolved to `res://scenes/main/start_ui.tscn`, and
  zero diagnostics.
- `ItsNotBug` validation reached 3/5 before and after import because the
  project has autoload/global-class patterns that fail isolated script checks;
  resources and scene inspection passed, runtime improved after import from
  0/45 to 28/45, and Web export preset discovery worked but export was blocked
  by missing Godot 4.6.2 Web export templates.
- Selected `/home/nietkui/GodotProjects/card-battle` as the second corpus
  target: 244 files, 34 scripts, 8 scenes, 1 asset, and 1 export preset.
- `card-battle` surfaced a real scene parser gap: Godot text scenes can use
  relative parent paths like `parent="./BattleVBox"`. Added parent-path
  normalization with regression coverage.
- After Godot import/global-class registration, `card-battle` validation passed
  5/5: inventory 244 files, scripts 34/34, resources 8/8, scene inspection
  8/8, runtime probes 8/8.
- Live runtime `project.doctor` passed on `card-battle` with 6/6 checks:
  protocol surface, Godot version, project summary, main scene, project
  content, and imports.
- `card-battle` export preset discovery worked for `CardGame`; export was
  blocked by missing Godot 4.6.2 Windows export templates, not by addon logic.
- Validation and cleanup completed at 2026-05-24 23:52:28 CST.

Validation completed for this increment:

- `python -m py_compile godot_playwright/inventory.py tests/test_inventory.py`
  -> passed
- `python -m unittest tests.test_inventory` -> 4 passed
- `python -m py_compile godot_playwright/scene.py tests/test_scene.py` ->
  passed
- `python -m unittest tests.test_scene` -> 4 passed
- `python -m godot_playwright.cli validate /tmp/godot-real-corpus-card-lzBDcp/card-battle --exclude 'addons/**' --frames 3 --artifacts-dir /tmp/godot-real-corpus-card-lzBDcp/report-final`
  -> 5/5 checks passed
- Live `project.doctor` on the copied `card-battle` project -> 6/6 checks
  passed
- `python -m py_compile godot_playwright/*.py tests/test_*.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
  -> passed
- `python -m unittest discover -s tests` -> 145 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli install examples/agent_workspace --autoload`
  -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report-basic`
  -> 5/5 checks passed
- `python -m godot_playwright.cli validate examples/agent_workspace --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report-agent`
  -> 5/5 checks passed
- Cleanup check -> no generated build/egg-info, `.uid`, `.godot`,
  `__pycache__`, `.codex_*`, reports, or `extension_api.json` files, no
  lingering Godot processes, and basic/agent/package bundled addon copies all
  match the source addon.

## Previous Completed Increment

External generated project scale, asset, and export-preflight evidence is in
complete.

Planned delivery in this increment:

- Add a live regression that creates a temporary non-bundled Godot project,
  installs the addon, adds extra scripts/scenes/resources/assets/export preset
  data, and validates it through the normal public APIs.
- Assert project inventory scale, selected runtime validation, asset/resource
  discovery, and export preset preflight fields so real-world project edges are
  covered beyond the bundled examples.
- Run focused/full validation and cleanup.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 99.99% to 99.995%.
- Implementation started at 2026-05-24 21:47:51 CST.
- Added `tests/test_external_project.py`, which creates a temporary
  non-bundled project, installs the addon through `init_project`, adds extra
  scripts/scenes/resources/assets/export preset data, runs validation, checks
  live `project.doctor`, and exercises export preflight.
- The fixture covers at least 35 project files, 12 PNG assets, 12 `.tres`
  resources, 6 scenes, 3 scripts, export preset discovery, runtime scene probes,
  and package-level addon bootstrap outside bundled examples.
- Initial version surfaced a real import boundary: unimported PNG files should
  not be forced through runtime `Texture2D` loads before Godot import metadata
  exists. The fixture now keeps asset paths as metadata while still covering
  asset discovery/import readiness.
- Validation and cleanup completed at 2026-05-24 23:05:51 CST.

Validation completed for this increment:

- `python -m py_compile tests/test_external_project.py` -> passed
- `python -m unittest tests.test_external_project` -> passed
- `python -m unittest tests.test_export tests.test_external_project` -> 6 passed
- `python -m unittest discover -s tests` -> 144 passed
- `python -m py_compile godot_playwright/*.py tests/test_*.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli install examples/agent_workspace --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report-basic` -> 5/5 checks passed
- `python -m godot_playwright.cli validate examples/agent_workspace --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report-agent` -> 5/5 checks passed
- Cleanup check -> no generated build/egg-info, `.uid`, `.godot`,
  `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
  processes, and basic/agent/package bundled addon copies all match the source
  addon.

## Previous Completed Increment

Release documentation and final validation pass were completed.

Planned delivery in this increment:

- Add concise release/operations documentation covering supported runtime
  assumptions, clean install, bundled addon packaging, validation commands,
  common failures, and release steps.
- Run the final validation sequence across syntax, codegen, full tests, bundled
  examples, and cleanup.
- Update the completion audit with the final evidence.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 99.98% to 99.99%.
- Implementation started at 2026-05-24 21:02:15 CST.
- Added `docs/release.md` with supported environment, clean install smoke,
  release validation commands, cleanup checks, common failures, and release
  checklist.
- Linked release/operations docs from README.
- Final validation and cleanup completed at 2026-05-24 21:44:52 CST.

Validation completed for this increment:

- Documentation review for `README.md`, `docs/protocol.md`,
  `docs/completion-audit.md`, and `docs/release.md` -> passed
- `python -m py_compile godot_playwright/*.py tests/test_*.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 10 passed
- `python -m unittest discover -s tests` -> 143 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli install examples/agent_workspace --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report-basic` -> 5/5 checks passed
- `python -m godot_playwright.cli validate examples/agent_workspace --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report-agent` -> 5/5 checks passed
- Cleanup check -> no generated build/egg-info, `.uid`, `.godot`,
  `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
  processes, and basic/agent/package bundled addon copies all match the source
  addon.

## Previous Completed Increment

Final trace/codegen edge audit was added and validated.

Planned delivery in this increment:

- Compare trace events emitted by the Godot addon with the events that
  `godot-playwright codegen-trace` can replay as helper calls.
- Add an explicit coverage audit or regression test so unsupported events are
  intentional and remain preserved as review comments instead of silently
  disappearing.
- Update docs/progress with the final trace/codegen evidence.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 99.95% to 99.98%.
- Implementation started at 2026-05-24 20:05:46 CST.
- Extracted the current addon `_record_event(...)` surface: 119 emitted event
  types.
- Verified `codegen-trace` replays 116 emitted event types as Python helper
  calls and intentionally treats `rpc`, `trace.start`, and `trace.stop` as
  infrastructure events.
- Added `tests.test_codegen.test_codegen_covers_addon_trace_event_surface` so
  new addon trace events must either be replayable or explicitly classified.
- Documented trace/codegen coverage in README and protocol docs.
- Validation and cleanup completed at 2026-05-24 20:57:11 CST.

Validation completed for this increment:

- Trace event extraction -> 119 addon-emitted event types
- Codegen support audit -> 116 replayed helper event types, 3 intentional infrastructure events
- `python -m py_compile tests/test_codegen.py` -> passed
- `python -m unittest tests.test_codegen` -> 10 passed
- `python -m unittest discover -s tests` -> 143 passed
- Cleanup check -> no generated build/egg-info, `.uid`, `.godot`,
  `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
  processes, and basic/agent/package bundled addon copies all match the source
  addon.

## Previous Completed Increment

Second-project evidence for broader Godot project shapes was added and
validated.

Planned delivery in this increment:

- Add a second example Godot project with a different layout from
  `examples/basic`, including nested scenes/scripts/resources and a main scene
  that can still be driven by the existing runtime/editor smoke tools.
- Install/sync the bundled addon into that project and run runtime smoke,
  editor smoke, and project validation against it.
- Record the multi-project evidence in the audit and progress log so the final
  completion decision is based on more than one bundled project shape.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 99.9% to 99.95%.
- Implementation started at 2026-05-24 19:31:09 CST.
- Added `examples/agent_workspace`, a second bundled project shape with nested
  scenes/scripts, a `.tres` resource, project autoloads, and a runtime-smoke
  compatible main scene.
- Added `tests/test_examples.py` so the second project is copied to a temporary
  directory and validated by the live Godot validation gate during the suite.
- Fixed `inspect_project(include_settings=False)` so hiding full settings maps
  no longer breaks main scene/autoload summary checks in validation reports.
- Added inventory coverage for the no-settings summary path and documented the
  second fixture in README/audit docs.
- Validation and cleanup completed at 2026-05-24 20:04:16 CST.

Validation completed for this increment:

- `python -m godot_playwright.cli check-scripts examples/agent_workspace --exclude 'addons/**' --json` -> 4/4 scripts passed
- `python -m godot_playwright.cli check-resources examples/agent_workspace --exclude 'addons/**' --json` -> 4/4 resources/scenes passed
- `python -m godot_playwright.cli inspect-project examples/agent_workspace --exclude 'addons/**' --json` -> 9 files, 4 scripts, 3 scenes, 1 resource, 2 autoloads
- `python -m godot_playwright.cli inspect-scene examples/agent_workspace res://scenes/main.tscn --json` -> 17 nodes, 4 external resources
- Runtime smoke on a temporary copy of `examples/agent_workspace` -> passed with `CounterButton` changing to `Clicked 1`
- Editor smoke on a temporary copy of `examples/agent_workspace` -> passed and saved `res://scenes/godot_playwright_smoke.tscn`
- Temporary-copy validation for `examples/agent_workspace` -> 5/5 checks passed
- `python -m py_compile godot_playwright/inventory.py tests/test_inventory.py tests/test_examples.py` -> passed
- `python -m unittest tests.test_inventory` -> 3 passed
- `python -m unittest tests.test_examples` -> 1 passed
- `python -m unittest discover -s tests` -> 142 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli install examples/agent_workspace --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report-basic` -> 5/5 checks passed
- `python -m godot_playwright.cli validate examples/agent_workspace --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report-agent` -> 5/5 checks passed
- Cleanup check -> no generated build/egg-info, `.uid`, `.godot`,
  `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
  processes, and basic/agent/package bundled addon copies all match the source
  addon.

## Previous Completed Increment

Fresh-environment packaging smoke and bootstrap documentation was added and
validated.

Planned delivery in this increment:

- Create a clean Python virtual environment outside the repository and install
  the local package through `pip`.
- Use the installed `godot-playwright` console script to initialize a fresh
  Godot project, run runtime/editor smoke checks, and run project validation.
- Document the verified bootstrap path and common environment assumptions so
  agents can start from a clean machine more reliably.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 99.8% to 99.9%.
- Implementation started at 2026-05-24 19:20:32 CST.
- Initial clean venv smoke exposed a real packaging bug: installed packages did
  not include the bundled Godot add-on files, so `godot-playwright init` failed.
- Fixed packaging by adding `godot_playwright/bundled_addons/godot_playwright`
  package data and teaching `bundled_addon_path()` to work from both source
  trees and installed packages.
- Added install coverage for bundled add-on files and documented the clean
  bootstrap path in README.
- Full validation and cleanup completed at 2026-05-24 19:28:20 CST.

Validation completed for this increment:

- `python -m py_compile godot_playwright/install.py tests/test_install.py` -> passed
- `python -m unittest tests.test_install` -> 7 passed
- Clean venv `pip install /home/nietkui/Projects/godot-cli` from outside the
  repository -> installed package imported from `site-packages`
- Installed package bundled add-on lookup -> resolved inside `site-packages`
- Fresh project `godot-playwright init` from installed console script -> passed
- Fresh project runtime smoke -> passed with `counter_button_present=True`
- Fresh project editor smoke -> passed and saved
  `res://scenes/godot_playwright_smoke.tscn`
- Fresh project `godot-playwright validate --exclude 'addons/**' --frames 3`
  -> 5/5 checks passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 141 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed
- Cleanup check -> no generated build/egg-info, `.uid`, `.godot`,
  `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
  processes, and both example/package bundled addon copies match the source
  addon.

## Previous Completed Increment

Completion audit matrix for the original Playwright-for-Godot objective was
added and validated.

Planned delivery in this increment:

- Add a compact audit document that maps the original objective to concrete
  capability areas: launch/connect, live inspection, selectors, actions,
  assertions, editor authoring, project/files/resources, traces/codegen,
  reporting, diagnostics, CI/scale, and packaging/docs.
- Ground each area in local evidence from implemented RPC methods, Python
  helpers, CLI commands, tests, docs, and validation results.
- Use the audit to identify the narrow remaining gaps before considering the
  broad goal complete.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 99.7% to 99.8%.
- Implementation started at 2026-05-24 19:18:07 CST.
- Audit document added at `docs/completion-audit.md`.
- Audit evidence was checked against protocol/test counts and local docs.
- Cleanup completed at 2026-05-24 19:19:46 CST.

Validation completed for this increment:

- `docs/completion-audit.md` review against README/protocol/test evidence -> passed
- RPC method count check from addon protocol list -> 160 methods
- Test function count check from `tests/test_*.py` -> 140 tests
- Cleanup check -> no generated `.uid`, `.godot`, `__pycache__`,
  `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and
  example addon copy matches the source addon.

## Previous Completed Increment

Live project doctor for agent readiness triage was added and validated.

Planned delivery in this increment:

- Add a `project.doctor` RPC that combines protocol capability discovery,
  engine/editor state, project summary, resource/import diagnostics, and
  actionable next steps into one readiness report.
- Add Python `project_doctor(...)`, fake server support, trace/codegen replay,
  README/protocol docs, and live integration coverage so agents can quickly
  decide whether a connected project is ready for authoring/testing or needs
  setup fixes first.
- Sync the example addon copy and run focused, live, full, CLI, and cleanup
  validation.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 99.5% to 99.7%.
- Implementation started at 2026-05-24 19:02:24 CST.
- Implementation is in place for addon RPC dispatch/readiness report, Python
  helper, fake server coverage, trace/codegen replay, focused unit tests,
  README/protocol docs, example addon sync, and live integration assertions.
- Syntax validation passed at 2026-05-24 19:08:44 CST.
- Focused unit validation passed at 2026-05-24 19:09:45 CST.
- Live Godot integration validation passed after focused unit validation.
- Full suite, CLI validation, addon sync, and cleanup completed at
  2026-05-24 19:16:29 CST.

Validation completed so far:

- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 37 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> passed
- `python -m unittest discover -s tests` -> 140 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Protocol self-description for agent capability discovery was added and validated.

Planned delivery in this increment:

- Add a `protocol.describe` RPC that reports server/Godot mode info, supported
  RPC methods grouped by domain, protocol features, and client helper names so
  agents can discover the live automation surface without relying only on docs.
- Add Python `protocol_describe(...)`, fake server coverage, trace/codegen
  replay where useful, README/protocol docs, and live integration assertions.
- Sync the example addon copy and run focused, live, full, CLI, and cleanup
  validation.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 99% to 99.5%.
- Implementation started at 2026-05-24 18:47:15 CST.
- Implementation is in place for addon RPC dispatch/description payload,
  Python helper, fake server coverage, trace/codegen replay, and focused unit
  tests, README/protocol docs, example addon sync, and live integration
  assertions.
- Syntax validation passed at 2026-05-24 18:54:04 CST.
- Focused unit validation passed at 2026-05-24 18:55:39 CST.
- Live Godot integration validation passed at 2026-05-24 18:57:10 CST.
- Full suite, CLI validation, addon sync, and cleanup completed at
  2026-05-24 18:59:45 CST.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 37 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> passed
- `python -m unittest discover -s tests` -> 140 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Resource move with reference update for safe project refactors was added and validated.

Planned delivery in this increment:

- Add a `resource.move` RPC that moves a referenced `res://` file and can
  update exact path references in text scene/resource files during the same
  operation, with dry-run preview and replacement evidence.
- Add Python `resource_move(...)`, fake server support, trace/codegen replay,
  README/protocol docs, and live integration coverage so agents can safely
  rename or relocate resources/scripts that scenes and resources depend on.
- Sync the example addon copy and run focused, live, full, CLI, and cleanup
  validation.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 98% to 99%.
- Implementation started at 2026-05-24 18:29:49 CST.
- Implementation is in place for addon RPC dispatch/move/reference rewrite,
  Python helper, fake server coverage, trace/codegen replay, and focused unit
  tests, README/protocol docs, example addon sync, and live integration
  assertions.
- Syntax validation passed at 2026-05-24 18:34:22 CST.
- Focused unit validation passed at 2026-05-24 18:37:12 CST.
- Live Godot integration validation passed at 2026-05-24 18:43:21 CST after
  replacing an eager resource-type load with static `.tres/.tscn/.gd` type
  detection to avoid stale-path ResourceLoader noise during move scans.
- Full suite, CLI validation, addon sync, and cleanup completed at
  2026-05-24 18:45:18 CST.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Unified editor filesystem open workflow was added and validated.

Planned delivery in this increment:

- Add an `editor.filesystem.open` RPC that selects a `res://` path and then
  dispatches by file kind: scenes open in the editor, scripts open in the
  ScriptEditor, and resources open in the Inspector.
- Add Python `editor_filesystem_open(...)`, fake server support, trace/codegen
  replay, docs, and live integration coverage so agents can navigate to a file
  without branching manually on extension/resource type.
- Sync the example addon copy and run focused, live, full, CLI, and cleanup
  validation.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 97% to 98%.
- Implementation started at 2026-05-24 17:20:29 CST.
- Implementation is in place for addon RPC dispatch/open behavior, Python
  helper, fake server coverage, trace/codegen replay, README/protocol docs, and
  live integration assertions.
- Syntax validation passed at 2026-05-24 18:16:25 CST.
- Focused unit validation passed at 2026-05-24 18:17:14 CST.
- Live Godot integration validation passed at 2026-05-24 18:18:01 CST.
- Full suite, CLI validation, addon sync, and cleanup completed at
  2026-05-24 18:20:55 CST.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Resource reverse references for safe refactor planning were added and validated.

Planned delivery in this increment:

- Add a `resource.references` RPC that scans project scene/resource files and
  returns files whose Godot dependency list references a target resource path or
  UID, with missing-state and truncation evidence.
- Add Python `resource_references(...)`, fake server support, trace/codegen
  replay, and an expectation so agents can assert a resource is referenced by
  an expected scene/resource before deletion, renaming, replacement, or export.
- Update README/protocol docs, sync the example addon copy, and run focused and
  full validation.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 96% to 97%.
- Implementation started at 2026-05-24 17:03:11 CST.
- Implementation is in place for addon RPC scanning, Python helper,
  expectation, fake server coverage, trace/codegen replay, README/protocol
  docs, and live integration assertions.
- Syntax validation passed at 2026-05-24 17:09:56 CST.
- Focused unit validation passed at 2026-05-24 17:11:11 CST.
- Live Godot integration validation passed at 2026-05-24 17:13:12 CST.
- Full suite, CLI validation, addon sync, and cleanup completed at
  2026-05-24 17:15:59 CST.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Static resource file describe for `.tres/.res` graph planning was added and validated.

Planned delivery in this increment:

- Add a `resource.file.describe` RPC that describes one saved resource file by
  path, format, load status, dependencies, root resource metadata, text
  external resources, text subresources, properties, and diagnostics.
- Add Python `resource_file_describe(...)`, fake server/parser coverage,
  trace/codegen replay, and focused expectations so agents can inspect saved
  resource graph shape before mutation, duplication, or scene wiring.
- Update README/protocol docs, sync the example addon copy, and run focused and
  full validation.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 95% to 96%.
- Implementation started at 2026-05-24 15:43:00 CST.
- Implementation is in place for addon RPC dispatch/parser, Python helper,
  expectations, fake server coverage, trace/codegen replay, README/protocol
  docs, and live integration assertions.
- Syntax validation passed at 2026-05-24 16:25:22 CST.
- Focused unit validation passed at 2026-05-24 16:26:15 CST.
- Live Godot integration validation passed at 2026-05-24 16:27:54 CST after
  fixing a `_safe_int` conversion issue seen in the first live run.
- Full suite, CLI validation, addon sync, and cleanup completed at
  2026-05-24 17:02:22 CST.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Live project summary for first-pass agent planning was added and validated.

Planned delivery in this increment:

- Add a `project.summary` RPC that aggregates main scene, autoloads, export
  presets, InputMap actions, scene files, script classes, resource files, import
  assets, counts, and diagnostics into one live project health snapshot.
- Add Python `project_summary(...)`, fake server support, trace/codegen replay,
  and live integration coverage so agents can quickly decide what to inspect or
  fix next in a connected Godot session.
- Update README/protocol docs, sync the example addon copy, and run focused and
  full validation.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 94% to 95%.
- Implementation started at 2026-05-24 15:05:58 CST and completed at
  2026-05-24 15:39:17 CST.

Validation completed for this increment:

- Live integration assertion confirmed `godot.project_summary(...)` aggregates
  main scene, autoloads, export presets, InputMap actions, scene files, script
  classes, resource files, imported assets, counts, and diagnostics in a
  connected editor session.
- Live summary confirmed generated scene/script/resource/import work is visible
  in one project-level snapshot, including the generated texture import.
- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project import asset discovery for safer asset planning was added and validated.

Planned delivery in this increment:

- Add a `resource.imports` RPC to scan importable project assets and summarize
  `.import` metadata, importer/resource type, loadability, generated file
  readiness, stale/missing generated files, diagnostics, and truncation state.
- Add Python `resource_imports(...)` plus expectation coverage so agents can
  assert imported external assets are discoverable before using them in scenes,
  resources, or export validation.
- Update fake server coverage, live integration assertions, trace/codegen
  replay, README/protocol docs, and sync the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 93% to 94%.
- Implementation started at 2026-05-24 14:43:37 CST and completed at
  2026-05-24 15:02:19 CST.

Validation completed for this increment:

- Live integration assertion confirmed `godot.resource_imports(...)` discovers
  the reimported `res://assets/generated_pixel.png` texture import by importer
  and generated-file readiness through the live RPC channel.
- Live expectation confirmed
  `expect_resource(godot, pixel_path).to_be_import_listed(importer="texture",
  generated_files_ready=True)`.
- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project script file describe for direct GDScript planning was added and validated.

Planned delivery in this increment:

- Add a `script.file.describe` RPC to inspect one `.gd` file by path,
  `class_name`, `extends`, functions, variables, constants, signals, optional
  source text, and load/resource status without requiring ScriptEditor state.
- Add Python `script_file_describe(...)` plus expectation coverage so agents can
  assert generated script shape before opening it or wiring it into scenes.
- Update fake server coverage, live integration assertions, trace/codegen
  replay, README/protocol docs, and sync the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 92% to 93%.
- Implementation started at 2026-05-24 14:25:04 CST and completed at
  2026-05-24 14:39:29 CST.

Validation completed for this increment:

- Live integration assertion confirmed `godot.script_file_describe(...)`
  inspects the generated `res://scripts/generated/agent_tool.gd` script by
  `class_name`, `extends`, functions, signals, variables, and source text
  through the live RPC channel.
- Live expectations confirmed
  `expect_script(godot, script_path).to_have_class_name("AgentTool")`,
  `to_define_signal("tool_ready")`, and `to_define_variable("enabled")`.
- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project resource file discovery for safer resource planning was added and validated.

Planned delivery in this increment:

- Add a `resource.files` RPC to discover project `.tres`/`.res` resources by
  path, filename, extension, class/type, resource name, and dependency status.
- Add Python `resource_files(...)` plus expectation coverage so agents can
  assert saved resources are discoverable before inspecting, mutating,
  duplicating, or wiring them into scenes.
- Update fake server coverage, live integration assertions, trace/codegen
  replay, README/protocol docs, and sync the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 91% to 92%.
- Implementation started at 2026-05-24 14:07:16 CST and completed at
  2026-05-24 14:21:51 CST.

Validation completed for this increment:

- Live integration assertion confirmed `godot.resource_files(...)` discovers
  the saved and updated `res://data/agent_resource.tres` resource by filename,
  class, resource name, and dependency state through the live RPC channel.
- Live expectation confirmed
  `expect_resource(godot, resource_path).to_be_listed(class_name="Resource",
  resource_name="AgentResourceV2")`.
- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project scene file describe for richer scene planning was added and validated.

Planned delivery in this increment:

- Add a `scene.file.describe` RPC to inspect one `.tscn`/`.scn` scene file with
  root, nodes, external resources, signal connections, properties, and
  dependency status.
- Add Python helper and expectation coverage so agents can assert saved scene
  structure and connections through the live RPC channel before opening,
  instantiating, or shipping generated scenes.
- Update fake server coverage, live integration assertions, trace/codegen
  replay, README/protocol docs, and sync the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 90% to 91%.
- Implementation started at 2026-05-24 13:45:18 CST and completed at
  2026-05-24 14:05:04 CST.

Validation completed for this increment:

- Live integration assertion confirmed `godot.scene_file_describe(...)`
  inspects the generated saved panel scene through the live RPC channel with
  node, property, resource, connection, and dependency evidence.
- Live expectations confirmed
  `expect_project_scene(godot, panel_scene_path).to_have_node(...)` and
  `to_have_connection(...)` on the described scene file.
- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project scene file discovery for safer scene planning was added and validated.

Delivered in this increment:

- Added `scene.files` RPC to discover project `.tscn`/`.scn` files by path,
  name, extension, root node class/name, node count, and dependency status.
- Added Python `scene_files(...)`,
  `expect_project_scene(...).to_be_listed(...)`, `to_have_root(...)`, and
  `to_have_no_missing_dependencies(...)`.
- Added runner fixtures for project scene/class discovery expectations,
  including previously documented node/resource/script class fixtures.
- Updated fake server coverage, live integration assertions, trace/codegen
  replay, README/protocol docs, and synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 89% to 90%.
- Implementation started at 2026-05-24 13:22:08 CST and completed at
  2026-05-24 13:41:41 CST.

Validation completed for this increment:

- Live integration assertion confirmed `godot.scene_files("res://scenes",
  name="generated_panel.tscn", root_class="VBoxContainer", include_nodes=True,
  max_results=20)` discovers the saved generated panel scene, exposes
  `root_name="GeneratedPanel"`, `root_class="VBoxContainer"`, a node count, and
  clean dependency status before further scene actions.
- Live expectations confirmed
  `expect_project_scene(godot, panel_scene_path).to_be_listed(root_class="VBoxContainer")`,
  `to_have_root(name="GeneratedPanel", class_name="VBoxContainer")`, and
  `to_have_no_missing_dependencies()`.
- Focused runner integration confirmed test fixtures expose
  `expect_project_scene`, `expect_node_class`, `expect_resource_class`, and
  `expect_script_class` in editor tests.
- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py tests/test_runner.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest tests.test_runner.RunnerIntegrationTests.test_runner_exposes_editor_semantic_fixtures` -> passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project script class discovery for custom Node/Resource planning was added and validated.

Delivered in this increment:

- Added `script.classes` RPC to scan project GDScript files for `class_name`,
  `extends`, path/global path, source symbols, and Node/Resource
  classification, including custom parent-chain classification.
- Added Python `script_classes(...)`,
  `expect_script_class(...).to_be_listed(...)`, `to_extend(...)`,
  `to_be_node(...)`, `to_be_resource(...)`, and `to_have_function(...)`.
- Updated fake server coverage, live integration assertions, trace/codegen
  replay, README/protocol docs, and synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 88% to 89%.
- Implementation started at 2026-05-24 12:59:36 CST and completed at
  2026-05-24 13:19:33 CST.

Validation completed for this increment:

- Live integration assertion confirmed `godot.script_classes(class_name="AgentTool",
  base_class="Node", max_results=20)` discovers the generated
  `class_name AgentTool` script at `res://scripts/generated/agent_tool.gd`,
  classifies it as a Node script class, not a Resource, and exposes its
  `tool_ready` signal, `enabled` variable, and `generated_value` function.
- Live expectations confirmed
  `expect_script_class(godot, "AgentTool").to_be_listed(base_class="Node")`,
  `to_extend("Node")`, `to_be_node()`, and
  `to_have_function("generated_value")`.
- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py godot_playwright/__init__.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Node class method/signal typed API schema for safer generated calls was added and validated.

Delivered in this increment:

- Normalized `node.class.describe` method/signal API entries with argument
  counts, default-argument counts, type names, hints, and return type metadata.
- Updated fake server and live integration coverage proving agents can inspect
  typed call/signal shapes before acting.
- Updated codegen/docs examples and synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 87% to 88%.

Validation completed for this increment:

- Live integration assertion confirmed
  `godot.node_class_describe("Label", methods=["set_text"],
  properties=["text"], storage_only=True)` exposes the `set_text` method with
  one `String` argument and still exposes the stored `text` property.
- Live integration assertion confirmed
  `godot.node_class_describe("Button", signals=["pressed"],
  include_methods=False, include_values=False)` exposes `pressed` with
  `arg_count=0`.
- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Node class method/signal schema discovery for safer calls and signal wiring was added and validated.

Delivered in this increment:

- Extended `node.class.describe` with class-level method and signal schema so
  agents can plan `node.call`, `node.call_all`, `signal.watch`, and
  `signal.connect` before instantiating nodes.
- Added Python `expect_node_class(...).to_have_method(...)` and
  `expect_node_class(...).to_have_signal(...)`.
- Added method/signal filters to Python `node_class_describe(...)` and
  trace/codegen replay.
- Updated fake server coverage, focused client/codegen tests, live integration
  assertions, README/protocol docs, and synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 86% to 87%.

Validation completed for this increment:

- Live integration assertion confirmed
  `godot.node_class_describe("Label", methods=["get_meta"],
  properties=["text"], storage_only=True)` exposes the inherited `get_meta`
  method and `godot.node_class_describe("Button", signals=["pressed"],
  include_methods=False, include_values=False)` exposes the `pressed` signal.
- Live expectations confirmed `expect_node_class(godot, "Label").to_have_method("get_meta")`
  and `expect_node_class(godot, "Button").to_have_signal("pressed")`.
- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Node class/schema discovery for safer scene authoring was added and validated.

Delivered in this increment:

- Added addon RPC `node.class.describe` for Node class instantiability,
  Node-subclass status, property metadata, type names, hints, usage flags,
  storage/editor-visible flags, and default values.
- Added Python `node_class_describe(...)`, `node_schema(...)`, and
  `expect_node_class(...).to_have_property(...)` /
  `expect_node_class(...).to_be_node(...)`.
- Added fake server coverage, focused client/codegen tests, live integration
  assertions, trace/codegen replay, README/protocol docs, and synced the
  example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 85% to 86%.

Validation completed for this increment:

- Live integration assertion confirmed
  `godot.node_class_describe("Label", properties=["text"],
  storage_only=True)` exposes the stored `text` property with
  `type_name="String"`, and
  `expect_node_class(godot, "Label").to_have_property("text",
  type_name="String", storage=True)` succeeds before `node.create`.
- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py godot_playwright/__init__.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Node class discovery/search for safer scene authoring was added and validated.

Delivered in this increment:

- Added addon RPC `node.classes` to list/search Node classes by base class,
  name substring, instantiability, enabled state, and optional property counts.
- Added Python `node_classes(...)`, `NodeClassExpect`, and
  `expect_node_class(...).to_be_listed(...)` /
  `expect_node_class(...).to_be_instantiable(...)`.
- Added fake server coverage, focused client/codegen tests, live integration
  assertions, trace/codegen replay, README/protocol docs, exports, and synced
  the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 84% to 85%.

Validation completed for this increment:

- Live integration assertion confirmed
  `godot.node_classes(base_class="Control", name_contains="Label",
  max_results=20)` lists `Label`, and
  `expect_node_class(godot, "Label").to_be_listed(base_class="Control")`
  succeeds before `node.create`.
- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py godot_playwright/__init__.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Resource class discovery/search for planning resource authoring was added and validated.

Delivered in this increment:

- Added addon RPC `resource.classes` to list/search Resource classes by base
  class, name substring, instantiability, Resource-subclass state, enabled
  state, and optional property counts.
- Added Python `resource_classes(...)` and
  `expect_resource_class(...).to_be_listed(...)`.
- Added fake server coverage, focused client/codegen tests, live integration
  assertions, trace/codegen replay, README/protocol docs, and synced the
  example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 83% to 84%.

Validation completed for this increment:

- Temporary live editor probe confirmed
  `godot.resource_classes(name_contains="Gradient", max_results=20)` returns
  `Gradient`, `GradientTexture1D`, and `GradientTexture2D`, and
  `expect_resource_class(godot, "GradientTexture1D").to_be_listed()` returns
  class evidence with property counts.
- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`,
`__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot
processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Resource class/schema discovery for safer resource authoring was added and validated.

Delivered in this increment:

- Added addon RPC `resource.class.describe` for Resource class instantiability, Resource-subclass status, property metadata, type names, hints, usage flags, storage/editor-visible flags, and default values.
- Added Python `resource_class_describe(...)`, `resource_schema(...)`, `ResourceClassExpect`, and `expect_resource_class(...)`.
- Added trace/codegen replay for `resource.class.describe`.
- Updated fake server coverage, focused client/codegen tests, live integration assertions, README, protocol docs, exports, and synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 82% to 83%.

Validation completed for this increment:

- Temporary live editor probe confirmed `resource_class_describe("GradientTexture1D")` exposes the stored `gradient` property with `hint_string="Gradient"`.
- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py godot_playwright/__init__.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Resource graph authoring for nested and referenced resources was added and validated.

Delivered in this increment:

- Extended resource property decoding with `ResourceRef` / `ExtResource` for external references and `SubResource` / pathless `Resource` specs for nested resources.
- Added recursive validation so missing referenced resources and non-instantiable nested resource classes fail before save/set/duplicate.
- Added resource readback canonicalization in the Python client so waits/assertions can verify saved resource graph properties.
- Added `dependency_state` evidence after `resource.save`, saved `resource.set_properties`, and `resource.duplicate`.
- Updated fake server coverage, focused client/codegen tests, live integration assertions, README, protocol docs, and synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 80% to 82%.

Validation completed for this increment:

- Temporary live editor probe confirmed `ResourceRef` from `GradientTexture1D.gradient` saves an external `Gradient` dependency and `SubResource` readback returns an inline `Gradient`.
- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor UI actions for main-screen switching and bottom-panel hiding were added and validated.

Delivered in this increment:

- Added addon RPCs `editor.ui.switch_main_screen` and `editor.ui.hide_bottom_panel`.
- Added live readback for current editor main-screen API names by deriving visible editor screen children from `EditorInterface.get_editor_main_screen()`, including `2D`, `3D`, `Script`, `Game`, and `AssetLib` heuristics.
- Added Python `wait_for_editor_main_screen(...)`, `editor_switch_main_screen(...)`, and `editor_hide_bottom_panel(...)` helpers with readback evidence.
- Added trace/codegen replay for `editor.ui.switch_main_screen` and `editor.ui.hide_bottom_panel`.
- Updated fake server coverage, focused client/codegen tests, integration assertions, README, protocol docs, and synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 78% to 80%.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/codegen.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- Temporary live editor probe confirmed `editor_switch_main_screen("Script")` changes `editor.ui.status.main_screen_name` to `Script`
- `python -m unittest tests.test_codegen` -> 9 passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor UI / main screen / bottom panel state evidence was added and validated.

Delivered in this increment:

- Added addon RPC `editor.ui.status` and embedded `ui` evidence into `editor.status`.
- Added editor base-control evidence, main-screen control/capability evidence, best-effort main-screen candidates, and bottom-panel capability evidence.
- Passed the `EditorPlugin` reference into the server so bottom-panel capability flags reflect real editor plugin methods.
- Added Python `editor_ui_status(...)`, `wait_for_editor_ui(...)`, `expect_editor(...).to_have_ui(...)`, `to_have_base_control(...)`, `to_have_main_screen(...)`, and `to_have_bottom_panel_capability(...)`.
- Updated fake server, focused client coverage, integration assertions, README, protocol docs, and synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.
- Overall estimate moved from 76% to 78%.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

Implementation notes:

- Godot 4.6.2 exposes `EditorInterface.get_base_control()`, `get_editor_main_screen()`, and `set_main_screen_editor(name)`.
- Bottom panel show/hide APIs live on `EditorPlugin`; there is no stable API in the inspected class metadata for listing bottom panel items or reading the active bottom panel, so this increment exposes explicit capability flags and null/empty fields when direct evidence is unavailable.

## Previous Completed Increment

Editor script workflow state evidence was added and validated.

Delivered in this increment:

- Added addon RPC `editor.script.status` for ScriptEditor availability, open script paths, open count, current script path, and capability flags.
- Added ScriptEditor status to `editor.status` and `editor.script.open` responses.
- Added Python `editor_script_status(...)`, `wait_for_editor_script(...)`, `expect_editor(...).to_have_open_script(...)`, and `expect_editor(...).to_have_current_script(...)`.
- Updated fake server, focused client coverage, integration assertions, README, and protocol docs.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project scale validation evidence was added and validated.

Delivered in this increment:

- Added inventory `files.scale` with file/directory counts, total/average/largest bytes, max path depth, category counts/bytes, top extensions, and top directories.
- Added per-file `directory` and `depth`, plus aggregate `directory_counts`, `directory_bytes`, and `top_directories`.
- Surfaced inventory scale evidence at top-level `validate_project(...)[\"scale\"]`.
- Updated `inspect-project` and `validate` CLI formatting to show scale evidence.
- Added focused inventory/validation tests and updated README/protocol docs.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/inventory.py godot_playwright/validate.py godot_playwright/cli.py tests/test_inventory.py tests/test_validate.py` -> passed
- `python -m unittest tests.test_inventory tests.test_validate` -> 6 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed; CLI output included `scale: files=12 dirs=5 bytes=32477 max_depth=3`
- `python -m godot_playwright.cli inspect-project examples/basic --exclude 'addons/**' --no-settings` -> passed; CLI output included directory hot spots and largest-file evidence

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Trace/codegen replay coverage expansion was added and validated.

Delivered in this increment:

- Added `codegen-trace` replay for `node.call_all`, animation play/stop/pause/seek/advance, 2D/3D physics probes, Camera3D ray/pick probes, viewport-size trace payloads, filesystem read/grep/copy/move operations, resource dependency/import metadata/reimport checks, and signal watch/event/unwatch/connect/disconnect flows.
- Preserved unsupported comments for write events where traces intentionally omit file contents.
- Added focused codegen coverage for runtime probes and signal workflows.
- Updated README/protocol trace replay coverage docs.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/codegen.py tests/test_codegen.py` -> passed
- `python -m unittest tests.test_codegen` -> 9 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 139 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Resource import diagnostics and reimport evidence were added and validated.

Delivered in this increment:

- Added source/import/generated file freshness evidence to `resource.import_metadata`, including file modified times.
- Added structured import diagnostics for missing sources, missing `.import` files, parse errors, source mismatches, stale metadata, missing/stale generated files, missing importers, and not-loadable imported resources.
- Added reimport preflight fields for source/import file states, forced reimport paths, forced count, and scan fallback state.
- Extended Python `wait_for_import(...)` with importer/resource-type/generated-file filters and diagnostic-rich timeout messages.
- Added focused client coverage and updated README/protocol docs.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_client` -> 36 passed
- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py` -> passed
- `python -m unittest discover -s tests` -> 138 passed
- `python -m godot_playwright.cli install examples/basic --autoload` -> passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Export diagnostics and preflight evidence were added and validated.

Delivered in this increment:

- Export reports now include structured Godot log diagnostics via the shared Godot output parser.
- Export reports now include `preset_export_path`, `preset_output_path`, `preset_output_state`, `output_relative_path`, and `output_matches_preset`.
- CLI export text output now surfaces output/preset path match evidence and export diagnostics.
- Added focused export tests for artifact reporting, output path mismatch evidence, structured diagnostics, and CLI formatting.
- Updated README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/export.py godot_playwright/cli.py tests/test_export.py` -> passed
- `python -m unittest tests.test_export` -> 5 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 138 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor workflow trace/codegen replay was added and validated.

Delivered in this increment:

- Extended addon trace payloads so editor workflow events retain replayable call parameters.
- Added trace events for editor play/stop and expanded trace payloads for scene new, undo/redo, selection, inspector, script-open, and editor filesystem selection flows.
- Extended `godot-playwright codegen-trace` to emit editable Python helper calls for full-parameter `scene.new`, `scene.open`, `scene.save`, `editor.play`, `editor.stop`, `editor.undo`, `editor.redo`, `editor.selection.set`, `editor.inspect`, `editor.inspector.set_property`, `editor.inspector.set_properties`, `editor.script.open`, `editor.filesystem.scan`, and `editor.filesystem.select`.
- Added focused codegen coverage for editor workflow replay.
- Updated README/protocol docs to describe the expanded replay surface.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/codegen.py tests/test_codegen.py` -> passed
- `python -m unittest tests.test_codegen` -> 8 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 137 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Granular node authoring trace/codegen was added and validated.

Delivered in this increment:

- Extended addon trace payloads so fine-grained node authoring events retain replayable call parameters.
- Extended `godot-playwright codegen-trace` to emit editable Python helper calls for `node.create`, `node.instantiate_scene`, `node.save_as_scene`, `node.set_properties`, `node.set_all_properties`, `node.attach_script`, `node.detach_script`, `node.set_metadata`, `node.remove_metadata`, `node.add_group`, `node.remove_group`, `node.reparent`, `node.move`, `node.duplicate`, and `node.delete`.
- Added focused codegen coverage for granular node authoring replay.
- Updated README/protocol docs to describe the expanded replay surface.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/codegen.py tests/test_codegen.py` -> passed
- `python -m unittest tests.test_codegen` -> 7 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 136 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project configuration trace/codegen replay was added and validated.

Delivered in this increment:

- Extended addon trace payloads so project setting, main scene, autoload, export preset, and InputMap mutation events retain replayable call parameters.
- Extended `godot-playwright codegen-trace` to emit editable Python helper calls for `project.set_setting`, `project.set_main_scene`, `project.add_autoload`, `project.remove_autoload`, `project.set_export_preset`, `input.action.configure`, and `input.action.erase`.
- Added focused codegen coverage for project configuration and InputMap replay.
- Updated README/protocol docs to describe the expanded replay surface.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/codegen.py tests/test_codegen.py` -> passed
- `python -m unittest tests.test_codegen` -> 6 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 135 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Visual inspection reports were added and validated.

Delivered in this increment:

- Added `SceneExpect.inspect_screenshot(...)` to capture a screenshot and always write an audit-friendly `*.visual.json` report.
- Added top-level `inspect_screenshot(path, ...)` for inspecting an existing PNG file.
- Reports include image size, SHA-256, actual PNG path, report path, sampled pixel colors, optional sample color-match status, region average/dominant colors, and optional region color-match metrics.
- Exported `inspect_screenshot` from the package API.
- Added focused visual tests for scene-captured and existing-file inspection reports.
- Updated README/protocol docs.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/visual.py godot_playwright/__init__.py tests/test_visual.py` -> passed
- `python -m unittest tests.test_visual` -> 8 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 134 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Semantic authoring trace/codegen was added and validated.

Delivered in this increment:

- Extended trace payloads for `node.create_tree`, `fs.replace_text`, `fs.replace_text_many`, `resource.save`, `resource.set_properties`, and `resource.duplicate` so they retain replayable call parameters.
- Extended `godot-playwright codegen-trace` to generate editable Python helper calls for those semantic authoring events.
- Added focused codegen coverage for node-tree creation, safe text patching, bulk text patching, Resource save/update, and Resource duplication.
- Updated README/protocol docs to describe trace replay coverage for semantic authoring events.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/codegen.py tests/test_codegen.py godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_codegen` -> 5 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 132 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Resource variant duplication was added and validated.

Delivered in this increment:

- Added addon RPC `resource.duplicate` for creating Resource variants from existing resources.
- Added Python helper `resource_duplicate(...)`.
- Source Resources are loaded through `ResourceLoader`, duplicated with deep-copy enabled by default, optionally updated with decoded property overrides, and saved through `ResourceSaver`.
- Added overwrite/create-parent behavior, property validation, source/destination metadata, previous/current property evidence, and saved status.
- Python helper auto-waits for source resource readback, destination resource property readback, destination file existence, and editor filesystem scan/index evidence.
- Updated fake server support and focused resource assertions.
- Updated README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_resource_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Declarative node tree authoring was added and validated.

Delivered in this increment:

- Added addon RPC `node.create_tree` for declarative nested node creation.
- Added Python helper `create_node_tree(...)`.
- Node specs support class/type, name, index, properties, metadata/meta, groups, script/script_path, and children.
- Created nodes are assigned edited-scene ownership when requested and the editor scene is marked dirty.
- Returned all created node summaries with property, metadata, group, and script evidence when requested.
- Python helper auto-waits for every created node plus requested property, metadata, group, and script readbacks.
- Updated fake server support and focused editor authoring assertions.
- Updated README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Resource property authoring was added and validated.

Delivered in this increment:

- Added addon RPC `resource.set_properties` for semantic updates to existing Godot Resources.
- Added Python helper `resource_set_properties(...)`.
- Resource updates load through `ResourceLoader`, validate target properties by default, apply decoded values, and save through `ResourceSaver` by default.
- Returned previous/current property evidence plus save status.
- Python helper auto-waits for resource property readback, saved file existence, and editor filesystem scan/index evidence when available.
- Updated fake server support and focused resource assertions.
- Updated README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_resource_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project-aware bulk text replacement was added and validated.

Delivered in this increment:

- Added addon RPC `fs.replace_text_many` for project-aware safe text replacement across files under `res://`.
- Added Python helper `fs_replace_text_many(...)`.
- Reused live filesystem filters: path, recursion, hidden/binary inclusion, name, name contains, extension, and resource type.
- Defaulted bulk replacement to dry-run mode.
- Required `expected_files` or `expected_replacements` before committed writes.
- Added per-file before/after line evidence, changed file count, total replacement count, and final text inclusion for verification.
- Python committed writes auto-wait on each changed file and include editor filesystem scan/index evidence.
- Updated fake server support and focused filesystem assertions.
- Updated README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_filesystem_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Live safe text replacement was added and validated.

Delivered in this increment:

- Added addon RPC `fs.replace_text` for safe live text replacement under `res://`.
- Added Python helper `fs_replace_text(...)` with default final-text verification and editor filesystem evidence.
- Added exact replacement count guard through `expected_replacements`, defaulting to one replacement.
- Added dry-run previews, case-sensitive or insensitive matching, max replacement caps, final text inclusion, and before/after line evidence.
- Updated fake server support and focused filesystem assertions.
- Updated README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_filesystem_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Live project grep was added and validated.

Delivered in this increment:

- Added addon RPC `fs.grep` for live text search across scripts, scenes, resources, and config files under `res://`.
- Added Python helper `fs_grep(...)`.
- Supported case sensitivity, recursion, hidden/binary inclusion, name/name-contains, extension, resource type, context line, max-file, max-result, and max-matches-per-file controls.
- Returned file path, global path, line, column, matching text, before-context, and after-context evidence for each match.
- Updated focused filesystem tests plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_filesystem_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Live filesystem discovery was added and validated.

Delivered in this increment:

- Added addon RPC `fs.info` for live file/directory metadata under `res://`.
- Added addon RPC `fs.find` for recursive project file discovery without relying on the editor filesystem dock.
- `fs.info` / `fs.find` entries expose path, type/kind, extension, bytes for files, resource type, and directory/file booleans.
- Added Python helpers `fs_info(...)` and `fs_find(...)`.
- Updated focused filesystem tests plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_filesystem_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Filesystem copy/move automation was added and validated.

Delivered in this increment:

- Added addon RPCs `fs.copy` and `fs.move` for agent-driven resource reorganization under `res://`.
- `fs.copy` copies files with overwrite/create-parent controls.
- `fs.move` moves or renames files/directories with overwrite/create-parent controls.
- Added Python helpers `fs_copy(...)` and `fs_move(...)`.
- Waited helpers return source/destination readback evidence plus editor filesystem scan/index evidence when available.
- Preserved fire-and-forget behavior through `wait=False`.
- Updated focused filesystem tests plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_filesystem_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project validation inventory gate was added and validated.

Delivered in this increment:

- Added `inventory` as the first default `validate_project(...)` check.
- Validation reports now include project structure, file-planning summary, autoload count, and export preset count alongside scripts/resources/scenes/runtime.
- Added CLI `--skip-inventory` for callers that need the previous narrower validation surface.
- Updated validation text output for inventory summaries.
- Fixed validation diagnostic location formatting so path-only diagnostics do not render `:None`.
- Updated README/protocol docs and focused validation coverage.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/validate.py godot_playwright/cli.py tests/test_validate.py tests/test_inventory.py` -> passed
- `python -m unittest tests.test_validate tests.test_inventory` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 5/5 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project inventory file-planning summaries were added and validated.

Delivered in this increment:

- Extended `inspect_project(...)[\"files\"]` with a full `files` list including file size and `mtime_ns`.
- Added aggregate `total_bytes`, `extension_counts`, and `extension_bytes`.
- Added `largest_files` and `newest_files` summaries to help agents plan edits before launching Godot.
- Updated CLI `inspect-project` formatting to show total bytes, extension distribution, and largest files.
- Updated README/protocol docs and focused inventory coverage.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/inventory.py godot_playwright/cli.py tests/test_inventory.py` -> passed
- `python -m unittest tests.test_inventory` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Export preflight and artifact freshness diagnostics were added and validated.

Delivered in this increment:

- Added `inspect_export_presets(...)` as a focused export preset inventory helper.
- Extended `export_project(...)` reports with `export_presets`, `preset_found`, and `preset_state`.
- Added output artifact freshness fields: `output_preexisting`, `output_mtime_before_ns`, `output_mtime_after_ns`, and `output_changed`.
- Updated CLI export formatting to show preset preflight and output freshness evidence.
- Updated README/protocol docs and focused export/inventory coverage.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/export.py godot_playwright/inventory.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_export.py tests/test_inventory.py` -> passed
- `python -m unittest tests.test_export tests.test_inventory` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Input action press/release auto-waits were added and validated.

Delivered in this increment:

- Extended `input_action(...)`, `action_down(...)`, `action_up(...)`, and `press_action(...)` with default pressed-state readback waits.
- Added `pressed_state` evidence to waited press/release helper results.
- Preserved fire-and-forget behavior through `wait=False`.
- Updated focused InputMap coverage for waited action press/release and `wait=False`.
- Updated README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_input_map_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

InputMap configuration auto-waits were added and validated.

Delivered in this increment:

- Added `GodotClient.wait_for_input_action_config(...)` for retryable InputMap action existence, event count, and deadzone readback.
- Extended `input_action_configure(...)` with default action readback waits and `action_state` evidence.
- Extended `input_action_set_events(...)` and bind helpers to pass wait controls through to configuration.
- Extended `input_action_erase(...)` with default action/event removal readback waits and `action_state` evidence.
- Preserved fire-and-forget behavior through `wait=False`.
- Updated focused InputMap coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_input_map_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Resource reimport editor-index auto-waits were added and validated.

Delivered in this increment:

- Extended `resource_reimport(...)` with editor filesystem index readback for every reimported `res://` path.
- Added `editor_filesystem` evidence for single-path reimports.
- Added `editor_filesystem_states` evidence for multi-path reimports.
- Preserved existing import metadata waits and `imports` / `import_count` evidence.
- Preserved fire-and-forget behavior through `wait=False`.
- Updated focused resource coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_resource_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor inspect auto-waits were added and validated.

Delivered in this increment:

- Added `Inspector.wait_for_description(...)` for retryable Inspector describe readback checks.
- Extended `editor_inspect(...)` with default Inspector describe readback waits and `inspector_state` evidence.
- Property-targeted inspect calls wait until the requested Inspector property is present.
- Preserved fire-and-forget behavior through `wait=False`.
- Updated focused editor Inspector coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor script open auto-waits were added and validated.

Delivered in this increment:

- Extended `editor_open_script(...)` with default script describe readback waits.
- Added `script_state` evidence to waited script open results.
- Exposed existing addon controls through Python `force` and `restore_external_editor` arguments.
- Routed `write_script(..., open_editor=True)` through the caller's timeout and interval when opening the generated script.
- Preserved fire-and-forget behavior through `wait=False`.
- Updated focused editor script coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor filesystem scan auto-waits were added and validated.

Delivered in this increment:

- Extended targeted `editor_scan_filesystem(...)` calls with default editor index readback waits.
- Added `filesystem_state` evidence for single-path scans.
- Added `filesystem_states` evidence for multi-path scans.
- Kept untargeted scans as raw scan requests because they have no concrete path to verify.
- Preserved fire-and-forget behavior through `wait=False`.
- Routed internal post-write/import/save scan calls through the caller's timeout and interval.
- Updated focused editor filesystem coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor filesystem selection auto-waits were added and validated.

Delivered in this increment:

- Added addon-side tracking for the last successful `editor.filesystem.select` target.
- Exposed filesystem selection readback through `editor.filesystem.describe` and `editor.filesystem.find` via `selected`.
- Added `GodotClient.wait_for_editor_filesystem_selection(...)`.
- Extended `GodotClient.wait_for_editor_filesystem_entry(...)` with a `selected` filter.
- Extended `GodotClient.editor_filesystem_select(...)` with default selected readback waits and `filesystem_state` evidence.
- Preserved fire-and-forget behavior through `wait=False`.
- Updated focused editor filesystem coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor scene open evidence auto-waits were added and validated.

Delivered in this increment:

- Extended `editor_open_scene(...)` with `interval` control for editor-scene readback.
- Waited scene opens now preserve the raw `scene.open` result, keep existing top-level edited-scene status fields, and include `editor_status` evidence.
- Preserved fire-and-forget behavior through `wait=False`.
- Updated focused editor authoring coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_locator_authoring_wrappers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Inspector property write auto-waits were added and validated.

Delivered in this increment:

- Added `Inspector.wait_for_property(...)` and `Inspector.wait_for_properties(...)` for retryable Inspector readback checks.
- Extended `Inspector.set(...)` with default readback waits and `property_state` evidence.
- Extended `Inspector.set_properties(...)` with default batch readback waits and `properties_state` evidence.
- Extended direct `editor_inspector_set_property(...)` and `editor_inspector_set_properties(...)` wrappers with `wait`, `timeout`, and `interval` controls.
- Preserved fire-and-forget behavior through `wait=False`.
- Updated focused Inspector coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_helpers_call_rpc` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor selection auto-waits were added and validated.

Delivered in this increment:

- Added `GodotClient.wait_for_editor_selection(...)` for retryable editor node selection checks by count or selected node names/paths.
- Extended `GodotClient.editor_select(...)` with default selection readback waits and `selection_state` evidence.
- Preserved fire-and-forget behavior through `wait=False`.
- Updated focused editor selection coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_expectations_poll_status` -> passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor undo/redo auto-waits were added and validated.

Delivered in this increment:

- Added `GodotClient.wait_for_editor_history(...)` for retryable editor undo/redo history checks.
- Extended `GodotClient.editor_undo(...)` with default history readback waits and `history_state` evidence.
- Extended `GodotClient.editor_redo(...)` with default history readback waits and `history_state` evidence.
- Preserved fire-and-forget behavior through `wait=False`.
- Updated focused editor authoring/history coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc tests.test_client.ClientTests.test_editor_expectations_poll_status` -> 2 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Locator structural expectations were added and validated.

Delivered in this increment:

- Added `expect(locator).to_match_node(...)` and `not_to_match_node(...)` for retryable `node.describe` summary assertions.
- Added `expect(locator).to_have_parent(...)` and `not_to_have_parent(...)`.
- Added `expect(locator).to_have_index(...)` and `not_to_have_index(...)`.
- Added `expect(locator).to_have_child_count(...)` and `not_to_have_child_count(...)`.
- Covered the new assertions in both generic locator expectation tests and generated-scene authoring wrapper tests.
- Updated README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_locator_richer_expectations tests.test_client.ClientTests.test_locator_authoring_wrappers_call_rpc` -> 2 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Node structural edit auto-waits were added and validated.

Delivered in this increment:

- Added `GodotClient.wait_for_node(...)` for direct attached/detached scene-tree checks with optional expected summary fields.
- Extended `create_node(...)`, `instantiate_scene(...)`, `reparent_node(...)`, `move_node(...)`, `duplicate_node(...)`, and `delete_node(...)` with default readback waits.
- Extended locator wrappers `create_child(...)`, `instantiate_scene(...)`, `reparent(...)`, `move(...)`, `duplicate(...)`, and `delete(...)` with wait controls.
- Added `node_state` evidence to structural edit results.
- Preserved fire-and-forget behavior through `wait=False`.
- Expanded node summaries with `parent` and `index`, using `get_index(true)` so internal editor nodes can be summarized without Godot errors.
- Updated focused authoring/structure coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc tests.test_client.ClientTests.test_locator_authoring_wrappers_call_rpc` -> 2 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Node group membership add/remove auto-waits were added and validated.

Delivered in this increment:

- Added `GodotClient.wait_for_node_group(...)` for direct present/missing group membership waits.
- Extended `GodotClient.add_node_group(...)` and `GodotClient.remove_node_group(...)` with default membership readback waits.
- Extended locator `add_group(...)` and `remove_group(...)` to pass through wait controls and return waited result payloads.
- Preserved fire-and-forget behavior through `wait=False`.
- Added `groups_state` evidence to direct group add/remove results.
- Updated focused authoring/group coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc tests.test_client.ClientTests.test_locator_authoring_wrappers_call_rpc` -> 2 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Node metadata write/remove auto-waits were added and validated.

Delivered in this increment:

- Added `GodotClient.set_node_metadata(...)` and `GodotClient.remove_node_metadata(...)` direct helpers with default metadata readback waits.
- Added `GodotClient.wait_for_node_meta(...)` and `GodotClient.wait_for_node_metadata(...)`.
- Extended locator `set_meta(...)`, `set_metadata(...)`, and `remove_meta(...)` to wait before returning the locator for chaining.
- Preserved fire-and-forget behavior through `wait=False`.
- Added `metadata_state` evidence to direct metadata write/remove results.
- Updated focused authoring metadata coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc tests.test_client.ClientTests.test_locator_richer_expectations` -> 2 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Node property write auto-waits were added and validated.

Delivered in this increment:

- Added `GodotClient.set_node_property(...)` and `GodotClient.set_node_properties(...)` direct helpers with default readback waits.
- Added `GodotClient.wait_for_node_property(...)` and `GodotClient.wait_for_node_properties(...)`.
- Extended locator `set(...)` and `set_properties(...)` to wait for readback before returning the locator for existing chain compatibility.
- Preserved fire-and-forget behavior through `wait=False`.
- Added `property_state` and `properties_state` evidence to direct client write results.
- Updated focused authoring/property coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc tests.test_client.ClientTests.test_locator_richer_expectations` -> 2 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor play/stop evidence auto-waits were added and validated.

Delivered in this increment:

- Enhanced `GodotClient.editor_play(...)` so waited results preserve the raw play RPC response while adding waited editor status fields and nested `editor_status` evidence.
- Enhanced `GodotClient.editor_stop(...)` the same way for stopped-state evidence.
- Added `interval` controls to both helpers.
- Preserved existing top-level compatibility for `playing` and `playing_scene`.
- Preserved fire-and-forget behavior through `wait=False`.
- Updated focused editor status coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_expectations_poll_status` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project configuration auto-waits were added and validated.

Delivered in this increment:

- Added `GodotClient.wait_for_project_setting(...)`, `wait_for_export_preset(...)`, `wait_for_project_main_scene(...)`, and `wait_for_project_autoload(...)`.
- Extended `project_set_setting(...)`, `project_set_export_preset(...)`, `project_set_main_scene(...)`, `project_add_autoload(...)`, and `project_remove_autoload(...)` with default readback waits.
- Preserved fire-and-forget behavior through `wait=False`.
- Added `setting`, `preset_state`, `main_scene`, and `autoload_state` evidence to project write results where applicable.
- Updated focused project authoring coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Signal connection lifecycle auto-waits were added and validated.

Delivered in this increment:

- Added `GodotClient.wait_for_signal_connection(...)` for direct connected/disconnected waits with signal, target, method, and persistence filters.
- Extended `GodotClient.signal_connect(...)` and locator `connect_signal(...)` with default waiting for the live connection to appear.
- Extended `GodotClient.signal_disconnect(...)` and locator `disconnect_signal(...)` with default waiting until the matching connection is absent.
- Preserved fire-and-forget behavior through `wait=False`.
- Added `connection_state` evidence to connect/disconnect results.
- Updated focused signal authoring coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Node script attach/detach auto-waits were added and validated.

Delivered in this increment:

- Extended `GodotClient.attach_script(...)` with default waiting for the node's `script` property to resolve to the requested script path.
- Extended `GodotClient.detach_script(...)` with default waiting until the node has no script.
- Added `GodotClient.wait_for_node_script(...)` for direct attached/detached script-state waits.
- Preserved fire-and-forget behavior through `wait=False`.
- Added `script_state` evidence to attach/detach results.
- Updated locator wrappers, focused authoring coverage, README, and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_locator_authoring_wrappers_call_rpc tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc` -> 2 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Script authoring auto-wait helper was added and validated.

Delivered in this increment:

- Added `GodotClient.wait_for_script(...)` for retryable script symbol inspection with optional `extends`, function, and source-snippet checks.
- Added `GodotClient.write_script(...)` to write GDScript source and wait for saved file/readback, editor filesystem `GDScript` index, and script symbols before returning.
- Preserved fire-and-forget behavior through `wait=False`.
- Added `script` and refreshed `editor_filesystem` evidence to script-write results; optional `open_editor=True` records `opened_script`.
- Updated fake-server script symbol extraction so focused tests reflect newly written script source.
- Updated focused editor coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor filesystem search count waits were added and validated.

Delivered in this increment:

- Extended `GodotClient.wait_for_editor_filesystem_find(...)` with optional `max_count` so searches can wait for exact or bounded result counts.
- Added `expect_filesystem(...).to_have_indexed_count(...)` for exact indexed search counts.
- Added `expect_filesystem(...).not_to_contain(...)` for negative editor filesystem search waits.
- Updated focused editor/filesystem coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Filesystem path lifecycle auto-waits were added and validated.

Delivered in this increment:

- Extended `GodotClient.fs_mkdir(...)` with default waits for directory existence, editor filesystem scan, and indexed directory metadata when available.
- Extended `GodotClient.fs_delete(...)` with default waits for missing path state, editor filesystem scan, and missing-index evidence when available.
- Added `GodotClient.wait_for_editor_filesystem_missing(...)` and `expect_filesystem(...).not_to_be_indexed(...)`.
- Preserved fire-and-forget behavior through `wait=False`.
- Added `directory`, `missing`, `editor_filesystem_scan`, and `editor_filesystem` evidence to mkdir/delete results where applicable.
- Updated focused filesystem coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_filesystem_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Filesystem write auto-waits were added and validated.

Delivered in this increment:

- Extended `GodotClient.fs_write_text(...)` with default waits for saved file existence, exact text readback, editor filesystem scan, and indexed file metadata when available.
- Extended `GodotClient.fs_write_bytes(...)` with default waits for saved file existence plus editor filesystem scan/index evidence when available.
- Preserved fire-and-forget behavior through `wait=False`.
- Added `file`, `text`, `editor_filesystem_scan`, and `editor_filesystem` evidence to write results where applicable.
- Updated focused filesystem coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_filesystem_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Resource save auto-waits were added and validated.

Delivered in this increment:

- Added `GodotClient.wait_for_resource(...)` for retryable saved-resource inspection with class and property filters.
- Extended `GodotClient.resource_save(...)` with default Playwright-style waits for saved `res://` file existence, loadable resource state, editor filesystem scan, and indexed file metadata when available.
- Preserved fire-and-forget behavior through `wait=False`.
- Added `file`, `resource`, `editor_filesystem_scan`, and `editor_filesystem` evidence to save results where applicable.
- Updated focused resource coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_resource_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Resource reimport auto-waits were added and validated.

Delivered in this increment:

- Extended `GodotClient.resource_reimport(...)` with default waiting for import metadata on common external asset types such as images, audio, fonts, and 3D models.
- Preserved fire-and-forget behavior through `wait=False`.
- Avoided false waits for native Godot resources such as `.gd`, `.tscn`, `.scn`, `.tres`, and `.res`.
- Added `imports` and `import_count` evidence to reimport results when waiting is enabled.
- Updated focused resource coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_resource_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor scene lifecycle auto-waits were added and validated.

Delivered in this increment:

- Added Playwright-style auto-waiting to `GodotClient.editor_new_scene(...)`.
- Made editor scene creation retry through Godot editor tab/root timing races and require the new edited-scene name to remain stable briefly before returning.
- Added auto-waiting to `GodotClient.editor_save_scene(...)` for edited-scene path, saved `res://` file existence, filesystem scan, and editor filesystem index entry.
- Preserved existing created-root/save result payloads while adding `editor_status`, `file`, `editor_filesystem_scan`, and `editor_filesystem` evidence where applicable.
- Added focused fake-server assertions and updated README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc` -> 1 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor filesystem index waits were added and validated.

Delivered in this increment:

- Added `GodotClient.wait_for_editor_filesystem_entry(...)` for retryable waits on Godot editor filesystem metadata after agent-authored file changes.
- Added `GodotClient.wait_for_editor_filesystem_find(...)` for retryable waits on indexed search results with `min_count`.
- Added `expect_filesystem(godot, path).to_be_indexed(...)` and routed resource-type expectations through the indexed metadata wait.
- Extended fake-server filesystem search filtering and focused editor/filesystem coverage.
- Updated README and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_helpers_call_rpc` -> 1 passed
- `python -m unittest tests.test_client.ClientTests.test_filesystem_helpers_call_rpc tests.test_client.ClientTests.test_editor_helpers_call_rpc` -> 2 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> 1 passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or `extension_api.json` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Viewport screenshot expectations were added and validated.

Delivered in this increment:

- Added `GodotClient.wait_for_screenshot(...)` for retryable viewport screenshot capture with file and dimension checks.
- Added `expect_viewport(godot).to_have_screenshot(...)` as a Playwright-style screenshot artifact assertion.
- Added focused fake-server coverage for screenshot capture, saved-file verification, minimum/exact dimensions, and failure messages.
- Updated README and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_viewport_helpers` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Signal event sequence expectations were added and validated.

Delivered in this increment:

- Added `GodotClient.wait_for_signal_sequence(...)` for ordered signal assertions over one watch or the combined captured event stream.
- Added `SignalExpect.to_have_event_sequence(...)` with optional action execution and optional clearing.
- Added signal sequence matching for signal-name strings, field dictionaries, path filters, and predicates.
- Added focused fake-server coverage for matching, watch filtering, failure handling, and clearing.
- Updated README and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_signal_event_sequence_expectations` -> 1 passed
- Final post-doc/code-format quick check repeated `py_compile` and `test_signal_event_sequence_expectations` -> passed
- `python -m unittest tests.test_client.ClientTests.test_signal_expectations_watch_and_count_events tests.test_client.ClientTests.test_client_signal_wait_helpers_watch_and_filter_events tests.test_runner.RunnerIntegrationTests.test_runner_executes_godot_test_and_writes_trace` -> 3 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 131 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Signal event expectations were added and validated.

Delivered in this increment:

- Added signal event field matching, `signal_count(...)`, and `wait_for_signal_count(...)`.
- Extended `wait_for_signal_event(...)` with field filters.
- Added `SignalExpect` plus `expect_signal(...)` with event, negative event, event-count, empty, clear, context-manager, and watcher cleanup helpers.
- Exported `expect_signal(...)` from the package and runner fixtures.
- Added focused client and runner coverage plus README/protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_client.py tests/test_runner.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_signal_expectations_watch_and_count_events tests.test_runner.RunnerIntegrationTests.test_runner_executes_godot_test_and_writes_trace` -> 2 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 130 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Runtime scene expectations were added and validated.

Delivered in this increment:

- Added `GodotClient.wait_for_scene_not(...)` for negative current-scene waits.
- Added `RuntimeSceneExpect` plus `expect_runtime_scene(godot)` with path, name, negative path/name, and info-map assertions over `scene.current`.
- Exported the new expectation helper from the package and runner fixtures without conflicting with visual `expect_scene`.
- Added focused client and runner coverage for runtime scene assertions and editor fixture injection.
- Updated README and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_client.py tests/test_runner.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_scene_navigation_helpers_call_rpc tests.test_runner.RunnerIntegrationTests.test_runner_executes_godot_test_and_writes_trace tests.test_runner.RunnerIntegrationTests.test_runner_exposes_editor_semantic_fixtures` -> 3 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 129 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Generic locator state expectations were added and validated.

Delivered in this increment:

- Added `Locator.wait_for_states(...)` and `wait_for_states_not(...)` for retryable arbitrary `node.state` maps.
- Added `expect(locator).to_have_state(...)`, `not_to_have_state(...)`, `to_match_state(...)`, `not_to_match_state(...)`, `to_be_focusable(...)`, and `to_receive_input(...)`.
- Added focused fake-server coverage and documentation.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_locator_generic_state_expectations` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 129 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Locator collection text expectations were added and validated.

Delivered in this increment:

- Added `Locator.text_contents(...)`, `wait_for_texts(...)`, and `wait_for_texts_not(...)` for retryable collection text checks.
- Added `expect(locator).to_have_texts(...)`, `to_contain_texts(...)`, and `not_to_have_texts(...)`.
- Extended fake-server text coverage for multi-match locators so repeated controls can be asserted by text sequence.
- Updated README and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_locator_collection_text_expectations` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 128 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Locator count range expectations were added and validated.

Delivered in this increment:

- Added `Locator.wait_for_count(...)` with exact, minimum, maximum, and range constraints.
- Added `expect(locator)` count assertions: `to_have_count_at_least(...)`, `to_have_count_at_most(...)`, `to_have_count_between(...)`, `to_be_empty(...)`, and `not_to_be_empty(...)`.
- Updated exact and negative count assertions to share interval-aware polling.
- Added focused fake-server coverage and documentation.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_locator_count_range_expectations` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 127 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Locator-scoped scene authoring wrappers were added and validated.

Delivered in this increment:

- Added locator-level wrappers for existing scene-authoring RPCs: `create_child(...)`, `instantiate_scene(...)`, `group_info(...)`, `groups(...)`, `add_group(...)`, `remove_group(...)`, `reparent(...)`, `move(...)`, `duplicate(...)`, `attach_script(...)`, `detach_script(...)`, and `delete()`.
- Kept the protocol unchanged; these are Python convenience APIs over existing `node.*` methods.
- Added focused fake-server coverage for RPC parameters and script/group behavior.
- Updated README and protocol docs to show locator-centric authoring workflows.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_locator_authoring_wrappers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 126 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Locator bounds and viewport geometry expectations were added and validated.

Delivered in this increment:

- Implemented locator geometry helpers on top of `node.bounds`: `center(...)`, `wait_for_bounds(...)`, `wait_for_position(...)`, `wait_for_size(...)`, `wait_for_center(...)`, and `wait_for_within_viewport(...)`.
- Added `expect(locator)` geometry assertions: `to_have_bounds(...)`, `to_have_position(...)`, `to_have_size(...)`, `to_have_center(...)`, and `to_be_within_viewport(...)`.
- Covered Control rect bounds, Node2D point bounds, tolerance matching, and viewport containment behavior in fake-server tests.
- Updated README and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_locator_geometry_helpers` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 125 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Trace event count expectations were added and validated.

Delivered in this increment:

- Implemented trace count helpers so agent flows can assert exact or minimum event/RPC counts and empty traces.
- Added API surface: `trace_count(...)`, `wait_for_trace_count(...)`, `expect_trace(...).to_have_event_count(...)`, `to_have_rpc_count(...)`, `not_to_have_rpc(...)`, and `to_be_empty(...)`.
- Extended fake-server coverage and documentation.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_trace_expectations_poll_events` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 124 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Client-level signal wait automation was added and validated.

Delivered in this increment:

- Implemented `GodotClient`-level signal waits so agent flows can listen for node events without first constructing a locator wrapper.
- Added API surface: `wait_for_signal(...)` and `wait_for_signal_event(...)`, with selector/root/signal filters, optional action callback, clearing, and automatic unwatch cleanup.
- Reused the new client helper from `Locator.wait_for_signal(...)`.
- Added fake-server coverage and documentation updates.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_locator_wait_for_signal_wraps_action tests.test_client.ClientTests.test_client_signal_wait_helpers_watch_and_filter_events` -> 2 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 124 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Engine/environment introspection expectations were added and validated.

Delivered in this increment:

- Implemented high-level engine/environment checks on top of existing `engine.info`.
- Added API surface: `engine_info(...)`, `wait_for_engine_info(...)`, `expect_engine(...).to_be_editor(...)`, `not_to_be_editor(...)`, `to_have_godot_version(...)`, `to_have_project_path(...)`, and `to_have_server_port(...)`.
- Added the runner `expect_engine` fixture and fake-server coverage.
- Updated README and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_client.py tests/test_runner.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_engine_expectations_poll_info` -> 1 passed
- `python -m unittest tests.test_runner.RunnerIntegrationTests.test_runner_exposes_editor_semantic_fixtures` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 123 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Raw filesystem waits and assertions were added and validated.

Delivered in this increment:

- Implemented direct `fs.exists`-backed waits and assertions for files, directories, missing paths, and text content.
- Added API surface: `wait_for_fs_path(...)`, `wait_for_file(...)`, `wait_for_directory(...)`, `wait_for_files(...)`, plus `expect_filesystem(...).to_be_file(...)`, `to_be_directory(...)`, `not_to_exist(...)`, `to_have_text(...)`, and `not_to_have_text(...)`.
- Extended fake-server filesystem state so file and directory waits are covered against mutable state.
- Updated README and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_filesystem_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 122 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Input action press state automation was added and validated.

Delivered in this increment:

- Implemented high-level action press/release helpers on top of existing `input.action`.
- Added API surface: `action_down(...)`, `action_up(...)`, `press_action(...)`, `wait_for_input_action(...)`, and project expectations for pressed/strength state.
- Extended server action summaries with `pressed` and `strength`.
- Added fake-server coverage and documentation updates.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_input_map_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 122 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Viewport state waits and expectations were added and validated.

Delivered in this increment:

- Implemented Playwright-style helpers around existing `viewport.info` and `viewport.set_size`.
- Added API surface: `wait_for_viewport_size(...)`, `expect_viewport(...).to_have_size(...)`, `not_to_have_size(...)`, `to_have_display_server(...)`, and `to_have_mouse_position(...)`.
- Added the runner `expect_viewport` fixture.
- Updated README and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_client.py tests/test_runner.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_viewport_helpers` -> 1 passed
- `python -m unittest tests.test_runner.RunnerIntegrationTests.test_runner_exposes_editor_semantic_fixtures` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 122 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor play session automation was added and validated.

Delivered in this increment:

- Implemented Python client helpers backed by existing `editor.play` and `editor.stop`, plus polling waits for editor play-session state.
- Added API surface: `editor_play(...)`, `editor_stop(...)`, `wait_for_editor_playing(...)`, and `wait_for_editor_stopped(...)`.
- Added fake-server play/stop simulation and extended editor expectation coverage to exercise the new helpers.
- Updated README and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_expectations_poll_status` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` -> passed
- `python -m unittest discover -s tests` -> 122 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Locator subtree snapshot automation was added and validated.

Delivered in this increment:

- Added `locator.snapshot(...)` for taking a `tree.snapshot` rooted at a locator.
- Added `locator.snapshot_nodes(...)` and `locator.snapshot_texts(...)` helpers for flattening a locator subtree.
- Added `expect(locator).to_contain_node(...)` and `not_to_contain_node(...)`.
- Added `expect(locator).to_contain_text(...)` and `not_to_contain_text(...)`.
- Added fake-server and real runtime coverage proving targeted subtree snapshots and assertions.
- Updated README and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_locator_richer_expectations` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect` -> 1 passed
- `python -m unittest discover -s tests` -> 122 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Locator capability introspection automation was added and validated.

Delivered in this increment:

- Added `locator.methods()` and `locator.signals()` helpers on top of existing `node.describe`.
- Added convenience predicates `locator.has_method(...)` and `locator.has_signal(...)`.
- Added `expect(locator).to_have_method(...)`, `not_to_have_method(...)`, `to_have_signal(...)`, and `not_to_have_signal(...)`.
- Added fake-server and real runtime coverage proving method/signal introspection on live nodes.
- Updated README and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_locator_richer_expectations` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect` -> 1 passed
- `python -m unittest discover -s tests` -> 122 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Locator expression wait automation was added and validated.

Delivered in this increment:

- Added `locator.wait_for_function(...)` for retrying node-scoped Godot expressions until truthy or a custom Python predicate matches.
- Added `locator.wait_for_expression(...)` and `locator.wait_for_expression_not(...)` for equality and negative expression polling.
- Added `expect(locator).to_match_expression(...)` and `not_to_match_expression(...)`.
- Added fake-server and real runtime coverage proving locator-scoped expression polling.
- Updated README and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_locator_richer_expectations` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect` -> 1 passed
- `python -m unittest discover -s tests` -> 122 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Locator batch method-call automation was added and validated.

Delivered in this increment:

- Added Godot RPC `node.call_all` for invoking one method across every matched node.
- Added Python locator helpers `call_all(...)` and `call_all_values(...)`.
- Returned per-node summaries, values, counts, and error counts, with `limit` and `strict` controls.
- Added fake-server and real runtime integration coverage proving batch method calls over matched locators.
- Updated README and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_locator_richer_expectations` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect` -> 1 passed
- `python -m unittest discover -s tests` -> 122 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Locator metadata automation was added and validated.

Delivered in this increment:

- Added Godot RPC methods for node metadata: `node.metadata`, `node.set_metadata`, and `node.remove_metadata`.
- Added one-action editor undo support for metadata set/remove operations.
- Added Python locator helpers: `metadata`, `get_meta`, `set_meta`, `set_metadata`, and `remove_meta`.
- Added locator expectations: `to_have_meta`, `not_to_have_meta`, `to_have_metadata`, and `not_to_have_metadata`.
- Added fake-server coverage, real runtime integration coverage, README examples, and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_locator_richer_expectations tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc` -> 2 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect` -> 1 passed
- `python -m unittest discover -s tests` -> 122 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Locator batch node property automation was added and validated.

Delivered in this increment:

- Added Godot RPC methods for batch node property reads and writes: `node.get_properties`, `node.set_properties`, and `node.set_all_properties`.
- Added one-action editor undo support for batch node property writes.
- Added Python locator helpers: `values`, `get_properties`, `all_values`, `set_properties`, and `set_all_properties`.
- Added locator expectations for batch property checks, including negative and all-match variants.
- Added fake-server coverage, real runtime integration coverage, README examples, and protocol docs.
- Synced the example addon copy.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_locator_richer_expectations tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc` -> 2 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect` -> 1 passed
- `python -m unittest discover -s tests` -> 122 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Batch Inspector property automation was added and validated.

Delivered in this increment:

- Added Inspector helpers to read a batch of properties as a name/value map.
- Added Inspector helpers to set multiple properties in one high-level call, with Resource save support.
- Added Inspector expectations for multiple properties, including negative checks.
- Added fake-server and real editor integration coverage for Node and Resource Inspector batches.
- Updated README and protocol docs.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_client.py tests/test_godot_integration.py tests/test_runner.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> 1 passed
- `python -m unittest discover -s tests` -> 122 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Camera3D locator 3D drag actions were added and validated.

Delivered in this increment:

- Added `camera_locator.drag_3d(...)` for guarded 3D drag input through a Camera3D.
- Uses the same matching filters as `click_3d(...)` before starting the drag.
- Sends a deterministic viewport mouse sequence with configurable button and steps.
- Added fake-server and real Godot coverage proving a `StaticBody3D` receives pressed, dragged, and released input events.
- Updated README and protocol docs.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_client.py tests/test_godot_integration.py tests/test_runner.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_camera3d_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect` -> 1 passed
- `python -m unittest discover -s tests` -> 122 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Camera3D locator 3D input actions were added and validated.

Delivered in this increment:

- Added Camera3D locator helpers for `hover_3d(...)` and `click_3d(...)`.
- Helpers wait for a matching 3D pick before sending viewport mouse input, so actions can be guarded by collider name, path, class, groups, metadata, or fields.
- Supplemented headless Godot mouse input dispatch for `CollisionObject3D.input_event` so 3D object interaction can be tested in CI/headless runs.
- Added fake-server and real Godot coverage proving a `StaticBody3D` receives the click input event.
- Updated README and protocol docs.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_client.py tests/test_godot_integration.py tests/test_runner.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_camera3d_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect` -> 1 passed
- `python -m unittest discover -s tests` -> 122 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Locator-driven Camera3D picking automation was added and validated.

Delivered in this increment:

- Added Camera3D locator helpers so `godot.locator("#Camera").camera3d_ray(...)` and `.pick_3d(...)` can drive screen-coordinate 3D picking.
- Added locator expectations so `expect(camera_locator).to_pick_camera_collision(...)` mirrors Playwright-style locator assertions.
- Kept low-level `godot.camera3d_*` helpers intact and reused the existing Camera3D RPC path.
- Added fake-server and real Godot coverage for locator-driven camera picking.
- Updated README and protocol docs.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_client.py tests/test_godot_integration.py tests/test_runner.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_camera3d_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect` -> 1 passed
- `python -m unittest discover -s tests` -> 122 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Camera3D screen ray and picking automation was added and validated.

Delivered in this increment:

- Added Godot RPC methods for Camera3D screen-coordinate ray projection and physics picking.
- Added Python client helpers for `camera3d.ray` and `camera3d.pick`.
- Extended `expect_physics3d(godot)` with screen-pick collision assertions and negative assertions.
- Supports matching picked collisions by collider name, path, class, groups, metadata, and fields.
- Added fake-server and real Godot coverage using a deterministic Camera3D plus `StaticBody3D` fixture.
- Updated README and protocol docs.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_client.py tests/test_godot_integration.py tests/test_runner.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_camera3d_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect` -> 1 passed
- `python -m unittest discover -s tests` -> 122 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

3D physics world query automation was added and validated.

Delivered in this increment:

- Add Godot RPC methods for 3D point and ray physics queries.
- Add Python client helpers for `physics3d.point` and `physics3d.ray`.
- Add `expect_physics3d(godot)` with point/ray collision assertions and negative assertions.
- Keep 3D collision matching aligned with 2D by collider name, path, class, groups, metadata, and fields.
- Expose the helper through the package and test runner.
- Add fake-server and real Godot coverage with a deterministic `StaticBody3D` fixture.
- Update README and protocol docs.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_client.py tests/test_godot_integration.py tests/test_runner.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_physics3d_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect` -> 1 passed
- `python -m unittest tests.test_runner.RunnerIntegrationTests.test_runner_exposes_editor_semantic_fixtures` -> 1 passed
- `python -m unittest discover -s tests` -> 121 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

2D physics world query automation was added and validated.

Delivered in this increment:

- Added Godot RPC methods for 2D point and ray physics queries.
- Added Python client helpers for `physics2d.point` and `physics2d.ray`.
- Added `expect_physics2d(godot)` with point/ray collision assertions and negative assertions.
- Supports matching collisions by collider name, path, class, groups, metadata, and fields.
- Exposes the helper from the Python package and runner fixture map.
- Added fake-server coverage and real Godot coverage with a deterministic `StaticBody2D` fixture.
- Updated README and protocol docs.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_client.py tests/test_godot_integration.py tests/test_runner.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_physics2d_helpers_call_rpc` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect` -> 1 passed
- `python -m unittest tests.test_runner.RunnerIntegrationTests.test_runner_exposes_editor_semantic_fixtures` -> 1 passed
- `python -m unittest discover -s tests` -> 120 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Negative Godot log severity expectations were added and validated.

Delivered in this increment:

- Added `expect_log(godot).not_to_have_error(...)`.
- Added `expect_log(godot).not_to_have_warning(...)`.
- Reuses the same text, kind, predicate, timeout, and interval filters as existing log expectations.
- Updated README and protocol docs.
- Added unit coverage against the live log collector, including pass and failure paths.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_log_expectations_poll_local_collector` -> 1 passed
- `python -m unittest discover -s tests` -> 119 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Screenshot pixel and region assertions were added and validated.

Delivered in this increment:

- Added `expect_scene.to_have_pixel(...)` for direct viewport pixel checks.
- Added `expect_scene.not_to_have_pixel(...)`.
- Added `expect_scene.to_have_region_color(...)` for sampled rectangular region checks.
- Supports tuple/list colors, `{"r","g","b","a"}` dictionaries, `#RRGGBB`, `#RRGGBBAA`, channel thresholds, and region match ratios.
- Reuses the existing screenshot artifact path handling and PNG RGBA decoder.
- Updated README and protocol docs.
- Added deterministic generated-PNG unit coverage.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/visual.py tests/test_visual.py` -> passed
- `python -m unittest tests.test_visual` -> 6 passed
- `python -m unittest discover -s tests` -> 119 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

AnimationPlayer semantic expectations were added and validated.

Delivered in this increment:

- Added `expect(locator).to_have_animation(...)` for animation library checks.
- Added `expect(locator).not_to_have_animation(...)`.
- Added `expect(locator).to_be_playing_animation(...)` and `not_to_be_playing_animation(...)`.
- Supports length, loop mode, track count, selected track fields, playback position, and speed scale matching.
- Updated README, protocol docs, and the example runtime test.
- Added fake-server and real Godot coverage.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_animation_helpers_call_rpc` -> 1 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect` -> 1 passed
- `python -m unittest discover -s tests` -> 117 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

InputMap concrete event expectations were added and validated.

Delivered in this increment:

- Added `expect_project(godot).to_have_input_action_event(...)`.
- Added `expect_project(godot).not_to_have_input_action_event(...)`.
- Supports matching event type, key, mouse/joypad button, joypad axis, axis value, device, modifiers, and arbitrary event fields.
- Matches both fake-server raw event specs and real Godot event summaries, including joypad button/axis aliases.
- Updated README, protocol docs, and the example runtime test.
- Added fake-server and real Godot coverage.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_input_map_helpers_call_rpc` -> 1 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect` -> 1 passed
- `python -m unittest discover -s tests` -> 117 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Static GDScript file expectations were added and validated.

Delivered in this increment:

- Added `expect_script_file(project, script_path)` for generated `.gd` file assertions.
- Covers file existence, source containment, `extends`, `class_name`, function definitions, Godot parser success, and expected diagnostics.
- Exposes the helper from the Python package and runner fixture map.
- Updated README, protocol docs, and the example editor expectation test.
- Added unit coverage with fake Godot output, runner fixture coverage, and real Godot parser/editor integration coverage.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/checks.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_checks.py tests/test_runner.py tests/test_godot_integration.py` -> passed
- `python -m unittest tests.test_checks.ScriptCheckUnitTests` -> 10 passed
- `python -m unittest tests.test_checks.ScriptCheckIntegrationTests.test_check_script_validates_real_gdscript` -> 1 passed
- `python -m unittest tests.test_runner.RunnerIntegrationTests.test_runner_exposes_editor_semantic_fixtures` -> 1 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> 1 passed
- `python -m unittest tests.test_checks` -> 11 passed
- `python -m unittest tests.test_runner` -> 41 passed
- `python -m unittest discover -s tests` -> 117 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Static saved-scene file expectations were added and validated.

Delivered in this increment:

- Added `expect_scene_file(project, scene_path)` for `.tscn`/PackedScene file assertions.
- Covers file existence, valid parse state, root node, node filters, node counts, external resources, groups, scripts, instances, and signal connections.
- Exposes the helper from the Python package and runner fixture map.
- Updated README, protocol docs, and the example editor expectation test.
- Added static parser unit coverage, runner fixture coverage, and real Godot editor integration coverage.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/scene.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_scene.py tests/test_runner.py tests/test_godot_integration.py` -> passed
- `python -m unittest tests.test_scene` -> 4 passed
- `python -m unittest tests.test_runner.RunnerIntegrationTests.test_runner_exposes_editor_semantic_fixtures` -> 1 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> 1 passed
- `python -m unittest tests.test_client` -> 24 passed
- `python -m unittest tests.test_runner` -> 41 passed
- `python -m unittest discover -s tests` -> 115 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Export preset option matching was added and validated.

Delivered in this increment:

- Extended `expect_project(godot).to_have_export_preset(...)` with preset field and option matching.
- Extended `expect_project(godot).not_to_have_export_preset(...)` with the same filters.
- Updated README and protocol docs for option checks.
- Added fake-server and real Godot editor coverage.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc` -> 1 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> 1 passed
- `python -m unittest tests.test_client` -> 24 passed
- `python -m unittest discover -s tests` -> 115 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor undo/history expectations were added and validated.

Delivered in this increment:

- Added `expect_editor(godot).to_have_undo(...)` and `not_to_have_undo(...)`.
- Added `expect_editor(godot).to_have_redo(...)` and `not_to_have_redo(...)`.
- Added `expect_editor(godot).to_match_history(...)` for `editor.history` payload checks.
- Updated README, protocol docs, and the example editor expectation test.
- Added fake-server unit coverage, runner fixture coverage, and real Godot editor integration coverage.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py tests/test_runner.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc tests.test_client.ClientTests.test_editor_expectations_poll_status` -> 2 passed
- `python -m unittest tests.test_runner.RunnerIntegrationTests.test_runner_exposes_editor_semantic_fixtures` -> 1 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> 1 passed
- `python -m unittest tests.test_client` -> 24 passed
- `python -m unittest tests.test_runner` -> 41 passed
- `python -m unittest discover -s tests` -> 115 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Export preset project expectations were added and validated.

Delivered in this increment:

- Added `expect_project(godot).to_have_export_preset(...)`.
- Added `expect_project(godot).not_to_have_export_preset(...)`.
- Covers name, platform, export path, runnable flag, and negative assertions.
- Updated README and protocol docs.
- Added fake-server unit coverage and real Godot editor integration coverage.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc` -> 1 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> 1 passed
- `python -m unittest tests.test_client` -> 24 passed
- `python -m unittest discover -s tests` -> 115 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Resource/dependency expectations were added and validated.

Delivered in this increment:

- Added `expect_resource(godot, path)` for assertions against generated Godot resources.
- Covers resource existence, class/type checks, selected properties, dependency filters, missing dependency checks, and import metadata.
- Exposes `expect_resource` from the Python package and the runner fixture map.
- Updated README and protocol docs.
- Added fake-server unit coverage, runner fixture coverage, and real Godot editor integration coverage.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_client.py tests/test_godot_integration.py tests/test_runner.py` -> passed
- `python -m unittest tests.test_client.ClientTests.test_resource_helpers_call_rpc` -> 1 passed
- `python -m unittest tests.test_runner.RunnerIntegrationTests.test_runner_exposes_editor_semantic_fixtures` -> 1 passed
- `python -m unittest tests.test_client` -> 24 passed
- `python -m unittest tests.test_runner` -> 41 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> 1 passed
- `python -m unittest discover -s tests` -> 115 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project-level expectations were added and validated.

Delivered in this increment:

- Added `expect_project(godot)` for assertions against `project.godot` and InputMap state.
- Covers main scene, autoload entries, and input actions.
- Exposes `expect_project` from the Python package and the runner fixture map.
- Uses tolerant deadzone comparisons for Godot's float round-tripping.
- Updated README and protocol docs.
- Added fake-server unit coverage, runner fixture coverage, and real Godot runtime/editor integration coverage.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/__init__.py godot_playwright/runner.py tests/test_client.py tests/test_godot_integration.py tests/test_runner.py`
- `python -m unittest tests.test_client` -> 24 passed
- `python -m unittest tests.test_runner.RunnerIntegrationTests.test_runner_exposes_editor_semantic_fixtures` -> 1 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect` -> 1 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> 1 passed
- `python -m unittest discover -s tests` -> 115 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Node group and script expectations were added and validated.

Delivered in this increment:

- Added locator expectations for Godot node group membership.
- Added locator expectations for attached node scripts.
- Supports positive and negative assertions with clear observed-state messages.
- Updated README and protocol docs with `to_have_group(...)` and `to_have_script(...)` usage.
- Added fake-server unit coverage and real Godot editor integration coverage.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py`
- `python -m unittest tests.test_client` -> 24 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> 1 passed
- `python -m unittest discover -s tests` -> 115 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Signal connection expectations were added and validated.

Delivered in this increment:

- Added locator expectations for live Godot signal connections.
- Support positive and negative assertions by signal, target, method, and persistent flag.
- Assertion messages show observed connections or the matched connection for generated scene debugging.
- Updated README and protocol docs with `to_have_signal_connection(...)` usage.
- Added fake-server unit coverage and real Godot editor integration coverage.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py`
- `python -m unittest tests.test_client` -> 24 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> 1 passed
- `python -m unittest discover -s tests` -> 115 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Generic polling expectations were added and validated.

Delivered in this increment:

- Add an `expect_poll` runner fixture for arbitrary callable polling.
- Support equality, inequality, truthy/falsy, and custom predicate assertions.
- Include clear timeout messages with the last observed value or last callable error.
- Make the fixture available to tests and hooks.
- Export `PollExpect` and `expect_poll` from the Python package.
- Updated README and protocol docs.
- Added unit coverage for passing polls, timeout error reporting, and argument validation.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py godot_playwright/__init__.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerUnitTests` -> 37 passed
- `python -m unittest tests.test_runner` -> 41 passed
- `python -m unittest discover -s tests` -> 115 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Soft assertions were added and validated.

Delivered in this increment:

- Add a `soft_expect` runner fixture for Playwright-style soft assertions.
- Tests continue after failed soft assertions and fail at the end with a combined `SoftAssertionError`.
- Soft assertion details are preserved in JSON results, diagnostics, text output, JUnit XML, and HTML reports.
- Runtime skips remain skipped even if soft assertions were recorded earlier.
- Hard assertion, RPC, and timeout failures remain the primary error while soft assertion metadata stays attached.
- Report summaries now include soft assertion failure counts.
- Exported `SoftAssertionError` from the Python package.
- Updated README and protocol docs.
- Added unit coverage for soft failure continuation, JUnit/diagnostics/report preservation, hard-failure precedence, and runtime-skip behavior.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py godot_playwright/__init__.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerUnitTests` -> 34 passed
- `python -m unittest tests.test_runner` -> 38 passed
- `python -m unittest discover -s tests` -> 112 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

JUnit XML reporting was added and validated.

Delivered in this increment:

- Added `run_tests(..., junit_xml=PATH)`.
- Added `godot-playwright test --junit-xml PATH`.
- Emits CI-friendly JUnit XML with pass/fail/skipped/interrupted outcomes.
- Includes failure tracebacks and Python stdout/stderr tails in testcase elements.
- Preserves artifact paths as testcase properties so agents can jump from CI failures to logs, traces, screenshots, diagnostics, and HTML reports.
- Text output prints the JUnit path when enabled.
- Keeps JSON and HTML as the richer native reports while adding JUnit as an integration format.
- Updated README and protocol docs.
- Added unit coverage for JUnit XML contents and CLI forwarding.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py godot_playwright/cli.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerUnitTests` -> 31 passed
- `python -m unittest tests.test_runner` -> 35 passed
- `python -m unittest discover -s tests` -> 109 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Fail-fast max failure limits were added and validated.

Delivered in this increment:

- Added `run_tests(..., max_failures=N)`.
- Added `godot-playwright test --max-failures N`.
- Stops launching additional isolated single-worker tests once the failure limit is reached.
- Marks not-run tests as `interrupted` so reports show exactly what fail-fast skipped.
- Adds interrupted counts, `INTERRUPTED` text markers, HTML summary/filter support, and stop reason metadata.
- Expected failures do not count toward `max_failures`; unexpected passes still count as failures.
- Keeps support explicit: rejects `max_failures` with `--reuse-godot` or `--workers > 1` until parallel/reuse fail-fast can be implemented without misleading results.
- Updated README and protocol docs.
- Added unit coverage for fail-fast interruption, expected-failure interaction, option validation, and CLI forwarding.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py godot_playwright/cli.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerUnitTests` -> 30 passed
- `python -m unittest tests.test_runner` -> 34 passed
- `python -m unittest discover -s tests` -> 108 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Per-test Python stdout/stderr capture was added and validated.

Delivered in this increment:

- Capture Python `stdout` and `stderr` emitted by test functions and hooks.
- Attach captured output to the specific test attempt rather than leaving it only in the terminal stream.
- Preserve output in JSON results, failed-test diagnostics, text output, and HTML reports.
- Store full output in artifact files while keeping report summaries compact.
- Keep Godot engine log capture separate from Python test output.
- Add output summaries with byte counts, line counts, tails, and artifact paths.
- Add HTML report blocks for Python stdout/stderr tails with links to full artifacts.
- Added unit coverage for passed-test output artifacts and failed-test diagnostics output.
- Updated README and protocol docs.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerUnitTests` -> 28 passed
- `python -m unittest tests.test_runner` -> 32 passed
- `python -m unittest discover -s tests` -> 106 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Configurable runner screenshots were added and validated.

Delivered in this increment:

- Added `run_tests(..., screenshots="off|only-on-failure|on")`.
- Added `godot-playwright test --screenshots ...`.
- Captures per-attempt viewport PNG artifacts after failed attempts when `only-on-failure` is enabled.
- Captures per-attempt viewport PNG artifacts for every launched attempt when `on` is enabled.
- Includes screenshot artifacts in JSON results, diagnostics, text output, and HTML reports.
- HTML reports now preview screenshot artifacts inline.
- Screenshot capture failures, including headless display limitations, are recorded as diagnostic metadata instead of replacing the original test failure.
- Default headless CI behavior remains stable because screenshots default to `off`.
- Updated README and protocol docs.
- Added unit coverage for failure screenshots, passed-attempt screenshots, screenshot capture errors, CLI forwarding, and option validation.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py godot_playwright/cli.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerUnitTests` -> 26 passed
- `python -m unittest tests.test_runner` -> 30 passed
- `python -m unittest discover -s tests` -> 104 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Per-test setup/teardown hooks were added and validated.

Delivered in this increment:

- Add Playwright-style `before_each` and `after_each` decorators for Python automation tests.
- Run hooks with the same fixtures as tests, including `godot`, `test_info`, `step`, and `attach`.
- Ensure `after_each` runs after passed, failed, and runtime-skipped tests.
- Preserve hook steps and attachments in JSON/text/HTML reports and diagnostics.
- Make `after_each` failures fail otherwise-passing tests so teardown errors are visible.
- Export `before_each` and `after_each` from the Python package.
- Document the hook API in README and protocol docs.
- Add unit coverage for hook fixture injection, failed-test teardown evidence, runtime-skip teardown, and teardown failure behavior.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py godot_playwright/__init__.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerUnitTests` -> 23 passed
- `python -m unittest tests.test_runner` -> 27 passed
- `python -m unittest discover -s tests` -> 101 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Runtime conditional skips were added and validated.

Delivered in this increment:

- Added `TestSkipped`.
- Added `test_info.skip("reason")` for tests that can only decide to skip after Godot/editor state is available.
- Runtime skips count as skipped, not failed.
- Runtime skips do not retry.
- Runtime skips preserve steps, attachments, Godot logs, trace summaries, and trace artifacts when tracing is on.
- Steps interrupted by runtime skips now report `skipped` and text output shows `STEP-SKIP`.
- Runtime skips are left as skipped even when the test also has `@expected_failure`.
- HTML reports show runtime skip reasons in a dedicated Reason block.
- Exported `TestSkipped` from the Python package.
- Updated README and protocol docs.
- Added unit coverage for runtime skip evidence, no-retry behavior, expected-failure interaction, package export, and report output.
- Added real Godot integration coverage for runtime skip artifact preservation.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py godot_playwright/__init__.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerUnitTests` -> 19 passed
- `python -m unittest tests.test_runner.RunnerIntegrationTests.test_runner_runtime_skip_with_real_godot_keeps_artifacts` -> 1 passed
- `python -m unittest discover -s tests` -> 97 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Test attachments and test info were added and validated.

Delivered in this increment:

- Added `TestInfo`.
- Added `test_info` and `attach` fixtures for Python automation tests.
- Added `test_info.output_path(...)` for per-test output files.
- Added `test_info.attach(...)` and `attach(...)` for file, text, bytes, and JSON-like body attachments.
- Attachments are copied or written into per-test artifact directories.
- Attachments are included in per-test JSON results and per-attempt retry records.
- Failed-test diagnostics include attachment metadata.
- Text reports show attachment lines.
- HTML reports include an Attachments table with links, content type, byte size, and path.
- Exported `TestInfo` from the Python package.
- Updated README and protocol docs.
- Added unit coverage for file attachments, body attachments, HTML/text output, package export, and failed-test diagnostics output.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py godot_playwright/__init__.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerUnitTests` -> 15 passed
- `python -m unittest tests.test_runner` -> 18 passed
- `python -m unittest discover -s tests` -> 92 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Structured test steps were added and validated.

Delivered in this increment:

- Added a Playwright-style `step` fixture for Python automation tests.
- Tests can write `with step("open inventory"):` or `step("assert result", lambda: ...)`.
- Step records include title, status, duration, nesting depth, and step-local failure details.
- Step records are included in per-test JSON results and per-attempt retry records.
- Failed-test diagnostics include the captured step timeline.
- Text reports show `STEP` and `STEP-FAIL` lines.
- HTML reports include a Steps table for each test result.
- Updated README and protocol docs.
- Added unit coverage for passed steps, nested steps, callback-style steps, failed steps, HTML output, text output, and diagnostics output.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerUnitTests` -> 13 passed
- `python -m unittest tests.test_runner` -> 16 passed
- `python -m unittest discover -s tests` -> 90 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Parallel test workers were added and validated.

Delivered in this increment:

- Added `run_tests(..., workers=N)`.
- Added `godot-playwright test --workers N`.
- Parallel workers run isolated per-test Godot processes concurrently.
- The runner installs the addon once before parallel worker launch to avoid concurrent addon-copy races.
- Parallel results are merged back into deterministic selected-test order.
- Skips, retries, expected failures, per-test logs, artifacts, JSON output, text output, and HTML report metadata are preserved.
- `reuse_godot=True` remains incompatible with multiple workers because it intentionally uses one shared Godot process.
- HTML reports include the configured worker count.
- Updated README and protocol docs.
- Added unit coverage for worker option validation, CLI forwarding, and skipped tests in worker mode.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py godot_playwright/cli.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerUnitTests` -> 11 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --workers 2 --trace off` -> 6 passed, report recorded `workers: 2`
- `python -m unittest tests.test_runner` -> 14 passed
- `python -m unittest discover -s tests` -> 88 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Trace-to-test code generation was added and validated.

Delivered in this increment:

- Added `godot_playwright.codegen`.
- Added `TraceCodegenError`.
- Added `generate_test_from_trace()`, `normalize_trace_events()`, and `load_trace_events()`.
- Added `godot-playwright codegen-trace TRACE_JSON`.
- Supports writing generated tests to stdout or `--output`.
- Converts common trace actions into editable Python test code: clicks, focus, fills, checks, selection controls, dialog accept/dismiss, scene changes, runtime/node evaluation, keyboard/mouse/touch/joypad input, viewport size/screenshot, and selected filesystem/resource actions.
- Preserves unsupported trace events as comments instead of silently dropping trace context.
- Exports the codegen API from the Python package.
- Updated README and protocol docs.
- Added unit coverage for event translation, invalid trace shapes, trace loading, and CLI output-file generation.

Validation completed for this increment:

- `python -m py_compile godot_playwright/codegen.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_codegen.py`
- `python -m unittest tests.test_codegen` -> 4 passed
- `python -m godot_playwright.cli codegen-trace godot-playwright-report/test_counter-test_counter_button-trace.json --test-name replay_counter --output <temp>/test_replay_counter.py`
- `python -m py_compile <temp>/test_replay_counter.py`
- `python -m unittest discover -s tests` -> 86 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

## Previous Completed Increment

Test annotations were added and validated.

Delivered in this increment:

- Added Python decorators `@skip("reason")`, `@expected_failure("reason")`, and alias `@xfail("reason")`.
- Added `UnexpectedPassError`.
- Skipped tests are recorded without launching Godot for that test.
- Expected-failure tests count as green expected-failed outcomes when they fail.
- Expected-failure tests that pass are reported as unexpected-pass failures.
- Reports now account for skipped, expected-failed, and unexpected-passed tests.
- Text reports show `SKIP`, `EXPECTED-FAIL`, and `UNEXPECTED-PASS` markers.
- HTML reports show summary cards, filters, status pills, and annotation details for the new outcomes.
- Exported the annotation decorators and `UnexpectedPassError` from the Python package.
- Updated README and protocol docs.
- Added unit coverage for skip/no-launch, expected-failure, and unexpected-pass behavior.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerUnitTests` -> 9 passed
- `python -m unittest tests.test_runner` -> 12 passed
- `python -m unittest discover -s tests` -> 82 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

Status:

- Broad objective remains active and incomplete.
- This increment is complete.

## Previous Completed Increment

Per-test timeout enforcement was added and validated.

Delivered in this increment:

- Added `TestTimeoutError`.
- Added `run_tests(..., test_timeout=N)` for per-test-attempt timeout enforcement.
- Added `godot-playwright test --test-timeout N`.
- Kept Godot launch timeout and test body timeout separate.
- Timed-out tests follow the normal failure path and keep diagnostics, Godot logs, traces, and failure scene snapshots.
- Reports include the configured `test_timeout`.
- HTML reports show the test timeout in summary cards.
- Exported `TestTimeoutError` from the Python package.
- Updated README and protocol docs.
- Added unit coverage proving a stuck test is interrupted quickly and still writes diagnostics/artifacts.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py godot_playwright/cli.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerUnitTests` -> 6 passed
- `python -m py_compile godot_playwright/runner.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_runner.py`
- `python -m unittest tests.test_runner` -> 9 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --grep counter --test-timeout 30 --trace off` -> 1 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest discover -s tests` -> 79 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

Status: broad objective remains active and incomplete; this increment is complete.

## Previous Completed Increment

Test retries and flaky reporting was added and validated.

Delivered in this increment:

- Added `run_tests(..., retries=N)` support.
- Added `godot-playwright test --retries N`.
- Failed tests retry up to the configured limit.
- Fail-then-pass tests are counted as passed and marked flaky.
- Reports now include retry count, max retries, attempt count, outcome, and flaky status.
- JSON reports keep per-attempt results and artifacts when retries occur.
- HTML reports include flaky summary count, flaky filtering, and an attempts table with per-attempt artifact links.
- Per-attempt artifact ids prevent retry logs, traces, diagnostics, and failure scene snapshots from overwriting each other.
- Updated README and protocol docs.
- Added unit coverage for fail-then-pass retry behavior, flaky marking, per-attempt diagnostics/artifacts, and CLI argument forwarding.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py godot_playwright/cli.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerUnitTests` -> 5 passed
- `python -m py_compile godot_playwright/runner.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_runner.py`
- `python -m unittest tests.test_runner` -> 8 passed
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --grep counter --retries 1 --trace off` -> 1 passed, 0 flaky
- `python -m unittest discover -s tests` -> 78 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

Status: broad objective remains active and incomplete; this increment is complete.

## Previous Completed Increment

Test runner selection and sharding was added and validated.

Delivered in this increment:

- Added `select_tests()` for deterministic test selection over discovered Python automation tests.
- Added regex `grep` selection, inverted grep selection, and deterministic `current/total` sharding.
- Added `run_tests(..., list_only=True)` so agents can plan selected tests without launching Godot.
- Added report metadata for discovered test count, selected count, grep state, invert state, and shard state.
- Added listed-test entries to JSON and HTML reports.
- Added `godot-playwright test --list`, `--grep`, `--grep-invert`, and `--shard current/total`.
- Exported `select_tests` from the Python package.
- Updated README and protocol docs.
- Added unit coverage for grep, inverted grep, sharding validation, list-only reports, and CLI argument forwarding.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py godot_playwright/cli.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerUnitTests` -> 4 passed
- `python -m py_compile godot_playwright/runner.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_runner.py`
- `python -m unittest tests.test_runner` -> 7 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --list --grep counter` -> 1 selected / 6 discovered, no Godot launch
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --list --grep 'counter|navigation' --shard 2/2 --json` -> 1 selected shard entry
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --grep counter --trace off` -> 1 passed
- `python -m unittest discover -s tests` -> 77 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

Status: broad objective remains active and incomplete; this increment is complete.

## Previous Completed Increment

Structured screenshot diffing was added and validated.

Delivered in this increment:

- Added stdlib PNG decode/encode support for 8-bit non-interlaced PNG screenshots.
- Added `compare_screenshots(expected, actual, ...)` with exact pixel comparison, `threshold`, `max_different_pixels`, and `max_diff_ratio` tolerances.
- Updated `expect_scene.to_match_screenshot()` to compare pixels instead of only hashes.
- Screenshot mismatches now write actual PNG, magenta-highlighted diff PNG, and JSON metric reports.
- Failure reports include dimensions, differing pixel count, diff ratio, max/mean channel deltas, hashes, allowed differences, and artifact paths.
- `SnapshotAssertionError` now carries the structured report on `.report`.
- Exported `compare_screenshots` from the Python package.
- Added unit coverage for screenshot mismatch diff artifacts and tolerance behavior.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/visual.py tests/test_visual.py`
- `python -m unittest tests.test_visual` -> 4 passed
- `python -m py_compile godot_playwright/visual.py godot_playwright/__init__.py tests/test_visual.py`
- `python -m unittest tests.test_visual tests.test_runner` -> 8 passed
- Screenshot comparison smoke check -> mismatch reported with 1 differing pixel and diff PNG generated
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest discover -s tests` -> 74 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

Status: broad objective remains active and incomplete; this increment is complete.

## Previous Completed Increment

Static project selector index was added and validated.

Delivered in this increment:

- Added `godot_playwright.locator_index.find_project_nodes`.
- Added `ProjectNodeQueryError` with structured report payloads for `check=True` failures.
- Added `godot-playwright find-nodes` CLI command with text and JSON output.
- Queries text `.tscn` scenes by selector, node name, Godot class/type, inferred role, accessible name, metadata test id, text, placeholder, tooltip, path, and property values.
- Returns project path, query, scene/node/match counts, diagnostics, scene path, node path, inferred role, accessible names, test id, metadata, line, and property count for each match.
- Keeps node properties internal for matching even when public output omits `properties`.
- Supports opt-in `--include-properties` output for agent debugging.
- Exported `find_project_nodes` and `ProjectNodeQueryError` from the Python package.
- Added unit coverage for static role/name/text/test-id/property matching, hidden-property matching, include-properties output, and CLI invocation.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/locator_index.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_locator_index.py`
- `python -m unittest tests.test_locator_index` -> 3 passed
- `python -m unittest tests.test_scene tests.test_inventory tests.test_validate tests.test_locator_index` -> 13 passed
- `python -m godot_playwright.cli find-nodes examples/basic --role button --test-id counter-button --json` -> 1 match
- `python -m godot_playwright.cli find-nodes examples/basic --selector 'text*=Scene'` -> 2 matches
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest discover -s tests` -> 72 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli find-nodes examples/basic --test-id counter-button` -> 1 match
- `python -m godot_playwright.cli find-nodes examples/basic --role button --role-name 'Clicked 0' --json` -> 1 match
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

Status: broad objective remains active and incomplete; this increment is complete.

## Previous Completed Increment

Offline project inventory inspection was added and validated.

Delivered in this increment:

- Added `godot_playwright.inventory.inspect_project`.
- Added `ProjectInventoryError` with structured report payloads for `check=True` failures.
- Added `godot-playwright inspect-project` CLI command with text and JSON output.
- Parses `project.godot` into sections, raw entries, parsed values, and line numbers.
- Parses `export_presets.cfg` into preset summaries and option maps.
- Reports configured project name, main scene, autoloads, export presets, discovered scenes/scripts/resources/assets, diagnostics, and duration.
- Detects missing `project.godot`, missing configured main scene, missing autoload targets, and unparsed config lines.
- Supports exclude globs for file inventory and `--no-settings` for compact reports.
- Exported `inspect_project` and `ProjectInventoryError` from the Python package.
- Added unit coverage for settings parsing, autoload/export/file summaries, missing project diagnostics, and CLI invocation.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/inventory.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_inventory.py`
- `python -m unittest tests.test_inventory` -> 3 passed
- `python -m py_compile godot_playwright/client.py godot_playwright/checks.py godot_playwright/cli.py godot_playwright/__init__.py godot_playwright/inventory.py godot_playwright/probe.py godot_playwright/scene.py godot_playwright/validate.py godot_playwright/runner.py tests/test_inventory.py tests/test_scene.py tests/test_validate.py tests/test_client.py tests/test_checks.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_inventory tests.test_scene tests.test_validate tests.test_checks tests.test_probe` -> 27 passed
- `python -m unittest discover -s tests` -> 69 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli inspect-project examples/basic --exclude 'addons/**'` -> project inventory passed
- `python -m godot_playwright.cli inspect-project examples/basic --exclude 'addons/**' --json` -> project inventory JSON passed
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project-level validation pipeline was added and validated.

Delivered in this increment:

- Added `godot_playwright.validate.validate_project`.
- Added `ProjectValidationError` with structured report payloads for `check=True` failures.
- Added `godot-playwright validate` CLI command with text and JSON output.
- Validation aggregates script parser checks, resource dependency checks, static scene inspection, and runtime scene probes.
- Added `inspect_project_scenes` for project-wide static `.tscn` inspection with discovery and exclude globs.
- Validation reports preserve each underlying check report under `checks`, while also exposing top-level pass/fail counts, failed check names, merged diagnostics, artifacts dir, and duration.
- CLI supports selected paths, exclude globs, Godot executable/headless/timeout/frame controls, extra Godot args, runtime error allowance, and skip flags for individual validation phases.
- Exported `validate_project`, `ProjectValidationError`, and `inspect_project_scenes` from the Python package.
- Added unit coverage for project-wide scene inspection, validation aggregation, skip flags, and CLI invocation.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/scene.py godot_playwright/validate.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_scene.py tests/test_validate.py`
- `python -m unittest tests.test_scene tests.test_validate` -> 7 passed
- `python -m py_compile godot_playwright/client.py godot_playwright/checks.py godot_playwright/cli.py godot_playwright/__init__.py godot_playwright/probe.py godot_playwright/scene.py godot_playwright/validate.py godot_playwright/runner.py godot_playwright/visual.py tests/test_scene.py tests/test_validate.py tests/test_client.py tests/test_checks.py tests/test_probe.py tests/test_runner.py tests/test_visual.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_scene tests.test_validate tests.test_checks tests.test_probe` -> 24 passed
- `python -m unittest discover -s tests` -> 66 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli validate examples/basic --exclude 'addons/**' --frames 3 --artifacts-dir godot-playwright-report` -> 4/4 checks passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Offline scene structure inspection was added and validated.

Delivered in this increment:

- Added `godot_playwright.scene.inspect_scene`.
- Added `SceneInspectError` with structured report payloads for `check=True` failures.
- Added `godot-playwright inspect-scene` CLI command with text and JSON output.
- Parses text `.tscn` headers, external resources, sub-resources, node sections, parent/child relationships, instance references, connections, and common property values.
- Builds a structured scene tree plus a flat node list with scene paths, parent paths, line numbers, property counts, and resource references.
- Reports missing scene files, unreadable text scenes, orphan nodes, missing roots, and multiple roots as diagnostics.
- Exported `inspect_scene` and `SceneInspectError` from the Python package.
- Added unit coverage for parsing real scene constructs, error reporting, and CLI invocation.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/scene.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_scene.py`
- `python -m unittest tests.test_scene` -> 3 passed
- `python -m godot_playwright.cli inspect-scene examples/basic res://scenes/main.tscn` -> parsed 16 nodes, 2 external resources, 0 diagnostics
- `python -m godot_playwright.cli inspect-scene examples/basic res://scenes/secondary.tscn --json` -> parsed 3 nodes, 1 external resource, 0 diagnostics
- `python -m py_compile godot_playwright/client.py godot_playwright/checks.py godot_playwright/cli.py godot_playwright/__init__.py godot_playwright/scene.py godot_playwright/runner.py godot_playwright/visual.py tests/test_scene.py tests/test_client.py tests/test_checks.py tests/test_runner.py tests/test_visual.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_scene tests.test_visual tests.test_runner` -> 9 passed
- `python -m unittest discover -s tests` -> 62 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli inspect-scene examples/basic res://scenes/main.tscn` -> parsed 16 nodes
- `python -m godot_playwright.cli inspect-scene examples/basic res://scenes/secondary.tscn --json` -> parsed 3 nodes
- `python -m godot_playwright.cli check-resources examples/basic res://scenes --exclude 'addons/**'` -> 2/2 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed
- `python -m godot_playwright.cli probe-scenes examples/basic res://scenes --frames 3 --artifacts-dir godot-playwright-report` -> 2/2 scenes passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Resource dependency inspection and checking was added and validated.

Delivered in this increment:

- Added addon RPC: `resource.dependencies`.
- Added Python helper: `resource_dependencies(path)`.
- Added Godot-side dependency summaries with raw dependency strings, extracted `res://` paths, UID/type metadata, existence flags, missing list, and counts.
- Added offline project resource dependency checks: `check_resource_dependencies` and `check_project_resources`.
- Added `ResourceCheckError` with structured report payloads for `check=True` failures.
- Added `godot-playwright check-resources` CLI command.
- Text resource discovery scans `.tscn` and `.tres`, supports selected paths and exclude globs, ignores generated `.godot` and `__pycache__`, and detects missing external resource paths before runtime/export.
- Added fake-server unit coverage, resource checker unit coverage, CLI coverage, and real Godot editor integration coverage for live dependency inspection.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/checks.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_client.py tests/test_checks.py tests/test_godot_integration.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_checks.ScriptCheckUnitTests.test_check_resource_dependencies_reports_missing_ext_resources tests.test_checks.ScriptCheckUnitTests.test_check_project_resources_discovers_excludes_and_can_raise tests.test_checks.ScriptCheckUnitTests.test_cli_check_resources_invokes_runner` -> 3 passed
- `python -m unittest tests.test_client.ClientTests.test_resource_helpers_call_rpc` -> 1 passed
- `python -m unittest tests.test_checks` -> 9 passed
- `python -m unittest tests.test_client` -> 24 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` -> passed on rerun
- `python -m unittest discover -s tests` -> 59 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli check-resources examples/basic res://scenes --exclude 'addons/**'` -> 2/2 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed
- `python -m godot_playwright.cli probe-scenes examples/basic res://scenes --frames 3 --artifacts-dir godot-playwright-report` -> 2/2 scenes passed

Observed during validation:

- One initial run of `tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene` failed before reaching the new dependency assertion because the editor still reported the previous scene name during startup settling; an immediate rerun and the full suite both passed.

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor undo/redo automation was added and validated.

Delivered in this increment:

- Added addon RPCs: `editor.history`, `editor.undo`, and `editor.redo`.
- Added Python helpers: `editor_history`, `editor_undo`, and `editor_redo`.
- `node.create` now records an editor undo action by default in editor mode.
- `node.set_property` now records an editor undo action by default in editor mode.
- Added `undo=false` and `undo_action` controls for direct edits and custom history labels.
- Preserved non-editor runtime behavior by falling back to direct mutation outside editor mode.
- Added fake-server unit coverage for helper calls, undoable property edits, redo, and direct no-undo node creation.
- Added real Godot integration coverage proving editor undo removes an agent-created node, redo restores it, undo reverts an agent property edit, and redo reapplies it.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene`
- `python -m py_compile godot_playwright/client.py godot_playwright/runner.py godot_playwright/__init__.py tests/test_client.py tests/test_godot_integration.py tests/test_probe.py`
- `python -m unittest discover -s tests` -> 56 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed
- `python -m godot_playwright.cli probe-scenes examples/basic res://scenes --frames 3 --artifacts-dir godot-playwright-report` -> 2/2 scenes passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project-wide scene runtime probing was added and validated.

Delivered in this increment:

- Added `godot_playwright.probe.probe_project_scenes`.
- Added `godot-playwright probe-scenes` CLI command.
- Discovers `.tscn` and `.scn` scenes from a whole project, selected directories, or selected scene files.
- Supports exclude globs, including `res://` paths and project-relative patterns.
- Ignores generated `.godot` and `__pycache__` directories during scene discovery.
- Reuses the existing single-scene `probe_project()` primitive for each scene, keeping command logging and diagnostic extraction consistent.
- Aggregates per-scene pass/fail counts, log paths, duration, and warning/error diagnostics into one structured report.
- Added `USER WARNING` recognition to Godot output summaries.
- Added unit coverage for discovery, aggregation, CLI invocation, and diagnostic parsing.
- Added real Godot integration coverage for project-wide scene probing with a generated failing scene.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/probe.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_probe.py`
- `python -m unittest tests.test_probe` -> 8 passed
- `python -m py_compile godot_playwright/probe.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_probe.py tests/test_client.py tests/test_runner.py tests/test_godot_integration.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest discover -s tests` -> 56 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli probe-scenes examples/basic res://scenes --frames 3 --artifacts-dir godot-playwright-report` -> 2/2 scenes passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Live Godot log observation was added and validated.

Delivered in this increment:

- Added a Python-side Godot stdout/stderr collector attached by the `Godot` launcher.
- Added `Godot(..., capture_logs=True, log_max_events=...)`; capture is enabled by default.
- Added live log helpers on `GodotClient`: `log_events`, `wait_for_log`, `log_text`, and `log_clear`.
- Added `LogExpect` and `expect_log`, including `to_have_message`, `to_have_error`, `to_have_warning`, and negative assertions.
- Added `expect_log` as a CLI runner fixture.
- Preserved the runner's existing per-test Godot log files by teeing captured process output to the configured `stdout` target.
- Added live log events to failure diagnostics collected by the runner.
- Added example coverage in `examples/basic/tests/test_logs.py`.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/runner.py godot_playwright/__init__.py tests/test_client.py tests/test_godot_integration.py tests/test_runner.py`
- `python -m unittest tests.test_client.ClientTests.test_log_expectations_poll_local_collector`
- `python -m unittest tests.test_client` -> 24 passed
- `python -m unittest tests.test_runner.RunnerIntegrationTests.test_runner_executes_godot_test_and_writes_trace`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest discover -s tests` -> 53 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m py_compile examples/basic/tests/test_logs.py`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 6 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed
- `python -m godot_playwright.cli probe examples/basic --scene res://scenes/main.tscn --frames 3 --artifacts-dir godot-playwright-report` -> passed with 0 errors and 0 warnings

Observed compatibility detail:

- On Godot 4.6.2 Arch Linux, `push_error()` from a runtime expression reports kind `ERROR` rather than `USER ERROR`; the API treats both as severity `error`.

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Runtime launch probing was added and validated.

Delivered in this increment:

- Added `godot_playwright.probe.probe_project`.
- Added `ProbeError` with structured report payloads for `check=True` failures.
- Added `godot-playwright probe` CLI command.
- Runs a Godot project or specific runtime scene with `--quit-after`.
- Captures stdout/stderr into a stable log artifact.
- Extracts structured error and warning diagnostics from Godot output, including paths and line numbers when Godot reports them.
- Supports headless launch, custom frame count, timeouts, extra Godot args, explicit log paths, and `allow_errors`.
- Added unit coverage for clean launches, logged errors, CLI invocation, and diagnostic parsing.
- Added real Godot integration coverage for a clean generated project and a scene script that calls `push_error`.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/probe.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_probe.py`
- `python -m unittest tests.test_probe` -> 5 passed
- `python -m py_compile godot_playwright/probe.py godot_playwright/checks.py godot_playwright/export.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_probe.py tests/test_checks.py tests/test_export.py tests/test_client.py tests/test_godot_integration.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest discover -s tests` -> 52 passed
- `python -m godot_playwright.cli probe examples/basic --scene res://scenes/main.tscn --frames 3 --artifacts-dir godot-playwright-report` -> passed with 0 errors and 0 warnings
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Project-wide GDScript checking was added and validated.

Delivered in this increment:

- Added `godot_playwright.checks.check_project_scripts`.
- Added `godot-playwright check-scripts` CLI command.
- Discovers `.gd` files under a project, selected folders, or selected files.
- Aggregates per-script Godot parser reports into project-level passed/failed counts and diagnostics.
- Supports exclude globs, including `res://` paths and project-relative patterns.
- Ignores generated `.godot` and `__pycache__` directories during discovery.
- Added unit coverage for discovery, exclude handling, aggregation, and CLI invocation.
- Extended real Godot integration coverage to validate a mixed valid/invalid script set.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/checks.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_checks.py tests/test_export.py tests/test_client.py tests/test_godot_integration.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_checks` -> 6 passed
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene`
- `python -m unittest discover -s tests` -> 47 passed
- `python -m godot_playwright.cli check-scripts examples/basic res://scripts --artifacts-dir godot-playwright-report` -> 2/2 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Stability adjustment in this increment:

- Relaxed one real editor integration wait from 2 seconds to 5 seconds because full-suite runs on Godot 4.6.2 occasionally reported the previous edited scene name before the editor status had settled.

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Structured GDScript syntax checking was added and validated.

Delivered in this increment:

- Added `godot_playwright.checks.check_script`.
- Added `ScriptCheckError` with structured report payloads for `check=True` failures.
- Added `godot-playwright check-script` CLI command.
- Uses Godot's real `--check-only --script` parser.
- Parses `SCRIPT ERROR`, `ERROR`, and `WARNING` diagnostics, including Godot source/path/line locations when present.
- Captures command, exit code, timeout state, duration, diagnostics, log path, and stdout tail.
- Added unit coverage for success, parsed failures, and CLI invocation.
- Added real Godot integration coverage for both valid and invalid generated GDScript.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/checks.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_checks.py tests/test_export.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_checks` -> 4 passed
- `python -m unittest discover -s tests` -> 45 passed
- `python -m godot_playwright.cli check-script examples/basic res://scripts/main.gd --artifacts-dir godot-playwright-report`
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Structured export execution was added and validated.

Delivered in this increment:

- Added `godot_playwright.export.export_project`.
- Added `ExportError` with structured report payloads for `check=True` failures.
- Added `godot-playwright export` CLI command.
- Supports `release`, `debug`, `pack`, and `patch` export modes.
- Captures command, exit code, timeout state, duration, output artifact existence/size, log path, and stdout tail.
- Creates output/log parent directories by default.
- Added unit coverage for successful export reports, structured failures, and CLI invocation.
- Added a real Godot failure-path probe that verifies logs and report structure when a preset is missing.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py godot_playwright/export.py godot_playwright/cli.py godot_playwright/__init__.py tests/test_client.py tests/test_godot_integration.py tests/test_export.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_export` -> 4 passed
- `python -m unittest discover -s tests` -> 41 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Export preset automation was added and validated.

Delivered in this increment:

- Added addon RPCs: `project.export_presets` and `project.set_export_preset`.
- Added Python helpers: `project_export_presets` and `project_set_export_preset`.
- Parsed and persisted Godot `res://export_presets.cfg` through `ConfigFile`.
- Supported common preset fields plus arbitrary extra preset fields and option keys.
- Added fake-server unit coverage for listing, creating, and updating presets.
- Added real editor integration coverage that creates and updates a Linux export preset, then verifies the saved `export_presets.cfg`.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene`
- `python -m unittest discover -s tests` -> 37 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Import metadata inspection was added and validated.

Delivered in this increment:

- Added addon RPC `resource.import_metadata`.
- Added Python helper `resource_import_metadata`.
- Added Python polling helper `wait_for_import`, matching the existing Playwright-like wait style.
- Parsed Godot `.import` files with `ConfigFile`, exposing `remap`, `deps`, `params`, `sections`, importer, imported resource type, source file, destination files, generated file summaries, and readiness flags.
- Added fake-server unit coverage for import metadata and import waiting.
- Added real editor integration coverage against a generated PNG imported by Godot.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_client.ClientTests.test_resource_helpers_call_rpc`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene`
- `python -m unittest discover -s tests` -> 37 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Previous Completed Increment

Editor binary asset and import workflow support was added and validated.

Delivered in this increment:

- Added addon RPCs: `fs.read_bytes` and `fs.write_bytes`.
- Added Python helpers: `fs_read_bytes` and `fs_write_bytes`, exposing normal `bytes` while using base64 on the JSON-RPC wire.
- Added fake-server unit coverage for binary file round trips.
- Added real editor integration coverage that writes a generated PNG to `res://assets/generated_pixel.png`, reads it back byte-for-byte, triggers import, and loads it as a texture resource.
- Fixed `resource.reimport` so the single-path Python helper works against the real server.
- Improved `resource.reimport(force=True)` for first-time generated assets by scanning when no `.import` metadata exists yet.
- Updated README and protocol docs.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_client.ClientTests.test_filesystem_helpers_call_rpc`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene`
- `python -m unittest discover -s tests` -> 37 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, `__pycache__`, or `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Completed Capabilities

- Runtime and editor launch through the Python `Godot` context manager.
- JSON-RPC addon server installable into Godot projects.
- Locator model for Godot nodes, including selectors by name, type/class, role, text, placeholder, tooltip, test id, metadata, properties, boolean composition, filters, and groups.
- Assertions and waits for node existence, visibility, enabled/editable state, text, properties, values, selection, editor state, scripts, filesystem entries, inspector properties, live logs, and traces.
- Runtime input automation for mouse, keyboard, text input, touch, joypad, menus, dialogs, item lists, tree controls, tabs, checkboxes, sliders, and option buttons.
- Runtime frame and clock helpers: process frames, physics frames, idle waits, timeouts, expression evaluation, and `wait_for_function`.
- Viewport information, viewport resize, and screenshot support when running with a visible window.
- InputMap automation for listing, describing, configuring, binding, and erasing actions.
- Filesystem, binary asset, resource/import metadata, project setting, export preset, structured export execution, single-script and project-wide GDScript checking, runtime launch probing, project-wide scene runtime probing, main scene, and autoload automation.
- Editor scene authoring: create nodes, instantiate packed scenes, reparent, reorder, duplicate, delete, attach/detach scripts, inspect editor UI, select nodes, inspect resources, open scripts, scan/select filesystem entries, save/open/create scenes, and verify undo/redo history for generated edits.
- Live Godot stdout/stderr observation, trace capture, and HTML reports for CLI test runs.
- Signal event watching for tests (`signal.watch`, `signal.events`, locator `wait_for_signal`).

## Recent Completed Increment

Node group automation was added and validated.

- Added RPCs: `node.groups`, `node.add_group`, `node.remove_group`.
- Added Python helpers: `node_groups`, `add_node_group`, `remove_node_group`.
- Added locator helpers: `get_by_group`, `editor_get_by_group`, and scoped locator group lookup.
- Persistent editor groups are saved into `.tscn` scenes by default.
- Real editor integration verifies persistent groups save and non-persistent groups are removed before save.

Validation completed for that increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene`
- `python -m unittest discover -s tests` -> 36 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after that increment was clean: no generated `.uid`, `.godot`, or `__pycache__`, no `.codex_*` files, no lingering Godot processes, and the example addon copy matched the source addon.

## Previous Completed Increment

Signal connection authoring was added and validated.

Delivered in this increment:

- Inspect existing signal connections on a node.
- Connect a source node signal to a target node method using Godot's real connection API.
- Persist editor-scene signal connections by default so saved `.tscn` files contain the connection.
- Disconnect previously authored connections.
- Provide Python client helpers and locator wrappers.
- Validate both live callback behavior and saved scene persistence in real Godot.

- Added addon dispatch entries for `signal.connections`, `signal.connect`, and `signal.disconnect`.
- Added server implementations for connection inspection, connect, disconnect, connection summaries, persistent/deferred/one-shot/reference-counted flags, bound arguments, and target method validation.
- Added Python client helpers: `signal_connections`, `signal_connect`, `signal_disconnect`.
- Added locator wrappers: `signal_connections`, `connect_signal`, `disconnect_signal`.
- Added fake-server unit coverage for inspecting, connecting, duplicate detection, and disconnecting signal connections.
- Added real editor integration coverage that creates a `SignalButton` and `SignalReceiver`, attaches a generated `@tool` receiver script, connects `pressed`, emits the signal, verifies the callback updates metadata, saves the scene, and checks the saved `.tscn`.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene`
- README and protocol docs were updated for signal connection authoring.
- `python -m unittest discover -s tests` -> 36 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment was clean: no generated `.uid`, `.godot`, or `__pycache__`, no `.codex_*` files, no lingering Godot processes, and the example addon copy matched the source addon.

## Previous Completed Increment

Node subtree scene extraction/saving was added and validated.

Delivered in this increment:

- Save an authored node subtree as a standalone `.tscn` or `.scn` `PackedScene`.
- Preserve the current edited scene by restoring original node owners after packing.
- Expose the workflow through Python client and locator helpers.
- Validate with a real editor-created branch containing child nodes, an instantiated subscene, a script, and a signal connection.

- Added addon RPC `node.save_as_scene`.
- Added Python helper `save_node_as_scene`.
- Added locator wrapper `locator.save_as_scene(...)`.
- Added fake-server unit coverage.
- Added real editor integration coverage for saving `GeneratedPanel` to `res://scenes/generated_panel.tscn` and checking the saved file contains the expected subtree contents.
- README and protocol docs were updated for the new workflow.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_client.ClientTests.test_editor_authoring_helpers_call_rpc`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_editor_can_create_modify_and_save_scene`
- `python -m unittest discover -s tests` -> 36 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment was clean: no generated `.uid`, `.godot`, or `__pycache__`, no `.codex_*` files, no lingering Godot processes, and the example addon copy matched the source addon.

## Previous Completed Increment

AnimationPlayer automation was added and validated.

Delivered in this increment:

- Inspect `AnimationPlayer` animations, current/assigned animation, position, length, playback state, and track metadata.
- Control animations through play, stop, pause, seek, and deterministic advance operations.
- Expose Python client helpers and locator wrappers.
- Validate against a real runtime `AnimationPlayer` whose value track changes a node property.

- Added addon RPCs: `animation.describe`, `animation.play`, `animation.stop`, `animation.pause`, `animation.seek`, and `animation.advance`.
- Added Python helpers: `animation_describe`, `animation_play`, `animation_stop`, `animation_pause`, `animation_seek`, and `animation_advance`.
- Added locator wrappers: `animation_describe`, `play_animation`, `stop_animation`, `pause_animation`, `seek_animation`, and `advance_animation`.
- Added fake-server unit coverage.
- Added real runtime integration coverage with an `AnimationPlayer` driving `AnimatedLabel.modulate.a`.
- README and protocol docs were updated for animation control.

Validation completed for this increment:

- `python -m py_compile godot_playwright/client.py tests/test_client.py tests/test_godot_integration.py`
- `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
- `python -m unittest tests.test_client.ClientTests.test_animation_helpers_call_rpc`
- `python -m unittest tests.test_godot_integration.GodotIntegrationTests.test_runtime_locator_click_and_expect`
- `python -m unittest discover -s tests` -> 37 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment was clean: no generated `.uid`, `.godot`, or `__pycache__`, no `.codex_*` files, no lingering Godot processes, and the example addon copy matched the source addon.

## Previous Completed Increment

Failure diagnostics artifacts were added and validated.

Delivered in this increment:

- Capture useful state when a test fails, before the Godot process exits.
- Persist a failure scene snapshot artifact for post-mortem debugging.
- Combine Python traceback, trace summary, Godot log summary, runtime/editor status, artifact links, and snapshot summary into a `*-diagnostics.json` file.
- Surface the diagnostics artifact and key summary in the HTML report.

- Added failure-time diagnostics capture in the runner.
- Added `*-failure-scene.json` snapshots for failed tests.
- Added `*-diagnostics.json` files for failed tests.
- Added HTML report Diagnostics block with trace/log/snapshot summary chips.
- Added runner integration coverage that verifies failure diagnostics artifacts and HTML output.
- README and protocol docs were updated for failure diagnostics.

Validation completed for this increment:

- `python -m py_compile godot_playwright/runner.py tests/test_runner.py`
- `python -m unittest tests.test_runner.RunnerIntegrationTests.test_runner_html_report_includes_failure_details`
- `python -m unittest discover -s tests` -> 37 passed
- `python -m godot_playwright.cli install examples/basic --autoload`
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace off` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests --update-snapshots --trace on` -> 5 passed
- `python -m godot_playwright.cli test examples/basic examples/basic/tests/test_editor_expectations.py --mode editor --trace off` -> 1 passed

Cleanup after this increment is clean: no generated `.uid`, `.godot`, or `__pycache__`, no `.codex_*` files, no lingering Godot processes, and the example addon copy matches the source addon.

## Next Steps

1. Continue toward broader parity with Playwright-level workflows.
2. High-value candidates after this increment: reusable fixtures for generated scenes, richer import metadata inspection, and export/build automation.
3. Keep updating this file after each completed increment and validation pass.
