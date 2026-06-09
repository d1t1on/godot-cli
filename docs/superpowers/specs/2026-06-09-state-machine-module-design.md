# State Machine Gameplay Module Design

Date: 2026-06-09

## Context

`godot-playwright` now has a reusable gameplay module installer and a first shipped module, `save_load`, for JSON slot persistence. An `inventory` module is being developed in a separate worktree. The next parallel module should be more foundational than `buff`: a lightweight `state_machine` module that later systems can build on for player control, enemy AI, UI flows, battle phases, skill lifecycles, quests, buffs, and other gameplay modes.

This design adds `state_machine` as an installable gameplay module. It follows the existing module style: low-intrusion installation, Godot-native scripts, structured results for expected failures, a small demo, copied demo tests, and agent-focused documentation.

## Goals

- Add `state_machine` as an installable gameplay module.
- Provide a generic node-based finite state machine that does not assume player, enemy, AI, animation, quest, or buff semantics.
- Make state setup natural in Godot scenes by using a `StateMachine` node with child state nodes.
- Provide a recommended `State` base class while allowing protocol-based integration for existing nodes.
- Support explicit external transitions and transitions requested from the current state.
- Support common lifecycle callbacks: enter, exit, process update, physics update, and input handling.
- Support optional transition guards through `can_enter()` and `can_exit()`.
- Support state snapshots through `get_state()` and `apply_state(data)` without automatically joining `save_load` persistence.
- Include a deterministic demo scene and copied Python test so agents can validate installation and behavior.
- Provide human and agent documentation for common usage patterns and validation.

## Non-Goals

- Do not build a behavior tree system.
- Do not build a visual state-machine editor.
- Do not provide character, enemy, animation, quest, buff, or UI-specific states in the core module.
- Do not implement full Resource-driven transition graphs in the MVP.
- Do not implement a state stack, push/pop transitions, or full hierarchical state machines in the MVP.
- Do not automatically register an Autoload.
- Do not automatically join `save_load` save groups.
- Do not persist private state-node internals in the MVP state snapshot.

## Chosen Approach

Use a node-component state machine with protocol-compatible state nodes.

Installation uses the existing module CLI:

```sh
godot-playwright module add <project> state_machine
godot-playwright module add <project> state_machine --demo
```

The module copies `res://addons/state_machine/` into the target project. It does not register an Autoload. A game adds a `StateMachine` node wherever stateful behavior is needed, then adds child nodes such as `Idle`, `Move`, `Attack`, or `Dead` as states.

This approach is preferred over a pure duck-typed helper because the `State` base class gives agents and users a clear template. It is also preferred over a Resource-driven state graph because the first version should be easy to inspect in the scene tree, easy for AI agents to generate, and simple to debug.

## Repository Layout

Add a new module tree:

```text
gameplay_modules/state_machine/
  module.json
  README.md
  AGENT.md
  addons/state_machine/
    state_machine.gd
    state.gd
    state_machine_result.gd
    state_machine_constants.gd
  demo/
    scenes/
    scripts/
  tests/
```

As with existing gameplay modules, package fallback copies should be kept byte-identical under:

```text
godot_playwright/bundled_gameplay_modules/state_machine/
```

`module.json` describes the base copy operation and demo copy operation. The module has no Autoload entries.

## Module Manifest

The manifest should follow the existing schema:

```json
{
  "name": "state_machine",
  "version": "0.1.0",
  "display_name": "State Machine",
  "description": "Node-based finite state machine component for Godot projects.",
  "godot_version": ">=4.6",
  "copy": [
    {"from": "addons/state_machine", "to": "addons/state_machine"}
  ],
  "autoloads": [],
  "demo": {
    "copy": [
      {"from": "demo/scenes", "to": "scenes/state_machine_demo"},
      {"from": "demo/scripts", "to": "scripts/state_machine_demo"},
      {"from": "tests", "to": "tests/state_machine_demo"}
    ]
  },
  "validation": {
    "commands": [
      "godot-playwright check-scripts /path/to/project res://addons/state_machine --exclude addons/godot_playwright/**",
      "godot-playwright check-resources /path/to/project res://addons/state_machine --exclude addons/godot_playwright/**"
    ]
  }
}
```

## Runtime Components

`state_machine.gd` defines `class_name StateMachine` and extends `Node`. It owns state discovery, current-state tracking, startup, transitions, lifecycle forwarding, structured transition results, signals, and state snapshot import/export.

`state.gd` defines `class_name State` and extends `Node`. It is the recommended base class for new state scripts. It provides an exported optional `state_id`, a `get_state_id()` helper that returns the explicit ID when set, and no-op lifecycle methods so generated state scripts can override only what they need.

