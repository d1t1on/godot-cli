extends Node2D

@onready var _interactor := $Actor/Interactor2D
@onready var _low_area := $LowTarget
@onready var _high_area := $HighPickup
@onready var _low := $LowTarget/Interactable
@onready var _pickup := $HighPickup/Interactable
@onready var _door := $Door/Interactable


func run_interaction_demo() -> Dictionary:
	var errors: Array[String] = []
	_reset_demo(errors)

	_interactor.call("_on_node_entered", _low_area)
	_interactor.call("_on_node_entered", _high_area)

	var best = _interactor.get_best_candidate()
	var best_interaction_id := _interaction_id(best)
	_assert_string("high", best_interaction_id, "priority winner", errors)
	_assert_string("Pick up potion", _interactor.get_best_prompt(), "best prompt", errors)

	var pickup_result: Dictionary = _interactor.interact_best()
	_assert_ok(pickup_result, "pickup interaction", errors)
	_assert_string("high", String(pickup_result.get("interaction_id", "")), "pickup interaction id", errors)
	_assert_bool(bool(pickup_result.get("picked_up", false)), "pickup result picked_up", errors)

	var pickup_state: Dictionary = _pickup.get_state()
	_assert_bool(bool(pickup_state.get("picked_up", false)), "pickup state picked_up", errors)
	_assert_bool(not bool(pickup_state.get("enabled", true)), "pickup disabled after collect", errors)
	var pickup_apply_result: Dictionary = _pickup.apply_state(pickup_state)
	_assert_ok(pickup_apply_result, "pickup state round trip", errors)

	var disabled_best = _interactor.get_best_candidate()
	var disabled_best_interaction_id := _interaction_id(disabled_best)
	_assert_string("low", disabled_best_interaction_id, "disabled high is skipped", errors)

	var door_result: Dictionary = _interactor.interact_with(_door)
	_assert_ok(door_result, "door interaction", errors)
	_assert_bool(bool(door_result.get("opened", false)), "door opened result", errors)

	var door_state: Dictionary = _door.get_state()
	_assert_bool(bool(door_state.get("opened", false)), "door state opened", errors)
	var door_apply_result: Dictionary = _door.apply_state(door_state)
	_assert_ok(door_apply_result, "door state round trip", errors)

	_interactor.clear_candidates()
	var no_candidate_result: Dictionary = _interactor.interact_best()
	var no_candidate_ok := bool(no_candidate_result.get("ok", true))
	_assert_bool(not no_candidate_ok, "no candidate should fail", errors)

	return {
		"ok": errors.is_empty(),
		"errors": errors,
		"best_interaction_id": best_interaction_id,
		"disabled_best_interaction_id": disabled_best_interaction_id,
		"pickup_picked_up": bool(_pickup.get("picked_up")),
		"door_opened": bool(_door.get("opened")),
		"no_candidate_ok": no_candidate_ok,
		"pickup_result": pickup_result,
		"door_result": door_result,
		"no_candidate_result": no_candidate_result,
	}


func _reset_demo(errors: Array[String]) -> void:
	_interactor.clear_candidates()

	var low_state: Dictionary = _low.get_state()
	low_state["enabled"] = true
	_assert_ok(_low.apply_state(low_state), "low reset", errors)

	var pickup_state: Dictionary = _pickup.get_state()
	pickup_state["enabled"] = true
	pickup_state["picked_up"] = false
	_assert_ok(_pickup.apply_state(pickup_state), "pickup reset", errors)

	var door_state: Dictionary = _door.get_state()
	door_state["enabled"] = true
	door_state["opened"] = false
	_assert_ok(_door.apply_state(door_state), "door reset", errors)


func _interaction_id(candidate: Node) -> String:
	if candidate == null:
		return ""
	if candidate.has_method("get_interaction_id"):
		return String(candidate.call("get_interaction_id"))
	return String(candidate.name)


func _assert_ok(result: Dictionary, label: String, errors: Array[String]) -> void:
	if not bool(result.get("ok", false)):
		errors.append("%s failed: %s" % [label, str(result)])


func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
	if not value:
		errors.append(message)


func _assert_string(expected: String, actual: String, label: String, errors: Array[String]) -> void:
	if expected != actual:
		errors.append("%s: expected %s, got %s" % [label, expected, actual])
