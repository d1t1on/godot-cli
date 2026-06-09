extends "res://addons/state_machine/state.gd"

var entered_from: String = ""


func enter(previous_state: Node, data: Dictionary) -> void:
    if previous_state != null:
        entered_from = String(previous_state.name)
