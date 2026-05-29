# godot-playwright Workflow for AI Agents

Use this guide when the harness includes `godot-playwright` / `godot-cli`.

`godot-playwright` gives an agent a Playwright-like way to inspect, edit, run, and test Godot projects. Treat it as the primary feedback loop for generated Godot work.

## Setup assumptions

The package may already be installed in the harness. If not, from a checkout of the project:

```bash
python -m pip install -e /path/to/godot-cli
```

Install the Godot add-on into a target project:

```bash
godot-playwright install /path/to/project
```

For runtime automation, also install the runtime autoload:

```bash
godot-playwright install /path/to/project --autoload
```

Create a clean starter project for experiments:

```bash
godot-playwright init /tmp/agent-game --name AgentGame
godot-playwright smoke /tmp/agent-game --mode runtime
godot-playwright smoke /tmp/agent-game --mode editor
godot-playwright validate /tmp/agent-game --exclude "addons/**"
```

## Agent loop

### 1. Inventory before edits

```bash
godot-playwright inspect-project /path/to/project --exclude "addons/**" --json
```

Use the inventory to learn:

- Godot version and project path if available.
- Main scene.
- Autoload names and paths.
- Export presets.
- Scene/script/resource counts.
- Large or hot directories.
- Recent files.

### 2. Static checks before launch

```bash
godot-playwright check-scripts /path/to/project res:// --exclude "addons/**"
godot-playwright check-resources /path/to/project res:// --exclude "addons/**"
```

Use targeted checks for fast iteration:

```bash
godot-playwright check-script /path/to/project res://features/player/player.gd
godot-playwright inspect-scene /path/to/project res://features/player/player.tscn --json
```

### 3. Runtime probe

Probe the scene most likely to break:

```bash
godot-playwright probe /path/to/project --scene res://features/player/player.tscn
```

Probe all scenes after broad refactors:

```bash
godot-playwright probe-scenes /path/to/project res://scenes --exclude "addons/**"
```

### 4. Live automation

Launch a headless editor or runtime server:

```bash
godot-playwright launch /path/to/project --mode editor --port auto
godot-playwright health --port PRINTED_PORT
godot-playwright snapshot --port PRINTED_PORT
godot-playwright rpc protocol.describe --port PRINTED_PORT
```

Use `protocol.describe` to check what methods are supported by the installed add-on before calling newer helpers.
Use an explicit fixed port only when another process must connect to that exact port. Parallel audits should go through `godot-playwright` commands so the tool can isolate ports and XDG user data.
When paths are uncertain, call `node.find` or use semantic locators before acting; generated scene roots are not always `/root/Main`.

### 5. Test

```bash
godot-playwright test /path/to/project tests --trace retain-on-failure --screenshots only-on-failure
```

Narrow tests while iterating:

```bash
godot-playwright test /path/to/project tests --grep "inventory|pause" --trace retain-on-failure
```

Use shards or workers only when the test suite is large and isolation requirements are understood.

## Writing Python automation tests

### Runtime UI test

```python
def test_pause_menu_resume(godot, expect):
    godot.press("Escape")
    menu = godot.get_by_test_id("pause-menu")
    expect(menu).to_be_visible()

    resume = menu.get_by_test_id("pause-resume")
    expect(resume).to_be_actionable()
    resume.click()

    expect(menu).to_be_hidden()
```

### Scene snapshot test

```python
def test_inventory_scene_structure(expect_scene):
    expect_scene.to_have_node(name="InventoryScreen", class_name="Control")
    expect_scene.to_have_node(name="CloseButton", class_name="Button")
    expect_scene.to_match_snapshot("inventory.scene.json", max_depth=3)
```

### Signal test

```python
def test_start_button_emits(godot, expect_signal):
    button = godot.get_by_test_id("start-button")
    expect_signal("#StartButton", "pressed").to_have_event(action=button.click)
```

### Property and state test

```python
def test_health_bar_updates(godot, expect):
    player = godot.locator("#Player")
    hud = godot.get_by_test_id("player-hud")

    player.call("apply_damage", 10)

    health_bar = hud.get_by_test_id("health-bar")
    expect(health_bar).to_have_property("value", 90.0)
```

### Physics query test

```python
def test_player_collision(godot, expect_physics2d):
    expect_physics2d.to_have_point_collision(120, 240, name="Player")
```

## Selector strategy

Prefer stable semantic selectors in this order:

1. `get_by_test_id("...")` using node metadata.
2. `get_by_role("button", name="Start")` for Control-based UI.
3. `locator("#NodeName")` for stable scene node names.
4. `locator("type=Player")` or class/type selectors when names vary.
5. Property/metadata dictionaries for advanced cases.

