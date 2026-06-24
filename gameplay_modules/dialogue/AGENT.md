# Agent Instructions: dialogue

Use this module when a Godot project needs branching dialogue, conversations, NPC interactions, or narrative trees.

Install with:

```sh
godot-playwright module add /path/to/project dialogue
```

Use `--demo` only when adding a demo scene, demo resources, and copied test is acceptable:

```sh
godot-playwright module add /path/to/project dialogue --demo
```

## Wiring Dialogue

1. Create one `DialogueChoiceDefinition` Resource per choice.
2. Create one `DialogueLineDefinition` Resource per line and attach its choices.
3. Create one `DialogueDefinition` Resource per dialogue and attach its lines.
4. Use stable lowercase `dialogue_id`, `line_id`, and `choice_id` values. Do not rename IDs after save data exists unless you also migrate saves.
5. Add dialogue definitions to a `DialogueDatabase` Resource.
6. Add a `DialogueRunner` node to the scene that owns dialogue state.
7. Assign the database and set a stable `save_id` only when this runner should persist through `save_load`.

## Runtime

Prefer explicit dialogue progression. Project code calls `start_dialogue()`, `select_choice()`, `advance()`, or `stop_dialogue()` only when gameplay should drive the conversation.

Do not add hidden listeners that automatically watch inventory, interaction, stats, abilities, effects, quests, combat, input, UI, or state machines. Those systems should call the public API when they accept an event.

`on_enter`, `on_exit`, and `on_select` payloads are reported in results and signals but are not automatically dispatched to other systems. Project code listens to signals and applies consequences.

## Boundaries

Do not add hidden dependencies on other modules. The module can coordinate with `interaction`, `inventory`, `stats`, `abilities`, `effects`, `quests`, `state_machine`, and `save_load` through IDs, result dictionaries, signals, and saved state, but it must not import those modules.

Variables, event payloads, and saved state must be JSON-compatible. Use strings, numbers, booleans, nulls, arrays, and dictionaries with string keys. Do not store Nodes, Resources, Callables, Signals, UI references, or cyclic containers.

Conditions run Godot `Expression` against the dialogue `variables` dictionary only. Do not rely on globals, Autoloads, or scene tree access inside conditions.

## Saving

The module does not require `save_load`. For custom persistence, use `get_state()` and `apply_state(data)`.

When the project uses `save_load`, set a stable `save_id` before the node enters the tree so the `DialogueRunner` joins the `save_participants` group and persists through `SaveService`.

Preserve byte-identical source and bundled trees when editing this module:

```sh
diff -qr gameplay_modules/dialogue godot_playwright/bundled_gameplay_modules/dialogue
```

## Validation Commands

```sh
godot-playwright check-scripts /path/to/project res://addons/dialogue --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/dialogue --exclude "addons/godot_playwright/**"
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```
