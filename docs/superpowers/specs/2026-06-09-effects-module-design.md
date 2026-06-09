# Effects Gameplay Module Design

Date: 2026-06-09

## Context

`godot-playwright` now has reusable gameplay modules for JSON save/load, Resource-driven inventory, and node-based state machines. An interaction module is being developed in a separate worktree. The next high-value parallel module should maximize broad reuse across game types while keeping the existing module style: low-intrusion installation, Godot-native scripts, structured dictionary results for expected failures, optional integration boundaries, deterministic demos, copied demo tests, and agent-focused documentation.

This design adds `effects` as an installable gameplay module. It provides a generic runtime effect container for buffs, debuffs, temporary bonuses, status ailments, damage-over-time markers, healing-over-time markers, item effects, equipment modifiers, and interaction- or area-triggered gameplay effects after another system chooses the target. The module intentionally avoids implementing a full stats, combat, skill, UI, quest, or spatial aura system in the MVP.

## Goals

- Add `effects` as an installable gameplay module.
- Provide Resource-driven effect definitions with stable IDs, display data, tags, durations, tick intervals, stacking rules, max stacks, and default data.
- Provide an `EffectContainer` node that can be attached to players, enemies, NPCs, interactable objects, equipment targets, or other gameplay owners.
- Support adding, removing, clearing, querying, ticking, expiring, serializing, and restoring active effects.
- Support common stacking behavior: refresh, stack, and ignore.
- Keep runtime effect events generic so combat, stats, skills, inventory, interaction, and UI systems can react without the core module owning their rules.
- Keep `save_load`, `inventory`, `interaction`, and `state_machine` integration optional and documented.
- Include a deterministic demo scene and copied Python test so agents can validate installation and behavior.
- Provide human and agent documentation for common usage patterns and validation.

## Non-Goals

- Do not build a full stats or attributes system.
- Do not build a combat damage, healing, resistance, threat, or target-selection system.
- Do not build a skill, spell, cooldown, projectile, or ability system.
- Do not build UI widgets, floating text, icons, tooltips, or status bars.
- Do not build spatial aura detection, proximity scanning, navigation, or high-volume perception.
- Do not build a formula editor, expression evaluator, or designer-authored scripting language.
- Do not require or auto-install `save_load`, `inventory`, `interaction`, or `state_machine`.
- Do not automatically register an Autoload.
- Do not store `Node`, `Resource`, `Callable`, `Signal`, or other engine objects in saved effect state.

## Chosen Approach

Use a lightweight `EffectContainer` node plus Godot Resource definitions.

Installation uses the existing module CLI:

```sh
godot-playwright module add <project> effects
godot-playwright module add <project> effects --demo
```

The module copies `res://addons/effects/` into the target project. It does not register an Autoload. A game adds an `EffectContainer` node wherever effects can be applied, then assigns an `EffectDatabase` resource containing `EffectDefinition` resources.

This approach is preferred over a global `EffectService` because multiple independent effect owners are common: player, enemies, NPCs, equipment previews, summoned objects, interactable hazards, and temporary test actors. It is also preferred over immediately building a complete `stats` module because effects are useful even when a project has no formal attribute model. Future stats, skills, combat, quest, and UI modules can consume effect events or query active effects through this stable component boundary.

## Repository Layout

Add a new module tree:

```text
gameplay_modules/effects/
  module.json
  README.md
  AGENT.md
  addons/effects/
    effect_container.gd
    effect_definition.gd
    effect_database.gd
    effect_instance.gd
    effect_result.gd
    effect_constants.gd
  demo/
    scenes/
    scripts/
    resources/
  tests/
```

As with existing gameplay modules, package fallback copies should be kept byte-identical under:

```text
godot_playwright/bundled_gameplay_modules/effects/
```

`module.json` describes the base copy operation and demo copy operation. The module has no Autoload entries.

## Module Manifest

The manifest should follow the existing schema:

```json
{
  "name": "effects",
  "version": "0.1.0",
  "display_name": "Effects",
  "description": "Resource-driven runtime effects and buffs for Godot projects.",
  "godot_version": ">=4.6",
  "copy": [
    {"from": "addons/effects", "to": "addons/effects"}
  ],
  "autoloads": [],
  "demo": {
    "copy": [
      {"from": "demo/scenes", "to": "scenes/effects_demo"},
      {"from": "demo/scripts", "to": "scripts/effects_demo"},
      {"from": "demo/resources", "to": "resources/effects_demo"},
      {"from": "tests", "to": "tests/effects_demo"}
    ]
  },
  "validation": {
    "commands": [
      "godot-playwright check-scripts /path/to/project res://addons/effects --exclude addons/godot_playwright/**",
      "godot-playwright check-resources /path/to/project res://addons/effects --exclude addons/godot_playwright/**"
    ]
  }
}
```

## Runtime Components

`effect_container.gd` defines `class_name EffectContainer` and extends `Node`. It owns exported configuration, active effect storage, add/remove/query operations, update/tick/expiry behavior, signals, structured results, and state import/export.

`effect_definition.gd` defines `class_name EffectDefinition` and extends `Resource`. It stores stable effect configuration.

`effect_database.gd` defines `class_name EffectDatabase` and extends `Resource`. It contains an exported array of `EffectDefinition` resources and exposes lookup/validation helpers. Effect IDs must be unique and non-empty.

`effect_instance.gd` holds small runtime dictionary helpers for active effect instances. It should keep instance creation, copying, serialization, and validation logic out of `effect_container.gd` when that keeps the container simpler.

`effect_result.gd` holds structured result helpers so expected failures return dictionaries instead of throwing exceptions.

`effect_constants.gd` holds schema version, module version, stack mode names, signal/event names, and shared save group names.

## Effect Definition

The initial public fields on `EffectDefinition` are:

```gdscript
@export var effect_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export_range(0.0, 999999.0, 0.1) var duration: float = 0.0
@export_range(0.0, 999999.0, 0.1) var tick_interval: float = 0.0
@export_enum("refresh", "stack", "ignore") var stack_mode: String = "refresh"
@export_range(1, 999, 1) var max_stacks: int = 1
@export var default_data: Dictionary = {}
```

`effect_id` is the stable identifier used by scripts, saved state, and tests. IDs should be lowercase and stable, such as `haste`, `poison`, `burning`, `shielded`, `stunned`, or `regen_small`.

`duration <= 0.0` means the effect is permanent until removed. `tick_interval <= 0.0` means the effect does not emit tick events. `default_data` must be JSON-compatible when effects will be saved.

The base definition does not encode damage, healing, stat formulas, or gameplay actions. Game code can interpret tags and `data` fields, listen to container signals, or query active effects to drive domain-specific behavior.

## EffectContainer API

The initial public API on `EffectContainer` is:

```gdscript
@export var database: Resource
@export var save_id: StringName
@export var auto_update: bool = true

func add_effect(effect_id: String, source: Node = null, stacks: int = 1, data: Dictionary = {}) -> Dictionary
func remove_effect(effect_id: String, stacks: int = 0) -> Dictionary
func clear_effects() -> void
func has_effect(effect_id: String) -> bool
func get_effect(effect_id: String) -> Dictionary
func get_effects() -> Array
func get_stack_count(effect_id: String) -> int
func update_effects(delta: float) -> Array[Dictionary]
func get_state() -> Dictionary
func apply_state(data: Dictionary) -> Dictionary
```

`database` must expose the `EffectDatabase` protocol. The exported type can remain `Resource` to avoid hard editor coupling and to match the inventory module style.

`save_id` is optional. When non-empty, the container joins the shared save participant group and exposes `get_save_id()`, `save_state()`, and `load_state(data)` wrappers compatible with `save_load`. Containers with empty `save_id` do not automatically persist.

`auto_update` controls whether `_process(delta)` calls `update_effects(delta)`. It defaults to `true` for ordinary scene-driven projects. Tests and turn-based projects can set it to `false` and call `update_effects(delta)` manually for deterministic control.

`source` is passed to add events and signals but is not stored in saved state. If a project needs persistent source information, it should pass a JSON-compatible source identifier in `data`, such as `{"source_id": "fire_trap_01"}`.

