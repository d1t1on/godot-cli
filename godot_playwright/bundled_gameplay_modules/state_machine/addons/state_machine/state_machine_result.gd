class_name StateMachineResult
extends RefCounted


static func make(ok: bool, from_state_id: String = "", to_state_id: String = "") -> Dictionary:
    return {
        "ok": ok,
        "from": from_state_id,
        "to": to_state_id,
        "warnings": [],
        "errors": [],
    }


static func add_warning(result: Dictionary, message: String) -> void:
    (result["warnings"] as Array).append(message)


static func add_error(result: Dictionary, message: String) -> void:
    result["ok"] = false
    (result["errors"] as Array).append(message)
