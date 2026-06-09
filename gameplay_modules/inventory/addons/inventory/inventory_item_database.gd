class_name InventoryItemDatabase
extends Resource

const InventoryItemDefinitionData := preload("res://addons/inventory/inventory_item_definition.gd")
const InventoryResultData := preload("res://addons/inventory/inventory_result.gd")

@export var items: Array[Resource] = []


func get_item(item_id: String) -> Resource:
	var normalized := item_id.strip_edges()
	if normalized.is_empty():
		return null
	for item in items:
		var definition = _definition_or_null(item)
		if definition == null:
			continue
		if String(definition.item_id) == normalized:
			return definition
	return null


func has_item(item_id: String) -> bool:
	return get_item(item_id) != null


func get_max_stack(item_id: String) -> int:
	var item = get_item(item_id)
	if item == null:
		return 0
	return int(item.max_stack)


func validate() -> Dictionary:
	var result := InventoryResultData.make(true)
	var seen := {}
	for index in range(items.size()):
		var item := items[index]
		if item == null:
			InventoryResultData.add_error(result, "items[%d] is null" % index)
			continue
		var definition = _definition_or_null(item)
		if definition == null:
			InventoryResultData.add_error(result, "items[%d] must be an InventoryItemDefinition" % index)
			continue
		var raw_item_id := String(definition.item_id)
		var item_id := raw_item_id.strip_edges()
		if item_id.is_empty():
			InventoryResultData.add_error(result, "items[%d].item_id must be non-empty" % index)
			continue
		if item_id != raw_item_id:
			InventoryResultData.add_error(result, "items[%d].item_id must not contain leading or trailing whitespace" % index)
			continue
		if seen.has(item_id):
			InventoryResultData.add_error(result, "Duplicate item_id: %s" % item_id)
			continue
		seen[item_id] = true
		var max_stack := int(definition.max_stack)
		if max_stack <= 0:
			InventoryResultData.add_error(result, "max_stack must be positive for item_id: %s" % item_id)
	return result


func _definition_or_null(item: Resource):
	if item == null:
		return null
	if item is InventoryItemDefinitionData:
		return item
	return null
