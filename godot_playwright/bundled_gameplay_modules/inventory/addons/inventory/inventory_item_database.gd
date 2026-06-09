class_name InventoryItemDatabase
extends Resource

const InventoryResultData := preload("res://addons/inventory/inventory_result.gd")

@export var items: Array[Resource] = []


func get_item(item_id: String) -> Resource:
	var normalized := item_id.strip_edges()
	for item in items:
		if item == null:
			continue
		if String(item.get("item_id")) == normalized:
			return item
	return null


func has_item(item_id: String) -> bool:
	return get_item(item_id) != null


func get_max_stack(item_id: String) -> int:
	var item := get_item(item_id)
	if item == null:
		return 0
	return int(item.get("max_stack"))


func validate() -> Dictionary:
	var result := InventoryResultData.make(true)
	var seen := {}
	for index in range(items.size()):
		var item := items[index]
		if item == null:
			InventoryResultData.add_error(result, "items[%d] is null" % index)
			continue
		var item_id := String(item.get("item_id")).strip_edges()
		if item_id.is_empty():
			InventoryResultData.add_error(result, "items[%d].item_id must be non-empty" % index)
			continue
		if seen.has(item_id):
			InventoryResultData.add_error(result, "Duplicate item_id: %s" % item_id)
			continue
		seen[item_id] = true
		var max_stack := int(item.get("max_stack"))
		if max_stack <= 0:
			InventoryResultData.add_error(result, "max_stack must be positive for item_id: %s" % item_id)
	return result
