# GDScript 4.x Patterns

Use this guide when generating or reviewing GDScript for Godot 4.x.

## Default script template

```gdscript
class_name ExampleComponent
extends Node

signal activated(source: Node)

const DEFAULT_LIMIT: int = 10

@export var enabled: bool = true
@export_range(0, 100) var limit: int = DEFAULT_LIMIT

var is_active: bool = false
var _count: int = 0

@onready var _timer: Timer = %Timer

func _ready() -> void:
    _timer.timeout.connect(_on_timer_timeout)

func activate(source: Node) -> void:
    if not enabled or is_active:
        return
    is_active = true
    activated.emit(source)

func deactivate() -> void:
    is_active = false

func _on_timer_timeout() -> void:
    if is_active:
        _count += 1
```

## Godot 4 syntax checklist

Use:

```gdscript
await get_tree().process_frame
button.pressed.connect(_on_button_pressed)
button.pressed.disconnect(_on_button_pressed)
some_signal.emit(value)
var player := body as Player
if player == null:
    return
```

Avoid Godot 3 patterns in Godot 4 projects:

```gdscript
yield(get_tree(), "idle_frame")
$Button.connect("pressed", self, "_on_button_pressed")
emit_signal("some_signal", value)
KinematicBody2D
Spatial
PoolVector2Array
```

## Typed exports

```gdscript
@export var stats: CharacterStats
@export var target_scene: PackedScene
@export_file("*.json") var dialogue_path: String
@export_dir var save_directory: String = "user://saves"
@export_range(0.0, 1.0, 0.01) var volume: float = 1.0
@export_enum("Easy", "Normal", "Hard") var difficulty: String = "Normal"
@export_flags("Fire", "Ice", "Poison") var elemental_flags: int = 0
@export_multiline var description: String = ""
```

Prefer semantic types over generic `Resource` when you control the class:

```gdscript
@export var ability: AbilityDefinition
```

## Safe child references

For required child nodes inside the same scene:

```gdscript
@onready var _health_bar: ProgressBar = %HealthBar
```

For optional child nodes:

```gdscript
@onready var _tooltip: Label = get_node_or_null("%Tooltip") as Label
```

For parent-supplied dependencies:

```gdscript
@export var inventory_path: NodePath
@onready var _inventory: Inventory = get_node_or_null(inventory_path) as Inventory

func _ready() -> void:
    assert(_inventory != null, "Inventory path must point to an Inventory node")
```

Avoid absolute paths inside reusable scenes:

```gdscript
# Bad for reusable scenes:
@onready var player = get_node("/root/Main/Player")
```

## Signals

Typed signal declaration:

```gdscript
signal item_selected(item: ItemDefinition)
signal closed
```

Connect once:

```gdscript
func _ready() -> void:
    if not item_selected.is_connected(_on_item_selected):
        item_selected.connect(_on_item_selected)
```

Parent wires child:

```gdscript
func _ready() -> void:
    %InventoryScreen.item_selected.connect(_player_inventory.equip)
```

For UI intent signals, prefer a named handler when the action has meaning:

```gdscript
func _ready() -> void:
    %StartButton.pressed.connect(_on_start_button_pressed)

func _on_start_button_pressed() -> void:
    start_requested.emit()
```

## Input

Movement intent:

```gdscript
func get_move_vector() -> Vector2:
    return Input.get_vector("move_left", "move_right", "move_up", "move_down")
```

Use physics for movement:

```gdscript
class_name Player
extends CharacterBody2D

@export var speed: float = 220.0

func _physics_process(_delta: float) -> void:
    var direction := Input.get_vector("move_left", "move_right", "move_up", "move_down")
    velocity = direction * speed
    move_and_slide()
```

Event-driven action:

```gdscript
func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed("interact"):
        interact_requested.emit()
        get_viewport().set_input_as_handled()
```

## Resource-backed gameplay

Definition Resource:

```gdscript
class_name WeaponDefinition
extends Resource

@export var id: StringName
@export var display_name: String = "Weapon"
@export_range(0, 9999) var damage: int = 1
@export_range(0.0, 30.0, 0.05) var cooldown: float = 0.5
@export var projectile_scene: PackedScene

func _init(
        p_id: StringName = &"",
        p_display_name: String = "Weapon",
        p_damage: int = 1,
        p_cooldown: float = 0.5) -> void:
    id = p_id
    display_name = p_display_name
    damage = p_damage
    cooldown = p_cooldown
```

