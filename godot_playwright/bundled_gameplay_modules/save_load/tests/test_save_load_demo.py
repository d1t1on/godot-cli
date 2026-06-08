from __future__ import annotations


def test_save_load_demo_round_trip(godot):
    result = godot.locator("#SaveLoadDemo").call("run_round_trip")
    assert result["ok"], result
    assert result["restored_coins"] == 2
    assert result["restored_position"] == [4.0, 8.0]
    assert result["slot_count_after_save"] == 1
    assert result["has_slot_after_delete"] is False
