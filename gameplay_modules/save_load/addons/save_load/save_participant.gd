class_name SaveParticipant
extends Node

const SaveConstantsData := preload("res://addons/save_load/save_constants.gd")

@export var save_id: StringName = &""


func _enter_tree() -> void:
	add_to_group(SaveConstantsData.GROUP)


func get_save_id() -> String:
	return String(save_id)


func save_state() -> Dictionary:
	return {}


func load_state(_data: Dictionary) -> void:
	pass
