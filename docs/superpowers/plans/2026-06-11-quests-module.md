# Quests Gameplay Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an installable `quests` gameplay module that provides Resource-driven quest and objective tracking for Godot projects.

**Architecture:** Follow the existing gameplay module pattern: source module under `gameplay_modules/quests`, bundled mirror under `godot_playwright/bundled_gameplay_modules/quests`, no Autoload, deterministic demo, copied Python demo test, strict JSON-compatible state, and structured result dictionaries for expected failures. Static authoring data lives in `QuestDefinition`, `ObjectiveDefinition`, and `QuestDatabase`; runtime state and mutation live in `QuestLog`; docs keep rewards declarative and all gameplay triggers explicit.

**Tech Stack:** Python `unittest`, `godot-playwright` module installer, Godot 4.6 GDScript, `.tres` Resource files, `.tscn` demo scene, package data in `pyproject.toml`.

---

## File Structure

Create:

- `gameplay_modules/quests/module.json` - module manifest for installer copy/demo behavior.
- `gameplay_modules/quests/README.md` - human-facing usage documentation.
- `gameplay_modules/quests/AGENT.md` - agent-facing wiring and boundary instructions.
- `gameplay_modules/quests/addons/quests/quest_constants.gd` - schema/module constants, save group name, statuses, policies, and event names.
- `gameplay_modules/quests/addons/quests/quest_result.gd` - shared result dictionary helpers.
- `gameplay_modules/quests/addons/quests/objective_definition.gd` - editor-authored objective definition Resource.
- `gameplay_modules/quests/addons/quests/quest_definition.gd` - editor-authored quest definition Resource.
- `gameplay_modules/quests/addons/quests/quest_database.gd` - definition registry and validation Resource.
- `gameplay_modules/quests/addons/quests/quest_log.gd` - runtime quest log component Node.
- `gameplay_modules/quests/demo/resources/collect_parts.tres` - demo objective Resource.
- `gameplay_modules/quests/demo/resources/scan_beacon.tres` - demo objective Resource.
- `gameplay_modules/quests/demo/resources/repair_beacon_objective.tres` - demo objective Resource.
- `gameplay_modules/quests/demo/resources/repair_beacon.tres` - demo quest Resource.
- `gameplay_modules/quests/demo/resources/quest_database.tres` - demo quest database Resource.
- `gameplay_modules/quests/demo/scenes/quests_demo.tscn` - deterministic demo scene.
- `gameplay_modules/quests/demo/scripts/quests_demo.gd` - demo assertions exposed through `run_quests_demo()`.
- `gameplay_modules/quests/tests/test_quests_demo.py` - copied demo test.
- `godot_playwright/bundled_gameplay_modules/quests/` - bundled mirror, byte-identical to `gameplay_modules/quests/`.

Modify:

- `tests/test_modules.py` - installer tests, source-shape tests, Godot runtime probes, demo tests, package-data assertions.
- `pyproject.toml` - include bundled quests package data.
- `README.md` - list quests install/demo commands and short module summary.

Do not modify:

- `godot_playwright/modules.py` - the current manifest-driven installer should discover the module automatically.
- Existing gameplay modules, except if a test import/order conflict is discovered during execution.

---

### Task 1: Add Installer Tests And Minimal Module Shell

**Files:**
- Modify: `tests/test_modules.py`
- Create: `gameplay_modules/quests/module.json`
- Create: `gameplay_modules/quests/README.md`
- Create: `gameplay_modules/quests/AGENT.md`
- Create: `gameplay_modules/quests/addons/quests/quest_constants.gd`
- Create: `gameplay_modules/quests/addons/quests/quest_result.gd`
- Create: `gameplay_modules/quests/addons/quests/objective_definition.gd`
- Create: `gameplay_modules/quests/addons/quests/quest_definition.gd`
- Create: `gameplay_modules/quests/addons/quests/quest_database.gd`
- Create: `gameplay_modules/quests/addons/quests/quest_log.gd`

- [ ] **Step 1: Write failing installer tests**

In `tests/test_modules.py`, add `test_repository_quests_module_is_discoverable()` near the existing repository module discovery tests:

```python
    def test_repository_quests_module_is_discoverable(self) -> None:
        modules = list_modules()
        quests = next(module for module in modules if module["name"] == "quests")
        self.assertEqual(quests["version"], "0.1.0")
        self.assertEqual(quests["godot_version"], ">=4.6")
        self.assertEqual(quests["autoloads"], [])
```

Add `test_add_quests_module_copies_files_without_autoload()` near the existing base copy tests:

```python
    def test_add_quests_module_copies_files_without_autoload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "quests")

            self.assertTrue(report["ok"], report)
            self.assertFalse(report["demo"])
            self.assertEqual(report["module"], "quests")
            self.assertEqual(report["autoloads"], [])
            expected_scripts = {
                "quest_constants.gd",
                "quest_result.gd",
                "objective_definition.gd",
                "quest_definition.gd",
                "quest_database.gd",
                "quest_log.gd",
            }
            for script_name in expected_scripts:
                self.assertTrue((project / "addons" / "quests" / script_name).exists(), script_name)
            project_text = (project / "project.godot").read_text(encoding="utf-8")
            self.assertNotIn("QuestService", project_text)
            copied_targets = {entry["target"] for entry in report["copied"]}
            self.assertTrue(
                {f"res://addons/quests/{script_name}" for script_name in expected_scripts}.issubset(copied_targets),
                copied_targets,
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_repository_quests_module_is_discoverable tests.test_modules.ModuleInstallerUnitTests.test_add_quests_module_copies_files_without_autoload
```

Expected: ERROR because `quests` is not discoverable.

- [ ] **Step 3: Create minimal module manifest and shell files**

Create directories:

```sh
mkdir -p gameplay_modules/quests/addons/quests
```

Create `gameplay_modules/quests/module.json`:

```json
{
  "name": "quests",
  "version": "0.1.0",
  "display_name": "Quests",
  "description": "Resource-driven quest and objective tracker for Godot projects.",
  "godot_version": ">=4.6",
  "copy": [
    {"from": "addons/quests", "to": "addons/quests"}
  ],
  "autoloads": [],
  "validation": {
    "commands": [
      "godot-playwright check-scripts /path/to/project res://addons/quests --exclude addons/godot_playwright/**",
      "godot-playwright check-resources /path/to/project res://addons/quests --exclude addons/godot_playwright/**"
    ]
  }
}
```

