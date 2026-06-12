# Gameplay Events Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an installable `gameplay_events` gameplay module that provides a Resource-driven event bus for Godot projects.

**Architecture:** Follow the existing gameplay module pattern: source module under `gameplay_modules/gameplay_events`, bundled mirror under `godot_playwright/bundled_gameplay_modules/gameplay_events`, no Autoload, deterministic demo, copied Python demo test, JSON-compatible payload/state, and structured result dictionaries for expected failures. Static authoring data lives in `EventDefinition` and `EventDatabase`; runtime dispatch, queue, subscriptions, history, and save state live in `GameplayEventBus`.

**Tech Stack:** Python `unittest`, `godot-playwright` module installer, Godot 4.6 GDScript, `.tres` Resource files, `.tscn` demo scene, package data in `pyproject.toml`.

---

## File Structure

Create:

- `gameplay_modules/gameplay_events/module.json` - module manifest for installer copy/demo behavior.
- `gameplay_modules/gameplay_events/README.md` - human-facing usage documentation.
- `gameplay_modules/gameplay_events/AGENT.md` - agent-facing wiring and boundary instructions.
- `gameplay_modules/gameplay_events/addons/gameplay_events/gameplay_event_constants.gd` - schema/module constants, save group name, and event names.
- `gameplay_modules/gameplay_events/addons/gameplay_events/gameplay_event_result.gd` - shared result dictionary helpers.
- `gameplay_modules/gameplay_events/addons/gameplay_events/event_definition.gd` - editor-authored event definition Resource.
- `gameplay_modules/gameplay_events/addons/gameplay_events/event_database.gd` - event definition registry and validation Resource.
- `gameplay_modules/gameplay_events/addons/gameplay_events/gameplay_event_bus.gd` - runtime event bus Node.
- `gameplay_modules/gameplay_events/demo/resources/item_collected.tres` - demo event definition.
- `gameplay_modules/gameplay_events/demo/resources/door_opened.tres` - demo event definition.
- `gameplay_modules/gameplay_events/demo/resources/quest_progressed.tres` - demo event definition.
- `gameplay_modules/gameplay_events/demo/resources/event_database.tres` - demo event database Resource.
- `gameplay_modules/gameplay_events/demo/scenes/gameplay_events_demo.tscn` - deterministic demo scene.
- `gameplay_modules/gameplay_events/demo/scripts/gameplay_events_demo.gd` - demo assertions exposed through `run_gameplay_events_demo()`.
- `gameplay_modules/gameplay_events/tests/test_gameplay_events_demo.py` - copied demo test.
- `godot_playwright/bundled_gameplay_modules/gameplay_events/` - bundled mirror, byte-identical to `gameplay_modules/gameplay_events/`.

Modify:

- `tests/test_modules.py` - installer tests, source-shape tests, demo install/runtime tests, package-data assertions, mirror assertions.
- `pyproject.toml` - include bundled gameplay events package data.
- `README.md` - list gameplay events install/demo commands and short module summary.

Do not modify:

- `godot_playwright/modules.py` - the manifest-driven installer should discover the module automatically.
- Existing gameplay modules.

---

### Task 1: Add Installer Tests And Minimal Module Shell

**Files:**
- Modify: `tests/test_modules.py`
- Create: `gameplay_modules/gameplay_events/module.json`
- Create: `gameplay_modules/gameplay_events/README.md`
- Create: `gameplay_modules/gameplay_events/AGENT.md`
- Create: `gameplay_modules/gameplay_events/addons/gameplay_events/gameplay_event_constants.gd`
- Create: `gameplay_modules/gameplay_events/addons/gameplay_events/gameplay_event_result.gd`
- Create: `gameplay_modules/gameplay_events/addons/gameplay_events/event_definition.gd`
- Create: `gameplay_modules/gameplay_events/addons/gameplay_events/event_database.gd`
- Create: `gameplay_modules/gameplay_events/addons/gameplay_events/gameplay_event_bus.gd`

- [ ] **Step 1: Write failing installer tests**

In `tests/test_modules.py`, add this test near the repository module discovery tests:

```python
    def test_repository_gameplay_events_module_is_discoverable(self) -> None:
        modules = list_modules()
        gameplay_events = next(module for module in modules if module["name"] == "gameplay_events")
        self.assertEqual(gameplay_events["version"], "0.1.0")
        self.assertEqual(gameplay_events["godot_version"], ">=4.6")
        self.assertEqual(gameplay_events["autoloads"], [])
```

Add this test near the base copy tests:

```python
    def test_add_gameplay_events_module_copies_files_without_autoload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "gameplay_events")

            self.assertTrue(report["ok"], report)
            self.assertFalse(report["demo"])
            self.assertEqual(report["module"], "gameplay_events")
            self.assertEqual(report["autoloads"], [])
            expected_scripts = {
                "gameplay_event_constants.gd",
                "gameplay_event_result.gd",
                "event_definition.gd",
                "event_database.gd",
                "gameplay_event_bus.gd",
            }
            for script_name in expected_scripts:
                self.assertTrue((project / "addons" / "gameplay_events" / script_name).exists(), script_name)
            project_text = (project / "project.godot").read_text(encoding="utf-8")
            self.assertNotIn("GameplayEventService", project_text)
            copied_targets = {entry["target"] for entry in report["copied"]}
            self.assertTrue(
                {f"res://addons/gameplay_events/{script_name}" for script_name in expected_scripts}.issubset(copied_targets),
                copied_targets,
            )
```

- [ ] **Step 2: Run the installer tests to verify they fail**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_repository_gameplay_events_module_is_discoverable tests.test_modules.ModuleInstallerUnitTests.test_add_gameplay_events_module_copies_files_without_autoload
```

Expected: error or failure because `gameplay_events` is not discoverable.

- [ ] **Step 3: Create the minimal module shell**

Create directories:

```sh
mkdir -p gameplay_modules/gameplay_events/addons/gameplay_events
```

Create `gameplay_modules/gameplay_events/module.json`:

```json
{
  "name": "gameplay_events",
  "version": "0.1.0",
  "display_name": "Gameplay Events",
  "description": "Resource-driven gameplay event bus for Godot projects.",
  "godot_version": ">=4.6",
  "copy": [
    {"from": "addons/gameplay_events", "to": "addons/gameplay_events"}
  ],
  "autoloads": [],
  "validation": {
    "commands": [
      "godot-playwright check-scripts /path/to/project res://addons/gameplay_events --exclude addons/godot_playwright/**",
      "godot-playwright check-resources /path/to/project res://addons/gameplay_events --exclude addons/godot_playwright/**"
    ]
  }
}
```

Create `gameplay_modules/gameplay_events/README.md`:

````markdown
# Gameplay Events Gameplay Module

`gameplay_events` adds a Resource-driven gameplay event bus for Godot 4.6+ projects.

Install into a Godot project:

```sh
godot-playwright module add /path/to/project gameplay_events
```

The installer copies `res://addons/gameplay_events/`. It does not register an Autoload.
````

Create `gameplay_modules/gameplay_events/AGENT.md`:

````markdown
# Agent Instructions: gameplay_events

