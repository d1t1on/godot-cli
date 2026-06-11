class_name QuestLog
extends Node

const QuestConstantsData := preload("res://addons/quests/quest_constants.gd")
const QuestResultData := preload("res://addons/quests/quest_result.gd")

signal quest_started(quest_id: String, result: Dictionary)
signal quest_completed(quest_id: String, result: Dictionary)
signal quest_failed(quest_id: String, result: Dictionary)
signal quest_status_changed(quest_id: String, status: String, result: Dictionary)
signal objective_progress_changed(quest_id: String, objective_id: String, progress: int, result: Dictionary)
signal objective_completed(quest_id: String, objective_id: String, result: Dictionary)
signal quests_changed(event: Dictionary)

@export var database: Resource
@export var save_id: StringName
@export var initialize_on_ready: bool = true

var _quests_by_id: Dictionary = {}
var _quest_ids: Array[String] = []
var _initialized: bool = false


func _enter_tree() -> void:
	if not String(save_id).is_empty():
		add_to_group(QuestConstantsData.SAVE_GROUP)


func _ready() -> void:
	if initialize_on_ready:
		initialize_quests()


func initialize_quests(reset: bool = false) -> Dictionary:
	var result := QuestResultData.make(true)
	if _initialized and not reset:
		return result
	if not _validate_database(result):
		return result

	_quests_by_id.clear()
	_quest_ids.clear()
	var ids: Array[String] = []
	ids.assign(database.call("get_quest_ids"))
	for quest_id in ids:
		var definition: Resource = database.call("get_quest", quest_id)
		_quests_by_id[quest_id] = _make_default_quest_entry(quest_id, definition)
		_quest_ids.append(quest_id)
	_initialized = true
	return result


func has_quest(quest_id: String) -> bool:
	if not _ensure_initialized_for_query():
		return false
	return _quests_by_id.has(quest_id.strip_edges())


func start_quest(quest_id: String, data: Dictionary = {}) -> Dictionary:
	var normalized := quest_id.strip_edges()
	var result := QuestResultData.make(true, normalized)
	if not _validate_quest_request(result, normalized, data):
		return result

	var quest: Dictionary = _quests_by_id[normalized]
	var previous_status := String(quest.get("status", ""))
	_populate_result_from_quest(result, normalized)
	if previous_status == QuestConstantsData.STATUS_ACTIVE:
		return result
	if _is_terminal_status(previous_status):
		QuestResultData.add_error(result, "Quest is terminal: %s" % normalized)
		return result
	if previous_status != QuestConstantsData.STATUS_INACTIVE:
		QuestResultData.add_error(result, "Quest has invalid status: %s" % previous_status)
		return result

	_merge_runtime_data(quest, data)
	quest["status"] = QuestConstantsData.STATUS_ACTIVE
	for objective in (quest.get("objectives", []) as Array):
		if String(objective.get("status", "")) == QuestConstantsData.OBJECTIVE_INACTIVE:
			objective["status"] = QuestConstantsData.OBJECTIVE_ACTIVE
	result["previous_status"] = previous_status
	_populate_result_from_quest(result, normalized)
	_emit_quest_status_change(normalized, QuestConstantsData.EVENT_QUEST_STARTED, previous_status, result)
	return result


func advance_objective(quest_id: String, objective_id: String, amount: int = 1, data: Dictionary = {}) -> Dictionary:
	var normalized_quest := quest_id.strip_edges()
	var normalized_objective := objective_id.strip_edges()
	var result := QuestResultData.make(true, normalized_quest, normalized_objective)
	if amount <= 0:
		QuestResultData.add_error(result, "amount must be positive")
		return result
	return _set_objective_progress(normalized_quest, normalized_objective, amount, true, data)


func set_objective_progress(quest_id: String, objective_id: String, amount: int, data: Dictionary = {}) -> Dictionary:
	var normalized_quest := quest_id.strip_edges()
	var normalized_objective := objective_id.strip_edges()
	var result := QuestResultData.make(true, normalized_quest, normalized_objective)
	if amount < 0:
		QuestResultData.add_error(result, "amount must be zero or greater")
		return result
	return _set_objective_progress(normalized_quest, normalized_objective, amount, false, data)