Create `gameplay_modules/quests/README.md`:

````markdown
# Quests Gameplay Module

`quests` adds a Resource-driven quest and objective tracker for Godot 4.6+ projects.

Install into a Godot project:

```sh
godot-playwright module add /path/to/project quests
```

The installer copies `res://addons/quests/`. It does not register an Autoload.
````

Create `gameplay_modules/quests/AGENT.md`:

````markdown
# Agent Instructions: quests

Use this module when a Godot project needs quests, objectives, tutorial steps, contracts, milestones, challenges, or scenario goals.

Install with:

```sh
godot-playwright module add /path/to/project quests
```

Keep progression explicit: project code calls `advance_objective()`, `set_objective_progress()`, or `complete_objective()` when gameplay should count toward an objective.
````

Create `gameplay_modules/quests/addons/quests/quest_constants.gd`:

```gdscript
class_name QuestConstants
extends RefCounted

const SAVE_GROUP: StringName = &"save_participants"
const SCHEMA_VERSION: int = 1
const MODULE_VERSION: String = "0.1.0"

const STATUS_INACTIVE: String = "inactive"
const STATUS_ACTIVE: String = "active"
const STATUS_COMPLETED: String = "completed"
const STATUS_FAILED: String = "failed"

const OBJECTIVE_INACTIVE: String = "inactive"
const OBJECTIVE_ACTIVE: String = "active"
const OBJECTIVE_COMPLETED: String = "completed"

const POLICY_ALL: String = "all"
const POLICY_ANY: String = "any"
```

Create `gameplay_modules/quests/addons/quests/quest_result.gd`:

```gdscript
class_name QuestResult
extends RefCounted


static func make(ok: bool = true, quest_id: String = "", objective_id: String = "") -> Dictionary:
	return {
		"ok": ok,
		"quest_id": quest_id,
		"objective_id": objective_id,
		"status": "",
		"previous_status": "",
		"progress": 0,
		"previous_progress": 0,
		"target_amount": 0,
		"clamped": false,
		"quest": {},
		"rewards": {},
		"data": {},
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

Create `gameplay_modules/quests/addons/quests/objective_definition.gd`:

```gdscript
class_name ObjectiveDefinition
extends Resource

@export var objective_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export_range(1, 999999, 1) var target_amount: int = 1
@export var optional: bool = false
@export var hidden: bool = false
@export var default_data: Dictionary = {}
```

Create `gameplay_modules/quests/addons/quests/quest_definition.gd`:

```gdscript
class_name QuestDefinition
extends Resource

@export var quest_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export var objectives: Array[Resource] = []
@export_enum("all", "any") var completion_policy: String = "all"
@export var auto_complete: bool = true
@export var start_active: bool = false
@export var rewards: Dictionary = {}
@export var default_data: Dictionary = {}
```

Create `gameplay_modules/quests/addons/quests/quest_database.gd`:

```gdscript
class_name QuestDatabase
extends Resource

@export var quests: Array[Resource] = []
```

Create `gameplay_modules/quests/addons/quests/quest_log.gd`:

```gdscript
class_name QuestLog
extends Node

@export var database: Resource
@export var save_id: StringName
@export var initialize_on_ready: bool = true
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_repository_quests_module_is_discoverable tests.test_modules.ModuleInstallerUnitTests.test_add_quests_module_copies_files_without_autoload
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```sh
git add tests/test_modules.py gameplay_modules/quests
git commit -m "Add quests gameplay module shell"
```

---

### Task 2: Add Quest Resource Helpers And Database Validation

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `gameplay_modules/quests/addons/quests/quest_constants.gd`
- Modify: `gameplay_modules/quests/addons/quests/quest_result.gd`
- Modify: `gameplay_modules/quests/addons/quests/objective_definition.gd`
- Modify: `gameplay_modules/quests/addons/quests/quest_definition.gd`
- Modify: `gameplay_modules/quests/addons/quests/quest_database.gd`

- [ ] **Step 1: Add source-shape tests**

Add this method inside `ModuleInstallerUnitTests` near the existing source helper tests:

```python
    def test_quests_source_defines_resource_helpers(self) -> None:
        source_root = default_module_roots()[0]
        quests_root = source_root / "quests" / "addons" / "quests"
        objective = (quests_root / "objective_definition.gd").read_text(encoding="utf-8")
        quest = (quests_root / "quest_definition.gd").read_text(encoding="utf-8")
        database = (quests_root / "quest_database.gd").read_text(encoding="utf-8")
        result = (quests_root / "quest_result.gd").read_text(encoding="utf-8")
        constants = (quests_root / "quest_constants.gd").read_text(encoding="utf-8")

        self.assertIn("class_name ObjectiveDefinition", objective)
        self.assertIn("@export var objective_id: StringName", objective)
        self.assertIn("@export_range(1, 999999, 1) var target_amount: int = 1", objective)
        self.assertIn("@export var optional: bool = false", objective)
        self.assertIn("@export var hidden: bool = false", objective)
        self.assertIn("@export var default_data: Dictionary = {}", objective)
        self.assertIn("class_name QuestDefinition", quest)
        self.assertIn("@export var quest_id: StringName", quest)
        self.assertIn("@export var objectives: Array[Resource] = []", quest)
        self.assertIn('@export_enum("all", "any") var completion_policy: String = "all"', quest)
        self.assertIn("@export var auto_complete: bool = true", quest)
        self.assertIn("@export var start_active: bool = false", quest)
        self.assertIn("@export var rewards: Dictionary = {}", quest)
        self.assertIn("@export var default_data: Dictionary = {}", quest)
        self.assertIn("class_name QuestDatabase", database)
        self.assertIn("func get_quest(quest_id: String) -> Resource", database)
        self.assertIn("func has_quest(quest_id: String) -> bool", database)
        self.assertIn("func get_quest_ids() -> Array[String]", database)
        self.assertIn("func get_objective(quest_id: String, objective_id: String) -> Resource", database)
        self.assertIn("func validate() -> Dictionary", database)
        self.assertIn("quests[%d] is null", database)
        self.assertIn("must be a QuestDefinition", database)
        self.assertIn("quest_id must be non-empty", database)
        self.assertIn("Duplicate quest_id", database)
        self.assertIn("Duplicate objective_id", database)
        self.assertIn("_is_json_compatible", database)
        self.assertIn("class_name QuestResult", result)
        self.assertIn('"quest_id": quest_id', result)
        self.assertIn('"objective_id": objective_id', result)
        self.assertIn('"rewards": {}', result)
        self.assertIn("static func add_event", result)
        self.assertIn("static func add_warning", result)
        self.assertIn("static func add_error", result)
        self.assertIn("const SCHEMA_VERSION: int = 1", constants)
        self.assertIn('const POLICY_ALL: String = "all"', constants)
        self.assertIn('const POLICY_ANY: String = "any"', constants)
```

