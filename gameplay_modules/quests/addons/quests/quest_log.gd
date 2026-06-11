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


func complete_quest(quest_id: String, data: Dictionary = {}) -> Dictionary:
	var normalized := quest_id.strip_edges()
	var result := QuestResultData.make(true, normalized)
	if not _validate_quest_request(result, normalized, data):
		return result
	_populate_result_from_quest(result, normalized)
	QuestResultData.add_error(result, "Quest completion requires completed objectives: %s" % normalized)
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
	QuestResultData.add_error(result, "apply_state is not implemented")
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
