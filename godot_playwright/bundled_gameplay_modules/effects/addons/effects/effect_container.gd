class_name EffectContainer
extends Node

const EffectConstantsData := preload("res://addons/effects/effect_constants.gd")
const EffectInstanceData := preload("res://addons/effects/effect_instance.gd")
const EffectResultData := preload("res://addons/effects/effect_result.gd")

signal effect_added(effect_id: String, effect: Dictionary, result: Dictionary)
signal effect_removed(effect_id: String, effect: Dictionary, result: Dictionary)
signal effect_ticked(effect_id: String, effect: Dictionary, event: Dictionary)
signal effect_expired(effect_id: String, effect: Dictionary, event: Dictionary)
signal effects_changed(event: Dictionary)

@export var database: Resource
@export var save_id: StringName
@export var auto_update: bool = true

var _effects: Array[Dictionary] = []


func _enter_tree() -> void:
    if not String(save_id).is_empty():
        add_to_group(EffectConstantsData.SAVE_GROUP)


func _process(delta: float) -> void:
    if auto_update:
        update_effects(delta)


func add_effect(effect_id: String, source: Node = null, stacks: int = 1, data: Dictionary = {}) -> Dictionary:
    var normalized := effect_id.strip_edges()
    var result := EffectResultData.make(true, normalized, stacks)
    if stacks <= 0:
        EffectResultData.add_error(result, "stacks must be positive")
        return result
    if not _is_json_compatible(data):
        EffectResultData.add_error(result, "data must be JSON-compatible")
        return result
    var definition = _definition_for_result(result, normalized)
    if definition == null:
        return result

    var index := _find_effect_index(normalized)
    if index == -1:
        return _add_new_effect(result, definition, normalized, source, stacks, data)
    return _apply_existing_effect(result, definition, index, source, stacks, data)


func remove_effect(effect_id: String, stacks: int = 0) -> Dictionary:
    var normalized := effect_id.strip_edges()
    var result := EffectResultData.make(true, normalized, stacks)
    var index := _find_effect_index(normalized)
    if index == -1:
        EffectResultData.add_error(result, "Effect is not active: %s" % normalized)
        return result

    var effect := _effects[index]
    var current_stacks := int(effect.get("stacks", 0))
    var removed := current_stacks if stacks <= 0 else mini(stacks, current_stacks)
    result["removed_stacks"] = removed
    if stacks <= 0 or removed >= current_stacks:
        var removed_effect := EffectInstanceData.copy_instance(effect)
        _effects.remove_at(index)
        result["effect"] = removed_effect
        var event := _make_event(EffectConstantsData.EVENT_REMOVED, removed_effect, null, removed, 0)
        EffectResultData.add_event(result, event)
        effect_removed.emit(normalized, removed_effect, result)
        effects_changed.emit(event)
        return result

    effect["stacks"] = current_stacks - removed
    var copied := EffectInstanceData.copy_instance(effect)
    result["effect"] = copied
    var partial_event := _make_event(EffectConstantsData.EVENT_REMOVED, copied, null, removed, 0)
    EffectResultData.add_event(result, partial_event)
    effect_removed.emit(normalized, copied, result)
    effects_changed.emit(partial_event)
    return result


func clear_effects() -> void:
    if _effects.is_empty():
        return
    var cleared: Array = []
    for effect in _effects:
        cleared.append(EffectInstanceData.copy_instance(effect))
    _effects.clear()
    effects_changed.emit({
        "ok": true,
        "type": EffectConstantsData.EVENT_CLEARED,
        "effects": cleared,
        "warnings": [],
        "errors": [],
    })


func has_effect(effect_id: String) -> bool:
    return _find_effect_index(effect_id.strip_edges()) != -1


func get_effect(effect_id: String) -> Dictionary:
    var index := _find_effect_index(effect_id.strip_edges())
    if index == -1:
        return {}
    return EffectInstanceData.copy_instance(_effects[index])


func get_effects() -> Array:
    var copied: Array = []
    for effect in _effects:
        copied.append(EffectInstanceData.copy_instance(effect))
    return copied


func get_stack_count(effect_id: String) -> int:
    var index := _find_effect_index(effect_id.strip_edges())
    if index == -1:
        return 0
    return int(_effects[index].get("stacks", 0))


