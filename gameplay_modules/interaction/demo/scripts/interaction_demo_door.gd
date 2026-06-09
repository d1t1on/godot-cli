extends "res://addons/interaction/interactable.gd"

var opened: bool = false


func interact(actor: Node, data: Dictionary = {}) -> Dictionary:
	var result := super.interact(actor, data)
	if not bool(result.get("ok", false)):
		return result
	opened = not opened
	result["opened"] = opened
	return result


func get_state() -> Dictionary:
	var state := super.get_state()
	state["opened"] = opened
	return state


func apply_state(data: Dictionary) -> Dictionary:
	var result := super.apply_state(data)
	var raw_opened = data.get("opened", null)
	if typeof(raw_opened) != TYPE_BOOL:
		InteractionResultData.add_error(result, "opened must be a bool")
	if not bool(result.get("ok", false)):
		return result
	opened = bool(raw_opened)
	return result