func complete_objective(quest_id: String, objective_id: String, data: Dictionary = {}) -> Dictionary:
	var normalized_quest := quest_id.strip_edges()
	var normalized_objective := objective_id.strip_edges()
	var result := QuestResultData.make(true, normalized_quest, normalized_objective)
	if not _validate_objective_mutation(result, normalized_quest, normalized_objective, data):
		return result
	var objective := _get_objective_runtime(normalized_quest, normalized_objective)
	return _set_objective_progress(normalized_quest, normalized_objective, int(objective.get("target_amount", 0)), false, data)


func complete_quest(quest_id: String, data: Dictionary = {}) -> Dictionary:
	var normalized := quest_id.strip_edges()
	var result := QuestResultData.make(true, normalized)
	if not _validate_quest_request(result, normalized, data):
		return result
	var quest: Dictionary = _quests_by_id[normalized]
	var status := String(quest.get("status", ""))
	_populate_result_from_quest(result, normalized)
	if status == QuestConstantsData.STATUS_COMPLETED:
		result["rewards"] = _rewards_for_quest(normalized)
		return result
	if status == QuestConstantsData.STATUS_FAILED:
		QuestResultData.add_error(result, "Quest is terminal: %s" % normalized)
		return result
	if status != QuestConstantsData.STATUS_ACTIVE:
		QuestResultData.add_error(result, "Quest must be active: %s" % normalized)
		return result
	if not _is_completion_policy_satisfied(normalized):
		QuestResultData.add_error(result, "Quest completion policy is not satisfied: %s" % normalized)
		return result
	_complete_quest_runtime(normalized, result, data)
	return result


func fail_quest(quest_id: String, data: Dictionary = {}) -> Dictionary:
	var normalized := quest_id.strip_edges()
	var result := QuestResultData.make(true, normalized)
	if not _validate_quest_request(result, normalized, data):
		return result

	var quest: Dictionary = _quests_by_id[normalized]
	var previous_status := String(quest.get("status", ""))
	_populate_result_from_quest(result, normalized)
	if previous_status == QuestConstantsData.STATUS_FAILED:
		return result
	if previous_status == QuestConstantsData.STATUS_COMPLETED:
		QuestResultData.add_error(result, "Quest is terminal: %s" % normalized)
		return result
	if previous_status != QuestConstantsData.STATUS_INACTIVE and previous_status != QuestConstantsData.STATUS_ACTIVE:
		QuestResultData.add_error(result, "Quest has invalid status: %s" % previous_status)
		return result

	_merge_runtime_data(quest, data)
	quest["status"] = QuestConstantsData.STATUS_FAILED
	result["previous_status"] = previous_status
	_populate_result_from_quest(result, normalized)
	_emit_quest_status_change(normalized, QuestConstantsData.EVENT_QUEST_FAILED, previous_status, result)
	return result


func set_quest_active(quest_id: String, active: bool) -> Dictionary:
	if active:
		return start_quest(quest_id)

	var normalized := quest_id.strip_edges()
	var result := QuestResultData.make(true, normalized)
	if not _validate_quest_request(result, normalized, {}):
		return result

	var quest: Dictionary = _quests_by_id[normalized]
	var previous_status := String(quest.get("status", ""))
	_populate_result_from_quest(result, normalized)
	if previous_status == QuestConstantsData.STATUS_INACTIVE:
		return result
	if _is_terminal_status(previous_status):
		QuestResultData.add_error(result, "Quest is terminal: %s" % normalized)
		return result
	if previous_status != QuestConstantsData.STATUS_ACTIVE:
		QuestResultData.add_error(result, "Quest has invalid status: %s" % previous_status)
		return result
	if _quest_has_progress(quest):
		QuestResultData.add_error(result, "Cannot deactivate quest with progress: %s" % normalized)
		return result

	quest["status"] = QuestConstantsData.STATUS_INACTIVE
	for objective in (quest.get("objectives", []) as Array):
		if String(objective.get("status", "")) == QuestConstantsData.OBJECTIVE_ACTIVE:
			objective["status"] = QuestConstantsData.OBJECTIVE_INACTIVE
	result["previous_status"] = previous_status
	_populate_result_from_quest(result, normalized)
	_emit_quest_status_change(normalized, QuestConstantsData.EVENT_QUEST_STATUS_CHANGED, previous_status, result)
	return result


func get_quest(quest_id: String) -> Dictionary:
	if not _ensure_initialized_for_query():
		return {}
	var normalized := quest_id.strip_edges()
	if not _quests_by_id.has(normalized):
		return {}
	return (_quests_by_id[normalized] as Dictionary).duplicate(true)


