# Stats Gameplay Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an installable `stats` gameplay module that provides Resource-driven runtime numeric stat containers for Godot projects.

**Architecture:** Follow the existing gameplay module pattern: source module under `gameplay_modules/stats`, bundled mirror under `godot_playwright/bundled_gameplay_modules/stats`, no Autoload, deterministic demo, copied Python demo test, and structured result dictionaries for expected failures. Runtime logic lives in `StatContainer`; static tunable data lives in `StatDefinition` and `StatDatabase`; docs explain integration boundaries with save/load, inventory, interaction, state machine, and effects.

**Tech Stack:** Python `unittest`, `godot-playwright` module installer, Godot 4.6 GDScript, `.tres` Resource files, `.tscn` demo scene, package data in `pyproject.toml`.

---

## File Structure

Create:

- `gameplay_modules/stats/module.json` - module manifest for installer copy/demo behavior.
- `gameplay_modules/stats/README.md` - human-facing usage documentation.
- `gameplay_modules/stats/AGENT.md` - agent-facing wiring and boundary instructions.
- `gameplay_modules/stats/addons/stats/stat_constants.gd` - schema/module constants and save group name.
- `gameplay_modules/stats/addons/stats/stat_result.gd` - shared result dictionary helpers.
- `gameplay_modules/stats/addons/stats/stat_definition.gd` - editor-authored stat definition Resource.
- `gameplay_modules/stats/addons/stats/stat_database.gd` - definition registry and validation Resource.
- `gameplay_modules/stats/addons/stats/stat_container.gd` - runtime stat component Node.
- `gameplay_modules/stats/demo/resources/health.tres` - demo pool stat.
- `gameplay_modules/stats/demo/resources/stamina.tres` - demo pool stat.
- `gameplay_modules/stats/demo/resources/move_speed.tres` - demo non-pool stat.
- `gameplay_modules/stats/demo/resources/heat.tres` - demo clamped non-pool stat.
- `gameplay_modules/stats/demo/resources/stat_database.tres` - demo stat database.
- `gameplay_modules/stats/demo/scenes/stats_demo.tscn` - deterministic demo scene.
- `gameplay_modules/stats/demo/scripts/stats_demo.gd` - demo assertions exposed through `run_stats_demo()`.
- `gameplay_modules/stats/tests/test_stats_demo.py` - copied demo test.
- `godot_playwright/bundled_gameplay_modules/stats/module.json` - bundled manifest.
- `godot_playwright/bundled_gameplay_modules/stats/README.md` - bundled human docs.
- `godot_playwright/bundled_gameplay_modules/stats/AGENT.md` - bundled agent docs.
- `godot_playwright/bundled_gameplay_modules/stats/addons/stats/` - bundled addon scripts.
- `godot_playwright/bundled_gameplay_modules/stats/demo/` - bundled demo scene, scripts, and resources.
- `godot_playwright/bundled_gameplay_modules/stats/tests/` - bundled copied demo test.

Modify:

- `tests/test_modules.py` - installer, source shape, docs, runtime, and demo tests.
- `pyproject.toml` - include bundled stats package data.
- `README.md` - list stats install/demo commands and short module summary.

Do not modify:

- `godot_playwright/modules.py` - the current manifest-driven installer should discover the module automatically.
- Existing gameplay modules, except if a test import/order conflict is discovered during execution.

---

### Task 1: Add Installer Tests And Minimal Module Shell

**Files:**
- Modify: `tests/test_modules.py`
- Create: `gameplay_modules/stats/module.json`
- Create: `gameplay_modules/stats/README.md`
- Create: `gameplay_modules/stats/AGENT.md`
- Create: `gameplay_modules/stats/addons/stats/stat_constants.gd`
- Create: `gameplay_modules/stats/addons/stats/stat_result.gd`
- Create: `gameplay_modules/stats/addons/stats/stat_definition.gd`
- Create: `gameplay_modules/stats/addons/stats/stat_database.gd`
- Create: `gameplay_modules/stats/addons/stats/stat_container.gd`

- [ ] **Step 1: Write failing Python installer tests**

In `tests/test_modules.py`, add these methods inside `ModuleInstallerUnitTests` near the existing repository module discovery/copy tests:

```python
    def test_repository_stats_module_is_discoverable(self) -> None:
        modules = list_modules()
        stats = next(module for module in modules if module["name"] == "stats")
        self.assertEqual(stats["version"], "0.1.0")
        self.assertEqual(stats["godot_version"], ">=4.6")
        self.assertEqual(stats["autoloads"], [])
        self.assertNotIn("demo", stats)

    def test_add_stats_module_copies_files_without_autoload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "stats")

            self.assertTrue(report["ok"], report)
            self.assertFalse(report["demo"])
            self.assertEqual(report["module"], "stats")
            self.assertEqual(report["autoloads"], [])
            expected_scripts = {
                "stat_constants.gd",
                "stat_result.gd",
                "stat_definition.gd",
                "stat_database.gd",
                "stat_container.gd",
            }
            for script_name in expected_scripts:
                self.assertTrue((project / "addons" / "stats" / script_name).exists(), script_name)
            project_text = (project / "project.godot").read_text(encoding="utf-8")
            self.assertNotIn("StatsService", project_text)
            copied_targets = {entry["target"] for entry in report["copied"]}
            self.assertTrue(
                {f"res://addons/stats/{script_name}" for script_name in expected_scripts}.issubset(copied_targets),
                copied_targets,
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```sh
python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_repository_stats_module_is_discoverable tests.test_modules.ModuleInstallerUnitTests.test_add_stats_module_copies_files_without_autoload
```

Expected: FAIL or ERROR because module `stats` is not discoverable.

- [ ] **Step 3: Create minimal module manifest and shell files**

Create directories:

```sh
mkdir -p gameplay_modules/stats/addons/stats
```

Create `gameplay_modules/stats/module.json`:

```json
{
  "name": "stats",
  "version": "0.1.0",
  "display_name": "Stats",
  "description": "Resource-driven runtime stat container for Godot projects.",
  "godot_version": ">=4.6",
  "copy": [
    {"from": "addons/stats", "to": "addons/stats"}
  ],
  "autoloads": [],
  "validation": {
    "commands": [
      "godot-playwright check-scripts /path/to/project res://addons/stats --exclude addons/godot_playwright/**",
      "godot-playwright check-resources /path/to/project res://addons/stats --exclude addons/godot_playwright/**"
    ]
  }
}
```

Create `gameplay_modules/stats/README.md`:

````markdown
# Stats Gameplay Module

`stats` adds a Resource-driven runtime stat container for Godot 4.6+ projects.

Install into a Godot project:

```sh
godot-playwright module add /path/to/project stats
```

The installer copies `res://addons/stats/`. It does not register an Autoload.
````

Create `gameplay_modules/stats/AGENT.md`:

````markdown
# Agent Instructions: stats

Use this module when a Godot project needs health, mana, stamina, speed, attack, defense, hunger, temperature, morale, energy, durability-like values, or other numeric runtime state.

Install with:

```sh
godot-playwright module add /path/to/project stats
```
````

Create minimal parseable GDScript shell files:

`gameplay_modules/stats/addons/stats/stat_constants.gd`

```gdscript
class_name StatConstants
extends RefCounted

const SAVE_GROUP: StringName = &"save_participants"
const SCHEMA_VERSION: int = 1
const MODULE_VERSION: String = "0.1.0"
```

`gameplay_modules/stats/addons/stats/stat_result.gd`

```gdscript
class_name StatResult
extends RefCounted


static func make(ok: bool, stat_id: String = "") -> Dictionary:
	return {
		"ok": ok,
		"stat_id": stat_id,
		"previous_value": 0.0,
		"current_value": 0.0,
		"previous_base_value": 0.0,
		"base_value": 0.0,
		"requested_value": 0.0,
		"delta": 0.0,
		"clamped": false,
		"events": [],
		"warnings": [],
		"errors": [],
	}


static func add_warning(result: Dictionary, message: String) -> void:
	(result["warnings"] as Array).append(message)


static func add_error(result: Dictionary, message: String) -> void:
	result["ok"] = false
	(result["errors"] as Array).append(message)
```

`gameplay_modules/stats/addons/stats/stat_definition.gd`

```gdscript
class_name StatDefinition
extends Resource

@export var stat_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export var default_base_value: float = 0.0
@export var default_current_value: float = 0.0
@export var clamp_min: bool = true
@export var min_value: float = 0.0
@export var clamp_max: bool = false
@export var max_value: float = 100.0
@export var is_pool: bool = false
```

`gameplay_modules/stats/addons/stats/stat_database.gd`

```gdscript
class_name StatDatabase
extends Resource

@export var stats: Array[Resource] = []
```

`gameplay_modules/stats/addons/stats/stat_container.gd`

