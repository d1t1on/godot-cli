class_name Interactor3D
extends Area3D

const InteractionResultData := preload("res://addons/interaction/interaction_result.gd")

var _candidates: Array[Node] = []


func _ready() -> void:
	body_entered.connect(_on_node_entered)
	body_exited.connect(_on_node_exited)
	area_entered.connect(_on_node_entered)
	area_exited.connect(_on_node_exited)


func get_candidates() -> Array:
	var valid_candidates: Array[Node] = []
	var available_candidates: Array[Node] = []
	for candidate in _candidates:
		if not is_instance_valid(candidate):
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


func interact_best() -> Dictionary:
	var candidate := get_best_candidate()
	if candidate == null:
		var result := InteractionResultData.make(false)
		InteractionResultData.add_error(result, "No interactable candidate")
		return result
	return interact_with(candidate)


func interact_with(candidate: Node) -> Dictionary:
	if candidate == null:
		var missing_result := InteractionResultData.make(false)
		InteractionResultData.add_error(missing_result, "No interactable candidate")
		return missing_result
	var result := InteractionResultData.make(false, _candidate_id(candidate), _candidate_target(candidate))
	if not _can_candidate_interact(candidate):
		InteractionResultData.add_error(result, "Interactable candidate is unavailable")
		return result
	if not candidate.has_method("interact"):
		InteractionResultData.add_error(result, "Candidate does not implement interact")
		return result
	var interaction_result = candidate.call("interact", self)
	if interaction_result is Dictionary:
		return interaction_result
	InteractionResultData.add_error(result, "Candidate returned an invalid interaction result")
	return result


func clear_candidates() -> void:
	_candidates.clear()


func _on_node_entered(node: Node) -> void:
	var candidate := _find_interactable(node)
	if candidate != null and not _candidates.has(candidate):
		_candidates.append(candidate)


func _on_node_exited(node: Node) -> void:
	var candidate := _find_interactable(node)
	if candidate != null:
		_candidates.erase(candidate)


func _find_interactable(node: Node) -> Node:
	if node == null:
		return null
	if node.has_method("interact") and node.has_method("can_interact"):
		return node
	for child in node.get_children():
		if child is Node and child.has_method("interact") and child.has_method("can_interact"):
			return child
	return null


func _can_candidate_interact(candidate: Node) -> bool:
	if candidate == null or not candidate.has_method("can_interact"):
		return false
	return bool(candidate.call("can_interact", self))


func _candidate_id(candidate: Node) -> String:
	if candidate.has_method("get_interaction_id"):
		return String(candidate.call("get_interaction_id"))
	return String(candidate.name)


func _candidate_prompt(candidate: Node) -> String:
	if candidate.has_method("get_interaction_prompt"):
		return String(candidate.call("get_interaction_prompt"))
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