func get_quests() -> Array:
	if not _ensure_initialized_for_query():
		return []
	var copied: Array = []
	for quest_id in _quest_ids:
		copied.append((_quests_by_id[quest_id] as Dictionary).duplicate(true))
	return copied


func clear_runtime_state() -> void:
	_quests_by_id.clear()
	_quest_ids.clear()
	_initialized = false


func get_state() -> Dictionary:
	var quests: Array = []
	if _ensure_initialized_for_query():
		for quest_id in _quest_ids:
			quests.append(_quest_to_state(_quests_by_id[quest_id] as Dictionary))
	return {
		"schema_version": QuestConstantsData.SCHEMA_VERSION,
		"quests": quests,
	}


func apply_state(data: Dictionary) -> Dictionary:
	var result := QuestResultData.make(true)
	var parsed := _parse_state(data, result)
	if not bool(result.get("ok", false)):
		return result
	_quests_by_id = parsed["quests_by_id"]
	_quest_ids.assign(parsed["quest_ids"])
	_initialized = true
	return result


func get_save_id() -> String:
	return String(save_id)


func save_state() -> Dictionary:
	return get_state()


func load_state(data: Dictionary) -> void:
	var result := apply_state(data)
	if not bool(result.get("ok", false)):
		push_warning("QuestLog load_state failed: %s" % ", ".join(PackedStringArray(result.get("errors", []))))


func _make_default_quest_entry(quest_id: String, definition: Resource) -> Dictionary:
	var status := QuestConstantsData.STATUS_ACTIVE if bool(definition.start_active) else QuestConstantsData.STATUS_INACTIVE
	var objectives: Array = []
	for objective in definition.objectives:
		var objective_id := String(objective.objective_id)
		objectives.append(_make_default_objective_entry(objective_id, objective, status))
	return {
		"quest_id": quest_id,
		"status": status,
		"data": (definition.default_data as Dictionary).duplicate(true),
		"objectives": objectives,
	}


func _make_default_objective_entry(objective_id: String, definition: Resource, quest_status: String) -> Dictionary:
	var status := QuestConstantsData.OBJECTIVE_ACTIVE if quest_status == QuestConstantsData.STATUS_ACTIVE else QuestConstantsData.OBJECTIVE_INACTIVE
	return {
		"objective_id": objective_id,
		"status": status,
		"progress": 0,
		"target_amount": int(definition.target_amount),
		"data": (definition.default_data as Dictionary).duplicate(true),
	}


func _validate_quest_request(result: Dictionary, quest_id: String, data: Dictionary) -> bool:
	if not _ensure_initialized(result):
		return false
	if quest_id.is_empty():
		QuestResultData.add_error(result, "quest_id must be non-empty")
		return false
	if not _is_json_compatible(data):
		QuestResultData.add_error(result, "data must be JSON-compatible")
		return false
	if not _quests_by_id.has(quest_id):
		QuestResultData.add_error(result, "Unknown quest_id: %s" % quest_id)
		return false
	return bool(result.get("ok", false))


func _validate_objective_mutation(result: Dictionary, quest_id: String, objective_id: String, data: Dictionary) -> bool:
	if not _validate_quest_request(result, quest_id, data):
		return false
	if objective_id.is_empty():
		QuestResultData.add_error(result, "objective_id must be non-empty")
		return false

	var quest: Dictionary = _quests_by_id[quest_id]
	var quest_status := String(quest.get("status", ""))
	_populate_result_from_quest(result, quest_id)
	if _is_terminal_status(quest_status):
		QuestResultData.add_error(result, "Quest is terminal: %s" % quest_id)
		return false
	if quest_status != QuestConstantsData.STATUS_ACTIVE:
		QuestResultData.add_error(result, "Quest must be active: %s" % quest_id)
		return false

	var objective := _get_objective_runtime(quest_id, objective_id)
	if objective.is_empty():
		QuestResultData.add_error(result, "Unknown objective_id: %s" % objective_id)
		return false
	var objective_status := String(objective.get("status", ""))
	_populate_result_from_objective(result, quest_id, objective_id)
	if objective_status == QuestConstantsData.OBJECTIVE_COMPLETED:
		QuestResultData.add_error(result, "Objective is completed: %s" % objective_id)
		return false
	if objective_status != QuestConstantsData.OBJECTIVE_ACTIVE:
		QuestResultData.add_error(result, "Objective must be active: %s" % objective_id)
		return false
	return bool(result.get("ok", false))


