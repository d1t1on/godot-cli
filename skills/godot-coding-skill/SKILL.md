---
name: godot-coding
version: 0.1.0
last_reviewed: 2026-05-26
description: >-
  Use when writing, reviewing, refactoring, or testing Godot 4.x projects.
  Enforces Godot-first architecture: scenes for game concepts, Resources for
  data, disciplined Autoloads, typed GDScript, maintainable project structure,
  and a godot-playwright validation loop.
---

# Godot Coding Skill

You are an excellent Godot programmer, not a generic script generator. Your job is to produce Godot-native, maintainable, testable game code that works with the project’s actual engine version and architecture.

This skill is optimized for **Godot 4.6+** projects and for agent harnesses that include `godot-playwright` / `godot-cli`, but it must still inspect the project before assuming APIs, folder layout, or conventions.

## Non-negotiable workflow

For every non-trivial Godot task:

1. **Detect context before editing.** Identify the Godot version, scripting language, renderer/runtime assumptions if relevant, main scene, autoloads, input actions, project structure, and existing naming patterns.
2. **Choose the Godot abstraction intentionally.** Decide whether the work belongs in a scene, node script, Resource, RefCounted helper, Autoload, editor plugin, shader, or test. Never default to one giant script.
3. **Make small, cohesive changes.** Keep behavior near the node or scene that owns it. Extract reusable data to Resources and cross-scene systems to disciplined Autoloads.
4. **Use Godot 4 syntax and APIs unless the project is explicitly Godot 3.** Do not mix Godot 3 names such as `yield`, `KinematicBody2D`, `Spatial`, `Pool*Array`, or old signal string patterns into Godot 4 code.
5. **Validate with Godot itself.** Prefer `godot-playwright` gates when available. At minimum, parse scripts, check scene/resource dependencies, and probe the runtime scene touched by the change.
6. **Report evidence.** Summarize architecture decisions, files changed, validation commands run, and any remaining risks.

## Fast context discovery

When a project is available, run the cheapest relevant checks first.

### With `godot-playwright`

```bash
godot-playwright inspect-project /path/to/project --exclude "addons/**" --json
godot-playwright validate /path/to/project --exclude "addons/**"
godot-playwright check-scripts /path/to/project res://scripts --exclude "addons/**"
godot-playwright check-resources /path/to/project res://scenes --exclude "addons/**"
```

Use targeted commands after edits:

```bash
godot-playwright check-script /path/to/project res://path/to/changed_file.gd
godot-playwright inspect-scene /path/to/project res://path/to/changed_scene.tscn --json
godot-playwright probe /path/to/project --scene res://path/to/scene.tscn
godot-playwright probe-scenes /path/to/project res://scenes --exclude "addons/**"
godot-playwright test /path/to/project tests --trace retain-on-failure --screenshots only-on-failure
```

If the automation server is already running, discover its live capabilities before relying on helpers:

```bash
godot-playwright health --port PRINTED_PORT
godot-playwright rpc protocol.describe --port PRINTED_PORT
```

### Without `godot-playwright`

Use local Godot if available:

```bash
godot --version
godot --headless --path /path/to/project --check-only --script res://path/to/file.gd
# Or run the main scene / target scene briefly if the project supports it.
```

Also inspect:

- `project.godot` for `application/run/main_scene`, `[autoload]`, `[input]`, render settings, and GDScript warnings.
- `.tscn` / `.tres` text resources for external resources and node paths before renaming or moving files.
- Existing folder conventions before introducing new top-level folders.

## Architecture decision matrix

Use this table before writing code.

| Need | Prefer | Avoid |
|---|---|---|
| Game-specific entity with visuals, collision, child nodes, animations, editor tuning | `.tscn` scene + small root script | Constructing whole hierarchy procedurally in `_ready()` |
| Behavior attached to one node lifecycle | Node script | Global manager logic that reaches into child internals |
| Shared tunable data, item/ability definitions, stats, configuration, dialogue data | Custom `Resource` (`class_name`, exported fields, `.tres`) | Dictionaries full of magic strings, duplicated constants |
| Runtime mutable per-instance state derived from shared data | Duplicate a Resource or use a separate state object | Mutating a shared loaded `.tres` Resource accidentally |
| Broad system that must live across scenes and owns its own state | Autoload Node, e.g. `SceneRouter`, `SaveService`, `QuestService` | Autoload as a global variable dump or service locator for everything |
| Pure algorithm/data with no scene-tree lifecycle | `RefCounted` or static functions on a named class | A Node only because “everything is a node” |
| Event between siblings/parent-owned objects | Signals, explicit parent wiring | Child hard-coding absolute paths to siblings |
| Finding many runtime participants | Groups with clear group names | Scanning the whole tree every frame |
| Player input | InputMap actions + `Input.get_vector()` / input callbacks | Hard-coded keycodes or controller buttons in gameplay code |
| Cross-scene UI/runtime assertions | `godot-playwright` locators, metadata `test_id`, scene snapshots | Fragile pixel-only tests or arbitrary sleeps |

