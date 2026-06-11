class_name QuestResult
extends RefCounted


static func make(ok: bool = true, quest_id: String = "", objective_id: String = "") -> Dictionary:
	return {
		"ok": ok,
		"quest_id": quest_id,
		"objective_id": objective_id,
		"status": "",
		"previous_status": "",
		"progress": 0,
		"previous_progress": 0,
		"target_amount": 0,
		"clamped": false,
		"quest": {},
		"rewards": {},
		"data": {},
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
