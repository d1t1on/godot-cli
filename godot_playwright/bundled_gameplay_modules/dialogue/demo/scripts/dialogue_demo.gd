extends Control

@onready var dialogue_runner: Node = $DialogueRunner


func _ready() -> void:
	dialogue_runner.initialize_dialogues()


func run_dialogue_demo() -> Dictionary:
	var errors: Array[String] = []
	var choices_seen: Dictionary = {}

	var start: Dictionary = dialogue_runner.start_dialogue("guard_greet")
	_assert_ok(start, "start dialogue", errors)
	_assert_string("guard_greet", String(dialogue_runner.get_current_line().get("line_id", "")), "initial line", errors)

	var greet_choices: Array = dialogue_runner.get_choices()
	_assert_int(2, greet_choices.size(), "greet choices count", errors)
	choices_seen["greet"] = greet_choices.size()

	var ask: Dictionary = dialogue_runner.select_choice("ask_business")
	_assert_ok(ask, "select ask_business", errors)
	_assert_string("guard_ask", String(dialogue_runner.get_current_line().get("line_id", "")), "line after ask_business", errors)

	var ask_choices: Array = dialogue_runner.get_choices()
	_assert_int(2, ask_choices.size(), "ask choices count", errors)
	choices_seen["ask"] = ask_choices.size()

	var supplies: Dictionary = dialogue_runner.select_choice("request_supplies")
	_assert_ok(supplies, "select request_supplies", errors)
	_assert_string("guard_supplies", String(dialogue_runner.get_current_line().get("line_id", "")), "line after request_supplies", errors)

	var variables: Dictionary = dialogue_runner.get_variables()
	var status := ""
	if _active_dialogue_exists():
		var dialogue: Dictionary = dialogue_runner.get_dialogue("guard_greet")
		status = String(dialogue.get("status", ""))

	return {
		"ok": errors.is_empty(),
		"errors": errors,
		"dialogue_status": status,
		"final_line_id": String(dialogue_runner.get_current_line().get("line_id", "")),
		"variables": variables,
		"choices_seen": choices_seen,
	}


func _active_dialogue_exists() -> bool:
	var dialogue: Dictionary = dialogue_runner.get_dialogue("guard_greet")
	return not dialogue.is_empty()


func _assert_ok(result: Dictionary, label: String, errors: Array[String]) -> void:
	if not bool(result.get("ok", false)):
		errors.append("%s failed: %s" % [label, str(result)])


func _assert_string(expected: String, actual: String, label: String, errors: Array[String]) -> void:
	if expected != actual:
		errors.append("%s: expected %s, got %s" % [label, expected, actual])


func _assert_int(expected: int, actual: int, label: String, errors: Array[String]) -> void:
	if expected != actual:
		errors.append("%s: expected %d, got %d" % [label, expected, actual])
