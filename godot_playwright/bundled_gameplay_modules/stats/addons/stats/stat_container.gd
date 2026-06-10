class_name StatContainer
extends Node

const StatConstantsData := preload("res://addons/stats/stat_constants.gd")
const StatResultData := preload("res://addons/stats/stat_result.gd")

signal stat_changed(stat_id: String, current_value: float, previous_value: float, result: Dictionary)
signal base_stat_changed(stat_id: String, base_value: float, previous_base_value: float, result: Dictionary)
signal stat_depleted(stat_id: String, current_value: float, result: Dictionary)
signal stat_filled(stat_id: String, current_value: float, result: Dictionary)
signal stats_changed(event: Dictionary)

@export var database: Resource
@export var save_id: StringName
@export var initialize_on_ready: bool = true

var _stats_by_id: Dictionary = {}
var _stat_ids: Array[String] = []
var _initialized: bool = false


func _enter_tree() -> void:
	if not String(save_id).is_empty():
		add_to_group(StatConstantsData.SAVE_GROUP)


func _ready() -> void:
	if initialize_on_ready:
		initialize_stats()


func initialize_stats(reset: bool = false) -> Dictionary:
	var result := StatResultData.make(true)
	if _initialized and not reset:
		return result
	if not _validate_database(result):
		return result
	_stats_by_id.clear()
	_stat_ids.clear()
	var ids: Array[String] = []
	ids.assign(database.call("get_stat_ids"))
	for stat_id in ids:
		var definition: Resource = database.call("get_stat", stat_id)
		var base_value := _clamp_base_value(definition, float(definition.default_base_value), null)
		var current_value := _clamp_current_value(definition, float(definition.default_current_value), base_value, null)
		_stats_by_id[stat_id] = {
			"stat_id": stat_id,
			"base_value": base_value,
			"current_value": current_value,
		}
		_stat_ids.append(stat_id)
	_initialized = true
	return result


func has_stat(stat_id: String) -> bool:
	_ensure_initialized()
	return _stats_by_id.has(stat_id.strip_edges())


func get_value(stat_id: String) -> float:
	_ensure_initialized()
	var normalized := stat_id.strip_edges()
	if not _stats_by_id.has(normalized):
		return 0.0
	return float((_stats_by_id[normalized] as Dictionary).get("current_value", 0.0))


func get_base_value(stat_id: String) -> float:
	_ensure_initialized()
	var normalized := stat_id.strip_edges()
	if not _stats_by_id.has(normalized):
		return 0.0
	return float((_stats_by_id[normalized] as Dictionary).get("base_value", 0.0))


func get_stat(stat_id: String) -> Dictionary:
	_ensure_initialized()
	var normalized := stat_id.strip_edges()
	if not _stats_by_id.has(normalized):
		return {}
	return (_stats_by_id[normalized] as Dictionary).duplicate(true)


func get_stats() -> Array:
	_ensure_initialized()
	var copied: Array = []
	for stat_id in _stat_ids:
		copied.append((_stats_by_id[stat_id] as Dictionary).duplicate(true))
	return copied


func set_value(stat_id: String, value: float) -> Dictionary:
	return _set_current_value(stat_id, value, false, 0.0)


func modify_value(stat_id: String, delta: float) -> Dictionary:
	var normalized := stat_id.strip_edges()
	_ensure_initialized()
	var current := get_value(normalized)
	return _set_current_value(normalized, current + delta, true, delta)


func set_base_value(stat_id: String, value: float) -> Dictionary:
	return _set_base_value(stat_id, value, false, 0.0)


func modify_base_value(stat_id: String, delta: float) -> Dictionary:
	var normalized := stat_id.strip_edges()
	_ensure_initialized()
	var current_base := get_base_value(normalized)
	return _set_base_value(normalized, current_base + delta, true, delta)


func clear_runtime_state() -> void:
	_stats_by_id.clear()
	_stat_ids.clear()
	_initialized = false


func get_state() -> Dictionary:
	return {
		"schema_version": StatConstantsData.SCHEMA_VERSION,
		"stats": get_stats(),
	}


func apply_state(data: Dictionary) -> Dictionary:
	var result := StatResultData.make(true)
	var parsed := _parse_state(data, result)
	if not bool(result.get("ok", false)):
		return result
	_stats_by_id = parsed["stats_by_id"]
	_stat_ids = parsed["stat_ids"]
	_initialized = true
	for stat_id in _stat_ids:
		var event := {"type": "state_applied", "stat_id": stat_id, "stat": get_stat(stat_id)}
		StatResultData.add_event(result, event)
		stats_changed.emit(event)
	return result


func get_save_id() -> String:
	return String(save_id)


func save_state() -> Dictionary:
	return get_state()


func load_state(data: Dictionary) -> void:
	var result := apply_state(data)
	if not bool(result.get("ok", false)):
		push_warning("StatContainer load_state failed: %s" % ", ".join(PackedStringArray(result.get("errors", []))))


