from __future__ import annotations


def test_interaction_demo_runs(godot):
    godot.change_scene("res://scenes/interaction_demo/interaction_demo.tscn")
    result = godot.locator("#InteractionDemo").call("run_interaction_demo")
    assert result["ok"], result
    assert result["best_interaction_id"] == "high"
    assert result["disabled_best_interaction_id"] == "low"
    assert result["pickup_picked_up"] is True
    assert result["door_opened"] is True
    assert result["no_candidate_ok"] is False