Use this module when a Godot project needs a reusable gameplay event bus for cross-system announcements.

Install with:

```sh
godot-playwright module add /path/to/project gameplay_events
```

Do not assume a global Autoload unless the project created one. Add a `GameplayEventBus` node to the scene that owns the event routing.
````

Create `gameplay_modules/gameplay_events/addons/gameplay_events/gameplay_event_constants.gd`:

```gdscript
class_name GameplayEventConstants
extends RefCounted

const SAVE_GROUP: StringName = &"save_participants"
const SCHEMA_VERSION: int = 1
const MODULE_VERSION: String = "0.1.0"

const EVENT_EMITTED: String = "event_emitted"
const EVENT_QUEUED: String = "event_queued"
const EVENT_FAILED: String = "event_failed"
const EVENT_QUEUE_FLUSHED: String = "queue_flushed"
const EVENT_QUEUE_CLEARED: String = "queue_cleared"
const EVENT_HISTORY_CLEARED: String = "history_cleared"
const EVENT_STATE_APPLIED: String = "state_applied"
```

Create `gameplay_modules/gameplay_events/addons/gameplay_events/gameplay_event_result.gd`:

```gdscript
class_name GameplayEventResult
extends RefCounted


static func make(ok: bool = true, event_id: String = "") -> Dictionary:
	return {
		"ok": ok,
		"event_id": event_id,
		"payload": {},
		"event": {},
		"subscriber_count": 0,
		"events": [],
		"warnings": [],
		"errors": [],
	}


static func add_event(result: Dictionary, event: Dictionary) -> void:
	(result["events"] as Array).append(event)


static func add_warning(result: Dictionary, message: String) -> void:
	(result["warnings"] as Array).append(message)


static func add_error(result: Dictionary, message: String) -> void:
	result["ok"] = false
	(result["errors"] as Array).append(message)
```

Create minimal public classes for the remaining scripts:

```gdscript
# event_definition.gd
class_name EventDefinition
extends Resource

@export var event_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export var default_payload: Dictionary = {}
@export var record_by_default: bool = true
```

```gdscript
# event_database.gd
class_name EventDatabase
extends Resource

@export var events: Array[Resource] = []
```

```gdscript
# gameplay_event_bus.gd
class_name GameplayEventBus
extends Node

@export var database: Resource
@export var save_id: StringName
@export var record_history: bool = true
@export_range(0, 10000, 1) var max_history: int = 100
@export var save_history: bool = false
@export var auto_flush: bool = false
@export_range(0, 10000, 1) var auto_flush_limit: int = 0
```

- [ ] **Step 4: Run the installer tests to verify they pass**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_repository_gameplay_events_module_is_discoverable tests.test_modules.ModuleInstallerUnitTests.test_add_gameplay_events_module_copies_files_without_autoload
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

```sh
git add tests/test_modules.py gameplay_modules/gameplay_events
git commit -m "Add gameplay events module shell"
```

---

### Task 2: Implement Event Definitions, Database, Constants, And Result Helpers

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `gameplay_modules/gameplay_events/addons/gameplay_events/gameplay_event_constants.gd`
- Modify: `gameplay_modules/gameplay_events/addons/gameplay_events/gameplay_event_result.gd`
- Modify: `gameplay_modules/gameplay_events/addons/gameplay_events/event_definition.gd`
- Modify: `gameplay_modules/gameplay_events/addons/gameplay_events/event_database.gd`

- [ ] **Step 1: Write source-shape tests for Resource helpers**

In `tests/test_modules.py`, add this test near the existing `test_quests_source_defines_resource_helpers` test:

```python
    def test_gameplay_events_source_defines_resource_helpers(self) -> None:
        source_root = default_module_roots()[0]
        events_root = source_root / "gameplay_events" / "addons" / "gameplay_events"
        definition = (events_root / "event_definition.gd").read_text(encoding="utf-8")
        database = (events_root / "event_database.gd").read_text(encoding="utf-8")
        result = (events_root / "gameplay_event_result.gd").read_text(encoding="utf-8")
        constants = (events_root / "gameplay_event_constants.gd").read_text(encoding="utf-8")

        self.assertIn("class_name EventDefinition", definition)
        self.assertIn("@export var event_id: StringName", definition)
        self.assertIn("@export var display_name: String", definition)
        self.assertIn("@export_multiline var description: String", definition)
        self.assertIn("@export var tags: Array[StringName] = []", definition)
        self.assertIn("@export var default_payload: Dictionary = {}", definition)
        self.assertIn("@export var record_by_default: bool = true", definition)
        self.assertIn("class_name EventDatabase", database)
        self.assertIn('EventDefinitionData := preload("res://addons/gameplay_events/event_definition.gd")', database)
        self.assertIn('GameplayEventResultData := preload("res://addons/gameplay_events/gameplay_event_result.gd")', database)
        self.assertIn("@export var events: Array[Resource] = []", database)
        self.assertIn("func get_event(event_id: String) -> Resource", database)
        self.assertIn("func has_event(event_id: String) -> bool", database)
        self.assertIn("func get_event_ids() -> Array[String]", database)
        self.assertIn("func get_events() -> Array", database)
        self.assertIn("func validate() -> Dictionary", database)
        self.assertIn("events[%d] is null", database)
        self.assertIn("must be an EventDefinition", database)
        self.assertIn("event_id must be non-empty", database)
        self.assertIn("must not contain leading or trailing whitespace", database)
        self.assertIn("Duplicate event_id", database)
        self.assertIn("default_payload must be JSON-compatible", database)
        self.assertIn("_is_json_compatible", database)
        self.assertIn("class_name GameplayEventResult", result)
        self.assertIn('"event_id": event_id', result)
        self.assertIn('"payload": {}', result)
        self.assertIn('"event": {}', result)
        self.assertIn('"subscriber_count": 0', result)
        self.assertIn('"events": []', result)
        self.assertIn("static func add_event", result)
        self.assertIn("static func add_warning", result)
        self.assertIn("static func add_error", result)
        self.assertIn("const SCHEMA_VERSION: int = 1", constants)
        self.assertIn('const EVENT_EMITTED: String = "event_emitted"', constants)
        self.assertIn('const EVENT_QUEUED: String = "event_queued"', constants)
        self.assertIn('const EVENT_FAILED: String = "event_failed"', constants)
```

- [ ] **Step 2: Run the source-shape test to verify it fails**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_gameplay_events_source_defines_resource_helpers
```

Expected: failure because `event_database.gd` does not define lookup, validation, and JSON compatibility helpers yet.

- [ ] **Step 3: Implement `event_database.gd`**

Replace `gameplay_modules/gameplay_events/addons/gameplay_events/event_database.gd` with:

```gdscript
class_name EventDatabase
extends Resource

const EventDefinitionData := preload("res://addons/gameplay_events/event_definition.gd")
const GameplayEventResultData := preload("res://addons/gameplay_events/gameplay_event_result.gd")

@export var events: Array[Resource] = []


func get_event(event_id: String) -> Resource:
	var normalized := event_id.strip_edges()
	for event in events:
		if event == null:
			continue
		if not event is EventDefinitionData:
			continue
		if String(event.event_id).strip_edges() == normalized:
			return event
	return null


