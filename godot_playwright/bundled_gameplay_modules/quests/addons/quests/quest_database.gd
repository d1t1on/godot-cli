class_name QuestDatabase
extends Resource

const QuestConstantsData := preload("res://addons/quests/quest_constants.gd")
const ObjectiveDefinitionData := preload("res://addons/quests/objective_definition.gd")
const QuestDefinitionData := preload("res://addons/quests/quest_definition.gd")
const QuestResultData := preload("res://addons/quests/quest_result.gd")

@export var quests: Array[Resource] = []


func get_quest(quest_id: String) -> Resource:
	var normalized := quest_id.strip_edges()
	if normalized.is_empty():
		return null
	for quest in quests:
		var definition = _definition_or_null(quest)
		if definition == null:
			continue
		if String(definition.quest_id) == normalized:
			return definition
	return null


func has_quest(quest_id: String) -> bool:
	return get_quest(quest_id) != null


func get_quest_ids() -> Array[String]:
	var ids: Array[String] = []
	for quest in quests:
		var definition = _definition_or_null(quest)
		if definition == null:
			continue
		var raw_quest_id := String(definition.quest_id)
		var quest_id := raw_quest_id.strip_edges()
		if not quest_id.is_empty() and quest_id == raw_quest_id:
			ids.append(raw_quest_id)
	return ids


func get_objective(quest_id: String, objective_id: String) -> Resource:
	var quest: Resource = _definition_or_null(get_quest(quest_id))
	if quest == null:
		return null
	var normalized := objective_id.strip_edges()
	if normalized.is_empty():
		return null
	for objective in quest.objectives:
		var definition = _objective_or_null(objective)
		if definition == null:
			continue
		if String(definition.objective_id) == normalized:
			return definition
	return null


func validate() -> Dictionary:
	var result := QuestResultData.make(true)
	var seen := {}
	for index in range(quests.size()):
		var quest := quests[index]
		if quest == null:
			QuestResultData.add_error(result, "quests[%d] is null" % index)
			continue
		var definition: Resource = _definition_or_null(quest)
		if definition == null:
			QuestResultData.add_error(result, "quests[%d] must be a QuestDefinition" % index)
			continue

		var raw_quest_id := String(definition.quest_id)
		var quest_id := raw_quest_id.strip_edges()
		if quest_id.is_empty():
			QuestResultData.add_error(result, "quests[%d].quest_id must be non-empty" % index)
			continue
		if quest_id != raw_quest_id:
			QuestResultData.add_error(result, "quests[%d].quest_id must not contain leading or trailing whitespace" % index)
			continue
		if seen.has(quest_id):
			QuestResultData.add_error(result, "Duplicate quest_id: %s" % quest_id)
			continue
		seen[quest_id] = true

		_validate_definition(definition, quest_id, result)
	return result


func _validate_definition(definition: Resource, quest_id: String, result: Dictionary) -> void:
	var policy := String(definition.completion_policy)
	if not [QuestConstantsData.POLICY_ALL, QuestConstantsData.POLICY_ANY].has(policy):
		QuestResultData.add_error(result, "completion_policy must be one of all or any for quest_id: %s" % quest_id)
	if not _is_json_compatible(definition.rewards):
		QuestResultData.add_error(result, "rewards must be JSON-compatible for quest_id: %s" % quest_id)
	if not _is_json_compatible(definition.default_data):
		QuestResultData.add_error(result, "default_data must be JSON-compatible for quest_id: %s" % quest_id)

	var objective_ids := {}
	for index in range(definition.objectives.size()):
		var objective: Resource = definition.objectives[index]
		if objective == null:
			QuestResultData.add_error(result, "quests[%s].objectives[%d] is null" % [quest_id, index])
			continue
		var objective_definition: Resource = _objective_or_null(objective)
		if objective_definition == null:
			QuestResultData.add_error(result, "quests[%s].objectives[%d] must be an ObjectiveDefinition" % [quest_id, index])
			continue

		var raw_objective_id := String(objective_definition.objective_id)
		var objective_id := raw_objective_id.strip_edges()
		if objective_id.is_empty():
			QuestResultData.add_error(result, "quests[%s].objectives[%d].objective_id must be non-empty" % [quest_id, index])
			continue
		if objective_id != raw_objective_id:
			QuestResultData.add_error(result, "quests[%s].objectives[%d].objective_id must not contain leading or trailing whitespace" % [quest_id, index])
			continue
		if objective_ids.has(objective_id):
			QuestResultData.add_error(result, "Duplicate objective_id: %s" % objective_id)
			continue
		objective_ids[objective_id] = true

		if int(objective_definition.target_amount) < 1:
			QuestResultData.add_error(result, "target_amount must be 1 or greater for objective_id: %s" % objective_id)
		if not _is_json_compatible(objective_definition.default_data):
			QuestResultData.add_error(result, "default_data must be JSON-compatible for objective_id: %s" % objective_id)


func _definition_or_null(quest: Resource) -> Resource:
	if quest == null:
		return null
	if quest is QuestDefinitionData:
		return quest
	return null


func _objective_or_null(objective: Resource) -> Resource:
	if objective == null:
		return null
	if objective is ObjectiveDefinitionData:
		return objective
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
