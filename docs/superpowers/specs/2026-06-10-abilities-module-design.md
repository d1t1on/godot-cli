# Abilities Gameplay Module Design

Date: 2026-06-10

## Context

`godot-playwright` now has reusable gameplay modules for JSON save/load, inventory, state machines, interaction, effects, and stats. Agents still repeatedly rebuild one missing layer: a generic way for an actor, object, item, or AI-controlled unit to attempt named gameplay actions with cooldowns, charges, enabled state, costs, and structured activation results.

This design adds `abilities` as an installable gameplay module. It is intentionally broader than combat skills. An ability can represent a dash, attack request, spell request, reload, scan, harvest action, repair action, build command, tool use, door override, unit command, or puzzle action.

The module is an action execution framework. It does not implement damage, hit detection, animation, input mapping, AI choice, resource deduction, effect application, or cast/channel timing.

## Goals

- Add `abilities` as an installable gameplay module.
- Provide Resource-driven ability definitions with stable IDs, display data, tags, cooldowns, charges, costs, enabled defaults, and JSON-compatible default data.
- Provide an `AbilityContainer` node that can be attached to players, enemies, NPCs, interactable objects, machines, tools, vehicles, or strategy units.
- Support initialization, `can_activate()`, `activate()`, enabled/disabled state, cooldown ticking, charge recovery, runtime inspection, state export, and state import.
- Use structured dictionary results for expected failures and activation details.
- Emit signals for ability activation, cooldown/charge changes, enabled changes, and generic ability events.
- Keep `save_load`, `stats`, `effects`, `inventory`, `interaction`, and `state_machine` optional.
- Include a deterministic demo scene and copied Python test so agents can validate installation and behavior.
- Provide human and agent documentation for common usage patterns and validation.

## Non-Goals

- Do not build a combat system, weapon system, hitbox system, projectile system, targeting system, armor formula, critical hit formula, or damage pipeline.
- Do not play animations, trigger input actions, control character movement, or make AI decisions.
- Do not apply effects, mutate stats, consume inventory items, spend ammo, or remove resources automatically.
- Do not implement cast time, channeling, wind-up, recovery, cancel windows, interrupt rules, combo chains, or queued commands in v1.
- Do not implement skill trees, leveling, unlock requirements, prerequisites, or progression graphs.
- Do not build UI widgets, hotbars, icons, tooltips, radial menus, or input rebinding.
- Do not require or auto-install `save_load`, `stats`, `effects`, `inventory`, `interaction`, or `state_machine`.
- Do not automatically register an Autoload.
- Do not store `Node`, `Resource`, `Callable`, `Signal`, or other engine objects in saved ability state or definition `default_data`.

## Chosen Approach

Use a lightweight `AbilityContainer` node plus Godot Resource definitions.

Installation uses the existing module CLI:

```sh
godot-playwright module add <project> abilities
godot-playwright module add <project> abilities --demo
```

The module copies `res://addons/abilities/` into the target project. It does not register an Autoload. A game adds an `AbilityContainer` node wherever a runtime owner can perform actions, then assigns an `AbilityDatabase` resource containing `AbilityDefinition` resources.

The first version supports instant activations with cooldowns and charges. If a game needs wind-up, cast time, channeling, combo flow, or cancellation, it should model that timing in project code or `state_machine` states and call `activate()` when the action should resolve.

The first version also treats costs as declarative data. `AbilityContainer` can report configured costs and include them in activation results, but it does not automatically deduct stamina, mana, action points, ammo, items, or other resources. Game code remains responsible for consulting `stats`, `inventory`, or other project systems before or after activation.

This approach is preferred over a global `AbilityService` because abilities usually belong to specific runtime owners. It is preferred over direct `stats` or `inventory` integration because it keeps the module reusable in projects that do not install those modules and avoids hidden side effects.

## Repository Layout

Add a new module tree:

```text
gameplay_modules/abilities/
  module.json
  README.md
  AGENT.md
  addons/abilities/
    ability_container.gd
    ability_definition.gd
    ability_database.gd
    ability_result.gd
    ability_constants.gd
  demo/
    scenes/
    scripts/
    resources/
  tests/
```

As with existing gameplay modules, package fallback copies should be kept byte-identical under:

```text
godot_playwright/bundled_gameplay_modules/abilities/
```

`module.json` describes the base copy operation and demo copy operation. The module has no Autoload entries.

