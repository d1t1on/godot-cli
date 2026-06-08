# Gameplay Module System and Save Load MVP Design

Date: 2026-06-08

## Context

`godot-playwright` already gives AI agents a strong Godot automation loop: project initialization, add-on installation, editor/runtime control, static inspection, script/resource checks, scene probes, project validation, UI scene generation, and Python test execution. The next bottleneck is not only control over Godot, but reusable gameplay capability. High-intelligence models can already build good small games, but larger indie games need common systems that should not be rebuilt from scratch every time.

This design adds a reusable gameplay module layer. The first module is `save_load`, chosen because it is foundational for multi-hour games and can support later modules such as `inventory`, `interaction`, `quest`, and `world_state`. Projectile systems are intentionally deferred because high-volume projectile performance is better suited to a later GDExtension/C++ implementation.

## Goals

- Add a gameplay module system that agents can install through `godot-playwright`.
- Ship `save_load` as the first MVP module.
- Make new projects work quickly while keeping installation low-intrusion for existing projects.
- Provide a small demo and validation loop so agents can verify the module after installation.
- Establish a reusable module format for future gameplay systems.
- Provide agent-focused documentation that explains when and how to use the module.

## Non-Goals

- Do not build a full game template in this increment.
- Do not implement `inventory`, `interaction`, `quest`, `projectile`, or other modules yet.
- Do not implement encrypted, compressed, binary, or cloud saves in the MVP.
- Do not solve save migration beyond a top-level schema version field.
- Do not overwrite user project files by default when conflicts are detected.

## Chosen Approach

Use a module package plus CLI installer plus tiny demo.

The MVP adds a module library inside this repository and a CLI entry point:

```sh
godot-playwright module list
godot-playwright module add <project> save_load
godot-playwright module add <project> save_load --demo
```

This is preferred over `init --with save_load` because module installation should scale to many modules and to existing projects. Future syntax can naturally support multiple module names in one command, for example:

```sh
godot-playwright module add <project> save_load inventory interaction
```

The first implementation only needs `module list` and `module add` for `save_load`.

## Repository Layout

Add a new top-level module library:

```text
gameplay_modules/
  save_load/
    module.json
    README.md
    AGENT.md
    addons/save_load/
      save_service.gd
      save_participant.gd
      save_result.gd
      save_constants.gd
    demo/
      scenes/
      scripts/
    tests/
```

`module.json` is the machine-readable manifest. `README.md` is for humans. `AGENT.md` is for AI agents and should be written as operational instructions rather than marketing documentation.

## Module Manifest

`module.json` describes how to install and validate the module. The MVP manifest should include these fields:

```json
{
  "name": "save_load",
  "version": "0.1.0",
  "display_name": "Save Load",
  "description": "JSON save/load service for Godot projects.",
  "godot_version": ">=4.6",
  "copy": [
    {"from": "addons/save_load", "to": "addons/save_load"}
  ],
  "autoloads": [
    {"name": "SaveService", "path": "res://addons/save_load/save_service.gd"}
  ],
  "demo": {
    "copy": [
      {"from": "demo/scenes", "to": "scenes/save_load_demo"},
      {"from": "demo/scripts", "to": "scripts/save_load_demo"},
      {"from": "tests", "to": "tests/save_load_demo"}
    ]
  },
  "validation": {
    "commands": [
      "godot-playwright check-scripts <project> res://addons/save_load --exclude addons/godot_playwright/**",
      "godot-playwright check-resources <project> res://addons/save_load --exclude addons/godot_playwright/**"
    ]
  }
}
```

The implementation can start with this schema and reject unsupported manifest fields rather than silently ignoring them.

## CLI Behavior

`godot-playwright module list` prints available local modules from `gameplay_modules/` with name, version, and description. Structured `--json` output is deferred until a later increment so the MVP stays focused on installation and validation.

`godot-playwright module add <project> save_load` performs these steps:

- Validate that `<project>` is a Godot project by checking `project.godot`.
- Load and validate `gameplay_modules/save_load/module.json`.
- Copy `addons/save_load/` into the target project.
- Register `SaveService` as an enabled Autoload in `project.godot` using `SaveService="*res://addons/save_load/save_service.gd"`. The manifest stores the unstarred `res://` path, and the installer is responsible for writing Godot's enabled-Autoload `*` marker.
- Refuse to overwrite existing files or Autoload entries by default.
- Print an installation report with copied files, Autoload changes, warnings, errors, and next steps.