- [ ] **Step 2: Add Godot database validation probe**

Add helper `_write_quests_database_probe(project: Path) -> None` in `tests/test_modules.py`. The generated script should preload `objective_definition.gd`, `quest_definition.gd`, and `quest_database.gd`, then expose `run_probe() -> Dictionary` with these assertions:

```gdscript
func run_probe() -> Dictionary:
	var errors: Array[String] = []
	var collect := ObjectiveDefinitionData.new()
	collect.objective_id = &"collect_parts"
	collect.target_amount = 3
	collect.default_data = {"item_id": "part"}

	var scan := ObjectiveDefinitionData.new()
	scan.objective_id = &"scan_beacon"
	scan.target_amount = 1

	var quest := QuestDefinitionData.new()
	quest.quest_id = &"repair_beacon"
	quest.objectives = [collect, scan]
	quest.completion_policy = "all"
	quest.rewards = {"coins": 50, "reputation": 5}
	quest.default_data = {"area": "north_field"}

	var valid_database := QuestDatabaseData.new()
	valid_database.quests.append(quest)
	_assert_ok(valid_database.validate(), "valid database", errors)
	_assert_bool(valid_database.has_quest("repair_beacon"), "has repair_beacon", errors)
	_assert_string("repair_beacon", String(valid_database.get_quest("repair_beacon").quest_id), "quest lookup", errors)
	_assert_string("collect_parts", String(valid_database.get_objective("repair_beacon", "collect_parts").objective_id), "objective lookup", errors)
	_assert_int(1, valid_database.get_quest_ids().size(), "quest id count", errors)

	var invalid_resource_database := QuestDatabaseData.new()
	invalid_resource_database.quests.append(Resource.new())
	_assert_error(invalid_resource_database.validate(), "must be a QuestDefinition", "invalid quest resource", errors)

	var empty_id := QuestDefinitionData.new()
	empty_id.quest_id = &""
	var empty_database := QuestDatabaseData.new()
	empty_database.quests.append(empty_id)
	_assert_error(empty_database.validate(), "quest_id must be non-empty", "empty quest_id", errors)

	var duplicate := QuestDefinitionData.new()
	duplicate.quest_id = &"repair_beacon"
	var duplicate_database := QuestDatabaseData.new()
	duplicate_database.quests.append(quest)
	duplicate_database.quests.append(duplicate)
	_assert_error(duplicate_database.validate(), "Duplicate quest_id", "duplicate quest_id", errors)

	var bad_policy := QuestDefinitionData.new()
	bad_policy.quest_id = &"bad_policy"
	bad_policy.completion_policy = "none"
	var bad_policy_database := QuestDatabaseData.new()
	bad_policy_database.quests.append(bad_policy)
	_assert_error(bad_policy_database.validate(), "completion_policy must be all or any", "bad policy", errors)

	var duplicate_objective := QuestDefinitionData.new()
	duplicate_objective.quest_id = &"duplicate_objective"
	var first := ObjectiveDefinitionData.new()
	first.objective_id = &"same"
	var second := ObjectiveDefinitionData.new()
	second.objective_id = &"same"
	duplicate_objective.objectives = [first, second]
	var duplicate_objective_database := QuestDatabaseData.new()
	duplicate_objective_database.quests.append(duplicate_objective)
	_assert_error(duplicate_objective_database.validate(), "Duplicate objective_id", "duplicate objective_id", errors)

	var bad_target_objective := ObjectiveDefinitionData.new()
	bad_target_objective.objective_id = &"bad_target"
	bad_target_objective.target_amount = 0
	var bad_target_quest := QuestDefinitionData.new()
	bad_target_quest.quest_id = &"bad_target_quest"
	bad_target_quest.objectives = [bad_target_objective]
	var bad_target_database := QuestDatabaseData.new()
	bad_target_database.quests.append(bad_target_quest)
	_assert_error(bad_target_database.validate(), "target_amount must be at least 1", "bad target", errors)

	var bad_rewards := QuestDefinitionData.new()
	bad_rewards.quest_id = &"bad_rewards"
	bad_rewards.rewards = {"node": self}
	var bad_rewards_database := QuestDatabaseData.new()
	bad_rewards_database.quests.append(bad_rewards)
	_assert_error(bad_rewards_database.validate(), "rewards must be JSON-compatible", "bad rewards", errors)

	return {"ok": errors.is_empty(), "errors": errors}
```

Use assertion helpers named `_assert_ok`, `_assert_error`, `_assert_bool`, `_assert_string`, and `_assert_int`, matching the existing stats and abilities probe style.

Add `QuestsModuleGodotTests.test_quest_database_validation_runs_in_godot()` that installs `quests`, writes the probe scene, runs Godot, calls `run_probe()`, and asserts `result["ok"]`.

- [ ] **Step 3: Run tests to verify they fail**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_quests_source_defines_resource_helpers tests.test_modules.QuestsModuleGodotTests.test_quest_database_validation_runs_in_godot
```

Expected: FAIL because `QuestDatabase` does not yet implement lookup and validation helpers.

- [ ] **Step 4: Implement database helpers**

Replace `quest_database.gd` with an implementation that:

- preloads `quest_definition.gd`, `objective_definition.gd`, and `quest_result.gd`;
- exposes `get_quest(quest_id)`, `has_quest(quest_id)`, `get_quest_ids()`, `get_objective(quest_id, objective_id)`, and `validate()`;
- rejects null quest resources, non-`QuestDefinition` resources, empty/whitespace quest IDs, duplicate quest IDs, invalid completion policies, non-JSON `rewards`, non-JSON quest `default_data`, null objective resources, non-`ObjectiveDefinition` resources, empty/whitespace objective IDs, duplicate objective IDs within a quest, `target_amount < 1`, and non-JSON objective `default_data`;
- treats strings, `StringName`, bools, ints, finite floats, arrays, dictionaries with string-like keys, and null as JSON-compatible;
- rejects Nodes, Resources, Callables, Signals, `INF`, `NAN`, and cyclic arrays/dictionaries.

Add a cycle-safe helper with this signature:

```gdscript
func _is_json_compatible(value: Variant, seen: Array = []) -> bool:
```

The helper should add object IDs for arrays and dictionaries to `seen`, reject a value when its ID is already present, and remove the ID before returning from that container branch.

- [ ] **Step 5: Run tests to verify they pass**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_quests_source_defines_resource_helpers tests.test_modules.QuestsModuleGodotTests.test_quest_database_validation_runs_in_godot
```

