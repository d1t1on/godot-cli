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
