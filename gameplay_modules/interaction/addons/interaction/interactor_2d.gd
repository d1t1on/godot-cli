class_name Interactor2D
extends Area2D

const InteractableData := preload("res://addons/interaction/interactable.gd")
const InteractionResultData := preload("res://addons/interaction/interaction_result.gd")

@export var actor_path: NodePath

var _candidates: Array[Node] = []
var _warnings: Array[String] = []


func _ready() -> void:
	body_entered.connect(_on_node_entered)
	body_exited.connect(_on_node_exited)
	area_entered.connect(_on_node_entered)
	area_exited.connect(_on_node_exited)


func get_candidates() -> Array:
	var valid_candidates: Array[Node] = []
	var available_candidates: Array[Node] = []
	for candidate in _candidates:
		if not is_instance_valid(candidate) or not _is_interactable(candidate):
			continue
		valid_candidates.append(candidate)
		if _can_candidate_interact(candidate):
			available_candidates.append(candidate)
	_candidates = valid_candidates
	return available_candidates


func get_best_candidate() -> Node:
	var best_candidate: Node = null
	var best_priority := 0
	for candidate in get_candidates():
		var candidate_priority := _candidate_priority(candidate)
		if best_candidate == null or candidate_priority > best_priority:
			best_candidate = candidate
			best_priority = candidate_priority
	return best_candidate


func get_best_prompt() -> String:
	var candidate := get_best_candidate()
	if candidate == null:
		return ""
	return _candidate_prompt(candidate)


func interact_best(data: Dictionary = {}) -> Dictionary:
	var candidate := get_best_candidate()
	if candidate == null:
		var result := InteractionResultData.make(false)
		InteractionResultData.add_error(result, "No interaction candidate")
		_append_warnings(result)
		return result
	return interact_with(candidate, data)


func interact_with(target, data: Dictionary = {}) -> Dictionary:
	if typeof(target) == TYPE_OBJECT and not is_instance_valid(target):
		var freed_result := InteractionResultData.make(false)
		InteractionResultData.add_error(freed_result, "Target is invalid")
		_append_warnings(freed_result)
		return freed_result
	if not _is_interactable(target):
		var invalid_result := InteractionResultData.make(false)
		InteractionResultData.add_error(invalid_result, "Target must be an Interactable")
		_append_warnings(invalid_result)
		return invalid_result

	var result := InteractionResultData.make(false, _candidate_id(target), _candidate_target(target))
	if not bool(target.get("enabled")):
		InteractionResultData.add_error(result, "Interactable is disabled")
		_append_warnings(result)
		return result

	var actor := _get_actor()
	if not bool(target.call("can_interact", actor, data)):
		InteractionResultData.add_error(result, "Interactable candidate is unavailable")
		_append_warnings(result)
		return result

	var interaction_result = target.call("interact", actor, data)
	if not interaction_result is Dictionary:
		InteractionResultData.add_error(result, "Interactable returned an invalid interaction result")
		_append_warnings(result)
		return result

	var normalized_result := _ensure_result_fields(interaction_result, target)
	_append_warnings(normalized_result)
	return normalized_result


func clear_candidates() -> void:
	_candidates.clear()
	_warnings.clear()


func _on_node_entered(node: Node) -> void:
	var candidate := _find_interactable(node, true)
	if candidate != null and not _candidates.has(candidate):
		_candidates.append(candidate)


func _on_node_exited(node: Node) -> void:
	var candidate := _find_interactable(node, false)
	if candidate != null:
		_candidates.erase(candidate)


func _find_interactable(node: Node, record_warnings: bool) -> Node:
	if node == null:
		return null
	if _is_interactable(node):
		return node

	var child_candidates: Array[Node] = []
	for child in node.get_children():
		if child is Node and _is_interactable(child):
			child_candidates.append(child)
	if child_candidates.size() == 1:
		return child_candidates[0]
	if child_candidates.size() > 1:
		if record_warnings:
			_add_warning("Ambiguous interactable children under %s" % node.name)
		return null

	var current := node.get_parent()
	while current != null:
		if _is_interactable(current):
			return current
		current = current.get_parent()
	return null


func _is_interactable(node) -> bool:
	if typeof(node) != TYPE_OBJECT:
		return false
	if not is_instance_valid(node):
		return false
	return node is InteractableData


func _can_candidate_interact(candidate: Node, data: Dictionary = {}) -> bool:
	if not _is_interactable(candidate):
		return false
	if not bool(candidate.get("enabled")):
		return false
	return bool(candidate.call("can_interact", _get_actor(), data))


func _get_actor() -> Node:
	if not String(actor_path).is_empty():
		var configured_actor := get_node_or_null(actor_path)
		if configured_actor != null:
			return configured_actor
	var parent := get_parent()
	if parent != null:
		return parent
	return self


func _candidate_id(candidate: Node) -> String:
	if candidate.has_method("get_interaction_id"):
		return String(candidate.call("get_interaction_id"))
	return String(candidate.name)


func _candidate_prompt(candidate: Node) -> String:
	if candidate.has_method("get_interaction_prompt"):
		return String(candidate.call("get_interaction_prompt", _get_actor()))
	return ""


func _candidate_priority(candidate: Node) -> int:
	var value = candidate.get("priority")
	if typeof(value) == TYPE_INT or typeof(value) == TYPE_FLOAT:
		return int(value)
	return 0


func _candidate_target(candidate: Node) -> String:
	if candidate.is_inside_tree():
		return String(candidate.get_path())
	return String(candidate.name)


func _ensure_result_fields(result: Dictionary, candidate: Node) -> Dictionary:
	if not result.has("errors") or typeof(result["errors"]) != TYPE_ARRAY:
		result["errors"] = []
	if not result.has("warnings") or typeof(result["warnings"]) != TYPE_ARRAY:
		result["warnings"] = []
	if not result.has("ok"):
		result["ok"] = true
	if not result.has("interaction_id"):
		result["interaction_id"] = _candidate_id(candidate)
	if not result.has("target"):
		result["target"] = _candidate_target(candidate)
	return result


func _add_warning(message: String) -> void:
	if not _warnings.has(message):
		_warnings.append(message)


func _append_warnings(result: Dictionary) -> void:
	if not result.has("warnings") or typeof(result["warnings"]) != TYPE_ARRAY:
		result["warnings"] = []
	var result_warnings: Array = result["warnings"]
	for warning in _warnings:
		if not result_warnings.has(warning):
			result_warnings.append(warning)
