class_name InventoryResult
extends RefCounted

static func make(ok: bool, item_id: String = "", requested: int = 0) -> Dictionary:
	return {
		"ok": ok,
		"item_id": item_id,
		"requested": requested,
		"added": 0,
		"removed": 0,
		"remainder": 0,
		"warnings": [],
		"errors": [],
	}


static func add_warning(result: Dictionary, message: String) -> void:
	(result["warnings"] as Array).append(message)


static func add_error(result: Dictionary, message: String) -> void:
	result["ok"] = false
	(result["errors"] as Array).append(message)
