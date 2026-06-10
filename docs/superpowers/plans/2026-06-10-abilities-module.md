# Abilities Gameplay Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an installable `abilities` gameplay module that provides Resource-driven instant action/ability containers for Godot projects.

**Architecture:** Follow the existing gameplay module pattern: source module under `gameplay_modules/abilities`, bundled mirror under `godot_playwright/bundled_gameplay_modules/abilities`, no Autoload, deterministic demo, copied Python demo test, and structured result dictionaries for expected failures. Runtime logic lives in `AbilityContainer`; static tunable data lives in `AbilityDefinition` and `AbilityDatabase`; docs explain that costs are reported but not automatically spent and that cast/channel timing stays outside v1.

**Tech Stack:** Python `unittest`, `godot-playwright` module installer, Godot 4.6 GDScript, `.tres` Resource files, `.tscn` demo scene, package data in `pyproject.toml`.

---

## File Structure

Create:

- `gameplay_modules/abilities/module.json` - module manifest for installer copy/demo behavior.
- `gameplay_modules/abilities/README.md` - human-facing usage documentation.
- `gameplay_modules/abilities/AGENT.md` - agent-facing wiring and boundary instructions.
- `gameplay_modules/abilities/addons/abilities/ability_constants.gd` - schema/module constants and save group name.
- `gameplay_modules/abilities/addons/abilities/ability_result.gd` - shared result dictionary helpers.
- `gameplay_modules/abilities/addons/abilities/ability_definition.gd` - editor-authored ability definition Resource.
- `gameplay_modules/abilities/addons/abilities/ability_database.gd` - definition registry and validation Resource.
- `gameplay_modules/abilities/addons/abilities/ability_container.gd` - runtime ability component Node.
- `gameplay_modules/abilities/demo/resources/dash.tres` - demo charged cooldown ability.
- `gameplay_modules/abilities/demo/resources/scan.tres` - demo no-charge cooldown ability.
- `gameplay_modules/abilities/demo/resources/repair.tres` - demo multi-charge recovery ability.
- `gameplay_modules/abilities/demo/resources/ability_database.tres` - demo ability database.
- `gameplay_modules/abilities/demo/scenes/abilities_demo.tscn` - deterministic demo scene.
- `gameplay_modules/abilities/demo/scripts/abilities_demo.gd` - demo assertions exposed through `run_abilities_demo()`.
- `gameplay_modules/abilities/tests/test_abilities_demo.py` - copied demo test.
- `godot_playwright/bundled_gameplay_modules/abilities/module.json` - bundled manifest.
- `godot_playwright/bundled_gameplay_modules/abilities/README.md` - bundled human docs.
- `godot_playwright/bundled_gameplay_modules/abilities/AGENT.md` - bundled agent docs.
- `godot_playwright/bundled_gameplay_modules/abilities/addons/abilities/` - bundled addon scripts.
- `godot_playwright/bundled_gameplay_modules/abilities/demo/` - bundled demo scene, scripts, and resources.
- `godot_playwright/bundled_gameplay_modules/abilities/tests/` - bundled copied demo test.

Modify:

- `tests/test_modules.py` - installer, source shape, docs, runtime, demo, and save-load integration tests.
- `pyproject.toml` - include bundled abilities package data.
- `README.md` - list abilities install/demo commands and short module summary.

Do not modify:

- `godot_playwright/modules.py` - the current manifest-driven installer should discover the module automatically.
- Existing gameplay modules, unless a test import/order conflict is discovered during execution.

---

### Task 1: Add Installer Tests And Minimal Module Shell

**Files:**
- Modify: `tests/test_modules.py`
- Create: `gameplay_modules/abilities/module.json`
- Create: `gameplay_modules/abilities/README.md`
- Create: `gameplay_modules/abilities/AGENT.md`
- Create: `gameplay_modules/abilities/addons/abilities/ability_constants.gd`
- Create: `gameplay_modules/abilities/addons/abilities/ability_result.gd`
- Create: `gameplay_modules/abilities/addons/abilities/ability_definition.gd`
- Create: `gameplay_modules/abilities/addons/abilities/ability_database.gd`
- Create: `gameplay_modules/abilities/addons/abilities/ability_container.gd`

- [ ] **Step 1: Write failing installer tests**

Add `test_repository_abilities_module_is_discoverable()` inside `ModuleInstallerUnitTests` immediately after `test_repository_effects_module_is_discoverable()`. Add `test_add_abilities_module_copies_files_without_autoload()` immediately after `test_add_effects_module_copies_files_without_autoload()`:

```python
    def test_repository_abilities_module_is_discoverable(self) -> None:
        modules = list_modules()
        abilities = next(module for module in modules if module["name"] == "abilities")
        self.assertEqual(abilities["version"], "0.1.0")
        self.assertEqual(abilities["godot_version"], ">=4.6")
        self.assertEqual(abilities["autoloads"], [])

    def test_add_abilities_module_copies_files_without_autoload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "abilities")

            self.assertTrue(report["ok"], report)
            self.assertFalse(report["demo"])
            self.assertEqual(report["module"], "abilities")
            self.assertEqual(report["autoloads"], [])
            expected_scripts = {
                "ability_constants.gd",
                "ability_result.gd",
                "ability_definition.gd",
                "ability_database.gd",
                "ability_container.gd",
            }
            for script_name in expected_scripts:
                self.assertTrue((project / "addons" / "abilities" / script_name).exists(), script_name)
            project_text = (project / "project.godot").read_text(encoding="utf-8")
            self.assertNotIn("AbilityService", project_text)
            copied_targets = {entry["target"] for entry in report["copied"]}
            self.assertTrue(
                {f"res://addons/abilities/{script_name}" for script_name in expected_scripts}.issubset(copied_targets),
                copied_targets,
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_repository_abilities_module_is_discoverable tests.test_modules.ModuleInstallerUnitTests.test_add_abilities_module_copies_files_without_autoload
```

Expected: ERROR because `abilities` is not discoverable.

- [ ] **Step 3: Create minimal module manifest and shell files**

Create directories:

```sh
mkdir -p gameplay_modules/abilities/addons/abilities
```

Create `gameplay_modules/abilities/module.json`:

```json
{
  "name": "abilities",
  "version": "0.1.0",
  "display_name": "Abilities",
  "description": "Resource-driven instant ability and action container for Godot projects.",
  "godot_version": ">=4.6",
  "copy": [
    {"from": "addons/abilities", "to": "addons/abilities"}
  ],
  "autoloads": [],
  "validation": {
    "commands": [
      "godot-playwright check-scripts /path/to/project res://addons/abilities --exclude addons/godot_playwright/**",
      "godot-playwright check-resources /path/to/project res://addons/abilities --exclude addons/godot_playwright/**"
    ]
  }
}
```