func _set_current_value(stat_id: String, value: float, is_delta: bool, delta: float) -> Dictionary:
	_ensure_initialized()
	var normalized := stat_id.strip_edges()
	var result := _make_stat_result(normalized)
	if not _validate_stat_mutation(result, normalized):
		return result
	if not _is_finite_number(value):
		StatResultData.add_error(result, "value must be finite")
		return result
	var stat: Dictionary = _stats_by_id[normalized]
	var definition: Resource = database.call("get_stat", normalized)
	var previous := float(stat["current_value"])
	var applied := _clamp_current_value(definition, value, float(stat["base_value"]), result)
	result["requested_value"] = value
	result["delta"] = delta if is_delta else applied - previous
	result["previous_value"] = previous
	result["current_value"] = applied
	stat["current_value"] = applied
	if previous != applied:
		_emit_current_events(normalized, definition, previous, applied, result)
	return result


func _set_base_value(stat_id: String, value: float, is_delta: bool, delta: float) -> Dictionary:
	_ensure_initialized()
	var normalized := stat_id.strip_edges()
	var result := _make_stat_result(normalized)
	if not _validate_stat_mutation(result, normalized):
		return result
	if not _is_finite_number(value):
		StatResultData.add_error(result, "value must be finite")
		return result
	var stat: Dictionary = _stats_by_id[normalized]
	var definition: Resource = database.call("get_stat", normalized)
	var previous_base := float(stat["base_value"])
	var previous_current := float(stat["current_value"])
	var applied_base := _clamp_base_value(definition, value, result)
	var applied_current := _clamp_current_value(definition, previous_current, applied_base, result)
	result["requested_value"] = value
	result["delta"] = delta if is_delta else applied_base - previous_base
	result["previous_base_value"] = previous_base
	result["base_value"] = applied_base
	result["previous_value"] = previous_current
	result["current_value"] = applied_current
	stat["base_value"] = applied_base
	stat["current_value"] = applied_current
	if previous_base != applied_base:
		var base_event := {"type": "base_changed", "stat_id": normalized, "previous_base_value": previous_base, "base_value": applied_base}
		StatResultData.add_event(result, base_event)
		base_stat_changed.emit(normalized, applied_base, previous_base, result)
		stats_changed.emit(base_event)
	if previous_current != applied_current:
		_emit_current_events(normalized, definition, previous_current, applied_current, result)
	return result


func _make_stat_result(stat_id: String) -> Dictionary:
	var result := StatResultData.make(true, stat_id)
	if _stats_by_id.has(stat_id):
		var stat: Dictionary = _stats_by_id[stat_id]
		result["previous_value"] = float(stat.get("current_value", 0.0))
		result["current_value"] = float(stat.get("current_value", 0.0))
		result["previous_base_value"] = float(stat.get("base_value", 0.0))
		result["base_value"] = float(stat.get("base_value", 0.0))
	return result


func _emit_current_events(stat_id: String, definition: Resource, previous: float, current: float, result: Dictionary) -> void:
	var changed_event := {"type": "changed", "stat_id": stat_id, "previous_value": previous, "current_value": current}
	StatResultData.add_event(result, changed_event)
	stat_changed.emit(stat_id, current, previous, result)
	stats_changed.emit(changed_event)
	if bool(definition.clamp_min):
		var minimum := float(definition.min_value)
		if previous > minimum and current <= minimum:
			var depleted_event := {"type": "depleted", "stat_id": stat_id, "current_value": current}
			StatResultData.add_event(result, depleted_event)
			stat_depleted.emit(stat_id, current, result)
			stats_changed.emit(depleted_event)
	var has_maximum := bool(definition.is_pool) or bool(definition.clamp_max)
	if has_maximum:
		var maximum := get_base_value(stat_id) if bool(definition.is_pool) else float(definition.max_value)
		if previous < maximum and current >= maximum:
			var filled_event := {"type": "filled", "stat_id": stat_id, "current_value": current}
			StatResultData.add_event(result, filled_event)
			stat_filled.emit(stat_id, current, result)
			stats_changed.emit(filled_event)


func _validate_stat_mutation(result: Dictionary, stat_id: String) -> bool:
	if stat_id.is_empty():
		StatResultData.add_error(result, "stat_id must be non-empty")
	if not _validate_database(result):
		return false
	if result["ok"] and (not _stats_by_id.has(stat_id) or not bool(database.call("has_stat", stat_id))):
		StatResultData.add_error(result, "Unknown stat_id: %s" % stat_id)
	return bool(result["ok"])


func _validate_database(result: Dictionary) -> bool:
	if database == null:
		StatResultData.add_error(result, "database must be assigned")
		return false
	if not database.has_method("validate") or not database.has_method("get_stat") or not database.has_method("has_stat") or not database.has_method("get_stat_ids"):
		StatResultData.add_error(result, "database must be a StatDatabase")
		return false
	var database_result: Dictionary = database.call("validate")
	if not bool(database_result.get("ok", false)):
		for error in database_result.get("errors", []):
			StatResultData.add_error(result, String(error))
		for warning in database_result.get("warnings", []):
			StatResultData.add_warning(result, String(warning))
		return false
	return true