## Module Manifest

The manifest should follow the existing schema:

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
  "demo": {
    "copy": [
      {"from": "demo/scenes", "to": "scenes/abilities_demo"},
      {"from": "demo/scripts", "to": "scripts/abilities_demo"},
      {"from": "demo/resources", "to": "resources/abilities_demo"},
      {"from": "tests", "to": "tests/abilities_demo"}
    ]
  },
  "validation": {
    "commands": [
      "godot-playwright check-scripts /path/to/project res://addons/abilities --exclude addons/godot_playwright/**",
      "godot-playwright check-resources /path/to/project res://addons/abilities --exclude addons/godot_playwright/**"
    ]
  }
}
```

## Runtime Components

`ability_container.gd` defines `class_name AbilityContainer` and extends `Node`. It owns exported configuration, runtime ability storage, initialization, activation checks, activation mutation, cooldown ticking, charge recovery, signals, structured results, and state import/export.

`ability_definition.gd` defines `class_name AbilityDefinition` and extends `Resource`. It stores stable ability configuration.

`ability_database.gd` defines `class_name AbilityDatabase` and extends `Resource`. It contains an exported array of `AbilityDefinition` resources and exposes lookup/validation helpers. Ability IDs must be unique and non-empty.

`ability_result.gd` holds structured result helpers so expected failures return dictionaries instead of throwing exceptions.

`ability_constants.gd` holds schema version, module version, save group name, event names, and any shared string constants.

## Ability Definition

The initial public fields on `AbilityDefinition` are:

```gdscript
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

`ability_id` is the stable identifier used by scripts, saved state, and tests. IDs should be lowercase and stable, such as `dash`, `basic_attack`, `fireball`, `reload`, `scan`, `harvest`, `repair`, `build_wall`, or `open_override`.

`cooldown` is seconds before the ability can be activated again after a successful activation. `0.0` means no cooldown.

`max_charges` is the maximum stored activation count. `0` means the ability has no charge gate. `1` is the default single-use-then-cooldown model.

`initial_charges` is clamped to `0..max_charges` when `max_charges > 0`. It should usually equal `max_charges`.

`charge_recovery_time` is seconds needed to restore one charge after a successful activation. If it is `0.0`, charge recovery uses `cooldown` when `cooldown > 0.0`; otherwise spent charges do not recover automatically. This rule keeps simple single-cooldown abilities easy while allowing multi-charge abilities to define separate recovery timing.

`enabled_by_default` initializes runtime enabled state.

`costs` is declarative JSON-compatible data. Common examples include `{"stamina": 20.0}`, `{"mana": 5.0}`, `{"ammo": 1}`, or `{"action_points": 2}`. The module validates that costs are JSON-compatible and numeric for common scalar cost values, but it does not spend them.

`default_data` is JSON-compatible context copied into runtime activation results. It can hold harmless metadata such as `{"range": 6.0, "radius": 2.0, "element": "fire"}`. It must not contain engine objects.

## AbilityContainer API

The initial public API on `AbilityContainer` is:

```gdscript
@export var database: Resource
@export var save_id: StringName
@export var initialize_on_ready: bool = true
@export var auto_update: bool = true

func initialize_abilities(reset: bool = false) -> Dictionary
func has_ability(ability_id: String) -> bool
func can_activate(ability_id: String, context: Dictionary = {}) -> Dictionary
func activate(ability_id: String, context: Dictionary = {}) -> Dictionary
func set_enabled(ability_id: String, enabled: bool) -> Dictionary
func is_enabled(ability_id: String) -> bool
func get_ability_runtime(ability_id: String) -> Dictionary
func get_abilities() -> Array
func update_abilities(delta: float) -> Array[Dictionary]
func clear_runtime_state() -> void
func get_state() -> Dictionary
func apply_state(data: Dictionary) -> Dictionary
```

`database` must expose the `AbilityDatabase` protocol. The exported type can remain `Resource` to match the inventory, effects, and stats module style.

`save_id` is optional. When non-empty, the container joins the shared save participant group and exposes `get_save_id()`, `save_state()`, and `load_state(data)` wrappers compatible with `save_load`. Containers with empty `save_id` do not automatically persist.

`initialize_on_ready` controls whether `_ready()` initializes runtime state from the database. It defaults to `true` for ordinary scene-driven projects. Tests and generated setup code can set it to `false` and call `initialize_abilities()` explicitly.

