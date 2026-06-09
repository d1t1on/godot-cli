class_name StateMachine
extends Node

const StateMachineConstantsData := preload("res://addons/state_machine/state_machine_constants.gd")
const StateMachineResultData := preload("res://addons/state_machine/state_machine_result.gd")

signal state_started(current_state_id: String, data: Dictionary)
signal state_changed(previous_state_id: String, current_state_id: String, data: Dictionary)
signal transition_failed(previous_state_id: String, target_state_id: String, result: Dictionary)

@export var initial_state_id: StringName
@export var auto_start: bool = true

var _states_by_id: Dictionary = {}
var _state_ids: Array[String] = []
var _initialization_errors: Array[String] = []
var _current_state: Node = null
var _current_state_id: String = ""
var _discovered: bool = false
var _started: bool = false
var _transitioning: bool = false


func _ready() -> void:
    _discover_states()
    if auto_start:
        start()


func _process(delta: float) -> void:
    if _started and is_instance_valid(_current_state) and _current_state.has_method("update"):
        _current_state.call("update", delta)


func _physics_process(delta: float) -> void:
    if _started and is_instance_valid(_current_state) and _current_state.has_method("physics_update"):
        _current_state.call("physics_update", delta)


func _input(event: InputEvent) -> void:
    if _started and is_instance_valid(_current_state) and _current_state.has_method("handle_input"):
        _current_state.call("handle_input", event)


func start(start_state_id: String = "", data: Dictionary = {}) -> Dictionary:
    _ensure_discovered()
    var target_state_id := _resolve_start_state_id(start_state_id)
    var result := StateMachineResultData.make(true, "", target_state_id)
    if _transitioning:
        StateMachineResultData.add_error(result, "StateMachine is already transitioning")
        transition_failed.emit(_current_state_id, target_state_id, result)
        return result
    if _started:
        StateMachineResultData.add_error(result, "StateMachine has already started")
        transition_failed.emit(_current_state_id, target_state_id, result)
        return result
    _append_initialization_errors(result)
    if not result["ok"]:
        transition_failed.emit("", target_state_id, result)
        return result
    if target_state_id.is_empty():
        StateMachineResultData.add_error(result, "StateMachine has no states to start")
        transition_failed.emit("", target_state_id, result)
        return result
    if not _states_by_id.has(target_state_id):
        StateMachineResultData.add_error(result, "Unknown state_id: %s" % target_state_id)
        transition_failed.emit("", target_state_id, result)
        return result

    var target_state: Node = _states_by_id[target_state_id]
    if not _can_enter_state(target_state, null, data):
        StateMachineResultData.add_error(result, "State cannot enter: %s" % target_state_id)
        transition_failed.emit("", target_state_id, result)
        return result

    _transitioning = true
    _current_state = target_state
    _current_state_id = target_state_id
    _started = true
    _call_enter(target_state, null, data)
    _transitioning = false
    state_started.emit(target_state_id, data)
    state_changed.emit("", target_state_id, data)
    return result


func transition_to(target_state_id: String, data: Dictionary = {}) -> Dictionary:
    _ensure_discovered()
    var from_state_id := _current_state_id if _started else ""
    var result := StateMachineResultData.make(true, from_state_id, target_state_id)
    if _transitioning:
        StateMachineResultData.add_error(result, "StateMachine is already transitioning")
        transition_failed.emit(from_state_id, target_state_id, result)
        return result
    _append_initialization_errors(result)
    if not result["ok"]:
        transition_failed.emit(from_state_id, target_state_id, result)
        return result
    if not _started:
        StateMachineResultData.add_error(result, "StateMachine has not started")
        transition_failed.emit(from_state_id, target_state_id, result)
        return result
    if target_state_id.is_empty():
        StateMachineResultData.add_error(result, "target_state_id must be non-empty")
        transition_failed.emit(from_state_id, target_state_id, result)
        return result
    if not _states_by_id.has(target_state_id):
        StateMachineResultData.add_error(result, "Unknown state_id: %s" % target_state_id)
        transition_failed.emit(from_state_id, target_state_id, result)
        return result
    if not _states_by_id.has(_current_state_id) or not is_instance_valid(_current_state):
        StateMachineResultData.add_error(result, "Current state is invalid: %s" % _current_state_id)
        transition_failed.emit(from_state_id, target_state_id, result)
        return result
    if target_state_id == _current_state_id:
        return result

    var previous_state: Node = _current_state
    var target_state: Node = _states_by_id[target_state_id]
    if not _can_exit_state(previous_state, target_state):
        StateMachineResultData.add_error(result, "State cannot exit: %s" % _current_state_id)
        transition_failed.emit(from_state_id, target_state_id, result)
        return result
    if not _can_enter_state(target_state, previous_state, data):
        StateMachineResultData.add_error(result, "State cannot enter: %s" % target_state_id)
        transition_failed.emit(from_state_id, target_state_id, result)
        return result

    _transitioning = true
    _call_exit(previous_state, target_state)
    _current_state = target_state
    _current_state_id = target_state_id
    _call_enter(target_state, previous_state, data)
    _transitioning = false
    state_changed.emit(from_state_id, target_state_id, data)
    return result