```gdscript
class_name StatContainer
extends Node

@export var database: Resource
@export var save_id: StringName
@export var initialize_on_ready: bool = true
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```sh
python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_repository_stats_module_is_discoverable tests.test_modules.ModuleInstallerUnitTests.test_add_stats_module_copies_files_without_autoload
```

Expected: PASS.

- [ ] **Step 5: Commit**

```sh
git add tests/test_modules.py gameplay_modules/stats
git commit -m "Add stats gameplay module shell"
```

---

### Task 2: Implement Stat Definition, Database, And Result Helpers

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `gameplay_modules/stats/addons/stats/stat_result.gd`
- Modify: `gameplay_modules/stats/addons/stats/stat_database.gd`

- [ ] **Step 1: Write failing source-shape tests**

In `tests/test_modules.py`, add this method inside `ModuleInstallerUnitTests` near the existing source-shape tests:

```python
    def test_stats_source_defines_resource_helpers(self) -> None:
        source_root = default_module_roots()[0]
        stats_root = source_root / "stats" / "addons" / "stats"
        definition = (stats_root / "stat_definition.gd").read_text(encoding="utf-8")
        database = (stats_root / "stat_database.gd").read_text(encoding="utf-8")
        result = (stats_root / "stat_result.gd").read_text(encoding="utf-8")

        self.assertIn("class_name StatDefinition", definition)
        self.assertIn("@export var stat_id: StringName", definition)
        self.assertIn("@export var display_name: String", definition)
        self.assertIn("@export_multiline var description: String", definition)
        self.assertIn("@export var tags: Array[StringName] = []", definition)
        self.assertIn("@export var default_base_value: float = 0.0", definition)
        self.assertIn("@export var default_current_value: float = 0.0", definition)
        self.assertIn("@export var clamp_min: bool = true", definition)
        self.assertIn("@export var min_value: float = 0.0", definition)
        self.assertIn("@export var clamp_max: bool = false", definition)
        self.assertIn("@export var max_value: float = 100.0", definition)
        self.assertIn("@export var is_pool: bool = false", definition)
        self.assertIn("class_name StatDatabase", database)
        self.assertIn('StatDefinitionData := preload("res://addons/stats/stat_definition.gd")', database)
        self.assertIn('StatResultData := preload("res://addons/stats/stat_result.gd")', database)
        self.assertIn("@export var stats: Array[Resource] = []", database)
        self.assertIn("func get_stat(stat_id: String) -> Resource", database)
        self.assertIn("func has_stat(stat_id: String) -> bool", database)
        self.assertIn("func get_stat_ids() -> Array[String]", database)
        self.assertIn("func validate() -> Dictionary", database)
        self.assertIn("Duplicate stat_id", database)
        self.assertIn("ids.append(raw_stat_id)", database)
        self.assertIn("_is_finite_number", database)
        self.assertIn("default_base_value must be finite", database)
        self.assertIn("min_value must be <= max_value", database)
        self.assertIn("class_name StatResult", result)
        self.assertIn('"ok": ok', result)
        self.assertIn('"stat_id": stat_id', result)
        self.assertIn('"previous_value": 0.0', result)
        self.assertIn('"current_value": 0.0', result)
        self.assertIn('"previous_base_value": 0.0', result)
        self.assertIn('"base_value": 0.0', result)
        self.assertIn('"requested_value": 0.0', result)
        self.assertIn('"delta": 0.0', result)
        self.assertIn('"clamped": false', result)
        self.assertIn("static func add_event", result)
        self.assertIn("static func add_warning", result)
        self.assertIn("static func add_error", result)
        self.assertIn('"events": []', result)
        self.assertIn('"warnings": []', result)
        self.assertIn('"errors": []', result)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```sh
python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_stats_source_defines_resource_helpers
```

Expected: FAIL because `StatDatabase` does not yet expose helper methods.

- [ ] **Step 3: Implement `stat_result.gd`**

Replace `gameplay_modules/stats/addons/stats/stat_result.gd` with:

```gdscript
class_name StatResult
extends RefCounted


static func make(ok: bool, stat_id: String = "") -> Dictionary:
	return {
		"ok": ok,
		"stat_id": stat_id,
		"previous_value": 0.0,
		"current_value": 0.0,
		"previous_base_value": 0.0,
		"base_value": 0.0,
		"requested_value": 0.0,
		"delta": 0.0,
		"clamped": false,
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

- [ ] **Step 4: Implement `stat_database.gd`**

Replace `gameplay_modules/stats/addons/stats/stat_database.gd` with:

```gdscript
class_name StatDatabase
extends Resource

const StatDefinitionData := preload("res://addons/stats/stat_definition.gd")
const StatResultData := preload("res://addons/stats/stat_result.gd")

@export var stats: Array[Resource] = []


func get_stat(stat_id: String) -> Resource:
	var normalized := stat_id.strip_edges()
	if normalized.is_empty():
		return null
	for stat in stats:
		var definition = _definition_or_null(stat)
		if definition == null:
			continue
		if String(definition.stat_id) == normalized:
			return definition
	return null


func has_stat(stat_id: String) -> bool:
	return get_stat(stat_id) != null


func get_stat_ids() -> Array[String]:
	var ids: Array[String] = []
	for stat in stats:
		var definition = _definition_or_null(stat)
		if definition == null:
			continue
		var raw_stat_id := String(definition.stat_id)
		var stat_id := raw_stat_id.strip_edges()
		if not stat_id.is_empty() and stat_id == raw_stat_id:
			ids.append(raw_stat_id)
	return ids


func validate() -> Dictionary:
	var result := StatResultData.make(true)
	var seen := {}
	for index in range(stats.size()):
		var stat := stats[index]
		if stat == null:
			StatResultData.add_error(result, "stats[%d] is null" % index)
			continue
		var definition = _definition_or_null(stat)
		if definition == null:
			StatResultData.add_error(result, "stats[%d] must be a StatDefinition" % index)
			continue
		var raw_stat_id := String(definition.stat_id)
		var stat_id := raw_stat_id.strip_edges()
		if stat_id.is_empty():
			StatResultData.add_error(result, "stats[%d].stat_id must be non-empty" % index)
			continue
		if stat_id != raw_stat_id:
			StatResultData.add_error(result, "stats[%d].stat_id must not contain leading or trailing whitespace" % index)
			continue
		if seen.has(stat_id):
			StatResultData.add_error(result, "Duplicate stat_id: %s" % stat_id)
			continue
		seen[stat_id] = true
		_validate_definition_numbers(definition, stat_id, result)
	return result


func _validate_definition_numbers(definition: Resource, stat_id: String, result: Dictionary) -> void:
	if not _is_finite_number(definition.default_base_value):
		StatResultData.add_error(result, "default_base_value must be finite for stat_id: %s" % stat_id)
	if not _is_finite_number(definition.default_current_value):
		StatResultData.add_error(result, "default_current_value must be finite for stat_id: %s" % stat_id)
	if not _is_finite_number(definition.min_value):
		StatResultData.add_error(result, "min_value must be finite for stat_id: %s" % stat_id)
	if not _is_finite_number(definition.max_value):
		StatResultData.add_error(result, "max_value must be finite for stat_id: %s" % stat_id)
	if bool(definition.clamp_min) and bool(definition.clamp_max) and float(definition.min_value) > float(definition.max_value):
		StatResultData.add_error(result, "min_value must be <= max_value for stat_id: %s" % stat_id)


func _definition_or_null(stat: Resource):
	if stat == null:
		return null
	if stat is StatDefinitionData:
		return stat
	return null


func _is_finite_number(value: Variant) -> bool:
	if typeof(value) != TYPE_INT and typeof(value) != TYPE_FLOAT:
		return false
	var number := float(value)
	return not is_nan(number) and not is_inf(number)
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```sh
python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_stats_source_defines_resource_helpers
```

Expected: PASS.

- [ ] **Step 6: Commit**

```sh
git add tests/test_modules.py gameplay_modules/stats/addons/stats/stat_result.gd gameplay_modules/stats/addons/stats/stat_database.gd
git commit -m "Add stats resource helpers"
```

---

### Task 3: Implement StatContainer Core API

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `gameplay_modules/stats/addons/stats/stat_container.gd`

- [ ] **Step 1: Write failing source-shape tests**

In `tests/test_modules.py`, add this method inside `ModuleInstallerUnitTests`:

```python
    def test_stats_source_defines_container_api(self) -> None:
        source_root = default_module_roots()[0]
        container = (source_root / "stats" / "addons" / "stats" / "stat_container.gd").read_text(
            encoding="utf-8"
        )

        self.assertIn("class_name StatContainer", container)
        self.assertIn("@export var database: Resource", container)
        self.assertIn("@export var save_id: StringName", container)
        self.assertIn("@export var initialize_on_ready: bool = true", container)
        self.assertIn("signal stat_changed", container)
        self.assertIn("signal base_stat_changed", container)
        self.assertIn("signal stat_depleted", container)
        self.assertIn("signal stat_filled", container)
        self.assertIn("signal stats_changed", container)
        self.assertIn("func initialize_stats(reset: bool = false) -> Dictionary", container)
        self.assertIn("func has_stat(stat_id: String) -> bool", container)
        self.assertIn("func get_value(stat_id: String) -> float", container)
        self.assertIn("func get_base_value(stat_id: String) -> float", container)
        self.assertIn("func get_stat(stat_id: String) -> Dictionary", container)
        self.assertIn("func get_stats() -> Array", container)
        self.assertIn("func set_value(stat_id: String, value: float) -> Dictionary", container)
        self.assertIn("func modify_value(stat_id: String, delta: float) -> Dictionary", container)
        self.assertIn("func set_base_value(stat_id: String, value: float) -> Dictionary", container)
        self.assertIn("func modify_base_value(stat_id: String, delta: float) -> Dictionary", container)
        self.assertIn("func get_state() -> Dictionary", container)
        self.assertIn("func apply_state(data: Dictionary) -> Dictionary", container)
        self.assertIn("func get_save_id() -> String", container)
        self.assertIn("func save_state() -> Dictionary", container)
        self.assertIn("func load_state(data: Dictionary) -> void", container)
        self.assertIn("StatConstantsData.SCHEMA_VERSION", container)
        self.assertIn("is_pool", container)
        self.assertIn("clamped", container)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```sh
python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_stats_source_defines_container_api
```

Expected: FAIL because `StatContainer` only has exported shell fields.

- [ ] **Step 3: Implement `stat_container.gd`**

Replace `gameplay_modules/stats/addons/stats/stat_container.gd` with the implementation below. Keep tabs for indentation, matching existing GDScript files such as `inventory.gd`.

```gdscript
class_name StatContainer
extends Node

const StatConstantsData := preload("res://addons/stats/stat_constants.gd")
const StatResultData := preload("res://addons/stats/stat_result.gd")

