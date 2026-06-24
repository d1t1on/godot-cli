class_name DialogueRunner
extends Node

const DialogueConstantsData := preload("res://addons/dialogue/dialogue_constants.gd")
const DialogueResultData := preload("res://addons/dialogue/dialogue_result.gd")
const DialogueLineDefinitionData := preload("res://addons/dialogue/dialogue_line_definition.gd")
const DialogueChoiceDefinitionData := preload("res://addons/dialogue/dialogue_choice_definition.gd")

signal dialogue_started(dialogue_id: String, result: Dictionary)
signal dialogue_ended(dialogue_id: String, result: Dictionary)
signal line_entered(dialogue_id: String, line_id: String, result: Dictionary)
signal line_exited(dialogue_id: String, line_id: String, result: Dictionary)
signal choice_selected(dialogue_id: String, choice_id: String, result: Dictionary)
signal dialogues_changed(event: Dictionary)

@export var database: Resource
@export var save_id: StringName
@export var initialize_on_ready: bool = true

# runtime state
var _dialogues_by_id: Dictionary = {}
var _dialogue_ids: Array[String] = []
var _initialized: bool = false
var _active_dialogue_id: String = ""
var _current_line_id: String = ""
var _status: String = "inactive"
var _variables: Dictionary = {}


func _enter_tree() -> void:
	if not String(save_id).is_empty():
		add_to_group(DialogueConstantsData.SAVE_GROUP)


func _ready() -> void:
	if initialize_on_ready:
		initialize_dialogues()


func initialize_dialogues(reset: bool = false) -> Dictionary:
	var result := DialogueResultData.make(true)
	if _initialized and not reset:
		return result
	if not _validate_database(result):
		return result

	_dialogues_by_id.clear()
	_dialogue_ids.clear()
	var ids: Array[String] = []
	ids.assign(database.call("get_dialogue_ids"))
	for dialogue_id in ids:
		var definition: Resource = database.call("get_dialogue", dialogue_id)
		_dialogues_by_id[dialogue_id] = _make_default_dialogue_entry(dialogue_id, definition)
		_dialogue_ids.append(dialogue_id)
	_initialized = true
	return result


func has_dialogue(dialogue_id: String) -> bool:
	if not _ensure_initialized_for_query():
		return false
	return _dialogues_by_id.has(dialogue_id.strip_edges())


func start_dialogue(dialogue_id: String, data: Dictionary = {}) -> Dictionary:
	var normalized := dialogue_id.strip_edges()
	var result := DialogueResultData.make(true, normalized)
	if not _validate_dialogue_request(result, normalized, data):
		return result

	var dialogue: Dictionary = _dialogues_by_id[normalized]
	var previous_status := String(dialogue.get("status", ""))
	_populate_result_from_dialogue(result, normalized)
	if previous_status == DialogueConstantsData.STATUS_ACTIVE:
		return result
	if _is_terminal_status(previous_status):
		DialogueResultData.add_error(result, "Dialogue is terminal: %s" % normalized)
		return result
	if previous_status != DialogueConstantsData.STATUS_INACTIVE:
		DialogueResultData.add_error(result, "Dialogue has invalid status: %s" % previous_status)
		return result

	_merge_runtime_data(dialogue, data)
	dialogue["status"] = DialogueConstantsData.STATUS_ACTIVE
	_variables = (dialogue.get("default_variables", {}) as Dictionary).duplicate(true)
	_active_dialogue_id = normalized
	_status = DialogueConstantsData.STATUS_ACTIVE
	var definition: Resource = database.call("get_dialogue", normalized)
	var start_line_id := String(definition.start_line_id)
	if not start_line_id.is_empty():
		_enter_line(normalized, start_line_id, result)
	else:
		_current_line_id = ""
	result["previous_status"] = previous_status
	_populate_result_from_dialogue(result, normalized)
	var event := _make_dialogue_event(DialogueConstantsData.EVENT_DIALOGUE_STARTED, normalized, DialogueConstantsData.STATUS_ACTIVE, previous_status)
	DialogueResultData.add_event(result, event)
	dialogue_started.emit(normalized, result)
	dialogues_changed.emit(event)
	return result


