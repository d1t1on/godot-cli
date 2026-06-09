class_name Interactable
extends Node

const InteractionConstantsData := preload("res://addons/interaction/interaction_constants.gd")
const InteractionResultData := preload("res://addons/interaction/interaction_result.gd")

@export var interaction_id: StringName
@export var prompt: String = "Interact"
@export var priority: int = 0
@export var enabled: bool = true


func get_interaction_id() -> String:
	var normalized := String(interaction_id).strip_edges()
	if not normalized.is_empty():
		return normalized
	return _target_name()


func get_interaction_prompt(actor: Node = null) -> String:
	return prompt


func can_interact(actor: Node, data: Dictionary = {}) -> bool:
	return enabled


func interact(actor: Node, data: Dictionary = {}) -> Dictionary:
	var result := InteractionResultData.make(true, get_interaction_id(), _target_name())
	if not can_interact(actor, data):
		InteractionResultData.add_error(result, "Interactable is disabled")
	return result


func get_state() -> Dictionary:
	return {
		"schema_version": InteractionConstantsData.SCHEMA_VERSION,
		"interaction_id": get_interaction_id(),
		"prompt": prompt,
		"priority": priority,
		"enabled": enabled,
	}


func apply_state(data: Dictionary) -> Dictionary:
	var result := InteractionResultData.make(true, get_interaction_id(), _target_name())
	var next_interaction_id := interaction_id
	var next_prompt := prompt
	var next_priority := priority
	var next_enabled := enabled

	if data.has("schema_version"):
		if typeof(data["schema_version"]) != TYPE_INT:
			InteractionResultData.add_error(result, "schema_version must be an int")
		elif int(data["schema_version"]) != InteractionConstantsData.SCHEMA_VERSION:
			InteractionResultData.add_error(result, "schema_version must be %d" % InteractionConstantsData.SCHEMA_VERSION)
	if data.has("interaction_id"):
		if typeof(data["interaction_id"]) != TYPE_STRING:
			InteractionResultData.add_error(result, "interaction_id must be a string")
		else:
			next_interaction_id = StringName(String(data["interaction_id"]).strip_edges())
	if data.has("prompt"):
		if typeof(data["prompt"]) != TYPE_STRING:
			InteractionResultData.add_error(result, "prompt must be a string")
		else:
			next_prompt = String(data["prompt"])
	if data.has("priority"):
		if typeof(data["priority"]) != TYPE_INT:
			InteractionResultData.add_error(result, "priority must be an int")
		else:
			next_priority = int(data["priority"])
	if data.has("enabled"):
		if typeof(data["enabled"]) != TYPE_BOOL:
			InteractionResultData.add_error(result, "enabled must be a bool")
		else:
			next_enabled = bool(data["enabled"])
	if not bool(result.get("ok", false)):
		return result

	interaction_id = next_interaction_id
	prompt = next_prompt
	priority = next_priority
	enabled = next_enabled
	return result


func _target_name() -> String:
	var parent := get_parent()
	if parent != null:
		var parent_name := String(parent.name).strip_edges()
		if not parent_name.is_empty():
			return parent_name
	return String(name)
