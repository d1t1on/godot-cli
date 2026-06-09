class_name EffectDatabase
extends Resource

@export var effects: Array[Resource] = []


func get_effect(effect_id: String) -> Resource:
    return null


func has_effect(effect_id: String) -> bool:
    return get_effect(effect_id) != null


func validate() -> Dictionary:
    return {"ok": false, "warnings": [], "errors": ["EffectDatabase seed failure"]}