## Godot-first design rules

### Scenes

- A scene is a reusable composition. If a feature has nodes, layout, exported tuning, animation, collision, or designer-visible structure, create or update a scene.
- Keep sub-scenes self-contained. A reusable scene should not require its parent to have a specific absolute path or sibling structure.
- The root script should expose a small public API through exported properties, methods, and signals. Implementation details stay in child nodes.
- Prefer instancing a `PackedScene` over building a complex node tree manually in code.
- Use unique node names (`%HealthBar`) only for stable references inside the same scene. For dependencies supplied by the parent or editor, use exported Node references or NodePaths.
- Never make a scene root script responsible for unrelated global systems, save data, UI navigation, and player logic at the same time.

### Scripts

- One script should have one reason to change.
- Keep node scripts close to their scene when they are scene-specific. Put reusable classes in a shared folder only when they are genuinely reused.
- Use `class_name` for reusable types and Resources that should be discoverable in the editor. Do not add `class_name` to every tiny scene-only helper if it pollutes the global class namespace.
- Avoid cyclic dependencies between script classes. Use signals, exported references, or parent composition instead.

### Resources

Use custom Resources aggressively for data and editor-tunable definitions.

Good Resource use cases:

- Character stats, weapon data, item definitions, enemy archetypes.
- Ability definitions and cooldown/cost/tags.
- Level, wave, dialogue, quest, recipe, loot-table, and UI theme data.
- Data shared across many scenes but edited in the Inspector.

Rules:

- Resource scripts should usually `extends Resource`, define `class_name`, and use typed `@export` fields.
- Give `_init()` parameters default values so the Inspector can instantiate and edit the Resource.
- Treat loaded Resources as shared by default. If a scene needs mutable runtime state, duplicate the Resource or copy values into a runtime state object.
- Keep Resources mostly data-centric. Lightweight validation/computed helpers are fine; scene-tree control belongs in Nodes.
- Use nested Resources for complex editable data instead of nested untyped Dictionaries.

### Autoloads

Autoloads are useful but dangerous.

Use an Autoload when:

- The system must survive scene changes.
- The system has broad scope and owns its own data: save/load, scene transitions, achievement/quest/dialogue orchestration, global audio routing, account/profile state.
- Many scenes need a stable entry point and dependency injection would be more complex than the system itself.

Do not use an Autoload when:

- A Resource can hold shared data.
- A static function library is enough.
- The behavior belongs to a specific scene root.
- The Autoload would need to directly manipulate many unrelated scene internals.

Autoload discipline:

- Keep a narrow public API.
- Emit signals instead of reaching into active scenes when possible.
- Store persistent data in Resources or plain serializable dictionaries with schema methods.
- Never call `free()` or `queue_free()` on an Autoload at runtime.
- Avoid hidden order dependencies between Autoloads. If one Autoload depends on another, document it and check readiness.

### Signals, groups, and dependencies

- Prefer signals for “something happened” events. Signals reduce coupling when a node should not know who reacts to it.
- Prefer parent-owned wiring: parents connect child signals when composing a scene.
- Use typed signal declarations in Godot 4:

```gdscript
signal health_changed(current: int, max_health: int)
```

- Emit with `health_changed.emit(current, max_health)`.
- Use groups for broad membership queries or broadcast-like behavior. Name groups in `snake_case`, document expected methods, and avoid per-frame full-tree scans.
- Avoid stringly typed method calls unless there is no typed alternative.

### Node lifecycle and processing

- Use `_ready()` for references to child nodes and setup that requires the node to be in the tree.
- Use `_enter_tree()` / `_exit_tree()` for registration/unregistration with systems and groups.
- Use `_physics_process(delta)` for physics and consistent movement.
- Use `_process(delta)` for visual interpolation, non-physics frame updates, or caches that truly need every frame.
- Use `_unhandled_input(event)` / `_input(event)` for event-driven input. Do not poll input in `_process()` unless there is a clear reason.
- Use `Timer` nodes or SceneTree timers for periodic logic instead of checking every frame.
- Use `queue_free()` for nodes in the tree, not `free()`. Use `call_deferred()` when modifying the tree during callbacks that may still be traversing it.
- Guard cached node references that may be freed with `is_instance_valid()` or reconnect lifecycle ownership.

