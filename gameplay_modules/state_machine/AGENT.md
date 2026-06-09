# Agent Instructions: state_machine

Use this module when a Godot project needs player state, enemy AI phases, UI modes, battle phases, skill lifecycles, quest stages, buff lifecycles, or any behavior that should have one active mode at a time.

Install with:

```sh
godot-playwright module add /path/to/project state_machine
```

Use `--demo` only when adding a demo scene and copied test is acceptable:

```sh
godot-playwright module add /path/to/project state_machine --demo
```

After installation, inspect `res://addons/state_machine/`. There is no Autoload.

## Wiring A State Machine

1. Add a `StateMachine` node under the gameplay object that owns the behavior.
2. Add direct child nodes for states such as `Idle`, `Move`, `Attack`, or `Dead`.
3. Attach state scripts that extend `res://addons/state_machine/state.gd` unless an existing script already follows the protocol.
4. Set explicit `state_id` values when external calls or save data should survive node renames.
5. Set `initial_state_id` and keep `auto_start = true` for ordinary scene-driven state machines.

Prefer lowercase stable IDs such as `idle`, `move`, `attack`, `dead`, `menu_open`, or `resolving_turn`.

## Transitions

Use `StateMachine.transition_to("state_id", data)` from owning scripts.

Use `request_transition("state_id", data)` from the active state. For example:

```gdscript
func request_attack() -> Dictionary:
    return get_parent().request_transition("attack", {"source": "move"})
```

Keep guards simple. Use `can_enter(previous_state, data)` and `can_exit(next_state)` for local conditions such as cooldowns, locks, or required resources. Do not create large transition tables in project code unless the game clearly needs a designer-authored graph.

## State Logic

Keep each state focused on one mode. Put long-lived domain data on the owning gameplay node, inventory module, save module, or another explicit component. Do not hide important game data inside temporary state nodes unless that data is easy to recreate.

Avoid repeated transitions from `enter()` or `exit()`. The module rejects reentrant transition requests with a structured error.

## Save Load

The module is usable without `save_load`. To persist the active state, explicitly join `save_participants` and wrap the state machine snapshot:

```gdscript
func save_state() -> Dictionary:
    return $StateMachine.get_state()


func load_state(data: Dictionary) -> void:
    $StateMachine.apply_state(data)
```

Do not automatically persist UI, enemy action, animation, or skill-resolution state machines unless the game design requires those transient states to survive loading.

## Validation Commands

Run targeted checks after installation:

```sh
godot-playwright check-scripts /path/to/project res://addons/state_machine --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/state_machine --exclude "addons/godot_playwright/**"
```

Run the copied demo test when `--demo` is installed:

```sh
godot-playwright test /path/to/project /path/to/project/tests/state_machine_demo --trace off
```
