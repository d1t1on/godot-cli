class_name EffectResult
extends RefCounted


static func make(ok: bool, effect_id: String = "", requested_stacks: int = 0) -> Dictionary:
    return {
        "ok": ok,
        "effect_id": effect_id,
        "requested_stacks": requested_stacks,
        "applied_stacks": 0,
        "removed_stacks": 0,
        "remainder": 0,
        "effect": {},
        "events": [],
        "warnings": [],
        "errors": [],
    }


static func add_warning(result: Dictionary, message: String) -> void:
    (result["warnings"] as Array).append(message)


static func add_error(result: Dictionary, message: String) -> void:
    result["ok"] = false
    (result["errors"] as Array).append(message)


static func add_event(result: Dictionary, event: Dictionary) -> void:
    (result["events"] as Array).append(event)
