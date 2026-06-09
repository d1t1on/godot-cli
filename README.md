# Godot Playwright

Godot Playwright is a local automation bridge for Godot 4.6+.

The goal is the same shape as Playwright for browsers: an agent or test can launch
Godot, inspect the live scene tree, select nodes, drive input, mutate scenes, save
editor state, capture screenshots, observe live engine logs, trace automation
steps, and assert behavior through a stable protocol.

This first implementation provides:

- A Godot add-on that exposes a localhost JSON-RPC server in the editor or runtime.
- A Python client with Playwright-like `Godot`, `GodotClient`, `locator()`,
  `get_by_role()`, and `get_by_test_id()` APIs.
- A CLI for creating starter projects, installing the add-on, launching Godot,
  running smoke checks, probing runtime startup errors, checking GDScript syntax,
  exporting presets, querying health, taking snapshots, and invoking arbitrary
  RPC methods.
- A tiny Godot example project and stdlib-only Python tests.

## Quick Start

Install the Python package in editable mode:

```sh
python -m pip install -e .
```

For a clean environment or agent bootstrap, install the package into a virtual
environment, then use the installed console script. The package includes the
Godot add-on files, so `init` and `install` do not need a separate repository
checkout after installation:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install /path/to/godot-cli

godot-playwright init /tmp/agent-game --name AgentGame
godot-playwright smoke /tmp/agent-game --mode runtime
godot-playwright smoke /tmp/agent-game --mode editor
godot-playwright validate /tmp/agent-game --exclude "addons/**"
```

Create a starter Godot project that is already wired for automation:

```sh
godot-playwright init /tmp/agent-game --name AgentGame
```

The repository also includes two validation fixtures:

- `examples/basic`: compact runtime/editor automation fixture.
- `examples/agent_workspace`: multi-scene project with nested scenes/scripts,
  a `.tres` resource, and project autoloads for broader validation evidence.

Release and operations checks are documented in `docs/release.md`.

Run a structured smoke check. Runtime mode verifies launch, health, scene
snapshotting, selector lookup, property reads, and button activation:

```sh
godot-playwright smoke /tmp/agent-game --mode runtime
```

Editor mode verifies launch, health, scene tree inspection, scene creation,
property mutation, and saving a generated scene:

```sh
godot-playwright smoke /tmp/agent-game --mode editor
```

Editor automation can also verify undo/redo after generated edits:

```python
def test_editor_undo(godot, expect, expect_editor):
    godot.editor_new_scene(class_name="Control", name="AgentScene")
    label = godot.create_node("edited", "Label", name="StatusLabel")
    expect_editor.to_have_undo()
    undone = godot.editor_undo()
    assert undone["history_state"]["can_redo"]
    expect_editor.to_have_redo()
    expect(godot.locator("#StatusLabel")).not_to_exist()
    redone = godot.editor_redo()
    assert redone["history_state"]["can_undo"]
    expect_editor.not_to_have_redo()
    expect(godot.locator("#StatusLabel")).to_exist()
```

Generate a new Godot-native UI scene from a structured design spec and write a
layout review report:

```sh
godot-playwright design-ui /tmp/agent-game ui_spec.json \
  --scene res://scenes/ui/main_menu.tscn \
  --viewport 1280x720 \
  --viewport 800x450
```

The `design-ui` command maps Figma-like tokens, components, variants, and
constraints onto Godot `Control` nodes, containers, theme overrides, metadata,
and groups. It saves the generated scene, captures per-viewport screenshots when
available, and writes `design-report.json` plus `design-report.html` with
layout issues such as overlaps, out-of-viewport controls, undersized touch
targets, text overflow, and missing referenced `res://` assets.

Minimal spec:

```json
{
  "schema_version": 1,
  "name": "MainMenu",
  "target": {"scene": "res://scenes/ui/main_menu.tscn"},
  "tokens": {
    "colors": {"surface": "#141418", "text": "#f7f7fb", "primary": "#ffcc00"},
    "spacing": {"md": 12, "lg": 24},
    "font_sizes": {"title": 32, "body": 16}
  },
  "components": {
    "menu_button": {
      "base": {"type": "button", "size": [220, 52], "style": {"font_color": "$colors.text"}},
      "variants": {"primary": {"style": {"font_color": "$colors.primary"}}}
    }
  },
  "root": {
    "type": "screen",
    "id": "main_menu",
    "style": {"background": "$colors.surface"},
    "children": [
      {"type": "text", "id": "title", "text": "Start", "font_size": "$font_sizes.title"},
      {"type": "instance", "component": "menu_button", "variant": "primary", "id": "play", "text": "Play"}
    ]
  }
}
```

Install reusable Godot gameplay modules for agent-built games:

```sh
godot-playwright module list
godot-playwright module add /tmp/agent-game save_load
godot-playwright module add /tmp/agent-game inventory
godot-playwright module add /tmp/agent-game inventory --demo
godot-playwright module add /tmp/agent-game interaction
godot-playwright module add /tmp/agent-game interaction --demo
```

The first gameplay module is `save_load`, a JSON slot save/load service. The
installer copies `res://addons/save_load/`, registers the `SaveService` Autoload,
and can optionally install a tiny demo scene plus copied Python test. Gameplay
objects participate by joining the `save_participants` group and implementing
`save_state()` / `load_state(data)` with JSON-compatible state.

The `inventory` module adds a reusable `Inventory` node component backed by `InventoryItemDefinition` and `InventoryItemDatabase` Resources. It supports finite stack capacity, add/remove/query operations, JSON-compatible `get_state()` / `apply_state(data)`, and optional persistence through `save_load` when an inventory has a stable `save_id`.

The `interaction` module adds reusable `Interactable`, `Interactor2D`, and `Interactor3D` components for nearby object interaction. It supports prompts, priority-based candidate selection, structured interaction results, JSON-compatible `get_state()` / `apply_state(data)`, and optional integration with project-specific inventory or save/load behavior without requiring either module.

Probe runtime startup for script errors and warning/error log diagnostics:

```sh
godot-playwright probe /tmp/agent-game --scene res://scenes/main.tscn
godot-playwright probe-scenes /tmp/agent-game res://scenes --exclude "addons/**"
```

Run Python automation tests against a Godot project:

```sh
godot-playwright test /tmp/agent-game examples/basic/tests --trace on
```

Plan or partition larger test suites before launching Godot:

```sh
godot-playwright test /tmp/agent-game examples/basic/tests --list --grep counter
godot-playwright test /tmp/agent-game examples/basic/tests --grep "counter|navigation" --shard 1/2
godot-playwright test /tmp/agent-game examples/basic/tests --retries 2 --trace retain-on-failure
godot-playwright test /tmp/agent-game examples/basic/tests --test-timeout 30
godot-playwright test /tmp/agent-game examples/basic/tests --max-failures 1
godot-playwright test /tmp/agent-game examples/basic/tests --junit-xml build/junit.xml
godot-playwright test /tmp/agent-game examples/basic/tests --workers 4
godot-playwright test /tmp/agent-game examples/basic/tests --screenshots only-on-failure --no-headless
```

Run a configured Godot export preset and write a structured log/report:

```sh
godot-playwright export /tmp/agent-game "Agent Linux" build/agent_linux.x86_64 --mode release
```

Export reports include `export_presets` preflight data, whether the requested
preset was found, whether the requested output path matches the preset
`export_path`, `output_changed` artifact freshness evidence, and structured
Godot log diagnostics.

