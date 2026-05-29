# Godot Architecture Guide

This guide teaches an AI agent how to choose the right Godot abstraction before writing code.

## Core principle

Godot architecture is a balance between declarative scene composition, imperative scripts, serialized Resources, and long-lived systems. Bad AI-generated Godot code usually fails because it treats Godot like a generic Python app: everything becomes one file, one singleton, or one procedural constructor.

A good Godot solution asks:

1. What owns this behavior?
2. What should designers be able to edit in the Inspector?
3. Does this need scene-tree lifecycle, rendering, physics, input, or UI layout?
4. Does this need to survive scene changes?
5. Does this data need to be shared, duplicated, saved, or referenced by many scenes?

## Scene vs script

### Use a scene when

- The concept is game-specific: player, enemy, projectile, inventory screen, pause menu, interactable door, level chunk.
- It has a node hierarchy, visuals, collision, animation, audio players, timers, or layout containers.
- Designers should edit it in the editor.
- It will be instanced in levels or other scenes.
- It has several child nodes whose relationships are part of the asset.

### Use a script-only class when

- The class is a reusable utility or component without a fixed child-node composition.
- It is a base class for multiple scenes.
- It represents a pure domain helper, state machine, algorithm, or plugin API.
- It should appear as a named type in the editor through `class_name`.

### Avoid

- Creating ten child nodes in `_ready()` when a `.tscn` would be clearer.
- Making scenes depend on absolute paths outside themselves.
- Putting all gameplay systems into a single root script.
- Adding `class_name` to every small scene script without considering global namespace pollution.

## Resources

Resources are central to good Godot code. They are serialized, Inspector-editable, referenceable, and lighter than Nodes.

### Use Resources for

- Stats and balancing data.
- Items, abilities, weapons, enemies, quests, dialogue, waves, recipes, loot tables.
- Editor-authored configuration.
- Shared definitions referenced by many scenes.
- Data that should be saved as `.tres` / `.res` files.

### Resource pattern

```gdscript
class_name AbilityDefinition
extends Resource

@export var id: StringName
@export var display_name: String = "Ability"
@export_multiline var description: String = ""
@export_range(0.0, 120.0, 0.1) var cooldown_seconds: float = 1.0
@export_range(0, 9999) var energy_cost: int = 0
@export var tags: Array[StringName] = []

func _init(
        p_id: StringName = &"",
        p_display_name: String = "Ability",
        p_cooldown_seconds: float = 1.0,
        p_energy_cost: int = 0) -> void:
    id = p_id
    display_name = p_display_name
    cooldown_seconds = p_cooldown_seconds
    energy_cost = p_energy_cost
```

### Runtime state from Resources

Definitions should often be immutable at runtime. If runtime code must mutate values, duplicate or copy the Resource.

```gdscript
class_name CharacterStatsRuntime
extends RefCounted

var max_health: int
var current_health: int
var move_speed: float

static func from_definition(definition: CharacterStats) -> CharacterStatsRuntime:
    var state := CharacterStatsRuntime.new()
    state.max_health = definition.max_health
    state.current_health = definition.max_health
    state.move_speed = definition.move_speed
    return state
```

Or, for a Resource that is safe to duplicate:

```gdscript
@export var base_stats: CharacterStats
var runtime_stats: CharacterStats

func _ready() -> void:
    assert(base_stats != null, "base_stats is required")
    runtime_stats = base_stats.duplicate(true) as CharacterStats
```

### Resource cautions

- Loaded Resources are cached by path. Multiple loads of the same path may return the same object reference.
- Mutating a shared `.tres` Resource can affect all nodes using it.
- Avoid storing live Node references inside Resources unless the Resource is explicitly runtime-only and not saved.
- Prefer typed exported fields over untyped Dictionaries.

## Autoloads

An Autoload is a long-lived node under `/root`. It is not a magical architecture solution.

### Good Autoloads

- `SceneRouter`: scene transitions and transition signals.
- `SaveService`: serialization and save slots.
- `AudioDirector`: global music/sfx buses, if it owns its players and does not poke arbitrary scenes.
- `QuestService`: broad quest state and events.
- `DialogueService`: active dialogue orchestration.
- `ProfileService`: account/settings/profile data.

### Bad Autoloads