func _set_objective_progress(quest_id: String, objective_id: String, amount: int, is_delta: bool, data: Dictionary) -> Dictionary:
	var result := QuestResultData.make(true, quest_id, objective_id)
	if not _validate_objective_mutation(result, quest_id, objective_id, data):
		return result

	var objective := _get_objective_runtime(quest_id, objective_id)
	var previous_progress := int(objective.get("progress", 0))
	var target_amount := int(objective.get("target_amount", 0))
	var requested_progress := previous_progress + amount if is_delta else amount
	var applied_progress := clampi(requested_progress, 0, target_amount)
	result["previous_progress"] = previous_progress
	result["progress"] = applied_progress
	result["target_amount"] = target_amount
	if requested_progress != applied_progress:
		result["clamped"] = true
		QuestResultData.add_warning(result, "progress was clamped from %d to %d" % [requested_progress, applied_progress])

	_merge_runtime_data(objective, data)
	if applied_progress != previous_progress:
		objective["progress"] = applied_progress
		_populate_result_from_objective(result, quest_id, objective_id)
		_emit_objective_progress_changed(quest_id, objective_id, previous_progress, result)

	if applied_progress >= target_amount:
		_complete_objective_runtime(quest_id, objective_id, result)
		_maybe_auto_complete_quest(quest_id, result)
	else:
		_populate_result_from_objective(result, quest_id, objective_id)
	return result


func _complete_objective_runtime(quest_id: String, objective_id: String, result: Dictionary) -> void:
	var objective := _get_objective_runtime(quest_id, objective_id)
	if objective.is_empty():
		return
	if String(objective.get("status", "")) == QuestConstantsData.OBJECTIVE_COMPLETED:
		return
	objective["status"] = QuestConstantsData.OBJECTIVE_COMPLETED
	objective["progress"] = int(objective.get("target_amount", 0))
	_populate_result_from_objective(result, quest_id, objective_id)
	var event := _make_objective_event(QuestConstantsData.EVENT_OBJECTIVE_COMPLETED, quest_id, objective_id, int(objective.get("progress", 0)))
	QuestResultData.add_event(result, event)
	objective_completed.emit(quest_id, objective_id, result)
	quests_changed.emit(event)


func _is_completion_policy_satisfied(quest_id: String) -> bool:
	if database == null or not database.has_method("get_quest") or not _quests_by_id.has(quest_id):
		return false
	var definition: Resource = database.call("get_quest", quest_id)
	if definition == null:
		return false
	var required_count := 0
	var completed_count := 0
	for objective_definition in definition.objectives:
		if bool(objective_definition.optional):
			continue
		required_count += 1
		var objective_id := String(objective_definition.objective_id)
		var objective := _get_objective_runtime(quest_id, objective_id)
		if String(objective.get("status", "")) == QuestConstantsData.OBJECTIVE_COMPLETED:
			completed_count += 1
	if required_count == 0:
		return false
	var policy := String(definition.completion_policy)
	if policy == QuestConstantsData.POLICY_ALL:
		return completed_count == required_count
	if policy == QuestConstantsData.POLICY_ANY:
		return completed_count > 0
	return false


func _maybe_auto_complete_quest(quest_id: String, result: Dictionary) -> void:
	if database == null or not database.has_method("get_quest"):
		return
	var definition: Resource = database.call("get_quest", quest_id)
	if definition == null or not bool(definition.auto_complete):
		return
	if _is_completion_policy_satisfied(quest_id):
		_complete_quest_runtime(quest_id, result, {})


func _complete_quest_runtime(quest_id: String, result: Dictionary, data: Dictionary) -> void:
	if not _quests_by_id.has(quest_id):
		return
	var quest: Dictionary = _quests_by_id[quest_id]
	var previous_status := String(quest.get("status", ""))
	if previous_status == QuestConstantsData.STATUS_COMPLETED:
		result["rewards"] = _rewards_for_quest(quest_id)
		_populate_result_from_quest(result, quest_id)
		return

	_merge_runtime_data(quest, data)
	var definition: Resource = database.call("get_quest", quest_id)
	for objective_definition in definition.objectives:
		if bool(objective_definition.optional):
			continue
		var objective_id := String(objective_definition.objective_id)
		var objective := _get_objective_runtime(quest_id, objective_id)
		if objective.is_empty():
			continue
		if String(objective.get("status", "")) != QuestConstantsData.OBJECTIVE_COMPLETED:
			objective["progress"] = int(objective.get("target_amount", 0))
			objective["status"] = QuestConstantsData.OBJECTIVE_COMPLETED
	quest["status"] = QuestConstantsData.STATUS_COMPLETED
	result["previous_status"] = previous_status
	result["rewards"] = _rewards_for_quest(quest_id)
	_populate_result_from_quest(result, quest_id)
	_emit_quest_status_change(quest_id, QuestConstantsData.EVENT_QUEST_COMPLETED, previous_status, result)