Add `test_id` metadata when creating important UI nodes:

```gdscript
func _ready() -> void:
    %StartButton.set_meta("test_id", "start-button")
```

Or set it during editor scene creation through the protocol when available.

## What to assert

Prefer assertions that match gameplay intent:

- Node exists/visible/enabled/actionable.
- Text/value/property changed.
- Signal emitted.
- Scene changed.
- Resource dependency exists.
- Physics query collides with expected object.
- Animation is present or playing.
- Save data was attached as JSON artifact.

Use screenshots only for layout/visual regressions. Headless display drivers may not expose viewport pixels, so screenshot failures should not obscure the primary logic failure. For real-time gameplay, prefer `runtime.sample_frames` with selectors/expressions or explicit pause/step/resume control over continuous screenshot capture.
If a visual check requires a fixed viewport, set the viewport size and wait for `viewport.info` / `wait_for_viewport_size` to report the intended size before capturing.

## Avoid fragile tests

Avoid:

```python
import time

time.sleep(1)
assert godot.locator("#Button").get("text") == "OK"
```

Prefer retryable expectations:

```python
button = godot.locator("#Button")
expect(button).to_have_text("OK")
```

Avoid raw pixel checks for gameplay logic. Use node state, properties, signals, physics, or scene snapshots.

## Editor authoring workflows

When editing scenes through automation:

```python
def test_create_status_scene(godot, expect_scene_file):
    godot.editor_new_scene(class_name="Control", name="StatusScene")
    godot.create_node("edited", "Label", name="StatusLabel")
    godot.set_node_properties("#StatusLabel", {"text": "Ready"})
    godot.editor_save_scene("res://ui/status_scene.tscn")

    expect_scene_file("res://ui/status_scene.tscn").to_have_node(
        name="StatusLabel",
        class_name="Label",
    )
```

When attaching scripts:

```python
godot.write_script(
    "res://ui/status_label.gd",
    "class_name StatusLabel\nextends Label\n\nfunc set_status(text: String) -> void:\n\tself.text = text\n",
    extends="Label",
    functions=["set_status"],
)
godot.attach_script("#StatusLabel", "res://ui/status_label.gd")
```

Always follow editor authoring with:

```bash
godot-playwright check-script /path/to/project res://ui/status_label.gd
godot-playwright inspect-scene /path/to/project res://ui/status_scene.tscn --json
godot-playwright check-resources /path/to/project res://ui
```

## Moving resources safely

Use resource-aware move operations when possible. Scenes and Resources contain external references that must be updated.

Bad:

```bash
mv res://data/old_item.tres res://items/new_item.tres
```

Better through automation helpers if available:

```python
godot.resource_move(
    "res://data/old_item.tres",
    "res://items/new_item.tres",
    search_path="res://",
    extensions="tscn,tres,gd",
)
```

Then check references:

```bash
godot-playwright check-resources /path/to/project res:// --exclude "addons/**"
```

## CI gate suggestion

For AI-generated PRs, use a validation sequence like:

```bash
godot-playwright inspect-project "$PROJECT" --exclude "addons/**" --json > build/project_inventory.json
godot-playwright check-scripts "$PROJECT" res:// --exclude "addons/**"
godot-playwright check-resources "$PROJECT" res:// --exclude "addons/**"
godot-playwright validate "$PROJECT" --exclude "addons/**"
godot-playwright test "$PROJECT" tests --retries 1 --trace retain-on-failure --junit-xml build/junit.xml
```

For small projects, `validate` may be enough. For large projects, narrow to changed paths and affected scenes first, then run broader gates before final delivery.

## Debugging failures

When a test fails:

1. Read the structured result JSON and linked trace/log artifacts.
2. Check Godot stdout/stderr for script parse errors, missing resources, and runtime errors.
3. Use scene snapshots to inspect actual node tree.
4. Use `protocol.describe` to verify helper availability.
5. Reproduce with a narrowed `--grep` and `--trace retain-on-failure`.
6. If input stops working after frame stepping, call `runtime.resume` before injecting input.
7. Prefer fixing the project behavior or selector stability over adding sleeps.

## Agent reporting format

After validation, report:

```text
Validated with:
- godot-playwright check-script ...: passed
- godot-playwright inspect-scene ...: passed
- godot-playwright probe ...: passed

Evidence:
- Scene contains StatusLabel with script res://ui/status_label.gd
- Runtime logs contain no errors/warnings from changed scene
```

If a validation step cannot be run, say exactly why and include the command the user should run locally.
