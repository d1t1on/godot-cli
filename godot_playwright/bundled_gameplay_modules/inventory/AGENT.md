# Agent Instructions: inventory

Use this module when a Godot project needs item stacks, keys, consumables, currencies, chests, player storage, stash contents, or simple shop stock.

Install with:

```sh
godot-playwright module add /path/to/project inventory
```

Use `--demo` only when adding a demo scene and copied test is acceptable:

```sh
godot-playwright module add /path/to/project inventory --demo
```

## Wiring Items

1. Create one `InventoryItemDefinition` Resource per item type.
2. Use stable `item_id` values. Do not rename `item_id` values after save data exists unless you also migrate saves.
3. Set `max_stack = 1` for non-stackable items such as keys.
4. Add the item definitions to an `InventoryItemDatabase` Resource.
5. Add an `Inventory` node to the scene that owns the item stacks.
6. Assign the database and capacity on the `Inventory` node.

## Using The Inventory

Call `add_item(item_id, quantity)`, `remove_item(item_id, quantity)`, `has_item(item_id, quantity)`, and `get_quantity(item_id)`. Always inspect returned dictionaries from mutating calls. Treat `ok: false` as a real gameplay or data error.

`add_item()` may return `ok: true` with a positive `remainder` when some items fit and some did not. Handle the remainder by leaving items on the ground, showing a message, or retrying later.

## Saving

The module does not require `SaveService`. For custom persistence, use `get_state()` and `apply_state(data)`.

When the project uses `save_load`, set a stable `save_id` on inventories that should persist. A non-empty `save_id` makes the node join the `save_participants` group and exposes wrappers compatible with `SaveService`.

Do not set `save_id` on temporary inventories such as shop previews or generated loot containers unless they must persist.

## Validation Commands

Run targeted checks after installation:

```sh
godot-playwright check-scripts /path/to/project res://addons/inventory --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/inventory --exclude "addons/godot_playwright/**"
```

Run broader validation after wiring game scenes:

```sh
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```

If using `SaveService`, run a save/load round-trip test that mutates the inventory after save and verifies the original item quantities are restored after load.
