from __future__ import annotations


def test_quests_demo_runs(godot):
    godot.change_scene("res://scenes/quests_demo/quests_demo.tscn")
    result = godot.locator("#QuestsDemo").call("run_quests_demo")
    assert result["ok"], result
    assert result["quest_status"] == "completed"
    assert result["collect_progress"] == 3
    assert result["scan_progress"] == 1
    assert result["repair_progress"] == 1
    assert result["rewards"]["coins"] == 50
    assert result["rewards"]["reputation"] == 5