func _parse_state(data: Dictionary, result: Dictionary) -> Dictionary:
	var parsed := {"quests_by_id": {}, "quest_ids": []}
	var saved_schema := _parse_integer_field(data.get("schema_version", null), "schema_version", result)
	if saved_schema != QuestConstantsData.SCHEMA_VERSION:
		QuestResultData.add_error(result, "schema_version must be %d" % QuestConstantsData.SCHEMA_VERSION)

	var raw_quests = data.get("quests", null)
	if not (raw_quests is Array):
		QuestResultData.add_error(result, "quests must be an Array")
		return parsed
	if not _validate_database(result):
		return parsed

	var saved_by_id := {}
	var seen_quests := {}
	var saved_quests: Array = raw_quests
	for index in range(saved_quests.size()):
		var saved_value = saved_quests[index]
		if not (saved_value is Dictionary):
			QuestResultData.add_error(result, "quests[%d] must be a Dictionary" % index)
			continue
		var saved_quest: Dictionary = saved_value
		var raw_quest_id = saved_quest.get("quest_id", "")
		if typeof(raw_quest_id) != TYPE_STRING and typeof(raw_quest_id) != TYPE_STRING_NAME:
			QuestResultData.add_error(result, "quests[%d].quest_id must be a string" % index)
			continue
		var quest_id := String(raw_quest_id)
		var normalized := quest_id.strip_edges()
		if normalized.is_empty():
			QuestResultData.add_error(result, "quests[%d].quest_id must be non-empty" % index)
			continue
		if normalized != quest_id:
			QuestResultData.add_error(result, "quests[%d].quest_id must not contain leading or trailing whitespace" % index)
			continue
		if seen_quests.has(normalized):
			QuestResultData.add_error(result, "Duplicate quest_id: %s" % normalized)
			continue
		seen_quests[normalized] = true
		if not bool(database.call("has_quest", normalized)):
			QuestResultData.add_error(result, "Unknown quest_id: %s" % normalized)
			continue
		saved_by_id[normalized] = saved_quest

	if not bool(result.get("ok", false)):
		return parsed

	var ids: Array[String] = []
	ids.assign(database.call("get_quest_ids"))
	for quest_id in ids:
		var definition: Resource = database.call("get_quest", quest_id)
		var quest_entry: Dictionary
		if saved_by_id.has(quest_id):
			quest_entry = _parse_quest_state(saved_by_id[quest_id], definition, result)
		else:
			quest_entry = _make_default_quest_entry(quest_id, definition)
		(parsed["quests_by_id"] as Dictionary)[quest_id] = quest_entry
		(parsed["quest_ids"] as Array).append(quest_id)
	return parsed