Resource import reports include source/import file state, generated destination
files, missing/stale generated-file diagnostics, and reimport preflight evidence
so agents can tell whether an asset is unimported, stale, or not loadable.

Check a generated script through Godot's own parser and get structured
diagnostics:

```sh
godot-playwright check-script /tmp/agent-game res://scripts/player.gd
godot-playwright check-scripts /tmp/agent-game res://scripts --exclude "addons/**"
```

Script checks run `godot --import` first by default so Godot can build the
global `class_name` cache before `--check-only` parses scripts. Use
`--no-import-cache` only when you explicitly need the older direct parser path.
Godot subprocesses launched by checks, probes, and exports also use an isolated
loopback port and XDG user-data directory, so parallel audits do not fight over
the runtime autoload port or `user://logs`.

Runner tests can use the same parser as an assertion fixture:

```python
def test_generated_script(expect_script_file):
    expect_script_file("res://scripts/player.gd").to_extend("Node")
    expect_script_file("res://scripts/player.gd").to_define_function("_ready")
    expect_script_file("res://scripts/player.gd").to_pass_godot_check()
```

Check scene/resource external dependencies before runtime/export:

```sh
godot-playwright check-resources /tmp/agent-game res://scenes --exclude "addons/**"
```

Inspect a text scene's node tree and resources without launching Godot:

```sh
godot-playwright inspect-scene /tmp/agent-game res://scenes/main.tscn --json
```

Inspect a project inventory before choosing what to edit or test:

```sh
godot-playwright inspect-project /tmp/agent-game --exclude "addons/**" --json
```

The inventory includes file totals, extension distribution, category counts and
bytes, directory hot spots, path depth, largest files, and newest files so
agents can estimate project scale and plan edits before launching the editor.

Find candidate selectors across text scenes before launching Godot:

```sh
godot-playwright find-nodes /tmp/agent-game --role button --test-id counter-button --json
```

Run a project-level validation gate that combines project inventory, script
parsing, resource dependency checks, static scene inspection, and runtime scene
probes:

```sh
godot-playwright validate /tmp/agent-game --exclude "addons/**"
```

Validation reports surface the same `scale` summary from inventory at the top
level, so agents can decide whether to narrow subsequent checks to specific
paths.

Every test run writes `results.json`, per-test Godot engine logs, and a portable
`report.html` into the artifacts directory. The HTML report summarizes pass/fail
state, links trace/log artifacts, expands failure tracebacks, and links failure
diagnostics with scene snapshots so agents can inspect the failing Godot state
without requiring extra tooling.

Tests can assert recorded automation events when tracing is enabled:

```python
def test_trace(godot, expect_trace):
    button = godot.locator("#CounterButton")
    button.click()
    expect_trace.to_have_event("node.click", data={"strategy": "pressed_signal"})
    expect_trace.to_have_rpc("node.click")
    expect_trace.to_have_event_count(1, "node.click")
    expect_trace.to_have_rpc_count("node.click", 1)
```

Tests can also assert the Godot environment before doing generated work:

```python
def test_engine_environment(godot, expect_engine):
    info = godot.engine_info()
    assert info["godot"]["major"] >= 4
    expect_engine.to_be_available()
    expect_engine.to_be_editor()
    expect_engine.to_have_godot_version(major=4)
    expect_engine.to_have_project_path("agent-game")
```

Agents can discover the live protocol surface before choosing an action:

```python
def test_protocol_surface(godot):
    protocol = godot.protocol_describe()
    methods = {entry["method"] for entry in protocol["methods"]}
    assert "editor.filesystem.open" in methods
    assert "resource.move" in methods
    assert "resource_safe_move" in protocol["features"]
```

Trace artifacts can also seed new tests. This is the current codegen path for
turning an exploratory run into editable Python automation:

```sh
godot-playwright codegen-trace godot-playwright-report/test_counter-test_counter_button-trace.json \
  --test-name replay_counter \
  --output tests/test_replay_counter.py
```

The generated script replays supported actions such as protocol discovery,
clicks, fills, checks, selection controls, scene changes, input events, viewport
actions, filesystem patches and file moves, animation controls, physics/camera
probes, signal watch/connect/disconnect flows, declarative node-tree creation,
fine-grained node authoring operations, semantic resource
creation/update/import operations, static resource file descriptions, reverse
resource reference scans, and editor workflow operations such as scene
create/open/save, play/stop,
undo/redo, selection, inspector, script-open, editor main-screen switching,
bottom-panel hiding, and editor filesystem actions.
Project configuration and InputMap mutations such as main scene, autoload,
export preset, project setting, and action binding changes are also replayed as
editable helper calls.
Unsupported events are kept as comments so an agent can fill in missing
assertions or project-specific intent instead of silently losing trace context.
The trace/codegen coverage test currently verifies every addon-emitted trace
event: 116 event types replay as helper calls, while `rpc`, `trace.start`, and
`trace.stop` are treated as infrastructure events and intentionally omitted.

Tests can also observe Godot stdout/stderr while the process is still running:

```python
def test_live_logs(godot, expect_log):
    godot.log_clear()
    godot.evaluate('print("agent reached gameplay state")')
    expect_log.to_have_message("agent reached gameplay state")
    expect_log.not_to_have_error("unexpected failure")
    godot.evaluate('push_error("agent detected a bad state")')
    expect_log.to_have_error("agent detected a bad state")
```

Python output from tests and hooks is captured per test attempt. Use ordinary
`print(...)` or `print(..., file=sys.stderr)` for agent debugging; non-empty
streams are written as artifacts and linked from `results.json`, diagnostics,
text output, and `report.html`.

By default, each test gets a fresh Godot process so scene state does not leak
between tests. Use `--reuse-godot` only when speed matters more than isolation.
Use `--update-snapshots` to create or refresh scene/screenshot baselines.
Use `--list` to inspect selected tests without launching Godot, `--grep` and
`--grep-invert` to filter test ids by regex, and `--shard current/total` to split
the selected tests deterministically across agents or CI jobs. Use `--retries`
to rerun failures; tests that fail first and pass on retry are counted as passed
and marked flaky, with each attempt's logs, traces, and diagnostics retained in
the JSON/HTML report. Use `--test-timeout` to fail a stuck test attempt while
still collecting the usual failure diagnostics and artifacts. Use
`--max-failures N` to stop launching additional single-worker isolated tests
after N failed tests; not-run tests are marked interrupted in the report. Use
`--workers` to run isolated per-test Godot processes concurrently while
preserving a single ordered JSON/HTML report. `--reuse-godot` intentionally
keeps one shared Godot process and is incompatible with multiple workers.
`--max-failures` currently requires the default single-worker isolated mode so
the report does not claim unlaunched tests were stopped while parallel workers
were already running.
Use `--junit-xml path/to/report.xml` when you need CI-friendly XML alongside the
JSON/HTML report. The XML includes failures, skipped/interrupted tests, and
artifact paths for downstream tooling.
Use `--screenshots only-on-failure` or `--screenshots on` to attach viewport PNG
artifacts to test attempts. Godot cannot capture viewport screenshots with the
headless display driver, so screenshot capture errors are recorded as diagnostic
metadata instead of failing the test a second time.

Known gaps can be marked explicitly with test annotations:

```python
from godot_playwright import expected_failure, skip


@skip("blocked by missing project fixture")
def test_waiting_on_fixture():
    pass


@expected_failure("known editor bug")
def test_known_editor_bug(godot):
    raise AssertionError("still broken")
```

Skipped tests are reported without launching Godot for that test. Expected
failures count as green expected-failed outcomes when they fail, while an
expected-failure test that passes is reported as an unexpected-pass failure.
For conditions that can only be known after Godot starts, call
`test_info.skip("reason")` inside the test:

