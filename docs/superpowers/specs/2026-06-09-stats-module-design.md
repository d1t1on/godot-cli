# Stats Gameplay Module Design

Date: 2026-06-09

## Context

`godot-playwright` has reusable gameplay modules for JSON save/load, Resource-driven inventory, node-based state machines, and range-based interaction. An `effects` module is being developed separately. The next module should avoid duplicating `effects` work while still covering a foundational problem that agents repeatedly rebuild in generated games: runtime numeric state.

This design adds `stats` as an installable gameplay module. It provides a generic stat container for health, mana, stamina, speed, attack, defense, hunger, temperature, morale, energy, durability-like values, and other numeric gameplay state. The module intentionally avoids implementing combat formulas, temporary effect modifiers, level curves, UI widgets, or ability logic.

## Goals

- Add `stats` as an installable gameplay module.
- Provide Resource-driven stat definitions with stable IDs, display data, tags, default base/current values, clamp rules, and pool behavior.
- Provide a `StatContainer` node that can be attached to players, enemies, NPCs, interactable objects, resources, machines, or other gameplay owners.
- Support initialization, get/set, add/subtract, base value mutation, clamping, depletion/fill detection, state export, and state import.
- Use structured dictionary results for expected failures and mutations.
- Emit signals for stat changes, base stat changes, depletion, fill, and generic stat events.
- Keep `save_load`, `inventory`, `interaction`, `state_machine`, and the future `effects` module optional.
- Include a deterministic demo scene and copied Python test so agents can validate installation and behavior.
- Provide human and agent documentation for common usage patterns and validation.

## Non-Goals

- Do not build a combat system, damage pipeline, armor formula, critical hit system, resistance system, threat system, or target selection system.
- Do not build a temporary modifier stack, buff/debuff system, DOT/HOT system, or status ailment system. Those belong to the separate `effects` module.
- Do not build level curves, experience tables, class growth, skill trees, or progression rules.
- Do not build ability, cooldown, spell, projectile, weapon, or item-use logic.
- Do not build stat UI, bars, floating text, tooltips, icons, or HUD widgets.
- Do not build formula evaluation, expression parsing, derived-stat graphs, or designer-authored scripting.
- Do not require or auto-install `save_load`, `inventory`, `interaction`, `state_machine`, or `effects`.
- Do not automatically register an Autoload.
- Do not store `Node`, `Resource`, `Callable`, `Signal`, or other engine objects in saved stat state.

## Chosen Approach

Use a lightweight `StatContainer` node plus Godot Resource definitions.

Installation uses the existing module CLI:

```sh
godot-playwright module add <project> stats
godot-playwright module add <project> stats --demo
```

The module copies `res://addons/stats/` into the target project. It does not register an Autoload. A game adds a `StatContainer` node wherever numeric gameplay state is needed, then assigns a `StatDatabase` resource containing `StatDefinition` resources.

This approach is preferred over a global `StatsService` because stats usually belong to specific runtime owners: a player, enemy, destructible object, generator, farming tile, vehicle, town, party, or UI model. It is also preferred over immediately building a full combat or progression module because many games need health, stamina, speed, hunger, or energy without needing combat formulas or RPG advancement.

## Repository Layout

Add a new module tree:

```text
gameplay_modules/stats/
  module.json
  README.md
  AGENT.md
  addons/stats/
    stat_container.gd
    stat_definition.gd
    stat_database.gd
    stat_result.gd
    stat_constants.gd
  demo/
    scenes/
    scripts/
    resources/
  tests/
```

As with existing gameplay modules, package fallback copies should be kept byte-identical under:

```text
godot_playwright/bundled_gameplay_modules/stats/
```

`module.json` describes the base copy operation and demo copy operation. The module has no Autoload entries.

## Module Manifest