`auto_update` controls whether `_process(delta)` advances cooldowns and charge recovery. It defaults to `true`. Turn-based games and deterministic tests can set it to `false` and call `update_abilities(delta)` manually.

`initialize_abilities(false)` should preserve existing runtime state once initialized. `initialize_abilities(true)` clears current runtime state and rebuilds from definitions.

`has_ability()` returns whether the initialized runtime state contains an ability ID.

`can_activate()` validates an activation attempt without mutating runtime state. It checks initialization, database validity, ability existence, enabled state, cooldown, charges, and JSON-compatible context. It returns a structured result with `ok`, `ability_id`, `costs`, `data`, `context`, `warnings`, and `errors`.

`activate()` performs the same checks and, on success, spends one charge when charges are enabled, starts or refreshes cooldown/recovery timers, emits activation signals/events, and returns a structured result. It does not spend external costs.

`set_enabled()` toggles runtime enabled state and emits an event when the value changes.

`get_ability_runtime()` and `get_abilities()` return copies of runtime dictionaries so callers cannot accidentally mutate internal state.

## Runtime Ability State

The container stores one runtime dictionary per ability:

```json
{
  "ability_id": "dash",
  "enabled": true,
  "cooldown_remaining": 0.0,
  "charges": 1,
  "charge_recovery_remaining": 0.0
}
```

The module should preserve deterministic ability order based on the database definition order. Saved state can be applied in any order, but `get_abilities()` should return the database order for stable tests and agent inspection.

The runtime state stores only JSON-compatible values. It does not store the `AbilityDefinition` resource or any engine object.

## Activation Rules

All public ability IDs are normalized by trimming whitespace. Empty IDs fail clearly.

An ability can activate only when:

- The container has initialized successfully.
- The database is assigned and validates.
- The ability ID exists.
- Runtime enabled state is true.
- `cooldown_remaining <= 0.0`.
- If `max_charges > 0`, runtime `charges > 0`.
- The provided `context` dictionary is JSON-compatible.

On successful activation:

- The result includes definition `costs`, a duplicate of definition `default_data` as `data`, input `context`, current runtime state, and an `ability_activated` event.
- If `max_charges > 0`, charges decrease by one.
- If `cooldown > 0.0`, `cooldown_remaining` becomes `cooldown`.
- If charges are enabled and a charge was spent, charge recovery starts when charges are below max and no recovery is already active.
- If charge recovery starts, `charge_recovery_remaining` uses `charge_recovery_time` when positive, otherwise `cooldown` when positive.
- Signals are emitted after runtime state changes.

`default_data` and `context` should not be merged into saved runtime state. They are activation-time payloads.

## Cooldowns And Charges

`update_abilities(delta)` validates that `delta` is finite and non-negative. Invalid deltas return an event array containing one `ability_update_failed` event with `ok = false` and an `errors` array. Ordinary invalid deltas should not call `push_warning()` because they are expected gameplay/runtime validation failures.

For each initialized ability:

- Decrease `cooldown_remaining` toward `0.0`.
- Decrease `charge_recovery_remaining` toward `0.0` when charges are below max.
- When charge recovery reaches `0.0`, restore one charge and emit an `ability_charge_recovered` event.
- If charges are still below max after a recovery event, start the next recovery interval.
- Emit `ability_cooldown_ready` when cooldown transitions from positive to zero.

Cooldown readiness and charge recovery are separate. A single-charge ability with cooldown can activate again only after cooldown reaches zero and at least one charge is available. A no-charge ability (`max_charges = 0`) ignores charge checks and relies only on cooldown/enabled state.

## Structured Results

`AbilityResult.make(ok: bool = true, ability_id: String = "")` should create dictionaries with stable keys:

```json
{
  "ok": true,
  "ability_id": "dash",
  "enabled": true,
  "cooldown_remaining": 0.0,
  "charges": 1,
  "max_charges": 1,
  "charge_recovery_remaining": 0.0,
  "costs": {},
  "data": {},
  "context": {},
  "events": [],
  "warnings": [],
  "errors": []
}
```

Helpers should include `add_event(result, event)`, `add_warning(result, message)`, and `add_error(result, message)`. Adding an error sets `ok` to false.

Expected failures should return structured results instead of throwing exceptions. Programming errors such as missing method names in project-specific code are outside the module boundary.

