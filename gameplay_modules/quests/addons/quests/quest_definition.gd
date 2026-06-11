class_name QuestDefinition
extends Resource

@export var quest_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export var objectives: Array[Resource] = []
@export_enum("all", "any") var completion_policy: String = "all"
@export var auto_complete: bool = true
@export var start_active: bool = false
@export var rewards: Dictionary = {}
@export var default_data: Dictionary = {}