```python
def test_runtime_only_feature(godot, test_info, step):
    with step("check runtime capabilities"):
        if not godot.evaluate("RenderingServer.get_current_rendering_driver_name() == 'vulkan'"):
            test_info.skip("requires Vulkan renderer")
```

Runtime skips launch Godot, keep steps, attachments, logs, and trace summaries
produced before the skip, do not retry, and count as skipped rather than failed.

Use `soft_expect` when an agent-authored test should gather multiple assertion
mismatches before failing. Soft assertion failures are recorded in
`results.json`, diagnostics, JUnit XML, text output, and `report.html`; the test
fails after the body and `after_each` hooks finish. Hard assertion, RPC, and
timeout failures still remain the primary error.

```python
def test_inventory_screen(godot, soft_expect):
    inventory = godot.get_by_test_id("inventory-list")
    soft_expect(inventory).to_have_count(4)
    soft_expect(inventory.nth(0)).to_have_text("Potion")
```

Use `expect_poll` for arbitrary state that needs Playwright-style retrying,
including Godot expressions wrapped in Python callables. It supports
`to_equal()`, `to_be()`, `not_to_equal()`, `to_be_truthy()`, `to_be_falsy()`,
and `to_satisfy()`, and timeout errors include the last observed value or last
callable error.

```python
def test_runtime_flag(godot, expect_poll):
    expect_poll(
        lambda: godot.evaluate('root.get("ready")'),
        description="root ready flag",
    ).to_be_truthy(timeout=2)
```

Per-file setup and teardown can use the same fixture names as tests:

```python
from godot_playwright import after_each, before_each


@before_each
def prepare_scene(godot, step):
    with step("open main scene"):
        godot.editor_open_scene("res://scenes/main.tscn")


@after_each
def collect_state(test_info, attach):
    attach("scene", body={"test": test_info.name})
```

`before_each` runs before each test in the module. `after_each` runs after
passed, failed, and runtime-skipped tests, so cleanup evidence is kept in
`results.json`, diagnostics, text output, and `report.html`.

Test functions can ask for built-in fixtures by parameter name:

```python
def test_counter_button(godot, expect, soft_expect, expect_poll, expect_signal, step):
    with step("wait for main scene"):
        main = godot.locator("#Main")
        godot.wait_for_process_frames(2)
        assert godot.evaluate('root.get("name")') == "Main"
    godot.wait_for_function('root.has_node("CounterButton")')
    expect_poll(lambda: godot.evaluate('root.has_node("CounterButton")')).to_be_truthy(timeout=1)

    player = godot.locator("#AutomationAnimation")
    expect(player).to_have_animation("fade_in", track={"path": "AnimatedLabel:modulate:a"})
    player.play_animation("fade_in", speed=0.0)
    player.seek_animation(0.5)
    expect(player).to_be_playing_animation("fade_in", position=0.5)
    player.advance_animation(0.25)
    title = main.get_by_text("Godot Playwright")
    expect(title).to_be_visible()
    expect(main.get_by_test_id("counter-button")).to_have_count(1)
    expect(main.get_by_role("button", name="Clicked 0")).to_have_count(1)
    expect(main.get_by_test_id("missing")).not_to_exist(timeout=0.2)
    expect(main.get_by_test_id("missing")).to_be_hidden(timeout=0.2)
    terms = main.get_by_test_id("accept-terms")
    terms.check()
    expect(terms).to_be_checked()
    terms.uncheck()
    expect(terms).not_to_be_checked()
    theme = main.get_by_test_id("theme-select")
    theme.select_option("Story")
    expect(theme).to_have_value("Story")
    volume = main.get_by_test_id("volume-slider")
    volume.set_value(75)
    expect(volume).to_have_value(75.0)
    tabs = main.get_by_test_id("mode-tabs")
    tabs.select_tab("Advanced")
    expect(tabs).to_have_value("Advanced")
    action_menu = main.get_by_test_id("action-menu")
    action_menu.select_menu_item({"metadata": {"action": "save"}})
    inventory = main.get_by_test_id("inventory-list")
    inventory.select_item("Elixir")
    expect(inventory).to_have_value("Elixir")
    quests = main.get_by_test_id("quest-tree")
    quests.select_tree_item({"path": ["Cave", "Boss"]})
    expect(quests).to_have_value("Boss")
    button = main.get_by_test_id("counter-button")
    button.wait_for(state="visible")
    expect(button).to_have_text("Clicked 0")
    soft_expect(main.get_by_test_id("optional-hint")).to_have_text("Ready")
    assert button.evaluate('node.get("text")') == "Clicked 0"
    assert main.locator("role=button").evaluate_all("count") >= 2
    expect(button).not_to_have_text("Clicked 2")
    expect(button).to_be_enabled()
    expect(button).not_to_be_disabled()
    expect(button).to_be_actionable()
    expect(main.locator("role=button").and_(main.get_by_test_id("counter-button"))).to_have_count(1)
    expect(main.locator("role=button").filter(has_text="Clicked", has_not_text="Next")).to_have_count(1)
    expect(main.locator("role=button").nth(0)).to_have_text("Clicked 0")
    button.wait_for_signal("pressed", action=button.click)
    godot.wait_for_signal("#CounterButton", "pressed", action=button.click)
    expect_signal("#CounterButton", "pressed").to_have_event(action=button.click)
    expect(button).to_have_text("Clicked 1")
```

Ordered signal assertions can watch a signal stream across multiple actions:

```python
with expect_signal("#CounterButton", "pressed") as pressed:
    button.click()
    button.click()
    pressed.to_have_event_sequence(["pressed", "pressed"])
```

Use the `step` fixture to wrap intent-level actions. Step titles, status,
duration, nesting depth, and step-local failure metadata are written to
`results.json`, diagnostics, and `report.html`, making long agent-authored tests
easier to debug.

Use `test_info` or the `attach` fixture to preserve custom evidence in the same
report:

```python
def test_with_debug_artifacts(godot, test_info, attach):
    state_path = test_info.output_path("state.json")
    state_path.write_text('{"screen":"inventory"}', encoding="utf-8")
    test_info.attach("state", path=state_path, content_type="application/json")
    attach("notes", body="inventory was open before clicking")
    attach("payload", body={"scene": godot.current_scene()})
```

Attachments are copied into a per-test output directory and linked from
`results.json`, diagnostics, text output, and `report.html`.

Text controls support Playwright-style fill and key press helpers:

```python
def test_line_edit(godot, expect):
    name = godot.locator("#Main").get_by_test_id("name-input")
    expect(name).to_be_editable()
    expect(name).to_have_value("")
    name.wait_for_signal("text_changed", action=lambda: name.fill("Ada"))
    expect(name).to_have_text("Ada")
    expect(name).to_have_value("Ada")
    name.wait_for_signal("text_submitted", action=lambda: name.press("Enter"))
```

Keyboard helpers support shortcut-style key combos and explicit modifiers:

```python
def test_shortcuts(godot):
    godot.press("Ctrl+S")
    godot.press("F4", shift=True)
```

Mouse helpers can drive hover, drag, and wheel input through viewport events:

```python
def test_mouse_flow(godot):
    item = godot.locator("#InventoryItem")
    item.hover()
    item.drag_to("#DropSlot")
    godot.locator("#ScrollablePanel").scroll(delta_y=240)
    assert item.center() == (160.0, 96.0)
    expect(item).to_have_bounds(x=128.0, y=72.0, width=64.0, height=48.0)
    expect(item).to_be_within_viewport()
```

