# Agent Instructions: gameplay_events

Use this module when a Godot project needs a reusable gameplay event bus for
explicit cross-system announcements.

Install with:

```sh
godot-playwright module add /path/to/project gameplay_events
godot-playwright module add /path/to/project gameplay_events --demo
```

Do not assume a global Autoload unless the project created one. Add a
`GameplayEventBus` node to the scene that owns the event routing.

Prefer stable lowercase event IDs such as `item_collected`, `door_opened`, or
`quest_progressed`. Define them as `EventDefinition` Resources and collect them
in an `EventDatabase`.

Keep payloads JSON-compatible. Do not store engine objects, Nodes, Resources,
Callables, cyclic containers, or scene references in payloads, queued events,
history, or saved state.

Use `emit_event()` for immediate announcements. Use `queue_event()` when event
order should be controlled by an explicit flush point.

Use `subscribe(event_id, target, method)` for one-argument callbacks:

```gdscript
func _on_item_collected(event: Dictionary) -> void:
	var payload: Dictionary = event.get("payload", {})
```

Keep cross-module consequences in explicit project code. For example, a
subscriber can turn `item_collected` into inventory mutation, quest progress, UI
feedback, analytics, or state transitions. Do not add hidden dependencies from
this module to inventory, stats, effects, abilities, quests, interaction, state
machines, save/load, combat, dialogue, or UI.

Do not use this module as a rules engine. It announces that something happened;
project systems still decide whether gameplay actions are allowed and what
state changes follow.

Before handing off generated projects, run:

```sh
godot-playwright check-scripts /path/to/project res://addons/gameplay_events --exclude addons/godot_playwright/**
godot-playwright check-resources /path/to/project res://addons/gameplay_events --exclude addons/godot_playwright/**
godot-playwright validate /path/to/project --exclude addons/godot_playwright/**
```