The manifest should follow the existing schema:

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
  "demo": {
    "copy": [
      {"from": "demo/scenes", "to": "scenes/stats_demo"},
      {"from": "demo/scripts", "to": "scripts/stats_demo"},
      {"from": "demo/resources", "to": "resources/stats_demo"},
      {"from": "tests", "to": "tests/stats_demo"}
    ]
  },
  "validation": {
    "commands": [
      "godot-playwright check-scripts /path/to/project res://addons/stats --exclude addons/godot_playwright/**",
      "godot-playwright check-resources /path/to/project res://addons/stats --exclude addons/godot_playwright/**"
    ]
  }
}
```

## Runtime Components

`stat_container.gd` defines `class_name StatContainer` and extends `Node`. It owns exported configuration, runtime stat storage, initialization, get/set/mutate operations, clamping, signals, structured results, and state import/export.

`stat_definition.gd` defines `class_name StatDefinition` and extends `Resource`. It stores stable stat configuration.

`stat_database.gd` defines `class_name StatDatabase` and extends `Resource`. It contains an exported array of `StatDefinition` resources and exposes lookup/validation helpers. Stat IDs must be unique and non-empty.

`stat_result.gd` holds structured result helpers so expected failures return dictionaries instead of throwing exceptions.

`stat_constants.gd` holds schema version, module version, save group name, event names, and any shared string constants.

## Stat Definition

The initial public fields on `StatDefinition` are:

```gdscript
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

`stat_id` is the stable identifier used by scripts, saved state, and tests. IDs should be lowercase and stable, such as `health`, `mana`, `stamina`, `move_speed`, `attack`, `defense`, `hunger`, `temperature`, or `morale`.

`default_base_value` is the nominal value or capacity for the stat. For health, mana, and stamina, it usually means the maximum usable amount. For speed, attack, and defense, it usually means the base attribute value.

`default_current_value` is the runtime value assigned when the container initializes. For health and stamina it often starts equal to `default_base_value`. For hunger or temperature it can intentionally start somewhere between the min and max.

`clamp_min` and `clamp_max` control definition-level bounds. `min_value` and `max_value` must be finite numbers, and when both clamps are enabled `min_value` must be less than or equal to `max_value`.

`is_pool` means the current value is clamped to the current base value as its upper bound. This is the common health/mana/stamina behavior: lowering max health also clamps current health if it is above the new maximum. For non-pool attributes such as speed or attack, current values are clamped only by definition bounds.

All values are numeric and stored as Godot floats in the MVP. Games that need integer display can round in UI or project-specific code. Integer-only storage, rounding policies, and presentation helpers are future extensions.

## StatContainer API

The initial public API on `StatContainer` is:

```gdscript
@export var database: Resource
@export var save_id: StringName
@export var initialize_on_ready: bool = true

func initialize_stats(reset: bool = false) -> Dictionary
func has_stat(stat_id: String) -> bool
func get_value(stat_id: String) -> float
func get_base_value(stat_id: String) -> float
func get_stat(stat_id: String) -> Dictionary
func get_stats() -> Array
func set_value(stat_id: String, value: float) -> Dictionary
func modify_value(stat_id: String, delta: float) -> Dictionary
func set_base_value(stat_id: String, value: float) -> Dictionary
func modify_base_value(stat_id: String, delta: float) -> Dictionary
func clear_runtime_state() -> void
func get_state() -> Dictionary
func apply_state(data: Dictionary) -> Dictionary
```

`database` must expose the `StatDatabase` protocol. The exported type can remain `Resource` to avoid hard editor coupling and to match the inventory and effects module style.

`save_id` is optional. When non-empty, the container joins the shared save participant group and exposes `get_save_id()`, `save_state()`, and `load_state(data)` wrappers compatible with `save_load`. Containers with empty `save_id` do not automatically persist.

`initialize_on_ready` controls whether `_ready()` initializes runtime state from the database. It defaults to `true` for ordinary scene-driven projects. Tests and generated setup code can set it to `false` and call `initialize_stats()` explicitly.

`initialize_stats(false)` should preserve existing runtime state once initialized. `initialize_stats(true)` clears current runtime state and rebuilds from definitions.