## Signals And Events

`AbilityContainer` should emit:

```gdscript
signal ability_activated(ability_id: String, result: Dictionary)
signal ability_failed(ability_id: String, result: Dictionary)
signal ability_enabled_changed(ability_id: String, enabled: bool, result: Dictionary)
signal ability_cooldown_ready(ability_id: String, result: Dictionary)
signal ability_charge_recovered(ability_id: String, charges: int, result: Dictionary)
signal abilities_changed(event: Dictionary)
```

The generic `abilities_changed` signal receives event dictionaries such as:

```json
{"type": "ability_activated", "ability_id": "dash"}
{"type": "ability_failed", "ability_id": "dash", "reason": "cooldown"}
{"type": "ability_enabled_changed", "ability_id": "dash", "enabled": false}
{"type": "ability_cooldown_ready", "ability_id": "dash"}
{"type": "ability_charge_recovered", "ability_id": "dash", "charges": 1}
{"type": "state_applied", "ability_id": "dash"}
```

Signals are for UI, sound, animation hooks, state-machine transitions, save diagnostics, and tests. They do not perform gameplay effects by themselves.

## State Import And Export

`get_state()` returns:

```json
{
  "schema_version": 1,
  "abilities": [
    {
      "ability_id": "dash",
      "enabled": true,
      "cooldown_remaining": 0.0,
      "charges": 1,
      "charge_recovery_remaining": 0.0
    }
  ]
}
```

`apply_state(data)` should parse and validate the complete input before mutating runtime state. Malformed state must return a structured failure without changing the existing runtime state.

State parsing should be strict at the persistence boundary:

- `schema_version` must be an integer and must match the current schema.
- `abilities` must be an array.
- Each ability entry must be a dictionary.
- `ability_id` must be a non-empty string without leading or trailing whitespace.
- Unknown ability IDs fail.
- Duplicate ability IDs fail.
- `enabled` must be a bool.
- `cooldown_remaining` and `charge_recovery_remaining` must be finite non-negative numbers.
- `charges` must be an integer within `0..max_charges` when charges are enabled.
- Saved runtime values must satisfy current definition rules.

If a saved state omits an ability that exists in the current database, `apply_state()` should fill it with current definition defaults. This matches the stats module's forward-compatible missing-entry behavior and makes adding new abilities to a shipped game less brittle.

If a saved state includes an ability that no longer exists in the current database, `apply_state()` should fail rather than silently dropping it. Silent drops can hide broken save migrations.

## Saving

Use `get_state()` and `apply_state(data)` for JSON-compatible persistence. If the project also uses `save_load`, set a stable `save_id` on containers that should persist. Containers with a non-empty `save_id` join the `save_participants` group and expose `save_state()` / `load_state(data)` wrappers.

Set `save_id` in the scene/inspector or before the node enters the tree so the container joins the save group. If `save_id` is assigned dynamically after the node has entered the tree, project code must also add the node to `save_participants` or otherwise wire persistence for that container.

Do not set `save_id` on temporary spawned enemies, previews, UI-only containers, or generated one-shot actions unless their cooldown/charge state must persist.

## Optional Integration

The core module does not import `stats`, `effects`, `inventory`, `interaction`, `state_machine`, or `save_load` files.

Common integration patterns:

- `stats`: Before calling `activate()`, project code can check stamina, mana, rage, or action points against `result.costs` from `can_activate()`. After successful activation, project code can call `StatContainer.modify_value()` to spend resources.
- `inventory`: Project code can check and consume ammo, tools, keys, or charges after a successful activation.
- `effects`: Project code can listen for `ability_activated` and call `EffectContainer.add_effect()` on the actor or target.
- `interaction`: An `Interactable` can call an ability on the actor, or an ability `context` can include a target interaction ID or plain data needed by game-specific code.
- `state_machine`: AI and character states can call `can_activate()` in guards and `activate()` when entering or exiting states.
- `save_load`: Stable `save_id` values persist cooldowns, charges, and enabled state.

## Demo

The demo should install a simple scene under `scenes/abilities_demo/`.

Suggested demo abilities:

- `dash`: one charge, short cooldown, stamina-like cost reported but not spent.
- `scan`: no charge gate, moderate cooldown, emits context/data for a target scan.
- `repair`: two charges, charge recovery over time, item-like cost reported but not spent.