func has_event(event_id: String) -> bool:
	return get_event(event_id) != null


func get_event_ids() -> Array[String]:
	var ids: Array[String] = []
	for event in events:
		if event == null:
			continue
		if not event is EventDefinitionData:
			continue
		var event_id := String(event.event_id).strip_edges()
		if not event_id.is_empty():
			ids.append(event_id)
	return ids


func get_events() -> Array:
	var copied: Array = []
	for event in events:
		if event != null and event is EventDefinitionData:
			copied.append(event)
	return copied


func validate() -> Dictionary:
	var result := GameplayEventResultData.make(true)
	var seen := {}
	for index in range(events.size()):
		var event: Resource = events[index]
		if event == null:
			GameplayEventResultData.add_error(result, "events[%d] is null" % index)
			continue
		if not event is EventDefinitionData:
			GameplayEventResultData.add_error(result, "events[%d] must be an EventDefinition" % index)
			continue
		var raw_event_id := String(event.event_id)
		var normalized := raw_event_id.strip_edges()
		if normalized.is_empty():
			GameplayEventResultData.add_error(result, "events[%d].event_id must be non-empty" % index)
			continue
		if normalized != raw_event_id:
			GameplayEventResultData.add_error(result, "events[%d].event_id must not contain leading or trailing whitespace" % index)
			continue
		if seen.has(normalized):
			GameplayEventResultData.add_error(result, "Duplicate event_id: %s" % normalized)
			continue
		seen[normalized] = true
		if not _is_json_compatible(event.default_payload):
			GameplayEventResultData.add_error(result, "events[%d].default_payload must be JSON-compatible" % index)
	return result


func _is_json_compatible(value: Variant, seen: Array = []) -> bool:
	var value_type := typeof(value)
	if value == null:
		return true
	if value_type == TYPE_BOOL or value_type == TYPE_INT or value_type == TYPE_STRING or value_type == TYPE_STRING_NAME:
		return true
	if value_type == TYPE_FLOAT:
		var number := float(value)
		return not is_nan(number) and not is_inf(number)
	if value is Array:
		if _contains_same_container(seen, value):
			return false
		seen.append(value)
		for item in value:
			if not _is_json_compatible(item, seen):
				seen.pop_back()
				return false
		seen.pop_back()
		return true
	if value is Dictionary:
		if _contains_same_container(seen, value):
			return false
		seen.append(value)
		for key in value.keys():
			if typeof(key) != TYPE_STRING and typeof(key) != TYPE_STRING_NAME:
				seen.pop_back()
				return false
			if not _is_json_compatible(value[key], seen):
				seen.pop_back()
				return false
		seen.pop_back()
		return true
	return false


func _contains_same_container(containers: Array, value: Variant) -> bool:
	for container in containers:
		if is_same(container, value):
			return true
	return false
```

- [ ] **Step 4: Run the source-shape test to verify it passes**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_gameplay_events_source_defines_resource_helpers
```

Expected: pass.

- [ ] **Step 5: Commit**

```sh
git add tests/test_modules.py gameplay_modules/gameplay_events/addons/gameplay_events
git commit -m "Add gameplay event resource helpers"
```

---

### Task 3: Implement Synchronous Dispatch And Subscriptions

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `gameplay_modules/gameplay_events/addons/gameplay_events/gameplay_event_bus.gd`

- [ ] **Step 1: Write source-shape tests for the bus API**

In `tests/test_modules.py`, add this test near the other container/log API tests:

```python
    def test_gameplay_events_source_defines_bus_api(self) -> None:
        source_root = default_module_roots()[0]
        bus = (source_root / "gameplay_events" / "addons" / "gameplay_events" / "gameplay_event_bus.gd").read_text(
            encoding="utf-8"
        )

        self.assertIn("class_name GameplayEventBus", bus)
        self.assertIn("@export var database: Resource", bus)
        self.assertIn("@export var save_id: StringName", bus)
        self.assertIn("@export var record_history: bool = true", bus)
        self.assertIn("@export_range(0, 10000, 1) var max_history: int = 100", bus)
        self.assertIn("@export var save_history: bool = false", bus)
        self.assertIn("@export var auto_flush: bool = false", bus)
        self.assertIn("@export_range(0, 10000, 1) var auto_flush_limit: int = 0", bus)
        self.assertIn("signal event_emitted", bus)
        self.assertIn("signal event_queued", bus)
        self.assertIn("signal event_failed", bus)
        self.assertIn("signal queue_flushed", bus)
        self.assertIn("signal events_changed", bus)
        self.assertIn("func emit_event(event_id: String, payload: Dictionary = {}) -> Dictionary", bus)
        self.assertIn("func subscribe(event_id: String, target: Object, method: StringName) -> Dictionary", bus)
        self.assertIn("func unsubscribe(event_id: String, target: Object, method: StringName) -> Dictionary", bus)
        self.assertIn("func clear_subscribers(event_id: String = \"\") -> void", bus)
        self.assertIn("func has_event(event_id: String) -> bool", bus)
        self.assertIn("func get_event_definition(event_id: String) -> Resource", bus)
        self.assertIn("func get_event_ids() -> Array[String]", bus)
        self.assertIn("_subscribers_by_event_id", bus)
        self.assertIn("_make_event", bus)
        self.assertIn("_dispatch_event", bus)
        self.assertIn("_is_json_compatible", bus)
```

- [ ] **Step 2: Run the bus source-shape test to verify it fails**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_gameplay_events_source_defines_bus_api
```

Expected: failure because `gameplay_event_bus.gd` does not define runtime API yet.

- [ ] **Step 3: Implement bus exports, signals, public query methods, synchronous dispatch, and subscriptions**

Update `gameplay_event_bus.gd` so it contains these public members and internal storage:

```gdscript
class_name GameplayEventBus
extends Node

const GameplayEventConstantsData := preload("res://addons/gameplay_events/gameplay_event_constants.gd")
const GameplayEventResultData := preload("res://addons/gameplay_events/gameplay_event_result.gd")

signal event_emitted(event_id: String, event: Dictionary, result: Dictionary)
signal event_queued(event_id: String, event: Dictionary, result: Dictionary)
signal event_failed(event_id: String, result: Dictionary)
signal queue_flushed(events: Array)
signal events_changed(event: Dictionary)

@export var database: Resource
@export var save_id: StringName
@export var record_history: bool = true
@export_range(0, 10000, 1) var max_history: int = 100
@export var save_history: bool = false
@export var auto_flush: bool = false
@export_range(0, 10000, 1) var auto_flush_limit: int = 0

var _sequence: int = 0
var _queue: Array[Dictionary] = []
var _history: Array[Dictionary] = []
var _subscribers_by_event_id: Dictionary = {}
```

Implement the public methods listed in the Task 3 test. Queue, history, and state APIs are added in Task 4 so this task can stay focused on immediate dispatch and runtime subscribers.

Implement `emit_event()` with this behavior:

```gdscript
func emit_event(event_id: String, payload: Dictionary = {}) -> Dictionary:
	var normalized := event_id.strip_edges()
	var result := GameplayEventResultData.make(true, normalized)
	var event := _make_event(normalized, payload, false, result)
	if not bool(result.get("ok", false)):
		event_failed.emit(normalized, result)
		return result
	return _dispatch_event(event, result)