`godot-playwright module add <project> save_load --demo` performs the default install and also copies the demo scenes, demo scripts, and demo tests described by the manifest.

`--force` allows overwriting paths owned by the same module, such as `addons/save_load/**`, but it must not overwrite unrelated user paths. If ownership cannot be determined safely, the command should fail with a clear error.

## Save Load Module Scope

`save_load` is a generic save/load kernel, not an RPG-specific or roguelite-specific template. It provides JSON save slots, metadata, schema versioning, participant discovery, structured results, and a simple object participation protocol.

Module files:

```text
addons/save_load/
  save_service.gd
  save_participant.gd
  save_result.gd
  save_constants.gd
```

`save_service.gd` is installed as the `SaveService` Autoload. It owns file IO, slot listing, save/load/delete operations, participant discovery, and result aggregation.

`save_participant.gd` is an optional helper base class for new projects. Existing projects do not have to inherit from it.

`save_result.gd` and `save_constants.gd` hold reusable result construction and shared names so `save_service.gd` stays focused on service behavior.

## Save Service API

The first public API is:

```gdscript
SaveService.save_slot(slot_id: String) -> Dictionary
SaveService.load_slot(slot_id: String) -> Dictionary
SaveService.delete_slot(slot_id: String) -> Dictionary
SaveService.list_slots() -> Array[Dictionary]
SaveService.has_slot(slot_id: String) -> bool
```

All mutating methods return structured dictionaries instead of throwing exceptions for expected user/project errors. This makes the API easier for agents and tests to inspect.

Example result:

```json
{
  "ok": true,
  "slot_id": "slot_1",
  "warnings": [],
  "errors": []
}
```

Failures use the same shape with `ok: false` and populated `errors`.

## Save File Format

The MVP uses readable JSON files in:

```text
user://saves/<slot_id>.json
```

Example payload:

```json
{
  "schema_version": 1,
  "module_version": "0.1.0",
  "saved_at": "2026-06-08T00:00:00Z",
  "scene": "res://scenes/main.tscn",
  "participants": {
    "player": {
      "position": [120, 80],
      "health": 7
    }
  }
}
```

Saved state must be JSON-compatible: dictionaries, arrays, strings, numbers, booleans, and null. Agents must not store live `Node`, `Resource`, signal, or callable objects in save data.

## Participant Protocol

A node participates in saving when it joins the `save_participants` group and implements the expected methods.

Recommended participant API:

```gdscript
func get_save_id() -> String:
    return "player"

func save_state() -> Dictionary:
    return {"position": [global_position.x, global_position.y]}

func load_state(data: Dictionary) -> void:
    var position_data := data.get("position", [0, 0])
    global_position = Vector2(position_data[0], position_data[1])
```

The save ID resolution order is:

- Use `get_save_id()` if present and non-empty.
- Otherwise read a `save_id` property if present and non-empty.
- Otherwise fall back to the node path.

Node path fallback keeps MVP usage friction low, but it is less stable if scenes are renamed or reorganized. `SaveService` must report a warning when fallback is used so agents can later add explicit IDs.

The optional helper base class follows this shape:

```gdscript
class_name SaveParticipant
extends Node

@export var save_id: StringName

func get_save_id() -> String:
    return str(save_id)
```

The helper is optional because many Godot classes already need to inherit from specific node types. Existing projects should be able to use the group and method protocol without changing their inheritance tree.

## Data Flow

Save flow:

```text
caller -> SaveService.save_slot(slot_id)
       -> discover nodes in save_participants group
       -> resolve save_id for each node
       -> call save_state()
       -> assemble JSON payload
       -> write user://saves/<slot_id>.json
       -> return structured result
```

Load flow:

```text
caller -> SaveService.load_slot(slot_id)
       -> read and parse JSON
       -> validate schema_version and participants map
       -> discover current save_participants
       -> match nodes by save_id
       -> call load_state(data)
       -> report missing participants and unused saved entries as warnings
```