signal stat_changed(stat_id: String, current_value: float, previous_value: float, result: Dictionary)
signal base_stat_changed(stat_id: String, base_value: float, previous_base_value: float, result: Dictionary)
signal stat_depleted(stat_id: String, current_value: float, result: Dictionary)
signal stat_filled(stat_id: String, current_value: float, result: Dictionary)
signal stats_changed(event: Dictionary)

@export var database: Resource
@export var save_id: StringName
@export var initialize_on_ready: bool = true

var _stats_by_id: Dictionary = {}
var _stat_ids: Array[String] = []
var _initialized: bool = false


func _enter_tree() -> void:
	if not String(save_id).is_empty():
		add_to_group(StatConstantsData.SAVE_GROUP)


func _ready() -> void:
	if initialize_on_ready:
		initialize_stats()


func initialize_stats(reset: bool = false) -> Dictionary:
	var result := StatResultData.make(true)
	if _initialized and not reset:
		return result
	if not _validate_database(result):
		return result
	_stats_by_id.clear()
	_stat_ids.clear()
	var ids: Array[String] = []
	ids.assign(database.call("get_stat_ids"))
	for stat_id in ids:
		var definition: Resource = database.call("get_stat", stat_id)
		var base_value := _clamp_base_value(definition, float(definition.default_base_value), null)
		var current_value := _clamp_current_value(definition, float(definition.default_current_value), base_value, null)
		_stats_by_id[stat_id] = {
			"stat_id": stat_id,
			"base_value": base_value,
			"current_value": current_value,
		}
		_stat_ids.append(stat_id)
	_initialized = true
	return result


func has_stat(stat_id: String) -> bool:
	_ensure_initialized()
	return _stats_by_id.has(stat_id.strip_edges())


func get_value(stat_id: String) -> float:
	_ensure_initialized()
	var normalized := stat_id.strip_edges()
	if not _stats_by_id.has(normalized):
		return 0.0
	return float((_stats_by_id[normalized] as Dictionary).get("current_value", 0.0))


func get_base_value(stat_id: String) -> float:
	_ensure_initialized()
	var normalized := stat_id.strip_edges()
	if not _stats_by_id.has(normalized):
		return 0.0
	return float((_stats_by_id[normalized] as Dictionary).get("base_value", 0.0))


func get_stat(stat_id: String) -> Dictionary:
	_ensure_initialized()
	var normalized := stat_id.strip_edges()
	if not _stats_by_id.has(normalized):
		return {}
	return (_stats_by_id[normalized] as Dictionary).duplicate(true)


func get_stats() -> Array:
	_ensure_initialized()
	var copied: Array = []
	for stat_id in _stat_ids:
		copied.append((_stats_by_id[stat_id] as Dictionary).duplicate(true))
	return copied


func set_value(stat_id: String, value: float) -> Dictionary:
	return _set_current_value(stat_id, value, false, 0.0)


func modify_value(stat_id: String, delta: float) -> Dictionary:
	var normalized := stat_id.strip_edges()
	_ensure_initialized()
	var current := get_value(normalized)
	return _set_current_value(normalized, current + delta, true, delta)


func set_base_value(stat_id: String, value: float) -> Dictionary:
	return _set_base_value(stat_id, value, false, 0.0)


func modify_base_value(stat_id: String, delta: float) -> Dictionary:
	var normalized := stat_id.strip_edges()
	_ensure_initialized()
	var current_base := get_base_value(normalized)
	return _set_base_value(normalized, current_base + delta, true, delta)


func clear_runtime_state() -> void:
	_stats_by_id.clear()
	_stat_ids.clear()
	_initialized = false


func get_state() -> Dictionary:
	return {
		"schema_version": StatConstantsData.SCHEMA_VERSION,
		"stats": get_stats(),
	}


func apply_state(data: Dictionary) -> Dictionary:
	var result := StatResultData.make(true)
	var parsed := _parse_state(data, result)
	if not bool(result.get("ok", false)):
		return result
	var previous_ids: Array[String] = []
	previous_ids.assign(_stat_ids)
	_stats_by_id = parsed["stats_by_id"]
	_stat_ids = parsed["stat_ids"]
	_initialized = true
	for stat_id in _stat_ids:
		var event := {"type": "state_applied", "stat_id": stat_id, "stat": get_stat(stat_id)}
		StatResultData.add_event(result, event)
		stats_changed.emit(event)
	return result


func get_save_id() -> String:
	return String(save_id)


func save_state() -> Dictionary:
	return get_state()


func load_state(data: Dictionary) -> void:
	var result := apply_state(data)
	if not bool(result.get("ok", false)):
		push_warning("StatContainer load_state failed: %s" % ", ".join(PackedStringArray(result.get("errors", []))))


func _set_current_value(stat_id: String, value: float, is_delta: bool, delta: float) -> Dictionary:
	_ensure_initialized()
	var normalized := stat_id.strip_edges()
	var result := _make_stat_result(normalized)
	if not _validate_stat_mutation(result, normalized):
		return result
	if not _is_finite_number(value):
		StatResultData.add_error(result, "value must be finite")
		return result
	var stat: Dictionary = _stats_by_id[normalized]
	var definition: Resource = database.call("get_stat", normalized)
	var previous := float(stat["current_value"])
	var applied := _clamp_current_value(definition, value, float(stat["base_value"]), result)
	result["requested_value"] = value
	result["delta"] = delta if is_delta else applied - previous
	result["previous_value"] = previous
	result["current_value"] = applied
	stat["current_value"] = applied
	if previous != applied:
		_emit_current_events(normalized, definition, previous, applied, result)
	return result


func _set_base_value(stat_id: String, value: float, is_delta: bool, delta: float) -> Dictionary:
	_ensure_initialized()
	var normalized := stat_id.strip_edges()
	var result := _make_stat_result(normalized)
	if not _validate_stat_mutation(result, normalized):
		return result
	if not _is_finite_number(value):
		StatResultData.add_error(result, "value must be finite")
		return result
	var stat: Dictionary = _stats_by_id[normalized]
	var definition: Resource = database.call("get_stat", normalized)
	var previous_base := float(stat["base_value"])
	var previous_current := float(stat["current_value"])
	var applied_base := _clamp_base_value(definition, value, result)
	var applied_current := _clamp_current_value(definition, previous_current, applied_base, result)
	result["requested_value"] = value
	result["delta"] = delta if is_delta else applied_base - previous_base
	result["previous_base_value"] = previous_base
	result["base_value"] = applied_base
	result["previous_value"] = previous_current
	result["current_value"] = applied_current
	stat["base_value"] = applied_base
	stat["current_value"] = applied_current
	if previous_base != applied_base:
		var base_event := {"type": "base_changed", "stat_id": normalized, "previous_base_value": previous_base, "base_value": applied_base}
		StatResultData.add_event(result, base_event)
		base_stat_changed.emit(normalized, applied_base, previous_base, result)
		stats_changed.emit(base_event)
	if previous_current != applied_current:
		_emit_current_events(normalized, definition, previous_current, applied_current, result)
	return result


func _make_stat_result(stat_id: String) -> Dictionary:
	var result := StatResultData.make(true, stat_id)
	if _stats_by_id.has(stat_id):
		var stat: Dictionary = _stats_by_id[stat_id]
		result["previous_value"] = float(stat.get("current_value", 0.0))
		result["current_value"] = float(stat.get("current_value", 0.0))
		result["previous_base_value"] = float(stat.get("base_value", 0.0))
		result["base_value"] = float(stat.get("base_value", 0.0))
	return result


func _emit_current_events(stat_id: String, definition: Resource, previous: float, current: float, result: Dictionary) -> void:
	var changed_event := {"type": "changed", "stat_id": stat_id, "previous_value": previous, "current_value": current}
	StatResultData.add_event(result, changed_event)
	stat_changed.emit(stat_id, current, previous, result)
	stats_changed.emit(changed_event)
	if bool(definition.clamp_min):
		var minimum := float(definition.min_value)
		if previous > minimum and current <= minimum:
			var depleted_event := {"type": "depleted", "stat_id": stat_id, "current_value": current}
			StatResultData.add_event(result, depleted_event)
			stat_depleted.emit(stat_id, current, result)
			stats_changed.emit(depleted_event)
	var has_maximum := bool(definition.is_pool) or bool(definition.clamp_max)
	if has_maximum:
		var maximum := get_base_value(stat_id) if bool(definition.is_pool) else float(definition.max_value)
		if previous < maximum and current >= maximum:
			var filled_event := {"type": "filled", "stat_id": stat_id, "current_value": current}
			StatResultData.add_event(result, filled_event)
			stat_filled.emit(stat_id, current, result)
			stats_changed.emit(filled_event)


func _validate_stat_mutation(result: Dictionary, stat_id: String) -> bool:
	if stat_id.is_empty():
		StatResultData.add_error(result, "stat_id must be non-empty")
	if not _validate_database(result):
		return false
	if result["ok"] and not _stats_by_id.has(stat_id):
		StatResultData.add_error(result, "Unknown stat_id: %s" % stat_id)
	return bool(result["ok"])


func _validate_database(result: Dictionary) -> bool:
	if database == null:
		StatResultData.add_error(result, "database must be assigned")
		return false
	if not database.has_method("validate") or not database.has_method("get_stat") or not database.has_method("has_stat") or not database.has_method("get_stat_ids"):
		StatResultData.add_error(result, "database must be a StatDatabase")
		return false
	var database_result: Dictionary = database.call("validate")
	if not bool(database_result.get("ok", false)):
		for error in database_result.get("errors", []):
			StatResultData.add_error(result, String(error))
		for warning in database_result.get("warnings", []):
			StatResultData.add_warning(result, String(warning))
		return false
	return true


func _ensure_initialized() -> void:
	if not _initialized:
		initialize_stats()


func _clamp_base_value(definition: Resource, value: float, result: Dictionary) -> float:
	var applied := value
	if bool(definition.clamp_min):
		applied = maxf(applied, float(definition.min_value))
	if bool(definition.clamp_max):
		applied = minf(applied, float(definition.max_value))
	if result != null and applied != value:
		result["clamped"] = true
		StatResultData.add_warning(result, "value was clamped from %s to %s" % [str(value), str(applied)])
	return applied


