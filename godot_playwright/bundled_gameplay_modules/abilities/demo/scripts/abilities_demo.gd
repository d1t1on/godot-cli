extends Node

@onready var abilities: Node = $AbilityContainer


func run_abilities_demo() -> Dictionary:
	var errors: Array[String] = []

	var initialize_result: Dictionary = abilities.initialize_abilities(true)
	_assert_ok(initialize_result, "initializing abilities should succeed", errors)

	var dash_result: Dictionary = abilities.activate("dash")
	_assert_ok(dash_result, "activating dash should succeed", errors)
	_assert_float(20.0, float(dash_result.get("costs", {}).get("stamina", 0.0)), "dash reported stamina cost", errors)
	_assert_float(4.0, float(dash_result.get("data", {}).get("range", 0.0)), "dash reported range", errors)

	var second_dash_result: Dictionary = abilities.activate("dash")
	_assert_bool(not bool(second_dash_result.get("ok", true)), "immediate second dash should fail", errors)

	var dash_events: Array = abilities.update_abilities(0.5)
	_assert_has_event(dash_events, "ability_cooldown_ready", "dash", "dash cooldown ready event", errors)
	_assert_has_event(dash_events, "ability_charge_recovered", "dash", "dash charge recovered event", errors)
	var dash_after_recovery: Dictionary = abilities.activate("dash")
	_assert_ok(dash_after_recovery, "dash should activate again after recovery", errors)

	var disable_scan_result: Dictionary = abilities.set_enabled("scan", false)
	_assert_ok(disable_scan_result, "disabling scan should succeed", errors)
	_assert_bool(not abilities.is_enabled("scan"), "scan should be disabled", errors)
	var disabled_scan_result: Dictionary = abilities.activate("scan")
	_assert_bool(not bool(disabled_scan_result.get("ok", true)), "disabled scan should fail", errors)
	var enable_scan_result: Dictionary = abilities.set_enabled("scan", true)
	_assert_ok(enable_scan_result, "re-enabling scan should succeed", errors)
	_assert_bool(abilities.is_enabled("scan"), "scan should be enabled", errors)

	var scan_result: Dictionary = abilities.activate("scan", {"target_id": "crate_01"})
	_assert_ok(scan_result, "activating scan should succeed", errors)
	_assert_float(6.0, float(scan_result.get("data", {}).get("range", 0.0)), "scan reported range", errors)
	_assert_string("crate_01", String(scan_result.get("context", {}).get("target_id", "")), "scan context target_id", errors)

	var repair_first_result: Dictionary = abilities.activate("repair")
	var repair_second_result: Dictionary = abilities.activate("repair")
	_assert_ok(repair_first_result, "first repair should succeed", errors)
	_assert_ok(repair_second_result, "second repair should succeed", errors)
	_assert_int(0, int(abilities.get_ability_runtime("repair").get("charges", -1)), "repair charges after two activations", errors)
	_assert_float(1.0, float(repair_first_result.get("costs", {}).get("parts", 0.0)), "repair reported parts cost", errors)
	_assert_float(15.0, float(repair_first_result.get("data", {}).get("amount", 0.0)), "repair reported amount", errors)

	var repair_events: Array = abilities.update_abilities(2.0)
	_assert_has_event(repair_events, "ability_charge_recovered", "repair", "repair charge recovered event", errors)
	var repair_after_recovery: Dictionary = abilities.get_ability_runtime("repair")
	_assert_int(1, int(repair_after_recovery.get("charges", -1)), "repair recovered one charge", errors)

	return {
		"ok": errors.is_empty(),
		"errors": errors,
		"dash_result": dash_result,
		"second_dash_result": second_dash_result,
		"dash_after_recovery": dash_after_recovery,
		"disable_scan_result": disable_scan_result,
		"disabled_scan_result": disabled_scan_result,
		"enable_scan_result": enable_scan_result,
		"scan_result": scan_result,
		"repair_first_result": repair_first_result,
		"repair_second_result": repair_second_result,
		"repair_charges_after_recovery": int(repair_after_recovery.get("charges", -1)),
	}


func _assert_ok(result: Dictionary, message: String, errors: Array[String]) -> void:
	if not bool(result.get("ok", false)):
		errors.append("%s: %s" % [message, str(result)])


func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
	if not value:
		errors.append(message)


func _assert_string(expected: String, actual: String, label: String, errors: Array[String]) -> void:
	if expected != actual:
		errors.append("%s: expected %s, got %s" % [label, expected, actual])


func _assert_int(expected: int, actual: int, label: String, errors: Array[String]) -> void:
	if expected != actual:
		errors.append("%s: expected %d, got %d" % [label, expected, actual])


func _assert_float(expected: float, actual: float, label: String, errors: Array[String]) -> void:
	if absf(expected - actual) > 0.001:
		errors.append("%s: expected %.3f, got %.3f" % [label, expected, actual])


func _assert_has_event(events: Array, event_type: String, ability_id: String, label: String, errors: Array[String]) -> void:
	for event in events:
		if String(event.get("type", "")) == event_type and String(event.get("ability_id", "")) == ability_id:
			return
	errors.append("%s missing %s for %s in %s" % [label, event_type, ability_id, str(events)])
