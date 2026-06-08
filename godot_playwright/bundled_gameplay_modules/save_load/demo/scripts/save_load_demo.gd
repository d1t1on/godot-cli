extends Node

@onready var actor: Node2D = $Actor


func run_round_trip() -> Dictionary:
	var save_service = get_node("/root/SaveService")
	save_service.delete_slot("demo_slot")
	actor.global_position = Vector2(4.0, 8.0)
	actor.set("coins", 2)
	var save_result: Dictionary = save_service.save_slot("demo_slot")
	var has_slot_after_save: bool = save_service.has_slot("demo_slot")
	actor.global_position = Vector2(40.0, 80.0)
	actor.set("coins", 99)
	var load_result: Dictionary = save_service.load_slot("demo_slot")
	var delete_result: Dictionary = save_service.delete_slot("demo_slot")
	return {
		"ok": bool(save_result.get("ok", false)) and bool(load_result.get("ok", false)) and bool(delete_result.get("ok", false)),
		"save_result": save_result,
		"load_result": load_result,
		"delete_result": delete_result,
		"saved_coins": 2,
		"restored_coins": int(actor.get("coins")),
		"restored_position": [actor.global_position.x, actor.global_position.y],
		"slot_count_after_save": 1 if has_slot_after_save else 0,
		"has_slot_after_save": has_slot_after_save,
		"has_slot_after_delete": save_service.has_slot("demo_slot"),
	}
