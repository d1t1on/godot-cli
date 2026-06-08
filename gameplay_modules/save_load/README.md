# Save Load Gameplay Module

`save_load` adds a small JSON save/load service for Godot 4.6+ projects.

Install into a Godot project:

```sh
godot-playwright module add /path/to/project save_load
```

Install the demo scene and copied demo test:

```sh
godot-playwright module add /path/to/project save_load --demo
```

The installer copies `res://addons/save_load/` and registers this enabled Autoload:

```text
SaveService="*res://addons/save_load/save_service.gd"
```

## API

```gdscript
SaveService.save_slot(slot_id: String) -> Dictionary
SaveService.load_slot(slot_id: String) -> Dictionary
SaveService.delete_slot(slot_id: String) -> Dictionary
SaveService.list_slots() -> Array[Dictionary]
SaveService.has_slot(slot_id: String) -> bool
```

Save files are written to `user://saves/{slot_id}.json`.

## Participant Nodes

Add a node to the `save_participants` group and implement:

```gdscript
func get_save_id() -> String:
    return "player"

func save_state() -> Dictionary:
    return {"health": 10}

func load_state(data: Dictionary) -> void:
    health = int(data.get("health", 10))
```

Use explicit stable `save_id` values for player, inventory, quest, world-state, and other long-lived objects.

## Validation

```sh
godot-playwright check-scripts /path/to/project res://addons/save_load --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/save_load --exclude "addons/godot_playwright/**"
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```
