extends Node

@onready var stats: Node = $Stats

var events: Array[String] = []


func _ready() -> void:
	stats.stat_depleted.connect(_on_stat_depleted)
	stats.stat_filled.connect(_on_stat_filled)


func run_stats_demo() -> Dictionary:
	var errors: Array[String] = []
	events.clear()

	var initialize_result: Dictionary = stats.initialize_stats(true)
	_assert_ok(initialize_result, "initializing stats should succeed", errors)
	_assert_float(100.0, stats.get_value("health"), "initial health", errors)
	_assert_float(100.0, stats.get_base_value("health"), "initial health base", errors)
	_assert_float(4.0, stats.get_value("move_speed"), "initial move speed", errors)

	var damage_result: Dictionary = stats.set_value("health", 75.0)
	_assert_ok(damage_result, "damaging health should succeed", errors)
	_assert_float(75.0, stats.get_value("health"), "health after damage", errors)

	var deplete_result: Dictionary = stats.set_value("health", -25.0)
	_assert_ok(deplete_result, "depleting health should succeed", errors)
	_assert_bool(bool(deplete_result.get("clamped", false)), "depleting health should report clamped", errors)
	_assert_float(0.0, stats.get_value("health"), "health after depletion", errors)
	_assert_contains("depleted:health", events, "health depletion event", errors)

	var fill_result: Dictionary = stats.set_value("health", 100.0)
	_assert_ok(fill_result, "filling health should succeed", errors)
	_assert_float(100.0, stats.get_value("health"), "health after fill", errors)
	_assert_contains("filled:health", events, "health filled event", errors)

	var base_result: Dictionary = stats.set_base_value("health", 40.0)
	_assert_ok(base_result, "lowering health base should succeed", errors)
	_assert_float(40.0, stats.get_base_value("health"), "health base after lower", errors)
	_assert_float(40.0, stats.get_value("health"), "health current after base lower", errors)

	var move_speed_result: Dictionary = stats.set_value("move_speed", 12.0)
	_assert_ok(move_speed_result, "setting move speed should succeed", errors)
	_assert_float(12.0, stats.get_value("move_speed"), "move speed after set", errors)

	var heat_result: Dictionary = stats.set_value("heat", 250.0)
	_assert_ok(heat_result, "setting heat should succeed", errors)
	_assert_bool(bool(heat_result.get("clamped", false)), "heat result should report clamped", errors)
	_assert_float(100.0, stats.get_value("heat"), "heat after clamp", errors)

	var saved_state: Dictionary = stats.get_state()
	var mutate_health_result: Dictionary = stats.set_value("health", 5.0)
	var mutate_move_speed_result: Dictionary = stats.set_value("move_speed", 1.0)
	_assert_ok(mutate_health_result, "mutating health before restore should succeed", errors)
	_assert_ok(mutate_move_speed_result, "mutating move speed before restore should succeed", errors)
	var apply_result: Dictionary = stats.apply_state(saved_state)
	_assert_ok(apply_result, "applying saved stats state should succeed", errors)
	var health_after_restore := float(stats.get_value("health"))
	var move_speed_after_restore := float(stats.get_value("move_speed"))
	_assert_float(40.0, health_after_restore, "health after state restore", errors)
	_assert_float(12.0, move_speed_after_restore, "move speed after state restore", errors)

	var missing_result: Dictionary = stats.set_value("missing", 1.0)
	var missing_stat_ok := bool(missing_result.get("ok", false))
	_assert_bool(not missing_stat_ok, "setting a missing stat should fail", errors)

	var save_load_checked := false
	var save_load_health := -1.0
	var save_load_save_result: Dictionary = {}
	var save_load_load_result: Dictionary = {}
	var save_load_delete_result: Dictionary = {}
	if has_node("/root/SaveService"):
		save_load_checked = true
		var save_service = get_node("/root/SaveService")
		save_service.delete_slot("stats_demo_slot")
		stats.set_value("health", 33.0)
		save_load_save_result = save_service.save_slot("stats_demo_slot")
		stats.set_value("health", 5.0)
		save_load_load_result = save_service.load_slot("stats_demo_slot")
		save_load_delete_result = save_service.delete_slot("stats_demo_slot")
		_assert_ok(save_load_save_result, "SaveService save should succeed", errors)
		_assert_ok(save_load_load_result, "SaveService load should succeed", errors)
		_assert_ok(save_load_delete_result, "SaveService delete should succeed", errors)
		save_load_health = float(stats.get_value("health"))
		_assert_float(33.0, save_load_health, "health after SaveService round-trip", errors)

	return {
		"ok": errors.is_empty(),
		"errors": errors,
		"events": events.duplicate(),
		"initialize_result": initialize_result,
		"damage_result": damage_result,
		"deplete_result": deplete_result,
		"fill_result": fill_result,
		"base_result": base_result,
		"move_speed_result": move_speed_result,
		"heat_result": heat_result,
		"mutate_health_result": mutate_health_result,
		"mutate_move_speed_result": mutate_move_speed_result,
		"apply_result": apply_result,
		"missing_result": missing_result,
		"missing_stat_ok": missing_stat_ok,
		"health_after_restore": health_after_restore,
		"move_speed_after_restore": move_speed_after_restore,
		"save_load_checked": save_load_checked,
		"save_load_health": save_load_health,
		"save_load_save_result": save_load_save_result,
		"save_load_load_result": save_load_load_result,
		"save_load_delete_result": save_load_delete_result,
	}


func _on_stat_depleted(stat_id: String, _current_value: float, _result: Dictionary) -> void:
	events.append("depleted:%s" % stat_id)


func _on_stat_filled(stat_id: String, _current_value: float, _result: Dictionary) -> void:
	events.append("filled:%s" % stat_id)


func _assert_ok(result: Dictionary, message: String, errors: Array[String]) -> void:
	if not bool(result.get("ok", false)):
		errors.append("%s: %s" % [message, ", ".join(PackedStringArray(result.get("errors", [])))])


func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
	if not value:
		errors.append(message)


func _assert_float(expected: float, actual: float, label: String, errors: Array[String]) -> void:
	if absf(expected - actual) > 0.001:
		errors.append("%s: expected %.3f, got %.3f" % [label, expected, actual])


func _assert_contains(expected: String, values: Array, label: String, errors: Array[String]) -> void:
	if not values.has(expected):
		errors.append("%s: expected %s in %s" % [label, expected, str(values)])