func update_effects(delta: float) -> Array[Dictionary]:
    var events: Array[Dictionary] = []
    if delta < 0.0:
        events.append({
            "ok": false,
            "type": EffectConstantsData.EVENT_ERROR,
            "effect_id": "",
            "warnings": [],
            "errors": ["delta must be zero or greater"],
        })
        return events
    if delta == 0.0:
        return events

    var index := 0
    while index < _effects.size():
        var effect := _effects[index]
        var definition = _definition_for_id(String(effect.get("effect_id", "")))
        if definition == null:
            index += 1
            continue
        var remaining_duration := float(effect.get("remaining_duration", -1.0))
        var active_delta := delta
        if remaining_duration >= 0.0:
            active_delta = max(0.0, min(delta, remaining_duration))
        effect["elapsed_time"] = float(effect.get("elapsed_time", 0.0)) + active_delta
        var tick_interval := float(definition.tick_interval)
        if tick_interval > 0.0:
            effect["tick_elapsed"] = float(effect.get("tick_elapsed", 0.0)) + active_delta
            while float(effect.get("tick_elapsed", 0.0)) >= tick_interval:
                effect["tick_elapsed"] = float(effect.get("tick_elapsed", 0.0)) - tick_interval
                var tick_event := _make_event(EffectConstantsData.EVENT_TICK, effect, null, 0, 0)
                events.append(tick_event)
                effect_ticked.emit(String(effect.get("effect_id", "")), EffectInstanceData.copy_instance(effect), tick_event)
                effects_changed.emit(tick_event)

        if remaining_duration >= 0.0:
            remaining_duration -= active_delta
            effect["remaining_duration"] = remaining_duration
            if remaining_duration <= 0.0:
                var expired_effect := EffectInstanceData.copy_instance(effect)
                _effects.remove_at(index)
                var expired_event := _make_event(EffectConstantsData.EVENT_EXPIRED, expired_effect, null, int(expired_effect.get("stacks", 0)), 0)
                events.append(expired_event)
                effect_expired.emit(String(expired_effect.get("effect_id", "")), expired_effect, expired_event)
                effects_changed.emit(expired_event)
                continue
        index += 1
    return events


func get_state() -> Dictionary:
    var state_effects: Array = []
    for effect in _effects:
        state_effects.append(EffectInstanceData.to_state(effect))
    return {
        "schema_version": EffectConstantsData.SCHEMA_VERSION,
        "effects": state_effects,
    }


func apply_state(data: Dictionary) -> Dictionary:
    var result := EffectResultData.make(true)
    var parsed_effects := _parse_state_effects(data, result)
    if not bool(result.get("ok", false)):
        return result
    _effects = parsed_effects
    return result


func get_save_id() -> String:
    return String(save_id)


func save_state() -> Dictionary:
    return get_state()


func load_state(data: Dictionary) -> void:
    var result := apply_state(data)
    if not bool(result.get("ok", false)):
        push_warning("EffectContainer load_state failed: %s" % ", ".join(PackedStringArray(result.get("errors", []))))


func _add_new_effect(result: Dictionary, definition: Resource, effect_id: String, source: Node, stacks: int, data: Dictionary) -> Dictionary:
    var max_stacks := int(definition.max_stacks)
    var applied := mini(stacks, max_stacks)
    var remainder := stacks - applied
    var effect := EffectInstanceData.make(definition, effect_id, applied, data)
    _effects.append(effect)
    result["applied_stacks"] = applied
    result["remainder"] = remainder
    result["effect"] = EffectInstanceData.copy_instance(effect)
    if remainder > 0:
        EffectResultData.add_warning(result, "Effect could not fit %d stack(s): %s" % [remainder, effect_id])
    var event := _make_event(EffectConstantsData.EVENT_ADDED, effect, source, applied, remainder)
    EffectResultData.add_event(result, event)
    effect_added.emit(effect_id, EffectInstanceData.copy_instance(effect), result)
    effects_changed.emit(event)
    return result