Touch helpers drive mobile-style taps and drags through viewport touch events:

```python
def test_touch_flow(godot):
    target = godot.locator("#Main").get_by_test_id("touch-target")
    target.tap()
    target.touch_drag_to(target)
```

Gamepad helpers can press joypad buttons and move axes without a physical controller:

```python
def test_gamepad_flow(godot):
    godot.joypad_press("a")
    godot.joypad_axis("left_x", 0.5)
```

2D and 3D physics helpers query live worlds so tests can assert collision
targets without depending on pixels:

```python
def test_physics_queries(godot, expect, expect_physics2d, expect_physics3d):
    hit = godot.physics2d_ray(0, 120, 400, 120)
    assert hit["hit"] is True
    expect_physics2d.to_have_point_collision(240, 120, name="Player")
    expect_physics2d.not_to_have_ray_collision(0, 16, 400, 16, name="Wall")

    hit3d = godot.physics3d_ray(-4, 0, 0, 4, 0, 0)
    assert hit3d["hit"] is True
    expect_physics3d.to_have_point_collision(0, 0, 0, name="PlayerBody")
    expect_physics3d.not_to_have_ray_collision(-4, 8, 0, 4, 8, 0, name="Wall")

    camera = godot.locator("#GameplayCamera")
    pick = camera.pick_3d(640, 360)
    assert pick["collision"]["name"] == "PlayerBody"
    expect(camera).to_pick_camera_collision(640, 360, name="PlayerBody")
    camera.click_3d(640, 360, name="PlayerBody")
    camera.drag_3d(640, 360, 700, 360, name="PlayerBody", steps=4)
```

InputMap helpers let tests create temporary game actions and bind keys, mouse
buttons, or controller inputs before driving them:

```python
def test_dynamic_controls(godot, expect_project):
    jump_action = godot.bind_action_key("agent_jump", "Space", replace=True)
    assert jump_action["action_state"]["event_count"] == 1
    godot.bind_action_joypad_button("agent_confirm", "a", replace=True)
    expect_project.to_have_input_action("agent_jump", min_event_count=1)
    expect_project.to_have_input_action_event("agent_jump", event_type="key", key="Space")
    expect_project.to_have_input_action_event("agent_confirm", event_type="joypad_button", button="a")
    down = godot.action_down("agent_jump", strength=0.75)
    assert down["pressed_state"]["strength"] == 0.75
    expect_project.to_have_input_action_pressed("agent_jump", min_strength=0.7)
    up = godot.action_up("agent_jump")
    assert up["pressed_state"]["pressed"] is False
    expect_project.not_to_have_input_action_pressed("agent_jump")
    godot.press_action("agent_confirm", frames=2)
    godot.press("Space")
    godot.joypad_press("a")
```

Viewport helpers expose the active window and visible rect, and can resize the
window for deterministic layout-sensitive automation:

```python
def test_responsive_layout(godot, expect_viewport):
    viewport = godot.viewport_info()
    assert viewport["window_size"]["width"] > 0
    godot.set_viewport_size(900, 700)
    godot.wait_for_viewport_size(900, 700)
    expect_viewport.to_have_size(900, 700)
    expect_viewport.to_have_mouse_position(0, 0)
    expect_viewport.to_have_screenshot("user://responsive-layout.png", min_width=900, min_height=700)
```

Popup menus can be inspected and activated without relying on screen pixels:

```python
def test_menu_command(godot):
    menu = godot.locator("#Main").get_by_test_id("action-menu")
    assert [item["text"] for item in menu.menu_items()] == ["Open", "Save", "Snap"]
    menu.select_menu_item({"metadata": {"action": "save"}})
```

Dialogs expose Playwright-style accept and dismiss actions:

```python
def test_dialog(godot):
    main = godot.locator("#Main")
    main.get_by_test_id("show-confirm").click()
    dialog = main.get_by_test_id("confirm-dialog")
    dialog.wait_for(state="visible")
    assert dialog.dialog()["text"] == "Run the agent action?"
    dialog.accept_dialog()
```

Editor sessions can create project files and Resources through the same protocol:

```python
def test_editor_asset_workflow(godot, expect, expect_project, expect_project_scene, expect_resource, expect_resource_class, expect_node_class, expect_script_class, expect_scene_file, expect_filesystem, expect_script):
    godot.project_set_setting("application/config/description", "Agent maintained", save=True)
    godot.editor_new_scene(class_name="Control", name="AgentScene")
    node_classes = godot.node_classes(base_class="Control", name_contains="Label", max_results=20)
    assert any(entry["class"] == "Label" for entry in node_classes["classes"])
    expect_node_class("Label").to_be_listed(base_class="Control")
    label_schema = godot.node_class_describe(
        "Label",
        properties=["text"],
        methods=["set_text"],
        storage_only=True,
    )
    assert label_schema["properties"][0]["type_name"] == "String"
    assert label_schema["methods"][0]["args"][0]["type_name"] == "String"
    expect_node_class("Label").to_have_property("text", type_name="String", storage=True)
    expect_node_class("Label").to_have_method("get_meta")
    expect_node_class("Button").to_have_signal("pressed")
    godot.create_node("edited", "Label", name="StatusLabel")
    panel_state = godot.create_node("edited", "VBoxContainer", name="GeneratedPanel")
    assert panel_state["node_state"]["path"].endswith("/GeneratedPanel")
    panel = godot.locator("#GeneratedPanel")
    status = godot.locator("#StatusLabel")
    godot.fs_write_text(
        "res://scenes/badge.tscn",
        '[gd_scene format=3]\n\n[node name="Badge" type="Label"]\ntext = "Reusable Badge"\n',
    )
    badge = panel.instantiate_scene("res://scenes/badge.tscn", name="BadgeInstance")
    assert badge["node_state"]["path"].endswith("/BadgeInstance")
    moved_status = status.reparent(panel, index=0)
    assert moved_status["node_state"]["parent"].endswith("/GeneratedPanel")
    copied_status = status.duplicate(parent=panel, name="StatusLabelCopy")
    assert copied_status["node_state"]["name"] == "StatusLabelCopy"
    reordered_copy = godot.locator("#StatusLabelCopy").move(0)
    assert reordered_copy["node_state"]["index"] == 0
    grouped = status.add_group("agent_generated")
    assert "agent_generated" in grouped["groups_state"]["groups"]
    expect(status).to_have_group("agent_generated")
    status.set("text", "created by automation")
    assert godot.wait_for_node_property("#StatusLabel", "text", "created by automation") == "created by automation"
    status_script = godot.write_script(
        "res://scripts/status_label.gd",
        '@tool\nextends Label\n\nfunc agent_status() -> String:\n\treturn text\n',
        extends="Label",
        functions=["agent_status"],
        source_contains="return text",
    )
    assert status_script["file"]["type"] == "file"
    assert status_script["script"]["symbols"]["extends"] == "Label"
    hud_tree = godot.create_node_tree(
        {
            "class": "PanelContainer",
            "name": "AgentHud",
            "groups": ["agent_ui"],
            "metadata": {"test_id": "agent-hud"},
            "children": [
                {"class": "Label", "name": "AgentTitle", "properties": {"text": "Agent Ready"}},
                {
                    "class": "Button",
                    "name": "AgentAction",
                    "properties": {"text": "Run"},
                    "script": "res://scripts/status_label.gd",
                },
            ],
        },
        parent="#GeneratedPanel",
    )
    assert hud_tree["count"] == 3
    assert hud_tree["nodes"][1]["properties_state"]["text"] == "Agent Ready"
    attached_status = status.attach_script("res://scripts/status_label.gd")
    assert attached_status["script_state"]["path"] == "res://scripts/status_label.gd"
    expect(status).to_have_script("res://scripts/status_label.gd")
    assert status.call("agent_status") == "created by automation"
    godot.locator("#StatusLabelCopy").attach_script("res://scripts/status_label.gd", reload=False)
    godot.locator("#StatusLabelCopy").detach_script()
    panel.create_child("Button", name="SignalButton")
    panel.create_child("Node", name="SignalReceiver")
    godot.write_script(
        "res://scripts/signal_receiver.gd",
        '@tool\nextends Node\n\nfunc on_signal_button_pressed() -> void:\n\tset_meta("pressed_seen", true)\n',
        extends="Node",
        functions=["on_signal_button_pressed"],
    )
    godot.attach_script("#SignalReceiver", "res://scripts/signal_receiver.gd")
    signal_connection = godot.locator("#SignalButton").connect_signal(
        "pressed",
        target="#SignalReceiver",
        method="on_signal_button_pressed",
    )
    assert signal_connection["connection_state"]["state"] == "connected"
    expect(godot.locator("#SignalButton")).to_have_signal_connection(
        "pressed",
        target="#SignalReceiver",
        method="on_signal_button_pressed",
        persistent=True,
    )
    godot.locator("#GeneratedPanel").save_as_scene("res://scenes/generated_panel.tscn")
    expect_scene_file("res://scenes/generated_panel.tscn").to_have_node(
        name="StatusLabel",
        script="res://scripts/status_label.gd",
        groups=["agent_generated"],
    )
    expect_scene_file("res://scenes/generated_panel.tscn").to_have_connection(
        "pressed",
        from_node="SignalButton",
        to="SignalReceiver",
        method="on_signal_button_pressed",
    )
    scene_files = godot.scene_files("res://scenes", name="generated_panel.tscn", root_class="VBoxContainer")
    assert scene_files["scenes"][0]["root_name"] == "GeneratedPanel"
    scene_description = godot.scene_file_describe("res://scenes/generated_panel.tscn", include_properties=True)
    assert scene_description["root_class"] == "VBoxContainer"
    expect_project_scene("res://scenes/generated_panel.tscn").to_have_root(
        name="GeneratedPanel",
        class_name="VBoxContainer",
    )
    expect_project_scene("res://scenes/generated_panel.tscn").to_have_node(
        name="StatusLabel",
        script="res://scripts/status_label.gd",
        groups=["agent_generated"],
    )
    expect_project_scene("res://scenes/generated_panel.tscn").to_have_connection(
        "pressed",
        from_node="SignalButton",
        to="SignalReceiver",
        method="on_signal_button_pressed",
    )
    expect_project_scene("res://scenes/generated_panel.tscn").to_have_no_missing_dependencies()
    expect_resource("res://scenes/generated_panel.tscn").to_have_class("PackedScene")
    expect_resource("res://scenes/generated_panel.tscn").to_have_no_missing_dependencies()
    saved = godot.editor_save_scene("res://scenes/agent_scene.tscn")
    assert saved["editor_status"]["edited_scene_file_path"] == "res://scenes/agent_scene.tscn"
    generated_dir = godot.fs_mkdir("res://scripts/generated")
    assert generated_dir["editor_filesystem"]["is_directory"]
    tool_script = godot.write_script(
        "res://scripts/agent_tool.gd",
        "class_name AgentTool\nextends Node\n\nfunc generated_value() -> int:\n\treturn 42\n",
        extends="Node",
        functions=["generated_value"],
    )
    assert tool_script["editor_filesystem"]["resource_type"] == "GDScript"
    script_classes = godot.script_classes(class_name="AgentTool", base_class="Node", max_results=20)
    assert script_classes["classes"][0]["path"] == "res://scripts/agent_tool.gd"
    script_file = godot.script_file_describe("res://scripts/agent_tool.gd", include_source=True)
    assert script_file["class_name"] == "AgentTool"
    assert script_file["functions"][0]["name"] == "generated_value"
    expect_script_class("AgentTool").to_be_listed(base_class="Node")
    expect_script_class("AgentTool").to_extend("Node")
    expect_script_class("AgentTool").to_have_function("generated_value")
    expect_script("res://scripts/agent_tool.gd").to_have_class_name("AgentTool")
    scratch_script = godot.fs_write_text("res://scripts/generated/scratch.gd", "extends Node\n")
    assert scratch_script["file"]["type"] == "file"
    removed_scratch = godot.fs_delete("res://scripts/generated/scratch.gd")
    assert removed_scratch["missing"]["type"] == "missing"
    godot.write_script("res://scripts/agent_state.gd", "extends Node\nvar ready := true\n", extends="Node")
    godot.wait_for_files(["res://scripts/agent_tool.gd", "res://scripts/agent_state.gd"])
    expect_filesystem("res://scripts/agent_state.gd").to_be_file()
    expect_filesystem("res://scripts/agent_state.gd").to_have_text("var ready := true")
    main_scene_state = godot.project_set_main_scene("res://scenes/agent_scene.tscn", save=True)
    assert main_scene_state["main_scene"]["path"] == "res://scenes/agent_scene.tscn"
    expect_project.to_have_main_scene("res://scenes/agent_scene.tscn")
    autoload_state = godot.project_add_autoload("AgentState", "res://scripts/agent_state.gd", save=True)
    assert autoload_state["autoload_state"]["path"] == "res://scripts/agent_state.gd"
    expect_project.to_have_autoload("AgentState", path="res://scripts/agent_state.gd", singleton=True)
    export_preset_state = godot.project_set_export_preset(
        "Agent Linux",
        "Linux",
        export_path="build/agent_linux.x86_64",
        options={"binary_format/embed_pck": False},
    )
    assert export_preset_state["preset_state"]["export_path"] == "build/agent_linux.x86_64"
    expect_project.to_have_export_preset(
        "Agent Linux",
        platform="Linux",
        export_path="build/agent_linux.x86_64",
        options={"binary_format/embed_pck": False},
    )
    project_summary = godot.project_summary(max_results=20)
    assert project_summary["main_scene"]["path"] == "res://scenes/agent_scene.tscn"
    assert project_summary["counts"]["scenes"] >= 1
    assert project_summary["counts"]["scripts"] >= 1
    project_doctor = godot.project_doctor(max_results=20)
    assert project_doctor["ready"]
    assert project_doctor["next_steps"]
    saved_resource = godot.resource_save(
        "res://data/agent_resource.tres",
        properties={"resource_name": "AgentResource"},
    )
    assert saved_resource["file"]["type"] == "file"
    updated_resource = godot.resource_set_properties(
        "res://data/agent_resource.tres",
        {"resource_name": "UpdatedAgentResource"},
    )
    assert updated_resource["previous"]["resource_name"] == "AgentResource"
    assert updated_resource["resource"]["properties"]["resource_name"] == "UpdatedAgentResource"
    resource_files = godot.resource_files(
        "res://data",
        name="agent_resource.tres",
        class_name="Resource",
        resource_name="UpdatedAgentResource",
    )
    assert resource_files["resources"][0]["path"] == "res://data/agent_resource.tres"
    expect_resource("res://data/agent_resource.tres").to_be_listed(
        class_name="Resource",
        resource_name="UpdatedAgentResource",
    )
    resource_file = godot.resource_file_describe("res://data/agent_resource.tres", include_source=True)
    assert resource_file["properties"]["resource_name"] == "UpdatedAgentResource"
    assert "UpdatedAgentResource" in resource_file["source"]
    expect_resource("res://data/agent_resource.tres").to_have_file_property(
        "resource_name",
        "UpdatedAgentResource",
    )
    variant_resource = godot.resource_duplicate(
        "res://data/agent_resource.tres",
        "res://data/agent_resource_variant.tres",
        properties={"resource_name": "VariantAgentResource"},
    )
    assert variant_resource["source_resource"]["properties"]["resource_name"] == "UpdatedAgentResource"
    assert variant_resource["resource"]["properties"]["resource_name"] == "VariantAgentResource"
    gradient = godot.resource_save(
        "res://data/agent_gradient.tres",
        class_name="Gradient",
        properties={"resource_name": "AgentGradient"},
    )
    resource_classes = godot.resource_classes(name_contains="Gradient", max_results=20)
    assert any(entry["class"] == "GradientTexture1D" for entry in resource_classes["classes"])
    expect_resource_class("GradientTexture1D").to_be_listed()
    gradient_schema = godot.resource_class_describe("GradientTexture1D", properties=["gradient"], storage_only=True)
    assert gradient_schema["properties"][0]["hint_string"] == "Gradient"
    expect_resource_class("GradientTexture1D").to_have_property("gradient", storage=True)
    gradient_texture = godot.resource_save(
        "res://data/agent_gradient_texture.tres",
        class_name="GradientTexture1D",
        properties={
            "resource_name": "AgentGradientTexture",
            "gradient": {
                "$type": "ResourceRef",
                "path": "res://data/agent_gradient.tres",
                "class": "Gradient",
            },
        },
    )
    assert gradient_texture["dependency_state"]["dependency_count"] == 1
    gradient_texture_file = godot.resource_file_describe("res://data/agent_gradient_texture.tres")
    assert gradient_texture_file["ext_resources"][0]["path"] == "res://data/agent_gradient.tres"
    expect_resource("res://data/agent_gradient_texture.tres").to_have_file_ext_resource(
        path="res://data/agent_gradient.tres",
        resource_type="Gradient",
    )
    gradient_references = godot.resource_references(
        "res://data/agent_gradient.tres",
        search_path="res://data",
        resource_type="Gradient",
    )
    assert gradient_references["references"][0]["path"] == "res://data/agent_gradient_texture.tres"
    expect_resource("res://data/agent_gradient.tres").to_be_referenced_by(
        "res://data/agent_gradient_texture.tres",
        search_path="res://data",
        resource_type="Gradient",
    )
    moved_gradient = godot.resource_move(
        "res://data/agent_gradient.tres",
        "res://data/agent_gradient_moved.tres",
        search_path="res://data",
        extensions="tres",
        expected_reference_files=1,
        expected_replacements=1,
    )
    assert moved_gradient["remaining_source_references"]["count"] == 0
    expect_resource("res://data/agent_gradient_moved.tres").to_be_referenced_by(
        "res://data/agent_gradient_texture.tres",
        search_path="res://data",
        resource_type="Gradient",
    )
    inline_gradient = godot.resource_set_properties(
        "res://data/agent_gradient_texture.tres",
        {"gradient": {"$type": "SubResource", "class": "Gradient", "resource_name": "InlineGradient"}},
    )
    assert inline_gradient["resource"]["properties"]["gradient"]["resource_name"] == "InlineGradient"
    expect_resource("res://data/agent_resource.tres").to_have_class("Resource")
    expect_resource("res://data/agent_resource.tres").to_have_property("resource_name", "UpdatedAgentResource")
    import base64

    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    godot.fs_write_bytes("res://assets/generated_pixel.png", png_bytes)
    assert godot.fs_read_bytes("res://assets/generated_pixel.png") == png_bytes
    copied = godot.fs_copy("res://assets/generated_pixel.png", "res://assets/generated_pixel_copy.png")
    assert copied["destination_state"]["type"] == "file"
    moved = godot.fs_move("res://assets/generated_pixel_copy.png", "res://assets/generated_pixel_renamed.png")
    assert moved["source_missing"]["type"] == "missing"
    assert godot.fs_info("res://assets/generated_pixel_renamed.png")["bytes"] == len(png_bytes)
    generated_assets = godot.fs_find("res://assets", extension="png", name_contains="generated")
    assert generated_assets["count"] >= 2
    script_hits = godot.fs_grep("extends", "res://scripts", extension="gd")
    assert script_hits["count"] >= 1
    replaced = godot.fs_replace_text(
        "res://scripts/agent_tool.gd",
        "func generated_value() -> int:\n\treturn 42",
        "func generated_value() -> int:\n\treturn 84",
    )
    assert replaced["replacements"] == 1
    assert replaced["text"].endswith("return 84\n")
    bulk_preview = godot.fs_replace_text_many(
        "var ready := true",
        "var ready := false",
        "res://scripts",
        extension="gd",
        name="agent_state.gd",
    )
    assert bulk_preview["dry_run"]
    bulk_commit = godot.fs_replace_text_many(
        "var ready := true",
        "var ready := false",
        "res://scripts",
        extension="gd",
        name="agent_state.gd",
        expected_files=1,
        expected_replacements=1,
        dry_run=False,
    )
    assert bulk_commit["changes"][0]["text"].endswith("var ready := false\n")
    reimported = godot.resource_reimport("res://assets/generated_pixel.png", force=True)
    assert reimported["editor_filesystem"]["is_file"]
    assert reimported["imports"][0]["generated_files_ready"]
    assert reimported["imports"][0]["missing_generated_file_count"] == 0
    texture = godot.resource_inspect("res://assets/generated_pixel.png", type_hint="Texture2D")
    assert texture["class"].endswith("Texture2D")
    import_metadata = godot.wait_for_import("res://assets/generated_pixel.png", importer="texture", generated_files_ready=True)
    assert import_metadata["importer"] == "texture"
    assert import_metadata["source_file_state"]["exists"]
    assert import_metadata["generated_files_ready"]
    imports = godot.resource_imports("res://assets", importer="texture", generated_files_ready=True)
    assert imports["imports"][0]["path"] == "res://assets/generated_pixel.png"
    expect_resource("res://assets/generated_pixel.png").to_be_imported(importer="texture", generated_files_ready=True)
    expect_resource("res://assets/generated_pixel.png").to_be_import_listed(importer="texture", generated_files_ready=True)
```

