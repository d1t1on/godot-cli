class_name AbilityDatabase
extends Resource

const AbilityDefinitionData := preload("res://addons/abilities/ability_definition.gd")
const AbilityResultData := preload("res://addons/abilities/ability_result.gd")

@export var abilities: Array[Resource] = []


func get_ability(ability_id: String) -> Resource:
	var normalized := ability_id.strip_edges()
	if normalized.is_empty():
		return null
	for ability in abilities:
		var definition = _definition_or_null(ability)
		if definition == null:
			continue
		if String(definition.ability_id) == normalized:
			return definition
	return null


func has_ability(ability_id: String) -> bool:
	return get_ability(ability_id) != null


func get_ability_ids() -> Array[String]:
	var ids: Array[String] = []
	for ability in abilities:
		var definition = _definition_or_null(ability)
		if definition == null:
			continue
		var raw_ability_id := String(definition.ability_id)
		var ability_id := raw_ability_id.strip_edges()
		if not ability_id.is_empty() and ability_id == raw_ability_id:
			ids.append(raw_ability_id)
	return ids


func validate() -> Dictionary:
	var result := AbilityResultData.make(true)
	var seen := {}
	for index in range(abilities.size()):
		var ability := abilities[index]
		if ability == null:
			AbilityResultData.add_error(result, "abilities[%d] is null" % index)
			continue
		var definition = _definition_or_null(ability)
		if definition == null:
			AbilityResultData.add_error(result, "abilities[%d] must be an AbilityDefinition" % index)
			continue

		var raw_ability_id := String(definition.ability_id)
		var ability_id := raw_ability_id.strip_edges()
		if ability_id.is_empty():
			AbilityResultData.add_error(result, "abilities[%d].ability_id must be non-empty" % index)
			continue
		if ability_id != raw_ability_id:
			AbilityResultData.add_error(result, "abilities[%d].ability_id must not contain leading or trailing whitespace" % index)
			continue
		if seen.has(ability_id):
			AbilityResultData.add_error(result, "Duplicate ability_id: %s" % ability_id)
			continue
		seen[ability_id] = true

		_validate_definition(definition, ability_id, result)
	return result


func _validate_definition(definition: Resource, ability_id: String, result: Dictionary) -> void:
	if not _is_finite_number(definition.cooldown):
		AbilityResultData.add_error(result, "cooldown must be finite for ability_id: %s" % ability_id)
	elif float(definition.cooldown) < 0.0:
		AbilityResultData.add_error(result, "cooldown must be zero or greater for ability_id: %s" % ability_id)

	if int(definition.max_charges) < 0:
		AbilityResultData.add_error(result, "max_charges must be zero or greater for ability_id: %s" % ability_id)
	if int(definition.initial_charges) < 0:
		AbilityResultData.add_error(result, "initial_charges must be zero or greater for ability_id: %s" % ability_id)
	if int(definition.initial_charges) > int(definition.max_charges):
		AbilityResultData.add_error(result, "initial_charges must be <= max_charges for ability_id: %s" % ability_id)

	if not _is_finite_number(definition.charge_recovery_time):
		AbilityResultData.add_error(result, "charge_recovery_time must be finite for ability_id: %s" % ability_id)
	elif float(definition.charge_recovery_time) < 0.0:
		AbilityResultData.add_error(result, "charge_recovery_time must be zero or greater for ability_id: %s" % ability_id)

	if not _is_json_compatible(definition.costs):
		AbilityResultData.add_error(result, "costs must be JSON-compatible for ability_id: %s" % ability_id)
	elif not _has_numeric_scalar_costs(definition.costs):
		AbilityResultData.add_error(result, "scalar costs must be finite numbers for ability_id: %s" % ability_id)
	if not _is_json_compatible(definition.default_data):
		AbilityResultData.add_error(result, "default_data must be JSON-compatible for ability_id: %s" % ability_id)


func _definition_or_null(ability: Resource):
	if ability == null:
		return null
	if ability is AbilityDefinitionData:
		return ability
	return null


func _is_json_compatible(value: Variant) -> bool:
	var value_type := typeof(value)
	if value == null:
		return true
	if value_type == TYPE_BOOL or value_type == TYPE_INT or value_type == TYPE_STRING or value_type == TYPE_STRING_NAME:
		return true
	if value_type == TYPE_FLOAT:
		var number := float(value)
		return not is_nan(number) and not is_inf(number)
	if value is Array:
		for item in value:
			if not _is_json_compatible(item):
				return false
		return true
	if value is Dictionary:
		for key in value.keys():
			if typeof(key) != TYPE_STRING and typeof(key) != TYPE_STRING_NAME:
				return false
			if not _is_json_compatible(value[key]):
				return false
		return true
	return false


func _has_numeric_scalar_costs(costs: Dictionary) -> bool:
	for key in costs.keys():
		var value: Variant = costs[key]
		if value is Dictionary or value is Array:
			continue
		if not _is_finite_number(value):
			return false
	return true


func _is_finite_number(value: Variant) -> bool:
	if typeof(value) != TYPE_INT and typeof(value) != TYPE_FLOAT:
		return false
	var number := float(value)
	return not is_nan(number) and not is_inf(number)