func _apply_existing_effect(result: Dictionary, definition: Resource, index: int, source: Node, stacks: int, data: Dictionary) -> Dictionary:
    var effect := _effects[index]
    var effect_id := String(effect.get("effect_id", ""))
    var stack_mode := String(definition.stack_mode)
    if stack_mode == EffectConstantsData.STACK_IGNORE:
        result["effect"] = EffectInstanceData.copy_instance(effect)
        result["remainder"] = stacks
        EffectResultData.add_warning(result, "Effect already active and stack_mode is ignore: %s" % effect_id)
        var ignored_event := _make_event(EffectConstantsData.EVENT_IGNORED, effect, source, 0, stacks)
        EffectResultData.add_event(result, ignored_event)
        return result

    if stack_mode == EffectConstantsData.STACK_STACK:
        var current_stacks := int(effect.get("stacks", 0))
        var available := int(definition.max_stacks) - current_stacks
        var applied := mini(stacks, max(available, 0))
        var remainder := stacks - applied
        if applied <= 0:
            EffectResultData.add_error(result, "Effect is already at max_stacks: %s" % effect_id)
            result["remainder"] = stacks
            result["effect"] = EffectInstanceData.copy_instance(effect)
            return result
        effect["stacks"] = current_stacks + applied
        result["applied_stacks"] = applied
        result["remainder"] = remainder
        if remainder > 0:
            EffectResultData.add_warning(result, "Effect could not fit %d stack(s): %s" % [remainder, effect_id])
        _refresh_timers(effect, definition)
        EffectInstanceData.merge_data(effect, data)
        result["effect"] = EffectInstanceData.copy_instance(effect)
        var stacked_event := _make_event(EffectConstantsData.EVENT_STACKED, effect, source, applied, remainder)
        EffectResultData.add_event(result, stacked_event)
        effects_changed.emit(stacked_event)
        return result

    _refresh_timers(effect, definition)
    EffectInstanceData.merge_data(effect, data)
    result["effect"] = EffectInstanceData.copy_instance(effect)
    var refreshed_event := _make_event(EffectConstantsData.EVENT_REFRESHED, effect, source, 0, 0)
    EffectResultData.add_event(result, refreshed_event)
    effects_changed.emit(refreshed_event)
    return result


func _definition_for_result(result: Dictionary, effect_id: String):
    if effect_id.is_empty():
        EffectResultData.add_error(result, "effect_id must be non-empty")
        return null
    if not _validate_database(result):
        return null
    var definition = _definition_for_id(effect_id)
    if definition == null:
        EffectResultData.add_error(result, "Unknown effect_id: %s" % effect_id)
    return definition


func _definition_for_id(effect_id: String):
    if database == null or not database.has_method("get_effect"):
        return null
    return database.call("get_effect", effect_id)


func _validate_database(result: Dictionary) -> bool:
    if database == null:
        EffectResultData.add_error(result, "database must be assigned")
        return false
    if not database.has_method("validate") or not database.has_method("has_effect") or not database.has_method("get_effect"):
        EffectResultData.add_error(result, "database must be an EffectDatabase")
        return false
    var database_result: Dictionary = database.call("validate")
    if not bool(database_result.get("ok", false)):
        for error in database_result.get("errors", []):
            EffectResultData.add_error(result, String(error))
        for warning in database_result.get("warnings", []):
            EffectResultData.add_warning(result, String(warning))
        return false
    return true