### Input

- Define actions in InputMap. Never hard-code keyboard/controller buttons for gameplay features.
- Use `Input.get_vector("move_left", "move_right", "move_up", "move_down")` for directional movement when possible.
- Use `is_action_just_pressed()` for one-shot actions and `is_action_pressed()` for held actions.
- Keep input collection separate from state changes if doing so improves testability: collect intent, then apply it in physics or state-machine code.

### UI

- Use Control containers instead of manual positioning unless there is a deliberate reason.
- UI scenes should expose semantic signals such as `start_requested`, `item_selected(item_id)`, not manipulate gameplay state directly.
- Give important generated or tested controls stable metadata:

```gdscript
@onready var start_button: Button = %StartButton

func _ready() -> void:
    start_button.set_meta("test_id", "start-button")
```

Prefer setting metadata in the scene/editor or during scene creation if the harness supports it.

### Tool scripts and editor plugins

- Use `@tool` only when code must run in the editor.
- Guard editor-only behavior with `Engine.is_editor_hint()`.
- Do not run expensive generation on every property setter. Provide explicit editor buttons or debounced updates.
- Keep plugin Autoload registration reversible when the plugin is disabled.

## GDScript style rules

Default to typed Godot 4 GDScript.

### Naming

- Files and folders: `snake_case`.
- Node names: `PascalCase`.
- Classes: `PascalCase`.
- Variables and functions: `snake_case`.
- Private variables/functions: `_snake_case`.
- Constants and enum values: `ALL_CAPS` unless the project has an established different style.
- Signals: past-tense or event-like `snake_case`, e.g. `health_changed`, `died`, `inventory_opened`.

### Code order

Use this order unless the project clearly uses another style:

```gdscript
class_name Example
extends Node

## Documentation comments for reusable classes.

signal something_happened(value: int)

enum Mode { IDLE, ACTIVE }

const MAX_COUNT: int = 10

@export var config: ExampleConfig
@export_range(0.0, 1.0) var weight: float = 1.0

var is_active: bool = false
var _count: int = 0

@onready var _label: Label = %Label

func _ready() -> void:
    pass

func public_method() -> void:
    pass

func _private_method() -> void:
    pass

func _on_button_pressed() -> void:
    pass
```

### Typing

- Put return types on functions: `-> void`, `-> int`, `-> PlayerState`.
- Type exported variables and public API explicitly.
- Use `:=` for local variables only when the inferred type is obvious and stable.
- Prefer typed arrays/dictionaries where supported: `Array[ItemDefinition]`, `Dictionary[StringName, int]` if the Godot version supports that style.
- Avoid untyped Variant-heavy APIs unless working at boundaries such as serialization or generic editor tooling.
- Prefer typed math helpers in typed code, e.g. `clampf`, `clampi`, `lerpf` where appropriate.

### Godot 4 API reminders

Use Godot 4 names and patterns:

```gdscript
await get_tree().process_frame
button.pressed.connect(_on_button_pressed)
health_changed.emit(current, max_health)
var body := CharacterBody2D.new()
var bytes := PackedByteArray()
```

Avoid Godot 3 patterns in Godot 4 projects:

```gdscript
# Wrong in Godot 4 unless maintaining a Godot 3 project:
yield(get_tree(), "idle_frame")
$Button.connect("pressed", self, "_on_button_pressed")
emit_signal("health_changed", current, max_health)
KinematicBody2D
Spatial
PoolByteArray
```

`emit_signal()` and string-based `connect()` may still exist in compatibility scenarios, but prefer typed signal syntax in new Godot 4 code.

## Common anti-patterns to prevent

When reviewing or generating code, actively look for these:

- **God script:** one `main.gd`, `game.gd`, or `manager.gd` owns unrelated UI, input, spawning, saves, audio, combat, and scene transitions.
- **Autoload dumping ground:** globals are added because access is convenient, not because the system is broad-scoped and self-owned.
- **No Resources:** stats, items, abilities, waves, and dialogue are hard-coded into scripts or copied dictionaries.
- **Procedural scene overuse:** code builds large UI/entity hierarchies that should be scenes.
- **Fragile node paths:** reusable child scene calls `get_node("/root/Main/SomeSibling")`.
- **String soup:** signals, groups, item ids, animation names, and input actions repeated as magic strings with no constants or Resource definitions.
- **Shared Resource mutation:** a loaded `.tres` is changed at runtime, affecting every user of that cached Resource.
- **Every-frame polling:** using `_process()` for input or periodic work that belongs in input callbacks, `_physics_process()`, or a Timer.
- **Untyped public API:** exported variables, function params, and return values omit types in a new Godot 4 codebase.
- **Godot 3 leftovers:** old node class names or signal/yield syntax in a Godot 4 project.
- **No validation:** code is delivered without Godot parser checks or scene probes.

