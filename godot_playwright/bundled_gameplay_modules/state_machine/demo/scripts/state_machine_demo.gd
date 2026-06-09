extends Node

@onready var machine: Node = $StateMachine

var transition_history: Array[String] = []


func _ready() -> void:
    machine.state_changed.connect(_on_state_changed)


func run_state_machine_demo() -> Dictionary:
    var initial_state := String(machine.call("get_current_state_id"))
    var move_result: Dictionary = machine.call("transition_to", "move", {"speed": 4})
    var attack_result: Dictionary = machine.call("get_current_state").call("request_attack")
    var forbidden_result: Dictionary = machine.call("transition_to", "forbidden")
    var snapshot: Dictionary = machine.call("get_state")
    var idle_result: Dictionary = machine.call("transition_to", "idle")
    var restore_result: Dictionary = machine.call("apply_state", snapshot)
    var ok := initial_state == "idle"
    ok = ok and bool(move_result.get("ok", false))
    ok = ok and bool(attack_result.get("ok", false))
    ok = ok and not bool(forbidden_result.get("ok", true))
    ok = ok and bool(idle_result.get("ok", false))
    ok = ok and bool(restore_result.get("ok", false))
    ok = ok and String(machine.call("get_current_state_id")) == "attack"
    return {
        "ok": ok,
        "initial_state": initial_state,
        "move_result": move_result,
        "attack_result": attack_result,
        "forbidden_result": forbidden_result,
        "snapshot": snapshot,
        "idle_result": idle_result,
        "restore_result": restore_result,
        "restored_state": String(machine.call("get_current_state_id")),
        "transition_history": transition_history,
    }


func _on_state_changed(previous_state_id: String, current_state_id: String, data: Dictionary) -> void:
    transition_history.append("%s>%s" % [previous_state_id, current_state_id])
