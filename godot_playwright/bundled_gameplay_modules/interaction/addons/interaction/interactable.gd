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
	if normalized.is_empty():
		return String(name)
	return normalized


func get_interaction_prompt() -> String:
	return prompt


func can_interact(_interactor: Node = null) -> bool:
	return enabled


func interact(interactor: Node = null) -> Dictionary:
	var result := InteractionResultData.make(true, get_interaction_id(), _target_path())
	if not can_interact(interactor):
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
	var result := InteractionResultData.make(true, get_interaction_id(), _target_path())
	var schema := int(data.get("schema_version", InteractionConstantsData.SCHEMA_VERSION))
	if schema != InteractionConstantsData.SCHEMA_VERSION:
		InteractionResultData.add_error(result, "schema_version must be %d" % InteractionConstantsData.SCHEMA_VERSION)
		return result
	if data.has("interaction_id"):
		interaction_id = StringName(String(data["interaction_id"]).strip_edges())
	if data.has("prompt"):
		prompt = String(data["prompt"])
	if data.has("priority"):
		priority = int(data["priority"])
	if data.has("enabled"):
		enabled = bool(data["enabled"])
	return result


func _target_path() -> String:
	if is_inside_tree():
		return String(get_path())
	return String(name)
