class_name AbilityContainer
extends Node

const AbilityConstantsData := preload("res://addons/abilities/ability_constants.gd")
const AbilityResultData := preload("res://addons/abilities/ability_result.gd")

signal ability_activated(ability_id: String, result: Dictionary)
signal ability_failed(ability_id: String, result: Dictionary)
signal ability_enabled_changed(ability_id: String, enabled: bool, result: Dictionary)
signal ability_cooldown_ready(ability_id: String, event: Dictionary)
signal ability_charge_recovered(ability_id: String, charges: int, event: Dictionary)
signal abilities_changed(event: Dictionary)

@export var database: Resource
@export var save_id: StringName
@export var initialize_on_ready: bool = true
@export var auto_update: bool = true

var _abilities_by_id: Dictionary = {}
var _ability_ids: Array[String] = []
var _initialized: bool = false


func _enter_tree() -> void:
	if not String(save_id).is_empty():
		add_to_group(AbilityConstantsData.SAVE_GROUP)


func _ready() -> void:
	if initialize_on_ready:
		initialize_abilities()


func _process(delta: float) -> void:
	if auto_update and _initialized:
		update_abilities(delta)


func initialize_abilities(reset: bool = false) -> Dictionary:
	var result := AbilityResultData.make(true)
	if _initialized and not reset:
		return result
	if not _validate_database(result):
		return result
	_abilities_by_id.clear()
	_ability_ids.clear()
	var ids: Array[String] = []
	ids.assign(database.call("get_ability_ids"))
	for ability_id in ids:
		var definition: Resource = database.call("get_ability", ability_id)
		_abilities_by_id[ability_id] = _make_runtime_entry(ability_id, definition)
		_ability_ids.append(ability_id)
	_initialized = true
	return result


func has_ability(ability_id: String) -> bool:
	_ensure_initialized()
	return _abilities_by_id.has(ability_id.strip_edges())


func can_activate(ability_id: String, context: Dictionary = {}) -> Dictionary:
	_ensure_initialized()
	var normalized := ability_id.strip_edges()
	var result := _make_ability_result(normalized)
	if not _validate_activation(result, normalized, context):
		return result
	result["context"] = context.duplicate(true)
	return result


func activate(ability_id: String, context: Dictionary = {}) -> Dictionary:
	_ensure_initialized()
	var normalized := ability_id.strip_edges()
	var result := _make_ability_result(normalized)
	if not _validate_activation(result, normalized, context):
		_emit_activation_failure_if_known(normalized, result)
		return result

	var runtime: Dictionary = _abilities_by_id[normalized]
	var definition: Resource = database.call("get_ability", normalized)
	if int(definition.max_charges) > 0:
		runtime["charges"] = int(runtime.get("charges", 0)) - 1
	if float(definition.cooldown) > 0.0:
		runtime["cooldown_remaining"] = float(definition.cooldown)
	_start_charge_recovery(runtime, definition)

	result = _make_ability_result(normalized)
	result["context"] = context.duplicate(true)
	var event := _make_event("ability_activated", normalized)
	AbilityResultData.add_event(result, event)
	ability_activated.emit(normalized, result)
	abilities_changed.emit(event)
	return result


func set_enabled(ability_id: String, enabled: bool) -> Dictionary:
	_ensure_initialized()
	var normalized := ability_id.strip_edges()
	var result := _make_ability_result(normalized)
	if not _validate_known_ability(result, normalized):
		return result
	var runtime: Dictionary = _abilities_by_id[normalized]
	var previous_enabled := bool(runtime.get("enabled", true))
	if previous_enabled == enabled:
		return result

	runtime["enabled"] = enabled
	result = _make_ability_result(normalized)
	var event := _make_event("ability_enabled_changed", normalized)
	event["enabled"] = enabled
	event["previous_enabled"] = previous_enabled
	AbilityResultData.add_event(result, event)
	ability_enabled_changed.emit(normalized, enabled, result)
	abilities_changed.emit(event)
	return result


func is_enabled(ability_id: String) -> bool:
	_ensure_initialized()
	var normalized := ability_id.strip_edges()
	if not _abilities_by_id.has(normalized):
		return false
	return bool((_abilities_by_id[normalized] as Dictionary).get("enabled", true))


func get_ability_runtime(ability_id: String) -> Dictionary:
	_ensure_initialized()
	return _copy_runtime(ability_id.strip_edges())


func get_abilities() -> Array:
	_ensure_initialized()
	var copied: Array = []
	for ability_id in _ability_ids:
		copied.append(_copy_runtime(ability_id))
	return copied


func update_abilities(delta: float) -> Array[Dictionary]:
	var events: Array[Dictionary] = []
	if is_nan(delta) or is_inf(delta) or delta < 0.0:
		events.append({
			"ok": false,
			"type": "ability_update_failed",
			"ability_id": "",
			"warnings": [],
			"errors": ["delta must be finite and zero or greater"],
		})
		return events
	if delta == 0.0:
		return events

	_ensure_initialized()
	for ability_id in _ability_ids:
		var runtime: Dictionary = _abilities_by_id[ability_id]
		var definition: Resource = database.call("get_ability", ability_id)
		_advance_cooldown(ability_id, runtime, delta, events)
		_advance_charge_recovery(ability_id, runtime, definition, delta, events)
	return events


