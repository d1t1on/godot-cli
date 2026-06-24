from __future__ import annotations


def test_dialogue_demo_runs(godot):
    godot.change_scene("res://scenes/dialogue_demo/dialogue_demo.tscn")
    result = godot.locator("#DialogueDemo").call("run_dialogue_demo")
    assert result["ok"], result
    assert result["final_line_id"] == "guard_supplies"
    assert result["variables"]["asked_supplies"] is True
    assert result["variables"]["supplies_received"] is True
    assert result["choices_seen"]["greet"] == 2
    assert result["choices_seen"]["ask"] == 2
