# Godot Refactoring Playbook

Use this playbook to improve bad or AI-generated Godot code without breaking the project.

## First rule: preserve behavior with validation

Before refactoring:

```bash
godot-playwright inspect-project /path/to/project --exclude "addons/**" --json
godot-playwright validate /path/to/project --exclude "addons/**"
```

If validation already fails, record the existing failures so you do not claim you introduced or fixed unrelated issues.

## Smell: one giant script

Symptoms:

- A root script handles input, player movement, enemy spawning, UI, score, save/load, audio, and scene transitions.
- Many `@onready` references into unrelated scene branches.
- Huge `_process()` or `_physics_process()`.
- Many booleans representing unrelated states.

Refactor steps:

1. Identify cohesive responsibilities.
2. Move UI behavior into UI scene scripts.
3. Move data to Resources.
4. Move long-lived systems to disciplined Autoloads only if they must survive scene changes.
5. Connect pieces through signals at the parent/root scene.
6. Add tests around public behavior before changing internals.

Example split:

```text
Before:
  main.gd
    player movement
    health
    inventory UI
    save/load
    music
    scene change

After:
  features/player/player.gd
  features/player/health.gd
  features/inventory/inventory_model.gd
  features/inventory/inventory_screen.gd
  autoload/save_service.gd
  autoload/scene_router.gd
  autoload/audio_director.gd
  levels/gameplay_root.gd  # wires signals together
```

## Smell: global state dump

Symptoms:

```gdscript
# Globals.gd
var player
var enemies = []
var score = 0
var current_level = ""
var selected_item = null
var music_player
var paused = false
```

Refactor direction:

- Keep persistent profile/save data in a `Resource` or serializable model.
- Keep scene-specific state on the scene root.
- Keep runtime participants in groups or parent-owned lists.
- Split real services into separate Autoloads with narrow APIs.

Better:

```text
ProfileService: current profile, settings, save slot metadata
SceneRouter: scene transitions only
AudioDirector: global music/sfx routing only
GameplayRoot: active player/enemies/hud for the current scene
```

## Smell: dictionaries for everything

Symptoms:

```gdscript
var weapons = {
    "sword": {"damage": 10, "cooldown": 0.5, "icon": "res://..."},
    "bow": {"damage": 6, "cooldown": 0.8, "icon": "res://..."},
}
```

Refactor to Resources:

```gdscript
class_name WeaponDefinition
extends Resource

@export var id: StringName
@export var damage: int = 1
@export var cooldown: float = 0.5
@export var icon: Texture2D
```

Then create `.tres` files and reference them from scenes or registries.

Use a dictionary only as an index:

```gdscript
var _weapons_by_id: Dictionary[StringName, WeaponDefinition] = {}
```

## Smell: hard-coded absolute NodePaths

Symptoms:

```gdscript
get_node("/root/Main/Player/Hud/HealthBar").value = health
```

Refactor options:

- If same scene: use `%HealthBar` or an exported Node reference.
- If parent/child: parent wires references.
- If event: emit a signal and let parent/HUD listen.
- If many participants: use groups.
- If broad system: expose a method on a disciplined Autoload, not arbitrary tree poking.

Better:

```gdscript
signal health_changed(current: int, max_health: int)

func apply_damage(amount: int) -> void:
    current_health = maxi(current_health - amount, 0)
    health_changed.emit(current_health, max_health)
```

Parent scene:

```gdscript
func _ready() -> void:
    %Player.health_changed.connect(%Hud.set_health)
```

## Smell: procedural UI construction

Symptoms:

- Large `_ready()` creates Containers, Labels, Buttons, and connections.
- Layout is hard to inspect visually.
- Tests depend on generated names that change.

Refactor direction:

- Create a `.tscn` for the UI layout.
- Use exported properties or methods to inject data.
- Use metadata `test_id` for important controls.
- Keep dynamic list rows as a reusable row scene.

Row scene pattern:

```gdscript
class_name InventoryRow
extends HBoxContainer

signal selected(item: ItemDefinition)

var _item: ItemDefinition

@onready var _name_label: Label = %NameLabel
@onready var _select_button: Button = %SelectButton

func _ready() -> void:
    _select_button.pressed.connect(func() -> void: selected.emit(_item))

func bind(item: ItemDefinition) -> void:
    _item = item
    _name_label.text = item.display_name
    set_meta("test_id", "inventory-row-%s" % item.id)
```

## Smell: shared Resource mutation

Symptoms:

- Player and enemies reference the same `.tres` stats file.
- Runtime code changes `stats.health` or `stats.ammo`.
- Changing one instance affects all others.

Refactor direction:

- Treat definition Resources as immutable.
- Move current health/ammo/cooldown to runtime state.
- Duplicate Resources only if the Resource is intended to become per-instance runtime data.

Better:

```gdscript
@export var stats_definition: CharacterStats
var _health: int

func _ready() -> void:
    _health = stats_definition.max_health
```

## Smell: polling and sleeps

Symptoms:

- `_process()` checks input, timers, conditions, and UI changes every frame.
- Tests use fixed sleeps.

Refactor direction:

- Input callbacks for one-shot input.
- `_physics_process()` for physics movement.
- Timer for periodic logic.
- Signals for events.
- Retryable `godot-playwright` expectations in tests.

## Smell: no stable automation selectors

Symptoms:

- Tests locate by incidental text that changes with localization.
- Tests rely on node order.
- Generated UI controls have duplicate names.

Refactor direction:

- Add metadata `test_id` to important controls.
- Use roles for standard controls when possible.
- Keep node names stable and PascalCase.

```gdscript
func _ready() -> void:
    %ConfirmButton.set_meta("test_id", "settings-confirm")
```

## Safe migration sequence

For broad refactors:

1. Run baseline validation and save results.
2. Add tests or probes for behavior to preserve.
3. Extract one responsibility at a time.
4. Run targeted checks after each extraction.
5. Only then delete old code.
6. Run project-level validation at the end.

Suggested commands:

```bash
godot-playwright check-scripts "$PROJECT" res://features/player --exclude "addons/**"
godot-playwright check-resources "$PROJECT" res://features/player --exclude "addons/**"
godot-playwright probe "$PROJECT" --scene res://levels/test_level.tscn
godot-playwright test "$PROJECT" tests --grep player --trace retain-on-failure
```

## Refactor response template

```text
Refactor performed:
- Extracted WeaponDefinition Resource from hard-coded weapon dictionary.
- Moved pause menu button logic from GameplayRoot to PauseMenu scene script.
- GameplayRoot now wires PauseMenu.resume_requested to pause state.

Why:
- Weapon data is editor-editable and reused by multiple scenes.
- PauseMenu now owns only UI intent; gameplay state remains in GameplayRoot.

Validated:
- check-script res://features/inventory/weapon_definition.gd: passed
- inspect-scene res://ui/pause_menu.tscn: passed
- test --grep pause: passed
```
