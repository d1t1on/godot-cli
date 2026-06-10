from __future__ import annotations


def test_stats_demo_runs(godot):
    godot.change_scene("res://scenes/stats_demo/stats_demo.tscn")
    result = godot.locator("#StatsDemo").call("run_stats_demo")
    assert result["ok"], result
    assert result["health_after_restore"] == 40.0
    assert result["move_speed_after_restore"] == 12.0
    assert result["missing_stat_ok"] is False