Create `gameplay_modules/abilities/README.md`:

````markdown
# Abilities Gameplay Module

`abilities` adds a Resource-driven instant ability and action container for Godot 4.6+ projects.

Install into a Godot project:

```sh
godot-playwright module add /path/to/project abilities
```

The installer copies `res://addons/abilities/`. It does not register an Autoload.
````

Create `gameplay_modules/abilities/AGENT.md`:

````markdown
# Agent Instructions: abilities

Use this module when a Godot project needs instant actions such as dashes, attacks, scans, repairs, reloads, build commands, tool uses, or unit commands with cooldowns, charges, enabled state, and structured activation results.

Install with:

```sh
godot-playwright module add /path/to/project abilities
```
````

Create parseable GDScript shell files:

`gameplay_modules/abilities/addons/abilities/ability_constants.gd`

```gdscript
class_name AbilityConstants
extends RefCounted

const SAVE_GROUP: StringName = &"save_participants"
const SCHEMA_VERSION: int = 1
const MODULE_VERSION: String = "0.1.0"
```

`gameplay_modules/abilities/addons/abilities/ability_result.gd`

```gdscript
class_name AbilityResult
extends RefCounted


static func make(ok: bool = true, ability_id: String = "") -> Dictionary:
	return {
		"ok": ok,
		"ability_id": ability_id,
		"enabled": true,
		"cooldown_remaining": 0.0,
		"charges": 0,
		"max_charges": 0,
		"charge_recovery_remaining": 0.0,
		"costs": {},
		"data": {},
		"context": {},
		"events": [],
		"warnings": [],
		"errors": [],
	}
```

`gameplay_modules/abilities/addons/abilities/ability_definition.gd`

```gdscript
class_name AbilityDefinition
extends Resource

@export var ability_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export var cooldown: float = 0.0
@export_range(0, 999, 1) var max_charges: int = 1
@export_range(0, 999, 1) var initial_charges: int = 1
@export var charge_recovery_time: float = 0.0
@export var enabled_by_default: bool = true
@export var costs: Dictionary = {}
@export var default_data: Dictionary = {}
```

`gameplay_modules/abilities/addons/abilities/ability_database.gd`

```gdscript
class_name AbilityDatabase
extends Resource

@export var abilities: Array[Resource] = []
```

`gameplay_modules/abilities/addons/abilities/ability_container.gd`

```gdscript
class_name AbilityContainer
extends Node

@export var database: Resource
@export var save_id: StringName
@export var initialize_on_ready: bool = true
@export var auto_update: bool = true
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_repository_abilities_module_is_discoverable tests.test_modules.ModuleInstallerUnitTests.test_add_abilities_module_copies_files_without_autoload
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```sh
git add tests/test_modules.py gameplay_modules/abilities
git commit -m "Add abilities gameplay module shell"
```

---

### Task 2: Add Ability Resource Helpers

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `gameplay_modules/abilities/addons/abilities/ability_constants.gd`
- Modify: `gameplay_modules/abilities/addons/abilities/ability_result.gd`
- Modify: `gameplay_modules/abilities/addons/abilities/ability_definition.gd`
- Modify: `gameplay_modules/abilities/addons/abilities/ability_database.gd`

- [ ] **Step 1: Add source-shape tests**

Add this method inside `ModuleInstallerUnitTests` immediately after `test_effects_source_defines_resource_helpers()`:

```python
    def test_abilities_source_defines_resource_helpers(self) -> None:
        source_root = default_module_roots()[0]
        abilities_root = source_root / "abilities" / "addons" / "abilities"
        definition = (abilities_root / "ability_definition.gd").read_text(encoding="utf-8")
        database = (abilities_root / "ability_database.gd").read_text(encoding="utf-8")
        result = (abilities_root / "ability_result.gd").read_text(encoding="utf-8")
        constants = (abilities_root / "ability_constants.gd").read_text(encoding="utf-8")

        self.assertIn("class_name AbilityDefinition", definition)
        self.assertIn("@export var ability_id: StringName", definition)
        self.assertIn("@export var display_name: String", definition)
        self.assertIn("@export_multiline var description: String", definition)
        self.assertIn("@export var tags: Array[StringName] = []", definition)
        self.assertIn("@export var cooldown: float = 0.0", definition)
        self.assertIn("@export_range(0, 999, 1) var max_charges: int = 1", definition)
        self.assertIn("@export_range(0, 999, 1) var initial_charges: int = 1", definition)
        self.assertIn("@export var charge_recovery_time: float = 0.0", definition)
        self.assertIn("@export var enabled_by_default: bool = true", definition)
        self.assertIn("@export var costs: Dictionary = {}", definition)
        self.assertIn("@export var default_data: Dictionary = {}", definition)
        self.assertIn("class_name AbilityDatabase", database)
        self.assertIn("func get_ability(ability_id: String) -> Resource", database)
        self.assertIn("func has_ability(ability_id: String) -> bool", database)
        self.assertIn("func get_ability_ids() -> Array[String]", database)
        self.assertIn("func validate() -> Dictionary", database)
        self.assertIn("abilities[%d] is null", database)
        self.assertIn("must be an AbilityDefinition", database)
        self.assertIn("ability_id must be non-empty", database)
        self.assertIn("Duplicate ability_id", database)
        self.assertIn("_is_json_compatible", database)
        self.assertIn("class_name AbilityResult", result)
        self.assertIn('"ability_id": ability_id', result)
        self.assertIn('"costs": {}', result)
        self.assertIn('"context": {}', result)
        self.assertIn("static func add_event", result)
        self.assertIn("static func add_warning", result)
        self.assertIn("static func add_error", result)
        self.assertIn("const SCHEMA_VERSION: int = 1", constants)
```

- [ ] **Step 2: Add Godot database validation probe**

Create a helper `_write_abilities_database_probe(project: Path) -> None` immediately before `_write_stats_database_probe(project: Path)`. The generated script should create valid and invalid `AbilityDefinition` resources and assert:

```gdscript
extends Node

const AbilityDefinitionData := preload("res://addons/abilities/ability_definition.gd")
const AbilityDatabaseData := preload("res://addons/abilities/ability_database.gd")