When an effect instance is created, instance `data` starts as a deep copy of the definition's `default_data`, then overlays the `data` argument passed to `add_effect()`. When an existing effect is refreshed or stacked, new `data` overlays the existing active instance data. This keeps default values useful while allowing item use, skills, interactions, or scripts to attach contextual JSON-compatible fields.

## Stacking Rules

The MVP supports three stack modes.

`refresh` means adding an effect that is already active resets its remaining duration and merges input data, but leaves the stack count unchanged. If the effect is not active, it creates one active instance with the requested stack count clamped to `max_stacks`.

`stack` means adding an effect increases its stack count up to `max_stacks` and refreshes remaining duration. If requested stacks exceed available stack room, the result stays successful when at least one stack is added and reports a warning with a `remainder` value.

`ignore` means adding an effect that is already active does not change the active instance. The result should be successful with a warning so callers can distinguish an ignored duplicate from an invalid effect.

Common validation rules:

- `effect_id` must be non-empty after trimming whitespace.
- `stacks` must be positive when adding.
- Unknown effect IDs fail clearly.
- `max_stacks` must be positive.
- Active stack counts must never exceed `max_stacks`.
- Removing with `stacks <= 0` removes the entire active effect.
- Removing with `stacks > 0` removes that many stacks and expires the effect if no stacks remain.

## Time, Tick, And Event Rules

Active effects store elapsed and remaining time in seconds. `update_effects(delta)` advances all active effects and returns an array of event dictionaries. It also emits signals for the same events.

Expected event types:

- `added`
- `refreshed`
- `stacked`
- `ignored`
- `removed`
- `tick`
- `expired`
- `cleared`

Tick behavior:

- Effects with `tick_interval <= 0.0` never emit tick events.
- Permanent effects can still tick when `tick_interval > 0.0`.
- A large `delta` may produce multiple tick events for the same effect.
- Tick events are generic. The module does not apply damage, healing, or stats by itself.

Expiry behavior:

- Effects with `duration <= 0.0` never expire by duration.
- Timed effects expire when remaining duration reaches zero or below.
- Expired effects are removed from the active list during `update_effects(delta)`.
- Expiry emits and returns an `expired` event after any tick events produced by the same update.

`update_effects(delta)` should reject negative delta values by returning a structured error event rather than mutating active effects. `delta == 0.0` is allowed and should not change timers.

## Signals

`EffectContainer` should expose these signals:

```gdscript
signal effect_added(effect_id: String, effect: Dictionary, result: Dictionary)
signal effect_removed(effect_id: String, effect: Dictionary, result: Dictionary)
signal effect_ticked(effect_id: String, effect: Dictionary, event: Dictionary)
signal effect_expired(effect_id: String, effect: Dictionary, event: Dictionary)
signal effects_changed(event: Dictionary)
```

Specific signals make common code easy to connect. `effects_changed` provides one generic hook for UI, logging, tests, and future integration modules.

The module should emit signals for successful effect changes and tick/expiry events. Expected validation failures are returned through result dictionaries and should not emit change signals.

## Structured Results

Expected failures should be returned in result dictionaries, matching the existing gameplay-module style:

```gdscript
{
  "ok": false,
  "effect_id": "poison",
  "requested_stacks": 1,
  "applied_stacks": 0,
  "remainder": 0,
  "warnings": [],
  "errors": ["Unknown effect_id: poison"]
}
```

Successful mutating results should include `ok: true`, `effect_id`, `requested_stacks`, `applied_stacks`, `removed_stacks`, `remainder`, `effect`, `events`, `warnings`, and `errors` where applicable. The result shape should remain stable enough for agents and copied tests to inspect without parsing warning text.

Common expected failures:

- `database` is unassigned.
- `database` does not expose the expected protocol.
- The database has duplicate, empty, or invalid effect definitions.
- `effect_id` is empty or unknown.
- Requested stack count is invalid.
- The effect definition has an invalid duration, tick interval, stack mode, or max stack count.
- Saved state is malformed or references unknown effects.
- Negative `delta` is passed to `update_effects(delta)`.

The module should avoid throwing exceptions for expected gameplay or wiring errors. Parser errors, missing script dependencies, and other hard Godot failures remain validation failures outside the result-dictionary contract.

## Active Effect State