Runtime user:

```gdscript
class_name WeaponSlot
extends Node2D

signal fired(weapon: WeaponDefinition)

@export var weapon: WeaponDefinition
@onready var _cooldown_timer: Timer = %CooldownTimer

func can_fire() -> bool:
    return weapon != null and _cooldown_timer.is_stopped()

func fire(origin: Node2D, direction: Vector2) -> void:
    if not can_fire():
        return

    var projectile := weapon.projectile_scene.instantiate() as Node2D
    projectile.global_position = origin.global_position
    projectile.rotation = direction.angle()
    get_tree().current_scene.add_child(projectile)

    _cooldown_timer.start(weapon.cooldown)
    fired.emit(weapon)
```

## Scene transition Autoload

```gdscript
class_name SceneRouter
extends Node

signal transition_started(path: String)
signal transition_failed(path: String, message: String)
signal transition_finished(path: String)

var _busy: bool = false

func goto_scene(path: String) -> void:
    if _busy:
        return
    if not path.begins_with("res://"):
        transition_failed.emit(path, "Only res:// scene paths are allowed")
        return

    _busy = true
    transition_started.emit(path)

    await get_tree().process_frame
    var error := get_tree().change_scene_to_file(path)
    if error != OK:
        _busy = false
        transition_failed.emit(path, error_string(error))
        return

    await get_tree().process_frame
    _busy = false
    transition_finished.emit(path)
```

Keep transition visuals in a scene, and let the Autoload own only the routing flow or broad transition orchestration.

## Save participant group pattern

Participants expose a method; the save system queries the group when saving.

```gdscript
# In a node that has state to save.
func _enter_tree() -> void:
    add_to_group(&"save_participants")

func _exit_tree() -> void:
    remove_from_group(&"save_participants")

func collect_save_data() -> Dictionary:
    return {
        "path": get_path(),
        "position": [global_position.x, global_position.y],
    }
```

```gdscript
# In SaveService autoload.
func collect_world_state() -> Array[Dictionary]:
    var rows: Array[Dictionary] = []
    for node in get_tree().get_nodes_in_group(&"save_participants"):
        if node.has_method("collect_save_data"):
            rows.append(node.collect_save_data())
    return rows
```

Do not call this every frame. Save/load is a deliberate operation.

## UI semantic intent pattern

```gdscript
class_name PauseMenu
extends Control

signal resume_requested
signal settings_requested
signal quit_requested

@onready var _resume_button: Button = %ResumeButton
@onready var _settings_button: Button = %SettingsButton
@onready var _quit_button: Button = %QuitButton

func _ready() -> void:
    _resume_button.set_meta("test_id", "pause-resume")
    _settings_button.set_meta("test_id", "pause-settings")
    _quit_button.set_meta("test_id", "pause-quit")

    _resume_button.pressed.connect(_on_resume_button_pressed)
    _settings_button.pressed.connect(_on_settings_button_pressed)
    _quit_button.pressed.connect(_on_quit_button_pressed)

func _on_resume_button_pressed() -> void:
    resume_requested.emit()

func _on_settings_button_pressed() -> void:
    settings_requested.emit()

func _on_quit_button_pressed() -> void:
    quit_requested.emit()
```

The pause menu emits intent. The gameplay/root/controller scene decides what those requests mean.

## Error handling

Use `assert()` for required editor-wired dependencies during development:

```gdscript
func _ready() -> void:
    assert(stats != null, "Stats Resource is required")
```

Use user-facing or recoverable errors for runtime data:

```gdscript
func load_item(path: String) -> ItemDefinition:
    var item := load(path) as ItemDefinition
    if item == null:
        push_error("Could not load ItemDefinition: %s" % path)
    return item
```

## Performance habits

- Do not scan the scene tree every frame.
- Cache required child references in `@onready` variables.
- Prefer event-driven updates over polling.
- Use `Packed*Array` for large numeric arrays.
- Avoid allocating in tight `_process` / `_physics_process` loops unless necessary.
- Use object pools only when profiling or project constraints justify them; do not add pooling complexity preemptively.

## Testing hooks

When creating new UI or gameplay scenes, add stable identifiers that automation can query.

```gdscript
func _ready() -> void:
    set_meta("test_id", "inventory-screen")
    %CloseButton.set_meta("test_id", "inventory-close")
```

Do not expose internal test-only APIs in shipping gameplay code unless the project already has a debug/test boundary. Prefer metadata, signals, and public gameplay API.