func stop_dialogue(data: Dictionary = {}) -> Dictionary:
	var result := DialogueResultData.make(true, _active_dialogue_id)
	if _active_dialogue_id.is_empty():
		DialogueResultData.add_error(result, "No active dialogue")
		return result
	if not _is_json_compatible(data):
		DialogueResultData.add_error(result, "data must be JSON-compatible")
		return result
	var dialogue: Dictionary = _dialogues_by_id[_active_dialogue_id]
	var previous_status := String(dialogue.get("status", ""))
	if not _current_line_id.is_empty():
		_exit_line(_active_dialogue_id, _current_line_id, result)
	_merge_runtime_data(dialogue, data)
	dialogue["status"] = DialogueConstantsData.STATUS_COMPLETED
	_status = DialogueConstantsData.STATUS_COMPLETED
	result["previous_status"] = previous_status
	_populate_result_from_dialogue(result, _active_dialogue_id)
	var event := _make_dialogue_event(DialogueConstantsData.EVENT_DIALOGUE_ENDED, _active_dialogue_id, DialogueConstantsData.STATUS_COMPLETED, previous_status)
	DialogueResultData.add_event(result, event)
	dialogue_ended.emit(_active_dialogue_id, result)
	dialogues_changed.emit(event)
	_active_dialogue_id = ""
	_current_line_id = ""
	return result


func get_current_line() -> Dictionary:
	if _active_dialogue_id.is_empty() or _current_line_id.is_empty():
		return {}
	var definition: Resource = database.call("get_dialogue", _active_dialogue_id)
	if definition == null:
		return {}
	var line: Resource = _get_line_definition(definition, _current_line_id)
	if line == null:
		return {}
	return _make_line_snapshot(line)


func get_choices() -> Array:
	if _active_dialogue_id.is_empty() or _current_line_id.is_empty():
		return []
	var definition: Resource = database.call("get_dialogue", _active_dialogue_id)
	if definition == null:
		return []
	var line: Resource = _get_line_definition(definition, _current_line_id)
	if line == null:
		return []
	var choices: Array = []
	for choice in line.choices:
		var choice_definition = _choice_or_null(choice)
		if choice_definition == null:
			continue
		var available := _evaluate_condition(String(choice_definition.condition), _variables)
		choices.append({
			"choice_id": String(choice_definition.choice_id),
			"display_name": String(choice_definition.display_name),
			"description": String(choice_definition.description),
			"next_line_id": String(choice_definition.next_line_id),
			"available": available,
		})
	return choices


func select_choice(choice_id: String, data: Dictionary = {}) -> Dictionary:
	var normalized := choice_id.strip_edges()
	var result := DialogueResultData.make(true, _active_dialogue_id, _current_line_id, normalized)
	if _active_dialogue_id.is_empty():
		DialogueResultData.add_error(result, "No active dialogue")
		return result
	if not _is_json_compatible(data):
		DialogueResultData.add_error(result, "data must be JSON-compatible")
		return result
	var definition: Resource = database.call("get_dialogue", _active_dialogue_id)
	if definition == null:
		DialogueResultData.add_error(result, "Unknown dialogue_id: %s" % _active_dialogue_id)
		return result
	var line: Resource = _get_line_definition(definition, _current_line_id)
	if line == null:
		DialogueResultData.add_error(result, "Unknown line_id: %s" % _current_line_id)
		return result
	var choice: Resource = _get_choice_definition(line, normalized)
	if choice == null:
		DialogueResultData.add_error(result, "Unknown choice_id: %s" % normalized)
		return result
	if not _evaluate_condition(String(choice.condition), _variables):
		DialogueResultData.add_error(result, "Choice is not available: %s" % normalized)
		return result

	_exit_line(_active_dialogue_id, _current_line_id, result)
	var choice_event := _make_choice_event(DialogueConstantsData.EVENT_CHOICE_SELECTED, _active_dialogue_id, normalized)
	DialogueResultData.add_event(result, choice_event)
	choice_selected.emit(_active_dialogue_id, normalized, result)
	dialogues_changed.emit(choice_event)
	_merge_runtime_data(_dialogues_by_id[_active_dialogue_id], data)
	for key in choice.apply_variables.keys():
		_variables[key] = choice.apply_variables[key]
	var next_line_id := String(choice.next_line_id).strip_edges()
	if next_line_id.is_empty():
		_complete_dialogue(result)
	else:
		_enter_line(_active_dialogue_id, next_line_id, result)
	return result