func _clamp_current_value(definition: Resource, value: float, base_value: float, result: Dictionary) -> float:
	var applied := value
	if bool(definition.clamp_min):
		applied = maxf(applied, float(definition.min_value))
	if bool(definition.is_pool):
		applied = minf(applied, base_value)
	elif bool(definition.clamp_max):
		applied = minf(applied, float(definition.max_value))
	if result != null and applied != value:
		result["clamped"] = true
		StatResultData.add_warning(result, "value was clamped from %s to %s" % [str(value), str(applied)])
	return applied


func _parse_state(data: Dictionary, result: Dictionary) -> Dictionary:
	var parsed := {"stats_by_id": {}, "stat_ids": []}
	if int(data.get("schema_version", -1)) != StatConstantsData.SCHEMA_VERSION:
		StatResultData.add_error(result, "schema_version must be %d" % StatConstantsData.SCHEMA_VERSION)
	var raw_stats = data.get("stats", null)
	if not (raw_stats is Array):
		StatResultData.add_error(result, "stats must be an Array")
		return parsed
	if not _validate_database(result):
		return parsed
	var seen := {}
	var next_by_id := {}
	var next_ids: Array[String] = []
	var saved_stats: Array = raw_stats
	for index in range(saved_stats.size()):
		var value = saved_stats[index]
		if not (value is Dictionary):
			StatResultData.add_error(result, "stats[%d] must be a Dictionary" % index)
			continue
		var stat: Dictionary = value
		var raw_stat_id = stat.get("stat_id", "")
		if typeof(raw_stat_id) != TYPE_STRING and typeof(raw_stat_id) != TYPE_STRING_NAME:
			StatResultData.add_error(result, "stats[%d].stat_id must be a string" % index)
			continue
		var stat_id := String(raw_stat_id)
		var normalized := stat_id.strip_edges()
		if normalized.is_empty():
			StatResultData.add_error(result, "stats[%d].stat_id must be non-empty" % index)
			continue
		if normalized != stat_id:
			StatResultData.add_error(result, "stats[%d].stat_id must not contain leading or trailing whitespace" % index)
			continue
		if seen.has(normalized):
			StatResultData.add_error(result, "Duplicate stat_id: %s" % normalized)
			continue
		if not bool(database.call("has_stat", normalized)):
			StatResultData.add_error(result, "Unknown stat_id: %s" % normalized)
			continue
		seen[normalized] = true
		var base_value = stat.get("base_value", null)
		var current_value = stat.get("current_value", null)
		if not _is_finite_number(base_value):
			StatResultData.add_error(result, "stats[%d].base_value must be finite" % index)
			continue
		if not _is_finite_number(current_value):
			StatResultData.add_error(result, "stats[%d].current_value must be finite" % index)
			continue
		var definition: Resource = database.call("get_stat", normalized)
		var parsed_base := _clamp_base_value(definition, float(base_value), null)
		var parsed_current := _clamp_current_value(definition, float(current_value), parsed_base, null)
		if parsed_base != float(base_value) or parsed_current != float(current_value):
			StatResultData.add_error(result, "stats[%d] values do not satisfy current clamp rules" % index)
			continue
		next_by_id[normalized] = {"stat_id": normalized, "base_value": parsed_base, "current_value": parsed_current}
	for database_id in database.call("get_stat_ids"):
		if next_by_id.has(database_id):
			next_ids.append(database_id)
		else:
			var definition: Resource = database.call("get_stat", database_id)
			next_by_id[database_id] = {
				"stat_id": database_id,
				"base_value": _clamp_base_value(definition, float(definition.default_base_value), null),
				"current_value": _clamp_current_value(definition, float(definition.default_current_value), float(definition.default_base_value), null),
			}
			next_ids.append(database_id)
	if bool(result.get("ok", false)):
		parsed["stats_by_id"] = next_by_id
		parsed["stat_ids"] = next_ids
	return parsed


func _is_finite_number(value: Variant) -> bool:
	if typeof(value) != TYPE_INT and typeof(value) != TYPE_FLOAT:
		return false
	var number := float(value)
	return not is_nan(number) and not is_inf(number)
```

- [ ] **Step 4: Run source-shape test**

Run:

```sh
python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_stats_source_defines_container_api
```

Expected: PASS.

- [ ] **Step 5: Run Python module installer tests touched so far**

Run:

```sh
python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_repository_stats_module_is_discoverable tests.test_modules.ModuleInstallerUnitTests.test_add_stats_module_copies_files_without_autoload tests.test_modules.ModuleInstallerUnitTests.test_stats_source_defines_resource_helpers tests.test_modules.ModuleInstallerUnitTests.test_stats_source_defines_container_api
```

Expected: PASS.

- [ ] **Step 6: Commit**

```sh
git add tests/test_modules.py gameplay_modules/stats/addons/stats/stat_container.gd
git commit -m "Add stats container core API"
```

---

### Task 4: Add Godot Runtime Probes For Database And Container

**Files:**
- Modify: `tests/test_modules.py`

- [ ] **Step 1: Write failing Godot runtime tests and helper probe writers**

Add this class near the other Godot-gated module test classes that use `@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")`:

```python
@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class StatsModuleGodotTests(unittest.TestCase):
    def test_installed_stats_scripts_parse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Stats Parse Probe")
            add_module(project, "stats")

            report = check_project_scripts(
                project,
                ["res://addons/stats"],
                artifacts_dir=root / "artifacts",
            )

        self.assertTrue(report["ok"], report["diagnostics"])

    def test_stats_database_validation_runs_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Stats Database Probe")
            add_module(project, "stats")
            _write_stats_database_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/stats_database_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#StatsDatabaseProbe").call("run_probe")

        self.assertTrue(result["ok"], result)

    def test_stats_container_operations_run_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Stats Container Probe")
            add_module(project, "stats")
            _write_stats_container_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/stats_container_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#StatsContainerProbe").call("run_probe")

        self.assertTrue(result["ok"], result)
```

Add these helper functions near the existing `_write_*_probe` helpers:

```python
def _write_stats_database_probe(project: Path) -> None:
    (project / "scripts" / "stats_database_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            const StatDefinitionData := preload("res://addons/stats/stat_definition.gd")
            const StatDatabaseData := preload("res://addons/stats/stat_database.gd")


            func run_probe() -> Dictionary:
                var errors: Array[String] = []
                var health := StatDefinitionData.new()
                health.stat_id = &"health"
                health.display_name = "Health"
                health.default_base_value = 100.0
                health.default_current_value = 100.0
                health.clamp_min = true
                health.min_value = 0.0
                health.is_pool = true

                var stamina := StatDefinitionData.new()
                stamina.stat_id = &"stamina"
                stamina.display_name = "Stamina"
                stamina.default_base_value = 50.0
                stamina.default_current_value = 25.0
                stamina.clamp_min = true
                stamina.min_value = 0.0
                stamina.is_pool = true

                var database := StatDatabaseData.new()
                database.stats = [health, stamina]
                var valid_result: Dictionary = database.validate()
                _assert_bool(bool(valid_result.get("ok", false)), "database should validate", errors)
                _assert_bool(database.has_stat("health"), "database has health", errors)
                _assert_bool(database.get_stat("missing") == null, "missing stat returns null", errors)
                _assert_array(["health", "stamina"], database.get_stat_ids(), "stat id order", errors)

                var duplicate := StatDefinitionData.new()
                duplicate.stat_id = &"health"
                var duplicate_database := StatDatabaseData.new()
                duplicate_database.stats = [health, duplicate]
                var duplicate_result: Dictionary = duplicate_database.validate()
                _assert_bool(not bool(duplicate_result.get("ok", true)), "duplicate database should fail", errors)
                _assert_contains(duplicate_result.get("errors", []), "Duplicate stat_id: health", "duplicate error", errors)

                var bad_bounds := StatDefinitionData.new()
                bad_bounds.stat_id = &"bad_bounds"
                bad_bounds.clamp_min = true
                bad_bounds.min_value = 10.0
                bad_bounds.clamp_max = true
                bad_bounds.max_value = 1.0
                var bad_database := StatDatabaseData.new()
                bad_database.stats = [bad_bounds]
                var bad_result: Dictionary = bad_database.validate()
                _assert_bool(not bool(bad_result.get("ok", true)), "bad bounds should fail", errors)
                _assert_contains(bad_result.get("errors", []), "min_value must be <= max_value", "bad bounds error", errors)

                return {"ok": errors.is_empty(), "errors": errors}


            func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
                if not value:
                    errors.append(message)


            func _assert_array(expected: Array, actual: Array, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %s, got %s" % [label, str(expected), str(actual)])


            func _assert_contains(messages: Array, needle: String, label: String, errors: Array[String]) -> void:
                for message in messages:
                    if String(message).contains(needle):
                        return
                errors.append("%s: missing %s in %s" % [label, needle, str(messages)])
            """
        ),
        encoding="utf-8",
    )
    (project / "scenes" / "stats_database_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/stats_database_probe.gd" id="1_probe_script"]

            [node name="StatsDatabaseProbe" type="Node"]
            script = ExtResource("1_probe_script")
            """
        ),
        encoding="utf-8",
    )


def _write_stats_container_probe(project: Path) -> None:
    (project / "scripts" / "stats_container_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            const StatDefinitionData := preload("res://addons/stats/stat_definition.gd")
            const StatDatabaseData := preload("res://addons/stats/stat_database.gd")
            const StatContainerData := preload("res://addons/stats/stat_container.gd")

            var events: Array[String] = []


            func run_probe() -> Dictionary:
                var errors: Array[String] = []
                var container := StatContainerData.new()
                container.name = "Stats"
                container.initialize_on_ready = false
                add_child(container)
                container.database = _make_database()
                container.stat_depleted.connect(func(stat_id: String, _value: float, _result: Dictionary): events.append("depleted:%s" % stat_id))
                container.stat_filled.connect(func(stat_id: String, _value: float, _result: Dictionary): events.append("filled:%s" % stat_id))

                var init_result: Dictionary = container.initialize_stats()
                _assert_ok(init_result, "initialize", errors)
                _assert_float(100.0, container.get_base_value("health"), "health base", errors)
                _assert_float(100.0, container.get_value("health"), "health current", errors)
                _assert_float(4.0, container.get_value("move_speed"), "move speed current", errors)

                var damage_result: Dictionary = container.modify_value("health", -25.0)
                _assert_ok(damage_result, "damage", errors)
                _assert_float(75.0, container.get_value("health"), "health after damage", errors)

                var deplete_result: Dictionary = container.modify_value("health", -999.0)
                _assert_ok(deplete_result, "deplete", errors)
                _assert_bool(bool(deplete_result.get("clamped", false)), "deplete should clamp", errors)
                _assert_float(0.0, container.get_value("health"), "health after depletion", errors)
                _assert_contains(events, "depleted:health", "depletion event", errors)

                var fill_result: Dictionary = container.set_value("health", 100.0)
                _assert_ok(fill_result, "fill", errors)
                _assert_contains(events, "filled:health", "fill event", errors)

                var lower_base_result: Dictionary = container.set_base_value("health", 40.0)
                _assert_ok(lower_base_result, "lower base", errors)
                _assert_float(40.0, container.get_base_value("health"), "lowered base", errors)
                _assert_float(40.0, container.get_value("health"), "pool current clamps to base", errors)

                var speed_result: Dictionary = container.set_base_value("move_speed", 8.0)
                _assert_ok(speed_result, "speed base", errors)
                var speed_current_result: Dictionary = container.set_value("move_speed", 12.0)
                _assert_ok(speed_current_result, "speed current", errors)
                _assert_float(12.0, container.get_value("move_speed"), "non-pool current ignores base maximum", errors)

                var saved_state: Dictionary = container.get_state()
                container.set_value("health", 5.0)
                container.set_value("move_speed", 1.0)
                var restore_result: Dictionary = container.apply_state(saved_state)
                _assert_ok(restore_result, "state restore", errors)
                _assert_float(40.0, container.get_value("health"), "restored health", errors)
                _assert_float(12.0, container.get_value("move_speed"), "restored move speed", errors)

                var bad_result: Dictionary = container.set_value("missing", 1.0)
                _assert_bool(not bool(bad_result.get("ok", true)), "missing stat should fail", errors)
                _assert_contains(bad_result.get("errors", []), "Unknown stat_id: missing", "missing stat error", errors)

                var bad_state := {"schema_version": 1, "stats": [{"stat_id": "health", "base_value": 100.0, "current_value": 500.0}]}
                var bad_state_result: Dictionary = container.apply_state(bad_state)
                _assert_bool(not bool(bad_state_result.get("ok", true)), "bad state should fail", errors)
                _assert_float(40.0, container.get_value("health"), "bad state should not mutate", errors)

                return {"ok": errors.is_empty(), "errors": errors, "events": events}


            func _make_database() -> Resource:
                var health := StatDefinitionData.new()
                health.stat_id = &"health"
                health.display_name = "Health"
                health.default_base_value = 100.0
                health.default_current_value = 100.0
                health.clamp_min = true
                health.min_value = 0.0
                health.is_pool = true

                var move_speed := StatDefinitionData.new()
                move_speed.stat_id = &"move_speed"
                move_speed.display_name = "Move Speed"
                move_speed.default_base_value = 4.0
                move_speed.default_current_value = 4.0
                move_speed.clamp_min = true
                move_speed.min_value = 0.0

                var database := StatDatabaseData.new()
                database.stats = [health, move_speed]
                return database


            func _assert_ok(result: Dictionary, label: String, errors: Array[String]) -> void:
                if not bool(result.get("ok", false)):
                    errors.append("%s failed: %s" % [label, str(result)])


            func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
                if not value:
                    errors.append(message)


            func _assert_float(expected: float, actual: float, label: String, errors: Array[String]) -> void:
                if not is_equal_approx(expected, actual):
                    errors.append("%s: expected %s, got %s" % [label, str(expected), str(actual)])


            func _assert_contains(messages: Array, needle: String, label: String, errors: Array[String]) -> void:
                for message in messages:
                    if String(message).contains(needle):
                        return
                errors.append("%s: missing %s in %s" % [label, needle, str(messages)])
            """
        ),
        encoding="utf-8",
    )
    (project / "scenes" / "stats_container_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/stats_container_probe.gd" id="1_probe_script"]

            [node name="StatsContainerProbe" type="Node"]
            script = ExtResource("1_probe_script")
            """
        ),
        encoding="utf-8",
    )
```

- [ ] **Step 2: Run runtime tests**

Run:

```sh
python -m unittest tests.test_modules.StatsModuleGodotTests.test_installed_stats_scripts_parse tests.test_modules.StatsModuleGodotTests.test_stats_database_validation_runs_in_runtime tests.test_modules.StatsModuleGodotTests.test_stats_container_operations_run_in_runtime
```

Expected when Godot is installed: PASS. If skipped because Godot is unavailable, record that live Godot validation remains pending.

- [ ] **Step 3: Fix any parser/runtime defects**

If Step 2 fails with Godot parser errors, fix the exact reported file and rerun the same command. Common expected fixes are typed-array syntax mismatches or `Variant` typing in GDScript. Do not broaden module scope while fixing parser/runtime issues.

- [ ] **Step 4: Commit**

```sh
git add tests/test_modules.py gameplay_modules/stats/addons/stats
git commit -m "Validate stats runtime behavior"
```

---

### Task 5: Add Demo Scene, Demo Resources, And Copied Demo Test

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `gameplay_modules/stats/module.json`
- Modify: `gameplay_modules/stats/README.md`
- Modify: `gameplay_modules/stats/AGENT.md`
- Modify: `README.md`
- Create: `gameplay_modules/stats/demo/resources/health.tres`
- Create: `gameplay_modules/stats/demo/resources/stamina.tres`
- Create: `gameplay_modules/stats/demo/resources/move_speed.tres`
- Create: `gameplay_modules/stats/demo/resources/heat.tres`
- Create: `gameplay_modules/stats/demo/resources/stat_database.tres`
- Create: `gameplay_modules/stats/demo/scenes/stats_demo.tscn`
- Create: `gameplay_modules/stats/demo/scripts/stats_demo.gd`
- Create: `gameplay_modules/stats/tests/test_stats_demo.py`

- [ ] **Step 1: Write failing installer and Godot demo tests**

In `tests/test_modules.py`, add this method inside `ModuleInstallerUnitTests` near the other demo-copy tests:

```python
    def test_add_stats_module_with_demo_copies_demo_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "stats", demo=True)

            self.assertTrue(report["ok"], report)
            self.assertTrue(report["demo"])
            self.assertTrue((project / "scenes" / "stats_demo" / "stats_demo.tscn").exists())
            self.assertTrue((project / "scripts" / "stats_demo" / "stats_demo.gd").exists())
            self.assertTrue((project / "resources" / "stats_demo" / "stat_database.tres").exists())
            self.assertTrue((project / "tests" / "stats_demo" / "test_stats_demo.py").exists())
```

Add these methods inside `StatsModuleGodotTests`:

```python
    def test_installed_stats_demo_resources_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Stats Resource Probe")
            add_module(project, "stats", demo=True)

            report = check_project_resources(
                project,
                ["res://scenes/stats_demo", "res://resources/stats_demo"],
            )

        self.assertTrue(report["ok"], report["diagnostics"])

    def test_stats_demo_runs_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Stats Runtime Probe")
            add_module(project, "stats", demo=True)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/stats_demo/stats_demo.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#StatsDemo").call("run_stats_demo")

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["health_after_restore"], 40.0)
        self.assertEqual(result["move_speed_after_restore"], 12.0)
        self.assertFalse(result["missing_stat_ok"])
        self.assertFalse(result["save_load_checked"])

    def test_installed_stats_demo_test_runs_without_main_scene_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Stats Demo Test Probe")
            add_module(project, "stats", demo=True)

            report = run_tests(
                project,
                [project / "tests" / "stats_demo"],
                artifacts_dir=root / "artifacts",
                trace="off",
                timeout=30,
            )

        self.assertEqual(report["failed"], 0, report["tests"])
        self.assertEqual(report["passed"], 1)

    def test_stats_demo_integrates_with_save_load_when_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Stats Save Load Probe")
            add_module(project, "save_load")
            add_module(project, "stats", demo=True)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/stats_demo/stats_demo.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#StatsDemo").call("run_stats_demo")

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["save_load_checked"], result)
        self.assertEqual(result["save_load_health"], 33.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```sh
python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_add_stats_module_with_demo_copies_demo_assets
```

Expected: FAIL because demo files do not exist.

If Godot is available, also run:

```sh
python -m unittest tests.test_modules.StatsModuleGodotTests.test_installed_stats_demo_resources_are_valid tests.test_modules.StatsModuleGodotTests.test_stats_demo_runs_in_runtime tests.test_modules.StatsModuleGodotTests.test_installed_stats_demo_test_runs_without_main_scene_override tests.test_modules.StatsModuleGodotTests.test_stats_demo_integrates_with_save_load_when_installed
```

Expected: FAIL because demo resources and scene do not exist.

- [ ] **Step 3: Create demo Resource files**

Create directories:

```sh
mkdir -p gameplay_modules/stats/demo/resources gameplay_modules/stats/demo/scenes gameplay_modules/stats/demo/scripts gameplay_modules/stats/tests
```

Create `gameplay_modules/stats/demo/resources/health.tres`:

```text
[gd_resource type="Resource" script_class="StatDefinition" load_steps=2 format=3]

