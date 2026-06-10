class_name EffectInstance
extends RefCounted


static func make(definition: Resource, effect_id: String, stacks: int, data: Dictionary) -> Dictionary:
    var merged_data := _copy_dictionary(definition.default_data)
    for key in data.keys():
        merged_data[key] = _copy_value(data[key])
    var duration := float(definition.duration)
    return {
        "effect_id": effect_id,
        "stacks": stacks,
        "remaining_duration": duration if duration > 0.0 else -1.0,
        "elapsed_time": 0.0,
        "tick_elapsed": 0.0,
        "data": merged_data,
    }


static func copy_instance(effect: Dictionary) -> Dictionary:
    return effect.duplicate(true)


static func to_state(effect: Dictionary) -> Dictionary:
    return {
        "effect_id": String(effect.get("effect_id", "")),
        "stacks": int(effect.get("stacks", 0)),
        "remaining_duration": float(effect.get("remaining_duration", -1.0)),
        "elapsed_time": float(effect.get("elapsed_time", 0.0)),
        "tick_elapsed": float(effect.get("tick_elapsed", 0.0)),
        "data": _copy_dictionary(effect.get("data", {})),
    }


static func merge_data(effect: Dictionary, data: Dictionary) -> void:
    var current_data: Dictionary = effect.get("data", {})
    for key in data.keys():
        current_data[key] = _copy_value(data[key])
    effect["data"] = current_data


static func _copy_dictionary(value: Variant) -> Dictionary:
    if value is Dictionary:
        return (value as Dictionary).duplicate(true)
    return {}


static func _copy_value(value: Variant) -> Variant:
    if value is Dictionary or value is Array:
        return value.duplicate(true)
    return value