Expected: 2 tests pass.

- [ ] **Step 6: Commit**

```sh
git add tests/test_modules.py gameplay_modules/quests/addons/quests
git commit -m "Add quests resource helpers"
```

---

### Task 3: Add QuestLog Initialization, Queries, And Quest Status Transitions

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `gameplay_modules/quests/addons/quests/quest_log.gd`

- [ ] **Step 1: Add source-shape test for QuestLog API**

Add this method inside `ModuleInstallerUnitTests` near the existing container API source tests:

```python
    def test_quests_source_defines_log_api(self) -> None:
        source_root = default_module_roots()[0]
        quest_log = (source_root / "quests" / "addons" / "quests" / "quest_log.gd").read_text(encoding="utf-8")

        self.assertIn("class_name QuestLog", quest_log)
        self.assertIn("@export var database: Resource", quest_log)
        self.assertIn("@export var save_id: StringName", quest_log)
        self.assertIn("@export var initialize_on_ready: bool = true", quest_log)
        self.assertIn("signal quest_started", quest_log)
        self.assertIn("signal quest_completed", quest_log)
        self.assertIn("signal quest_failed", quest_log)
        self.assertIn("signal quest_status_changed", quest_log)
        self.assertIn("signal objective_progress_changed", quest_log)
        self.assertIn("signal objective_completed", quest_log)
        self.assertIn("signal quests_changed", quest_log)
        self.assertIn("func initialize_quests(reset: bool = false) -> Dictionary", quest_log)
        self.assertIn("func has_quest(quest_id: String) -> bool", quest_log)
        self.assertIn("func start_quest(quest_id: String, data: Dictionary = {}) -> Dictionary", quest_log)
        self.assertIn("func complete_quest(quest_id: String, data: Dictionary = {}) -> Dictionary", quest_log)
        self.assertIn("func fail_quest(quest_id: String, data: Dictionary = {}) -> Dictionary", quest_log)
        self.assertIn("func set_quest_active(quest_id: String, active: bool) -> Dictionary", quest_log)
        self.assertIn("func get_quest(quest_id: String) -> Dictionary", quest_log)
        self.assertIn("func get_quests() -> Array", quest_log)
        self.assertIn("func clear_runtime_state() -> void", quest_log)
        self.assertIn("func get_state() -> Dictionary", quest_log)
        self.assertIn("func apply_state(data: Dictionary) -> Dictionary", quest_log)
        self.assertIn("func save_state() -> Dictionary", quest_log)
        self.assertIn("func load_state(data: Dictionary) -> void", quest_log)
        self.assertIn("_quests_by_id", quest_log)
        self.assertIn("_quest_ids", quest_log)
```

- [ ] **Step 2: Add runtime status probe**

Add `_write_quests_log_status_probe(project: Path) -> None` and `QuestsModuleGodotTests.test_quest_log_status_transitions_run_in_godot()`. The probe should:

- build a database with one inactive quest `repair_beacon`, one `start_active` quest `daily_check`, and valid objectives;
- initialize a `QuestLog` with `initialize_on_ready = false`;
- assert `initialize_quests()` succeeds;
- assert `repair_beacon` starts inactive and its objectives start inactive;
- assert `daily_check` starts active and its objectives start active;
- assert `get_quests()` returns definition order;
- assert `start_quest("repair_beacon")` changes the quest and objectives to active;
- assert calling `start_quest("repair_beacon")` again is a successful no-op;
- assert `fail_quest("repair_beacon")` changes the quest to failed;
- assert `start_quest("repair_beacon")` after failure returns `ok = false`;
- assert `set_quest_active("daily_check", false)` can return an active quest with no progress to inactive;
- assert returned snapshots are deep copies by mutating a copy and verifying internal state is unchanged.

Use the same `_assert_ok`, `_assert_error`, `_assert_string`, `_assert_int`, and `_assert_dictionary` helper style used by the other module probes.

