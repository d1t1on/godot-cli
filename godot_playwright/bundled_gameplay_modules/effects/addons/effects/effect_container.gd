class_name EffectContainer
extends Node

@export var database: Resource
@export var save_id: StringName
@export var auto_update: bool = true


func add_effect(effect_id: String, source: Node = null, stacks: int = 1, data: Dictionary = {}) -> Dictionary:
    return {"ok": false, "effect_id": effect_id, "requested_stacks": stacks, "warnings": [], "errors": ["EffectContainer seed failure"]}