`get_effect(effect_id)` and `get_effects()` return copies of active effect dictionaries so callers cannot mutate internal state accidentally. A typical active effect dictionary is:

```json
{
  "effect_id": "haste",
  "stacks": 2,
  "remaining_duration": 4.5,
  "elapsed_time": 1.5,
  "tick_elapsed": 0.5,
  "data": {
    "speed_multiplier": 1.25
  }
}
```

`remaining_duration` uses `-1.0` for permanent effects. All active effect data must remain JSON-compatible when the effect may be saved.

The container should preserve deterministic active-effect order. New effects append to the end. Refreshing or stacking an existing effect should not move it. Removing an effect should preserve the order of remaining effects.

## State Format

`EffectContainer.get_state()` returns JSON-compatible data:

```json
{
  "schema_version": 1,
  "effects": [
    {
      "effect_id": "haste",
      "stacks": 2,
      "remaining_duration": 4.5,
      "elapsed_time": 1.5,
      "tick_elapsed": 0.5,
      "data": {"speed_multiplier": 1.25}
    }
  ]
}
```

`apply_state(data)` validates the complete state against the current effect database before mutating. It checks schema version, array shape, duplicate effect IDs, known definitions, stack counts, max stacks, timer values, and data shape. Invalid state returns `ok: false` and does not partially mutate the active effects.

The saved state intentionally stores runtime effect instances only. It does not store the full `EffectDefinition` data. Missing or renamed effect definitions should fail loudly during load so agents can fix the database or write an explicit migration.

## Optional Module Integration

The module must be usable without `save_load`, `inventory`, `interaction`, or `state_machine`.

For projects using `save_load`, a container with a non-empty `save_id` can participate directly by joining the save participant group and exposing thin wrappers:

```gdscript
func get_save_id() -> String:
    return String(save_id)


func save_state() -> Dictionary:
    return get_state()


func load_state(data: Dictionary) -> void:
    apply_state(data)
```

For projects using `inventory`, item-use scripts can call `EffectContainer.add_effect()` after removing or consuming an item. The core `effects` module should not import or preload inventory scripts.

For projects using `interaction`, interactable scripts can find the actor's `EffectContainer` and add effects on use. The core `effects` module should not depend on interaction classes.

For projects using `state_machine`, state logic can query `has_effect()` or `get_effect()` to decide transitions, guards, or behavior. The core `effects` module should not depend on state-machine files, classes, or lifecycle behavior.

For future `stats` or `combat` modules, effects can be interpreted through tags and data. For example, a future stats module may read active effects tagged `stat_modifier`, while a future combat module may listen for `effect_ticked` and apply damage or healing. This MVP should only expose the stable data and event boundary.

## Demo

`--demo` installs a compact deterministic runtime scene. The demo should be small and focused, not a combat template.

Scene contents:

- One root node with an `EffectContainer` child.
- One `EffectDatabase` resource.
- Sample `EffectDefinition` resources for `haste`, `poison`, `shielded`, and `stunned`.
- A root script exposing `run_effects_demo() -> Dictionary`.

The demo should validate:

- A timed refresh effect can be added and queried.
- Re-adding a refresh effect refreshes remaining duration without increasing stacks.
- A stack effect increases stack count up to `max_stacks` and reports remainder when requested stacks exceed capacity.
- An ignore effect reports an ignored duplicate without mutating the active effect.
- Tick events are emitted and returned for an effect with `tick_interval > 0.0`.
- Timed effects expire after sufficient `update_effects(delta)` calls.
- Permanent effects remain active until removed.
- `remove_effect()` removes partial stacks and full effects deterministically.
- `get_state()` and `apply_state()` restore active effects without preserving source nodes.
- Unknown effect IDs, invalid stack counts, missing database, malformed state, and negative delta return structured failures.

The copied Python demo test should load the scene through `godot-playwright`, call `run_effects_demo()`, and assert a structured success result.

## CLI And Installer Behavior

The existing `godot-playwright module list` should show `effects` once this module is present.

`godot-playwright module add <project> effects` should copy only the base module files and use existing safe installer behavior:

- Refuse to overwrite files by default.
- Allow `--force` only for module-owned paths.
- Reject duplicate planned targets.
- Avoid symlink target overwrites.
- Return a clear installation report.
- Add no Autoload entries.