func _parse_quest_state(saved_quest: Dictionary, definition: Resource, result: Dictionary) -> Dictionary:
	var quest_id := String(definition.quest_id)
	var status := _parse_status(saved_quest.get("status", ""), [QuestConstantsData.STATUS_INACTIVE, QuestConstantsData.STATUS_ACTIVE, QuestConstantsData.STATUS_COMPLETED, QuestConstantsData.STATUS_FAILED], "quest status", result)
	var raw_data = saved_quest.get("data", {})
	var quest_data := {}
	if not (raw_data is Dictionary):
		QuestResultData.add_error(result, "quest data must be a Dictionary for quest_id: %s" % quest_id)
	elif not _is_json_compatible(raw_data):
		QuestResultData.add_error(result, "data must be JSON-compatible for quest_id: %s" % quest_id)
	else:
		quest_data = (raw_data as Dictionary).duplicate(true)

	var raw_objectives = saved_quest.get("objectives", null)
	if not (raw_objectives is Array):
		QuestResultData.add_error(result, "objectives must be an Array for quest_id: %s" % quest_id)
		return _make_default_quest_entry(quest_id, definition)

	var saved_by_id := {}
	var seen_objectives := {}
	var valid_objective_ids := {}
	for objective_definition in definition.objectives:
		valid_objective_ids[String(objective_definition.objective_id)] = true

	var saved_objectives: Array = raw_objectives
	for index in range(saved_objectives.size()):
		var saved_value = saved_objectives[index]
		if not (saved_value is Dictionary):
			QuestResultData.add_error(result, "objectives[%d] must be a Dictionary for quest_id: %s" % [index, quest_id])
			continue
		var saved_objective: Dictionary = saved_value
		var raw_objective_id = saved_objective.get("objective_id", "")
		if typeof(raw_objective_id) != TYPE_STRING and typeof(raw_objective_id) != TYPE_STRING_NAME:
			QuestResultData.add_error(result, "objectives[%d].objective_id must be a string for quest_id: %s" % [index, quest_id])
			continue
		var objective_id := String(raw_objective_id)
		var normalized := objective_id.strip_edges()
		if normalized.is_empty():
			QuestResultData.add_error(result, "objectives[%d].objective_id must be non-empty for quest_id: %s" % [index, quest_id])
			continue
		if normalized != objective_id:
			QuestResultData.add_error(result, "objectives[%d].objective_id must not contain leading or trailing whitespace for quest_id: %s" % [index, quest_id])
			continue
		if seen_objectives.has(normalized):
			QuestResultData.add_error(result, "Duplicate objective_id: %s" % normalized)
			continue
		seen_objectives[normalized] = true
		if not valid_objective_ids.has(normalized):
			QuestResultData.add_error(result, "Unknown objective_id: %s" % normalized)
			continue
		saved_by_id[normalized] = saved_objective

	var objectives: Array = []
	for objective_definition in definition.objectives:
		var objective_id := String(objective_definition.objective_id)
		if saved_by_id.has(objective_id):
			objectives.append(_parse_objective_state(saved_by_id[objective_id], objective_definition, status, result))
		else:
			objectives.append(_make_default_objective_entry(objective_id, objective_definition, status))
	return {
		"quest_id": quest_id,
		"status": status,
		"data": quest_data,
		"objectives": objectives,
	}


func _parse_objective_state(saved_objective: Dictionary, definition: Resource, parent_status: String, result: Dictionary) -> Dictionary:
	var objective_id := String(definition.objective_id)
	var status := _parse_status(saved_objective.get("status", ""), [QuestConstantsData.OBJECTIVE_INACTIVE, QuestConstantsData.OBJECTIVE_ACTIVE, QuestConstantsData.OBJECTIVE_COMPLETED], "objective status", result)
	var progress := _parse_integer_field(saved_objective.get("progress", null), "progress", result)
	var target_amount := int(definition.target_amount)
	if progress < 0:
		QuestResultData.add_error(result, "progress must be zero or greater for objective_id: %s" % objective_id)
	if progress > target_amount:
		QuestResultData.add_error(result, "progress must not exceed target_amount for objective_id: %s" % objective_id)
	if status == QuestConstantsData.OBJECTIVE_INACTIVE and progress != 0:
		QuestResultData.add_error(result, "inactive objective progress must be zero for objective_id: %s" % objective_id)
	if status == QuestConstantsData.OBJECTIVE_ACTIVE:
		if parent_status == QuestConstantsData.STATUS_INACTIVE:
			QuestResultData.add_error(result, "inactive quest cannot contain active objectives")
		if progress >= target_amount:
			QuestResultData.add_error(result, "active objective progress must be below target_amount for objective_id: %s" % objective_id)
	if status == QuestConstantsData.OBJECTIVE_COMPLETED and progress != target_amount:
		QuestResultData.add_error(result, "completed objective progress must equal target_amount for objective_id: %s" % objective_id)

	var raw_data = saved_objective.get("data", {})
	var objective_data := {}
	if not (raw_data is Dictionary):
		QuestResultData.add_error(result, "objective data must be a Dictionary for objective_id: %s" % objective_id)
	elif not _is_json_compatible(raw_data):
		QuestResultData.add_error(result, "data must be JSON-compatible for objective_id: %s" % objective_id)
	else:
		objective_data = (raw_data as Dictionary).duplicate(true)

	return {
		"objective_id": objective_id,
		"status": status,
		"progress": progress,
		"target_amount": target_amount,
		"data": objective_data,
	}