- `Globals` with unrelated variables.
- `GameManager` that owns player input, UI, enemies, score, inventory, saving, and transitions.
- `EventBus` used to avoid real dependencies everywhere.
- A service that manipulates arbitrary scene internals through hard-coded paths.

### Autoload API pattern

```gdscript
class_name SaveService
extends Node

signal save_completed(slot: int)
signal save_failed(slot: int, message: String)

const SAVE_DIR := "user://saves"

var _current_profile: PlayerProfile

func set_profile(profile: PlayerProfile) -> void:
    _current_profile = profile

func save_game(slot: int) -> void:
    if _current_profile == null:
        save_failed.emit(slot, "No profile loaded")
        return

    var result := _write_profile(slot, _current_profile)
    if result == OK:
        save_completed.emit(slot)
    else:
        save_failed.emit(slot, error_string(result))

func _write_profile(slot: int, profile: PlayerProfile) -> Error:
    # Implementation detail.
    return OK
```

Autoload callers should use its public methods and signals; they should not mutate private fields or assume implementation nodes exist.

## Node composition

### Parent owns composition

A scene parent should wire child dependencies.

```gdscript
class_name PlayerHud
extends Control

signal pause_requested

@onready var _pause_button: Button = %PauseButton
@onready var _health_bar: ProgressBar = %HealthBar

func _ready() -> void:
    _pause_button.pressed.connect(_on_pause_button_pressed)

func _on_pause_button_pressed() -> void:
    pause_requested.emit()

func set_health(current: int, max_health: int) -> void:
    _health_bar.max_value = max_health
    _health_bar.value = current
```

```gdscript
class_name GameplayRoot
extends Node

@onready var _player: Player = %Player
@onready var _hud: PlayerHud = %PlayerHud

func _ready() -> void:
    _player.health_changed.connect(_hud.set_health)
    _hud.pause_requested.connect(_on_pause_requested)
```

The HUD does not know where the player lives. The player does not know where the HUD lives.

### Exported dependencies

For reusable scenes, export dependencies supplied by the editor or parent.

```gdscript
class_name Door
extends Area2D

@export var target_scene: PackedScene
@export var required_item: ItemDefinition

func interact(actor: Node) -> void:
    if required_item != null and not actor.has_item(required_item.id):
        return
    opened.emit(target_scene)
```

## Signals vs groups vs direct references

### Direct references are fine when

- Parent owns child.
- Child is a required internal implementation detail.
- The node path is within the same scene and stable.

### Signals are better when

- The sender should not know who reacts.
- A reusable child reports events to its parent.
- UI reports intent to gameplay.
- Multiple listeners may respond.

### Groups are better when

- Many nodes share a capability.
- Membership changes dynamically.
- You need queries like all enemies, interactables, save participants.

Use groups sparingly in performance-critical code. Cache membership when needed and update it on enter/exit tree.

## State machines

Prefer a state machine when behavior has mutually exclusive states with clear transitions.

For simple state, an enum is enough:

```gdscript
enum State { IDLE, CHASE, ATTACK, STUNNED }

var _state: State = State.IDLE

func _set_state(next: State) -> void:
    if _state == next:
        return
    _exit_state(_state)
    _state = next
    _enter_state(_state)
```

For complex states, use child nodes or RefCounted state objects. Do not create a giant `match` that owns every behavior of a complex enemy if separate states would be clearer.

## File organization

Prefer feature folders for game-specific scenes and data:

```text
res://
  project.godot
  addons/
  autoload/
    scene_router.gd
    save_service.gd
  shared/
    math/
    ui/
  features/
    player/
      player.tscn
      player.gd
      player_stats.tres
    enemies/
      slime/
        slime.tscn
        slime.gd
        slime_stats.tres
    inventory/
      inventory_screen.tscn
      inventory_screen.gd
      item_definition.gd
      items/
  levels/
    forest/forest_01.tscn
  tests/
```

Adapt to the existing project. Do not reorganize a large project without a migration plan and dependency checks.

## Refactor priorities

When improving AI-generated Godot code:

1. Extract data constants into Resources.
2. Split unrelated behavior out of monolithic scripts.
3. Move complex procedurally created node trees into scenes.
4. Replace hard-coded absolute paths with exported references, parent wiring, signals, or groups.
5. Introduce typed APIs and return types.
6. Add validation tests using `godot-playwright`.
