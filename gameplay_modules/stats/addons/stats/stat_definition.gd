class_name StatDefinition
extends Resource

@export var stat_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export var default_base_value: float = 0.0
@export var default_current_value: float = 0.0
@export var clamp_min: bool = true
@export var min_value: float = 0.0
@export var clamp_max: bool = false
@export var max_value: float = 100.0
@export var is_pool: bool = false
