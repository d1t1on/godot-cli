# Completion Audit

Last updated: 2026-05-24 23:52:28 CST

Objective under review: build a Godot automation layer for AI agents with
Playwright-like development and testing control over Godot projects.

Current judgment: **completion gates satisfied for a serious automation toolkit
in the current local Arch Linux and Godot 4.6.2 environment**. The implemented
surface is broad enough for real agent-driven Godot authoring and testing.
Further work should be treated as post-completion hardening across broader
project corpora, operating systems, and Godot/Python version matrices.

## Evidence Snapshot

- Protocol surface: 160 documented live RPC methods across 19 domains in
  `addons/godot_playwright/godot_playwright_server.gd`.
- Python client surface: `GodotClient`, `Locator`, assertion classes, and
  project/editor/resource helpers in `godot_playwright/client.py`.
- CLI surface: init, install, launch, smoke, probe, probe-scenes,
  check-script(s), check-resources, inspect-scene, inspect-project, find-nodes,
  validate, export, test, codegen-trace, health, snapshot, and raw RPC in
  `godot_playwright/cli.py`.
- Test evidence: 145 tests passed in the latest full suite, including live Godot
  runtime/editor integration tests.
- Latest live validation: both bundled example projects passed
  `godot-playwright validate --exclude 'addons/**' --frames 3` with 5/5 checks.
- Fresh package bootstrap: a clean virtual environment imported
  `godot_playwright` from `site-packages`, resolved the bundled add-on from
  installed package data, initialized a fresh project, passed runtime/editor
  smoke checks, and passed validation 5/5.
- Multi-project evidence: `examples/agent_workspace` adds a second bundled
  project shape with 4 scripts, 3 scenes, 1 `.tres` resource, nested
  scene/script directories, and 2 autoloads; runtime/editor smoke passed on a
  temp copy and validation passed 5/5.
- Trace/codegen audit: the addon currently emits 119 trace event types; 116
  replay as editable Python helper calls and `rpc`, `trace.start`, and
  `trace.stop` are classified as intentional infrastructure events.
- Release/operations docs: `docs/release.md` records supported environment,
  clean install smoke, release validation commands, cleanup checks, common
  failures, and release checklist.
- External generated-project evidence: a temporary non-bundled project is
  generated during tests with 35+ files, 12 assets, 12 `.tres` resources,
  6 scenes, 3 scripts, export preset data, live doctor readiness, validation,
  and export preflight.
- Human real-project corpus evidence: copied two non-generated projects from
  `/home/nietkui/GodotProjects` into `/tmp`, installed the addon through the
  public CLI, and validated real-world project shapes. `ItsNotBug` surfaced and
  verified UID main-scene resolution, while `card-battle` passed 5/5 validation
  after Godot import/global-class registration and live `project.doctor` passed
  6/6.
- Real-project fixes from corpus failures: static project inventory resolves
  `uid://...` main scenes/autoloads via `.uid` sidecars and text resource
  headers; static scene inspection now normalizes Godot parent paths like
  `parent="./BattleVBox"`.
- Export evidence from human projects: export preset discovery worked for
  `ItsNotBug` Web and `card-battle` Windows presets; actual export was blocked
  by missing Godot 4.6.2 export templates in the local user environment.
- Latest cleanup: no generated `.uid`, `.godot`, `__pycache__`, `.codex_*`, or
  `extension_api.json` files remained; no lingering Godot processes; example
  and package bundled addon copies matched the source addon.

## Capability Matrix

