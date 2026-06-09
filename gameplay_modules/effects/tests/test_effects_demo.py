from __future__ import annotations


def test_effects_demo_seed_scene_loads(godot):
    godot.change_scene("res://scenes/effects_demo/effects_demo.tscn")
    result = godot.locator("#EffectsDemo").call("run_effects_demo")
    assert result["ok"] is False
    assert "effects demo seed failure" in result["errors"]
