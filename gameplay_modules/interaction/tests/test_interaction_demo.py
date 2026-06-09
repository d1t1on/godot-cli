from __future__ import annotations


def test_interaction_demo_runs(godot):
    godot.change_scene("res://scenes/interaction_demo/interaction_demo.tscn")
    result = godot.locator("#InteractionDemo").call("run_interaction_demo")
    assert result["ok"], result
