extends Node

@onready var event_bus: Node = $GameplayEventBus

var _received_items: Array = []


func run_gameplay_events_demo() -> Dictionary:
	_received_items.clear()
	var errors: Array[String] = []
	var subscribed: Dictionary = event_bus.subscribe("item_collected", self, &"_on_item_collected")
	_assert_ok(subscribed, "subscribe item_collected", errors)
	var duplicate_subscribe: Dictionary = event_bus.subscribe("item_collected", self, &"_on_item_collected")
	_assert_ok(duplicate_subscribe, "duplicate subscribe item_collected", errors)
	var emitted: Dictionary = event_bus.emit_event("item_collected", {"item_id": "coin"})
	_assert_ok(emitted, "emit item_collected", errors)
	var missing_event: Dictionary = event_bus.emit_event("missing_event", {})
	if bool(missing_event.get("ok", true)):
		errors.append("missing_event should fail")
	var bad_payload: Dictionary = event_bus.emit_event("item_collected", {"node": self})
	if bool(bad_payload.get("ok", true)):
		errors.append("non-json payload should fail")
	var queued_door: Dictionary = event_bus.queue_event("door_opened", {"door_id": "north_gate"})
	_assert_ok(queued_door, "queue door_opened", errors)
	var queued_quest: Dictionary = event_bus.queue_event("quest_progressed", {"quest_id": "repair_beacon"})
	_assert_ok(queued_quest, "queue quest_progressed", errors)
	var flushed: Array[Dictionary] = event_bus.flush_events()
	if flushed.size() != 2:
		errors.append("expected 2 flushed events, got %d" % flushed.size())
	var unsubscribed: Dictionary = event_bus.unsubscribe("item_collected", self, &"_on_item_collected")
	_assert_ok(unsubscribed, "unsubscribe item_collected", errors)
	event_bus.queue_event("door_opened", {"door_id": "west_gate"})
	event_bus.queue_event("quest_progressed", {"quest_id": "repair_beacon", "amount": 2})
	var limited_flush: Array[Dictionary] = event_bus.flush_events(1)
	if limited_flush.size() != 1:
		errors.append("expected 1 limited flush result, got %d" % limited_flush.size())
	var history: Array = event_bus.get_history()
	var state: Dictionary = event_bus.get_state()
	var remaining_queue_count := (state.get("queue", []) as Array).size()
	event_bus.save_history = true
	var saved_state: Dictionary = event_bus.get_state()
	var saved_history_count := (saved_state.get("history", []) as Array).size()
	event_bus.clear_history()
	event_bus.clear_queue()
	var applied: Dictionary = event_bus.apply_state(saved_state)
	_assert_ok(applied, "apply saved state", errors)
	var restored_state: Dictionary = event_bus.get_state()
	return {
		"ok": errors.is_empty(),
		"errors": errors,
		"received_count": _received_items.size(),
		"received_item_id": _received_items[0].get("item_id", "") if not _received_items.is_empty() else "",
		"received_quantity": int(_received_items[0].get("quantity", 0)) if not _received_items.is_empty() else 0,
		"emit_payload_quantity": int((emitted.get("payload", {}) as Dictionary).get("quantity", 0)),
		"duplicate_warning_count": (duplicate_subscribe.get("warnings", []) as Array).size(),
		"missing_event_ok": bool(missing_event.get("ok", true)),
		"bad_payload_ok": bool(bad_payload.get("ok", true)),
		"unsubscribe_ok": bool(unsubscribed.get("ok", false)),
		"flushed_count": flushed.size(),
		"limited_flush_count": limited_flush.size(),
		"history_count": history.size(),
		"state_queue_count": (state.get("queue", []) as Array).size(),
		"state_history_count": (state.get("history", []) as Array).size(),
		"remaining_queue_count": remaining_queue_count,
		"saved_history_count": saved_history_count,
		"apply_state_ok": bool(applied.get("ok", false)),
		"restored_queue_count": (restored_state.get("queue", []) as Array).size(),
		"restored_history_count": (restored_state.get("history", []) as Array).size(),
	}


func _on_item_collected(event: Dictionary) -> void:
	_received_items.append((event.get("payload", {}) as Dictionary).duplicate(true))


func _assert_ok(result: Dictionary, label: String, errors: Array[String]) -> void:
	if not bool(result.get("ok", false)):
		errors.append("%s failed: %s" % [label, str(result)])
