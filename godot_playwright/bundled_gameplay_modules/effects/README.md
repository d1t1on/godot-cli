# Effects Gameplay Module

`effects` adds a Resource-driven runtime effect container for Godot 4.6+ projects.

Install into a Godot project:

```sh
godot-playwright module add /path/to/project effects
```

Install the demo scene and copied demo test:

```sh
godot-playwright module add /path/to/project effects --demo
```

The installer copies `res://addons/effects/`. It does not register an Autoload.

## Effect Definitions

Create `EffectDefinition` resources for each effect type. Use stable `effect_id` values such as `haste`, `poison`, `burning`, `shielded`, `stunned`, or `regen_small`.

Each definition includes:

- `effect_id`: stable identifier used by scripts and save data.
- `display_name`: human-readable label.
- `description`: optional descriptive text.
- `tags`: optional labels such as `buff`, `debuff`, `dot`, `movement`, or `control`.
- `duration`: seconds before expiry. Use `0.0` for permanent effects.
- `tick_interval`: seconds between generic tick events. Use `0.0` for no ticks.
- `stack_mode`: `refresh`, `stack`, or `ignore`.
- `max_stacks`: maximum active stacks for the effect.
- `default_data`: JSON-compatible context data copied into new active instances.

Add definitions to an `EffectDatabase` resource and assign that database to each `EffectContainer` node.

## API

```gdscript
EffectContainer.add_effect(effect_id: String, source: Node = null, stacks: int = 1, data: Dictionary = {}) -> Dictionary
EffectContainer.remove_effect(effect_id: String, stacks: int = 0) -> Dictionary
EffectContainer.clear_effects() -> void
EffectContainer.has_effect(effect_id: String) -> bool
EffectContainer.get_effect(effect_id: String) -> Dictionary
EffectContainer.get_effects() -> Array
EffectContainer.get_stack_count(effect_id: String) -> int
EffectContainer.update_effects(delta: float) -> Array[Dictionary]
EffectContainer.get_state() -> Dictionary
EffectContainer.apply_state(data: Dictionary) -> Dictionary
```

Mutating calls return dictionaries with `ok`, `warnings`, and `errors` fields. `add_effect()` also reports `requested_stacks`, `applied_stacks`, `remainder`, `effect`, and `events`. `remove_effect()` reports `removed_stacks`.

## Stacking

`refresh` refreshes remaining duration and overlays new `data` when the effect is already active.

`stack` increases active stacks up to `max_stacks`, refreshes duration, and reports any `remainder`.

`ignore` leaves an already-active effect unchanged and returns a successful result with a warning.

## Ticks And Expiry

Set `auto_update = true` for ordinary scene-driven projects so `_process(delta)` advances timers. Set `auto_update = false` for turn-based or deterministic tests and call `update_effects(delta)` manually.

Tick events are generic. The module does not apply damage, healing, or stat math by itself. Project code or future `stats`, `combat`, or `skills` modules can listen to `effect_ticked` and `effects_changed` or query active effects.

## Saving

Use `get_state()` and `apply_state(data)` for JSON-compatible persistence. If the project also uses `save_load`, set a stable `save_id` on containers that should persist. Containers with a non-empty `save_id` join the `save_participants` group and expose `save_state()` / `load_state(data)` wrappers.

Do not store Nodes, Resources, Callables, Signals, or other engine objects in effect `default_data` or active effect `data` when the effect may be saved.

## Optional Integration

Inventory item-use scripts can call `EffectContainer.add_effect()` after consuming an item.

Interaction scripts can add effects to the actor or target after an interaction succeeds.

State-machine states can query `has_effect()` or `get_effect()` to decide transitions or guards.

The core module does not import `inventory`, `interaction`, `state_machine`, `stats`, `combat`, or `skills` files.

## Validation

```sh
godot-playwright check-scripts /path/to/project res://addons/effects --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/effects --exclude "addons/godot_playwright/**"
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```
