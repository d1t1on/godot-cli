extends Node

const SaveConstantsData := preload("res://addons/save_load/save_constants.gd")
const SaveResultData := preload("res://addons/save_load/save_result.gd")

signal save_completed(slot_id: String, result: Dictionary)
signal save_failed(slot_id: String, result: Dictionary)
signal load_completed(slot_id: String, result: Dictionary)
signal load_failed(slot_id: String, result: Dictionary)


func save_slot(slot_id: String) -> Dictionary:
	var normalized_slot_id := _normalize_slot_id(slot_id)
	var result := SaveResultData.make(true, normalized_slot_id)
	if normalized_slot_id.is_empty():
		SaveResultData.add_error(result, "slot_id must be non-empty and may not contain path separators, ':', or '..'")
		save_failed.emit(slot_id, result)
		return result

	var participants := _collect_participants(result, true)
	if not result["ok"]:
		save_failed.emit(normalized_slot_id, result)
		return result

	var payload := {
		"schema_version": SaveConstantsData.SCHEMA_VERSION,
		"module_version": SaveConstantsData.MODULE_VERSION,
		"saved_at": Time.get_datetime_string_from_system(true),
		"scene": _current_scene_path(),
		"participants": participants,
	}
	var dir_error := DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(SaveConstantsData.SAVE_DIR))
	if dir_error != OK:
		SaveResultData.add_error(result, "Could not create save directory: %s" % error_string(dir_error))
		save_failed.emit(normalized_slot_id, result)
		return result

	var path := _slot_path(normalized_slot_id)
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		SaveResultData.add_error(result, "Could not open save file for writing: %s" % error_string(FileAccess.get_open_error()))
		save_failed.emit(normalized_slot_id, result)
		return result
	file.store_string(JSON.stringify(payload, "\t"))
	save_completed.emit(normalized_slot_id, result)
	return result


func load_slot(slot_id: String) -> Dictionary:
	var normalized_slot_id := _normalize_slot_id(slot_id)
	var result := SaveResultData.make(true, normalized_slot_id)
	if normalized_slot_id.is_empty():
		SaveResultData.add_error(result, "slot_id must be non-empty and may not contain path separators, ':', or '..'")
		load_failed.emit(slot_id, result)
		return result

	var path := _slot_path(normalized_slot_id)
	if not FileAccess.file_exists(path):
		SaveResultData.add_error(result, "Save slot does not exist: %s" % normalized_slot_id)
		load_failed.emit(normalized_slot_id, result)
		return result

	var text := FileAccess.get_file_as_string(path)
	var payload = JSON.parse_string(text)
	if not payload is Dictionary:
		SaveResultData.add_error(result, "Save file is not valid JSON object: %s" % normalized_slot_id)
		load_failed.emit(normalized_slot_id, result)
		return result
	if int(payload.get("schema_version", -1)) != SaveConstantsData.SCHEMA_VERSION:
		SaveResultData.add_error(result, "Unsupported save schema_version: %s" % str(payload.get("schema_version")))
		load_failed.emit(normalized_slot_id, result)
		return result

	var saved_participants = payload.get("participants", {})
	if not saved_participants is Dictionary:
		SaveResultData.add_error(result, "Save file participants field must be a Dictionary")
		load_failed.emit(normalized_slot_id, result)
		return result

	var live_participants := _participant_nodes_by_id(result, false)
	if not result["ok"]:
		load_failed.emit(normalized_slot_id, result)
		return result
	for save_id in saved_participants.keys():
		var key := String(save_id)
		if not live_participants.has(key):
			SaveResultData.add_warning(result, "Saved participant has no live node: %s" % key)
			continue
		var state = saved_participants[save_id]
		if not state is Dictionary:
			SaveResultData.add_warning(result, "Saved participant state is not a Dictionary: %s" % key)
			continue
		live_participants[key].call("load_state", state)

	if result["ok"]:
		load_completed.emit(normalized_slot_id, result)
	else:
		load_failed.emit(normalized_slot_id, result)
	return result


func delete_slot(slot_id: String) -> Dictionary:
	var normalized_slot_id := _normalize_slot_id(slot_id)
	var result := SaveResultData.make(true, normalized_slot_id)
	if normalized_slot_id.is_empty():
		SaveResultData.add_error(result, "slot_id must be non-empty and may not contain path separators, ':', or '..'")
		return result
	var path := _slot_path(normalized_slot_id)
	if not FileAccess.file_exists(path):
		return result
	var error := DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	if error != OK:
		SaveResultData.add_error(result, "Could not delete save slot: %s" % error_string(error))
	return result