func _ensure_initialized() -> void:
	if not _initialized:
		initialize_stats()


func _clamp_base_value(definition: Resource, value: float, result: Variant) -> float:
	var applied := value
	if bool(definition.clamp_min):
		applied = maxf(applied, float(definition.min_value))
	if bool(definition.clamp_max):
		applied = minf(applied, float(definition.max_value))
	if result != null and applied != value:
		result["clamped"] = true
		StatResultData.add_warning(result, "value was clamped from %s to %s" % [str(value), str(applied)])
	return applied


func _clamp_current_value(definition: Resource, value: float, base_value: float, result: Variant) -> float:
	var applied := value
	if bool(definition.clamp_min):
		applied = maxf(applied, float(definition.min_value))
	if bool(definition.is_pool):
		applied = minf(applied, base_value)
	elif bool(definition.clamp_max):
		applied = minf(applied, float(definition.max_value))
	if result != null and applied != value:
		result["clamped"] = true
		StatResultData.add_warning(result, "value was clamped from %s to %s" % [str(value), str(applied)])
	return applied


func _parse_state(data: Dictionary, result: Dictionary) -> Dictionary:
	var parsed := {"stats_by_id": {}, "stat_ids": []}
	if int(data.get("schema_version", -1)) != StatConstantsData.SCHEMA_VERSION:
		StatResultData.add_error(result, "schema_version must be %d" % StatConstantsData.SCHEMA_VERSION)
	var raw_stats = data.get("stats", null)
	if not (raw_stats is Array):
		StatResultData.add_error(result, "stats must be an Array")
		return parsed
	if not _validate_database(result):
		return parsed
	var seen := {}
	var next_by_id := {}
	var next_ids: Array[String] = []
	var saved_stats: Array = raw_stats
	for index in range(saved_stats.size()):
		var value = saved_stats[index]
		if not (value is Dictionary):
			StatResultData.add_error(result, "stats[%d] must be a Dictionary" % index)
			continue
		var stat: Dictionary = value
		var raw_stat_id = stat.get("stat_id", "")
		if typeof(raw_stat_id) != TYPE_STRING and typeof(raw_stat_id) != TYPE_STRING_NAME:
			StatResultData.add_error(result, "stats[%d].stat_id must be a string" % index)
			continue
		var stat_id := String(raw_stat_id)
		var normalized := stat_id.strip_edges()
		if normalized.is_empty():
			StatResultData.add_error(result, "stats[%d].stat_id must be non-empty" % index)
			continue
		if normalized != stat_id:
			StatResultData.add_error(result, "stats[%d].stat_id must not contain leading or trailing whitespace" % index)
			continue
		if seen.has(normalized):
			StatResultData.add_error(result, "Duplicate stat_id: %s" % normalized)
			continue
		if not bool(database.call("has_stat", normalized)):
			StatResultData.add_error(result, "Unknown stat_id: %s" % normalized)
			continue
		seen[normalized] = true
		var base_value = stat.get("base_value", null)
		var current_value = stat.get("current_value", null)
		if not _is_finite_number(base_value):
			StatResultData.add_error(result, "stats[%d].base_value must be finite" % index)
			continue
		if not _is_finite_number(current_value):
			StatResultData.add_error(result, "stats[%d].current_value must be finite" % index)
			continue
		var definition: Resource = database.call("get_stat", normalized)
		var parsed_base := _clamp_base_value(definition, float(base_value), null)
		var parsed_current := _clamp_current_value(definition, float(current_value), parsed_base, null)
		if parsed_base != float(base_value) or parsed_current != float(current_value):
			StatResultData.add_error(result, "stats[%d] values do not satisfy current clamp rules" % index)
			continue
		next_by_id[normalized] = {"stat_id": normalized, "base_value": parsed_base, "current_value": parsed_current}
	for database_id in database.call("get_stat_ids"):
		if next_by_id.has(database_id):
			next_ids.append(database_id)
		else:
			var definition: Resource = database.call("get_stat", database_id)
			var default_base_value := _clamp_base_value(definition, float(definition.default_base_value), null)
			next_by_id[database_id] = {
				"stat_id": database_id,
				"base_value": default_base_value,
				"current_value": _clamp_current_value(definition, float(definition.default_current_value), default_base_value, null),
			}
			next_ids.append(database_id)
	if bool(result.get("ok", false)):
		parsed["stats_by_id"] = next_by_id
		parsed["stat_ids"] = next_ids
	return parsed


func _is_finite_number(value: Variant) -> bool:
	if typeof(value) != TYPE_INT and typeof(value) != TYPE_FLOAT:
		return false
	var number := float(value)
	return not is_nan(number) and not is_inf(number)
