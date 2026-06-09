from __future__ import annotations


def test_effects_demo_round_trip(godot):
    godot.change_scene("res://scenes/effects_demo/effects_demo.tscn")
    result = godot.locator("#EffectsDemo").call("run_effects_demo")
    assert result["ok"], result
    assert result["poison_stack_count"] == 3
    assert result["poison_tick_count"] >= 2
    assert result["has_haste_after_expire"] is False
    assert result["has_shielded_after_update"] is True
    assert result["unknown_result"]["ok"] is False
    assert result["bad_stacks_result"]["ok"] is False