`state_machine_result.gd` holds structured result helpers so expected failures return dictionaries instead of throwing exceptions.

`state_machine_constants.gd` holds schema version, module version, and any shared names.

## StateMachine API

The initial public API on `StateMachine` is:

```gdscript
func start(initial_state_id: String = "", data: Dictionary = {}) -> Dictionary
func transition_to(state_id: String, data: Dictionary = {}) -> Dictionary
func request_transition(state_id: String, data: Dictionary = {}) -> Dictionary
func get_current_state_id() -> String
func get_current_state() -> Node
func has_state(state_id: String) -> bool
func get_state_ids() -> Array[String]
func get_state() -> Dictionary
func apply_state(data: Dictionary) -> Dictionary
```

`transition_to()` is for external scripts. `request_transition()` is for the current state to request a transition through the same validation and transition path. The separate method names keep call sites clear without creating separate behavior.

Expected failures return structured dictionaries:

```gdscript
{
  "ok": false,
  "from": "Idle",
  "to": "Attack",
  "warnings": [],
  "errors": ["State cannot enter: Attack"]
}
```

The result shape should include enough context for tests and agents to diagnose failures. Successful transitions return `ok: true`, the previous state ID, the target state ID, warnings, and errors.

## State Lifecycle API

State nodes may implement these methods:

```gdscript
func enter(previous_state: Node, data: Dictionary) -> void
func exit(next_state: Node) -> void
func update(delta: float) -> void
func physics_update(delta: float) -> void
func handle_input(event: InputEvent) -> void
func can_enter(previous_state: Node, data: Dictionary) -> bool
func can_exit(next_state: Node) -> bool
```

The `State` base class should provide these methods with safe defaults. Protocol-based state nodes do not have to inherit from `State`; `StateMachine` should call a method only when it exists. Missing guards default to allowing the transition.

## Signals

`StateMachine` should expose:

```gdscript
signal state_changed(previous_state_id: String, current_state_id: String, data: Dictionary)
signal transition_failed(from_state_id: String, to_state_id: String, result: Dictionary)
```

`state_changed` is emitted after the current state has changed and the target state's `enter()` has run. `transition_failed` is emitted for expected transition failures such as unknown targets, rejected guards, or invalid startup.

## State Discovery And IDs

`StateMachine` scans direct child nodes as candidate states during `_ready()` or startup initialization. Every direct child node is treated as a state candidate; helper nodes should live inside a state node or outside the `StateMachine`. Nested state machines are allowed by composition, but child states of nested machines are not flattened into the parent.

State ID resolution order:

- Use `get_state_id()` if the child has the method and it returns a non-empty value.
- Otherwise use a non-empty `state_id` property if present.
- Otherwise use the child node name.

Duplicate state IDs are initialization errors. A state machine with duplicate IDs must not auto-start because nondeterministic state selection would create hard-to-debug behavior.

## Startup Rules

`StateMachine` should expose exported configuration:

```gdscript
@export var initial_state_id: StringName
@export var auto_start: bool = true
```

Startup rules:

- If `auto_start` is true, `_ready()` calls `start(initial_state_id)`.
- If `initial_state_id` is empty, startup uses the first discovered valid state.
- `start()` can only move from the not-started state into the first active state.
- Once started, callers should use `transition_to()` instead of `start()`.
- Startup with no valid states returns `ok: false` and emits `transition_failed`.

## Transition Rules

Transition order:

1. Ensure the target state exists.
2. Ensure the state machine has started when using `transition_to()` or `request_transition()`.
3. Check the current state's `can_exit(next_state)` if implemented.
4. Check the target state's `can_enter(previous_state, data)` if implemented.
5. Call the current state's `exit(next_state)` if implemented.
6. Update the current state reference and current state ID.
7. Call the target state's `enter(previous_state, data)` if implemented.
8. Emit `state_changed(previous_state_id, current_state_id, data)`.
9. Return a structured success result.

Only the current state receives `update(delta)`, `physics_update(delta)`, and `handle_input(event)` forwarding.

If the current state node is freed or becomes invalid, the module should report an error rather than guessing a fallback state. Automatic fallback could hide lifecycle bugs in generated gameplay code.

States may call `request_transition()` from their own logic. The MVP does not need a complex transition queue. If a transition is already in progress, another transition request should fail with a structured error instead of being queued or executed reentrantly. Documentation should advise users to request transitions from state methods such as `update()`, `physics_update()`, input handlers, or explicit state methods rather than repeatedly transitioning from `enter()` or `exit()`.

## State Snapshot Format

`get_state()` returns JSON-compatible data:

```json
{
  "schema_version": 1,
  "current_state_id": "Idle",
  "started": true
}
```

`apply_state(data)` validates the schema, `started` value, and target state ID. If `started` is true, it transitions or starts into `current_state_id` through normal guard checks. If `started` is false and the state machine has not started yet, it returns success and leaves the machine unstarted. If `started` is false after the machine has already started, it returns `ok: false` because the MVP has no stop/reset API. Invalid state data returns `ok: false` and does not partially mutate the state machine.

The MVP snapshot stores only the state machine's active state, not private variables inside individual state nodes. Games that need richer persistence should save that data in the owning gameplay node or in domain modules.

## Optional Save Load Integration

The module must be usable without `save_load`. It exposes `get_state()` and `apply_state(data)` as the persistence boundary.

For projects using `save_load`, a game can persist a state machine by explicitly joining the `save_participants` group and exposing save/load wrappers, for example:

```gdscript
func save_state() -> Dictionary:
    return $StateMachine.get_state()

func load_state(data: Dictionary) -> void:
    $StateMachine.apply_state(data)
```

The module should not auto-register every state machine as a save participant. Many state machines are temporary or local to UI, enemy behavior, skill resolution, or animation flow and should not be persisted by default.

## Demo

`--demo` installs a small runtime scene with one state machine and three states:

- `Idle`
- `Move`
- `Attack`

The demo root script exposes:

```gdscript
func run_state_machine_demo() -> Dictionary
```

The demo should validate:

- Auto-start enters the initial state.
- External `transition_to("Move")` succeeds.
- The current state can request `request_transition("Attack")`.
- A guard rejects one invalid transition and returns a structured error.
- `get_state()` and `apply_state()` restore the current state.
- Transition history or emitted-signal evidence proves the expected order.

The copied Python demo test should load the scene through `godot-playwright`, call `run_state_machine_demo()`, and assert a structured success result.

## CLI And Installer Behavior

The existing `godot-playwright module list` should show `state_machine` once this module is present.

`godot-playwright module add <project> state_machine` should copy only the base module files and use existing safe installer behavior:

- Refuse to overwrite files by default.
- Allow `--force` only for module-owned paths.
- Reject duplicate planned targets.
- Avoid symlink target overwrites.
- Return a clear installation report.
- Add no Autoload entries.

`godot-playwright module add <project> state_machine --demo` should also copy demo scenes, demo scripts, and copied tests into module-specific paths such as:

```text
res://scenes/state_machine_demo/
res://scripts/state_machine_demo/
tests/state_machine_demo/
```

## Documentation

`README.md` should explain:

- How to install the module.
- How to add a `StateMachine` node and child states to a scene.
- How state IDs are resolved.
- How to call `start()`, `transition_to()`, and `request_transition()`.
- How lifecycle callbacks and guards work.
- How to snapshot and restore the current state.
- How to validate the module after installation.

`AGENT.md` should give operational instructions:

- Use this module when a game needs player state, enemy AI phases, UI modes, battle phases, skill lifecycles, quest stages, or buff lifecycles.
- Prefer short stable state IDs such as `idle`, `move`, `attack`, `dead`, `menu_open`, or `resolving_turn`.
- Use explicit `state_id` values when persistence or external calls should survive node renames.
- Keep state logic focused; put domain data on the owning gameplay node or relevant module.
- Prefer explicit transitions and simple guards before inventing large transition tables.
- Validate with targeted script/resource checks and the copied demo test.

## Testing Strategy

Python tests should cover:

- Module discovery lists `state_machine` with version `0.1.0`.
- `module add state_machine` copies base files and does not add Autoloads.
- `module add state_machine --demo` copies demo files and copied tests.
- Package fallback data contains the bundled state-machine module.
- Source and bundled module trees stay byte-identical.
- `pyproject.toml` includes bundled state-machine package data.
- Existing installer safety behavior still applies to the new module.

Godot validation should cover when Godot is available:

- State-machine module scripts pass Godot parser checks.
- Demo scene/resource dependencies are valid.
- Demo runtime method validates auto-start, external transition, state-requested transition, guard rejection, snapshot restore, and transition history evidence.

If Godot is unavailable, Python installer tests still provide coverage, and final reporting must state that live Godot validation was skipped.

## Future Extensions

- State stack support for pause menus, overlays, and temporary interrupts.
- Resource-driven state graph definitions for projects that want designer-authored transition tables.
- Hierarchical state machines with parent/child transition behavior.
- AnimationPlayer or AnimationTree integration helpers.
- Debug inspector output for current state, available states, and recent transition history.
- Optional helpers for common gameplay domains such as character movement, AI combat phases, buff lifecycles, and turn phases.
