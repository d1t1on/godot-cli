# Gameplay Events Gameplay Module

`gameplay_events` adds a Resource-driven gameplay event bus for Godot 4.6+
projects. It is useful when game systems need explicit cross-system
announcements without hard dependencies between those systems.

Install into a Godot project:

```sh
godot-playwright module add /path/to/project gameplay_events
godot-playwright module add /path/to/project gameplay_events --demo
```

The installer copies `res://addons/gameplay_events/`. It does not register an
Autoload. Add a `GameplayEventBus` node to the scene that owns event routing.

## Authoring

Create `EventDefinition` Resources for stable event IDs, then collect them in an
`EventDatabase` Resource assigned to a `GameplayEventBus`.

`EventDefinition` fields:

- `event_id`: stable lowercase event ID such as `item_collected`.
- `display_name`: editor-facing name.
- `description`: editor-facing notes.
- `tags`: optional grouping labels.
- `default_payload`: JSON-compatible defaults merged before caller payload.
- `record_by_default`: whether dispatched events are retained in history.

`EventDatabase.validate()` checks non-empty unique IDs, trims errors, Resource
types, and JSON-compatible default payloads.

## GameplayEventBus API

Use these calls from project code:

- `emit_event(event_id, payload)`: synchronously create and dispatch an event.
- `queue_event(event_id, payload)`: append an event for later dispatch.
- `flush_events(limit)`: dispatch queued events in order.
- `subscribe(event_id, target, method)`: register a one-argument
  `event: Dictionary` callback.
- `unsubscribe(event_id, target, method)`: remove a callback.
- `get_history(limit)` / `clear_history()`: inspect or clear retained history.
- `get_state()` / `apply_state(data)`: export and restore queue/history state.
- `save_state()` / `load_state(data)`: save-load compatible wrappers.

Synchronous dispatch:

```gdscript
var result := event_bus.emit_event("item_collected", {"item_id": "coin"})
if result.get("ok", false):
	var event: Dictionary = result.get("event", {})
	print(event.get("payload", {}))
```

Queued dispatch:

```gdscript
event_bus.queue_event("door_opened", {"door_id": "north_gate"})
event_bus.flush_events()
```

Subscriptions:

```gdscript
event_bus.subscribe("item_collected", self, &"_on_item_collected")


func _on_item_collected(event: Dictionary) -> void:
	var payload: Dictionary = event.get("payload", {})
```

## Saving

Set `save_id` before the node enters the tree if you want the bus to join the
`save_participants` group. `get_state()` returns the schema version, sequence,
queue, and history. History is only included when `save_history` is true.

Use `record_history` and `max_history` to control runtime history retention. Use
`save_history` only when replay or debugging history should persist in saved
games.

## Boundaries

This module does not directly integrate with inventory, stats, effects,
abilities, quests, interaction, state machines, combat, dialogue, UI, or
analytics. Use explicit project code to subscribe to an event and trigger
consequences in those systems.

Payloads, queued events, history, and saved state must stay JSON-compatible. Do
not put Nodes, Resources, Callables, engine objects, or cyclic containers in
event payloads.

## Validation

Run the installed module through Godot checks:

```sh
godot-playwright check-scripts /path/to/project res://addons/gameplay_events --exclude addons/godot_playwright/**
godot-playwright check-resources /path/to/project res://addons/gameplay_events --exclude addons/godot_playwright/**
```
