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


func emit_event(event_id: String, payload: Dictionary = {}) -> Dictionary:
	var normalized := event_id.strip_edges()
	var result := GameplayEventResultData.make(true, normalized)
	var event := _make_event(normalized, payload, false, result)
	if not bool(result.get("ok", false)):
		event_failed.emit(normalized, result)
		return result
	return _dispatch_event(event, result)


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