func advance(data: Dictionary = {}) -> Dictionary:
	var result := DialogueResultData.make(true, _active_dialogue_id, _current_line_id)
	if _active_dialogue_id.is_empty():
		DialogueResultData.add_error(result, "No active dialogue")
		return result
	if not _is_json_compatible(data):
		DialogueResultData.add_error(result, "data must be JSON-compatible")
		return result
	var definition: Resource = database.call("get_dialogue", _active_dialogue_id)
	if definition == null:
		DialogueResultData.add_error(result, "Unknown dialogue_id: %s" % _active_dialogue_id)
		return result
	var line: Resource = _get_line_definition(definition, _current_line_id)
	if line == null:
		DialogueResultData.add_error(result, "Unknown line_id: %s" % _current_line_id)
		return result
	if not (line.choices as Array).is_empty():
		DialogueResultData.add_error(result, "Cannot advance a line with choices")
		return result
	var next_line_id := String(line.next_line_id).strip_edges()
	if next_line_id.is_empty():
		_exit_line(_active_dialogue_id, _current_line_id, result)
		_complete_dialogue(result)
	else:
		_exit_line(_active_dialogue_id, _current_line_id, result)
		_merge_runtime_data(_dialogues_by_id[_active_dialogue_id], data)
		_enter_line(_active_dialogue_id, next_line_id, result)
	return result


func get_variable(key: String) -> Variant:
	return _variables.get(key)


func set_variable(key: String, value: Variant) -> Dictionary:
	var result := DialogueResultData.make(true, _active_dialogue_id, _current_line_id)
	if not _is_json_compatible(value):
		DialogueResultData.add_error(result, "value must be JSON-compatible")
		return result
	_variables[key] = value
	var event := _make_dialogue_event(DialogueConstantsData.EVENT_DIALOGUES_CHANGED, _active_dialogue_id, _status, "")
	DialogueResultData.add_event(result, event)
	dialogues_changed.emit(event)
	return result


func get_variables() -> Dictionary:
	return _variables.duplicate(true)


func get_dialogue(dialogue_id: String) -> Dictionary:
	if not _ensure_initialized_for_query():
		return {}
	var normalized := dialogue_id.strip_edges()
	if not _dialogues_by_id.has(normalized):
		return {}
	return (_dialogues_by_id[normalized] as Dictionary).duplicate(true)


func get_state() -> Dictionary:
	var dialogues: Array = []
	if _ensure_initialized_for_query():
		for dialogue_id in _dialogue_ids:
			dialogues.append(_dialogue_to_state(_dialogues_by_id[dialogue_id] as Dictionary))
	return {
		"schema_version": DialogueConstantsData.SCHEMA_VERSION,
		"active_dialogue_id": _active_dialogue_id,
		"current_line_id": _current_line_id,
		"status": _status,
		"variables": _variables.duplicate(true),
		"dialogues": dialogues,
	}


