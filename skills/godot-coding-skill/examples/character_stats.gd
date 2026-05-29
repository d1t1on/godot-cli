class_name CharacterStats
extends Resource

@export_range(1, 9999) var max_health: int = 100
@export_range(0.0, 2000.0, 0.1) var move_speed: float = 220.0
@export_range(0, 9999) var contact_damage: int = 10
@export var tags: Array[StringName] = []

func _init(
        p_max_health: int = 100,
        p_move_speed: float = 220.0,
        p_contact_damage: int = 10) -> void:
    max_health = p_max_health
    move_speed = p_move_speed
    contact_damage = p_contact_damage
