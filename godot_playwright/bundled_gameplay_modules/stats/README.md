# Stats Gameplay Module

`stats` adds a Resource-driven runtime stat container for Godot 4.6+ projects.

Install into a Godot project:

```sh
godot-playwright module add /path/to/project stats
```

Install the demo scene and copied demo test:

```sh
godot-playwright module add /path/to/project stats --demo
```

The installer copies `res://addons/stats/`. It does not register an Autoload.

## Stat Definitions

Create `StatDefinition` resources for each numeric state value. Use stable `stat_id` values such as `health`, `mana`, `stamina`, `move_speed`, `attack`, `defense`, `hunger`, or `heat`.

Each definition includes:

- `stat_id`: stable identifier used by scripts and save data.
- `display_name`: human-readable label.
- `description`: optional descriptive text.
- `tags`: optional category labels.
- `default_base_value`: nominal value or pool capacity.
- `default_current_value`: runtime value used at initialization.
- `clamp_min`, `min_value`, `clamp_max`, `max_value`: bounds.
- `is_pool`: whether current value is capped by the current base value.

Add definitions to a `StatDatabase` resource and assign that database to each `StatContainer` node.

## API

```gdscript
StatContainer.initialize_stats(reset: bool = false) -> Dictionary
StatContainer.has_stat(stat_id: String) -> bool
StatContainer.get_value(stat_id: String) -> float
StatContainer.get_base_value(stat_id: String) -> float
StatContainer.get_stat(stat_id: String) -> Dictionary
StatContainer.get_stats() -> Array
StatContainer.set_value(stat_id: String, value: float) -> Dictionary
StatContainer.modify_value(stat_id: String, delta: float) -> Dictionary
StatContainer.set_base_value(stat_id: String, value: float) -> Dictionary
StatContainer.modify_base_value(stat_id: String, delta: float) -> Dictionary
StatContainer.get_state() -> Dictionary
StatContainer.apply_state(data: Dictionary) -> Dictionary
```

Operation results are dictionaries with `ok`, `stat_id`, previous/current values, previous/current base values, `requested_value`, `delta`, `clamped`, `events`, `warnings`, and `errors` fields.

## Pool Stats

Use `is_pool = true` for health, mana, stamina, batteries, shields, or other values where the current value should not exceed the base value. Lowering a pool base value clamps the current value when needed.

Non-pool stats such as `move_speed`, `attack`, or `defense` do not use the base value as a current-value maximum. They only use explicit min/max clamps.

## Signals

`StatContainer` emits `stat_changed`, `base_stat_changed`, `stat_depleted`, `stat_filled`, and `stats_changed`.

Use signals for UI, death handling, exhaustion, low-resource logic, and tests. Keep combat formulas, healing formulas, level curves, temporary effects, and UI rendering outside this module.

## Saving

Use `get_state()` and `apply_state(data)` for JSON-compatible persistence. If the project also uses `save_load`, set a stable `save_id` on stat containers that should persist. A non-empty `save_id` makes the node join the `save_participants` group and exposes wrappers compatible with `SaveService`.

Do not set `save_id` on temporary previews, generated enemies, or UI-only containers unless they must persist.

## Optional Integration

Inventory item-use scripts can call `modify_value()` after consuming an item. Interaction scripts can modify stats on use. State machines can query stats in guards. The future `effects` module can call stat mutation methods for direct tick consequences.

The core module does not import or require `inventory`, `interaction`, `state_machine`, `effects`, or `save_load`.

## Validation

```sh
godot-playwright check-scripts /path/to/project res://addons/stats --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/stats --exclude "addons/godot_playwright/**"
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```
