# State Machine Gameplay Module

`state_machine` adds a small node-based finite state machine for Godot 4.6+ projects.

Install into a Godot project:

```sh
godot-playwright module add /path/to/project state_machine
```

Install the demo scene and copied demo test:

```sh
godot-playwright module add /path/to/project state_machine --demo
```

The installer copies `res://addons/state_machine/`. It does not register an Autoload.

## Scene Structure

Add a `StateMachine` node where behavior needs a current state, then add direct child nodes as states:

```text
Player
  StateMachine
    Idle
    Move
    Attack
```

Each direct child is treated as a state candidate. Put helper nodes inside a state node or outside the `StateMachine`.

## State IDs

State IDs resolve in this order:

- `get_state_id()` if implemented and non-empty.
- Exported `state_id` if present and non-empty.
- Child node name.

Use explicit `state_id` values when save data or external scripts should survive node renames.

## API

```gdscript
StateMachine.start(initial_state_id: String = "", data: Dictionary = {}) -> Dictionary
StateMachine.transition_to(state_id: String, data: Dictionary = {}) -> Dictionary
StateMachine.request_transition(state_id: String, data: Dictionary = {}) -> Dictionary
StateMachine.get_current_state_id() -> String
StateMachine.get_current_state() -> Node
StateMachine.has_state(state_id: String) -> bool
StateMachine.get_state_ids() -> Array[String]
StateMachine.get_state() -> Dictionary
StateMachine.apply_state(data: Dictionary) -> Dictionary
```

Use `transition_to()` from owning gameplay scripts. Use `request_transition()` from inside the current state.

Expected failures return structured dictionaries instead of exceptions:

```gdscript
{
    "ok": false,
    "from": "idle",
    "to": "attack",
    "warnings": [],
    "errors": ["State cannot enter: attack"]
}
```

## State Lifecycle

New states can extend the provided base class:

```gdscript
extends "res://addons/state_machine/state.gd"


func enter(previous_state: Node, data: Dictionary) -> void:
    pass


func update(delta: float) -> void:
    pass
```

State nodes may implement:

```gdscript
func enter(previous_state: Node, data: Dictionary) -> void
func exit(next_state: Node) -> void
func update(delta: float) -> void
func physics_update(delta: float) -> void
func handle_input(event: InputEvent) -> void
func can_enter(previous_state: Node, data: Dictionary) -> bool
func can_exit(next_state: Node) -> bool
```

Missing lifecycle methods are ignored. Missing guards allow the transition.

## Save State

`get_state()` returns JSON-compatible data:

```json
{
  "schema_version": 1,
  "current_state_id": "idle",
  "started": true
}
```

The module does not automatically join `save_load`. To persist a state machine, explicitly add the owning node or the `StateMachine` node to `save_participants` and call `get_state()` / `apply_state(data)` from save/load wrappers.

## Validation

```sh
godot-playwright check-scripts /path/to/project res://addons/state_machine --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/state_machine --exclude "addons/godot_playwright/**"
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```
