class_name StatResult
extends RefCounted


static func make(ok: bool, stat_id: String = "") -> Dictionary:
	return {
		"ok": ok,
		"stat_id": stat_id,
		"previous_value": 0.0,
		"current_value": 0.0,
		"previous_base_value": 0.0,
		"base_value": 0.0,
		"requested_value": 0.0,
		"delta": 0.0,
		"clamped": false,
		"events": [],
		"warnings": [],
		"errors": [],
	}


static func add_event(result: Dictionary, event: Dictionary) -> void:
	(result["events"] as Array).append(event)


static func add_warning(result: Dictionary, message: String) -> void:
	(result["warnings"] as Array).append(message)


static func add_error(result: Dictionary, message: String) -> void:
	result["ok"] = false
	(result["errors"] as Array).append(message)
