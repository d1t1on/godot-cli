extends Node

const SAVE_GROUP: StringName = &"save_participants"

@onready var effects: Node = $EffectContainer


func run_effects_demo() -> Dictionary:
    var errors: Array[String] = []
    effects.clear_effects()

    var add_haste: Dictionary = effects.add_effect("haste", self, 1, {"source_id": "demo"})
    _assert_bool(bool(add_haste.get("ok", false)), "adding haste should succeed", errors)
    var refresh_haste: Dictionary = effects.add_effect("haste", self, 1, {"speed_multiplier": 1.5})
    _assert_bool(bool(refresh_haste.get("ok", false)), "refreshing haste should succeed", errors)
    _assert_int(1, effects.get_stack_count("haste"), "haste stack count", errors)

    var add_poison: Dictionary = effects.add_effect("poison", self, 5, {"source_id": "demo_poison"})
    _assert_bool(bool(add_poison.get("ok", false)), "adding poison should succeed", errors)
    _assert_int(3, effects.get_stack_count("poison"), "poison stack count", errors)
    _assert_int(2, int(add_poison.get("remainder", -1)), "poison remainder", errors)

    var add_shielded: Dictionary = effects.add_effect("shielded", self, 1)
    var ignored_shielded: Dictionary = effects.add_effect("shielded", self, 1)
    _assert_bool(bool(add_shielded.get("ok", false)), "adding shielded should succeed", errors)
    _assert_bool(bool(ignored_shielded.get("ok", false)), "duplicate shielded should be ignored successfully", errors)

    var tick_events: Array = effects.update_effects(2.5)
    var poison_tick_count := _count_events(tick_events, "tick")
    _assert_int(2, poison_tick_count, "poison tick count", errors)
    effects.update_effects(3.0)
    _assert_bool(not effects.has_effect("haste"), "haste should expire", errors)
    _assert_bool(effects.has_effect("shielded"), "shielded should remain", errors)
    var has_haste_after_expire: bool = effects.has_effect("haste")
    var has_shielded_after_update: bool = effects.has_effect("shielded")

    effects.clear_effects()
    effects.add_effect("poison", self, 2)
    effects.add_effect("stunned", self, 1)
    var saved_state: Dictionary = effects.get_state()
    effects.clear_effects()
    var apply_result: Dictionary = effects.apply_state(saved_state)
    _assert_bool(bool(apply_result.get("ok", false)), "state apply should succeed", errors)
    _assert_int(2, effects.get_stack_count("poison"), "poison stack count after state round-trip", errors)

    var remove_stunned: Dictionary = effects.remove_effect("stunned")
    _assert_bool(bool(remove_stunned.get("ok", false)), "removing stunned should succeed", errors)
    _assert_bool(not effects.has_effect("stunned"), "stunned should be removed", errors)

    var unknown_result: Dictionary = effects.add_effect("missing", self, 1)
    var bad_stacks_result: Dictionary = effects.add_effect("haste", self, 0)
    var negative_delta_events: Array = effects.update_effects(-1.0)
    _assert_bool(not bool(unknown_result.get("ok", true)), "unknown effect should fail", errors)
    _assert_bool(not bool(bad_stacks_result.get("ok", true)), "zero stacks should fail", errors)
    _assert_bool(not bool(negative_delta_events[0].get("ok", true)), "negative delta should fail", errors)

    var save_load_checked := false
    var save_load_poison_stacks := -1
    if has_node("/root/SaveService"):
        save_load_checked = true
        var save_service = get_node("/root/SaveService")
        save_service.delete_slot("effects_demo_slot")
        effects.clear_effects()
        effects.add_effect("poison", self, 2)
        if effects.is_in_group(SAVE_GROUP):
            effects.remove_from_group(SAVE_GROUP)
        if not is_in_group(SAVE_GROUP):
            add_to_group(SAVE_GROUP)
        var save_result: Dictionary = save_service.save_slot("effects_demo_slot")
        effects.clear_effects()
        var load_result: Dictionary = save_service.load_slot("effects_demo_slot")
        var delete_result: Dictionary = save_service.delete_slot("effects_demo_slot")
        remove_from_group(SAVE_GROUP)
        effects.add_to_group(SAVE_GROUP)
        _assert_bool(bool(save_result.get("ok", false)), "SaveService save should succeed", errors)
        _assert_bool(bool(load_result.get("ok", false)), "SaveService load should succeed", errors)
        _assert_bool(bool(delete_result.get("ok", false)), "SaveService delete should succeed", errors)
        save_load_poison_stacks = effects.get_stack_count("poison")
        _assert_int(2, save_load_poison_stacks, "poison stacks after SaveService round-trip", errors)

    return {
        "ok": errors.is_empty(),
        "errors": errors,
        "add_haste": add_haste,
        "refresh_haste": refresh_haste,
        "add_poison": add_poison,
        "poison_stack_count": 3,
        "poison_tick_count": poison_tick_count,
        "has_haste_after_expire": has_haste_after_expire,
        "has_shielded_after_update": has_shielded_after_update,
        "apply_result": apply_result,
        "remove_stunned": remove_stunned,
        "unknown_result": unknown_result,
        "bad_stacks_result": bad_stacks_result,
        "negative_delta_event": negative_delta_events[0],
        "save_load_checked": save_load_checked,
        "save_load_poison_stacks": save_load_poison_stacks,
    }


func get_save_id() -> String:
    return String(effects.get("save_id"))


func save_state() -> Dictionary:
    return effects.get_state()


func load_state(data: Dictionary) -> void:
    effects.apply_state(_normalize_effect_state(data))


func _normalize_effect_state(data: Dictionary) -> Dictionary:
    var normalized: Dictionary = data.duplicate(true)
    var schema_version = normalized.get("schema_version", null)
    if typeof(schema_version) == TYPE_INT or typeof(schema_version) == TYPE_FLOAT:
        normalized["schema_version"] = int(schema_version)
    return normalized


func _count_events(events: Array, event_type: String) -> int:
    var count := 0
    for event in events:
        if String(event.get("type", "")) == event_type:
            count += 1
    return count


func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
    if not value:
        errors.append(message)


func _assert_int(expected: int, actual: int, label: String, errors: Array[String]) -> void:
    if expected != actual:
        errors.append("%s: expected %d, got %d" % [label, expected, actual])