func run_probe() -> Dictionary:
	var errors: Array[String] = []
	var dash := AbilityDefinitionData.new()
	dash.ability_id = &"dash"
	dash.cooldown = 0.5
	dash.max_charges = 1
	dash.initial_charges = 1
	dash.costs = {"stamina": 20.0}
	dash.default_data = {"range": 4.0}

	var valid_database := AbilityDatabaseData.new()
	valid_database.abilities.append(dash)
	_assert_ok(valid_database.validate(), "valid database", errors)
	_assert_bool(valid_database.has_ability("dash"), "has dash", errors)
	_assert_string("dash", String(valid_database.get_ability("dash").ability_id), "dash lookup", errors)
	_assert_int(1, valid_database.get_ability_ids().size(), "ability id count", errors)

	var invalid_resource_database := AbilityDatabaseData.new()
	invalid_resource_database.abilities.append(Resource.new())
	_assert_error(invalid_resource_database.validate(), "must be an AbilityDefinition", "invalid resource", errors)

	var empty_id := AbilityDefinitionData.new()
	empty_id.ability_id = &""
	var empty_database := AbilityDatabaseData.new()
	empty_database.abilities.append(empty_id)
	_assert_error(empty_database.validate(), "ability_id must be non-empty", "empty ability_id", errors)

	var duplicate := AbilityDefinitionData.new()
	duplicate.ability_id = &"dash"
	var duplicate_database := AbilityDatabaseData.new()
	duplicate_database.abilities.append(dash)
	duplicate_database.abilities.append(duplicate)
	_assert_error(duplicate_database.validate(), "Duplicate ability_id", "duplicate ability_id", errors)

	var bad_cooldown := AbilityDefinitionData.new()
	bad_cooldown.ability_id = &"bad_cooldown"
	bad_cooldown.cooldown = -1.0
	var cooldown_database := AbilityDatabaseData.new()
	cooldown_database.abilities.append(bad_cooldown)
	_assert_error(cooldown_database.validate(), "cooldown must be zero or greater", "bad cooldown", errors)

	var bad_charges := AbilityDefinitionData.new()
	bad_charges.ability_id = &"bad_charges"
	bad_charges.max_charges = 1
	bad_charges.initial_charges = 2
	var charges_database := AbilityDatabaseData.new()
	charges_database.abilities.append(bad_charges)
	_assert_error(charges_database.validate(), "initial_charges must be <= max_charges", "bad charges", errors)

	var bad_data := AbilityDefinitionData.new()
	bad_data.ability_id = &"bad_data"
	bad_data.default_data = {"node": self}
	var data_database := AbilityDatabaseData.new()
	data_database.abilities.append(bad_data)
	_assert_error(data_database.validate(), "default_data must be JSON-compatible", "bad default_data", errors)

	var bad_costs := AbilityDefinitionData.new()
	bad_costs.ability_id = &"bad_costs"
	bad_costs.costs = {"node": self}
	var costs_database := AbilityDatabaseData.new()
	costs_database.abilities.append(bad_costs)
	_assert_error(costs_database.validate(), "costs must be JSON-compatible", "bad costs", errors)

	return {"ok": errors.is_empty(), "errors": errors}


func _assert_ok(result: Dictionary, label: String, errors: Array[String]) -> void:
	if not bool(result.get("ok", false)):
		errors.append("%s failed: %s" % [label, str(result)])


func _assert_error(result: Dictionary, needle: String, label: String, errors: Array[String]) -> void:
	if bool(result.get("ok", true)):
		errors.append("%s should fail" % label)
		return
	for message in result.get("errors", []):
		if String(message).contains(needle):
			return
	errors.append("%s missing %s in %s" % [label, needle, str(result)])


func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
	if not value:
		errors.append(message)


func _assert_string(expected: String, actual: String, label: String, errors: Array[String]) -> void:
	if expected != actual:
		errors.append("%s: expected %s, got %s" % [label, expected, actual])


func _assert_int(expected: int, actual: int, label: String, errors: Array[String]) -> void:
	if expected != actual:
		errors.append("%s: expected %d, got %d" % [label, expected, actual])
```

Also add `AbilitiesModuleGodotTests.test_ability_database_validation_runs_in_godot()` that installs `abilities`, writes this probe scene, runs Godot, calls `run_probe()`, and asserts `result["ok"]`.

- [ ] **Step 3: Run tests to verify they fail**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_abilities_source_defines_resource_helpers tests.test_modules.AbilitiesModuleGodotTests.test_ability_database_validation_runs_in_godot
```

Expected: FAIL because `AbilityDatabase` does not yet implement validation helpers.

- [ ] **Step 4: Implement resource helpers**

Replace `ability_result.gd` with helpers matching the stats/effects style:

```gdscript
class_name AbilityResult
extends RefCounted


static func make(ok: bool = true, ability_id: String = "") -> Dictionary:
	return {
		"ok": ok,
		"ability_id": ability_id,
		"enabled": true,
		"cooldown_remaining": 0.0,
		"charges": 0,
		"max_charges": 0,
		"charge_recovery_remaining": 0.0,
		"costs": {},
		"data": {},
		"context": {},
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

Replace `ability_database.gd` with an implementation that:

- preloads `ability_definition.gd` and `ability_result.gd`;
- exposes `get_ability(ability_id)`, `has_ability(ability_id)`, `get_ability_ids()`, and `validate()`;
- rejects null resources, non-`AbilityDefinition` resources, empty/whitespace IDs, duplicate IDs, non-finite or negative numeric fields, `initial_charges > max_charges`, and non-JSON `costs`/`default_data`;
- treats strings, bools, ints, floats, arrays, and dictionaries as JSON-compatible when nested values are also compatible;
- rejects `Node`, `Resource`, `Callable`, `Signal`, `INF`, and `NAN`.

Use this helper shape so `ability_container.gd` in Task 3 can reuse the same validation expectations:

```gdscript
func _is_json_compatible(value: Variant) -> bool:
	var value_type := typeof(value)
	if value == null:
		return true
	if value_type == TYPE_BOOL or value_type == TYPE_INT or value_type == TYPE_STRING or value_type == TYPE_STRING_NAME:
		return true
	if value_type == TYPE_FLOAT:
		var number := float(value)
		return not is_nan(number) and not is_inf(number)
	if value is Array:
		for item in value:
			if not _is_json_compatible(item):
				return false
		return true
	if value is Dictionary:
		for key in value.keys():
			if typeof(key) != TYPE_STRING and typeof(key) != TYPE_STRING_NAME:
				return false
			if not _is_json_compatible(value[key]):
				return false
		return true
	return false
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_abilities_source_defines_resource_helpers tests.test_modules.AbilitiesModuleGodotTests.test_ability_database_validation_runs_in_godot
```

Expected: 2 tests pass.

- [ ] **Step 6: Commit**

```sh
git add tests/test_modules.py gameplay_modules/abilities/addons/abilities
git commit -m "Add abilities resource helpers"
```

---

### Task 3: Add AbilityContainer Core Runtime API

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `gameplay_modules/abilities/addons/abilities/ability_container.gd`

- [ ] **Step 1: Add source-shape test for container API**

Add this method inside `ModuleInstallerUnitTests` near the source API tests:

```python
    def test_abilities_source_defines_container_api(self) -> None:
        source_root = default_module_roots()[0]
        container = (source_root / "abilities" / "addons" / "abilities" / "ability_container.gd").read_text(
            encoding="utf-8"
        )

        self.assertIn("class_name AbilityContainer", container)
        self.assertIn("@export var database: Resource", container)
        self.assertIn("@export var save_id: StringName", container)
        self.assertIn("@export var initialize_on_ready: bool = true", container)
        self.assertIn("@export var auto_update: bool = true", container)
        self.assertIn("signal ability_activated", container)
        self.assertIn("signal ability_failed", container)
        self.assertIn("signal ability_enabled_changed", container)
        self.assertIn("signal ability_cooldown_ready", container)
        self.assertIn("signal ability_charge_recovered", container)
        self.assertIn("signal abilities_changed", container)
        self.assertIn("func initialize_abilities(reset: bool = false) -> Dictionary", container)
        self.assertIn("func has_ability(ability_id: String) -> bool", container)
        self.assertIn("func can_activate(ability_id: String, context: Dictionary = {}) -> Dictionary", container)
        self.assertIn("func activate(ability_id: String, context: Dictionary = {}) -> Dictionary", container)
        self.assertIn("func set_enabled(ability_id: String, enabled: bool) -> Dictionary", container)
        self.assertIn("func is_enabled(ability_id: String) -> bool", container)
        self.assertIn("func get_ability_runtime(ability_id: String) -> Dictionary", container)
        self.assertIn("func get_abilities() -> Array", container)
        self.assertIn("func update_abilities(delta: float) -> Array[Dictionary]", container)
        self.assertIn("func clear_runtime_state() -> void", container)
        self.assertIn("func get_state() -> Dictionary", container)
        self.assertIn("func apply_state(data: Dictionary) -> Dictionary", container)
        self.assertIn("func save_state() -> Dictionary", container)
        self.assertIn("func load_state(data: Dictionary) -> void", container)
        self.assertIn("AbilityConstantsData.SCHEMA_VERSION", container)
        self.assertIn("_parse_integer_field", container)
```

- [ ] **Step 2: Add runtime Godot probe**

Add `_write_abilities_container_probe(project: Path) -> None` and `AbilitiesModuleGodotTests.test_ability_container_runtime_runs_in_godot()`. The probe should:

- create `dash`, `scan`, and `repair` definitions in a database;
- initialize a container with `initialize_on_ready = false`;
- assert `initialize_abilities()` succeeds;
- assert `can_activate("dash")` succeeds and does not mutate charges/cooldown;
- activate `dash` and assert costs/data/context are reported;
- assert immediate second `dash` fails due to cooldown or charges without changing state;
- call `update_abilities(0.5)` and assert cooldown/charge readiness recovers;
- disable `scan`, assert activation fails, enable it, assert activation succeeds;
- activate `repair` twice, assert charge count drops to zero, update recovery, assert charge recovers;
- assert `update_abilities(-1.0)` returns one failed event and does not mutate runtime state.

Use assertion helpers matching the existing stats/effects probes:

```gdscript
func _assert_ok(result: Dictionary, label: String, errors: Array[String]) -> void:
	if not bool(result.get("ok", false)):
		errors.append("%s failed: %s" % [label, str(result)])


func _assert_error(result: Dictionary, needle: String, label: String, errors: Array[String]) -> void:
	if bool(result.get("ok", true)):
		errors.append("%s should fail" % label)
		return
	for message in result.get("errors", []):
		if String(message).contains(needle):
			return
	errors.append("%s missing %s in %s" % [label, needle, str(result)])
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_abilities_source_defines_container_api tests.test_modules.AbilitiesModuleGodotTests.test_ability_container_runtime_runs_in_godot
```

Expected: FAIL because the shell `AbilityContainer` does not implement the runtime API.

- [ ] **Step 4: Implement `AbilityContainer` runtime logic**

Replace `ability_container.gd` with a focused implementation following these decisions:

- preload `ability_constants.gd` and `ability_result.gd`;
- define all six signals from the spec;
- store `_abilities_by_id: Dictionary`, `_ability_ids: Array[String]`, and `_initialized: bool`;
- add `_enter_tree()` to join `AbilityConstantsData.SAVE_GROUP` when `save_id` is non-empty;
- add `_ready()` to call `initialize_abilities()` when `initialize_on_ready` is true;
- add `_process(delta)` to call `update_abilities(delta)` when `auto_update` is true and initialized;
- implement `_validate_database(result)` using `validate()`, `has_ability()`, `get_ability()`, and `get_ability_ids()`;
- initialize runtime entries from definitions with keys `ability_id`, `enabled`, `cooldown_remaining`, `charges`, and `charge_recovery_remaining`;
- implement `can_activate()` by validating without mutation;
- implement `activate()` by calling the same validation, spending one charge when `max_charges > 0`, starting cooldown/recovery timers, adding `ability_activated`, emitting `ability_activated` and `abilities_changed`;
- implement failure results so `activate()` emits `ability_failed` and `abilities_changed` when a known activation attempt fails;
- implement `set_enabled()` with `ability_enabled_changed` events only when the value changes;
- implement `update_abilities(delta)` as deterministic timer advancement with `ability_cooldown_ready` and `ability_charge_recovered` events;
- return copied dictionaries from `get_ability_runtime()` and `get_abilities()`;
- add `_is_json_compatible(value)` in the container to validate activation context.

Use these key helper signatures:

```gdscript
func _make_ability_result(ability_id: String) -> Dictionary:
	var result := AbilityResultData.make(true, ability_id)
	if _abilities_by_id.has(ability_id):
		var runtime: Dictionary = _abilities_by_id[ability_id]
		var definition: Resource = database.call("get_ability", ability_id)
		result["enabled"] = bool(runtime.get("enabled", true))
		result["cooldown_remaining"] = float(runtime.get("cooldown_remaining", 0.0))
		result["charges"] = int(runtime.get("charges", 0))
		result["max_charges"] = int(definition.max_charges)
		result["charge_recovery_remaining"] = float(runtime.get("charge_recovery_remaining", 0.0))
		result["costs"] = (definition.costs as Dictionary).duplicate(true)
		result["data"] = (definition.default_data as Dictionary).duplicate(true)
	return result
