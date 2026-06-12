# Agent Instructions: gameplay_events

Use this module when a Godot project needs a reusable gameplay event bus for cross-system announcements.

Install with:

```sh
godot-playwright module add /path/to/project gameplay_events
```

Do not assume a global Autoload unless the project created one. Add a `GameplayEventBus` node to the scene that owns the event routing.