The demo script should:

- Create or load an `AbilityDatabase`.
- Assign it to an `AbilityContainer`.
- Activate `dash` successfully.
- Show that a second immediate `dash` fails due to cooldown or charges.
- Manually call `update_abilities(delta)` to recover readiness.
- Toggle an ability disabled and show activation failure.
- Return a deterministic dictionary from `run_abilities_demo()` so copied Python tests can assert behavior.

The demo may include explanatory node names and simple labels, but it should not depend on UI layout or input events for automated validation.

## Tests

Unit and Godot tests should cover:

- Repository module discoverability and manifest fields.
- Installing `abilities` copies addon files and no Autoload.
- Installing `abilities --demo` copies scenes, scripts, resources, and copied tests.
- Source and bundled `abilities` trees are byte-identical.
- `pyproject.toml` includes bundled abilities package data.
- README and AGENT docs contain install, API, validation, and integration guidance.
- `AbilityDefinition`, `AbilityDatabase`, `AbilityResult`, and `AbilityContainer` source expose expected APIs.
- Godot parses installed addon scripts.
- Godot validates demo resources.
- Database validation rejects null resources, wrong resource types, empty IDs, whitespace IDs, duplicate IDs, negative cooldowns, invalid charge values, and non-JSON data.
- Runtime activation succeeds when ready and fails without mutation when unknown, disabled, cooling down, out of charges, or given non-JSON context.
- `can_activate()` does not mutate cooldowns or charges.
- `activate()` emits events and mutates cooldowns/charges only on success.
- `update_abilities(delta)` recovers cooldowns and charges deterministically.
- `get_state()` / `apply_state()` round-trip enabled state, cooldowns, charges, and recovery timers.
- Malformed persisted schema values such as `1.5` and `"1"` fail without mutating runtime state.
- Missing saved abilities are filled from current definitions.
- Stale saved abilities fail clearly.
- Save-load integration works when `save_load` is installed and `save_id` is set before entering the tree.

## Documentation

`README.md` should explain:

- What the module does and does not do.
- How to install with and without the demo.
- How to create definitions and databases.
- The `AbilityContainer` API.
- Instant activation, cooldown, charge, and enabled-state behavior.
- The cost boundary: costs are reported, not automatically spent.
- Save/load usage.
- Optional integration with stats, inventory, effects, interaction, and state machines.
- Validation commands.

`AGENT.md` should give concise guidance for AI agents:

- Use stable `ability_id` values.
- Keep combat, animation, input, and AI decisions outside the module.
- Use `can_activate()` for guards and `activate()` for accepted action requests.
- Do not store engine objects in `default_data`, `context`, or saved state.
- If spending resources, do it explicitly in project code after checking `costs`.
- Set `save_id` before the node enters the tree when persistence is needed.
- Run the module's validation commands after installation.

## Error Handling And Validation

Expected invalid operations should return structured failures. The module should avoid `push_error()` for ordinary gameplay failures such as cooldown, disabled ability, unknown ability IDs, invalid context, or out-of-charges.

Validation should be strict enough that invalid Resource data fails early:

- IDs must be non-empty and stable strings.
- Numeric fields must be finite.
- Cooldowns and recovery times must be zero or greater.
- Charge counts must be zero or greater.
- `initial_charges` must not exceed `max_charges` when charges are enabled.
- `costs` and `default_data` must be JSON-compatible.

Saved-state validation should fully parse into local temporary dictionaries before replacing runtime state. This avoids partial mutation on malformed saves.

## Future Extensions

Future modules or versions can build on this boundary:

- Cast time, channeling, cancellation, and interrupt windows.
- Ability queues and input buffering.
- Ability groups, shared cooldowns, and global cooldown.
- Prerequisites, unlocks, and progression trees.
- Targeting helpers and range checks.
- Built-in optional adapters for `stats`, `inventory`, or `effects`.
- Hotbar/UI helpers.
- Turn-based action-point helpers.

These are intentionally out of v1 so the first module stays small, reliable, and composable with the existing gameplay modules.

## Open Decisions Resolved

- v1 uses instant activation only. Cast/channel/cancel timing is out of scope.
- v1 reports declarative costs but does not automatically spend stats, inventory items, ammo, or other resources.
- v1 does not register an Autoload.
- v1 stores only JSON-compatible runtime state.