```

```gdscript
func _start_charge_recovery(runtime: Dictionary, definition: Resource) -> void:
	if int(definition.max_charges) <= 0:
		return
	if int(runtime.get("charges", 0)) >= int(definition.max_charges):
		return
	if float(runtime.get("charge_recovery_remaining", 0.0)) > 0.0:
		return
	var recovery_time := float(definition.charge_recovery_time)
	if recovery_time <= 0.0:
		recovery_time = float(definition.cooldown)
	if recovery_time > 0.0:
		runtime["charge_recovery_remaining"] = recovery_time
```

```gdscript
func _is_json_compatible(value: Variant) -> bool:
	var value_type := typeof(value)
	if value == null:
		return true
	if value_type == TYPE_BOOL or value_type == TYPE_INT or value_type == TYPE_STRING or value_type == TYPE_STRING_NAME:
		return true
	if value_type == TYPE_FLOAT:
		var number := float(value)
		return not is_nan(number) and not is_inf(number)
	if value is Array:
		for item in value:
			if not _is_json_compatible(item):
				return false
		return true
	if value is Dictionary:
		for key in value.keys():
			if typeof(key) != TYPE_STRING and typeof(key) != TYPE_STRING_NAME:
				return false
			if not _is_json_compatible(value[key]):
				return false
		return true
	return false
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_abilities_source_defines_container_api tests.test_modules.AbilitiesModuleGodotTests.test_ability_container_runtime_runs_in_godot
```

Expected: 2 tests pass.

- [ ] **Step 6: Commit**

```sh
git add tests/test_modules.py gameplay_modules/abilities/addons/abilities/ability_container.gd
git commit -m "Add abilities container runtime API"
```

---

### Task 4: Add State Persistence And Save Integration

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `gameplay_modules/abilities/addons/abilities/ability_container.gd`

- [ ] **Step 1: Add runtime persistence regression probe**

Add `_write_abilities_container_review_probe(project: Path) -> None` and `AbilitiesModuleGodotTests.test_ability_container_review_regressions_are_validated()`. The probe should assert:

- applying a state missing a newly added ability fills that ability from current definition defaults;
- applying state containing a stale ability ID fails without mutating runtime state;
- applying `schema_version: 1.5` fails without mutating runtime state;
- applying `schema_version: "1"` fails without mutating runtime state;
- applying non-integer `charges` fails without mutating runtime state;
- applying `cooldown_remaining < 0.0` fails without mutating runtime state;
- applying `enabled: "yes"` fails without mutating runtime state.

Use this state comparison helper:

```gdscript
func _assert_dictionary(expected: Dictionary, actual: Dictionary, label: String, errors: Array[String]) -> void:
	if expected != actual:
		errors.append("%s: expected %s, got %s" % [label, str(expected), str(actual)])
```

- [ ] **Step 2: Add save-load integration probe**

Add `AbilitiesModuleGodotTests.test_abilities_demo_integrates_with_save_load_when_installed()` or a direct save-load probe that:

- installs `save_load`;
- installs `abilities`;
- creates an `AbilityContainer` with `save_id = &"probe_abilities"` before adding it to the scene tree;
- activates an ability so cooldown/charges change;
- saves state through `SaveService` or direct save participant wrappers;
- clears runtime state;
- loads state;
- asserts cooldown/charge state was restored.

- [ ] **Step 3: Run tests to verify they fail**

Run:

```sh
python3 -m unittest tests.test_modules.AbilitiesModuleGodotTests.test_ability_container_review_regressions_are_validated tests.test_modules.AbilitiesModuleGodotTests.test_abilities_demo_integrates_with_save_load_when_installed
```

Expected: FAIL because `get_state()`, `apply_state()`, and save wrappers are incomplete.

- [ ] **Step 4: Implement persistence**

In `ability_container.gd`, implement:

- `get_state() -> Dictionary` returning `{"schema_version": AbilityConstantsData.SCHEMA_VERSION, "abilities": get_abilities()}`;
- `apply_state(data: Dictionary) -> Dictionary` that parses into local dictionaries and mutates `_abilities_by_id`, `_ability_ids`, and `_initialized` only when the result remains `ok`;
- `get_save_id() -> String`, `save_state() -> Dictionary`, and `load_state(data: Dictionary) -> void`;
- `_parse_state(data, result)` with strict schema parsing and state validation;
- `_parse_integer_field(value, field_name, result)` matching the strict pattern used by inventory/stats;
- missing saved abilities filled from current definitions in database order;
- stale saved ability IDs treated as errors;
- all malformed state failures leaving previous runtime state unchanged.

Use this strict parser shape:

```gdscript
func _parse_integer_field(value: Variant, field_name: String, result: Dictionary) -> int:
	if typeof(value) == TYPE_INT:
		return int(value)
	if typeof(value) == TYPE_FLOAT:
		var float_value := float(value)
		if float_value == floor(float_value):
			return int(float_value)
	AbilityResultData.add_error(result, "%s must be an integer" % field_name)
	return 0
