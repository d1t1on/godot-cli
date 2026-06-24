class_name DialogueChoiceDefinition
extends Resource

@export var choice_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export var next_line_id: StringName
@export var condition: String = ""
@export var on_select: Dictionary = {}
@export var apply_variables: Dictionary = {}
@export var default_data: Dictionary = {}
