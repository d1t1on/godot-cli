class_name GameplayEventBus
extends Node

const GameplayEventConstantsData := preload("res://addons/gameplay_events/gameplay_event_constants.gd")
const GameplayEventResultData := preload("res://addons/gameplay_events/gameplay_event_result.gd")

signal event_emitted(event_id: String, event: Dictionary, result: Dictionary)
signal event_queued(event_id: String, event: Dictionary, result: Dictionary)
signal event_failed(event_id: String, result: Dictionary)
signal queue_flushed(events: Array)
signal events_changed(event: Dictionary)

@export var database: Resource
@export var save_id: StringName
@export var record_history: bool = true
@export_range(0, 10000, 1) var max_history: int = 100
@export var save_history: bool = false
@export var auto_flush: bool = false
@export_range(0, 10000, 1) var auto_flush_limit: int = 0

var _sequence: int = 0
var _queue: Array[Dictionary] = []
var _history: Array[Dictionary] = []
var _subscribers_by_event_id: Dictionary = {}


func _enter_tree() -> void:
	if not String(save_id).is_empty():
		add_to_group(GameplayEventConstantsData.SAVE_GROUP)


func _process(delta: float) -> void:
	if auto_flush:
		flush_events(auto_flush_limit)


func emit_event(event_id: String, payload: Dictionary = {}) -> Dictionary:
	var normalized := event_id.strip_edges()
	var result := GameplayEventResultData.make(true, normalized)
	var event := _make_event(normalized, payload, false, result)
	if not bool(result.get("ok", false)):
		event_failed.emit(normalized, result)
		return result
	return _dispatch_event(event, result)


func queue_event(event_id: String, payload: Dictionary = {}) -> Dictionary:
	var normalized := event_id.strip_edges()
	var result := GameplayEventResultData.make(true, normalized)
	var event := _make_event(normalized, payload, true, result)
	if not bool(result.get("ok", false)):
		event_failed.emit(normalized, result)
		return result
	_queue.append(_copy_event(event))
	result["event"] = _copy_event(event)
	var changed_event := _make_result_event(GameplayEventConstantsData.EVENT_QUEUED, event)
	GameplayEventResultData.add_event(result, changed_event)
	event_queued.emit(normalized, _copy_event(event), result)
	events_changed.emit(changed_event)
	return result


func flush_events(limit: int = 0) -> Array[Dictionary]:
	var results: Array[Dictionary] = []
	if limit < 0:
		var failed := GameplayEventResultData.make(false)
		GameplayEventResultData.add_error(failed, "limit must be zero or greater")
		event_failed.emit("", failed)
		return results

	var remaining := limit
	while not _queue.is_empty() and (limit == 0 or remaining > 0):
		var event := _queue.pop_front()
		var result := GameplayEventResultData.make(true, String(event.get("event_id", "")))
		result["payload"] = (event.get("payload", {}) as Dictionary).duplicate(true)
		result["event"] = _copy_event(event)
		results.append(_dispatch_event(event, result))
		if limit > 0:
			remaining -= 1

	var emitted_events: Array = []
	for result in results:
		if bool(result.get("ok", false)) and result.get("event", {}) is Dictionary:
			emitted_events.append((result.get("event", {}) as Dictionary).duplicate(true))
	queue_flushed.emit(emitted_events)
	return results


func clear_queue() -> void:
	if _queue.is_empty():
		return
	_queue.clear()
	var changed_event := _make_result_event(GameplayEventConstantsData.EVENT_QUEUE_CLEARED, {})
	events_changed.emit(changed_event)


func subscribe(event_id: String, target: Object, method: StringName) -> Dictionary:
	var normalized := event_id.strip_edges()
	var result := GameplayEventResultData.make(true, normalized)
	if not _validate_event_id(result, normalized):
		return result
	if target == null:
		GameplayEventResultData.add_error(result, "target must be non-null")
		return result
	if String(method).strip_edges().is_empty():
		GameplayEventResultData.add_error(result, "method must be non-empty")
		return result
	if not target.has_method(method):
		GameplayEventResultData.add_error(result, "target does not have method: %s" % String(method))
		return result
	var subscribers: Array = _subscribers_by_event_id.get(normalized, [])
	for subscriber in subscribers:
		if subscriber.get("target") == target and subscriber.get("method") == method:
			GameplayEventResultData.add_warning(result, "Duplicate subscription ignored: %s.%s" % [normalized, String(method)])
			return result
	subscribers.append({"target": target, "method": method})
	_subscribers_by_event_id[normalized] = subscribers
	return result


func unsubscribe(event_id: String, target: Object, method: StringName) -> Dictionary:
	var normalized := event_id.strip_edges()
	var result := GameplayEventResultData.make(true, normalized)
	if not _validate_event_id(result, normalized):
		return result
	var subscribers: Array = _subscribers_by_event_id.get(normalized, [])
	for index in range(subscribers.size()):
		var subscriber: Dictionary = subscribers[index]
		if subscriber.get("target") == target and subscriber.get("method") == method:
			subscribers.remove_at(index)
			if subscribers.is_empty():
				_subscribers_by_event_id.erase(normalized)
			else:
				_subscribers_by_event_id[normalized] = subscribers
			return result
	GameplayEventResultData.add_warning(result, "Subscription not found: %s.%s" % [normalized, String(method)])
	return result