```

Implement `subscribe()` and `unsubscribe()` with one-argument listener callbacks:

```gdscript
func subscribe(event_id: String, target: Object, method: StringName) -> Dictionary:
	var normalized := event_id.strip_edges()
	var result := GameplayEventResultData.make(true, normalized)
	if not _validate_event_id(result, normalized):
		return result
	if target == null:
		GameplayEventResultData.add_error(result, "target must be non-null")
		return result
	if String(method).strip_edges().is_empty():
		GameplayEventResultData.add_error(result, "method must be non-empty")
		return result
	if not target.has_method(method):
		GameplayEventResultData.add_error(result, "target does not have method: %s" % String(method))
		return result
	var subscribers: Array = _subscribers_by_event_id.get(normalized, [])
	for subscriber in subscribers:
		if subscriber.get("target") == target and subscriber.get("method") == method:
			GameplayEventResultData.add_warning(result, "Duplicate subscription ignored: %s.%s" % [normalized, String(method)])
			return result
	subscribers.append({"target": target, "method": method})
	_subscribers_by_event_id[normalized] = subscribers
	return result
```

Use these required private helpers:

```gdscript
func _validate_event_id(result: Dictionary, event_id: String) -> bool
func _validate_database(result: Dictionary) -> bool
func _make_event(event_id: String, payload: Dictionary, queued: bool, result: Dictionary) -> Dictionary
func _dispatch_event(event: Dictionary, result: Dictionary) -> Dictionary
func _record_history(event: Dictionary, definition: Resource) -> void
func _copy_event(event: Dictionary) -> Dictionary
func _is_json_compatible(value: Variant, seen: Array = []) -> bool
```

The helper behavior must match the approved spec:

- Empty event IDs fail with `event_id must be non-empty`.
- Missing database fails with `database must be assigned`.
- Unknown event IDs fail with `Unknown event_id: <id>`.
- Non-JSON payloads fail with `payload must be JSON-compatible`.
- Default payload is copied first, caller payload overrides it.
- `_dispatch_event()` emits `event_emitted`, calls every subscriber registered for the event ID, records subscriber errors without skipping remaining subscribers, emits `event_failed` if the final result is failed, emits `events_changed`, and returns the result.
- Subscriber callbacks receive exactly one `Dictionary` argument.

- [ ] **Step 4: Run the bus source-shape test to verify it passes**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_gameplay_events_source_defines_bus_api
```

Expected: pass.

- [ ] **Step 5: Commit**

```sh
git add tests/test_modules.py gameplay_modules/gameplay_events/addons/gameplay_events/gameplay_event_bus.gd
git commit -m "Add gameplay event bus dispatch API"
```

---

### Task 4: Implement Queue, History, State Import/Export, And Save Wrappers

**Files:**
- Modify: `gameplay_modules/gameplay_events/addons/gameplay_events/gameplay_event_bus.gd`
- Modify: `tests/test_modules.py`

- [ ] **Step 1: Add source-shape assertions for queue/state details**

Extend `test_gameplay_events_source_defines_bus_api` with these assertions:

```python
        self.assertIn("func queue_event(event_id: String, payload: Dictionary = {}) -> Dictionary", bus)
        self.assertIn("func flush_events(limit: int = 0) -> Array[Dictionary]", bus)
        self.assertIn("func clear_queue() -> void", bus)
        self.assertIn("func get_history(limit: int = 0) -> Array", bus)
        self.assertIn("func clear_history() -> void", bus)
        self.assertIn("func get_state() -> Dictionary", bus)
        self.assertIn("func apply_state(data: Dictionary) -> Dictionary", bus)
        self.assertIn("func get_save_id() -> String", bus)
        self.assertIn("func save_state() -> Dictionary", bus)
        self.assertIn("func load_state(data: Dictionary) -> void", bus)
        self.assertIn("func _enter_tree() -> void", bus)
        self.assertIn("func _process(delta: float) -> void", bus)
        self.assertIn("add_to_group(GameplayEventConstantsData.SAVE_GROUP)", bus)
        self.assertIn("if auto_flush:", bus)
        self.assertIn("flush_events(auto_flush_limit)", bus)
        self.assertIn("_parse_event_state", bus)
        self.assertIn("_parse_integer_field", bus)
        self.assertIn("save_history", bus)
        self.assertIn("max_history", bus)
```

- [ ] **Step 2: Run the source-shape test to verify it fails**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_gameplay_events_source_defines_bus_api
```

Expected: failure until queue/state helpers are present.

- [ ] **Step 3: Replace the Task 3 queue and state stubs with full behavior**

Implement:

```gdscript
func _enter_tree() -> void:
	if not String(save_id).is_empty():
		add_to_group(GameplayEventConstantsData.SAVE_GROUP)


func _process(delta: float) -> void:
	if auto_flush:
		flush_events(auto_flush_limit)


func queue_event(event_id: String, payload: Dictionary = {}) -> Dictionary:
	var normalized := event_id.strip_edges()
	var result := GameplayEventResultData.make(true, normalized)
	var event := _make_event(normalized, payload, true, result)
	if not bool(result.get("ok", false)):
		event_failed.emit(normalized, result)
		return result
	_queue.append(_copy_event(event))
	result["event"] = _copy_event(event)
	var changed_event := _make_result_event(GameplayEventConstantsData.EVENT_QUEUED, event)
	GameplayEventResultData.add_event(result, changed_event)
	event_queued.emit(normalized, _copy_event(event), result)
	events_changed.emit(changed_event)
	return result


func flush_events(limit: int = 0) -> Array[Dictionary]:
	var results: Array[Dictionary] = []
	if limit < 0:
		var failed := GameplayEventResultData.make(false)
		GameplayEventResultData.add_error(failed, "limit must be zero or greater")
		event_failed.emit("", failed)
		return results
	var remaining := limit
	while not _queue.is_empty() and (limit == 0 or remaining > 0):
		var event := _queue.pop_front()
		var result := GameplayEventResultData.make(true, String(event.get("event_id", "")))
		result["payload"] = (event.get("payload", {}) as Dictionary).duplicate(true)
		results.append(_dispatch_event(event, result))
		if limit > 0:
			remaining -= 1
	var emitted_events: Array = []
	for result in results:
		if bool(result.get("ok", false)) and result.get("event", {}) is Dictionary:
			emitted_events.append((result.get("event", {}) as Dictionary).duplicate(true))
	queue_flushed.emit(emitted_events)
	return results