func _parse_status(value: Variant, allowed: Array, field_name: String, result: Dictionary) -> String:
	if typeof(value) != TYPE_STRING and typeof(value) != TYPE_STRING_NAME:
		QuestResultData.add_error(result, "%s must be a string" % field_name)
		return ""
	var status := String(value)
	if not allowed.has(status):
		QuestResultData.add_error(result, "%s is invalid: %s" % [field_name, status])
	return status


func _parse_integer_field(value: Variant, field_name: String, result: Dictionary) -> int:
	if typeof(value) == TYPE_INT:
		return int(value)
	if typeof(value) == TYPE_FLOAT:
		var float_value := float(value)
		if not is_nan(float_value) and not is_inf(float_value) and float_value == floor(float_value):
			return int(float_value)
	QuestResultData.add_error(result, "%s must be an integer" % field_name)
	return 0


func _validate_database(result: Dictionary) -> bool:
	if database == null:
		QuestResultData.add_error(result, "database must be assigned")
		return false
	if not database.has_method("validate") or not database.has_method("get_quest") or not database.has_method("has_quest") or not database.has_method("get_quest_ids"):
		QuestResultData.add_error(result, "database must be a QuestDatabase")
		return false
	var database_result: Dictionary = database.call("validate")
	if not bool(database_result.get("ok", false)):
		for error in database_result.get("errors", []):
			QuestResultData.add_error(result, String(error))
		for warning in database_result.get("warnings", []):
			QuestResultData.add_warning(result, String(warning))
		return false
	return true


func _ensure_initialized(result: Dictionary) -> bool:
	if _initialized:
		return true
	var init_result := initialize_quests()
	if bool(init_result.get("ok", false)):
		return true
	for error in init_result.get("errors", []):
		QuestResultData.add_error(result, String(error))
	for warning in init_result.get("warnings", []):
		QuestResultData.add_warning(result, String(warning))
	return false


func _ensure_initialized_for_query() -> bool:
	if _initialized:
		return true
	var result := initialize_quests()
	return bool(result.get("ok", false))


func _populate_result_from_quest(result: Dictionary, quest_id: String) -> void:
	if not _quests_by_id.has(quest_id):
		return
	var quest: Dictionary = _quests_by_id[quest_id]
	result["status"] = String(quest.get("status", ""))
	result["quest"] = quest.duplicate(true)
	result["data"] = (quest.get("data", {}) as Dictionary).duplicate(true)


func _populate_result_from_objective(result: Dictionary, quest_id: String, objective_id: String) -> void:
	_populate_result_from_quest(result, quest_id)
	var objective := _get_objective_runtime(quest_id, objective_id)
	if objective.is_empty():
		return
	result["objective_id"] = objective_id
	result["progress"] = int(objective.get("progress", 0))
	result["target_amount"] = int(objective.get("target_amount", 0))
	result["data"] = (objective.get("data", {}) as Dictionary).duplicate(true)


func _get_objective_runtime(quest_id: String, objective_id: String) -> Dictionary:
	if not _quests_by_id.has(quest_id):
		return {}
	var quest: Dictionary = _quests_by_id[quest_id]
	for objective in (quest.get("objectives", []) as Array):
		if String(objective.get("objective_id", "")) == objective_id:
			return objective
	return {}


func _merge_runtime_data(quest: Dictionary, data: Dictionary) -> void:
	if data.is_empty():
		return
	var runtime_data: Dictionary = quest.get("data", {})
	var copied_data := data.duplicate(true)
	for key in copied_data.keys():
		runtime_data[key] = copied_data[key]
	quest["data"] = runtime_data


func _quest_has_progress(quest: Dictionary) -> bool:
	for objective in (quest.get("objectives", []) as Array):
		if int(objective.get("progress", 0)) > 0:
			return true
		if String(objective.get("status", "")) == QuestConstantsData.OBJECTIVE_COMPLETED:
			return true
	return false


func _is_terminal_status(status: String) -> bool:
	return status == QuestConstantsData.STATUS_COMPLETED or status == QuestConstantsData.STATUS_FAILED