func apply_state(data: Dictionary) -> Dictionary:
	var result := DialogueResultData.make(true)
	var parsed := _parse_state(data, result)
	if not bool(result.get("ok", false)):
		return result
	_dialogues_by_id = parsed["dialogues_by_id"]
	_dialogue_ids.assign(parsed["dialogue_ids"])
	_active_dialogue_id = parsed["active_dialogue_id"]
	_current_line_id = parsed["current_line_id"]
	_status = parsed["status"]
	_variables = parsed["variables"]
	_initialized = true
	var event := _make_dialogue_event(DialogueConstantsData.EVENT_DIALOGUES_CHANGED, _active_dialogue_id, _status, "")
	DialogueResultData.add_event(result, event)
	dialogues_changed.emit(event)
	return result


func clear_runtime_state() -> void:
	_dialogues_by_id.clear()
	_dialogue_ids.clear()
	_initialized = false
	_active_dialogue_id = ""
	_current_line_id = ""
	_status = DialogueConstantsData.STATUS_INACTIVE
	_variables.clear()


func get_save_id() -> String:
	return String(save_id)


func save_state() -> Dictionary:
	return get_state()


func load_state(data: Dictionary) -> void:
	var result := apply_state(data)
	if not bool(result.get("ok", false)):
		push_warning("DialogueRunner load_state failed: %s" % ", ".join(PackedStringArray(result.get("errors", []))))


func _make_default_dialogue_entry(dialogue_id: String, definition: Resource) -> Dictionary:
	return {
		"dialogue_id": dialogue_id,
		"status": DialogueConstantsData.STATUS_INACTIVE,
		"default_variables": (definition.default_variables as Dictionary).duplicate(true),
		"data": (definition.default_data as Dictionary).duplicate(true),
	}


func _validate_database(result: Dictionary) -> bool:
	if database == null:
		DialogueResultData.add_error(result, "database must be assigned")
		return false
	if not database.has_method("validate") or not database.has_method("get_dialogue") or not database.has_method("has_dialogue") or not database.has_method("get_dialogue_ids"):
		DialogueResultData.add_error(result, "database must be a DialogueDatabase")
		return false
	var database_result: Dictionary = database.call("validate")
	if not bool(database_result.get("ok", false)):
		for error in database_result.get("errors", []):
			DialogueResultData.add_error(result, String(error))
		for warning in database_result.get("warnings", []):
			DialogueResultData.add_warning(result, String(warning))
		return false
	return true


func _ensure_initialized(result: Dictionary) -> bool:
	if _initialized:
		return true
	var init_result := initialize_dialogues()
	if bool(init_result.get("ok", false)):
		return true
	for error in init_result.get("errors", []):
		DialogueResultData.add_error(result, String(error))
	for warning in init_result.get("warnings", []):
		DialogueResultData.add_warning(result, String(warning))
	return false


func _ensure_initialized_for_query() -> bool:
	if _initialized:
		return true
	var result := initialize_dialogues()
	return bool(result.get("ok", false))


func _validate_dialogue_request(result: Dictionary, dialogue_id: String, data: Dictionary) -> bool:
	if not _ensure_initialized(result):
		return false
	if dialogue_id.is_empty():
		DialogueResultData.add_error(result, "dialogue_id must be non-empty")
		return false
	if not _is_json_compatible(data):
		DialogueResultData.add_error(result, "data must be JSON-compatible")
		return false
	if not _dialogues_by_id.has(dialogue_id):
		DialogueResultData.add_error(result, "Unknown dialogue_id: %s" % dialogue_id)
		return false
	return bool(result.get("ok", false))


func _is_terminal_status(status: String) -> bool:
	return status == DialogueConstantsData.STATUS_COMPLETED


func _populate_result_from_dialogue(result: Dictionary, dialogue_id: String) -> void:
	if not _dialogues_by_id.has(dialogue_id):
		return
	var dialogue: Dictionary = _dialogues_by_id[dialogue_id]
	result["status"] = String(dialogue.get("status", ""))
	result["dialogue"] = dialogue.duplicate(true)
	result["data"] = (dialogue.get("data", {}) as Dictionary).duplicate(true)
	result["variables"] = _variables.duplicate(true)


