class_name DialogueDatabase
extends Resource

const DialogueConstantsData := preload("res://addons/dialogue/dialogue_constants.gd")
const DialogueChoiceDefinitionData := preload("res://addons/dialogue/dialogue_choice_definition.gd")
const DialogueLineDefinitionData := preload("res://addons/dialogue/dialogue_line_definition.gd")
const DialogueDefinitionData := preload("res://addons/dialogue/dialogue_definition.gd")
const DialogueResultData := preload("res://addons/dialogue/dialogue_result.gd")

@export var dialogues: Array[Resource] = []


func get_dialogue(dialogue_id: String) -> Resource:
	var normalized := dialogue_id.strip_edges()
	if normalized.is_empty():
		return null
	for dialogue in dialogues:
		var definition = _definition_or_null(dialogue)
		if definition == null:
			continue
		if String(definition.dialogue_id) == normalized:
			return definition
	return null


func has_dialogue(dialogue_id: String) -> bool:
	return get_dialogue(dialogue_id) != null


func get_dialogue_ids() -> Array[String]:
	var ids: Array[String] = []
	for dialogue in dialogues:
		var definition = _definition_or_null(dialogue)
		if definition == null:
			continue
		var raw_dialogue_id := String(definition.dialogue_id)
		var dialogue_id := raw_dialogue_id.strip_edges()
		if not dialogue_id.is_empty() and dialogue_id == raw_dialogue_id:
			ids.append(raw_dialogue_id)
	return ids


func get_line(dialogue_id: String, line_id: String) -> Resource:
	var dialogue: Resource = _definition_or_null(get_dialogue(dialogue_id))
	if dialogue == null:
		return null
	var normalized := line_id.strip_edges()
	if normalized.is_empty():
		return null
	for line in dialogue.lines:
		var definition = _line_or_null(line)
		if definition == null:
			continue
		if String(definition.line_id) == normalized:
			return definition
	return null


func validate() -> Dictionary:
	var result := DialogueResultData.make(true)
	var seen := {}
	for index in range(dialogues.size()):
		var dialogue := dialogues[index]
		if dialogue == null:
			DialogueResultData.add_error(result, "dialogues[%d] is null" % index)
			continue
		var definition: Resource = _definition_or_null(dialogue)
		if definition == null:
			DialogueResultData.add_error(result, "dialogues[%d] must be a DialogueDefinition" % index)
			continue

		var raw_dialogue_id := String(definition.dialogue_id)
		var dialogue_id := raw_dialogue_id.strip_edges()
		if dialogue_id.is_empty():
			DialogueResultData.add_error(result, "dialogues[%d].dialogue_id must be non-empty" % index)
			continue
		if dialogue_id != raw_dialogue_id:
			DialogueResultData.add_error(result, "dialogues[%d].dialogue_id must not contain leading or trailing whitespace" % index)
			continue
		if seen.has(dialogue_id):
			DialogueResultData.add_error(result, "Duplicate dialogue_id: %s" % dialogue_id)
			continue
		seen[dialogue_id] = true

		_validate_definition(definition, dialogue_id, result)
	return result


