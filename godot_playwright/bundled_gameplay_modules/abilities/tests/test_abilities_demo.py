from __future__ import annotations


def test_abilities_demo_runtime(godot):
    godot.change_scene("res://scenes/abilities_demo/abilities_demo.tscn")
    result = godot.locator("#AbilitiesDemo").call("run_abilities_demo")
    assert result["ok"], result
