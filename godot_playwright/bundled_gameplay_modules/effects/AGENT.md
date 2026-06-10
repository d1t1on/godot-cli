# Agent Instructions: effects

Use this module when a Godot project needs buffs, debuffs, status ailments, temporary modifiers, item effects, equipment modifiers, DOT/HOT markers, or interaction-triggered effects.

Install with:

```sh
godot-playwright module add /path/to/project effects
```

Use `--demo` only when adding a demo scene and copied test is acceptable:

```sh
godot-playwright module add /path/to/project effects --demo
```

## Wiring Effects

1. Create one `EffectDefinition` Resource per effect type.
2. Use stable `effect_id` values. Do not rename `effect_id` values after save data exists unless you also migrate saves.
3. Set `duration = 0.0` for permanent effects.
4. Set `tick_interval = 0.0` for effects that do not tick.
5. Choose `stack_mode`: `refresh`, `stack`, or `ignore`.
6. Add definitions to an `EffectDatabase` Resource.
7. Add an `EffectContainer` node to each gameplay object that can receive effects.
8. Assign the database and choose whether `auto_update` should run timers automatically.

## Using Effects

Call `EffectContainer.add_effect(effect_id, source, stacks, data)`, `remove_effect(effect_id, stacks)`, `has_effect(effect_id)`, `get_effect(effect_id)`, and `get_stack_count(effect_id)`. Always inspect returned dictionaries from mutating calls. Treat `ok: false` as a gameplay or data error.

Use `auto_update = false` for deterministic turn-based tests or systems that should advance effects only on explicit turns. Then call `update_effects(delta)` when the turn or simulation step advances.

## Boundaries

Do not use this module as a full stats, combat, skill, quest, UI, or aura/spatial-detection system. Put actual damage, healing, stat math, UI rendering, and gameplay consequences in project scripts or future domain modules.

The `effects` module can support future `stats`, `combat`, and `skills` modules through active effect tags, data, and tick events, but it does not depend on those modules.

## Saving

The module does not require `save_load`. For custom persistence, use `get_state()` and `apply_state(data)`.

When the project uses `save_load`, set a stable `save_id` on containers that should persist. A non-empty `save_id` makes the node join the `save_participants` group and exposes wrappers compatible with `SaveService`.

Do not set `save_id` on temporary effect previews, generated hazards, or one-scene objects unless they must persist.

## Validation Commands

Run targeted checks after installation:

```sh
godot-playwright check-scripts /path/to/project res://addons/effects --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/effects --exclude "addons/godot_playwright/**"
```

Run broader validation after wiring game scenes:

```sh
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```

If using `SaveService`, run a save/load round-trip test that mutates effects after save and verifies the original active effect IDs, stack counts, timers, and data are restored after load.