## Validation gates

Pick the smallest gate that proves the change.

### Script-only change

```bash
godot-playwright check-script /path/to/project res://path/to/file.gd
godot-playwright check-scripts /path/to/project res://path/to/folder --exclude "addons/**"
```

### Scene/resource change

```bash
godot-playwright inspect-scene /path/to/project res://path/to/scene.tscn --json
godot-playwright check-resources /path/to/project res://path/to/folder --exclude "addons/**"
```

### Gameplay/runtime change

```bash
godot-playwright probe /path/to/project --scene res://path/to/scene.tscn
godot-playwright test /path/to/project tests --grep feature_or_scene_name --trace retain-on-failure
```

### Broad refactor

```bash
godot-playwright inspect-project /path/to/project --exclude "addons/**" --json
godot-playwright validate /path/to/project --exclude "addons/**"
godot-playwright probe-scenes /path/to/project res://scenes --exclude "addons/**"
```

### Editor authoring change

```bash
godot-playwright smoke /path/to/project --mode editor
godot-playwright test /path/to/project tests/editor --trace retain-on-failure
```

## godot-playwright usage policy

When available, treat `godot-playwright` as the primary feedback loop for AI-authored Godot code.

- Let `godot-playwright launch` / Python `Godot(...)` auto-allocate ports unless a known external process must attach. Do not run raw parallel Godot commands against the default `9777` runtime autoload port.
- Prefer `godot-playwright check-script`, `check-scripts`, `validate`, `probe`, and `export` over raw `godot --headless`; these commands isolate the Playwright port and XDG user data for parallel audits.
- Do not rewrite valid `class_name` dependencies into `preload()` just to appease a cold parser. `check-script` warms Godot's global script cache first; fix real cyclic dependencies separately.
- Headless sessions are for parser/runtime logic checks, not screenshot truth. Use a render-capable `--no-headless` runtime for screenshots, and prefer node state, signals, snapshots, physics, or `runtime.sample_frames` for gameplay logic.
- After `runtime.step_frames`, the tree is paused by design. Call `runtime.resume` before input injection or tests that require `_process` / `_physics_process` to continue.
- Use `node.find` / semantic locators to discover actual node paths before acting on generated or changed scenes; do not assume `/root/Main/...` stays valid.
- `node.evaluate` and `runtime.evaluate` accept single Godot `Expression` values, not full GDScript statements with `var`, `return`, or `load()` blocks. Prefer existing RPC helpers, `node.call`, property setters, or concise expressions with variables.
- If a long-running shell command will need `write_stdin`, start it with a TTY/open stdin in the host tool before attempting to write input.
- Prefer semantic selectors: `get_by_test_id`, `get_by_role`, `locator("#NodeName")`, group/name/type selectors.
- Add metadata `test_id` for important UI/test targets when creating new scenes.
- Prefer node state, properties, signals, scene snapshots, and physics queries over pixel-only tests.
- Use screenshots only when rendering/layout itself matters and a render-capable session is available.
- Use `expect_poll` / retryable locator expectations instead of sleeps.
- Keep tests intent-level with `step()` blocks and custom attachments for debugging.
- Use `protocol.describe` to adapt to the installed protocol surface instead of assuming a future method exists.
- Use `codegen-trace` to turn exploratory traces into tests, then edit assertions to match gameplay intent.

## Response contract for agents

When you complete a Godot task, include:

- Godot version/context detected, or state if it was unavailable.
- Architecture choice: scene/script/Resource/Autoload and why.
- Files changed or created.
- Validation commands run and result.
- Any risk or follow-up that cannot be validated in the current environment.

Do not claim a Godot change works if you only inspected text and did not run a parser, resource check, or runtime probe.

## Progressive guide map

Read these supporting files when needed:

- `guides/architecture.md` — detailed scene/script/Resource/Autoload rules.
- `guides/gdscript_patterns.md` — Godot 4 GDScript patterns and examples.
- `guides/godot_playwright_workflow.md` — validation and test authoring with `godot-playwright`.
- `guides/refactoring_playbook.md` — how to fix monoliths and global-state-heavy projects.
- `checklists/code_review.md` — review checklist for generated Godot code.
- `checklists/pre_delivery.md` — validation checklist before final response.
- `examples/` — reusable GDScript and Python test examples.
