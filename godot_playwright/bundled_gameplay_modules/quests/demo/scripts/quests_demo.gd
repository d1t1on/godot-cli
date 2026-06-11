extends Control

@onready var quest_log: Node = $QuestLog


func _ready() -> void:
	quest_log.initialize_quests()


func run_quests_demo() -> Dictionary:
	var errors: Array[String] = []
	var start: Dictionary = quest_log.start_quest("repair_beacon", {"source": "demo"})
	_assert_ok(start, "start quest", errors)
	var collect: Dictionary = quest_log.advance_objective("repair_beacon", "collect_parts", 3)
	_assert_ok(collect, "collect parts", errors)
	var scan: Dictionary = quest_log.complete_objective("repair_beacon", "scan_beacon")
	_assert_ok(scan, "scan beacon", errors)
	var repair: Dictionary = quest_log.complete_objective("repair_beacon", "repair_beacon")
	_assert_ok(repair, "repair beacon", errors)
	var quest: Dictionary = quest_log.get_quest("repair_beacon")
	var objectives := _objectives_by_id(quest)
	var rewards: Dictionary = repair.get("rewards", {})
	return {
		"ok": errors.is_empty(),
		"errors": errors,
		"quest_status": String(quest.get("status", "")),
		"collect_progress": int(objectives.get("collect_parts", {}).get("progress", -1)),
		"scan_progress": int(objectives.get("scan_beacon", {}).get("progress", -1)),
		"repair_progress": int(objectives.get("repair_beacon", {}).get("progress", -1)),
		"rewards": rewards,
	}


func _objectives_by_id(quest: Dictionary) -> Dictionary:
	var by_id := {}
	for objective in quest.get("objectives", []):
		by_id[String(objective.get("objective_id", ""))] = objective
	return by_id


func _assert_ok(result: Dictionary, label: String, errors: Array[String]) -> void:
	if not bool(result.get("ok", false)):
		errors.append("%s failed: %s" % [label, str(result)])