func clear_runtime_state() -> void:
	_abilities_by_id.clear()
	_ability_ids.clear()
	_initialized = false


func get_state() -> Dictionary:
	return {
		"schema_version": AbilityConstantsData.SCHEMA_VERSION,
		"abilities": get_abilities(),
	}


func apply_state(data: Dictionary) -> Dictionary:
	var result := AbilityResultData.make(true)
	AbilityResultData.add_error(result, "apply_state is not implemented yet")
	return result


func get_save_id() -> String:
	return String(save_id)


func save_state() -> Dictionary:
	return get_state()


func load_state(data: Dictionary) -> void:
	var result := apply_state(data)
	if not bool(result.get("ok", false)):
		push_warning("AbilityContainer load_state failed: %s" % ", ".join(PackedStringArray(result.get("errors", []))))


func _make_runtime_entry(ability_id: String, definition: Resource) -> Dictionary:
	return {
		"ability_id": ability_id,
		"enabled": bool(definition.enabled_by_default),
		"cooldown_remaining": 0.0,
		"charges": int(definition.initial_charges),
		"charge_recovery_remaining": 0.0,
	}


func _make_ability_result(ability_id: String) -> Dictionary:
	var result := AbilityResultData.make(true, ability_id)
	if _abilities_by_id.has(ability_id):
		var runtime: Dictionary = _abilities_by_id[ability_id]
		var definition: Resource = null
		if database != null and database.has_method("get_ability"):
			definition = database.call("get_ability", ability_id)
		result["enabled"] = bool(runtime.get("enabled", true))
		result["cooldown_remaining"] = float(runtime.get("cooldown_remaining", 0.0))
		result["charges"] = int(runtime.get("charges", 0))
		result["charge_recovery_remaining"] = float(runtime.get("charge_recovery_remaining", 0.0))
		if definition != null:
			result["max_charges"] = int(definition.max_charges)
			result["costs"] = (definition.costs as Dictionary).duplicate(true)
			result["data"] = (definition.default_data as Dictionary).duplicate(true)
	return result


func _validate_activation(result: Dictionary, ability_id: String, context: Dictionary) -> bool:
	if ability_id.is_empty():
		AbilityResultData.add_error(result, "ability_id must be non-empty")
	if not _is_json_compatible(context):
		AbilityResultData.add_error(result, "context must be JSON-compatible")
	if not _validate_database(result):
		return false
	if not bool(result.get("ok", false)):
		return false
	if not _abilities_by_id.has(ability_id) or not bool(database.call("has_ability", ability_id)):
		AbilityResultData.add_error(result, "Unknown ability_id: %s" % ability_id)
		return false

	var runtime: Dictionary = _abilities_by_id[ability_id]
	var definition: Resource = database.call("get_ability", ability_id)
	if not bool(runtime.get("enabled", true)):
		AbilityResultData.add_error(result, "Ability is disabled: %s" % ability_id)
	if float(runtime.get("cooldown_remaining", 0.0)) > 0.0:
		AbilityResultData.add_error(result, "Ability is on cooldown: %s" % ability_id)
	if int(definition.max_charges) > 0 and int(runtime.get("charges", 0)) <= 0:
		AbilityResultData.add_error(result, "Ability has no charges: %s" % ability_id)
	return bool(result.get("ok", false))


func _validate_known_ability(result: Dictionary, ability_id: String) -> bool:
	if ability_id.is_empty():
		AbilityResultData.add_error(result, "ability_id must be non-empty")
	if not _validate_database(result):
		return false
	if bool(result.get("ok", false)) and (not _abilities_by_id.has(ability_id) or not bool(database.call("has_ability", ability_id))):
		AbilityResultData.add_error(result, "Unknown ability_id: %s" % ability_id)
	return bool(result.get("ok", false))


func _validate_database(result: Dictionary) -> bool:
	if database == null:
		AbilityResultData.add_error(result, "database must be assigned")
		return false
	if not database.has_method("validate") or not database.has_method("has_ability") or not database.has_method("get_ability") or not database.has_method("get_ability_ids"):
		AbilityResultData.add_error(result, "database must be an AbilityDatabase")
		return false
	var database_result: Dictionary = database.call("validate")
	if not bool(database_result.get("ok", false)):
		for error in database_result.get("errors", []):
			AbilityResultData.add_error(result, String(error))
		for warning in database_result.get("warnings", []):
			AbilityResultData.add_warning(result, String(warning))
		return false
	return true


func _ensure_initialized() -> void:
	if not _initialized:
		initialize_abilities()