Use `@tool` for generated scripts whose methods need to run on editor-scene nodes.

Editor automation can also inspect editor UI controls, drive editor selection,
focus the Inspector, open scripts, and refresh the editor filesystem:

```python
def test_editor_workflow(godot, expect, expect_editor, expect_inspector, expect_script, expect_script_file, expect_filesystem):
    expect(godot.editor_get_by_role("panel")).to_exist()
    assert godot.editor_snapshot(max_depth=1)["class"] == "Panel"
    opened_scene = godot.editor_open_scene("res://scenes/main.tscn")
    assert opened_scene["editor_status"]["edited_scene_file_path"] == "res://scenes/main.tscn"
    expect_editor.to_have_edited_scene("res://scenes/main.tscn")
    expect_editor.to_match_history({"available": True})
    godot.wait_for_editor_history({"can_undo": False})
    selected_player = godot.editor_select("#Player", inspect=True)
    assert selected_player["selection_state"]["count"] == 1
    godot.wait_for_editor_selection("#Player", exact=True)
    expect_editor.to_have_selection("#Player")
    inspected_player = godot.editor_inspect(selector="#Player", property="position")
    assert inspected_player["inspector_state"]["properties"][0]["name"] == "position"
    opened_script = godot.editor_open_script("res://scripts/player.gd", line=12)
    assert opened_script["script_state"]["path"] == "res://scripts/player.gd"
    assert "open_paths" in opened_script["script_editor"]
    if opened_script["opened"]:
        godot.wait_for_editor_script("res://scripts/player.gd", current=True)
    editor_ui = godot.editor_ui_status()
    assert editor_ui["has_base_control"]
    assert "bottom_panel" in editor_ui
    godot.wait_for_editor_ui({"has_base_control": True})
    expect_editor.to_have_base_control()
    expect_editor.to_have_main_screen()
    expect_editor.to_have_bottom_panel_capability(can_hide=True)
    if editor_ui["can_set_main_screen"] and editor_ui["main_screen_name"]:
        godot.editor_switch_main_screen(editor_ui["main_screen_name"])
    if editor_ui["bottom_panel"]["can_hide"]:
        godot.editor_hide_bottom_panel()
    script = godot.editor_script_describe("res://scripts/player.gd")
    assert any(method["name"] == "_ready" for method in script["methods"])
    expect_editor.not_to_be_playing()
    play_state = godot.editor_play("current")
    assert play_state["editor_status"]["playing"]
    expect_editor.to_be_playing("res://scenes/main.tscn")
    stop_state = godot.editor_stop()
    assert not stop_state["editor_status"]["playing"]
    expect_editor.not_to_be_playing()
    assert godot.editor_filesystem_find("res://scripts", extension="gd")["count"] > 0
    scan_state = godot.editor_scan_filesystem("res://scripts/player.gd")
    assert scan_state["filesystem_state"]["path"] == "res://scripts/player.gd"
    selected_script = godot.editor_filesystem_select("res://scripts/player.gd", inspect=True)
    assert selected_script["filesystem_state"]["selected"]
    opened_file = godot.editor_filesystem_open("res://scripts/player.gd", line=12)
    assert opened_file["action"] == "script"
    assert opened_file["script_state"]["path"] == "res://scripts/player.gd"
    godot.wait_for_editor_filesystem_entry("res://scripts/player.gd", resource_type="GDScript")
    godot.wait_for_editor_filesystem_missing("res://scripts/generated/old_tool.gd")
    godot.wait_for_editor_filesystem_find("res://scripts", extension="gd", min_count=1, max_count=10)
    visible_state = godot.inspector("#Player").property("visible").set(False)
    assert visible_state["property_state"]["value"] is False
    expect_inspector(godot.inspector("#Player")).to_have_property("visible", False)
    player_inspector = godot.inspector("#Player")
    inspector_state = player_inspector.set_properties({"visible": True, "tooltip_text": "Ready"})
    assert inspector_state["properties_state"]["tooltip_text"] == "Ready"
    expect_inspector(player_inspector).to_have_properties({"visible": True, "tooltip_text": "Ready"})
    expect_script("res://scripts/player.gd").to_define_function("_ready")
    expect_script_file("res://scripts/player.gd").to_pass_godot_check()
    expect_filesystem("res://scripts/player.gd").to_be_indexed(resource_type="GDScript")
    expect_filesystem("res://scripts/generated/old_tool.gd").not_to_be_indexed()
    expect_filesystem("res://scripts").to_have_indexed_count(1, name="player.gd", extension="gd")
    expect_filesystem("res://scripts").to_contain("player.gd", extension="gd")
    expect_filesystem("res://scripts").not_to_contain("old_tool.gd", extension="gd")
    expect_filesystem("res://scripts/player.gd").to_be_file()
    expect_filesystem("res://scripts/player.gd").not_to_have_text("syntax error")
```