func _merge_runtime_data(dialogue: Dictionary, data: Dictionary) -> void:
	if data.is_empty():
		return
	var runtime_data: Dictionary = dialogue.get("data", {})
	var copied_data := data.duplicate(true)
	for key in copied_data.keys():
		runtime_data[key] = copied_data[key]
	dialogue["data"] = runtime_data


func _enter_line(dialogue_id: String, line_id: String, result: Dictionary) -> void:
	_current_line_id = line_id
	var definition: Resource = database.call("get_dialogue", dialogue_id)
	var line: Resource = _get_line_definition(definition, line_id)
	if line == null:
		return
	for key in line.apply_variables.keys():
		_variables[key] = line.apply_variables[key]
	var event := _make_line_event(DialogueConstantsData.EVENT_LINE_ENTERED, dialogue_id, line_id)
	DialogueResultData.add_event(result, event)
	line_entered.emit(dialogue_id, line_id, result)
	dialogues_changed.emit(event)


func _exit_line(dialogue_id: String, line_id: String, result: Dictionary) -> void:
	var event := _make_line_event(DialogueConstantsData.EVENT_LINE_EXITED, dialogue_id, line_id)
	DialogueResultData.add_event(result, event)
	line_exited.emit(dialogue_id, line_id, result)
	dialogues_changed.emit(event)


func _complete_dialogue(result: Dictionary) -> void:
	if _active_dialogue_id.is_empty():
		return
	var dialogue: Dictionary = _dialogues_by_id[_active_dialogue_id]
	var previous_status := String(dialogue.get("status", ""))
	dialogue["status"] = DialogueConstantsData.STATUS_COMPLETED
	_status = DialogueConstantsData.STATUS_COMPLETED
	result["previous_status"] = previous_status
	result["status"] = DialogueConstantsData.STATUS_COMPLETED
	_populate_result_from_dialogue(result, _active_dialogue_id)
	var event := _make_dialogue_event(DialogueConstantsData.EVENT_DIALOGUE_ENDED, _active_dialogue_id, DialogueConstantsData.STATUS_COMPLETED, previous_status)
	DialogueResultData.add_event(result, event)
	dialogue_ended.emit(_active_dialogue_id, result)
	dialogues_changed.emit(event)
	_active_dialogue_id = ""
	_current_line_id = ""


func _get_line_definition(definition: Resource, line_id: String) -> Resource:
	if definition == null:
		return null
	for line in definition.lines:
		var line_definition = _line_or_null(line)
		if line_definition == null:
			continue
		if String(line_definition.line_id) == line_id:
			return line_definition
	return null


func _get_choice_definition(line: Resource, choice_id: String) -> Resource:
	if line == null:
		return null
	for choice in line.choices:
		var choice_definition = _choice_or_null(choice)
		if choice_definition == null:
			continue
		if String(choice_definition.choice_id) == choice_id:
			return choice_definition
	return null


func _line_or_null(line: Resource) -> Resource:
	if line == null:
		return null
	if line is DialogueLineDefinitionData:
		return line
	return null


func _choice_or_null(choice: Resource) -> Resource:
	if choice == null:
		return null
	if choice is DialogueChoiceDefinitionData:
		return choice
	return null


func _make_line_snapshot(line: Resource) -> Dictionary:
	if line == null:
		return {}
	return {
		"line_id": String(line.line_id),
		"speaker": String(line.speaker),
		"text": String(line.text),
		"next_line_id": String(line.next_line_id),
		"has_choices": not (line.choices as Array).is_empty(),
		"condition": String(line.condition),
		"on_enter": (line.on_enter as Dictionary).duplicate(true),
		"on_exit": (line.on_exit as Dictionary).duplicate(true),
		"apply_variables": (line.apply_variables as Dictionary).duplicate(true),
		"data": (line.default_data as Dictionary).duplicate(true),
	}


func _evaluate_condition(condition: String, variables: Dictionary) -> bool:
	if condition.strip_edges().is_empty():
		return true
	var expression := Expression.new()
	var err := expression.parse(condition, ["variables"])
	if err != OK:
		return false
	var result = expression.execute([variables])
	if expression.has_execute_failed():
		return false
	if typeof(result) != TYPE_BOOL:
		return false
	return bool(result)