func _start_charge_recovery(runtime: Dictionary, definition: Resource) -> void:
	if int(definition.max_charges) <= 0:
		return
	if int(runtime.get("charges", 0)) >= int(definition.max_charges):
		return
	if float(runtime.get("charge_recovery_remaining", 0.0)) > 0.0:
		return
	var recovery_time := float(definition.charge_recovery_time)
	if recovery_time <= 0.0:
		recovery_time = float(definition.cooldown)
	if recovery_time > 0.0:
		runtime["charge_recovery_remaining"] = recovery_time


func _advance_cooldown(ability_id: String, runtime: Dictionary, delta: float, events: Array[Dictionary]) -> void:
	var previous := float(runtime.get("cooldown_remaining", 0.0))
	if previous <= 0.0:
		return
	var remaining := maxf(0.0, previous - delta)
	runtime["cooldown_remaining"] = remaining
	if remaining <= 0.0:
		var event := _make_event("ability_cooldown_ready", ability_id)
		events.append(event)
		ability_cooldown_ready.emit(ability_id, event)
		abilities_changed.emit(event)


func _advance_charge_recovery(ability_id: String, runtime: Dictionary, definition: Resource, delta: float, events: Array[Dictionary]) -> void:
	var max_charges := int(definition.max_charges)
	if max_charges <= 0:
		return
	var charges := int(runtime.get("charges", 0))
	if charges >= max_charges:
		runtime["charge_recovery_remaining"] = 0.0
		return

	var remaining_delta := delta
	while remaining_delta > 0.0 and charges < max_charges:
		var recovery_remaining := float(runtime.get("charge_recovery_remaining", 0.0))
		if recovery_remaining <= 0.0:
			_start_charge_recovery(runtime, definition)
			recovery_remaining = float(runtime.get("charge_recovery_remaining", 0.0))
			if recovery_remaining <= 0.0:
				return
		if remaining_delta < recovery_remaining:
			runtime["charge_recovery_remaining"] = recovery_remaining - remaining_delta
			return

		remaining_delta -= recovery_remaining
		charges += 1
		runtime["charges"] = charges
		var event := _make_event("ability_charge_recovered", ability_id)
		event["charges"] = charges
		events.append(event)
		ability_charge_recovered.emit(ability_id, charges, event)
		abilities_changed.emit(event)
		if charges >= max_charges:
			runtime["charge_recovery_remaining"] = 0.0
			return
		runtime["charge_recovery_remaining"] = 0.0
		_start_charge_recovery(runtime, definition)


func _emit_activation_failure_if_known(ability_id: String, result: Dictionary) -> void:
	if not _abilities_by_id.has(ability_id):
		return
	var event := _make_event("ability_failed", ability_id, false)
	event["warnings"] = (result.get("warnings", []) as Array).duplicate(true)
	event["errors"] = (result.get("errors", []) as Array).duplicate(true)
	AbilityResultData.add_event(result, event)
	ability_failed.emit(ability_id, result)
	abilities_changed.emit(event)


func _make_event(event_type: String, ability_id: String, ok: bool = true) -> Dictionary:
	return {
		"ok": ok,
		"type": event_type,
		"ability_id": ability_id,
		"runtime": _copy_runtime(ability_id),
		"warnings": [],
		"errors": [],
	}


func _copy_runtime(ability_id: String) -> Dictionary:
	if not _abilities_by_id.has(ability_id):
		return {}
	return (_abilities_by_id[ability_id] as Dictionary).duplicate(true)


func _parse_integer_field(value: Variant, field_name: String, result: Dictionary) -> int:
	if typeof(value) == TYPE_INT:
		return int(value)
	if typeof(value) == TYPE_FLOAT:
		var float_value := float(value)
		if not is_nan(float_value) and not is_inf(float_value) and float_value == floor(float_value):
			return int(float_value)
	AbilityResultData.add_error(result, "%s must be an integer" % field_name)
	return 0


func _is_json_compatible(value: Variant) -> bool:
	return _is_json_compatible_recursive(value, [])


func _is_json_compatible_recursive(value: Variant, containers: Array) -> bool:
	var value_type := typeof(value)
	if value == null:
		return true
	if value_type == TYPE_BOOL or value_type == TYPE_INT or value_type == TYPE_STRING or value_type == TYPE_STRING_NAME:
		return true
	if value_type == TYPE_FLOAT:
		var number := float(value)
		return not is_nan(number) and not is_inf(number)
	if value is Array:
		if _contains_same_container(containers, value):
			return false
		containers.append(value)
		for item in value:
			if not _is_json_compatible_recursive(item, containers):
				containers.pop_back()
				return false
		containers.pop_back()
		return true
	if value is Dictionary:
		if _contains_same_container(containers, value):
			return false
		containers.append(value)
		for key in value.keys():
			if typeof(key) != TYPE_STRING and typeof(key) != TYPE_STRING_NAME:
				containers.pop_back()
				return false
			if not _is_json_compatible_recursive(value[key], containers):
				containers.pop_back()
				return false
		containers.pop_back()
		return true
	return false


func _contains_same_container(containers: Array, value: Variant) -> bool:
	for container in containers:
		if is_same(container, value):
			return true
	return false
