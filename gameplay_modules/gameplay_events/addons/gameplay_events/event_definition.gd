class_name EventDefinition
extends Resource

@export var event_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export var default_payload: Dictionary = {}
@export var record_by_default: bool = true
