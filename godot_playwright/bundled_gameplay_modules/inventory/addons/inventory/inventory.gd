class_name Inventory
extends Node

const InventoryConstantsData := preload("res://addons/inventory/inventory_constants.gd")
const InventoryResultData := preload("res://addons/inventory/inventory_result.gd")
const InventoryStackData := preload("res://addons/inventory/inventory_stack.gd")

@export var database: Resource
@export_range(0, 999, 1) var capacity: int = 12
@export var save_id: StringName

var _stacks: Array[Dictionary] = []

func add_item(item_id: String, quantity: int = 1) -> Dictionary:
	var normalized := item_id.strip_edges()
	var result := InventoryResultData.make(true, normalized, quantity)
	if not _validate_common_mutation(result, normalized, quantity):
		return result

	var max_stack := int(database.call("get_max_stack", normalized))
	if max_stack <= 0:
		InventoryResultData.add_error(result, "max_stack must be positive for item_id: %s" % normalized)
		return result

	var remaining := quantity
	for stack in _stacks:
		if remaining <= 0:
			break
		if String(stack.get("item_id", "")) != normalized:
			continue
		var current := int(stack.get("quantity", 0))
		var available_space := max_stack - current
		if available_space <= 0:
			continue
		var added := mini(available_space, remaining)
		stack["quantity"] = current + added
		result["added"] = int(result["added"]) + added
		remaining -= added

	while remaining > 0 and _stacks.size() < capacity:
		var added := mini(max_stack, remaining)
		_stacks.append(InventoryStackData.make(normalized, added))
		result["added"] = int(result["added"]) + added
		remaining -= added

	result["remainder"] = remaining
	if int(result["added"]) == 0:
		InventoryResultData.add_error(result, "Inventory has no room for item_id: %s" % normalized)
	elif remaining > 0:
		InventoryResultData.add_warning(result, "Inventory could not fit %d item(s) for item_id: %s" % [remaining, normalized])
	return result


func remove_item(item_id: String, quantity: int = 1) -> Dictionary:
	var normalized := item_id.strip_edges()
	var result := InventoryResultData.make(true, normalized, quantity)
	if not _validate_common_mutation(result, normalized, quantity):
		return result
	var available := get_quantity(normalized)
	if available < quantity:
		InventoryResultData.add_error(result, "Inventory only has %d item(s) for item_id: %s" % [available, normalized])
		return result

	var remaining := quantity
	var index := 0
	while index < _stacks.size() and remaining > 0:
		var stack := _stacks[index]
		if String(stack.get("item_id", "")) != normalized:
			index += 1
			continue
		var current := int(stack.get("quantity", 0))
		var removed := mini(current, remaining)
		stack["quantity"] = current - removed
		result["removed"] = int(result["removed"]) + removed
		remaining -= removed
		if int(stack.get("quantity", 0)) <= 0:
			_stacks.remove_at(index)
		else:
			index += 1
	return result


func has_item(item_id: String, quantity: int = 1) -> bool:
	if quantity <= 0:
		return false
	return get_quantity(item_id) >= quantity


func get_quantity(item_id: String) -> int:
	var normalized := item_id.strip_edges()
	var total := 0
	for stack in _stacks:
		if String(stack.get("item_id", "")) == normalized:
			total += int(stack.get("quantity", 0))
	return total


func clear() -> void:
	_stacks.clear()


func get_stacks() -> Array:
	var copied: Array = []
	for stack in _stacks:
		copied.append(InventoryStackData.copy_stack(stack))
	return copied


func _validate_common_mutation(result: Dictionary, item_id: String, quantity: int) -> bool:
	if item_id.is_empty():
		InventoryResultData.add_error(result, "item_id must be non-empty")
	if quantity <= 0:
		InventoryResultData.add_error(result, "quantity must be positive")
	if capacity < 0:
		InventoryResultData.add_error(result, "capacity must be zero or greater")
	if not _validate_database(result):
		return false
	if result["ok"] and not bool(database.call("has_item", item_id)):
		InventoryResultData.add_error(result, "Unknown item_id: %s" % item_id)
	return bool(result["ok"])


func _validate_database(result: Dictionary) -> bool:
	if database == null:
		InventoryResultData.add_error(result, "database must be assigned")
		return false
	if not database.has_method("validate") or not database.has_method("has_item") or not database.has_method("get_max_stack"):
		InventoryResultData.add_error(result, "database must be an InventoryItemDatabase")
		return false
	var database_result: Dictionary = database.call("validate")
	if not bool(database_result.get("ok", false)):
		for error in database_result.get("errors", []):
			InventoryResultData.add_error(result, String(error))
		for warning in database_result.get("warnings", []):
			InventoryResultData.add_warning(result, String(warning))
		return false
	return true
