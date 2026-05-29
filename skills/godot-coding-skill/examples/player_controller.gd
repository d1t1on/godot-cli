class_name PlayerController
extends CharacterBody2D

signal interact_requested

@export var stats: CharacterStats

func _ready() -> void:
    assert(stats != null, "PlayerController requires a CharacterStats Resource")

func _physics_process(_delta: float) -> void:
    var direction := Input.get_vector("move_left", "move_right", "move_up", "move_down")
    velocity = direction * stats.move_speed
    move_and_slide()

func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed("interact"):
        interact_requested.emit()
        get_viewport().set_input_as_handled()
