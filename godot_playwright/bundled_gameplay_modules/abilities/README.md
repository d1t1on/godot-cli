# Abilities Gameplay Module

`abilities` adds a Resource-driven instant ability and action container for Godot 4.6+ projects.

Install into a Godot project:

```sh
godot-playwright module add /path/to/project abilities
```

Install the demo scene, demo resources, and copied demo test:

```sh
godot-playwright module add /path/to/project abilities --demo
```

The installer copies `res://addons/abilities/`. It does not register an Autoload.

## Ability Definitions

Create `AbilityDefinition` resources for each action the game can request. Use stable `ability_id` values such as `dash`, `scan`, `repair`, `reload`, `attack_light`, or `build_wall`.

Each definition includes:

- `ability_id`: stable identifier used by scripts and save data.
- `display_name`: human-readable label.
- `description`: optional descriptive text.
- `tags`: optional labels such as `movement`, `attack`, `utility`, `repair`, or `build`.
- `cooldown`: seconds before the ability can activate again. Use `0.0` for no cooldown.
- `max_charges`: maximum stored charges. Use `0` for an ability that is not charge-gated.
- `initial_charges`: charges available when runtime state is initialized.
- `charge_recovery_time`: seconds to recover one charge. Use `0.0` to fall back to `cooldown`.
- `enabled_by_default`: whether the ability starts enabled.
- `costs`: JSON-compatible cost data reported in activation results.
- `default_data`: JSON-compatible ability data copied into query and activation results.

Add definitions to an `AbilityDatabase` resource and assign that database to each `AbilityContainer` node.

## API

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

Mutating calls return dictionaries with `ok`, `warnings`, and `errors` fields. Ability query and activation results also include `ability_id`, `enabled`, `cooldown_remaining`, `charges`, `max_charges`, `charge_recovery_remaining`, `costs`, `data`, `context`, and `events`.

## Instant Activation

Abilities are instant in v1. Call `AbilityContainer.can_activate(ability_id, context)` before accepting input, AI, interaction, or UI requests. It validates the database, known `ability_id`, enabled state, cooldown, charges, and JSON-compatible `context` without mutating runtime state.

Call `AbilityContainer.activate(ability_id, context)` only after the request is accepted. A successful activation consumes one charge when `max_charges > 0`, starts cooldown when `cooldown > 0.0`, starts charge recovery when needed, emits `ability_activated`, and reports an `ability_activated` event. A failed activation returns `ok: false` and emits `ability_failed` for known abilities.

The module does not run animations, apply input buffering, pick targets, decide AI actions, apply effects, or deal damage. Use project code or other modules for those consequences.

## Cooldown And Charges

`cooldown_remaining` blocks activation until it reaches zero. With `auto_update = true`, the container advances timers in `_process(delta)`. For turn-based games or deterministic tests, set `auto_update = false` and call `update_abilities(delta)` manually.

When `max_charges > 0`, activation requires at least one charge and spends one charge on success. Charges recover one at a time until `max_charges` is reached. `charge_recovery_time` controls the recovery interval; when it is `0.0`, recovery uses `cooldown`.

When `max_charges == 0`, charges do not gate activation and activation does not spend charges. Use cooldown, enabled state, and game-specific guards for those abilities.

## Costs

The costs are reported in `can_activate()` and `activate()` results but not automatically spent. This boundary is deliberate: the module does not know whether a cost means stamina, mana, ammo, inventory items, charges in another system, or a project-specific resource.

Spend resources in project code after `can_activate()` succeeds and before or around `activate()`. If spending fails, do not call `activate()`, or call `set_enabled()` / project-specific feedback logic as appropriate.

## Saving

Use `get_state()` and `apply_state(data)` for JSON-compatible persistence. The saved state stores schema version, stable `ability_id` values, enabled state, cooldown timers, charges, and charge recovery timers.

If the project also uses `save_load`, set a stable `save_id` on containers that should persist. Containers with a non-empty `save_id` join the `save_participants` group when they enter the tree and expose `save_state()` / `load_state(data)` wrappers. Set `save_id` before the node enters the tree so group membership is ready for `SaveService`.

Do not store Nodes, Resources, Callables, Signals, or other engine objects in `default_data`, activation `context`, or saved state.

## Optional Integration

Stats scripts can inspect reported `costs`, spend stamina or mana, and use `AbilityContainer.can_activate()` as one guard before accepting an action.

Inventory scripts can spend ammo, tools, or ingredients before calling `AbilityContainer.activate()`.

Effects scripts can listen for `ability_activated` and apply buffs, debuffs, cooldown modifiers, or gameplay consequences outside the abilities module.

Interaction scripts can call `can_activate()` and `activate()` when an interactable requests an action from an actor or target.

State-machine states can query `has_ability()`, `is_enabled()`, `can_activate()`, or runtime cooldown and charge data to decide transitions or guards.

The core module does not import `stats`, `inventory`, `effects`, `interaction`, `state_machine`, `save_load`, combat, animation, input, UI, or AI files.

## Validation

```sh
godot-playwright check-scripts /path/to/project res://addons/abilities --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/abilities --exclude "addons/godot_playwright/**"
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```
