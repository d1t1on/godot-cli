class_name InteractionResult
extends RefCounted


static func make(ok: bool, interaction_id: String = "", target: String = "") -> Dictionary:
	return {
		"ok": ok,
		"interaction_id": interaction_id,
		"target": target,
		"warnings": [],
		"errors": [],
	}


static func add_warning(result: Dictionary, message: String) -> void:
	(result["warnings"] as Array).append(message)


static func add_error(result: Dictionary, message: String) -> void:
	result["ok"] = false
	(result["errors"] as Array).append(message)
