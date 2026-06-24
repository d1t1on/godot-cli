class_name DialogueResult
extends RefCounted


static func make(ok: bool = true, dialogue_id: String = "", line_id: String = "", choice_id: String = "") -> Dictionary:
	return {
		"ok": ok,
		"dialogue_id": dialogue_id,
		"line_id": line_id,
		"choice_id": choice_id,
		"status": "",
		"previous_status": "",
		"line": {},
		"choices": [],
		"variables": {},
		"event": {},
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
