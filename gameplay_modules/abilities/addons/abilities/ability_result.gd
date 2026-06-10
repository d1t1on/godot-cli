class_name AbilityResult
extends RefCounted


static func make(ok: bool = true, ability_id: String = "") -> Dictionary:
	return {
		"ok": ok,
		"ability_id": ability_id,
		"enabled": true,
		"cooldown_remaining": 0.0,
		"charges": 0,
		"max_charges": 0,
		"charge_recovery_remaining": 0.0,
		"costs": {},
		"data": {},
		"context": {},
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