[ext_resource type="Script" path="res://addons/stats/stat_definition.gd" id="1_stat_definition"]

[resource]
script = ExtResource("1_stat_definition")
stat_id = &"health"
display_name = "Health"
description = "Current life pool."
tags = Array[StringName]([&"pool", &"survival"])
default_base_value = 100.0
default_current_value = 100.0
clamp_min = true
min_value = 0.0
clamp_max = false
max_value = 100.0
is_pool = true
```

Create `gameplay_modules/stats/demo/resources/stamina.tres`:

```text
[gd_resource type="Resource" script_class="StatDefinition" load_steps=2 format=3]

[ext_resource type="Script" path="res://addons/stats/stat_definition.gd" id="1_stat_definition"]

[resource]
script = ExtResource("1_stat_definition")
stat_id = &"stamina"
display_name = "Stamina"
description = "Short-term action resource."
tags = Array[StringName]([&"pool", &"movement"])
default_base_value = 50.0
default_current_value = 50.0
clamp_min = true
min_value = 0.0
clamp_max = false
max_value = 50.0
is_pool = true
```

Create `gameplay_modules/stats/demo/resources/move_speed.tres`:

```text
[gd_resource type="Resource" script_class="StatDefinition" load_steps=2 format=3]

[ext_resource type="Script" path="res://addons/stats/stat_definition.gd" id="1_stat_definition"]

[resource]
script = ExtResource("1_stat_definition")
stat_id = &"move_speed"
display_name = "Move Speed"
description = "Base movement speed."
tags = Array[StringName]([&"movement"])
default_base_value = 4.0
default_current_value = 4.0
clamp_min = true
min_value = 0.0
clamp_max = false
max_value = 100.0
is_pool = false
```

Create `gameplay_modules/stats/demo/resources/heat.tres`:

```text
[gd_resource type="Resource" script_class="StatDefinition" load_steps=2 format=3]

[ext_resource type="Script" path="res://addons/stats/stat_definition.gd" id="1_stat_definition"]

[resource]
script = ExtResource("1_stat_definition")
stat_id = &"heat"
display_name = "Heat"
description = "Clamped machine heat."
tags = Array[StringName]([&"machine"])
default_base_value = 0.0
default_current_value = 0.0
clamp_min = true
min_value = 0.0
clamp_max = true
max_value = 100.0
is_pool = false
```

Create `gameplay_modules/stats/demo/resources/stat_database.tres`:

```text
[gd_resource type="Resource" script_class="StatDatabase" load_steps=6 format=3]

[ext_resource type="Script" path="res://addons/stats/stat_database.gd" id="1_stat_database"]
[ext_resource type="Resource" path="res://resources/stats_demo/health.tres" id="2_health"]
[ext_resource type="Resource" path="res://resources/stats_demo/stamina.tres" id="3_stamina"]
[ext_resource type="Resource" path="res://resources/stats_demo/move_speed.tres" id="4_move_speed"]
[ext_resource type="Resource" path="res://resources/stats_demo/heat.tres" id="5_heat"]

[resource]
script = ExtResource("1_stat_database")
stats = Array[Resource]([ExtResource("2_health"), ExtResource("3_stamina"), ExtResource("4_move_speed"), ExtResource("5_heat")])
```

- [ ] **Step 4: Create demo scene and script**

Create `gameplay_modules/stats/demo/scenes/stats_demo.tscn`:

```text
[gd_scene load_steps=4 format=3]

[ext_resource type="Script" path="res://scripts/stats_demo/stats_demo.gd" id="1_demo_script"]
[ext_resource type="Script" path="res://addons/stats/stat_container.gd" id="2_stats_script"]
[ext_resource type="Resource" path="res://resources/stats_demo/stat_database.tres" id="3_stat_database"]

[node name="StatsDemo" type="Node"]
script = ExtResource("1_demo_script")

[node name="Stats" type="Node" parent="."]
script = ExtResource("2_stats_script")
database = ExtResource("3_stat_database")
save_id = &"demo_stats"
```

Create `gameplay_modules/stats/demo/scripts/stats_demo.gd`:

```gdscript
extends Node

@onready var stats: Node = $Stats

var events: Array[String] = []


func _ready() -> void:
	stats.stat_depleted.connect(func(stat_id: String, _value: float, _result: Dictionary): events.append("depleted:%s" % stat_id))
	stats.stat_filled.connect(func(stat_id: String, _value: float, _result: Dictionary): events.append("filled:%s" % stat_id))


func run_stats_demo() -> Dictionary:
	var errors: Array[String] = []
	events.clear()
	stats.initialize_stats(true)

	_assert_float(100.0, stats.get_value("health"), "initial health", errors)
	_assert_float(100.0, stats.get_base_value("health"), "initial health base", errors)
	_assert_float(4.0, stats.get_value("move_speed"), "initial move speed", errors)

	var damage_result: Dictionary = stats.modify_value("health", -25.0)
	_assert_ok(damage_result, "damage health", errors)
	_assert_float(75.0, stats.get_value("health"), "health after damage", errors)

	var deplete_result: Dictionary = stats.modify_value("health", -999.0)
	_assert_ok(deplete_result, "deplete health", errors)
	_assert_bool(bool(deplete_result.get("clamped", false)), "deplete should clamp", errors)
	_assert_float(0.0, stats.get_value("health"), "health depleted", errors)
	_assert_contains(events, "depleted:health", "depleted signal", errors)

	var fill_result: Dictionary = stats.set_value("health", 100.0)
	_assert_ok(fill_result, "fill health", errors)
	_assert_contains(events, "filled:health", "filled signal", errors)

	var lower_base_result: Dictionary = stats.set_base_value("health", 40.0)
	_assert_ok(lower_base_result, "lower health base", errors)
	_assert_float(40.0, stats.get_base_value("health"), "lowered health base", errors)
	_assert_float(40.0, stats.get_value("health"), "health clamped to lowered base", errors)

	var speed_result: Dictionary = stats.set_value("move_speed", 12.0)
	_assert_ok(speed_result, "set move speed", errors)
	_assert_float(12.0, stats.get_value("move_speed"), "non-pool move speed", errors)

	var heat_result: Dictionary = stats.set_value("heat", 250.0)
	_assert_ok(heat_result, "set heat", errors)
	_assert_bool(bool(heat_result.get("clamped", false)), "heat should clamp", errors)
	_assert_float(100.0, stats.get_value("heat"), "heat clamped max", errors)

	var saved_state: Dictionary = stats.get_state()
	stats.set_value("health", 5.0)
	stats.set_value("move_speed", 1.0)
	var restore_result: Dictionary = stats.apply_state(saved_state)
	_assert_ok(restore_result, "state restore", errors)
	var health_after_restore := float(stats.get_value("health"))
	var move_speed_after_restore := float(stats.get_value("move_speed"))
	_assert_float(40.0, health_after_restore, "restored health", errors)
	_assert_float(12.0, move_speed_after_restore, "restored move speed", errors)

	var missing_result: Dictionary = stats.set_value("missing", 1.0)
	var missing_stat_ok := bool(missing_result.get("ok", true))
	_assert_bool(not missing_stat_ok, "missing stat should fail", errors)

	var save_load_checked := false
	var save_load_health := -1.0
	if has_node("/root/SaveService"):
		save_load_checked = true
		var save_service = get_node("/root/SaveService")
		save_service.delete_slot("stats_demo_slot")
		stats.set_value("health", 33.0)
		var save_result: Dictionary = save_service.save_slot("stats_demo_slot")
		stats.set_value("health", 2.0)
		var load_result: Dictionary = save_service.load_slot("stats_demo_slot")
		var delete_result: Dictionary = save_service.delete_slot("stats_demo_slot")
		_assert_ok(save_result, "SaveService save", errors)
		_assert_ok(load_result, "SaveService load", errors)
		_assert_ok(delete_result, "SaveService delete", errors)
		save_load_health = stats.get_value("health")
		_assert_float(33.0, save_load_health, "health after SaveService round-trip", errors)

	return {
		"ok": errors.is_empty(),
		"errors": errors,
		"events": events,
		"damage_result": damage_result,
		"deplete_result": deplete_result,
		"fill_result": fill_result,
		"lower_base_result": lower_base_result,
		"speed_result": speed_result,
		"heat_result": heat_result,
		"restore_result": restore_result,
		"missing_result": missing_result,
		"missing_stat_ok": missing_stat_ok,
		"health_after_restore": health_after_restore,
		"move_speed_after_restore": move_speed_after_restore,
		"save_load_checked": save_load_checked,
		"save_load_health": save_load_health,
	}


func _assert_ok(result: Dictionary, label: String, errors: Array[String]) -> void:
	if not bool(result.get("ok", false)):
		errors.append("%s failed: %s" % [label, str(result)])


func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
	if not value:
		errors.append(message)


func _assert_float(expected: float, actual: float, label: String, errors: Array[String]) -> void:
	if not is_equal_approx(expected, actual):
		errors.append("%s: expected %s, got %s" % [label, str(expected), str(actual)])


func _assert_contains(messages: Array, needle: String, label: String, errors: Array[String]) -> void:
	for message in messages:
		if String(message).contains(needle):
			return
	errors.append("%s: missing %s in %s" % [label, needle, str(messages)])
```

- [ ] **Step 5: Create copied demo test**

Create `gameplay_modules/stats/tests/test_stats_demo.py`:

```python
from __future__ import annotations


def test_stats_demo_runs(godot):
    godot.change_scene("res://scenes/stats_demo/stats_demo.tscn")
    result = godot.locator("#StatsDemo").call("run_stats_demo")
    assert result["ok"], result
    assert result["health_after_restore"] == 40.0
    assert result["move_speed_after_restore"] == 12.0
    assert result["missing_stat_ok"] is False