```

Implement `get_history(limit)`, `clear_history()`, `get_state()`, `apply_state(data)`, `get_save_id()`, `save_state()`, and `load_state(data)` according to the spec:

- `get_history(0)` returns all retained history.
- Positive history limit returns the most recent entries.
- `clear_history()` emits `events_changed` only when history was non-empty.
- `get_state()` returns `schema_version`, `sequence`, `queue`, and `history`.
- `history` is empty in state unless `save_history = true`.
- `apply_state(data)` validates all fields before mutating `_sequence`, `_queue`, and `_history`.
- `load_state(data)` calls `apply_state(data)` and `push_warning()` on failure.

Add parsing helpers:

```gdscript
func _parse_event_state(value: Variant, field_name: String, result: Dictionary) -> Dictionary
func _parse_event_array(value: Variant, field_name: String, result: Dictionary) -> Array[Dictionary]
func _parse_integer_field(value: Variant, field_name: String, result: Dictionary) -> int
```

Validation rules:

- `sequence` must be an integer zero or greater.
- Event state must be a Dictionary.
- Event state must include known non-empty `event_id`.
- Event `payload` must be a JSON-compatible Dictionary.
- Event `sequence` must be an integer zero or greater.
- Event `queued` must be a bool.
- Event `timestamp_msec` must be an integer zero or greater.
- Failed `apply_state()` leaves current runtime state unchanged.

- [ ] **Step 4: Run the source-shape test to verify it passes**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_gameplay_events_source_defines_bus_api
```

Expected: pass.

- [ ] **Step 5: Commit**

```sh
git add tests/test_modules.py gameplay_modules/gameplay_events/addons/gameplay_events/gameplay_event_bus.gd
git commit -m "Add gameplay event queue and state"
```

---

### Task 5: Add Demo Resources, Demo Scene, And Demo Test

**Files:**
- Modify: `gameplay_modules/gameplay_events/module.json`
- Create: `gameplay_modules/gameplay_events/demo/resources/item_collected.tres`
- Create: `gameplay_modules/gameplay_events/demo/resources/door_opened.tres`
- Create: `gameplay_modules/gameplay_events/demo/resources/quest_progressed.tres`
- Create: `gameplay_modules/gameplay_events/demo/resources/event_database.tres`
- Create: `gameplay_modules/gameplay_events/demo/scenes/gameplay_events_demo.tscn`
- Create: `gameplay_modules/gameplay_events/demo/scripts/gameplay_events_demo.gd`
- Create: `gameplay_modules/gameplay_events/tests/test_gameplay_events_demo.py`
- Modify: `tests/test_modules.py`

- [ ] **Step 1: Add demo copy assertions**

In `tests/test_modules.py`, add this test near the other `test_add_*_module_with_demo_copies_demo_assets` tests:

```python
    def test_add_gameplay_events_module_with_demo_copies_demo_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "gameplay_events", demo=True)

            self.assertTrue(report["ok"], report)
            self.assertTrue(report["demo"])
            self.assertTrue((project / "scenes" / "gameplay_events_demo" / "gameplay_events_demo.tscn").exists())
            self.assertTrue((project / "scripts" / "gameplay_events_demo" / "gameplay_events_demo.gd").exists())
            self.assertTrue((project / "resources" / "gameplay_events_demo" / "event_database.tres").exists())
            self.assertTrue((project / "tests" / "gameplay_events_demo" / "test_gameplay_events_demo.py").exists())
```

- [ ] **Step 2: Run the demo copy test to verify it fails**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_add_gameplay_events_module_with_demo_copies_demo_assets
```

Expected: failure because the manifest has no demo copy entries and demo files do not exist.

- [ ] **Step 3: Add demo copy entries to `module.json`**

Update `gameplay_modules/gameplay_events/module.json` so it includes:

```json
  "demo": {
    "copy": [
      {"from": "demo/scenes", "to": "scenes/gameplay_events_demo"},
      {"from": "demo/scripts", "to": "scripts/gameplay_events_demo"},
      {"from": "demo/resources", "to": "resources/gameplay_events_demo"},
      {"from": "tests", "to": "tests/gameplay_events_demo"}
    ]
  },
```

Keep `"autoloads": []`.

- [ ] **Step 4: Create demo resources**

Create `gameplay_modules/gameplay_events/demo/resources/item_collected.tres`:

```text
[gd_resource type="Resource" script_class="EventDefinition" load_steps=2 format=3]

[ext_resource type="Script" path="res://addons/gameplay_events/event_definition.gd" id="1_event_script"]

[resource]
script = ExtResource("1_event_script")
event_id = &"item_collected"
display_name = "Item Collected"
description = "Demo event emitted when the player collects an item."
tags = Array[StringName]([&"demo", &"inventory"])
default_payload = {"quantity": 1}
record_by_default = true
```

Create `gameplay_modules/gameplay_events/demo/resources/door_opened.tres`:

```text
[gd_resource type="Resource" script_class="EventDefinition" load_steps=2 format=3]

[ext_resource type="Script" path="res://addons/gameplay_events/event_definition.gd" id="1_event_script"]

[resource]
script = ExtResource("1_event_script")
event_id = &"door_opened"
display_name = "Door Opened"
description = "Demo event queued when a door opens."
tags = Array[StringName]([&"demo", &"interaction"])
default_payload = {"locked": false}
record_by_default = true
```

Create `gameplay_modules/gameplay_events/demo/resources/quest_progressed.tres`:

```text
[gd_resource type="Resource" script_class="EventDefinition" load_steps=2 format=3]

[ext_resource type="Script" path="res://addons/gameplay_events/event_definition.gd" id="1_event_script"]

[resource]
script = ExtResource("1_event_script")
event_id = &"quest_progressed"
display_name = "Quest Progressed"
description = "Demo event queued when quest progress is reported."
tags = Array[StringName]([&"demo", &"quest"])
default_payload = {"amount": 1}
record_by_default = true
```

Create `gameplay_modules/gameplay_events/demo/resources/event_database.tres`:

```text
[gd_resource type="Resource" script_class="EventDatabase" load_steps=5 format=3]

[ext_resource type="Script" path="res://addons/gameplay_events/event_database.gd" id="1_database_script"]
[ext_resource type="Resource" path="res://resources/gameplay_events_demo/item_collected.tres" id="2_item_collected"]
[ext_resource type="Resource" path="res://resources/gameplay_events_demo/door_opened.tres" id="3_door_opened"]
[ext_resource type="Resource" path="res://resources/gameplay_events_demo/quest_progressed.tres" id="4_quest_progressed"]

[resource]
script = ExtResource("1_database_script")
events = Array[Resource]([ExtResource("2_item_collected"), ExtResource("3_door_opened"), ExtResource("4_quest_progressed")])
```

- [ ] **Step 5: Create demo scene**

Create `gameplay_modules/gameplay_events/demo/scenes/gameplay_events_demo.tscn`:

```text
[gd_scene load_steps=4 format=3]

[ext_resource type="Script" path="res://scripts/gameplay_events_demo/gameplay_events_demo.gd" id="1_demo_script"]
[ext_resource type="Script" path="res://addons/gameplay_events/gameplay_event_bus.gd" id="2_event_bus_script"]
[ext_resource type="Resource" path="res://resources/gameplay_events_demo/event_database.tres" id="3_event_database"]

[node name="GameplayEventsDemo" type="Node"]
script = ExtResource("1_demo_script")