func _parse_state_effects(data: Dictionary, result: Dictionary) -> Array[Dictionary]:
    var parsed_effects: Array[Dictionary] = []
    var schema_version = data.get("schema_version", null)
    if typeof(schema_version) != TYPE_INT or int(schema_version) != EffectConstantsData.SCHEMA_VERSION:
        EffectResultData.add_error(result, "schema_version must be %d" % EffectConstantsData.SCHEMA_VERSION)
    var raw_effects = data.get("effects", null)
    if not (raw_effects is Array):
        EffectResultData.add_error(result, "effects must be an Array")
        return parsed_effects
    if not _validate_database(result):
        return parsed_effects
    if not bool(result.get("ok", false)):
        return parsed_effects

    var seen := {}
    var effect_items: Array = raw_effects
    for index in range(effect_items.size()):
        var effect_value = effect_items[index]
        if not (effect_value is Dictionary):
            EffectResultData.add_error(result, "effects[%d] must be a Dictionary" % index)
            continue
        var effect: Dictionary = effect_value
        var effect_error_count := (result.get("errors", []) as Array).size()
        var raw_effect_id = effect.get("effect_id", "")
        if typeof(raw_effect_id) != TYPE_STRING and typeof(raw_effect_id) != TYPE_STRING_NAME:
            EffectResultData.add_error(result, "effects[%d].effect_id must be a string" % index)
            continue
        var effect_id := String(raw_effect_id)
        var normalized := effect_id.strip_edges()
        if normalized.is_empty():
            EffectResultData.add_error(result, "effects[%d].effect_id must be non-empty" % index)
        elif normalized != effect_id:
            EffectResultData.add_error(result, "effects[%d].effect_id must not contain leading or trailing whitespace" % index)
        elif seen.has(normalized):
            EffectResultData.add_error(result, "Duplicate active effect_id: %s" % normalized)
        seen[normalized] = true

        var definition = _definition_for_id(normalized)
        if definition == null:
            EffectResultData.add_error(result, "Unknown effect_id: %s" % normalized)
            continue
        var stacks := _parse_int(effect.get("stacks", null), "stacks", result)
        if stacks <= 0:
            EffectResultData.add_error(result, "effects[%d].stacks must be positive" % index)
        elif stacks > int(definition.max_stacks):
            EffectResultData.add_error(result, "effects[%d].stacks exceeds max_stacks for effect_id: %s" % [index, normalized])
        var remaining_duration := _parse_float(effect.get("remaining_duration", null), "remaining_duration", result)
        var elapsed_time := _parse_float(effect.get("elapsed_time", null), "elapsed_time", result)
        var tick_elapsed := _parse_float(effect.get("tick_elapsed", null), "tick_elapsed", result)
        if remaining_duration < -1.0:
            EffectResultData.add_error(result, "effects[%d].remaining_duration must be -1 or greater" % index)
        if elapsed_time < 0.0:
            EffectResultData.add_error(result, "effects[%d].elapsed_time must be zero or greater" % index)
        if tick_elapsed < 0.0:
            EffectResultData.add_error(result, "effects[%d].tick_elapsed must be zero or greater" % index)
        var effect_data = effect.get("data", {})
        if not (effect_data is Dictionary):
            EffectResultData.add_error(result, "effects[%d].data must be a Dictionary" % index)
        elif not _is_json_compatible(effect_data):
            EffectResultData.add_error(result, "effects[%d].data must be JSON-compatible" % index)
        if (result.get("errors", []) as Array).size() == effect_error_count:
            parsed_effects.append({
                "effect_id": normalized,
                "stacks": stacks,
                "remaining_duration": remaining_duration,
                "elapsed_time": elapsed_time,
                "tick_elapsed": tick_elapsed,
                "data": (effect_data as Dictionary).duplicate(true),
            })
    return parsed_effects


func _parse_int(value: Variant, field_name: String, result: Dictionary) -> int:
    if typeof(value) == TYPE_INT:
        return int(value)
    if typeof(value) == TYPE_FLOAT and float(value) == floor(float(value)):
        return int(value)
    EffectResultData.add_error(result, "%s must be an integer" % field_name)
    return 0


func _parse_float(value: Variant, field_name: String, result: Dictionary) -> float:
    if typeof(value) == TYPE_INT or typeof(value) == TYPE_FLOAT:
        var number := float(value)
        if not is_nan(number) and not is_inf(number):
            return number
    EffectResultData.add_error(result, "%s must be a finite number" % field_name)
    return 0.0


func _is_json_compatible(value: Variant) -> bool:
    match typeof(value):
        TYPE_NIL, TYPE_BOOL, TYPE_STRING, TYPE_INT:
            return true
        TYPE_FLOAT:
            var number := float(value)
            return not is_nan(number) and not is_inf(number)
        TYPE_ARRAY:
            for item in value:
                if not _is_json_compatible(item):
                    return false
            return true
        TYPE_DICTIONARY:
            for key in value.keys():
                if typeof(key) != TYPE_STRING and typeof(key) != TYPE_STRING_NAME:
                    return false
                if not _is_json_compatible(value[key]):
                    return false
            return true
        _:
            return false


func _find_effect_index(effect_id: String) -> int:
    for index in range(_effects.size()):
        if String(_effects[index].get("effect_id", "")) == effect_id:
            return index
    return -1


func _refresh_timers(effect: Dictionary, definition: Resource) -> void:
    var duration := float(definition.duration)
    effect["remaining_duration"] = duration if duration > 0.0 else -1.0
    effect["elapsed_time"] = 0.0
    effect["tick_elapsed"] = 0.0


func _make_event(event_type: String, effect: Dictionary, source: Node, changed_stacks: int, remainder: int) -> Dictionary:
    var event := {
        "ok": true,
        "type": event_type,
        "effect_id": String(effect.get("effect_id", "")),
        "effect": EffectInstanceData.copy_instance(effect),
        "changed_stacks": changed_stacks,
        "remainder": remainder,
        "source": source.name if source != null else "",
        "warnings": [],
        "errors": [],
    }
    return event
