# Interaction Gameplay Module

`interaction` adds range-based interaction components for Godot 4.6+ projects.

Install into a Godot project:

```sh
godot-playwright module add /path/to/project interaction
```

Install the demo scene and copied demo test:

```sh
godot-playwright module add /path/to/project interaction --demo
```

The installer copies `res://addons/interaction/`. It does not register an Autoload.

## Core Components

Add an `Interactable` node under objects that can be used, picked up, opened, talked to, or triggered. Configure stable `interaction_id` values for objects that may be saved.

Add `Interactor2D` to a 2D actor or `Interactor3D` to a 3D actor. The interactor tracks nearby areas and bodies, resolves an `Interactable`, chooses the highest-priority enabled candidate, and breaks priority ties by earliest enter order.

## API

```gdscript
Interactable.interact(actor: Node, data: Dictionary = {}) -> Dictionary
Interactable.can_interact(actor: Node, data: Dictionary = {}) -> bool
Interactable.get_interaction_prompt(actor: Node = null) -> String
Interactable.get_state() -> Dictionary
Interactable.apply_state(data: Dictionary) -> Dictionary

Interactor2D.get_candidates() -> Array
Interactor2D.get_best_candidate() -> Node
Interactor2D.get_best_prompt() -> String
Interactor2D.interact_best(data: Dictionary = {}) -> Dictionary
Interactor2D.interact_with(target: Node, data: Dictionary = {}) -> Dictionary
Interactor2D.clear_candidates() -> void
```

`Interactor3D` exposes the same methods as `Interactor2D`.

Operation results are dictionaries with `ok`, `interaction_id`, `target`, `warnings`, and `errors` fields. Game-specific interactables may add fields such as `opened`, `picked_up`, `item_id`, or `quantity`.

## Saving

Use `get_state()` and `apply_state(data)` for JSON-compatible persistence of generic interaction fields. If the project also uses `save_load`, wrap those methods in explicit save participant methods only on objects that should persist.

## UI Prompts

The module does not draw UI. Use `get_best_prompt()` or `get_best_candidate().get_interaction_prompt(actor)` from your own UI code.

## Validation

```sh
godot-playwright check-scripts /path/to/project res://addons/interaction --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/interaction --exclude "addons/godot_playwright/**"
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```
