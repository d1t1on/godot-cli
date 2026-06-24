class_name DialogueLineDefinition
extends Resource

@export var line_id: StringName
@export var speaker: String
@export_multiline var text: String
@export var tags: Array[StringName] = []
@export var next_line_id: StringName
@export var choices: Array[Resource] = []
@export var condition: String = ""
@export var on_enter: Dictionary = {}
@export var on_exit: Dictionary = {}
@export var apply_variables: Dictionary = {}
@export var default_data: Dictionary = {}
