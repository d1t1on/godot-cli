class_name SaveResult
extends RefCounted

static func make(ok: bool, slot_id: String = "") -> Dictionary:
	return {
		"ok": ok,
		"slot_id": slot_id,
		"warnings": [],
		"errors": [],
	}


static func add_warning(result: Dictionary, message: String) -> void:
	(result["warnings"] as Array).append(message)


static func add_error(result: Dictionary, message: String) -> void:
	result["ok"] = false
	(result["errors"] as Array).append(message)