```

- [ ] **Step 5: Run focused tests**

Run:

```sh
python3 -m unittest tests.test_modules.AbilitiesModuleGodotTests.test_ability_container_review_regressions_are_validated tests.test_modules.AbilitiesModuleGodotTests.test_abilities_demo_integrates_with_save_load_when_installed
```

Expected: 2 tests pass.

- [ ] **Step 6: Run all abilities Godot tests**

Run:

```sh
python3 -m unittest tests.test_modules.AbilitiesModuleGodotTests
```

Expected: all current abilities Godot tests pass.

- [ ] **Step 7: Commit**

```sh
git add tests/test_modules.py gameplay_modules/abilities/addons/abilities/ability_container.gd
git commit -m "Add abilities state persistence"
```

---

### Task 5: Add Demo Scene, Resources, And Copied Demo Test

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `gameplay_modules/abilities/module.json`
- Create: `gameplay_modules/abilities/demo/resources/dash.tres`
- Create: `gameplay_modules/abilities/demo/resources/scan.tres`
- Create: `gameplay_modules/abilities/demo/resources/repair.tres`
- Create: `gameplay_modules/abilities/demo/resources/ability_database.tres`
- Create: `gameplay_modules/abilities/demo/scenes/abilities_demo.tscn`
- Create: `gameplay_modules/abilities/demo/scripts/abilities_demo.gd`
- Create: `gameplay_modules/abilities/tests/test_abilities_demo.py`

- [ ] **Step 1: Add installer demo tests**

Add this method inside `ModuleInstallerUnitTests` immediately after `test_add_effects_module_with_demo_copies_demo_assets()`:

```python
    def test_add_abilities_module_with_demo_copies_demo_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "abilities", demo=True)

            self.assertTrue(report["ok"], report)
            self.assertTrue(report["demo"])
            self.assertTrue((project / "scenes" / "abilities_demo" / "abilities_demo.tscn").exists())
            self.assertTrue((project / "scripts" / "abilities_demo" / "abilities_demo.gd").exists())
            self.assertTrue((project / "resources" / "abilities_demo" / "ability_database.tres").exists())
            self.assertTrue((project / "tests" / "abilities_demo" / "test_abilities_demo.py").exists())
```

- [ ] **Step 2: Add Godot demo tests**

Add these methods to `AbilitiesModuleGodotTests` after `test_ability_container_review_regressions_are_validated()`:

```python
    def test_installed_abilities_scripts_parse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Abilities Parse Probe")
            add_module(project, "abilities", demo=True)

            result = check_project_scripts(
                project,
                ["res://addons/abilities", "res://scripts/abilities_demo"],
                excludes=["addons/godot_playwright/**"],
            )

            self.assertTrue(result.ok, result.errors)

    def test_installed_abilities_demo_resources_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Abilities Resource Probe")
            add_module(project, "abilities", demo=True)

            result = check_project_resources(
                project,
                ["res://scenes/abilities_demo", "res://resources/abilities_demo"],
                excludes=["addons/godot_playwright/**"],
            )

            self.assertTrue(result.ok, result.errors)

    def test_abilities_demo_runs_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Abilities Demo Probe")
            add_module(project, "abilities", demo=True)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8")
                + '\nrun/main_scene="res://scenes/abilities_demo/abilities_demo.tscn"\n',
                encoding="utf-8",
            )

            with Godot(project) as godot:
                result = godot.locator("#AbilitiesDemo").call("run_abilities_demo")

            self.assertTrue(result["ok"], result)

    def test_installed_abilities_demo_test_runs_without_main_scene_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Abilities Demo Test Probe")
            add_module(project, "abilities", demo=True)

            result = run_tests(project, [project / "tests" / "abilities_demo"], extra_args=["--quiet"])

            self.assertEqual(result.exit_code, 0, result.output)
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_add_abilities_module_with_demo_copies_demo_assets tests.test_modules.AbilitiesModuleGodotTests.test_installed_abilities_scripts_parse tests.test_modules.AbilitiesModuleGodotTests.test_installed_abilities_demo_resources_are_valid tests.test_modules.AbilitiesModuleGodotTests.test_abilities_demo_runs_in_runtime tests.test_modules.AbilitiesModuleGodotTests.test_installed_abilities_demo_test_runs_without_main_scene_override
```

Expected: FAIL because demo files and manifest demo copy data do not exist.

- [ ] **Step 4: Add demo copy data to manifest**

Update `gameplay_modules/abilities/module.json` to include:

```json
  "demo": {
    "copy": [
      {"from": "demo/scenes", "to": "scenes/abilities_demo"},
      {"from": "demo/scripts", "to": "scripts/abilities_demo"},
      {"from": "demo/resources", "to": "resources/abilities_demo"},
      {"from": "tests", "to": "tests/abilities_demo"}
    ]
  },
```

Keep the existing `validation` block after `demo`.

- [ ] **Step 5: Create demo resources**

Create three `AbilityDefinition` `.tres` files:

`dash.tres`:

```ini
[gd_resource type="Resource" script_class="AbilityDefinition" load_steps=2 format=3]

[ext_resource type="Script" path="res://addons/abilities/ability_definition.gd" id="1_definition"]

[resource]
script = ExtResource("1_definition")
ability_id = &"dash"
display_name = "Dash"
description = "A short movement action. The abilities module reports stamina cost but does not spend it."
tags = Array[StringName]([&"movement"])
cooldown = 0.5
max_charges = 1
initial_charges = 1
charge_recovery_time = 0.5
costs = {"stamina": 20.0}
default_data = {"range": 4.0}
```

`scan.tres`:

```ini
[gd_resource type="Resource" script_class="AbilityDefinition" load_steps=2 format=3]

[ext_resource type="Script" path="res://addons/abilities/ability_definition.gd" id="1_definition"]

[resource]
script = ExtResource("1_definition")
ability_id = &"scan"
display_name = "Scan"
description = "A no-charge utility action with a cooldown."
tags = Array[StringName]([&"utility"])
cooldown = 1.0
max_charges = 0
initial_charges = 0
default_data = {"range": 6.0}
```

`repair.tres`:

```ini
[gd_resource type="Resource" script_class="AbilityDefinition" load_steps=2 format=3]

[ext_resource type="Script" path="res://addons/abilities/ability_definition.gd" id="1_definition"]

[resource]
script = ExtResource("1_definition")
ability_id = &"repair"
display_name = "Repair"
description = "A multi-charge action. The abilities module reports material cost but does not spend inventory."
tags = Array[StringName]([&"utility", &"tool"])
cooldown = 0.0
max_charges = 2
initial_charges = 2
charge_recovery_time = 2.0
costs = {"parts": 1}
default_data = {"amount": 15.0}
```

Create `ability_database.tres` referencing all three resources in demo order.

- [ ] **Step 6: Create demo scene and script**

Create `abilities_demo.tscn` with one `Node` named `AbilitiesDemo`, the demo script, an `AbilityContainer` child, and the demo database resource assigned to the container.

Create `abilities_demo.gd` with `run_abilities_demo() -> Dictionary`. It should:

- initialize the child container;
- activate `dash` once and assert success;
- assert a second immediate `dash` fails;
- call `update_abilities(0.5)` and assert `dash` can activate again;
- disable and re-enable `scan`;
- activate `scan` with `{"target_id": "crate_01"}`;
- activate `repair` twice and assert charges reach zero;
- call `update_abilities(2.0)` and assert one `repair` charge recovers;
- return `{"ok": errors.is_empty(), "errors": errors}`.

- [ ] **Step 7: Create copied demo test**

Create `gameplay_modules/abilities/tests/test_abilities_demo.py`:

```python
from godot_playwright import Godot