func request_transition(target_state_id: String, data: Dictionary = {}) -> Dictionary:
    return transition_to(target_state_id, data)


func get_current_state_id() -> String:
    return _current_state_id if _started else ""


func get_current_state() -> Node:
    if _started and is_instance_valid(_current_state):
        return _current_state
    return null


func has_state(state_id: String) -> bool:
    _ensure_discovered()
    return _states_by_id.has(state_id)


func get_state_ids() -> Array[String]:
    _ensure_discovered()
    var ids: Array[String] = []
    ids.assign(_state_ids)
    return ids


func get_state() -> Dictionary:
    return {
        "schema_version": StateMachineConstantsData.SCHEMA_VERSION,
        "current_state_id": get_current_state_id(),
        "started": _started,
    }


func apply_state(data: Dictionary) -> Dictionary:
    _ensure_discovered()
    var target_state_id := String(data.get("current_state_id", ""))
    var result := StateMachineResultData.make(true, _current_state_id if _started else "", target_state_id)
    if int(data.get("schema_version", -1)) != StateMachineConstantsData.SCHEMA_VERSION:
        StateMachineResultData.add_error(result, "Unsupported state machine schema_version: %s" % str(data.get("schema_version")))
        return result

    var saved_started = data.get("started")
    if typeof(saved_started) != TYPE_BOOL:
        StateMachineResultData.add_error(result, "StateMachine snapshot started must be a bool")
        return result
    if not bool(saved_started):
        if _started:
            StateMachineResultData.add_error(result, "Cannot apply an unstarted snapshot to a started StateMachine")
        return result
    if target_state_id.is_empty():
        StateMachineResultData.add_error(result, "StateMachine snapshot current_state_id must be non-empty when started")
        return result
    if not _states_by_id.has(target_state_id):
        StateMachineResultData.add_error(result, "Unknown state_id: %s" % target_state_id)
        return result
    if _started:
        return transition_to(target_state_id)
    return start(target_state_id)


func _ensure_discovered() -> void:
    if not _discovered:
        _discover_states()


func _discover_states() -> void:
    _states_by_id.clear()
    _state_ids.clear()
    _initialization_errors.clear()
    for child in get_children():
        if not child is Node:
            continue
        var state_node := child as Node
        var resolved_id := _resolve_state_id(state_node)
        if resolved_id.is_empty():
            _initialization_errors.append("State child has empty state_id: %s" % state_node.name)
            continue
        if _states_by_id.has(resolved_id):
            _initialization_errors.append("Duplicate state_id: %s" % resolved_id)
            continue
        _states_by_id[resolved_id] = state_node
        _state_ids.append(resolved_id)
    _discovered = true


func _resolve_start_state_id(start_state_id: String) -> String:
    if not start_state_id.is_empty():
        return start_state_id
    var configured_initial_state_id := String(initial_state_id)
    if not configured_initial_state_id.is_empty():
        return configured_initial_state_id
    if not _state_ids.is_empty():
        return _state_ids[0]
    return ""


func _resolve_state_id(state_node: Node) -> String:
    if state_node.has_method("get_state_id"):
        var method_id := String(state_node.call("get_state_id"))
        if not method_id.is_empty():
            return method_id
    var property_id = state_node.get("state_id")
    if property_id != null and not String(property_id).is_empty():
        return String(property_id)
    return String(state_node.name)


func _append_initialization_errors(result: Dictionary) -> void:
    for error in _initialization_errors:
        StateMachineResultData.add_error(result, error)


func _can_enter_state(target_state: Node, previous_state: Node, data: Dictionary) -> bool:
    if not target_state.has_method("can_enter"):
        return true
    return bool(target_state.call("can_enter", previous_state, data))


func _can_exit_state(previous_state: Node, target_state: Node) -> bool:
    if not previous_state.has_method("can_exit"):
        return true
    return bool(previous_state.call("can_exit", target_state))


func _call_enter(target_state: Node, previous_state: Node, data: Dictionary) -> void:
    if target_state.has_method("enter"):
        target_state.call("enter", previous_state, data)


func _call_exit(previous_state: Node, target_state: Node) -> void:
    if previous_state.has_method("exit"):
        previous_state.call("exit", target_state)
