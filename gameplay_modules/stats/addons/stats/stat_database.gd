class_name StatDatabase
extends Resource

const StatDefinitionData := preload("res://addons/stats/stat_definition.gd")
const StatResultData := preload("res://addons/stats/stat_result.gd")

@export var stats: Array[Resource] = []


func get_stat(stat_id: String) -> Resource:
	var normalized := stat_id.strip_edges()
	if normalized.is_empty():
		return null
	for stat in stats:
		var definition = _definition_or_null(stat)
		if definition == null:
			continue
		if String(definition.stat_id) == normalized:
			return definition
	return null


func has_stat(stat_id: String) -> bool:
	return get_stat(stat_id) != null


func get_stat_ids() -> Array[String]:
	var ids: Array[String] = []
	for stat in stats:
		var definition = _definition_or_null(stat)
		if definition == null:
			continue
		var raw_stat_id := String(definition.stat_id)
		var stat_id := raw_stat_id.strip_edges()
		if not stat_id.is_empty() and stat_id == raw_stat_id:
			ids.append(raw_stat_id)
	return ids


func validate() -> Dictionary:
	var result := StatResultData.make(true)
	var seen := {}
	for index in range(stats.size()):
		var stat := stats[index]
		if stat == null:
			StatResultData.add_error(result, "stats[%d] is null" % index)
			continue
		var definition = _definition_or_null(stat)
		if definition == null:
			StatResultData.add_error(result, "stats[%d] must be a StatDefinition" % index)
			continue
		var raw_stat_id := String(definition.stat_id)
		var stat_id := raw_stat_id.strip_edges()
		if stat_id.is_empty():
			StatResultData.add_error(result, "stats[%d].stat_id must be non-empty" % index)
			continue
		if stat_id != raw_stat_id:
			StatResultData.add_error(result, "stats[%d].stat_id must not contain leading or trailing whitespace" % index)
			continue
		if seen.has(stat_id):
			StatResultData.add_error(result, "Duplicate stat_id: %s" % stat_id)
			continue
		seen[stat_id] = true
		_validate_definition_numbers(definition, stat_id, result)
	return result


func _validate_definition_numbers(definition: Resource, stat_id: String, result: Dictionary) -> void:
	if not _is_finite_number(definition.default_base_value):
		StatResultData.add_error(result, "default_base_value must be finite for stat_id: %s" % stat_id)
	if not _is_finite_number(definition.default_current_value):
		StatResultData.add_error(result, "default_current_value must be finite for stat_id: %s" % stat_id)
	if not _is_finite_number(definition.min_value):
		StatResultData.add_error(result, "min_value must be finite for stat_id: %s" % stat_id)
	if not _is_finite_number(definition.max_value):
		StatResultData.add_error(result, "max_value must be finite for stat_id: %s" % stat_id)
	if bool(definition.clamp_min) and bool(definition.clamp_max) and float(definition.min_value) > float(definition.max_value):
		StatResultData.add_error(result, "min_value must be <= max_value for stat_id: %s" % stat_id)


func _definition_or_null(stat: Resource):
	if stat == null:
		return null
	if stat is StatDefinitionData:
		return stat
	return null


func _is_finite_number(value: Variant) -> bool:
	if typeof(value) != TYPE_INT and typeof(value) != TYPE_FLOAT:
		return false
	var number := float(value)
	return not is_nan(number) and not is_inf(number)
