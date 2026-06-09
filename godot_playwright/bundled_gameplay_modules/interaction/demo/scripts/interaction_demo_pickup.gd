extends "res://addons/interaction/interactable.gd"

@export var item_id: StringName = &"potion"
@export var quantity: int = 1

var picked_up: bool = false


func can_interact(actor: Node, data: Dictionary = {}) -> bool:
	return enabled and not picked_up


func interact(actor: Node, data: Dictionary = {}) -> Dictionary:
	var result := super.interact(actor, data)
	if not bool(result.get("ok", false)):
		return result
	if picked_up:
		InteractionResultData.add_error(result, "Pickup already collected")
		return result

	picked_up = true
	enabled = false
	result["picked_up"] = true
	result["item_id"] = String(item_id)
	result["quantity"] = quantity

	var inventory := _find_inventory(actor)
	if inventory != null and inventory.has_method("add_item"):
		var inventory_result: Dictionary = inventory.call("add_item", String(item_id), quantity)
		result["inventory_result"] = inventory_result
		if not bool(inventory_result.get("ok", false)):
			InteractionResultData.add_warning(result, "Inventory add_item did not fully succeed")
	return result


func get_state() -> Dictionary:
	var state := super.get_state()
	state["picked_up"] = picked_up
	state["item_id"] = String(item_id)
	state["quantity"] = quantity
	return state


func apply_state(data: Dictionary) -> Dictionary:
	var result := super.apply_state(data)
	var raw_picked_up = data.get("picked_up", null)
	if typeof(raw_picked_up) != TYPE_BOOL:
		InteractionResultData.add_error(result, "picked_up must be a bool")

	var raw_quantity = data.get("quantity", null)
	var parsed_quantity := _parse_demo_integer(raw_quantity, "quantity", result)
	if parsed_quantity <= 0:
		InteractionResultData.add_error(result, "quantity must be positive")

	var raw_item_id = data.get("item_id", null)
	if typeof(raw_item_id) != TYPE_STRING and typeof(raw_item_id) != TYPE_STRING_NAME:
		InteractionResultData.add_error(result, "item_id must be a string")

	if not bool(result.get("ok", false)):
		return result

	picked_up = bool(raw_picked_up)
	quantity = parsed_quantity
	item_id = StringName(String(raw_item_id))
	if picked_up:
		enabled = false
	return result


func _find_inventory(actor: Node) -> Node:
	if actor == null:
		return null
	if actor.has_node("Inventory"):
		return actor.get_node("Inventory")
	return null


func _parse_demo_integer(value: Variant, field_name: String, result: Dictionary) -> int:
	if typeof(value) == TYPE_INT:
		return int(value)
	if typeof(value) == TYPE_FLOAT:
		var float_value := float(value)
		if float_value == floor(float_value):
			return int(float_value)
	InteractionResultData.add_error(result, "%s must be an integer" % field_name)
	return 0