Runtime scene navigation mirrors the shape of browser navigation:

```python
def test_scene_navigation(godot, expect, expect_runtime_scene):
    godot.change_scene("res://scenes/secondary.tscn")
    expect(godot.locator("#SecondaryTitle")).to_have_text("Secondary Scene")
    godot.wait_for_scene("res://scenes/secondary.tscn")
    expect_runtime_scene.to_have_path("res://scenes/secondary.tscn")
    expect_runtime_scene.to_have_name("Secondary")
```

Use `expect_runtime_scene` for retryable assertions over `scene.current`.
The `expect_scene` fixture remains the visual/snapshot assertion helper.

Scene snapshots work in headless mode and are useful for agent-friendly regression
checks:

```python
def test_scene_snapshot(expect_scene):
    expect_scene.to_have_node(name="CounterButton", class_name="Button")
    expect_scene.to_contain_text("Godot Playwright")
    expect_scene.to_match_snapshot("main.scene.json", max_depth=2)
```

When a scene snapshot baseline mismatches, the runner writes both the actual JSON
and a unified diff into the artifacts directory.

Screenshot snapshots are also available through `expect_scene.to_match_screenshot`,
but they require a render-capable Godot session. On mismatch the assertion writes
the actual PNG, a magenta-highlighted diff PNG, and a JSON report with dimensions,
different pixel count, diff ratio, channel deltas, hashes, and tolerance settings.
Use `threshold`, `max_different_pixels`, or `max_diff_ratio` for deliberate render
tolerance. Godot's `--headless` display driver does not expose viewport texture
pixels.

For targeted render checks, screenshot assertions can inspect exact pixels or
small regions without maintaining a full baseline:

```python
def test_render_pixels(expect_scene):
    expect_scene.to_have_pixel(16, 16, "#ffcc00", threshold=2)
    expect_scene.to_have_region_color(0, 0, 32, 32, {"r": 20, "g": 20, "b": 24}, min_ratio=0.95)
```

For audit-friendly visual evidence that should be saved even when there is no
snapshot mismatch, use `expect_scene.inspect_screenshot(...)`. It captures the
actual PNG and writes a sibling `*.visual.json` report with image dimensions,
SHA-256, sampled pixel colors, and optional region summaries:

```python
def test_visual_evidence(expect_scene):
    report = expect_scene.inspect_screenshot(
        "layout.png",
        sample_points=[{"label": "badge", "x": 16, "y": 16}],
        regions=[
            {
                "label": "panel",
                "x": 0,
                "y": 0,
                "width": 160,
                "height": 64,
                "expected_color": "#141418",
                "min_ratio": 0.9,
                "threshold": 3,
            }
        ],
    )
    assert report["ok"]
```

Install the Godot add-on into a project and enable the editor plugin:

```sh
godot-playwright install /path/to/project
```

For runtime automation, also add the autoload:

```sh
godot-playwright install /path/to/project --autoload
```

Launch a headless editor session and keep it running:

```sh
godot-playwright launch /path/to/project --mode editor --port auto
```

In another shell:

```sh
godot-playwright health --port <printed-port>
godot-playwright snapshot --port <printed-port>
godot-playwright rpc engine.info --port <printed-port>
```

`launch` and `smoke` allocate a free port by default. Pass an explicit port only
when another process needs to attach to that known endpoint; `--port` works both
before and after the subcommand.

## Python API