```

- [ ] **Step 6: Add demo copy block to the module manifest**

Update `gameplay_modules/stats/module.json` to add the demo copy block after `autoloads`:

```json
  "demo": {
    "copy": [
      {"from": "demo/scenes", "to": "scenes/stats_demo"},
      {"from": "demo/scripts", "to": "scripts/stats_demo"},
      {"from": "demo/resources", "to": "resources/stats_demo"},
      {"from": "tests", "to": "tests/stats_demo"}
    ]
  },
```

- [ ] **Step 7: Add demo install commands to source module docs**

Update `gameplay_modules/stats/README.md` to include the demo install command after the base install command:

````markdown
Install the demo scene and copied demo test:

```sh
godot-playwright module add /path/to/project stats --demo
```
````

Update `gameplay_modules/stats/AGENT.md` to include the demo install command after the base install command:

````markdown
Use `--demo` only when adding a demo scene and copied test is acceptable:

```sh
godot-playwright module add /path/to/project stats --demo
```
````

- [ ] **Step 8: Add stats commands and summary to top-level README**

In `README.md`, add these commands to the gameplay module command block:

```sh
godot-playwright module add /tmp/agent-game stats
godot-playwright module add /tmp/agent-game stats --demo
```

Add this short description after the `interaction` module paragraph:

```markdown
The `stats` module adds a reusable `StatContainer` node backed by `StatDefinition` and `StatDatabase` Resources. It supports base/current values, pool stats such as health or stamina, min/max clamping, change/depletion/fill signals, JSON-compatible `get_state()` / `apply_state(data)`, and optional persistence through `save_load` when a container has a stable `save_id`.
```

- [ ] **Step 9: Run tests to verify they pass**

Run:

```sh
python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_add_stats_module_with_demo_copies_demo_assets
```

Expected: PASS.

If Godot is available, run:

```sh
python -m unittest tests.test_modules.StatsModuleGodotTests.test_installed_stats_demo_resources_are_valid tests.test_modules.StatsModuleGodotTests.test_stats_demo_runs_in_runtime tests.test_modules.StatsModuleGodotTests.test_installed_stats_demo_test_runs_without_main_scene_override tests.test_modules.StatsModuleGodotTests.test_stats_demo_integrates_with_save_load_when_installed
```

Expected: PASS.

- [ ] **Step 10: Commit**

```sh
git add tests/test_modules.py README.md gameplay_modules/stats
git commit -m "Add stats gameplay module demo"
```

---

### Task 6: Add Bundled Mirror And Package Data

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `pyproject.toml`
- Create: `godot_playwright/bundled_gameplay_modules/stats/module.json`
- Create: `godot_playwright/bundled_gameplay_modules/stats/README.md`
- Create: `godot_playwright/bundled_gameplay_modules/stats/AGENT.md`
- Create: `godot_playwright/bundled_gameplay_modules/stats/addons/stats/stat_constants.gd`
- Create: `godot_playwright/bundled_gameplay_modules/stats/addons/stats/stat_result.gd`
- Create: `godot_playwright/bundled_gameplay_modules/stats/addons/stats/stat_definition.gd`
- Create: `godot_playwright/bundled_gameplay_modules/stats/addons/stats/stat_database.gd`
- Create: `godot_playwright/bundled_gameplay_modules/stats/addons/stats/stat_container.gd`
- Create: `godot_playwright/bundled_gameplay_modules/stats/demo/scenes/stats_demo.tscn`
- Create: `godot_playwright/bundled_gameplay_modules/stats/demo/scripts/stats_demo.gd`
- Create: `godot_playwright/bundled_gameplay_modules/stats/demo/resources/health.tres`
- Create: `godot_playwright/bundled_gameplay_modules/stats/demo/resources/stamina.tres`
- Create: `godot_playwright/bundled_gameplay_modules/stats/demo/resources/move_speed.tres`
- Create: `godot_playwright/bundled_gameplay_modules/stats/demo/resources/heat.tres`
- Create: `godot_playwright/bundled_gameplay_modules/stats/demo/resources/stat_database.tres`
- Create: `godot_playwright/bundled_gameplay_modules/stats/tests/test_stats_demo.py`

- [ ] **Step 1: Write failing bundled/package tests**

In `tests/test_modules.py`, add these methods inside `ModuleInstallerUnitTests` near the bundled mirror and package-data tests:

```python
    def test_packaged_stats_module_mirror_exists(self) -> None:
        bundled_root = default_module_roots()[1]
        manifest = load_module_manifest("stats", module_root=bundled_root)
        self.assertEqual(manifest["name"], "stats")
        self.assertEqual(manifest["autoloads"], [])
        self.assertTrue((bundled_root / "stats" / "addons" / "stats" / "stat_container.gd").exists())

    def test_source_and_packaged_stats_trees_are_identical(self) -> None:
        source_root, bundled_root = default_module_roots()
        source = source_root / "stats"
        bundled = bundled_root / "stats"
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

Update `test_pyproject_includes_bundled_gameplay_module_data` by adding:

```python
        self.assertIn('"bundled_gameplay_modules/stats/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/stats/addons/stats/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/stats/demo/scenes/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/stats/demo/scripts/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/stats/demo/resources/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/stats/tests/*"', pyproject)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```sh
python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_packaged_stats_module_mirror_exists tests.test_modules.ModuleInstallerUnitTests.test_source_and_packaged_stats_trees_are_identical tests.test_modules.ModuleInstallerUnitTests.test_pyproject_includes_bundled_gameplay_module_data
```

Expected: FAIL because bundled stats data and package entries do not exist.

- [ ] **Step 3: Copy source module to bundled mirror**

Run:

```sh
cp -R gameplay_modules/stats godot_playwright/bundled_gameplay_modules/stats
```

If the target exists from a prior failed attempt, remove only the stats mirror first:

```sh
rm -rf godot_playwright/bundled_gameplay_modules/stats
cp -R gameplay_modules/stats godot_playwright/bundled_gameplay_modules/stats
```

- [ ] **Step 4: Add package data entries**

In `pyproject.toml`, add stats entries after the interaction entries:

```toml
  "bundled_gameplay_modules/stats/*",
  "bundled_gameplay_modules/stats/addons/stats/*",
  "bundled_gameplay_modules/stats/demo/scenes/*",
  "bundled_gameplay_modules/stats/demo/scripts/*",
  "bundled_gameplay_modules/stats/demo/resources/*",
  "bundled_gameplay_modules/stats/tests/*",
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```sh
python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_packaged_stats_module_mirror_exists tests.test_modules.ModuleInstallerUnitTests.test_source_and_packaged_stats_trees_are_identical tests.test_modules.ModuleInstallerUnitTests.test_pyproject_includes_bundled_gameplay_module_data
```

Expected: PASS.

- [ ] **Step 6: Commit**

```sh
git add tests/test_modules.py pyproject.toml godot_playwright/bundled_gameplay_modules/stats
git commit -m "Bundle stats gameplay module"
```

---

### Task 7: Complete Human And Agent Documentation

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `gameplay_modules/stats/README.md`
- Modify: `gameplay_modules/stats/AGENT.md`
- Modify: `godot_playwright/bundled_gameplay_modules/stats/README.md`
- Modify: `godot_playwright/bundled_gameplay_modules/stats/AGENT.md`
- Modify: `README.md`

- [ ] **Step 1: Write failing docs tests**

In `tests/test_modules.py`, add this method inside `ModuleInstallerUnitTests` near the other docs tests:

```python
    def test_stats_docs_exist_for_humans_and_agents(self) -> None:
        source_root = default_module_roots()[0] / "stats"
        bundled_root = default_module_roots()[1] / "stats"
        for root in (source_root, bundled_root):
            readme = (root / "README.md").read_text(encoding="utf-8")
            agent = (root / "AGENT.md").read_text(encoding="utf-8")
            self.assertIn("godot-playwright module add /path/to/project stats", readme)
            self.assertIn("StatContainer.set_value", readme)
            self.assertIn("StatDefinition", readme)
            self.assertIn("pool", readme)
            self.assertIn("save_load", readme)
            self.assertIn("stat_id", agent)
            self.assertIn("Resource", agent)
            self.assertIn("SaveService", agent)
            self.assertIn("combat", agent)
```

Update `test_readme_gameplay_module_commands_include_inventory_and_interaction_demos` to include stats checks from Task 5 and rename it to `test_readme_gameplay_module_commands_include_current_modules`:

```python
    def test_readme_gameplay_module_commands_include_current_modules(self) -> None:
        readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")

        self.assertIn("godot-playwright module add /tmp/agent-game inventory --demo", readme)
        self.assertIn("godot-playwright module add /tmp/agent-game interaction", readme)
        self.assertIn("godot-playwright module add /tmp/agent-game interaction --demo", readme)
        self.assertIn("godot-playwright module add /tmp/agent-game stats", readme)
        self.assertIn("godot-playwright module add /tmp/agent-game stats --demo", readme)
```

- [ ] **Step 2: Run docs tests to verify they fail**

Run:

```sh
python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_stats_docs_exist_for_humans_and_agents tests.test_modules.ModuleInstallerUnitTests.test_readme_gameplay_module_commands_include_current_modules
```

Expected: FAIL because docs are incomplete and top-level README does not mention stats.

- [ ] **Step 3: Expand `gameplay_modules/stats/README.md`**

Replace `gameplay_modules/stats/README.md` with expanded docs that preserve the base and demo install commands introduced in Task 5:

````markdown
# Stats Gameplay Module

`stats` adds a Resource-driven runtime stat container for Godot 4.6+ projects.

Install into a Godot project:

```sh
godot-playwright module add /path/to/project stats
```

Install the demo scene and copied demo test:

```sh
godot-playwright module add /path/to/project stats --demo
```

The installer copies `res://addons/stats/`. It does not register an Autoload.

## Stat Definitions

