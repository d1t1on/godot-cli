class_name InventoryStack
extends RefCounted

static func make(item_id: String, quantity: int) -> Dictionary:
	return {
		"item_id": item_id,
		"quantity": quantity,
	}


static func copy_stack(stack: Dictionary) -> Dictionary:
	return {
		"item_id": String(stack.get("item_id", "")),
		"quantity": int(stack.get("quantity", 0)),
	}
