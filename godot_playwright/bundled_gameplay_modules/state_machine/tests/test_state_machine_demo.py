from __future__ import annotations


def test_state_machine_demo_round_trip(godot):
    godot.change_scene("res://scenes/state_machine_demo/state_machine_demo.tscn")
    result = godot.locator("#StateMachineDemo").call("run_state_machine_demo")
    assert result["ok"], result
    assert result["initial_state"] == "idle"
    assert result["restored_state"] == "attack"
    assert result["forbidden_result"]["ok"] is False
    assert result["transition_history"] == ["idle>move", "move>attack", "attack>idle", "idle>attack"]