`get_value()` and `get_base_value()` return `0.0` when a stat cannot be resolved. Mutating calls return structured failures for missing databases, invalid IDs, unknown stats, or invalid numbers.

`get_stat()` and `get_stats()` return copies of runtime stat dictionaries so callers cannot accidentally mutate internal state.

## Runtime Stat State

The container stores one runtime dictionary per stat:

```json
{
  "stat_id": "health",
  "base_value": 100.0,
  "current_value": 75.0
}
```

The module should preserve deterministic stat order based on the database definition order. Saved state can be applied in any order, but `get_stats()` should return the database order for stable tests and agent inspection.

The runtime state stores only values that can be saved as JSON-compatible data. It does not store the `StatDefinition` resource or any engine object.

## Value And Clamping Rules

All public stat IDs are normalized by trimming whitespace. Empty IDs fail clearly.

`set_value(stat_id, value)` sets the current value after validating the stat and clamping the value.

`modify_value(stat_id, delta)` adds `delta` to the current value and then applies the same current-value clamp.

`set_base_value(stat_id, value)` sets the base value after validating and clamping the base value. If the stat is a pool and the current value is above the new base value, the current value is also clamped down.

`modify_base_value(stat_id, delta)` adds `delta` to the base value and then applies the same base-value rules.

Current-value clamp rules:

- If `clamp_min` is true, current value cannot go below `min_value`.
- If `is_pool` is true, current value cannot go above `base_value`.
- If `is_pool` is false and `clamp_max` is true, current value cannot go above `max_value`.
- If the input value is `NaN` or infinite, the mutation fails without changing state.

Base-value clamp rules:

- If `clamp_min` is true, base value cannot go below `min_value`.
- If `clamp_max` is true, base value cannot go above `max_value`.
- If the input value is `NaN` or infinite, the mutation fails without changing state.

Expected clamping is not an error. Mutating calls report `clamped: true` and include a warning when the requested value differs from the applied value.

## Signals

`StatContainer` should expose these signals:

```gdscript
signal stat_changed(stat_id: String, current_value: float, previous_value: float, result: Dictionary)
signal base_stat_changed(stat_id: String, base_value: float, previous_base_value: float, result: Dictionary)
signal stat_depleted(stat_id: String, current_value: float, result: Dictionary)
signal stat_filled(stat_id: String, current_value: float, result: Dictionary)
signal stats_changed(event: Dictionary)
```

`stat_changed` emits when a current value actually changes.

`base_stat_changed` emits when a base value actually changes.

`stat_depleted` emits when a current value crosses from above the effective minimum to the effective minimum. This is useful for death, exhaustion, empty battery, broken object, or depleted resource handling.

`stat_filled` emits when a current value crosses from below the effective maximum to the effective maximum. For pool stats the effective maximum is `base_value`. For non-pool stats the effective maximum is `max_value` only when `clamp_max` is enabled.

`stats_changed` emits a generic event dictionary for current changes, base changes, clamping, depletion, fill, and state application. It gives UI, tests, logging, and future modules one stable hook without requiring them to connect every specific signal.

Expected validation failures are returned through result dictionaries and should not emit change signals.

## Structured Results

Expected failures should be returned in result dictionaries, matching the existing gameplay-module style:

```gdscript
{
  "ok": false,
  "stat_id": "health",
  "previous_value": 75.0,
  "current_value": 75.0,
  "previous_base_value": 100.0,
  "base_value": 100.0,
  "requested_value": -25.0,
  "delta": 0.0,
  "clamped": false,
  "events": [],
  "warnings": [],
  "errors": ["Unknown stat_id: health"]
}
```

Successful mutating results should include `ok: true`, `stat_id`, previous and current values, previous and current base values, requested value or delta where applicable, `clamped`, `events`, `warnings`, and `errors`. The result shape should remain stable enough for agents and copied tests to inspect without parsing warning text.

Common expected failures:

- `database` is unassigned.
- `database` does not expose the expected protocol.
- The database has duplicate, empty, or invalid stat definitions.
- `stat_id` is empty or unknown.
- The input value or delta is `NaN`, infinite, or not numeric.
- A stat definition has invalid clamp bounds.
- Saved state is malformed or references unknown stats.

The module should avoid throwing exceptions for expected gameplay or wiring errors. Parser errors, missing script dependencies, and other hard Godot failures remain validation failures outside the result-dictionary contract.

## State Format

`StatContainer.get_state()` returns JSON-compatible data:

```json
{
  "schema_version": 1,
  "stats": [
    {
      "stat_id": "health",
      "base_value": 100.0,
      "current_value": 75.0
    },
    {
      "stat_id": "stamina",
      "base_value": 50.0,
      "current_value": 20.0
    }
  ]
}
```

`apply_state(data)` validates the complete state against the current stat database before mutating. It checks schema version, array shape, duplicate stat IDs, known definitions, finite numeric values, clamp compatibility, and data shape. Invalid state returns `ok: false` and does not partially mutate the active stats.

The saved state intentionally stores runtime values only. It does not store the full `StatDefinition` data. Missing or renamed stat definitions should fail loudly during load so agents can fix the database or write an explicit migration.

## Optional Module Integration

The module must be usable without `save_load`, `inventory`, `interaction`, `state_machine`, or `effects`.

For projects using `save_load`, a container with a non-empty `save_id` can participate directly by joining the save participant group and exposing thin wrappers:

```gdscript
func get_save_id() -> String:
    return String(save_id)


func save_state() -> Dictionary:
    return get_state()


func load_state(data: Dictionary) -> void:
    apply_state(data)
```

For projects using `inventory`, item-use scripts can call `StatContainer.modify_value()` after removing or consuming an item. The core `stats` module should not import or preload inventory scripts.

For projects using `interaction`, interactable scripts can find the actor's `StatContainer` and modify stats on use, such as healing at a fountain or draining energy from a machine. The core `stats` module should not depend on interaction classes.

For projects using `state_machine`, state logic can query `has_stat()` or `get_value()` to decide transitions, guards, or behavior. The core `stats` module should not depend on state-machine files, classes, or lifecycle behavior.

For the future `effects` module, effects can call stat mutation methods for direct consequences such as poison damage or healing ticks. Future stats extensions may also add explicit modifier APIs, but this MVP should not implement temporary modifier ownership or automatic reversal because that belongs to the effects/stat-modifier integration boundary.

## Demo

`--demo` installs a compact deterministic runtime scene. The demo should be small and focused, not a combat template.

Scene contents:

- One root node with a `StatContainer` child.
- One `StatDatabase` resource.
- Sample `StatDefinition` resources for `health`, `stamina`, `move_speed`, and `heat`.
- A root script exposing `run_stats_demo() -> Dictionary`.

The demo should validate:

- A container initializes from the database.
- `get_value()` and `get_base_value()` return expected defaults.
- `modify_value("health", -25.0)` lowers current health.
- Reducing health below minimum clamps to the minimum and emits/reports depletion.
- Restoring health to the pool maximum emits/reports fill.
- Reducing a pool base value clamps current value when current exceeds the new base.
- A non-pool stat such as `move_speed` can change without using base value as a maximum.
- `get_state()` and `apply_state()` restore stat values.
- Unknown stat IDs, invalid numbers, missing database, malformed state, and duplicate definitions return structured failures.

The copied Python demo test should load the scene through `godot-playwright`, call `run_stats_demo()`, and assert a structured success result.

## CLI And Installer Behavior

The existing `godot-playwright module list` should show `stats` once this module is present.

`godot-playwright module add <project> stats` should copy only the base module files and use existing safe installer behavior:

- Refuse to overwrite files by default.
- Allow `--force` only for module-owned paths.
- Reject duplicate planned targets.
- Avoid symlink target overwrites.
- Return a clear installation report.
- Add no Autoload entries.

`godot-playwright module add <project> stats --demo` should also copy demo scenes, demo scripts, demo resources, and copied tests into module-specific paths such as:

```text
res://scenes/stats_demo/
res://scripts/stats_demo/
res://resources/stats_demo/
tests/stats_demo/
```

## Documentation

`README.md` should explain:

- How to install the module.
- How to create stat definitions and a stat database.
- How to add a `StatContainer` to a scene.
- How base values, current values, clamps, and pool stats work.
- How to call get/set/modify methods and inspect result dictionaries.
- How to listen to stat signals.
- How to serialize state with `get_state()` and `apply_state(data)`.
- How to integrate manually with save slots, inventory item use, interaction triggers, state-machine guards, and future effects.
- How to validate the module after installation.

`AGENT.md` should give operational instructions:

- Use this module when a game needs health, mana, stamina, speed, attack, defense, hunger, temperature, morale, energy, durability-like values, or other numeric runtime state.
- Do not use this module as a combat, effects, progression, skill, inventory, UI, or formula system.
- Prefer stable explicit `stat_id` values before save data exists.
- Keep stat definitions data-only and JSON-compatible when they may be saved.
- Put damage formulas, healing formulas, temporary buffs, UI rendering, level curves, and gameplay consequences in project scripts or future domain modules.
- Use `save_id` only for containers that should persist.
- Validate with targeted script/resource checks and the copied demo test.

## Testing Strategy

Python tests should cover:

- Module discovery lists `stats` with version `0.1.0`.
- `module add stats` copies base files and does not add Autoloads.
- `module add stats --demo` copies demo scenes, scripts, resources, and copied tests.
- Package fallback data contains the bundled stats module.
- Source and bundled module trees stay byte-identical.
- `pyproject.toml` includes bundled stats package data.
- Existing installer safety behavior still applies to the new module.

Godot validation should cover when Godot is available:

- Stats module scripts pass Godot parser checks.
- Demo scene/resource dependencies are valid.
- Demo runtime method validates initialization, get/set, modify, clamping, pool base changes, depletion, fill, state round-trip, and structured failures.
- Optional save integration works when `save_load` is installed and `save_id` is configured.

If Godot is unavailable, Python installer tests still provide coverage, and final reporting must state that live Godot validation was skipped.

## Future Extensions

- Explicit stat modifier APIs after the `effects` module boundary is known.
- Derived stats, formulas, dependency graphs, and invalidation rules.
- Integer presentation or rounding modes for stats that should display as whole numbers.
- Stat requirements for equipment, abilities, dialogue options, or interactions.
- Level curves, experience tables, and growth profiles.
- Combat integration that uses stats for damage, healing, resistance, and mitigation.
- UI helper scenes for stat bars, meters, text labels, and threshold indicators.
- Threshold resources for low-health, overheated, exhausted, or morale-break events.
- Migration helpers for renamed stat IDs after save data exists.

## Acceptance Criteria

- `godot-playwright module list` shows `stats`.
- `godot-playwright module add <project> stats` installs `res://addons/stats/` without registering an Autoload.
- `godot-playwright module add <project> stats --demo` installs demo scene, scripts, resources, and copied demo test.
- `StatDefinition` supports stable IDs, display data, tags, default base/current values, clamp rules, and pool behavior.
- `StatDatabase` validates definitions and exposes lookup helpers.
- `StatContainer` supports initialization, get/set, add/subtract, base value mutation, state export, and state import.
- Pool stats clamp current values to base values.
- Non-pool stats do not use base value as a current-value maximum.
- Depletion and fill events are deterministic and inspectable.
- Unknown stat IDs, invalid numbers, missing databases, duplicate definitions, malformed state, and invalid clamp bounds fail clearly.
- Mutating calls return stable structured result dictionaries.
- `apply_state()` validates before mutation.
- Runtime stat state is JSON-compatible and does not persist engine objects.
- Optional `save_load`, `inventory`, `interaction`, `state_machine`, and future `effects` integration paths are documented without core dependencies.
- Demo validates core runtime behavior and structured failures.
- Human and agent docs explain usage, non-goals, optional integrations, and validation.