func clear_subscribers(event_id: String = "") -> void:
	var normalized := event_id.strip_edges()
	if normalized.is_empty():
		_subscribers_by_event_id.clear()
	else:
		_subscribers_by_event_id.erase(normalized)


func has_event(event_id: String) -> bool:
	if database == null or not database.has_method("has_event"):
		return false
	return bool(database.call("has_event", event_id.strip_edges()))


func get_event_definition(event_id: String) -> Resource:
	if database == null or not database.has_method("get_event"):
		return null
	return database.call("get_event", event_id.strip_edges())


func get_event_ids() -> Array[String]:
	if database == null or not database.has_method("get_event_ids"):
		return []
	var ids: Array[String] = []
	ids.assign(database.call("get_event_ids"))
	return ids


func get_history(limit: int = 0) -> Array:
	if limit == 0:
		return _copy_event_array(_history)
	if limit < 0:
		return []
	var start_index := maxi(0, _history.size() - limit)
	var copied: Array = []
	for index in range(start_index, _history.size()):
		copied.append(_copy_event(_history[index]))
	return copied


func clear_history() -> void:
	if _history.is_empty():
		return
	_history.clear()
	var changed_event := _make_result_event(GameplayEventConstantsData.EVENT_HISTORY_CLEARED, {})
	events_changed.emit(changed_event)


func get_state() -> Dictionary:
	return {
		"schema_version": GameplayEventConstantsData.SCHEMA_VERSION,
		"sequence": _sequence,
		"queue": _copy_event_array(_queue),
		"history": _copy_event_array(_history) if save_history else [],
	}


func apply_state(data: Dictionary) -> Dictionary:
	var result := GameplayEventResultData.make(true)
	var raw_schema_version = data.get("schema_version", null)
	if typeof(raw_schema_version) != TYPE_INT:
		GameplayEventResultData.add_error(result, "schema_version must be an integer")

	var next_sequence := _parse_integer_field(data.get("sequence", null), "sequence", result)
	if next_sequence < 0:
		GameplayEventResultData.add_error(result, "sequence must be zero or greater")

	var next_queue := _parse_event_array(data.get("queue", []), "queue", result)
	var next_history := _parse_event_array(data.get("history", []), "history", result)
	if not bool(result.get("ok", false)):
		return result

	_sequence = next_sequence
	_queue = next_queue
	_history = next_history
	var changed_event := {
		"ok": true,
		"type": GameplayEventConstantsData.EVENT_STATE_APPLIED,
		"event_id": "",
		"warnings": [],
		"errors": [],
	}
	GameplayEventResultData.add_event(result, changed_event)
	events_changed.emit(changed_event)
	return result


func get_save_id() -> String:
	return String(save_id)


func save_state() -> Dictionary:
	return get_state()


func load_state(data: Dictionary) -> void:
	var result := apply_state(data)
	if not bool(result.get("ok", false)):
		push_warning("GameplayEventBus load_state failed: %s" % ", ".join(PackedStringArray(result.get("errors", []))))


func _validate_event_id(result: Dictionary, event_id: String) -> bool:
	if event_id.is_empty():
		GameplayEventResultData.add_error(result, "event_id must be non-empty")
	if not _validate_database(result):
		return false
	if not bool(result.get("ok", false)):
		return false
	if not bool(database.call("has_event", event_id)):
		GameplayEventResultData.add_error(result, "Unknown event_id: %s" % event_id)
	return bool(result.get("ok", false))


func _validate_database(result: Dictionary) -> bool:
	if database == null:
		GameplayEventResultData.add_error(result, "database must be assigned")
		return false
	var required_methods := ["has_event", "get_event", "get_event_ids", "validate"]
	for method_name in required_methods:
		if not database.has_method(method_name):
			GameplayEventResultData.add_error(result, "database missing required method: %s" % method_name)
			return false
	var validation: Dictionary = database.call("validate")
	if not bool(validation.get("ok", false)):
		for warning in validation.get("warnings", []):
			GameplayEventResultData.add_warning(result, String(warning))
		for error in validation.get("errors", []):
			GameplayEventResultData.add_error(result, String(error))
		return false
	return true


func _make_event(event_id: String, payload: Dictionary, queued: bool, result: Dictionary) -> Dictionary:
	if not _validate_event_id(result, event_id):
		return {}
	if not _is_json_compatible(payload):
		GameplayEventResultData.add_error(result, "payload must be JSON-compatible")
		return {}
	var definition: Resource = database.call("get_event", event_id)
	var merged_payload: Dictionary = (definition.default_payload as Dictionary).duplicate(true)
	for key in payload.keys():
		merged_payload[key] = payload[key]
	_sequence += 1
	var event := {
		"event_id": event_id,
		"payload": merged_payload.duplicate(true),
		"sequence": _sequence,
		"queued": queued,
		"timestamp_msec": Time.get_ticks_msec(),
	}
	result["payload"] = merged_payload.duplicate(true)
	result["event"] = _copy_event(event)
	return event


