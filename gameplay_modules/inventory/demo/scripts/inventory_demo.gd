extends Node

@onready var inventory: Node = $Inventory


func run_inventory_demo() -> Dictionary:
	var errors: Array[String] = []
	inventory.clear()

	var add_potions: Dictionary = inventory.add_item("potion", 7)
	_assert_bool(add_potions.get("ok", false), "adding potions should succeed", errors)
	_assert_int(7, inventory.get_quantity("potion"), "potion quantity after add", errors)

	var failed_key_add: Dictionary = inventory.add_item("key", 1)
	_assert_bool(not bool(failed_key_add.get("ok", false)), "adding key should fail while capacity is full", errors)

	var remove_potions: Dictionary = inventory.remove_item("potion", 5)
	_assert_bool(remove_potions.get("ok", false), "removing potions should succeed", errors)
	var add_key: Dictionary = inventory.add_item("key", 1)
	_assert_bool(add_key.get("ok", false), "adding key should succeed after freeing a stack", errors)
	_assert_int(2, inventory.get_quantity("potion"), "potion quantity after remove", errors)
	_assert_int(1, inventory.get_quantity("key"), "key quantity after add", errors)

	var saved_state: Dictionary = inventory.get_state()
	inventory.clear()
	inventory.add_item("coin", 4)
	var apply_result: Dictionary = inventory.apply_state(saved_state)
	_assert_bool(apply_result.get("ok", false), "state apply should succeed", errors)
	var round_trip_potion_quantity := int(inventory.get_quantity("potion"))
	var round_trip_key_quantity := int(inventory.get_quantity("key"))
	_assert_int(2, round_trip_potion_quantity, "potion quantity after state round-trip", errors)
	_assert_int(1, round_trip_key_quantity, "key quantity after state round-trip", errors)

	var save_load_checked := false
	var save_load_coin_quantity := -1
	if has_node("/root/SaveService"):
		save_load_checked = true
		var save_service = get_node("/root/SaveService")
		save_service.delete_slot("inventory_demo_slot")
		inventory.clear()
		inventory.add_item("coin", 3)
		var save_result: Dictionary = save_service.save_slot("inventory_demo_slot")
		inventory.clear()
		var load_result: Dictionary = save_service.load_slot("inventory_demo_slot")
		var delete_result: Dictionary = save_service.delete_slot("inventory_demo_slot")
		_assert_bool(save_result.get("ok", false), "SaveService save should succeed", errors)
		_assert_bool(load_result.get("ok", false), "SaveService load should succeed", errors)
		_assert_bool(delete_result.get("ok", false), "SaveService delete should succeed", errors)
		save_load_coin_quantity = inventory.get_quantity("coin")
		_assert_int(3, save_load_coin_quantity, "coin quantity after SaveService round-trip", errors)

	return {
		"ok": errors.is_empty(),
		"errors": errors,
		"add_potions": add_potions,
		"failed_key_add": failed_key_add,
		"failed_key_add_ok": bool(failed_key_add.get("ok", false)),
		"remove_potions": remove_potions,
		"add_key": add_key,
		"apply_result": apply_result,
		"potion_quantity": round_trip_potion_quantity,
		"key_quantity": round_trip_key_quantity,
		"state_round_trip_quantity": round_trip_potion_quantity,
		"save_load_checked": save_load_checked,
		"save_load_coin_quantity": save_load_coin_quantity,
	}


func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
	if not value:
		errors.append(message)


func _assert_int(expected: int, actual: int, label: String, errors: Array[String]) -> void:
	if expected != actual:
		errors.append("%s: expected %d, got %d" % [label, expected, actual])