func _emit_quest_status_change(quest_id: String, event_type: String, previous_status: String, result: Dictionary) -> void:
	var status := String(result.get("status", ""))
	if event_type == QuestConstantsData.EVENT_QUEST_STATUS_CHANGED:
		var changed_event := _make_quest_event(QuestConstantsData.EVENT_QUEST_STATUS_CHANGED, quest_id, status, previous_status)
		QuestResultData.add_event(result, changed_event)
		quest_status_changed.emit(quest_id, status, result)
		quests_changed.emit(changed_event)
		return

	var primary_event := _make_quest_event(event_type, quest_id, status, previous_status)
	QuestResultData.add_event(result, primary_event)
	if event_type == QuestConstantsData.EVENT_QUEST_STARTED:
		quest_started.emit(quest_id, result)
	elif event_type == QuestConstantsData.EVENT_QUEST_COMPLETED:
		quest_completed.emit(quest_id, result)
	elif event_type == QuestConstantsData.EVENT_QUEST_FAILED:
		quest_failed.emit(quest_id, result)
	quests_changed.emit(primary_event)

	var status_event := _make_quest_event(QuestConstantsData.EVENT_QUEST_STATUS_CHANGED, quest_id, status, previous_status)
	QuestResultData.add_event(result, status_event)
	quest_status_changed.emit(quest_id, status, result)
	quests_changed.emit(status_event)


func _emit_objective_progress_changed(quest_id: String, objective_id: String, previous_progress: int, result: Dictionary) -> void:
	var progress := int(result.get("progress", 0))
	var event := _make_objective_event(QuestConstantsData.EVENT_OBJECTIVE_PROGRESS_CHANGED, quest_id, objective_id, progress, previous_progress)
	QuestResultData.add_event(result, event)
	objective_progress_changed.emit(quest_id, objective_id, progress, result)
	quests_changed.emit(event)


func _make_quest_event(event_type: String, quest_id: String, status: String, previous_status: String = "") -> Dictionary:
	return {
		"ok": true,
		"type": event_type,
		"quest_id": quest_id,
		"objective_id": "",
		"status": status,
		"previous_status": previous_status,
		"warnings": [],
		"errors": [],
	}


func _make_objective_event(event_type: String, quest_id: String, objective_id: String, progress: int, previous_progress: int = 0) -> Dictionary:
	return {
		"ok": true,
		"type": event_type,
		"quest_id": quest_id,
		"objective_id": objective_id,
		"status": String((_quests_by_id.get(quest_id, {}) as Dictionary).get("status", "")),
		"progress": progress,
		"previous_progress": previous_progress,
		"warnings": [],
		"errors": [],
	}


func _rewards_for_quest(quest_id: String) -> Dictionary:
	if database == null or not database.has_method("get_quest"):
		return {}
	var definition: Resource = database.call("get_quest", quest_id)
	if definition == null:
		return {}
	return (definition.rewards as Dictionary).duplicate(true)


func _quest_to_state(quest: Dictionary) -> Dictionary:
	var objectives: Array = []
	for objective in (quest.get("objectives", []) as Array):
		objectives.append({
			"objective_id": String(objective.get("objective_id", "")),
			"status": String(objective.get("status", "")),
			"progress": int(objective.get("progress", 0)),
			"data": (objective.get("data", {}) as Dictionary).duplicate(true),
		})
	return {
		"quest_id": String(quest.get("quest_id", "")),
		"status": String(quest.get("status", "")),
		"data": (quest.get("data", {}) as Dictionary).duplicate(true),
		"objectives": objectives,
	}


func _is_json_compatible(value: Variant, seen: Array = []) -> bool:
	var value_type := typeof(value)
	if value == null:
		return true
	if value_type == TYPE_BOOL or value_type == TYPE_INT or value_type == TYPE_STRING or value_type == TYPE_STRING_NAME:
		return true
	if value_type == TYPE_FLOAT:
		var number := float(value)
		return not is_nan(number) and not is_inf(number)
	if value is Array:
		if _contains_same_container(seen, value):
			return false
		seen.append(value)
		for item in value:
			if not _is_json_compatible(item, seen):
				seen.pop_back()
				return false
		seen.pop_back()
		return true
	if value is Dictionary:
		if _contains_same_container(seen, value):
			return false
		seen.append(value)
		for key in value.keys():
			if typeof(key) != TYPE_STRING and typeof(key) != TYPE_STRING_NAME:
				seen.pop_back()
				return false
			if not _is_json_compatible(value[key], seen):
				seen.pop_back()
				return false
		seen.pop_back()
		return true
	return false


func _contains_same_container(seen: Array, value: Variant) -> bool:
	for container in seen:
		if is_same(container, value):
			return true
	return false