- [ ] **Step 3: Run tests to verify they fail**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_quests_source_defines_log_api tests.test_modules.QuestsModuleGodotTests.test_quest_log_status_transitions_run_in_godot
```

Expected: FAIL because `QuestLog` only has exported fields.

- [ ] **Step 4: Implement QuestLog initialization and quest status transitions**

Replace `quest_log.gd` with an implementation that:

- preloads `quest_constants.gd` and `quest_result.gd`;
- defines all seven signals from the spec;
- stores `_quests_by_id: Dictionary`, `_quest_ids: Array[String]`, and `_initialized: bool`;
- joins `QuestConstantsData.SAVE_GROUP` in `_enter_tree()` when `save_id` is non-empty;
- calls `initialize_quests()` from `_ready()` when `initialize_on_ready` is true;
- validates the database through `database.call("validate")`;
- creates one runtime quest entry per definition with `quest_id`, `status`, `data`, and ordered `objectives`;
- initializes quest status from `start_active`;
- initializes objective status to `active` when the quest starts active and `inactive` otherwise;
- duplicates `default_data` into runtime `data` so saved runtime data remains JSON-compatible and independent of definitions;
- implements `has_quest()`, `get_quest()`, `get_quests()`, and `clear_runtime_state()`;
- implements `start_quest()`, `fail_quest()`, and `set_quest_active()` as described in the spec;
- returns `QuestResult.make()` dictionaries for all expected failures.

Use compact event dictionaries shaped like:

```gdscript
{
	"ok": true,
	"type": "quest_started",
	"quest_id": quest_id,
	"objective_id": "",
	"status": QuestConstantsData.STATUS_ACTIVE,
	"warnings": [],
	"errors": [],
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_quests_source_defines_log_api tests.test_modules.QuestsModuleGodotTests.test_quest_log_status_transitions_run_in_godot
```

Expected: 2 tests pass.

- [ ] **Step 6: Commit**

```sh
git add tests/test_modules.py gameplay_modules/quests/addons/quests/quest_log.gd
git commit -m "Add quests log status runtime"
```

---

### Task 4: Add Objective Progression And Completion Policies

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `gameplay_modules/quests/addons/quests/quest_log.gd`

- [ ] **Step 1: Add objective API assertions to source-shape test**

Extend `test_quests_source_defines_log_api()` with:

```python
        self.assertIn("func advance_objective(quest_id: String, objective_id: String, amount: int = 1, data: Dictionary = {}) -> Dictionary", quest_log)
        self.assertIn("func set_objective_progress(quest_id: String, objective_id: String, amount: int, data: Dictionary = {}) -> Dictionary", quest_log)
        self.assertIn("func complete_objective(quest_id: String, objective_id: String, data: Dictionary = {}) -> Dictionary", quest_log)
        self.assertIn("_is_completion_policy_satisfied", quest_log)
        self.assertIn("_maybe_auto_complete_quest", quest_log)
```

- [ ] **Step 2: Add progression Godot probe**

Add `_write_quests_progression_probe(project: Path) -> None` and `QuestsModuleGodotTests.test_quest_objective_progression_runs_in_godot()`. The probe should:

- create an `all` policy quest with required objectives `collect_parts` target 3, `scan_beacon` target 1, and optional objective `find_note` target 1;
- create an `any` policy quest with two required objectives;
- create an `auto_complete = false` quest with one objective;
- initialize and start those quests;
- assert `advance_objective("repair_beacon", "collect_parts", 2)` updates progress to 2 and keeps objective active;
- assert `advance_objective("repair_beacon", "collect_parts", 5)` clamps progress to 3, reports `clamped = true`, completes the objective, and keeps the quest active because other required objectives remain incomplete;
- assert further progress on completed `collect_parts` fails without mutation;
- assert completing optional `find_note` does not complete the quest;
- assert completing `scan_beacon` completes the `all` policy quest and reports rewards;
- assert completing one required objective completes the `any` policy quest;
- assert optional-only progress does not satisfy an `any` policy quest;
- assert `auto_complete = false` leaves the quest active after its objective completes and `complete_quest()` then completes it;
- assert `advance_objective()` with amount 0 fails;
- assert `set_objective_progress()` with a negative amount fails;
- assert non-JSON `data` fails without mutation.

- [ ] **Step 3: Run tests to verify they fail**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_quests_source_defines_log_api tests.test_modules.QuestsModuleGodotTests.test_quest_objective_progression_runs_in_godot
```

Expected: FAIL because objective mutation methods do not yet exist.

- [ ] **Step 4: Implement objective progression**

In `quest_log.gd`, add:

- `advance_objective(quest_id, objective_id, amount, data)`;
- `set_objective_progress(quest_id, objective_id, amount, data)`;
- `complete_objective(quest_id, objective_id, data)`;
- `complete_quest(quest_id, data)`;
- `_validate_objective_mutation(result, quest_id, objective_id, data)`;
- `_set_objective_progress(quest_id, objective_id, amount, is_delta, data)`;
- `_complete_objective_runtime(quest_id, objective_id, result)`;
- `_is_completion_policy_satisfied(quest_id)`;
- `_maybe_auto_complete_quest(quest_id, result)`;
- `_complete_quest_runtime(quest_id, result, data)`;
- `_is_json_compatible(value, seen = [])` with cycle detection.

Required behavior:

- normalize quest and objective IDs with `strip_edges()`;
- `advance_objective()` requires `amount > 0`;
- `set_objective_progress()` requires `amount >= 0`;
- clamp progress to `0..target_amount`;
- expected clamping sets `result["clamped"] = true` and adds a warning;
- completed objectives and completed/failed quests reject further progress;
- inactive quests reject objective progress;
- terminal quest completion emits `quest_completed`, `quest_status_changed`, and `quests_changed`;
- objective completion emits `objective_completed`, `objective_progress_changed` when progress changed, and `quests_changed`;
- successful quest completion duplicates definition `rewards` into `result["rewards"]`;
- no external rewards, stats, inventory, abilities, effects, or interaction code is imported or called.

- [ ] **Step 5: Run tests to verify they pass**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_quests_source_defines_log_api tests.test_modules.QuestsModuleGodotTests.test_quest_objective_progression_runs_in_godot
```

Expected: 2 tests pass.

- [ ] **Step 6: Commit**

```sh
git add tests/test_modules.py gameplay_modules/quests/addons/quests/quest_log.gd
git commit -m "Add quests objective progression"
```

---

### Task 5: Add Strict State Persistence And Save Integration

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `gameplay_modules/quests/addons/quests/quest_log.gd`

- [ ] **Step 1: Add persistence regression probe**

Add `_write_quests_persistence_probe(project: Path) -> None` and `QuestsModuleGodotTests.test_quest_log_state_persistence_runs_in_godot()`. The probe should assert:

- `get_state()` returns `schema_version = 1` and an ordered `quests` array;
- applying valid state restores quest status, objective status, progress, and runtime `data`;
- applying state missing a newly added quest fills that quest from current definition defaults;
- applying a stale quest ID fails without mutating current runtime state;
- applying a stale objective ID fails without mutating current runtime state;
- applying duplicate quest IDs fails atomically;
- applying duplicate objective IDs fails atomically;
- applying `schema_version: 1.5` fails atomically;
- applying `schema_version: "1"` fails atomically;
- applying `progress: 1.5` fails atomically;
- applying a completed objective with progress below target fails atomically;
- applying an active objective with progress at target fails atomically;
- applying an active objective under an inactive quest fails atomically;
- applying non-JSON runtime `data` fails atomically.

Use a helper:

```gdscript
func _assert_state_unchanged(before: Dictionary, log: Node, label: String, errors: Array[String]) -> void:
	var after := log.get_state()
	if before != after:
		errors.append("%s mutated state: before %s after %s" % [label, str(before), str(after)])
```

- [ ] **Step 2: Add save-load wrapper probe**

Add `QuestsModuleGodotTests.test_quests_integrate_with_save_load_when_installed()`. The probe should:

- install `save_load`;
- install `quests`;
- create a `QuestLog` with `save_id = &"probe_quests"` before adding it to the scene tree;
- start a quest and advance one objective;
- assert the node is in the `save_participants` group;
- call `save_state()` directly and verify it contains the progressed objective;
- create a second `QuestLog` with the same database and call `load_state(saved_state)`;
- assert the second log restored quest status and objective progress.

- [ ] **Step 3: Run tests to verify they fail**

Run:

```sh
python3 -m unittest tests.test_modules.QuestsModuleGodotTests.test_quest_log_state_persistence_runs_in_godot tests.test_modules.QuestsModuleGodotTests.test_quests_integrate_with_save_load_when_installed
```

Expected: FAIL because strict persistence and save wrappers are incomplete.

- [ ] **Step 4: Implement state export/import**

In `quest_log.gd`, implement:

- `get_state() -> Dictionary`;
- `apply_state(data: Dictionary) -> Dictionary`;
- `get_save_id() -> String`;
- `save_state() -> Dictionary`;
- `load_state(data: Dictionary) -> void`;
- `_parse_state(data, result) -> Dictionary`;
- `_parse_quest_state(saved_quest, definition, result) -> Dictionary`;
- `_parse_objective_state(saved_objective, definition, parent_status, result) -> Dictionary`;
- `_parse_integer_field(value, field_name, result) -> int`;
- `_make_default_quest_entry(quest_id, definition) -> Dictionary`;
- `_make_default_objective_entry(objective_id, definition, quest_status) -> Dictionary`.

Required behavior:

- `apply_state()` mutates `_quests_by_id`, `_quest_ids`, and `_initialized` only after full validation succeeds;
- saved quest IDs can appear in any order but runtime order follows database order;
- saved objectives can appear in any order but runtime objective order follows definition order;
- saved state cannot contain unknown/stale quest IDs or objective IDs;
- missing saved quests initialize from current definitions in database order;
- missing saved objectives inside a saved quest initialize from current definitions;
- status/progress consistency rules from the spec are enforced;
- runtime `data` dictionaries are deep duplicated after validation;
- `load_state()` pushes one warning on failure and does not throw.

Use strict integer parsing:

```gdscript
func _parse_integer_field(value: Variant, field_name: String, result: Dictionary) -> int:
	if typeof(value) == TYPE_INT:
		return int(value)
	if typeof(value) == TYPE_FLOAT:
		var float_value := float(value)
		if not is_nan(float_value) and not is_inf(float_value) and float_value == floor(float_value):
			return int(float_value)
	QuestResultData.add_error(result, "%s must be an integer" % field_name)
	return 0
```

- [ ] **Step 5: Run focused tests**

Run:

```sh
python3 -m unittest tests.test_modules.QuestsModuleGodotTests.test_quest_log_state_persistence_runs_in_godot tests.test_modules.QuestsModuleGodotTests.test_quests_integrate_with_save_load_when_installed
```

Expected: 2 tests pass.

- [ ] **Step 6: Run all quest Godot tests**

Run:

```sh
python3 -m unittest tests.test_modules.QuestsModuleGodotTests
```

Expected: all current quest Godot tests pass.

- [ ] **Step 7: Commit**

```sh
git add tests/test_modules.py gameplay_modules/quests/addons/quests/quest_log.gd
git commit -m "Add quests state persistence"
```

---

### Task 6: Add Demo Scene, Resources, And Copied Demo Test

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `gameplay_modules/quests/module.json`
- Create: `gameplay_modules/quests/demo/resources/collect_parts.tres`
- Create: `gameplay_modules/quests/demo/resources/scan_beacon.tres`
- Create: `gameplay_modules/quests/demo/resources/repair_beacon_objective.tres`
- Create: `gameplay_modules/quests/demo/resources/repair_beacon.tres`
- Create: `gameplay_modules/quests/demo/resources/quest_database.tres`
- Create: `gameplay_modules/quests/demo/scenes/quests_demo.tscn`
- Create: `gameplay_modules/quests/demo/scripts/quests_demo.gd`
- Create: `gameplay_modules/quests/tests/test_quests_demo.py`

- [ ] **Step 1: Add installer demo test**

Add this method inside `ModuleInstallerUnitTests` near the other demo copy tests:

```python
    def test_add_quests_module_with_demo_copies_demo_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "quests", demo=True)

            self.assertTrue(report["ok"], report)
            self.assertTrue(report["demo"])
            self.assertTrue((project / "scenes" / "quests_demo" / "quests_demo.tscn").exists())
            self.assertTrue((project / "scripts" / "quests_demo" / "quests_demo.gd").exists())
            self.assertTrue((project / "resources" / "quests_demo" / "quest_database.tres").exists())
            self.assertTrue((project / "tests" / "quests_demo" / "test_quests_demo.py").exists())
