class_name EffectDatabase
extends Resource

const EffectConstantsData := preload("res://addons/effects/effect_constants.gd")
const EffectDefinitionData := preload("res://addons/effects/effect_definition.gd")
const EffectResultData := preload("res://addons/effects/effect_result.gd")

@export var effects: Array[Resource] = []


func get_effect(effect_id: String) -> Resource:
	var normalized := effect_id.strip_edges()
	if normalized.is_empty():
		return null
	for effect in effects:
		var definition = _definition_or_null(effect)
		if definition == null:
			continue
		if String(definition.effect_id) == normalized:
			return definition
	return null


func has_effect(effect_id: String) -> bool:
	return get_effect(effect_id) != null


func validate() -> Dictionary:
	var result := EffectResultData.make(true)
	var seen := {}
	for index in range(effects.size()):
		var effect := effects[index]
		if effect == null:
			EffectResultData.add_error(result, "effects[%d] is null" % index)
			continue
		var definition = _definition_or_null(effect)
		if definition == null:
			EffectResultData.add_error(result, "effects[%d] must be an EffectDefinition" % index)
			continue

		var raw_effect_id := String(definition.effect_id)
		var effect_id := raw_effect_id.strip_edges()
		if effect_id.is_empty():
			EffectResultData.add_error(result, "effects[%d].effect_id must be non-empty" % index)
			continue
		if effect_id != raw_effect_id:
			EffectResultData.add_error(result, "effects[%d].effect_id must not contain leading or trailing whitespace" % index)
			continue
		if seen.has(effect_id):
			EffectResultData.add_error(result, "Duplicate effect_id: %s" % effect_id)
			continue
		seen[effect_id] = true

		var duration := float(definition.duration)
		if not _is_finite_number(duration) or duration < 0.0:
			EffectResultData.add_error(result, "duration must be finite and zero or greater for effect_id: %s" % effect_id)
		var tick_interval := float(definition.tick_interval)
		if not _is_finite_number(tick_interval) or tick_interval < 0.0:
			EffectResultData.add_error(result, "tick_interval must be finite and zero or greater for effect_id: %s" % effect_id)
		var stack_mode := String(definition.stack_mode)
		if not [EffectConstantsData.STACK_REFRESH, EffectConstantsData.STACK_STACK, EffectConstantsData.STACK_IGNORE].has(stack_mode):
			EffectResultData.add_error(result, "stack_mode must be refresh, stack, or ignore for effect_id: %s" % effect_id)
		if int(definition.max_stacks) <= 0:
			EffectResultData.add_error(result, "max_stacks must be positive for effect_id: %s" % effect_id)
		if not _is_json_compatible(definition.default_data):
			EffectResultData.add_error(result, "default_data must be JSON-compatible for effect_id: %s" % effect_id)
	return result


func _definition_or_null(effect: Resource):
	if effect == null:
		return null
	if effect is EffectDefinitionData:
		return effect
	return null


func _is_json_compatible(value: Variant) -> bool:
	match typeof(value):
		TYPE_NIL, TYPE_BOOL, TYPE_STRING, TYPE_INT:
			return true
		TYPE_FLOAT:
			var number := float(value)
			return _is_finite_number(number)
		TYPE_ARRAY:
			for item in value:
				if not _is_json_compatible(item):
					return false
			return true
		TYPE_DICTIONARY:
			for key in value.keys():
				if typeof(key) != TYPE_STRING and typeof(key) != TYPE_STRING_NAME:
					return false
				if not _is_json_compatible(value[key]):
					return false
			return true
		_:
			return false


func _is_finite_number(value: float) -> bool:
	return not is_nan(value) and not is_inf(value)