func list_slots() -> Array[Dictionary]:
	var slots: Array[Dictionary] = []
	var dir := DirAccess.open(SaveConstantsData.SAVE_DIR)
	if dir == null:
		return slots
	dir.list_dir_begin()
	var file_name := dir.get_next()
	while not file_name.is_empty():
		if not dir.current_is_dir() and file_name.ends_with(".json"):
			var slot_id := file_name.trim_suffix(".json")
			var entry := {"slot_id": slot_id, "path": _slot_path(slot_id)}
			var payload = JSON.parse_string(FileAccess.get_file_as_string(_slot_path(slot_id)))
			if payload is Dictionary:
				entry["saved_at"] = payload.get("saved_at", "")
				entry["scene"] = payload.get("scene", "")
				entry["schema_version"] = payload.get("schema_version", 0)
			slots.append(entry)
		file_name = dir.get_next()
	dir.list_dir_end()
	return slots


func has_slot(slot_id: String) -> bool:
	var normalized_slot_id := _normalize_slot_id(slot_id)
	return not normalized_slot_id.is_empty() and FileAccess.file_exists(_slot_path(normalized_slot_id))


func _collect_participants(result: Dictionary, require_save_state: bool) -> Dictionary:
	var participants := {}
	var nodes := _participant_nodes_by_id(result, require_save_state)
	for save_id in nodes.keys():
		var node: Node = nodes[save_id]
		var state = node.call("save_state")
		if not state is Dictionary:
			SaveResultData.add_error(result, "save_state() must return a Dictionary for %s" % save_id)
			continue
		if not _is_json_compatible(state):
			SaveResultData.add_error(result, "save_state() returned non-JSON-compatible data for %s" % save_id)
			continue
		participants[save_id] = state
	return participants


func _participant_nodes_by_id(result: Dictionary, require_save_state: bool) -> Dictionary:
	var participants := {}
	for node in get_tree().get_nodes_in_group(SaveConstantsData.GROUP):
		if not is_instance_valid(node):
			continue
		if require_save_state and not node.has_method("save_state"):
			SaveResultData.add_error(result, "Participant is missing save_state(): %s" % node.get_path())
			continue
		if not require_save_state and not node.has_method("load_state"):
			SaveResultData.add_error(result, "Participant is missing load_state(data): %s" % node.get_path())
			continue
		var save_id := _resolve_save_id(node, result)
		if save_id.is_empty():
			continue
		if participants.has(save_id):
			SaveResultData.add_error(result, "Duplicate save_id: %s" % save_id)
			continue
		participants[save_id] = node
	return participants


func _resolve_save_id(node: Node, result: Dictionary) -> String:
	if node.has_method("get_save_id"):
		var method_id := String(node.call("get_save_id"))
		if not method_id.is_empty():
			return method_id
	var property_id = node.get("save_id")
	if property_id != null and not String(property_id).is_empty():
		return String(property_id)
	var fallback := String(node.get_path())
	SaveResultData.add_warning(result, "Participant uses NodePath fallback save_id: %s" % fallback)
	return fallback


func _normalize_slot_id(slot_id: String) -> String:
	var value := slot_id.strip_edges()
	if value.is_empty() or value.contains("/") or value.contains("\\") or value.contains(":") or value.contains(".."):
		return ""
	return value


func _slot_path(slot_id: String) -> String:
	return "%s/%s.json" % [SaveConstantsData.SAVE_DIR, slot_id]


func _current_scene_path() -> String:
	var current_scene := get_tree().current_scene
	if current_scene == null:
		return ""
	return current_scene.scene_file_path


func _is_json_compatible(value) -> bool:
	match typeof(value):
		TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_STRING:
			return true
		TYPE_FLOAT:
			return not is_nan(value) and not is_inf(value)
		TYPE_ARRAY:
			for item in value:
				if not _is_json_compatible(item):
					return false
			return true
		TYPE_DICTIONARY:
			for key in value.keys():
				if not (key is String or key is StringName):
					return false
				if not _is_json_compatible(value[key]):
					return false
			return true
		_:
			return false
