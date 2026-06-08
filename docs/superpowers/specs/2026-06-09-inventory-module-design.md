# Inventory Gameplay Module Design

Date: 2026-06-09

## Context

`godot-playwright` now has a gameplay module system and a first module, `save_load`, for JSON slot persistence. The next useful module is `inventory`: many agent-built Godot games need item stacks, consumables, keys, currencies, chest contents, or player storage, and these systems should not be rebuilt from scratch for every project.

This design adds an installable `inventory` module as the second gameplay module. It builds a reusable data core and a small validation demo. It intentionally avoids UI, equipment, hotbars, pickups, shops, crafting, loot tables, and unique item instances in the MVP.

## Goals

- Add `inventory` as an installable gameplay module.
- Provide a Godot-native inventory data core using Resource item definitions.
- Support multiple inventories in one project through a reusable node component.
- Support finite slot capacity, stack limits, add/remove/query operations, and JSON-compatible state round-trips.
- Keep `save_load` integration optional while documenting and testing the integration path.
- Include a small demo scene and copied test so agents can validate installation and behavior.
- Provide human and agent documentation for common usage and validation.

## Non-Goals

- Do not build inventory UI, drag/drop, hotbars, item pickup actors, shops, crafting, loot tables, or equipment slots.
- Do not implement unique item instances with durability, randomized stats, or per-instance metadata.
- Do not require or auto-install `save_load`.
- Do not scan arbitrary resource directories at runtime.
- Do not support JSON item definition files in this increment.

## Chosen Approach

Use a lightweight `Inventory` node component plus Godot Resource definitions.

Installation uses the existing module CLI:

```sh
godot-playwright module add <project> inventory
godot-playwright module add <project> inventory --demo
```

The module copies `res://addons/inventory/` into the target project. It does not register an Autoload. A game adds `Inventory` nodes wherever it needs inventory state: player, chest, shop, stash, or NPC.

This approach is preferred over an `InventoryService` Autoload because it avoids assuming a single global player inventory. It is also preferred over a larger gameplay pack because it keeps this iteration focused on the data model that later modules can reuse.

## Repository Layout

Add a new module tree:

```text
gameplay_modules/inventory/
  module.json
  README.md
  AGENT.md
  addons/inventory/
    inventory.gd
    inventory_item_definition.gd
    inventory_item_database.gd
    inventory_stack.gd
    inventory_result.gd
    inventory_constants.gd
  demo/
    scenes/
    scripts/
    resources/
  tests/
```

As with `save_load`, package fallback copies should be kept under:

```text
godot_playwright/bundled_gameplay_modules/inventory/
```

`module.json` should describe the base copy operation and demo copy operation. The module has no Autoload entries.

## Runtime Components

`inventory.gd` defines `class_name Inventory` and extends `Node`. It owns exported capacity, optional save ID, item database reference, stack storage, add/remove/query operations, and state import/export.

`inventory_item_definition.gd` defines `class_name InventoryItemDefinition` and extends `Resource`. MVP fields:

```gdscript
@export var item_id: StringName
@export var display_name: String
@export_multiline var description: String
@export_range(1, 999, 1) var max_stack: int = 99
```

`inventory_item_database.gd` defines `class_name InventoryItemDatabase` and extends `Resource`. It contains an exported array of `InventoryItemDefinition` resources and exposes lookup/validation helpers. Item IDs must be unique and non-empty.

`inventory_stack.gd` may hold a small data helper for stack dictionaries or Resource-like stack records if it keeps `inventory.gd` simpler. It must not become a separate persistent item-instance system.

`inventory_result.gd` and `inventory_constants.gd` hold shared result construction and names so result shapes stay consistent across the module.

## Inventory API

The initial public API on `Inventory` is:

```gdscript
func add_item(item_id: String, quantity: int = 1) -> Dictionary
func remove_item(item_id: String, quantity: int = 1) -> Dictionary
func has_item(item_id: String, quantity: int = 1) -> bool
func get_quantity(item_id: String) -> int
func clear() -> void
func get_state() -> Dictionary
func apply_state(data: Dictionary) -> Dictionary
func get_stacks() -> Array
```

The API uses structured dictionaries for operation results, matching the `save_load` style:

```gdscript
{
  "ok": true,
  "item_id": "potion",
  "requested": 5,
  "added": 5,
  "removed": 0,
  "remainder": 0,
  "warnings": [],
  "errors": []
}
```

Expected failures use `ok: false` with `errors`, not exceptions.

## Stack And Capacity Rules

Inventory stores simple stacks: each stack has an `item_id` and a positive integer `quantity`. The item definition controls `max_stack`. Non-stackable items use `max_stack = 1`.

Rules:

- `capacity` is the maximum number of stacks, not total item quantity.
- `capacity < 0` is invalid. `capacity = 0` means no stacks can be held.
- `max_stack <= 0` is invalid.
- `quantity <= 0` for add/remove is invalid.
- Unknown item IDs are rejected.
- `add_item()` fills existing compatible stacks first, then creates new stacks while capacity allows.
- If nothing can be added, `add_item()` returns `ok: false`.
- If some items are added but capacity or stack limits leave a remainder, `add_item()` returns `ok: true`, sets `remainder > 0`, and includes a warning.
- `remove_item()` only mutates if the requested quantity is available. Removing more than available returns `ok: false` and leaves the inventory unchanged.
- Empty stacks are removed after successful removal.

The module should preserve stack order where practical so UI code and tests can reason about deterministic output.