def test_abilities_demo_runtime(project_path):
    with Godot(project_path) as godot:
        result = godot.locator("#AbilitiesDemo").call("run_abilities_demo")
    assert result["ok"], result
```

- [ ] **Step 8: Run demo tests to verify they pass**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_add_abilities_module_with_demo_copies_demo_assets tests.test_modules.AbilitiesModuleGodotTests.test_installed_abilities_scripts_parse tests.test_modules.AbilitiesModuleGodotTests.test_installed_abilities_demo_resources_are_valid tests.test_modules.AbilitiesModuleGodotTests.test_abilities_demo_runs_in_runtime tests.test_modules.AbilitiesModuleGodotTests.test_installed_abilities_demo_test_runs_without_main_scene_override
```

Expected: 5 tests pass.

- [ ] **Step 9: Commit**

```sh
git add tests/test_modules.py gameplay_modules/abilities
git commit -m "Add abilities gameplay module demo"
```

---

### Task 6: Add Bundled Mirror And Package Data

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `pyproject.toml`
- Create: `godot_playwright/bundled_gameplay_modules/abilities/`

- [ ] **Step 1: Add package and mirror tests**

Add these methods or assertions inside `ModuleInstallerUnitTests`:

```python
    def test_packaged_abilities_module_mirror_exists(self) -> None:
        bundled_root = default_module_roots()[1]
        manifest = load_module_manifest("abilities", module_root=bundled_root)
        self.assertEqual(manifest["name"], "abilities")
        self.assertEqual(manifest["autoloads"], [])
        self.assertTrue((bundled_root / "abilities" / "addons" / "abilities" / "ability_container.gd").exists())

    def test_source_and_packaged_abilities_trees_are_identical(self) -> None:
        source_root, bundled_root = default_module_roots()
        source = source_root / "abilities"
        bundled = bundled_root / "abilities"
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

Extend `test_pyproject_includes_bundled_gameplay_module_data()` with:

```python
        self.assertIn('"bundled_gameplay_modules/abilities/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/abilities/addons/abilities/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/abilities/demo/scenes/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/abilities/demo/scripts/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/abilities/demo/resources/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/abilities/tests/*"', pyproject)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_packaged_abilities_module_mirror_exists tests.test_modules.ModuleInstallerUnitTests.test_source_and_packaged_abilities_trees_are_identical tests.test_modules.ModuleInstallerUnitTests.test_pyproject_includes_bundled_gameplay_module_data
```

Expected: FAIL because bundled abilities and package data are missing.

- [ ] **Step 3: Copy source module to bundled mirror**

Run:

```sh
mkdir -p godot_playwright/bundled_gameplay_modules
cp -R gameplay_modules/abilities godot_playwright/bundled_gameplay_modules/abilities
```

If the target already exists during a rerun, remove only `godot_playwright/bundled_gameplay_modules/abilities` first, then copy from source again.

- [ ] **Step 4: Add package data**

In `pyproject.toml`, add these entries immediately after the `"bundled_gameplay_modules/stats/tests/*"` package-data entry:

```toml
  "bundled_gameplay_modules/abilities/*",
  "bundled_gameplay_modules/abilities/addons/abilities/*",
  "bundled_gameplay_modules/abilities/demo/scenes/*",
  "bundled_gameplay_modules/abilities/demo/scripts/*",
  "bundled_gameplay_modules/abilities/demo/resources/*",
  "bundled_gameplay_modules/abilities/tests/*",
```

- [ ] **Step 5: Run tests and identity diff**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_packaged_abilities_module_mirror_exists tests.test_modules.ModuleInstallerUnitTests.test_source_and_packaged_abilities_trees_are_identical tests.test_modules.ModuleInstallerUnitTests.test_pyproject_includes_bundled_gameplay_module_data
diff -qr gameplay_modules/abilities godot_playwright/bundled_gameplay_modules/abilities
```

Expected: tests pass and `diff -qr` prints no output.

- [ ] **Step 6: Commit**

```sh
git add tests/test_modules.py pyproject.toml godot_playwright/bundled_gameplay_modules/abilities
git commit -m "Bundle abilities gameplay module"
```

---

### Task 7: Add Documentation And Root README Entries

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `README.md`
- Modify: `gameplay_modules/abilities/README.md`
- Modify: `gameplay_modules/abilities/AGENT.md`
- Modify: `godot_playwright/bundled_gameplay_modules/abilities/README.md`
- Modify: `godot_playwright/bundled_gameplay_modules/abilities/AGENT.md`

- [ ] **Step 1: Add documentation tests**

Add this method inside `ModuleInstallerUnitTests` immediately after `test_effects_docs_exist_for_humans_and_agents()`:

```python
    def test_abilities_docs_exist_for_humans_and_agents(self) -> None:
        source_root = default_module_roots()[0] / "abilities"
        bundled_root = default_module_roots()[1] / "abilities"
        for root in (source_root, bundled_root):
            readme = (root / "README.md").read_text(encoding="utf-8")
            agent = (root / "AGENT.md").read_text(encoding="utf-8")
            self.assertIn("godot-playwright module add /path/to/project abilities", readme)
            self.assertIn("godot-playwright module add /path/to/project abilities --demo", readme)
            self.assertIn("AbilityContainer.activate", readme)
            self.assertIn("AbilityContainer.can_activate", readme)
            self.assertIn("AbilityDefinition", readme)
            self.assertIn("cooldown", readme)
            self.assertIn("charges", readme)
            self.assertIn("costs are reported", readme)
            self.assertIn("not automatically spent", readme)
            self.assertIn("save_load", readme)
            self.assertIn("state_machine", readme)
            self.assertIn("godot-playwright check-scripts", readme)
            self.assertIn("ability_id", agent)
            self.assertIn("instant", agent)
            self.assertIn("can_activate", agent)
            self.assertIn("Do not store engine objects", agent)
            self.assertIn("Do not use this module as a combat system", agent)
            self.assertIn("save_participants", agent)
```

Extend `test_readme_gameplay_module_commands_include_current_modules()` with:

```python
        self.assertIn("godot-playwright module add /tmp/agent-game abilities", readme)
        self.assertIn("godot-playwright module add /tmp/agent-game abilities --demo", readme)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_abilities_docs_exist_for_humans_and_agents tests.test_modules.ModuleInstallerUnitTests.test_readme_gameplay_module_commands_include_current_modules
```