```

- [ ] **Step 2: Add Godot demo tests**

Add these methods to `QuestsModuleGodotTests`:

```python
    def test_installed_quests_scripts_parse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Quests Parse Probe")
            add_module(project, "quests", demo=True)

            result = check_project_scripts(
                project,
                ["res://addons/quests", "res://scripts/quests_demo"],
                excludes=["addons/godot_playwright/**"],
            )

            self.assertTrue(result.ok, result.errors)

    def test_installed_quests_demo_resources_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Quests Resource Probe")
            add_module(project, "quests", demo=True)

            result = check_project_resources(
                project,
                ["res://scenes/quests_demo", "res://resources/quests_demo"],
                excludes=["addons/godot_playwright/**"],
            )

            self.assertTrue(result.ok, result.errors)

    def test_quests_demo_runs_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Quests Demo Probe")
            add_module(project, "quests", demo=True)
            probe = probe_project(project, scene="res://scenes/quests_demo/quests_demo.tscn")

            self.assertTrue(probe.ok, probe.errors)

            with Godot(project) as godot:
                godot.open_scene("res://scenes/quests_demo/quests_demo.tscn")
                result = godot.evaluate("return get_tree().current_scene.run_quests_demo()")

            self.assertTrue(result["ok"], result.get("errors"))
            self.assertEqual(result["quest_status"], "completed")
            self.assertEqual(result["collect_progress"], 3)
            self.assertEqual(result["scan_progress"], 1)
            self.assertEqual(result["repair_progress"], 1)
            self.assertEqual(result["rewards"]["coins"], 50)
            self.assertEqual(result["rewards"]["reputation"], 5)
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_add_quests_module_with_demo_copies_demo_assets tests.test_modules.QuestsModuleGodotTests.test_installed_quests_scripts_parse tests.test_modules.QuestsModuleGodotTests.test_installed_quests_demo_resources_are_valid tests.test_modules.QuestsModuleGodotTests.test_quests_demo_runs_in_runtime
```

Expected: FAIL because demo assets do not exist.

- [ ] **Step 4: Add demo copy manifest**

Update `gameplay_modules/quests/module.json` with:

```json
  "demo": {
    "copy": [
      {"from": "demo/scenes", "to": "scenes/quests_demo"},
      {"from": "demo/scripts", "to": "scripts/quests_demo"},
      {"from": "demo/resources", "to": "resources/quests_demo"},
      {"from": "tests", "to": "tests/quests_demo"}
    ]
  },
