class_name HealthComponent
extends Node

signal health_changed(current: int, max_health: int)
signal died

@export var stats: CharacterStats

var current_health: int = 0

func _ready() -> void:
    assert(stats != null, "HealthComponent requires a CharacterStats Resource")
    current_health = stats.max_health
    health_changed.emit(current_health, stats.max_health)

func apply_damage(amount: int) -> void:
    if amount <= 0 or current_health <= 0:
        return

    current_health = maxi(current_health - amount, 0)
    health_changed.emit(current_health, stats.max_health)

    if current_health == 0:
        died.emit()

func heal(amount: int) -> void:
    if amount <= 0 or current_health <= 0:
        return

    current_health = mini(current_health + amount, stats.max_health)
    health_changed.emit(current_health, stats.max_health)