`godot-playwright module add <project> effects --demo` should also copy demo scenes, demo scripts, demo resources, and copied tests into module-specific paths such as:

```text
res://scenes/effects_demo/
res://scripts/effects_demo/
res://resources/effects_demo/
tests/effects_demo/
```

## Documentation

`README.md` should explain:

- How to install the module.
- How to create effect definitions and an effect database.
- How to add an `EffectContainer` to a scene.
- How refresh, stack, and ignore modes work.
- How timed effects, permanent effects, ticks, and expiry work.
- How to call add/remove/query/update methods and inspect result dictionaries.
- How to listen to effect signals.
- How to serialize state with `get_state()` and `apply_state(data)`.
- How to integrate manually with inventory item use, interaction triggers, save slots, and state-machine logic.
- How to validate the module after installation.

`AGENT.md` should give operational instructions:

- Use this module when a game needs buffs, debuffs, status ailments, temporary modifiers, item effects, equipment modifiers, DOT/HOT markers, or interaction-triggered effects.
- Do not use this module as a full stats, combat, skill, quest, UI, or aura/spatial-detection system.
- Prefer stable explicit `effect_id` values before save data exists.
- Keep effect definitions data-only and JSON-compatible when they may be saved.
- Put actual damage, healing, stat math, UI rendering, and gameplay consequences in project scripts or future domain modules.
- Use `auto_update = false` for deterministic turn-based tests or systems that should advance effects only on explicit turns.
- Use `save_id` only for containers that should persist.
- Validate with targeted script/resource checks and the copied demo test.

## Testing Strategy

Python tests should cover:

- Module discovery lists `effects` with version `0.1.0`.
- `module add effects` copies base files and does not add Autoloads.
- `module add effects --demo` copies demo scenes, scripts, resources, and copied tests.
- Package fallback data contains the bundled effects module.
- Source and bundled module trees stay byte-identical.
- `pyproject.toml` includes bundled effects package data.
- Existing installer safety behavior still applies to the new module.

Godot validation should cover when Godot is available:

- Effects module scripts pass Godot parser checks.
- Demo scene/resource dependencies are valid.
- Demo runtime method validates add/query, refresh, stack, ignore, tick, expiry, removal, state round-trip, and structured failures.
- Optional save integration works when `save_load` is installed and `save_id` is configured.

If Godot is unavailable, Python installer tests still provide coverage, and final reporting must state that live Godot validation was skipped.

## Future Extensions

- A separate `stats` module that reads active effects as stat modifiers.
- A separate `combat` module that applies damage or healing from tick events.
- A separate `skills` module that applies effects as skill outcomes.
- UI helper scenes for status icons, timers, stack counts, and tooltips.
- Area or aura helpers that apply effects to nearby targets through physics queries.
- Effect categories with dispel rules, immunity rules, and cleanse filtering.
- Cooldown and usage-limit helpers if a future ability module needs them.
- Resource-driven migration helpers for renamed effect IDs after save data exists.

## Acceptance Criteria

- `godot-playwright module list` shows `effects`.
- `godot-playwright module add <project> effects` installs `res://addons/effects/` without registering an Autoload.
- `godot-playwright module add <project> effects --demo` installs demo scene, scripts, resources, and copied demo test.
- `EffectDefinition` supports stable IDs, display data, tags, duration, tick interval, stack mode, max stacks, and default data.
- `EffectDatabase` validates definitions and exposes lookup helpers.
- `EffectContainer` supports adding, removing, clearing, querying, updating, state export, and state import.
- Refresh, stack, and ignore modes behave deterministically and return structured results.
- Timed effects tick and expire through `update_effects(delta)`.
- Permanent effects do not expire by duration.
- Unknown effect IDs, invalid stack counts, missing databases, malformed state, and negative delta fail clearly.
- `apply_state()` validates before mutation.
- Active effect state is JSON-compatible and does not persist engine objects.
- Optional `save_load`, `inventory`, `interaction`, and `state_machine` integration paths are documented without core dependencies.
- Demo validates core runtime behavior and structured failures.
- Human and agent docs explain usage, non-goals, optional integrations, and validation.
