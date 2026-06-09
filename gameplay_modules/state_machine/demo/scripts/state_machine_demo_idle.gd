extends "res://addons/state_machine/state.gd"

var enter_count: int = 0


func enter(previous_state: Node, data: Dictionary) -> void:
    enter_count += 1