## State Format

`get_state()` returns JSON-compatible data:

```json
{
  "schema_version": 1,
  "capacity": 12,
  "stacks": [
    {"item_id": "potion", "quantity": 5},
    {"item_id": "key", "quantity": 1}
  ]
}
```

`capacity` in saved state records the capacity at save time for diagnostics. `apply_state(data)` does not overwrite the scene's current exported capacity. It validates the complete state against the current inventory configuration before mutating, including schema version, capacity shape, stack array shape, known item IDs, positive integer quantities, stack limits, and whether the saved stacks fit the current capacity. A capacity mismatch may produce a warning when the stacks still fit. Invalid state returns `ok: false` and does not partially mutate the inventory.

Saved unknown item IDs fail by default rather than being ignored. This makes missing item definitions visible during development and validation.

## Optional Save Load Integration

The module must be usable without `save_load`. It exposes `get_state()` and `apply_state(data)` as the stable persistence boundary.

For projects using `save_load`, an `Inventory` node can participate directly by joining the `save_participants` group and exposing:

```gdscript
func get_save_id() -> String
func save_state() -> Dictionary
func load_state(data: Dictionary) -> void
```

These methods should be thin wrappers around `get_state()` and `apply_state(data)`. The module should not auto-register the group for every inventory by default unless a clear exported `save_id` is configured. This avoids accidental persistence of temporary inventories such as shops or loot previews.

The demo should validate module-local state round-trip by default. If `SaveService` is present in the project, the demo should also verify a real slot save/load round-trip.

## Demo

`--demo` installs a small runtime scene with:

- One `Inventory` node.
- A small `InventoryItemDatabase` resource.
- Sample `InventoryItemDefinition` resources for `potion`, `key`, and `coin`.
- A root script with a deterministic `run_inventory_demo()` method.

The demo method should cover:

- Adding stackable and non-stackable items.
- Querying quantities.
- Removing a consumable quantity.
- Hitting capacity or stack remainder behavior.
- Round-tripping through `get_state()` and `apply_state()`.
- Optional `SaveService` save/load round-trip when `save_load` is installed.

The copied Python demo test should load the scene through `godot-playwright`, call the demo method, and assert a structured success result.

## CLI And Installer Behavior

The existing `godot-playwright module list` should show both `save_load` and `inventory` once this module is present.

`godot-playwright module add <project> inventory` should copy only the base module files. It should use existing safe installer behavior:

- Refuse to overwrite files by default.
- Allow `--force` only for module-owned paths.
- Reject duplicate planned targets.
- Avoid symlink target overwrites.
- Return a clear installation report.

`godot-playwright module add <project> inventory --demo` should also copy demo scenes, scripts, resources, and tests into module-specific demo paths such as:

```text
res://scenes/inventory_demo/
res://scripts/inventory_demo/
res://resources/inventory_demo/
tests/inventory_demo/
```

## Documentation

`README.md` should explain:

- How to install the module.
- How to create item definitions and an item database.
- How to add an `Inventory` node to a scene.
- How to call add/remove/query methods.
- How to serialize state.
- How to integrate with `save_load` when desired.

`AGENT.md` should give operational instructions:

- Use this module when a game needs item stacks, keys, consumables, currencies, chests, or player storage.
- Prefer stable `item_id` values such as `potion_small`, `gold_coin`, or `dungeon_key`.
- Keep item definitions in Resources and reference them from an item database.
- Validate after installation with targeted script/resource checks.
- If using `save_load`, add explicit save IDs and run a save/load round-trip test.

## Testing Strategy

Python tests should cover:

- Module discovery lists both modules.
- `module add inventory` copies base files and does not add Autoloads.
- `module add inventory --demo` copies demo files, resources, and tests.
- Package fallback data contains the bundled inventory module.
- Source and bundled module trees stay byte-identical.
- Existing installer safety behavior still applies to the new module.

Godot validation should cover when Godot is available:

- Inventory module scripts pass Godot parser checks.
- Demo scenes/resources have valid dependencies.
- Demo runtime method validates add/remove/capacity/state round-trip.
- Temporary project with both `save_load` and `inventory` installed validates optional `SaveService` integration.

If Godot is unavailable, Python installer tests still provide coverage, and final reporting must state that live Godot validation was skipped.

## Future Extensions

After the MVP is stable, future modules or iterations can add:

- Item pickup actors, likely integrated with a future `interaction` module.
- Inventory UI scenes and semantic UI signals.
- Equipment slots and stat modifiers.
- Hotbars and quick-use behavior.
- Loot tables and item drops.
- Unique item instances with durability or generated attributes.
- JSON item definition import/export if agent bulk editing needs it.

These are outside this increment.

## Acceptance Criteria

- `godot-playwright module list` shows `inventory`.
- `godot-playwright module add <project> inventory` installs `res://addons/inventory/` without registering an Autoload.
- `godot-playwright module add <project> inventory --demo` installs demo scene, scripts, resources, and copied demo test.
- `Inventory` supports add, remove, has, quantity, clear, state export, and state import.
- Item definitions are Godot Resources and are looked up through an item database Resource.
- Unknown item IDs and invalid quantities fail clearly.
- Capacity and partial-add behavior are deterministic and tested.
- `apply_state()` validates before mutation.
- Demo validates module-local state round-trip.
- Demo or integration test validates optional `save_load` round-trip when both modules are installed.
- Human and agent docs explain usage and validation.
