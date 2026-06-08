# Agent Instructions: save_load

Use this module when a Godot project needs local save slots, persistent player state, world flags, inventory data, quest data, settings, or other JSON-compatible runtime state.

Install with:

```sh
godot-playwright module add /path/to/project save_load
```

Use `--demo` only when adding a demo scene and copied test is acceptable:

```sh
godot-playwright module add /path/to/project save_load --demo
```

After installation, inspect `res://addons/save_load/` and confirm `SaveService` is registered as an Autoload.

## Wiring Objects

For every object that should persist:

1. Add the node to the `save_participants` group.
2. Give it a stable explicit `save_id` through `get_save_id()` or a `save_id` exported property.
3. Implement `save_state() -> Dictionary`.
4. Implement `load_state(data: Dictionary) -> void`.

Saved data must be JSON-compatible: dictionaries, arrays, strings, numbers, booleans, and null. Do not store Nodes, Resources, Signals, Callables, or engine objects.

If `SaveService` reports a NodePath fallback warning, add an explicit `save_id` before serious release work. NodePath fallback is useful during prototyping but fragile after scene renames or reparenting.

## Validation Commands

Run targeted checks after installation:

```sh
godot-playwright check-scripts /path/to/project res://addons/save_load --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/save_load --exclude "addons/godot_playwright/**"
```

Run broader validation after wiring game objects:

```sh
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```
