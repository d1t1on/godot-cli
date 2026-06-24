class_name DialogueDefinition
extends Resource

@export var dialogue_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export var lines: Array[Resource] = []
@export var start_line_id: StringName
@export var default_variables: Dictionary = {}
@export var default_data: Dictionary = {}
