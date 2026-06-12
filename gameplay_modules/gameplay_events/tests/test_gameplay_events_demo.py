from __future__ import annotations


def test_gameplay_events_demo_runs(godot):
    godot.change_scene("res://scenes/gameplay_events_demo/gameplay_events_demo.tscn")
    result = godot.locator("#GameplayEventsDemo").call("run_gameplay_events_demo")
    assert result["ok"], result
    assert result["received_count"] == 1
    assert result["received_item_id"] == "coin"
    assert result["received_quantity"] == 1
    assert result["emit_payload_quantity"] == 1
    assert result["duplicate_warning_count"] >= 1
    assert result["missing_event_ok"] is False
    assert result["bad_payload_ok"] is False
    assert result["unsubscribe_ok"] is True
    assert result["flushed_count"] == 2
    assert result["limited_flush_count"] == 1
    assert result["history_count"] == 4
    assert result["state_queue_count"] == 1
    assert result["state_history_count"] == 0
    assert result["remaining_queue_count"] == 1
    assert result["saved_history_count"] == 4
    assert result["apply_state_ok"] is True
    assert result["restored_queue_count"] == 1
    assert result["restored_history_count"] == 4
