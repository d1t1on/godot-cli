# Inventory Gameplay Module

`inventory` adds a Resource-driven item stack inventory component for Godot 4.6+ projects.

Install into a Godot project:

```sh
godot-playwright module add /path/to/project inventory
```

Install the demo scene and copied demo test:

```sh
godot-playwright module add /path/to/project inventory --demo
```

The installer copies `res://addons/inventory/`. It does not register an Autoload.

## Item Definitions

Create `InventoryItemDefinition` resources for each item type. Use stable `item_id` values such as `potion_small`, `gold_coin`, or `dungeon_key`.

Each definition includes:

- `item_id`: stable identifier used by scripts and save data.
- `display_name`: human-readable label.
- `description`: optional descriptive text.
- `max_stack`: maximum quantity per stack. Use `1` for non-stackable items.

Add definitions to an `InventoryItemDatabase` resource and assign that database to each `Inventory` node.

## API

```gdscript
Inventory.add_item(item_id: String, quantity: int = 1) -> Dictionary
Inventory.remove_item(item_id: String, quantity: int = 1) -> Dictionary
Inventory.has_item(item_id: String, quantity: int = 1) -> bool
Inventory.get_quantity(item_id: String) -> int
Inventory.clear() -> void
Inventory.get_state() -> Dictionary
Inventory.apply_state(data: Dictionary) -> Dictionary
Inventory.get_stacks() -> Array
```

Operation results are dictionaries with `ok`, `warnings`, and `errors` fields. `add_item()` also reports `added` and `remainder`; `remove_item()` reports `removed`.

## Saving

Use `get_state()` and `apply_state(data)` for JSON-compatible persistence. If the project also uses `save_load`, set a stable `save_id` on the `Inventory` node. Inventories with a non-empty `save_id` join the `save_participants` group and expose `save_state()` / `load_state(data)` wrappers.

## Validation

```sh
godot-playwright check-scripts /path/to/project res://addons/inventory --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/inventory --exclude "addons/godot_playwright/**"
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```
