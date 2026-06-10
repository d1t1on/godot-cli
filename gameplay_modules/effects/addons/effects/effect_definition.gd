class_name EffectDefinition
extends Resource

@export var effect_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export_range(0.0, 999999.0, 0.1) var duration: float = 0.0
@export_range(0.0, 999999.0, 0.1) var tick_interval: float = 0.0
@export_enum("refresh", "stack", "ignore") var stack_mode: String = "refresh"
@export_range(1, 999, 1) var max_stacks: int = 1
@export var default_data: Dictionary = {}
