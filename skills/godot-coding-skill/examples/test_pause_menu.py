def test_pause_menu_resume(godot, expect):
    godot.press("Escape")

    menu = godot.get_by_test_id("pause-menu")
    expect(menu).to_be_visible()

    resume = menu.get_by_test_id("pause-resume")
    expect(resume).to_be_actionable()
    resume.click()

    expect(menu).to_be_hidden()