func _make_dialogue_event(event_type: String, dialogue_id: String, status: String, previous_status: String = "") -> Dictionary:
	return {
		"ok": true,
		"type": event_type,
		"dialogue_id": dialogue_id,
		"line_id": "",
		"choice_id": "",
		"status": status,
		"previous_status": previous_status,
		"warnings": [],
		"errors": [],
	}


func _make_line_event(event_type: String, dialogue_id: String, line_id: String) -> Dictionary:
	return {
		"ok": true,
		"type": event_type,
		"dialogue_id": dialogue_id,
		"line_id": line_id,
		"choice_id": "",
		"status": _status,
		"previous_status": "",
		"warnings": [],
		"errors": [],
	}


func _make_choice_event(event_type: String, dialogue_id: String, choice_id: String) -> Dictionary:
	return {
		"ok": true,
		"type": event_type,
		"dialogue_id": dialogue_id,
		"line_id": _current_line_id,
		"choice_id": choice_id,
		"status": _status,
		"previous_status": "",
		"warnings": [],
		"errors": [],
	}


func _dialogue_to_state(dialogue: Dictionary) -> Dictionary:
	return {
		"dialogue_id": String(dialogue.get("dialogue_id", "")),
		"status": String(dialogue.get("status", "")),
		"data": (dialogue.get("data", {}) as Dictionary).duplicate(true),
	}


func _parse_state(data: Dictionary, result: Dictionary) -> Dictionary:
	var parsed := {
		"dialogues_by_id": {},
		"dialogue_ids": [],
		"active_dialogue_id": "",
		"current_line_id": "",
		"status": DialogueConstantsData.STATUS_INACTIVE,
		"variables": {},
	}
	var saved_schema := _parse_integer_field(data.get("schema_version", null), "schema_version", result)
	if saved_schema != DialogueConstantsData.SCHEMA_VERSION:
		DialogueResultData.add_error(result, "schema_version must be %d" % DialogueConstantsData.SCHEMA_VERSION)

	var raw_dialogues = data.get("dialogues", null)
	if not (raw_dialogues is Array):
		DialogueResultData.add_error(result, "dialogues must be an Array")
		return parsed
	if not _validate_database(result):
		return parsed

	var saved_by_id := {}
	var seen_dialogues := {}
	var saved_dialogues: Array = raw_dialogues
	for index in range(saved_dialogues.size()):
		var saved_value = saved_dialogues[index]
		if not (saved_value is Dictionary):
			DialogueResultData.add_error(result, "dialogues[%d] must be a Dictionary" % index)
			continue
		var saved_dialogue: Dictionary = saved_value
		var raw_dialogue_id = saved_dialogue.get("dialogue_id", "")
		if typeof(raw_dialogue_id) != TYPE_STRING and typeof(raw_dialogue_id) != TYPE_STRING_NAME:
			DialogueResultData.add_error(result, "dialogues[%d].dialogue_id must be a string" % index)
			continue
		var dialogue_id := String(raw_dialogue_id)
		var normalized := dialogue_id.strip_edges()
		if normalized.is_empty():
			DialogueResultData.add_error(result, "dialogues[%d].dialogue_id must be non-empty" % index)
			continue
		if normalized != dialogue_id:
			DialogueResultData.add_error(result, "dialogues[%d].dialogue_id must not contain leading or trailing whitespace" % index)
			continue
		if seen_dialogues.has(normalized):
			DialogueResultData.add_error(result, "Duplicate dialogue_id: %s" % normalized)
			continue
		seen_dialogues[normalized] = true
		if not bool(database.call("has_dialogue", normalized)):
			DialogueResultData.add_error(result, "Unknown dialogue_id: %s" % normalized)
			continue
		saved_by_id[normalized] = saved_dialogue

	if not bool(result.get("ok", false)):
		return parsed

	var ids: Array[String] = []
	ids.assign(database.call("get_dialogue_ids"))
	for dialogue_id in ids:
		var definition: Resource = database.call("get_dialogue", dialogue_id)
		var dialogue_entry: Dictionary
		if saved_by_id.has(dialogue_id):
			dialogue_entry = _parse_dialogue_state(saved_by_id[dialogue_id], definition, result)
		else:
			dialogue_entry = _make_default_dialogue_entry(dialogue_id, definition)
		(parsed["dialogues_by_id"] as Dictionary)[dialogue_id] = dialogue_entry
		(parsed["dialogue_ids"] as Array).append(dialogue_id)

	var raw_active = data.get("active_dialogue_id", "")
	if typeof(raw_active) == TYPE_STRING or typeof(raw_active) == TYPE_STRING_NAME:
		parsed["active_dialogue_id"] = String(raw_active).strip_edges()
	var raw_line = data.get("current_line_id", "")
	if typeof(raw_line) == TYPE_STRING or typeof(raw_line) == TYPE_STRING_NAME:
		parsed["current_line_id"] = String(raw_line).strip_edges()
	var raw_status = data.get("status", "")
	if typeof(raw_status) == TYPE_STRING or typeof(raw_status) == TYPE_STRING_NAME:
		var status := String(raw_status)
		if status in [DialogueConstantsData.STATUS_INACTIVE, DialogueConstantsData.STATUS_ACTIVE, DialogueConstantsData.STATUS_COMPLETED]:
			parsed["status"] = status
		else:
			DialogueResultData.add_error(result, "status is invalid: %s" % status)
	var raw_variables = data.get("variables", {})
	if raw_variables is Dictionary:
		if _is_json_compatible(raw_variables):
			parsed["variables"] = (raw_variables as Dictionary).duplicate(true)
		else:
			DialogueResultData.add_error(result, "variables must be JSON-compatible")
	else:
		DialogueResultData.add_error(result, "variables must be a Dictionary")

	return parsed