```python
from godot_playwright import Godot, expect

with Godot("examples/basic", mode="runtime", autoload=True) as godot:
    main = godot.locator("#Main")
    title = main.get_by_text("Godot Playwright")
    expect(title).to_exist()
    assert title.get("text") == "Godot Playwright"

    button = main.get_by_test_id("counter-button")
    button.wait_for(state="visible")
    expect(button).to_be_actionable()
    expect(button).to_have_method("get_meta")
    expect(button).to_have_signal("pressed")
    assert button.evaluate('node.get("text")') == "Clicked 0"
    assert main.snapshot(max_depth=2)["name"] == "Main"
    expect(main).to_contain_node(name="CounterButton", class_name="Button")
    expect(main).to_contain_text("Godot Playwright")
    button.wait_for_function('node.get("text") == expected', expected="Clicked 0")
    expect(button).to_match_expression('node.get("text")', "Clicked 0")
    assert button.values(["text", "disabled"]) == {"text": "Clicked 0", "disabled": False}
    update_state = godot.set_node_properties("#CounterButton", {"tooltip_text": "Counter", "disabled": False})
    assert update_state["properties_state"]["tooltip_text"] == "Counter"
    expect(button).to_have_properties({"tooltip_text": "Counter", "disabled": False})
    main.locator("role=button").set_all_properties({"tooltip_text": "Automation-ready"})
    expect(main.locator("role=button")).to_have_all_properties({"tooltip_text": "Automation-ready"})
    metadata_state = godot.set_node_metadata("#CounterButton", {"agent_tag": "counter"})
    assert metadata_state["metadata_state"]["agent_tag"] == "counter"
    button.set_metadata({"generated_by": "godot_playwright"})
    expect(button).to_have_metadata({"agent_tag": "counter"})
    assert godot.locator({"metadata": {"agent_tag": "counter"}}).count() == 1
    button.remove_meta("agent_tag")
    values = button.or_(main.get_by_test_id("next-scene")).call_all_values("get_meta", "test_id", "")
    assert set(values) == {"counter-button", "next-scene"}
    main.get_by_test_id("accept-terms").check()
    main.get_by_test_id("theme-select").select_option({"id": 30})
    main.get_by_test_id("volume-slider").set_value(75)
    main.get_by_test_id("mode-tabs").select_tab({"metadata": {"mode": "telemetry"}})
    main.get_by_test_id("inventory-list").select_item({"metadata": {"kind": "key"}})
    main.get_by_test_id("quest-tree").select_tree_item({"path": ["Cave", "Boss"]})
    expect(main.get_by_test_id("missing")).not_to_exist(timeout=0.2)
    expect(main.locator("role=button").and_(button)).to_have_count(1)
    expect(main.locator("role=button").filter(has_text="Clicked")).to_have_count(1)
    button.click()
    expect(godot.locator("#CounterButton")).to_have_property("text", "Clicked 1")
```

`Locator.wait_for(state=...)` accepts `attached`, `detached`, `visible`, and
`hidden`. `expect(locator)` includes matching positive and negative assertions
such as `to_be_visible()`, `to_be_hidden()`, `not_to_exist()`,
`not_to_have_text()`, `not_to_be_disabled()`, `not_to_have_count()`,
`to_have_count_at_least()`, `to_have_count_at_most()`,
`to_have_count_between()`, `to_be_empty()`, and `not_to_be_empty()`.
`Locator.wait_for_states(...)`, `expect(locator).to_have_state(...)`,
`to_match_state(...)`, `to_be_focusable()`, and `to_receive_input()` expose
arbitrary `node.state` fields for retryable actionability checks.
For collections, `text_contents()`, `wait_for_texts(...)`,
`expect(locator).to_have_texts(...)`, `to_contain_texts(...)`, and
`not_to_have_texts(...)` provide retryable list assertions for menus, item
lists, and repeated controls.
`godot.clock()` exposes Godot's process and physics frame counters, and
`wait_for_process_frames()`, `wait_for_physics_frames()`, and `wait_for_idle()`
wait against those counters for frame-driven game logic.
For deterministic realtime gameplay checks, prefer `pause()`, `step_frames()`,
and `sample_frames()` to large screenshot sequences. They advance exact process
or physics frames and collect compact node/expression state for assertions.
`godot.evaluate()` and `godot.wait_for_function()` run Godot `Expression`
snippets against a root with `tree` and `root` inputs. `Locator.evaluate()` and
`Locator.evaluate_all()` add `node` or `nodes`/`count` inputs, plus any variables
passed from Python, so agents can query and wait on computed live state without
adding project scripts.
`Locator.wait_for_function()` and `expect(locator).to_match_expression()` poll
node-scoped expressions, which keeps agent checks retryable without writing a
manual loop.
`Locator.methods()`, `Locator.signals()`, `to_have_method()`, and
`to_have_signal()` expose node capabilities for generated script and signal
verification.
`expect(locator).to_match_node(...)`, `not_to_match_node(...)`,
`to_have_parent(...)`, `to_have_index(...)`, and `to_have_child_count(...)`
poll `node.describe` for retryable scene-tree structure assertions after
generated edits.
`Locator.snapshot()`, `snapshot_nodes()`, `snapshot_texts()`,
`to_contain_node()`, and `to_contain_text()` inspect and assert over a locator's
subtree without snapshotting the whole scene.
`Locator.values()`, `Locator.set_properties()`, and
`Locator.set_all_properties()` provide batch node property reads/writes, with
`to_have_properties()` and `to_have_all_properties()` assertions for stable
multi-field checks.
`godot.set_node_metadata()` and `godot.remove_node_metadata()` auto-wait for
metadata readback and return `metadata_state`; `wait_for_node_meta()` and
`wait_for_node_metadata()` expose the same waits directly. Locator
`metadata()`, `set_meta()`, `set_metadata()`, and `remove_meta()` helpers wait
before returning the locator for chaining. Pass `wait=False` for fire-and-forget
writes. `to_have_meta()` and `to_have_metadata()` assertions cover agent-owned
tags and stable `get_by_test_id()` selectors.
`Locator.call_all()` and `call_all_values()` invoke a Godot method across every
matched node and return per-node results, useful for batch probes and generated
node verification.
`Locator.bounds()`, `center()`, `wait_for_bounds()`, `wait_for_position()`,
`wait_for_size()`, and `wait_for_center()` expose live 2D geometry, with
`expect(locator).to_have_bounds(...)`, `to_have_position(...)`,
`to_have_size(...)`, `to_have_center(...)`, and `to_be_within_viewport()` for
retryable layout assertions.
Checkable controls support `check()`, `uncheck()`, and `set_checked()` with
`to_be_checked()` / `not_to_be_checked()` assertions.
OptionButton controls support `select_option()` by text, index, or item id, and
the selected text is exposed through `input_value()` / `to_have_value()`.
Range controls such as sliders and spin boxes support `set_value()`, with their
numeric value exposed through the same value assertions.
TabBar and TabContainer controls support `select_tab()` by title, index, or tab
metadata, and the selected tab title is exposed through the same value
assertions.
ItemList controls support `select_item()` by text, index, or item metadata. A
single selected item is exposed as a string value; multiple selected items are
exposed as a list of strings.
Tree controls support `select_tree_item()` by text, flat index, text path, or
cell metadata. Selected tree item text is exposed through value assertions, with
multi-selection surfaced as a list of strings.

## Protocol

The add-on listens on `127.0.0.1:9777` by default, and falls back to an available
port when that default is already occupied. Override this with:

- `GODOT_PLAYWRIGHT_HOST`
- `GODOT_PLAYWRIGHT_PORT`
- `GODOT_PLAYWRIGHT_STRICT_PORT=1` to fail instead of falling back

See [docs/protocol.md](docs/protocol.md) for the current RPC surface.

## Current Scope

This is a working foundation, not the full end state. The next major steps toward a
true Playwright-grade Godot agent harness are broader editor UI control coverage,
deeper test runner integration, and more domain-specific game/editor assertions.
