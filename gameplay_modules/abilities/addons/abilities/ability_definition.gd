class_name AbilityDefinition
extends Resource

@export var ability_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export var cooldown: float = 0.0
@export_range(0, 999, 1) var max_charges: int = 1
@export_range(0, 999, 1) var initial_charges: int = 1
@export var charge_recovery_time: float = 0.0
@export var enabled_by_default: bool = true
@export var costs: Dictionary = {}
@export var default_data: Dictionary = {}
