class_name StateMachine
extends Node

@export var initial_state_id: StringName
@export var auto_start: bool = true


func start(start_state_id: String = "", data: Dictionary = {}) -> Dictionary:
    return {"ok": false, "from": "", "to": start_state_id, "warnings": [], "errors": ["StateMachine seed implementation"]}
