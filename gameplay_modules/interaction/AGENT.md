# Agent Instructions: interaction

Use this module when a Godot project needs nearby object interaction, pickups, doors, chests, buttons, NPC use prompts, or simple mechanisms.

Install with:

```sh
godot-playwright module add /path/to/project interaction
```

Use `--demo` only when adding a demo scene and copied test is acceptable:

```sh
godot-playwright module add /path/to/project interaction --demo
```

## Wiring Interactions

1. Add an `Interactable` node under the object that can be used.
2. Set a stable `interaction_id` for objects that may be saved or referenced by scripts.
3. Set `prompt`, `priority`, and `enabled`.
4. Add `Interactor2D` or `Interactor3D` to the actor that detects nearby objects.
5. Give the interactor a collision shape and collision layers/masks appropriate for the project.
6. Call `interact_best()` when game input, UI, or AI behavior decides to interact.

## Boundaries

Do not use this module as a quest system, dialogue graph, inventory system, or UI system. Keep each `Interactable.interact()` method small and domain-specific.

Use `Inventory` only when the project has installed the inventory module and the interaction needs item transfer. Use `SaveService` only through explicit save participant wrappers on objects that should persist.

## Validation Commands

Run targeted checks after installation:

```sh
godot-playwright check-scripts /path/to/project res://addons/interaction --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/interaction --exclude "addons/godot_playwright/**"
```

Run broader validation after wiring game scenes:

```sh
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```