Create `StatDefinition` resources for each numeric state value. Use stable `stat_id` values such as `health`, `mana`, `stamina`, `move_speed`, `attack`, `defense`, `hunger`, or `heat`.

Each definition includes:

- `stat_id`: stable identifier used by scripts and save data.
- `display_name`: human-readable label.
- `description`: optional descriptive text.
- `tags`: optional category labels.
- `default_base_value`: nominal value or pool capacity.
- `default_current_value`: runtime value used at initialization.
- `clamp_min`, `min_value`, `clamp_max`, `max_value`: bounds.
- `is_pool`: whether current value is capped by the current base value.

Add definitions to a `StatDatabase` resource and assign that database to each `StatContainer` node.

## API

```gdscript
StatContainer.initialize_stats(reset: bool = false) -> Dictionary
StatContainer.has_stat(stat_id: String) -> bool
StatContainer.get_value(stat_id: String) -> float
StatContainer.get_base_value(stat_id: String) -> float
StatContainer.get_stat(stat_id: String) -> Dictionary
StatContainer.get_stats() -> Array
StatContainer.set_value(stat_id: String, value: float) -> Dictionary
StatContainer.modify_value(stat_id: String, delta: float) -> Dictionary
StatContainer.set_base_value(stat_id: String, value: float) -> Dictionary
StatContainer.modify_base_value(stat_id: String, delta: float) -> Dictionary
StatContainer.get_state() -> Dictionary
StatContainer.apply_state(data: Dictionary) -> Dictionary
```

Operation results are dictionaries with `ok`, `stat_id`, previous/current values, previous/current base values, `requested_value`, `delta`, `clamped`, `events`, `warnings`, and `errors` fields.

## Pool Stats

Use `is_pool = true` for health, mana, stamina, batteries, shields, or other values where the current value should not exceed the base value. Lowering a pool base value clamps the current value when needed.

Non-pool stats such as `move_speed`, `attack`, or `defense` do not use the base value as a current-value maximum. They only use explicit min/max clamps.

## Signals

`StatContainer` emits `stat_changed`, `base_stat_changed`, `stat_depleted`, `stat_filled`, and `stats_changed`.

Use signals for UI, death handling, exhaustion, low-resource logic, and tests. Keep combat formulas, healing formulas, level curves, temporary effects, and UI rendering outside this module.

## Saving

Use `get_state()` and `apply_state(data)` for JSON-compatible persistence. If the project also uses `save_load`, set a stable `save_id` on stat containers that should persist. A non-empty `save_id` makes the node join the `save_participants` group and exposes wrappers compatible with `SaveService`.

Do not set `save_id` on temporary previews, generated enemies, or UI-only containers unless they must persist.

## Optional Integration

Inventory item-use scripts can call `modify_value()` after consuming an item. Interaction scripts can modify stats on use. State machines can query stats in guards. The future `effects` module can call stat mutation methods for direct tick consequences.

The core module does not import or require `inventory`, `interaction`, `state_machine`, `effects`, or `save_load`.

## Validation

```sh
godot-playwright check-scripts /path/to/project res://addons/stats --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/stats --exclude "addons/godot_playwright/**"
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```
````

- [ ] **Step 4: Expand `gameplay_modules/stats/AGENT.md`**

Replace `gameplay_modules/stats/AGENT.md` with expanded docs that preserve the base and demo install commands introduced in Task 5:

````markdown
# Agent Instructions: stats

Use this module when a Godot project needs health, mana, stamina, speed, attack, defense, hunger, temperature, morale, energy, durability-like values, or other numeric runtime state.

Install with:

```sh
godot-playwright module add /path/to/project stats
```

Use `--demo` only when adding a demo scene and copied test is acceptable:

```sh
godot-playwright module add /path/to/project stats --demo
```

## Wiring Stats

1. Create one `StatDefinition` Resource per stat.
2. Use stable `stat_id` values. Do not rename `stat_id` values after save data exists unless you also migrate saves.
3. Set `is_pool = true` for health, mana, stamina, shields, batteries, and other current/max values.
4. Set explicit min and max clamps when the value has real bounds.
5. Add definitions to a `StatDatabase` Resource.
6. Add a `StatContainer` node to the gameplay object that owns the numeric runtime state.
7. Assign the database to the `StatContainer`.

## Using Stats

Call `set_value(stat_id, value)`, `modify_value(stat_id, delta)`, `set_base_value(stat_id, value)`, and `modify_base_value(stat_id, delta)`. Always inspect returned dictionaries from mutating calls. Treat `ok: false` as a real gameplay or data error.

Use `stat_changed`, `stat_depleted`, and `stat_filled` signals for UI updates, death handling, exhaustion, empty resource behavior, or tests.

## Boundaries

Do not use this module as a combat system, effects system, progression system, skill system, inventory system, UI system, or formula engine.

Keep damage formulas, healing formulas, temporary buffs, level curves, experience tables, stat bar rendering, and gameplay consequences in project scripts or future domain modules.

Use `Inventory` only when the project has installed the inventory module and an item should change a stat. Use `SaveService` only through `save_id` on containers that should persist. Use future effects integration only after the `effects` module boundary is known.

## Saving

The module does not require `SaveService`. For custom persistence, use `get_state()` and `apply_state(data)`.

When the project uses `save_load`, set a stable `save_id` on stat containers that should persist. A non-empty `save_id` makes the node join the `save_participants` group and exposes wrappers compatible with `SaveService`.

Do not set `save_id` on temporary enemies, stat previews, shop previews, or generated test containers unless they must persist.

## Validation Commands

Run targeted checks after installation:

```sh
godot-playwright check-scripts /path/to/project res://addons/stats --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/stats --exclude "addons/godot_playwright/**"
```

Run broader validation after wiring game scenes:

```sh
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```

If using `SaveService`, run a save/load round-trip test that mutates stats after save and verifies the original values are restored after load.
````

- [ ] **Step 5: Sync bundled docs**

Run:

```sh
cp gameplay_modules/stats/README.md godot_playwright/bundled_gameplay_modules/stats/README.md
cp gameplay_modules/stats/AGENT.md godot_playwright/bundled_gameplay_modules/stats/AGENT.md
```

- [ ] **Step 6: Expand top-level README module section**

Ensure the gameplay module command block still includes the stats commands introduced in Task 5:

```sh
godot-playwright module add /tmp/agent-game stats
godot-playwright module add /tmp/agent-game stats --demo
```

Ensure the stats description introduced in Task 5 is present after the `interaction` module paragraph:

```markdown
The `stats` module adds a reusable `StatContainer` node backed by `StatDefinition` and `StatDatabase` Resources. It supports base/current values, pool stats such as health or stamina, min/max clamping, change/depletion/fill signals, JSON-compatible `get_state()` / `apply_state(data)`, and optional persistence through `save_load` when a container has a stable `save_id`.
```

- [ ] **Step 7: Run docs tests**

Run:

```sh
python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_stats_docs_exist_for_humans_and_agents tests.test_modules.ModuleInstallerUnitTests.test_readme_gameplay_module_commands_include_current_modules tests.test_modules.ModuleInstallerUnitTests.test_source_and_packaged_stats_trees_are_identical
```

Expected: PASS.

- [ ] **Step 8: Commit**

```sh
git add tests/test_modules.py README.md gameplay_modules/stats/README.md gameplay_modules/stats/AGENT.md godot_playwright/bundled_gameplay_modules/stats/README.md godot_playwright/bundled_gameplay_modules/stats/AGENT.md
git commit -m "Document stats gameplay module"
```

---

### Task 8: Final Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run focused Python module tests**

Run:

```sh
python -m unittest tests.test_modules.ModuleInstallerUnitTests
```

Expected: PASS.

- [ ] **Step 2: Run focused Godot tests if Godot is installed**

Run:

```sh
python -m unittest tests.test_modules.StatsModuleGodotTests
```

Expected when Godot is installed: PASS. If skipped because Godot is unavailable, report the skip clearly in the final implementation summary.

- [ ] **Step 3: Run existing gameplay module smoke tests**

Run:

```sh
python -m unittest tests.test_modules.InventoryModuleGodotTests tests.test_modules.StateMachineModuleGodotTests tests.test_modules.InteractionSeedModuleGodotTests tests.test_modules.SaveLoadModuleGodotTests
```

Expected when Godot is installed: PASS. If skipped because Godot is unavailable, report the skip clearly.

- [ ] **Step 4: Verify source and bundled stats trees still match**

Run:

```sh
python -m unittest tests.test_modules.ModuleInstallerUnitTests.test_source_and_packaged_stats_trees_are_identical
```

Expected: PASS.

- [ ] **Step 5: Check git status**

Run:

```sh
git status --short
```

Expected: no uncommitted changes unless final verification created ignored artifacts. If there are untracked artifacts, remove only generated test artifacts, not user files.

- [ ] **Step 6: Handle unexpected verification changes**

If Step 5 shows tracked changes, identify which earlier task introduced the needed fix, rerun that task's listed verification command, and commit the exact files through that task's commit step. If Step 5 is clean, do not create an empty commit.

---

## Self-Review Notes

- Spec coverage: The plan covers module discovery, installation, no Autoload, stat definitions, stat database validation, stat container initialization/mutation/clamping/events/state, demo resources, copied tests, optional save-load integration, bundled mirror, package data, and docs.
- Scope boundaries: The plan intentionally excludes combat formulas, effects/modifier stacks, progression curves, UI widgets, derived stat graphs, and expression evaluation.
- Type consistency: Public names match the approved spec: `StatDefinition`, `StatDatabase`, `StatContainer`, `stat_id`, `default_base_value`, `default_current_value`, `is_pool`, `initialize_stats`, `set_value`, `modify_value`, `set_base_value`, `modify_base_value`, `get_state`, and `apply_state`.
- Placeholder scan: No task relies on an unspecified file path, unnamed test, or undefined command. Parser/runtime defects found during execution must be fixed against exact Godot diagnostics and then rerun through the listed commands.