Delete/list flow uses the same `user://saves` directory and returns structured metadata for agent-readable verification.

## Error Handling

Expected problems should be returned in result dictionaries:

- Invalid or empty slot ID.
- Save directory creation failure.
- File write/read/delete failure.
- Invalid JSON.
- Unsupported schema version.
- Duplicate participant save IDs.
- Participant missing `save_state()` or `load_state()`.
- Participant returns non-dictionary or non-JSON-compatible data.
- Saved participant has no matching runtime node during load.

Duplicate explicit save IDs should be an error because loading would be ambiguous. Node path fallback should be a warning. Missing saved participants during load should be a warning because the current scene may intentionally omit objects from another scene.

## Demo Scope

The `--demo` install adds a very small demo, not a full template game. It should prove the core path:

- A scene with one participant node, such as a player or counter object.
- The participant has an explicit `save_id`.
- Saving records position or a simple integer state.
- Loading restores that state after it is changed.
- Listing and deleting slots can be exercised by tests or UI buttons.

The demo should avoid becoming a gameplay framework. It exists to teach the module contract and provide validation evidence.

## Agent Documentation

`AGENT.md` must tell AI agents:

- Install with `godot-playwright module add <project> save_load`.
- Use `--demo` only when a demo scene/test is useful and safe for the project.
- Add nodes to the `save_participants` group when they need persistence.
- Prefer explicit stable `save_id` values for anything that should survive scene edits.
- Implement `save_state()` and `load_state(data)` with JSON-compatible data only.
- Do not store live Nodes, Resources, Callables, Signals, or arbitrary engine objects in JSON state.
- Treat NodePath fallback warnings as issues to fix before a serious release.
- Run targeted validation after installation and after wiring game objects.

Suggested validation commands for agents:

```sh
godot-playwright inspect-project <project> --exclude "addons/godot_playwright/**" --json
godot-playwright check-scripts <project> res://addons/save_load --exclude "addons/godot_playwright/**"
godot-playwright check-resources <project> res://addons/save_load --exclude "addons/godot_playwright/**"
godot-playwright validate <project> --exclude "addons/godot_playwright/**"
```

Agents can narrow validation to affected files for small edits, but final delivery should state which checks were run and which were skipped.

## Testing Strategy

Python tests should cover:

- Module discovery from `gameplay_modules/`.
- Manifest parsing and validation.
- `module list` output.
- `module add` copying files into a temporary Godot project.
- Autoload registration in `project.godot`.
- Conflict handling when files or Autoload entries already exist.
- `--demo` copying demo files.
- `--force` only overwriting module-owned paths.

Godot validation should cover when Godot is available:

- `save_load` scripts pass Godot parser checks.
- Demo scene/resource dependencies are valid.
- Demo save/load flow restores changed state.
- Installed demo project passes targeted `check-scripts`, `check-resources`, and either `probe` or `validate` as appropriate.

If Godot is unavailable in the local environment, Python tests still provide installer coverage, and final reporting must state that live Godot validation was not run.

## Future Extensions

After the MVP is stable, the same module protocol can support:

- `inventory`, using `save_load` to persist item stacks.
- `interaction`, for reusable prompts and interactable objects.
- `quest`, for objectives, flags, and rewards.
- `dialogue`, for conversation graphs and state.
- `projectile`, likely with a GDExtension/C++ core for high-volume performance.
- `module info <name>` for detailed manifest and agent-doc summaries.
- `module validate <project> <name>` for module-specific validation gates.
- Multi-module install in one command.

These are not part of the MVP implementation scope.

## Acceptance Criteria

- `godot-playwright module list` shows `save_load`.
- `godot-playwright module add <project> save_load` installs files and registers `SaveService` Autoload.
- Existing target files or Autoload conflicts fail clearly by default.
- `godot-playwright module add <project> save_load --demo` also installs the small demo and demo tests.
- The installed `SaveService` can save, load, list, check, and delete JSON slots.
- Participant nodes can save and restore state through the group and method protocol.
- Missing explicit `save_id` falls back to NodePath and reports a warning.
- Python tests cover manifest/install/conflict behavior.
- Godot validation covers parser/resource/demo behavior when Godot is available.
- `README.md` and `AGENT.md` explain the module for humans and agents.
