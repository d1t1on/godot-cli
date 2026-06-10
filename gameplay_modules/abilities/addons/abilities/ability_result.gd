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