Expected: FAIL because docs are still minimal and root README does not list `abilities`.

- [ ] **Step 3: Expand module README**

Replace `gameplay_modules/abilities/README.md` with sections covering:

- install commands with and without `--demo`;
- definition fields;
- `AbilityContainer` API;
- instant activation rules;
- cooldown and charge behavior;
- explicit cost boundary: costs are reported but not automatically spent;
- saving with `save_id` and `save_load`;
- optional integrations with stats, inventory, effects, interaction, and state machines;
- validation commands.

Include this exact API block:

```gdscript
AbilityContainer.initialize_abilities(reset: bool = false) -> Dictionary
AbilityContainer.has_ability(ability_id: String) -> bool
AbilityContainer.can_activate(ability_id: String, context: Dictionary = {}) -> Dictionary
AbilityContainer.activate(ability_id: String, context: Dictionary = {}) -> Dictionary
AbilityContainer.set_enabled(ability_id: String, enabled: bool) -> Dictionary
AbilityContainer.is_enabled(ability_id: String) -> bool
AbilityContainer.get_ability_runtime(ability_id: String) -> Dictionary
AbilityContainer.get_abilities() -> Array
AbilityContainer.update_abilities(delta: float) -> Array[Dictionary]
AbilityContainer.get_state() -> Dictionary
AbilityContainer.apply_state(data: Dictionary) -> Dictionary
```

- [ ] **Step 4: Expand AGENT instructions**

Replace `gameplay_modules/abilities/AGENT.md` with concise instructions that state:

- use stable `ability_id` values;
- use `can_activate()` for guards and `activate()` for accepted requests;
- abilities are instant in v1;
- keep combat, animation, input, AI decisions, resource spending, and effect application outside the module;
- costs are reported, not automatically spent;
- do not store engine objects in `default_data`, `context`, or saved state;
- set `save_id` before the node enters the tree when persistence is needed;
- run validation commands after install.

- [ ] **Step 5: Update root README**

In `README.md`, add:

```sh
godot-playwright module add /tmp/agent-game abilities
godot-playwright module add /tmp/agent-game abilities --demo
```

Add a short summary paragraph:

```markdown
The `abilities` module adds a reusable `AbilityContainer` node backed by `AbilityDefinition` and `AbilityDatabase` Resources. It supports instant action requests, cooldowns, charges, enabled state, structured activation results, JSON-compatible `get_state()` / `apply_state(data)`, and optional persistence through `save_load` when a container has a stable `save_id`. Costs are reported in activation results but are not automatically spent.
```

- [ ] **Step 6: Sync docs to bundled mirror**

Run:

```sh
cp gameplay_modules/abilities/README.md godot_playwright/bundled_gameplay_modules/abilities/README.md
cp gameplay_modules/abilities/AGENT.md godot_playwright/bundled_gameplay_modules/abilities/AGENT.md
```

- [ ] **Step 7: Run docs and identity tests**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_abilities_docs_exist_for_humans_and_agents tests.test_modules.ModuleInstallerUnitTests.test_readme_gameplay_module_commands_include_current_modules tests.test_modules.ModuleInstallerUnitTests.test_source_and_packaged_abilities_trees_are_identical
diff -qr gameplay_modules/abilities godot_playwright/bundled_gameplay_modules/abilities
```

Expected: tests pass and `diff -qr` prints no output.

- [ ] **Step 8: Commit**

```sh
git add README.md tests/test_modules.py gameplay_modules/abilities/README.md gameplay_modules/abilities/AGENT.md godot_playwright/bundled_gameplay_modules/abilities/README.md godot_playwright/bundled_gameplay_modules/abilities/AGENT.md
git commit -m "Document abilities gameplay module"
```

---

### Task 8: Final Verification And Review

**Files:**
- No planned source edits.

- [ ] **Step 1: Run full installer tests**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests
```

Expected: all module installer tests pass.

- [ ] **Step 2: Run abilities Godot tests**

Run:

```sh
python3 -m unittest tests.test_modules.AbilitiesModuleGodotTests
```

Expected: all abilities Godot tests pass.

- [ ] **Step 3: Run existing module smoke tests**

Run:

```sh
python3 -m unittest tests.test_modules.StatsModuleGodotTests tests.test_modules.EffectsModuleGodotTests tests.test_modules.EffectsSeedModuleGodotTests tests.test_modules.InventoryModuleGodotTests tests.test_modules.InventorySeedModuleGodotTests tests.test_modules.StateMachineModuleGodotTests tests.test_modules.InteractionSeedModuleGodotTests tests.test_modules.SaveLoadModuleGodotTests
```

Expected: all listed Godot tests pass.

- [ ] **Step 4: Verify source and bundled mirrors**

Run:

```sh
diff -qr gameplay_modules/abilities godot_playwright/bundled_gameplay_modules/abilities
diff -qr gameplay_modules/stats godot_playwright/bundled_gameplay_modules/stats
diff -qr gameplay_modules/effects godot_playwright/bundled_gameplay_modules/effects
```

Expected: no output from all three commands.

- [ ] **Step 5: Verify whitespace and status**

Run:

```sh
git diff --check
git status --short
```

Expected: `git diff --check` prints no output. `git status --short` shows only intentional uncommitted edits if a final review fix is in progress; otherwise it is empty.

- [ ] **Step 6: Request final code review**

Use `superpowers:requesting-code-review`. Review range should start at the abilities design commit or the parent of Task 1 and end at current `HEAD`. The reviewer prompt should ask specifically about:

- strict persistence parsing;
- no hidden `stats`, `inventory`, or `effects` dependency;
- source/bundled mirror identity;
- demo determinism;
- cost boundary documented and implemented as report-only.

- [ ] **Step 7: Fix review issues one at a time**

For every Critical or Important review issue:

1. Add or update a failing test that captures the issue.
2. Run the focused test and confirm it fails for the expected reason.
3. Implement the smallest fix.
4. Sync source and bundled `abilities` files when any module file changes.
5. Run the focused test, full abilities tests, installer mirror test, and `diff -qr`.
6. Commit the fix with a targeted message.
7. Request re-review when all Critical and Important issues are resolved.

- [ ] **Step 8: Finish branch**

After review passes and all verification commands pass, use `superpowers:finishing-a-development-branch` to present merge/PR/keep/discard options. Do not merge, push, or delete work without the user's selected option.
