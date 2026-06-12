class_name EventDatabase
extends Resource

const EventDefinitionData := preload("res://addons/gameplay_events/event_definition.gd")
const GameplayEventResultData := preload("res://addons/gameplay_events/gameplay_event_result.gd")

@export var events: Array[Resource] = []


func get_event(event_id: String) -> Resource:
	var normalized := event_id.strip_edges()
	for event in events:
		if event == null:
			continue
		if not event is EventDefinitionData:
			continue
		if String(event.event_id).strip_edges() == normalized:
			return event
	return null


func has_event(event_id: String) -> bool:
	return get_event(event_id) != null


func get_event_ids() -> Array[String]:
	var ids: Array[String] = []
	for event in events:
		if event == null:
			continue
		if not event is EventDefinitionData:
			continue
		var event_id := String(event.event_id).strip_edges()
		if not event_id.is_empty():
			ids.append(event_id)
	return ids


func get_events() -> Array:
	var copied: Array = []
	for event in events:
		if event != null and event is EventDefinitionData:
			copied.append(event)
	return copied


func validate() -> Dictionary:
	var result := GameplayEventResultData.make(true)
	var seen := {}
	for index in range(events.size()):
		var event: Resource = events[index]
		if event == null:
			GameplayEventResultData.add_error(result, "events[%d] is null" % index)
			continue
		if not event is EventDefinitionData:
			GameplayEventResultData.add_error(result, "events[%d] must be an EventDefinition" % index)
			continue
		var raw_event_id := String(event.event_id)
		var normalized := raw_event_id.strip_edges()
		if normalized.is_empty():
			GameplayEventResultData.add_error(result, "events[%d].event_id must be non-empty" % index)
			continue
		if normalized != raw_event_id:
			GameplayEventResultData.add_error(result, "events[%d].event_id must not contain leading or trailing whitespace" % index)
			continue
		if seen.has(normalized):
			GameplayEventResultData.add_error(result, "Duplicate event_id: %s" % normalized)
			continue
		seen[normalized] = true
		if not _is_json_compatible(event.default_payload):
			GameplayEventResultData.add_error(result, "events[%d].default_payload must be JSON-compatible" % index)
	return result


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
