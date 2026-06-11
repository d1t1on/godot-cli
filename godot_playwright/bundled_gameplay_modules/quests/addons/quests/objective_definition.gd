class_name ObjectiveDefinition
extends Resource

@export var objective_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export_range(1, 999999, 1) var target_amount: int = 1
@export var optional: bool = false
@export var hidden: bool = false
@export var default_data: Dictionary = {}
