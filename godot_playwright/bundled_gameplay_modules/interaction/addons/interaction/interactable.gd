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
	var next_prompt := prompt
	var next_priority := priority
	var next_enabled := enabled

	for field_name in ["schema_version", "interaction_id", "enabled", "prompt", "priority"]:
		_require_field(data, field_name, result)

	if data.has("schema_version"):
		var schema_version := _parse_integer_field(data["schema_version"], "schema_version", result)
		if schema_version != InteractionConstantsData.SCHEMA_VERSION:
			InteractionResultData.add_error(result, "schema_version must be %d" % InteractionConstantsData.SCHEMA_VERSION)
	if data.has("interaction_id"):
		if typeof(data["interaction_id"]) != TYPE_STRING:
			InteractionResultData.add_error(result, "interaction_id must be a string")
	if data.has("prompt"):
		if typeof(data["prompt"]) != TYPE_STRING:
			InteractionResultData.add_error(result, "prompt must be a string")
		else:
			next_prompt = String(data["prompt"])
	if data.has("priority"):
		next_priority = _parse_integer_field(data["priority"], "priority", result)
	if data.has("enabled"):
		if typeof(data["enabled"]) != TYPE_BOOL:
			InteractionResultData.add_error(result, "enabled must be a bool")
		else:
			next_enabled = bool(data["enabled"])
	if not bool(result.get("ok", false)):
		return result

	prompt = next_prompt
	priority = next_priority
	enabled = next_enabled
	return result


func _require_field(data: Dictionary, field_name: String, result: Dictionary) -> bool:
	if data.has(field_name):
		return true
	InteractionResultData.add_error(result, "%s is required" % field_name)
	return false


func _parse_integer_field(value: Variant, field_name: String, result: Dictionary) -> int:
	if typeof(value) == TYPE_INT:
		return int(value)
	if typeof(value) == TYPE_FLOAT:
		var float_value := float(value)
		if float_value == floor(float_value):
			return int(float_value)
	InteractionResultData.add_error(result, "%s must be an integer" % field_name)
	return 0


func _target_name() -> String:
	var parent := get_parent()
	if parent != null:
		var parent_name := String(parent.name).strip_edges()
		if not parent_name.is_empty():
			return parent_name
	return String(name)