func _parse_dialogue_state(saved_dialogue: Dictionary, definition: Resource, result: Dictionary) -> Dictionary:
	var dialogue_id := String(definition.dialogue_id)
	var status := _parse_status(saved_dialogue.get("status", ""), [DialogueConstantsData.STATUS_INACTIVE, DialogueConstantsData.STATUS_ACTIVE, DialogueConstantsData.STATUS_COMPLETED], "dialogue status", result)
	var raw_data = saved_dialogue.get("data", {})
	var dialogue_data := {}
	if not (raw_data is Dictionary):
		DialogueResultData.add_error(result, "dialogue data must be a Dictionary for dialogue_id: %s" % dialogue_id)
	elif not _is_json_compatible(raw_data):
		DialogueResultData.add_error(result, "data must be JSON-compatible for dialogue_id: %s" % dialogue_id)
	else:
		dialogue_data = (raw_data as Dictionary).duplicate(true)

	return {
		"dialogue_id": dialogue_id,
		"status": status,
		"default_variables": (definition.default_variables as Dictionary).duplicate(true),
		"data": dialogue_data,
	}


func _parse_status(value: Variant, allowed: Array, field_name: String, result: Dictionary) -> String:
	if typeof(value) != TYPE_STRING and typeof(value) != TYPE_STRING_NAME:
		DialogueResultData.add_error(result, "%s must be a string" % field_name)
		return ""
	var status := String(value)
	if not allowed.has(status):
		DialogueResultData.add_error(result, "%s is invalid: %s" % [field_name, status])
	return status


func _parse_integer_field(value: Variant, field_name: String, result: Dictionary) -> int:
	if typeof(value) == TYPE_INT:
		return int(value)
	if typeof(value) == TYPE_FLOAT:
		var float_value := float(value)
		if not is_nan(float_value) and not is_inf(float_value) and float_value == floor(float_value):
			return int(float_value)
	DialogueResultData.add_error(result, "%s must be an integer" % field_name)
	return 0


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