func _dispatch_event(event: Dictionary, result: Dictionary) -> Dictionary:
	var event_id := String(event.get("event_id", ""))
	var definition: Resource = database.call("get_event", event_id)
	_record_history(event, definition)
	var emitted_event := _make_result_event(GameplayEventConstantsData.EVENT_EMITTED, event)
	GameplayEventResultData.add_event(result, emitted_event)
	event_emitted.emit(event_id, _copy_event(event), result)
	var subscribers: Array = _subscribers_by_event_id.get(event_id, [])
	result["subscriber_count"] = subscribers.size()
	for subscriber in subscribers:
		var target: Object = subscriber.get("target")
		var method: StringName = subscriber.get("method")
		if target == null or not is_instance_valid(target):
			GameplayEventResultData.add_error(result, "subscriber target is no longer valid: %s" % event_id)
			continue
		if not target.has_method(method):
			GameplayEventResultData.add_error(result, "subscriber method missing: %s" % String(method))
			continue
		target.call(method, _copy_event(event))
	if not bool(result.get("ok", false)):
		event_failed.emit(event_id, result)
	events_changed.emit(emitted_event)
	return result


func _record_history(event: Dictionary, definition: Resource) -> void:
	if not record_history or max_history <= 0:
		return
	if definition != null and not bool(definition.record_by_default):
		return
	_history.append(_copy_event(event))
	while _history.size() > max_history:
		_history.pop_front()


func _make_result_event(type: String, event: Dictionary) -> Dictionary:
	return {
		"ok": true,
		"type": type,
		"event_id": String(event.get("event_id", "")),
		"event": _copy_event(event),
		"warnings": [],
		"errors": [],
	}


func _copy_event(event: Dictionary) -> Dictionary:
	return event.duplicate(true)


func _copy_event_array(events: Array) -> Array:
	var copied: Array = []
	for event in events:
		copied.append(_copy_event(event))
	return copied


func _parse_event_array(value: Variant, field_name: String, result: Dictionary) -> Array[Dictionary]:
	var parsed: Array[Dictionary] = []
	if not value is Array:
		GameplayEventResultData.add_error(result, "%s must be an array" % field_name)
		return parsed
	var raw_events: Array = value
	for index in range(raw_events.size()):
		var parsed_event := _parse_event_state(raw_events[index], "%s[%d]" % [field_name, index], result)
		if not parsed_event.is_empty():
			parsed.append(parsed_event)
	return parsed


func _parse_event_state(value: Variant, field_name: String, result: Dictionary) -> Dictionary:
	if not value is Dictionary:
		GameplayEventResultData.add_error(result, "%s must be a dictionary" % field_name)
		return {}
	var raw_event: Dictionary = value
	var event_id := String(raw_event.get("event_id", "")).strip_edges()
	var field_result := GameplayEventResultData.make(true, event_id)
	if not _validate_event_id(field_result, event_id):
		for error in field_result.get("errors", []):
			GameplayEventResultData.add_error(result, "%s.%s" % [field_name, String(error)])
		return {}

	var raw_payload = raw_event.get("payload", null)
	if not raw_payload is Dictionary:
		GameplayEventResultData.add_error(result, "%s.payload must be a dictionary" % field_name)
	elif not _is_json_compatible(raw_payload):
		GameplayEventResultData.add_error(result, "%s.payload must be JSON-compatible" % field_name)

	var sequence := _parse_integer_field(raw_event.get("sequence", null), "%s.sequence" % field_name, result)
	if sequence < 0:
		GameplayEventResultData.add_error(result, "%s.sequence must be zero or greater" % field_name)

	var raw_queued = raw_event.get("queued", null)
	if typeof(raw_queued) != TYPE_BOOL:
		GameplayEventResultData.add_error(result, "%s.queued must be a bool" % field_name)

	var timestamp_msec := _parse_integer_field(raw_event.get("timestamp_msec", null), "%s.timestamp_msec" % field_name, result)
	if timestamp_msec < 0:
		GameplayEventResultData.add_error(result, "%s.timestamp_msec must be zero or greater" % field_name)

	if not bool(result.get("ok", false)):
		return {}
	return {
		"event_id": event_id,
		"payload": (raw_payload as Dictionary).duplicate(true),
		"sequence": sequence,
		"queued": bool(raw_queued),
		"timestamp_msec": timestamp_msec,
	}


func _parse_integer_field(value: Variant, field_name: String, result: Dictionary) -> int:
	if typeof(value) == TYPE_INT:
		return int(value)
	if typeof(value) == TYPE_FLOAT:
		var float_value := float(value)
		if float_value == floor(float_value):
			return int(float_value)
	GameplayEventResultData.add_error(result, "%s must be an integer" % field_name)
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


func _contains_same_container(containers: Array, value: Variant) -> bool:
	for container in containers:
		if is_same(container, value):
			return true
	return false
