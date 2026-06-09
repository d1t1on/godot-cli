from __future__ import annotations


def test_inventory_demo_round_trip(godot):
    godot.change_scene("res://scenes/inventory_demo/inventory_demo.tscn")
    result = godot.locator("#InventoryDemo").call("run_inventory_demo")
    assert result["ok"], result
    assert result["potion_quantity"] == 2
    assert result["key_quantity"] == 1
    assert result["failed_key_add_ok"] is False
    assert result["state_round_trip_quantity"] == 2