func _validate_definition(definition: Resource, dialogue_id: String, result: Dictionary) -> void:
	if not _is_json_compatible(definition.default_variables):
		DialogueResultData.add_error(result, "default_variables must be JSON-compatible for dialogue_id: %s" % dialogue_id)
	if not _is_json_compatible(definition.default_data):
		DialogueResultData.add_error(result, "default_data must be JSON-compatible for dialogue_id: %s" % dialogue_id)

	var line_ids := {}
	var has_start_line := false
	for index in range(definition.lines.size()):
		var line: Resource = definition.lines[index]
		if line == null:
			DialogueResultData.add_error(result, "dialogues[%s].lines[%d] is null" % [dialogue_id, index])
			continue
		var line_definition: Resource = _line_or_null(line)
		if line_definition == null:
			DialogueResultData.add_error(result, "dialogues[%s].lines[%d] must be a DialogueLineDefinition" % [dialogue_id, index])
			continue

		var raw_line_id := String(line_definition.line_id)
		var line_id := raw_line_id.strip_edges()
		if line_id.is_empty():
			DialogueResultData.add_error(result, "dialogues[%s].lines[%d].line_id must be non-empty" % [dialogue_id, index])
			continue
		if line_id != raw_line_id:
			DialogueResultData.add_error(result, "dialogues[%s].lines[%d].line_id must not contain leading or trailing whitespace" % [dialogue_id, index])
			continue
		if line_ids.has(line_id):
			DialogueResultData.add_error(result, "Duplicate line_id: %s" % line_id)
			continue
		line_ids[line_id] = true

		if String(definition.start_line_id) == line_id:
			has_start_line = true

	for index in range(definition.lines.size()):
		var line: Resource = definition.lines[index]
		var line_definition: Resource = _line_or_null(line)
		if line_definition == null:
			continue
		var line_id := String(line_definition.line_id).strip_edges()

		if not _is_json_compatible(line_definition.on_enter):
			DialogueResultData.add_error(result, "on_enter must be JSON-compatible for line_id: %s" % line_id)
		if not _is_json_compatible(line_definition.on_exit):
			DialogueResultData.add_error(result, "on_exit must be JSON-compatible for line_id: %s" % line_id)
		if not _is_json_compatible(line_definition.apply_variables):
			DialogueResultData.add_error(result, "apply_variables must be JSON-compatible for line_id: %s" % line_id)
		if not _is_json_compatible(line_definition.default_data):
			DialogueResultData.add_error(result, "default_data must be JSON-compatible for line_id: %s" % line_id)

		var choice_ids := {}
		for choice_index in range(line_definition.choices.size()):
			var choice: Resource = line_definition.choices[choice_index]
			if choice == null:
				DialogueResultData.add_error(result, "dialogues[%s].lines[%s].choices[%d] is null" % [dialogue_id, line_id, choice_index])
				continue
			var choice_definition: Resource = _choice_or_null(choice)
			if choice_definition == null:
				DialogueResultData.add_error(result, "dialogues[%s].lines[%s].choices[%d] must be a DialogueChoiceDefinition" % [dialogue_id, line_id, choice_index])
				continue

			var raw_choice_id := String(choice_definition.choice_id)
			var choice_id := raw_choice_id.strip_edges()
			if choice_id.is_empty():
				DialogueResultData.add_error(result, "dialogues[%s].lines[%s].choices[%d].choice_id must be non-empty" % [dialogue_id, line_id, choice_index])
				continue
			if choice_id != raw_choice_id:
				DialogueResultData.add_error(result, "dialogues[%s].lines[%s].choices[%d].choice_id must not contain leading or trailing whitespace" % [dialogue_id, line_id, choice_index])
				continue
			if choice_ids.has(choice_id):
				DialogueResultData.add_error(result, "Duplicate choice_id: %s" % choice_id)
				continue
			choice_ids[choice_id] = true

			if not _is_json_compatible(choice_definition.on_select):
				DialogueResultData.add_error(result, "on_select must be JSON-compatible for choice_id: %s" % choice_id)
			if not _is_json_compatible(choice_definition.apply_variables):
				DialogueResultData.add_error(result, "apply_variables must be JSON-compatible for choice_id: %s" % choice_id)
			if not _is_json_compatible(choice_definition.default_data):
				DialogueResultData.add_error(result, "default_data must be JSON-compatible for choice_id: %s" % choice_id)

			var choice_next_line_id := String(choice_definition.next_line_id).strip_edges()
			if not choice_next_line_id.is_empty() and not line_ids.has(choice_next_line_id):
				DialogueResultData.add_error(result, "next_line_id references unknown line_id: %s" % choice_next_line_id)

		var next_line_id := String(line_definition.next_line_id).strip_edges()
		if not next_line_id.is_empty() and not line_ids.has(next_line_id):
			DialogueResultData.add_error(result, "next_line_id references unknown line_id: %s" % next_line_id)

	if not has_start_line and not String(definition.start_line_id).is_empty():
		DialogueResultData.add_error(result, "start_line_id must reference an existing line_id for dialogue_id: %s" % dialogue_id)
	if String(definition.start_line_id).is_empty() and definition.lines.size() > 0:
		DialogueResultData.add_error(result, "start_line_id must be non-empty when lines are present for dialogue_id: %s" % dialogue_id)


func _definition_or_null(dialogue: Resource) -> Resource:
	if dialogue == null:
		return null
	if dialogue is DialogueDefinitionData:
		return dialogue
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


# Array and Dictionary are reference types, so identity comparison is the
# correct way to detect recursive self-reference while validating JSON data.
func _contains_same_container(seen: Array, value: Variant) -> bool:
	for container in seen:
		if is_same(container, value):
			return true
	return false
