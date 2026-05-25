def test_editor_expectation_fixtures(
    godot,
    expect,
    expect_editor,
    expect_filesystem,
    expect_scene_file,
    expect_script,
    expect_script_file,
    mode,
):
    if mode != "editor":
        return

    scene_path = "res://scenes/main.tscn"
    script_path = "res://scripts/main.gd"

    expect(godot.editor_get_by_role("panel")).to_exist()
    godot.editor_open_scene(scene_path)
    expect_editor.to_be_available()
    expect_editor.to_match_history({"available": True})
    expect_editor.to_have_open_scene(scene_path)
    expect_editor.to_have_edited_scene(scene_path)
    expect_editor.not_to_be_playing()
    godot.editor_select("#CounterButton")
    expect_editor.to_have_selection_count(1)
    expect_editor.to_have_selection("CounterButton")
    expect_filesystem("res://scripts").to_contain("main.gd", extension="gd")
    expect_filesystem(script_path).to_exist()
    expect_scene_file(scene_path).to_have_node(name="CounterButton", class_name="Button")
    expect_script(script_path).to_extend("Control")
    expect_script(script_path).to_define_function("_ready")
    expect_script_file(script_path).to_extend("Control")
    expect_script_file(script_path).to_define_function("_ready")
