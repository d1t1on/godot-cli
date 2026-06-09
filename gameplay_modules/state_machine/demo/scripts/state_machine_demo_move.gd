extends "res://addons/state_machine/state.gd"

var last_speed: int = 0


func enter(previous_state: Node, data: Dictionary) -> void:
    last_speed = int(data.get("speed", 0))


func request_attack() -> Dictionary:
    return get_parent().call("request_transition", "attack", {"source": "move"})