[node name="GameplayEventBus" type="Node" parent="."]
script = ExtResource("2_event_bus_script")
database = ExtResource("3_event_database")
save_id = &"demo_gameplay_events"
auto_flush = false
```

- [ ] **Step 6: Create demo script**

Create `gameplay_modules/gameplay_events/demo/scripts/gameplay_events_demo.gd`:

```gdscript
extends Node

@onready var event_bus: Node = $GameplayEventBus

var _received_items: Array = []


func run_gameplay_events_demo() -> Dictionary:
	_received_items.clear()
	var errors: Array[String] = []
	var subscribed: Dictionary = event_bus.subscribe("item_collected", self, &"_on_item_collected")
	_assert_ok(subscribed, "subscribe item_collected", errors)
	var duplicate_subscribe: Dictionary = event_bus.subscribe("item_collected", self, &"_on_item_collected")
	_assert_ok(duplicate_subscribe, "duplicate subscribe item_collected", errors)
	var emitted: Dictionary = event_bus.emit_event("item_collected", {"item_id": "coin"})
	_assert_ok(emitted, "emit item_collected", errors)
	var missing_event: Dictionary = event_bus.emit_event("missing_event", {})
	if bool(missing_event.get("ok", true)):
		errors.append("missing_event should fail")
	var bad_payload: Dictionary = event_bus.emit_event("item_collected", {"node": self})
	if bool(bad_payload.get("ok", true)):
		errors.append("non-json payload should fail")
	var queued_door: Dictionary = event_bus.queue_event("door_opened", {"door_id": "north_gate"})
	_assert_ok(queued_door, "queue door_opened", errors)
	var queued_quest: Dictionary = event_bus.queue_event("quest_progressed", {"quest_id": "repair_beacon"})
	_assert_ok(queued_quest, "queue quest_progressed", errors)
	var flushed: Array[Dictionary] = event_bus.flush_events()
	if flushed.size() != 2:
		errors.append("expected 2 flushed events, got %d" % flushed.size())
	var unsubscribed: Dictionary = event_bus.unsubscribe("item_collected", self, &"_on_item_collected")
	_assert_ok(unsubscribed, "unsubscribe item_collected", errors)
	event_bus.queue_event("door_opened", {"door_id": "west_gate"})
	event_bus.queue_event("quest_progressed", {"quest_id": "repair_beacon", "amount": 2})
	var limited_flush: Array[Dictionary] = event_bus.flush_events(1)
	if limited_flush.size() != 1:
		errors.append("expected 1 limited flush result, got %d" % limited_flush.size())
	var history: Array = event_bus.get_history()
	var state: Dictionary = event_bus.get_state()
	var remaining_queue_count := (state.get("queue", []) as Array).size()
	event_bus.save_history = true
	var saved_state: Dictionary = event_bus.get_state()
	var saved_history_count := (saved_state.get("history", []) as Array).size()
	event_bus.clear_history()
	event_bus.clear_queue()
	var applied: Dictionary = event_bus.apply_state(saved_state)
	_assert_ok(applied, "apply saved state", errors)
	var restored_state: Dictionary = event_bus.get_state()
	return {
		"ok": errors.is_empty(),
		"errors": errors,
		"received_count": _received_items.size(),
		"received_item_id": _received_items[0].get("item_id", "") if not _received_items.is_empty() else "",
		"received_quantity": int(_received_items[0].get("quantity", 0)) if not _received_items.is_empty() else 0,
		"emit_payload_quantity": int((emitted.get("payload", {}) as Dictionary).get("quantity", 0)),
		"duplicate_warning_count": (duplicate_subscribe.get("warnings", []) as Array).size(),
		"missing_event_ok": bool(missing_event.get("ok", true)),
		"bad_payload_ok": bool(bad_payload.get("ok", true)),
		"unsubscribe_ok": bool(unsubscribed.get("ok", false)),
		"flushed_count": flushed.size(),
		"limited_flush_count": limited_flush.size(),
		"history_count": history.size(),
		"state_queue_count": (state.get("queue", []) as Array).size(),
		"state_history_count": (state.get("history", []) as Array).size(),
		"remaining_queue_count": remaining_queue_count,
		"saved_history_count": saved_history_count,
		"apply_state_ok": bool(applied.get("ok", false)),
		"restored_queue_count": (restored_state.get("queue", []) as Array).size(),
		"restored_history_count": (restored_state.get("history", []) as Array).size(),
	}


func _on_item_collected(event: Dictionary) -> void:
	_received_items.append((event.get("payload", {}) as Dictionary).duplicate(true))


func _assert_ok(result: Dictionary, label: String, errors: Array[String]) -> void:
	if not bool(result.get("ok", false)):
		errors.append("%s failed: %s" % [label, str(result)])
```

- [ ] **Step 7: Create copied demo test**

Create `gameplay_modules/gameplay_events/tests/test_gameplay_events_demo.py`:

```python
from __future__ import annotations


def test_gameplay_events_demo_runs(godot):
    godot.change_scene("res://scenes/gameplay_events_demo/gameplay_events_demo.tscn")
    result = godot.locator("#GameplayEventsDemo").call("run_gameplay_events_demo")
    assert result["ok"], result
    assert result["received_count"] == 1
    assert result["received_item_id"] == "coin"
    assert result["received_quantity"] == 1
    assert result["emit_payload_quantity"] == 1
    assert result["duplicate_warning_count"] >= 1
    assert result["missing_event_ok"] is False
    assert result["bad_payload_ok"] is False
    assert result["unsubscribe_ok"] is True
    assert result["flushed_count"] == 2
    assert result["limited_flush_count"] == 1
    assert result["history_count"] == 4
    assert result["state_queue_count"] == 1
    assert result["state_history_count"] == 0
    assert result["remaining_queue_count"] == 1
    assert result["saved_history_count"] == 4
    assert result["apply_state_ok"] is True
    assert result["restored_queue_count"] == 1
    assert result["restored_history_count"] == 4
```

- [ ] **Step 8: Run the demo copy test to verify it passes**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_add_gameplay_events_module_with_demo_copies_demo_assets
```

Expected: pass.

- [ ] **Step 9: Commit**

```sh
git add tests/test_modules.py gameplay_modules/gameplay_events
git commit -m "Add gameplay events demo assets"
```

---

### Task 6: Add Runtime Demo Tests And Validation Coverage

**Files:**
- Modify: `tests/test_modules.py`

- [ ] **Step 1: Add installed demo validation and runtime tests**

Add these methods near the existing installed quest/stats demo tests:

```python
    def test_installed_gameplay_events_demo_resources_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")
            add_module(project, "gameplay_events", demo=True)

            result = check_project_resources(
                project,
                ["res://scenes/gameplay_events_demo", "res://resources/gameplay_events_demo"],
                exclude=["addons/godot_playwright/**"],
            )

            self.assertTrue(result["ok"], result)

    def test_gameplay_events_demo_runs_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")
            init_project(project, force=True)
            add_module(project, "gameplay_events", demo=True)
            project_file = project / "project.godot"
            text = project_file.read_text(encoding="utf-8")
            text += '\nrun/main_scene="res://scenes/gameplay_events_demo/gameplay_events_demo.tscn"\n'
            project_file.write_text(text, encoding="utf-8")

            with Godot(project) as godot:
                result = godot.locator("#GameplayEventsDemo").call("run_gameplay_events_demo")

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["received_count"], 1)
            self.assertEqual(result["received_item_id"], "coin")
            self.assertEqual(result["received_quantity"], 1)
            self.assertEqual(result["flushed_count"], 2)
            self.assertEqual(result["history_count"], 3)

    def test_installed_gameplay_events_demo_test_runs_without_main_scene_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")
            init_project(project, force=True)
            add_module(project, "gameplay_events", demo=True)

            report = run_tests(
                project,
                [project / "tests" / "gameplay_events_demo"],
                artifacts_dir=root / "artifacts",
                trace="off",
            )

            self.assertTrue(report["ok"], report)
            self.assertEqual(report["passed"], 1)
```

- [ ] **Step 2: Run the new runtime tests**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_installed_gameplay_events_demo_resources_are_valid tests.test_modules.ModuleInstallerUnitTests.test_gameplay_events_demo_runs_in_runtime tests.test_modules.ModuleInstallerUnitTests.test_installed_gameplay_events_demo_test_runs_without_main_scene_override
```

Expected: pass when Godot is available in the environment. If Godot is unavailable, record the exact missing executable or startup error in the final implementation notes.

- [ ] **Step 3: Add script validation test**

Add this method near existing installed module script validation tests:

```python
    def test_installed_gameplay_events_scripts_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")
            add_module(project, "gameplay_events", demo=True)

            result = check_project_scripts(
                project,
                ["res://addons/gameplay_events", "res://scripts/gameplay_events_demo"],
                exclude=["addons/godot_playwright/**"],
            )

            self.assertTrue(result["ok"], result)
```

- [ ] **Step 4: Run script/resource validation tests**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_installed_gameplay_events_scripts_are_valid tests.test_modules.ModuleInstallerUnitTests.test_installed_gameplay_events_demo_resources_are_valid
```

Expected: pass.

- [ ] **Step 5: Commit**

```sh
git add tests/test_modules.py
git commit -m "Add gameplay events runtime tests"
```

---

### Task 7: Add Documentation And README Integration

**Files:**
- Modify: `gameplay_modules/gameplay_events/README.md`
- Modify: `gameplay_modules/gameplay_events/AGENT.md`
- Modify: `README.md`
- Modify: `tests/test_modules.py`

- [ ] **Step 1: Add documentation tests**

In `tests/test_modules.py`, add:

```python
    def test_gameplay_events_docs_describe_boundaries(self) -> None:
        source_root = default_module_roots()[0]
        readme = (source_root / "gameplay_events" / "README.md").read_text(encoding="utf-8")
        agent = (source_root / "gameplay_events" / "AGENT.md").read_text(encoding="utf-8")

        self.assertIn("godot-playwright module add /path/to/project gameplay_events", readme)
        self.assertIn("godot-playwright module add /path/to/project gameplay_events --demo", readme)
        self.assertIn("EventDefinition", readme)
        self.assertIn("EventDatabase", readme)
        self.assertIn("GameplayEventBus", readme)
        self.assertIn("emit_event", readme)
        self.assertIn("queue_event", readme)
        self.assertIn("flush_events", readme)
        self.assertIn("subscribe", readme)
        self.assertIn("record_history", readme)
        self.assertIn("save_history", readme)
        self.assertIn("does not directly integrate", readme)
        self.assertIn("JSON-compatible", agent)
        self.assertIn("Do not store engine objects", agent)
        self.assertIn("Do not assume a global Autoload", agent)
        self.assertIn("queue_event", agent)
        self.assertIn("explicit project code", agent)
```

Extend `test_readme_gameplay_module_commands_include_current_modules`:

```python
        self.assertIn("godot-playwright module add /tmp/agent-game gameplay_events", readme)
        self.assertIn("godot-playwright module add /tmp/agent-game gameplay_events --demo", readme)
```

- [ ] **Step 2: Run documentation tests to verify they fail**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_gameplay_events_docs_describe_boundaries tests.test_modules.ModuleInstallerUnitTests.test_readme_gameplay_module_commands_include_current_modules
```

Expected: failure until docs and top-level README mention the full gameplay events module.

- [ ] **Step 3: Expand `README.md` for the module**

Update `gameplay_modules/gameplay_events/README.md` to include:

- Install command with and without `--demo`.
- Event definition fields.
- API list for `GameplayEventBus`.
- Synchronous dispatch example:

```gdscript
var result := event_bus.emit_event("item_collected", {"item_id": "coin"})
if result.ok:
	print(result.event.payload)
```

- Queued dispatch example:

```gdscript
event_bus.queue_event("door_opened", {"door_id": "north_gate"})
event_bus.flush_events()
```

- Subscription example:

```gdscript
event_bus.subscribe("item_collected", self, &"_on_item_collected")

func _on_item_collected(event: Dictionary) -> void:
	var payload: Dictionary = event.get("payload", {})
```

- Saving section explaining `save_id`, `get_state()`, `apply_state(data)`, `record_history`, and `save_history`.
- Optional integration section that states the module does not directly integrate with inventory, stats, effects, abilities, quests, interaction, state machines, combat, dialogue, UI, or analytics.
- Validation commands.

- [ ] **Step 4: Expand `AGENT.md`**

Update `gameplay_modules/gameplay_events/AGENT.md` with these instructions:

- Prefer stable lowercase event IDs.
- Keep payloads JSON-compatible.
- Use explicit project code for cross-module consequences.
- Use `queue_event()` when event order should be controlled.
- Do not store engine objects in payloads, queued events, history, or saved state.
- Do not assume a global Autoload unless the project created one.
- Use `subscribe(event_id, target, method)` for one-argument `event: Dictionary` callbacks.
- Do not use this module as a rules engine.

- [ ] **Step 5: Update top-level `README.md`**

Add gameplay events to the gameplay module command list near the existing module commands:

```sh
godot-playwright module add /tmp/agent-game gameplay_events
godot-playwright module add /tmp/agent-game gameplay_events --demo
```

Add one short summary sentence:

```markdown
`gameplay_events` provides a Resource-driven event bus for explicit cross-system gameplay announcements.
```

- [ ] **Step 6: Run documentation tests to verify they pass**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_gameplay_events_docs_describe_boundaries tests.test_modules.ModuleInstallerUnitTests.test_readme_gameplay_module_commands_include_current_modules
```

Expected: pass.

- [ ] **Step 7: Commit**

```sh
git add README.md tests/test_modules.py gameplay_modules/gameplay_events/README.md gameplay_modules/gameplay_events/AGENT.md
git commit -m "Document gameplay events module"
```

---

### Task 8: Add Bundled Mirror And Package Data

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `pyproject.toml`
- Create: `godot_playwright/bundled_gameplay_modules/gameplay_events/`

- [ ] **Step 1: Add bundled mirror and package-data tests**

In `tests/test_modules.py`, add:

```python
    def test_packaged_gameplay_events_module_mirror_exists(self) -> None:
        bundled_root = default_module_roots()[1]
        manifest = load_module_manifest("gameplay_events", module_root=bundled_root)
        self.assertEqual(manifest["name"], "gameplay_events")
        self.assertEqual(manifest["autoloads"], [])
        self.assertTrue(
            (bundled_root / "gameplay_events" / "addons" / "gameplay_events" / "gameplay_event_bus.gd").exists()
        )

    def test_source_and_packaged_gameplay_events_trees_are_identical(self) -> None:
        source_root, bundled_root = default_module_roots()
        source = source_root / "gameplay_events"
        bundled = bundled_root / "gameplay_events"
        source_files = sorted(path.relative_to(source) for path in source.rglob("*") if path.is_file())
        bundled_files = sorted(path.relative_to(bundled) for path in bundled.rglob("*") if path.is_file())

        self.assertEqual([path.as_posix() for path in source_files], [path.as_posix() for path in bundled_files])
        for relative_path in source_files:
            self.assertEqual(
                (source / relative_path).read_bytes(),
                (bundled / relative_path).read_bytes(),
                relative_path.as_posix(),
            )
```

Extend `test_pyproject_includes_bundled_gameplay_module_data`:

```python
        self.assertIn('"bundled_gameplay_modules/gameplay_events/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/gameplay_events/addons/gameplay_events/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/gameplay_events/demo/scenes/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/gameplay_events/demo/scripts/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/gameplay_events/demo/resources/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/gameplay_events/tests/*"', pyproject)
```

- [ ] **Step 2: Run bundled/package tests to verify they fail**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_packaged_gameplay_events_module_mirror_exists tests.test_modules.ModuleInstallerUnitTests.test_source_and_packaged_gameplay_events_trees_are_identical tests.test_modules.ModuleInstallerUnitTests.test_pyproject_includes_bundled_gameplay_module_data
```

Expected: failure because bundled mirror and package-data entries do not exist.

- [ ] **Step 3: Create byte-identical bundled mirror**

Run:

```sh
mkdir -p godot_playwright/bundled_gameplay_modules
rsync -a --delete gameplay_modules/gameplay_events/ godot_playwright/bundled_gameplay_modules/gameplay_events/
```

This command only synchronizes the `gameplay_events` bundled mirror from the source module.

- [ ] **Step 4: Add package data entries**

In `pyproject.toml`, add these entries under `[tool.setuptools.package-data]`:

```toml
  "bundled_gameplay_modules/gameplay_events/*",
  "bundled_gameplay_modules/gameplay_events/addons/gameplay_events/*",
  "bundled_gameplay_modules/gameplay_events/demo/scenes/*",
  "bundled_gameplay_modules/gameplay_events/demo/scripts/*",
  "bundled_gameplay_modules/gameplay_events/demo/resources/*",
  "bundled_gameplay_modules/gameplay_events/tests/*",
```

- [ ] **Step 5: Run bundled/package tests to verify they pass**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_packaged_gameplay_events_module_mirror_exists tests.test_modules.ModuleInstallerUnitTests.test_source_and_packaged_gameplay_events_trees_are_identical tests.test_modules.ModuleInstallerUnitTests.test_pyproject_includes_bundled_gameplay_module_data
```

Expected: pass.

- [ ] **Step 6: Commit**

```sh
git add tests/test_modules.py pyproject.toml godot_playwright/bundled_gameplay_modules/gameplay_events
git commit -m "Bundle gameplay events module"
```

---

### Task 9: Final Verification And Polish

**Files:**
- Review: `gameplay_modules/gameplay_events/`
- Review: `godot_playwright/bundled_gameplay_modules/gameplay_events/`
- Review: `tests/test_modules.py`
- Review: `README.md`
- Review: `pyproject.toml`

- [ ] **Step 1: Run targeted unit tests**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_repository_gameplay_events_module_is_discoverable tests.test_modules.ModuleInstallerUnitTests.test_add_gameplay_events_module_copies_files_without_autoload tests.test_modules.ModuleInstallerUnitTests.test_add_gameplay_events_module_with_demo_copies_demo_assets tests.test_modules.ModuleInstallerUnitTests.test_gameplay_events_source_defines_resource_helpers tests.test_modules.ModuleInstallerUnitTests.test_gameplay_events_source_defines_bus_api tests.test_modules.ModuleInstallerUnitTests.test_gameplay_events_docs_describe_boundaries tests.test_modules.ModuleInstallerUnitTests.test_packaged_gameplay_events_module_mirror_exists tests.test_modules.ModuleInstallerUnitTests.test_source_and_packaged_gameplay_events_trees_are_identical
```

Expected: pass.

- [ ] **Step 2: Run runtime and copied demo tests**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_installed_gameplay_events_scripts_are_valid tests.test_modules.ModuleInstallerUnitTests.test_installed_gameplay_events_demo_resources_are_valid tests.test_modules.ModuleInstallerUnitTests.test_gameplay_events_demo_runs_in_runtime tests.test_modules.ModuleInstallerUnitTests.test_installed_gameplay_events_demo_test_runs_without_main_scene_override
```

Expected: pass when Godot is available.

- [ ] **Step 3: Run full module test file**

Run:

```sh
uv run python -m unittest tests.test_modules
```

Expected: pass.

- [ ] **Step 4: Run source and bundled tree comparison**

Run:

```sh
uv run python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_source_and_packaged_gameplay_events_trees_are_identical
```

Expected: pass.

- [ ] **Step 5: Inspect git status**

Run:

```sh
git status --short
```

Expected: only intentional changes remain. If all task commits were made, working tree should be clean.

- [ ] **Step 6: Commit any final verification fixes**

If Step 5 shows intentional uncommitted fixes, commit them:

```sh
git add README.md pyproject.toml tests/test_modules.py gameplay_modules/gameplay_events godot_playwright/bundled_gameplay_modules/gameplay_events
git commit -m "Polish gameplay events module"
```

Expected: commit created only when final fixes exist.

---

## Self-Review

Spec coverage:

- Installable `gameplay_events` module: Tasks 1, 5, 8.
- Resource-driven `EventDefinition` and `EventDatabase`: Task 2.
- `GameplayEventBus` synchronous dispatch, subscriptions, generic signals: Task 3.
- Queue, auto-flush, history, state import/export, save wrappers: Task 4.
- Demo scene, resources, copied test: Tasks 5 and 6.
- Docs and agent guidance: Task 7.
- Bundled mirror and package data: Task 8.
- Validation and runtime checks: Tasks 6 and 9.

Type consistency:

- Module name: `gameplay_events`.
- Addon path: `res://addons/gameplay_events/`.
- Runtime class: `GameplayEventBus`.
- Definition class: `EventDefinition`.
- Database class: `EventDatabase`.
- Result helper: `GameplayEventResult`.
- Constants helper: `GameplayEventConstants`.
- Demo root node: `GameplayEventsDemo`.
- Demo callable: `run_gameplay_events_demo()`.

Implementation boundary:

- No Autoload entries.
- No direct imports from other gameplay modules.
- Payloads and state are JSON-compatible.
- Subscribers are runtime-only and excluded from saved state.
