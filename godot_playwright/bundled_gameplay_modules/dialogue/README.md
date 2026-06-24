# Dialogue Gameplay Module

`dialogue` adds a Resource-driven branching dialogue system for Godot 4.6+ projects.

Install into a Godot project:

```sh
godot-playwright module add /path/to/project dialogue
godot-playwright module add /path/to/project dialogue --demo
```

The installer copies `res://addons/dialogue/`. It does not register an Autoload.

## Authoring

Create `DialogueLineDefinition` Resources for individual lines, `DialogueChoiceDefinition` Resources for choices, and collect lines in a `DialogueDefinition` Resource. Add dialogue definitions to a `DialogueDatabase` Resource assigned to a `DialogueRunner` node.

`DialogueLineDefinition` fields:

- `line_id`: stable identifier used by scripts and save data.
- `speaker`: speaker name.
- `text`: line text.
- `tags`: optional grouping labels.
- `next_line_id`: next line for linear advance; empty = terminal.
- `choices`: array of `DialogueChoiceDefinition` Resources.
- `condition`: optional Godot Expression evaluated against dialogue variables.
- `on_enter` / `on_exit`: JSON-compatible event payloads.
- `apply_variables`: merged into dialogue variables when the line is entered.
- `default_data`: JSON-compatible runtime data.

`DialogueChoiceDefinition` fields:

- `choice_id`: stable identifier.
- `display_name`: human-readable label.
- `description`: optional descriptive text.
- `tags`: optional grouping labels.
- `next_line_id`: next line after selecting; empty = ends dialogue.
- `condition`: optional Godot Expression evaluated against dialogue variables.
- `on_select`: JSON-compatible event payload.
- `apply_variables`: merged into dialogue variables when selected.
- `default_data`: JSON-compatible runtime data.

`DialogueDefinition` fields:

- `dialogue_id`: stable identifier.
- `display_name`: human-readable label.
- `description`: optional descriptive text.
- `tags`: optional grouping labels.
- `lines`: array of `DialogueLineDefinition` Resources.
- `start_line_id`: first line when the dialogue starts.
- `default_variables`: initial dialogue variables.
- `default_data`: JSON-compatible runtime data.

## DialogueRunner API

Use these calls from project code:

- `start_dialogue(dialogue_id, data)`: begin a dialogue and enter its start line.
- `stop_dialogue(data)`: end the active dialogue.
- `get_current_line()`: snapshot of the current line.
- `get_choices()`: available choices for the current line (filtered by condition).
- `select_choice(choice_id, data)`: choose a path and advance.
- `advance(data)`: linear advance to next_line_id (only for lines without choices).
- `get_variable(key)` / `set_variable(key, value)` / `get_variables()`: read/write dialogue variables.
- `get_dialogue(dialogue_id)`: runtime snapshot of a dialogue.
- `get_state()` / `apply_state(data)`: export and restore runtime state.
- `save_state()` / `load_state(data)`: save-load compatible wrappers.

The runner emits `dialogue_started`, `dialogue_ended`, `line_entered`, `line_exited`, `choice_selected`, and `dialogues_changed`.

## Saving

Set `save_id` before the node enters the tree if you want the runner to join the `save_participants` group for `save_load` integration. `get_state()` returns schema version, active dialogue, current line, status, variables, and dialogue runtime data.

Keep variables, event payloads, and saved state JSON-compatible. Do not store Nodes, Resources, Callables, engine objects, or cyclic containers.

## Boundaries

This module does not directly integrate with inventory, stats, effects, abilities, quests, interaction, state machines, combat, UI, or AI. Use explicit project code to listen to runner signals and trigger consequences in those systems.

Conditions run Godot `Expression` against the dialogue `variables` dictionary only. Do not rely on globals, Autoloads, or scene tree access inside conditions.

## Validation

Run the installed module through Godot checks:

```sh
godot-playwright check-scripts /path/to/project res://addons/dialogue --exclude addons/godot_playwright/**
godot-playwright check-resources /path/to/project res://addons/dialogue --exclude addons/godot_playwright/**
```
