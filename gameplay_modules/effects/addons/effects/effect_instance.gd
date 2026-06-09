class_name EffectInstance
extends RefCounted


static func copy_instance(effect: Dictionary) -> Dictionary:
    return effect.duplicate(true)
