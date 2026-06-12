class_name GameplayEventResult
extends RefCounted


static func make(ok: bool = true, event_id: String = "") -> Dictionary:
	return {
		"ok": ok,
		"event_id": event_id,
		"payload": {},
		"event": {},
		"subscriber_count": 0,
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