```

Keep the JSON valid by placing this object before `"validation"`.

- [ ] **Step 5: Add demo resources**

Create `.tres` resources for:

- `collect_parts`: `ObjectiveDefinition`, `objective_id = "collect_parts"`, target 3, default data `{"item_id": "part"}`;
- `scan_beacon`: `ObjectiveDefinition`, `objective_id = "scan_beacon"`, target 1, default data `{"ability_id": "scan"}`;
- `repair_beacon_objective`: `ObjectiveDefinition`, `objective_id = "repair_beacon"`, target 1, default data `{"ability_id": "repair"}`;
- `repair_beacon`: `QuestDefinition`, `quest_id = "repair_beacon"`, `completion_policy = "all"`, `auto_complete = true`, rewards `{"coins": 50, "reputation": 5}`, objectives referencing the three objective resources;
- `quest_database`: `QuestDatabase`, quests referencing `repair_beacon`.

Use the existing `.tres` style from `gameplay_modules/abilities/demo/resources/ability_database.tres` and keep `load_steps`, `ext_resource`, and `sub_resource` IDs valid.

- [ ] **Step 6: Add demo script and scene**

Create `gameplay_modules/quests/demo/scripts/quests_demo.gd` with:

```gdscript
extends Control

@onready var quest_log: QuestLog = $QuestLog


func run_quests_demo() -> Dictionary:
	var errors: Array[String] = []
	var start := quest_log.start_quest("repair_beacon", {"source": "demo"})
	_assert_ok(start, "start quest", errors)
	var collect := quest_log.advance_objective("repair_beacon", "collect_parts", 3)
	_assert_ok(collect, "collect parts", errors)
	var scan := quest_log.complete_objective("repair_beacon", "scan_beacon")
	_assert_ok(scan, "scan beacon", errors)
	var repair := quest_log.complete_objective("repair_beacon", "repair_beacon")
	_assert_ok(repair, "repair beacon", errors)
	var quest := quest_log.get_quest("repair_beacon")
	var objectives := _objectives_by_id(quest)
	var rewards: Dictionary = repair.get("rewards", {})
	return {
		"ok": errors.is_empty(),
		"errors": errors,
		"quest_status": String(quest.get("status", "")),
		"collect_progress": int(objectives.get("collect_parts", {}).get("progress", -1)),
		"scan_progress": int(objectives.get("scan_beacon", {}).get("progress", -1)),
		"repair_progress": int(objectives.get("repair_beacon", {}).get("progress", -1)),
		"rewards": rewards,
	}


func _ready() -> void:
	quest_log.initialize_quests()


func _objectives_by_id(quest: Dictionary) -> Dictionary:
	var by_id := {}
	for objective in quest.get("objectives", []):
		by_id[String(objective.get("objective_id", ""))] = objective
	return by_id


func _assert_ok(result: Dictionary, label: String, errors: Array[String]) -> void:
	if not bool(result.get("ok", false)):
		errors.append("%s failed: %s" % [label, str(result)])
```

Create `quests_demo.tscn` with a `Control` root using `quests_demo.gd` and one child `QuestLog` node that references `quest_database.tres`.

- [ ] **Step 7: Add copied demo test**

Create `gameplay_modules/quests/tests/test_quests_demo.py`:

```python
from __future__ import annotations

from godot_playwright import Godot
from godot_playwright.probe import probe_project


def test_quests_demo_runs(godot_project):
    probe = probe_project(godot_project, scene="res://scenes/quests_demo/quests_demo.tscn")
    assert probe.ok, probe.errors

    with Godot(godot_project) as godot:
        godot.open_scene("res://scenes/quests_demo/quests_demo.tscn")
        result = godot.evaluate("return get_tree().current_scene.run_quests_demo()")

    assert result["ok"], result.get("errors")
    assert result["quest_status"] == "completed"
    assert result["collect_progress"] == 3
    assert result["scan_progress"] == 1
    assert result["repair_progress"] == 1
    assert result["rewards"]["coins"] == 50
    assert result["rewards"]["reputation"] == 5
```

- [ ] **Step 8: Run tests to verify they pass**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_add_quests_module_with_demo_copies_demo_assets tests.test_modules.QuestsModuleGodotTests.test_installed_quests_scripts_parse tests.test_modules.QuestsModuleGodotTests.test_installed_quests_demo_resources_are_valid tests.test_modules.QuestsModuleGodotTests.test_quests_demo_runs_in_runtime
```

Expected: 4 tests pass.

- [ ] **Step 9: Commit**

```sh
git add tests/test_modules.py gameplay_modules/quests
git commit -m "Add quests gameplay module demo"
```

---

### Task 7: Bundle Module, Package Data, And Documentation

**Files:**
- Modify: `tests/test_modules.py`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `gameplay_modules/quests/README.md`
- Modify: `gameplay_modules/quests/AGENT.md`
- Create: `godot_playwright/bundled_gameplay_modules/quests/`

- [ ] **Step 1: Add package-data and docs tests**

Extend `ModuleInstallerUnitTests.test_pyproject_includes_bundled_gameplay_modules()` with:

```python
        self.assertIn('"bundled_gameplay_modules/quests/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/quests/addons/quests/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/quests/demo/scenes/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/quests/demo/scripts/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/quests/demo/resources/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/quests/tests/*"', pyproject)
```

Add `test_quests_docs_describe_boundaries()` near the existing docs tests:

```python
    def test_quests_docs_describe_boundaries(self) -> None:
        source_root = default_module_roots()[0]
        readme = (source_root / "quests" / "README.md").read_text(encoding="utf-8")
        agent = (source_root / "quests" / "AGENT.md").read_text(encoding="utf-8")

        self.assertIn("QuestDefinition", readme)
        self.assertIn("ObjectiveDefinition", readme)
        self.assertIn("QuestDatabase", readme)
        self.assertIn("QuestLog", readme)
        self.assertIn("advance_objective", readme)
        self.assertIn("completion_policy", readme)
        self.assertIn("Rewards are reported", readme)
        self.assertIn("does not automatically", readme)
        self.assertIn("get_state()", readme)
        self.assertIn("apply_state(data)", readme)
        self.assertIn("Prefer explicit progression", agent)
        self.assertIn("JSON-compatible", agent)
        self.assertIn("Do not add hidden dependencies", agent)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_pyproject_includes_bundled_gameplay_modules tests.test_modules.ModuleInstallerUnitTests.test_quests_docs_describe_boundaries
```

Expected: FAIL because package data and full docs are not updated.

- [ ] **Step 3: Update package data**

Add these entries to `pyproject.toml` under `[tool.setuptools.package-data]` next to the other bundled gameplay modules:

```toml
  "bundled_gameplay_modules/quests/*",
  "bundled_gameplay_modules/quests/addons/quests/*",
  "bundled_gameplay_modules/quests/demo/scenes/*",
  "bundled_gameplay_modules/quests/demo/scripts/*",
  "bundled_gameplay_modules/quests/demo/resources/*",
  "bundled_gameplay_modules/quests/tests/*",
```

- [ ] **Step 4: Expand source docs**

Replace `gameplay_modules/quests/README.md` with a full guide that includes:

- install and demo install commands;
- definition field explanations for `QuestDefinition` and `ObjectiveDefinition`;
- `QuestLog` API list;
- explicit progression examples;
- `all` and `any` completion policy explanation;
- optional objective behavior;
- rewards reported but not automatically applied;
- saving through `get_state()` / `apply_state(data)` and optional `save_load`;
- optional integration with interaction, inventory, stats, abilities, effects, state machine, dialogue, and combat project code;
- validation commands.

Replace `gameplay_modules/quests/AGENT.md` with concise generation guidance:

- install command;
- stable lowercase IDs;
- explicit progression calls;
- rewards and runtime data must be JSON-compatible;
- no Nodes, Resources, Callables, Signals, or UI references in saved state;
- no hidden imports or dependencies on other modules;
- preserve byte-identical source and bundled trees.

- [ ] **Step 5: Update root README**

In `README.md`, add install commands:

```sh
godot-playwright module add /tmp/agent-game quests
godot-playwright module add /tmp/agent-game quests --demo
```

Add a short summary after the abilities paragraph:

```markdown
The `quests` module adds a reusable `QuestLog` node backed by `QuestDefinition`, `ObjectiveDefinition`, and `QuestDatabase` Resources. It supports explicit quest start/fail/complete flow, objective progress, `all`/`any` completion policies, optional objectives, structured mutation results, JSON-compatible `get_state()` / `apply_state(data)`, and optional persistence through `save_load` when a log has a stable `save_id`. Rewards are reported in completion results but are not automatically granted.
```

- [ ] **Step 6: Mirror source module to bundled tree**

Run:

```sh
mkdir -p godot_playwright/bundled_gameplay_modules
rm -rf godot_playwright/bundled_gameplay_modules/quests
cp -R gameplay_modules/quests godot_playwright/bundled_gameplay_modules/quests
```

- [ ] **Step 7: Run tests to verify they pass**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests.test_pyproject_includes_bundled_gameplay_modules tests.test_modules.ModuleInstallerUnitTests.test_quests_docs_describe_boundaries
```

Expected: 2 tests pass.

- [ ] **Step 8: Verify source and bundled module are identical**

Run:

```sh
diff -qr gameplay_modules/quests godot_playwright/bundled_gameplay_modules/quests
```

Expected: no output.

- [ ] **Step 9: Commit**

```sh
git add tests/test_modules.py pyproject.toml README.md gameplay_modules/quests godot_playwright/bundled_gameplay_modules/quests
git commit -m "Bundle quests gameplay module"
```

---

### Task 8: Final Verification And Branch Handoff

**Files:**
- No source edits expected unless verification reveals a defect.

- [ ] **Step 1: Run installer unit tests**

Run:

```sh
python3 -m unittest tests.test_modules.ModuleInstallerUnitTests
```

Expected: all tests pass.

- [ ] **Step 2: Run quest Godot tests**

Run:

```sh
python3 -m unittest tests.test_modules.QuestsModuleGodotTests
```

Expected: all quest Godot tests pass.

- [ ] **Step 3: Run existing gameplay module smoke tests**

Run:

```sh
python3 -m unittest \
  tests.test_modules.StatsModuleGodotTests \
  tests.test_modules.AbilitiesModuleGodotTests \
  tests.test_modules.EffectsModuleGodotTests \
  tests.test_modules.EffectsSeedModuleGodotTests \
  tests.test_modules.InventoryModuleGodotTests \
  tests.test_modules.InventorySeedModuleGodotTests \
  tests.test_modules.StateMachineModuleGodotTests \
  tests.test_modules.InteractionSeedModuleGodotTests \
  tests.test_modules.SaveLoadModuleGodotTests
```

Expected: all listed tests pass.

- [ ] **Step 4: Run mirror diffs**

Run:

```sh
diff -qr gameplay_modules/quests godot_playwright/bundled_gameplay_modules/quests
diff -qr gameplay_modules/stats godot_playwright/bundled_gameplay_modules/stats
diff -qr gameplay_modules/abilities godot_playwright/bundled_gameplay_modules/abilities
```

Expected: no output.

- [ ] **Step 5: Run whitespace check**

Run:

```sh
git diff --check
```

Expected: no output.

- [ ] **Step 6: Inspect status and recent commits**

Run:

```sh
git status --short --branch
git log --oneline -n 12
```

Expected: working tree clean; recent commits show the quest module work in task order.

- [ ] **Step 7: Use finishing workflow**

Use `superpowers:finishing-a-development-branch` before merging, deleting branches, or asking whether to push. Do not push unless the user explicitly asks for a push.
