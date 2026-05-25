def test_scene_navigation(godot, expect):
    current = godot.current_scene()
    assert current["scene_file_path"] == "res://scenes/main.tscn"

    godot.change_scene("res://scenes/secondary.tscn")
    expect(godot.locator("#SecondaryTitle")).to_have_text("Secondary Scene")

    back = godot.locator("#BackButton")
    back.wait_for_signal("pressed", action=back.click)
    godot.wait_for_scene("res://scenes/main.tscn")
    expect(godot.locator("#Title")).to_have_text("Godot Playwright")
