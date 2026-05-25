def test_line_edit_fill(godot, expect):
    main = godot.locator("#Main")
    name_input = main.get_by_test_id("name-input")
    echo = main.get_by_test_id("echo")

    expect(name_input).to_be_editable()
    expect(name_input).to_have_text("")
    expect(name_input).to_have_value("")
    name_input.focus()
    expect(name_input).to_be_focused()
    name_input.wait_for_signal("text_changed", action=lambda: name_input.fill("Ada"))
    expect(name_input).to_have_text("Ada")
    expect(name_input).to_have_value("Ada")
    expect(echo).to_have_text("Hello Ada")
    submitted = name_input.wait_for_signal("text_submitted", action=lambda: name_input.press("Enter"))
    assert submitted["args"] == ["Ada"]