| Area | Status | Evidence | Remaining gap |
| --- | --- | --- | --- |
| Launch and connect | Done | `Godot` launcher, CLI `launch`, health endpoint, runtime/editor modes, clean venv package smoke | More packaged install smoke tests across different Python/Godot versions |
| Live inspection | Done | `tree.snapshot`, `node.describe`, `node.state`, `node.bounds`, engine and viewport helpers | Deep editor dock/widget coverage can still grow |
| Selectors and locators | Done | Name, class, role, text, test id, metadata, boolean filters, descendant filters, static `find-nodes` | Static selector index does not cover every dynamic descendant case |
| User actions | Done | Click, fill, focus, dialog, menu, item, tab, tree item, keyboard, mouse, touch, joypad, viewport size | More platform input edge cases should be tested on non-headless desktops |
| Assertions | Done | Locator, editor, inspector, script, filesystem, resource, physics, project, engine, viewport, log, trace, signal expectations | More domain-specific assertions can be added as use cases appear |
| Runtime testing | Done | Runtime probes, scene probes, log capture, physics/camera/animation/signal helpers, multi-project runtime smoke, external generated-project probes, human `card-battle` 8/8 runtime probes | Broader multi-version human-project corpus coverage |
| Editor authoring | Mostly done | Scene create/open/save, node create/tree/edit/move/reparent/delete/duplicate, inspector, selection, undo/redo, script editor, filesystem open | Not every Godot editor workflow has a high-level ergonomic helper |
| Project and files | Done | Project settings, main scene, autoloads, export presets, filesystem mutation/search/grep/list/copy/move/delete | Conflict-aware multi-file refactor workflows can keep expanding |
| Resources and imports | Mostly done | Resource file discovery/describe/inspect/save/set/duplicate/dependencies/references/move/import metadata/reimport, generated PNG asset scale fixture, real-project import/global-class registration evidence | More asset/import edge cases can be added from broader corpora |
| Diagnostics | Done | `project.summary`, `project.doctor`, validation reports, export/import preflight evidence, script parser diagnostics, runtime log diagnostics | Failure ranking could become smarter after more real project data |
| Tracing and codegen | Done | Trace start/stop/events/clear, trace assertions, `codegen-trace` replay for 116 addon events, infrastructure-event audit for `rpc`/`trace.start`/`trace.stop`, unsupported custom events preserved as comments | More replay helpers can be added for future new event types |
| Reporting | Done | JSON results, HTML report, JUnit XML, traces, logs, screenshots, attachments, step records, soft assertions | Report UX polish remains possible |
| CI and scale control | Mostly done | List-only planning, grep, sharding, retries, max failures, timeouts, workers, inventory scale summaries, second project validation fixture, generated external-project scale regression, human corpus validation | Broader human-project scale benchmarks can continue post-completion |
| Documentation | Done | README quick start/bootstrap docs and examples, `docs/protocol.md`, `docs/release.md`, this completion audit | More tutorials can be added later |

## Completion Gates

The broad goal is complete for the current local environment because these
gates are now satisfied:

1. Fresh-environment install smoke: package install in a clean virtual
   environment, create a new project, install addon, run smoke/validate.
   Satisfied on 2026-05-24 for the local package and latest available Godot.
2. Multi-project evidence: run validation and a minimal runtime/editor test on
   at least one additional Godot project shape beyond `examples/basic`.
   Satisfied on 2026-05-24 with `examples/agent_workspace`.
3. Trace/codegen audit: confirm all high-value trace events either replay into
   helpers or are intentionally documented as comments.
   Satisfied on 2026-05-24 with a 119-event addon/codegen coverage regression.
4. Packaging/docs pass: document supported Godot/Python versions, install
   expectations, common failure modes, and release steps.
   Satisfied on 2026-05-24 with `docs/release.md`.
5. Final full validation: py_compile, addon `--check-only`, focused units, live
   integration, full suite, CLI install/validate, cleanup.
   Satisfied on 2026-05-24 with 145 tests and both bundled examples passing
   validation 5/5.
6. External generated scale/asset/export evidence: validate a non-bundled
   project shape with asset/resource scale and export preset preflight.
   Satisfied on 2026-05-24 with a temporary generated project and 144-test
   suite.
7. Human real-project corpus run: copy/install the addon into non-generated
   local Godot projects, run inventory/validate/live doctor/export preset
   checks, and fix or document discovered edge cases.
   Satisfied on 2026-05-24 with `ItsNotBug` and `card-battle`. The run produced
   two fixes, a 5/5 validation on `card-battle`, live `project.doctor` 6/6, and
   export preset evidence blocked only by missing local export templates.

## Next Best Increment

The highest-value next increment is post-completion hardening: run a broader
human-project corpus across more Godot versions/export templates, add any
failure-derived regressions, and expand packaged install smoke coverage across
Python and OS variants.
