class_name State
extends Node

@export var state_id: StringName


func get_state_id() -> String:
    return String(state_id)


func enter(previous_state: Node, data: Dictionary) -> void:
    pass


func exit(next_state: Node) -> void:
    pass


func update(delta: float) -> void:
    pass


func physics_update(delta: float) -> void:
    pass


func handle_input(event: InputEvent) -> void:
    pass


func can_enter(previous_state: Node, data: Dictionary) -> bool:
    return true


func can_exit(next_state: Node) -> bool:
    return true
