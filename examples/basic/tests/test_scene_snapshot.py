def test_scene_snapshot(expect_scene):
    expect_scene.to_have_node(name="CounterButton", class_name="Button", properties={"text": "Clicked 0"})
    expect_scene.to_have_node_count(1, name="Title", class_name="Label")
    expect_scene.to_contain_text("Godot Playwright")
    expect_scene.to_match_snapshot("main.scene.json", max_depth=2)
