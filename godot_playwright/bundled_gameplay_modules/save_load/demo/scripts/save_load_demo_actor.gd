extends Node2D

const SaveConstantsData := preload("res://addons/save_load/save_constants.gd")

@export var save_id: StringName = &"demo_actor"

var coins: int = 0


func _enter_tree() -> void:
	add_to_group(SaveConstantsData.GROUP)


func get_save_id() -> String:
	return String(save_id)


func save_state() -> Dictionary:
	return {
		"position": [global_position.x, global_position.y],
		"coins": coins,
	}


func load_state(data: Dictionary) -> void:
	var position_data: Array = data.get("position", [0.0, 0.0])
	global_position = Vector2(float(position_data[0]), float(position_data[1]))
	coins = int(data.get("coins", 0))
