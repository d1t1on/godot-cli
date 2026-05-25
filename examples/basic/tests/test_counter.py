def test_counter_button(godot, expect, expect_project):
    main = godot.locator("#Main")
    viewport = godot.viewport_info()
    assert viewport["window_size"]["width"] > 0
    assert viewport["visible_rect"]["height"] > 0
    clock = godot.clock()
    after_frames = godot.wait_for_process_frames(2)
    assert after_frames["process_frames"] >= clock["process_frames"] + 2
    after_idle = godot.wait_for_idle(frames=1)
    assert after_idle["process_frames"] >= after_frames["process_frames"] + 1
    assert godot.evaluate('root.get("name")') == "Main"
    assert godot.wait_for_function('root.has_node("CounterButton")') is True
    title = main.get_by_text("Godot Playwright")
    expect(title).to_be_visible()
    expect(title).to_have_text("Godot Playwright")
    player = godot.locator("#AutomationAnimation")
    expect(player).to_have_animation(
        "fade_in",
        length=1.0,
        track_count=1,
        track={"path": "AnimatedLabel:modulate:a"},
    )
    player.play_animation("fade_in", speed=0.0)
    expect(player).to_be_playing_animation("fade_in", position=0.0)
    player.seek_animation(0.5)
    expect(player).to_be_playing_animation("fade_in", position=0.5)
    player.advance_animation(0.25)
    expect(player).to_be_playing_animation("fade_in", position=0.75)

    expect(main.get_by_test_id("counter-button")).to_have_count(1)
    expect(main.get_by_role("button", name="Clicked 0")).to_have_count(1)
    expect(main.get_by_test_id("missing")).not_to_exist(timeout=0.2)
    expect(main.get_by_test_id("missing")).to_be_hidden(timeout=0.2)
    terms = main.get_by_test_id("accept-terms")
    expect(terms).not_to_be_checked()
    terms.check()
    expect(terms).to_be_checked()
    terms.uncheck()
    expect(terms).not_to_be_checked()
    theme = main.get_by_test_id("theme-select")
    expect(theme).to_have_value("Arcade")
    theme.select_option("Story")
    expect(theme).to_have_value("Story")
    theme.select_option({"id": 30})
    expect(theme).to_have_value("Simulation")
    volume = main.get_by_test_id("volume-slider")
    expect(volume).to_have_value(25.0)
    volume.set_value(75)
    expect(volume).to_have_value(75.0)
    tabs = main.get_by_test_id("mode-tabs")
    expect(tabs).to_have_value("General")
    tabs.select_tab("Advanced")
    expect(tabs).to_have_value("Advanced")
    tabs.select_tab({"metadata": {"mode": "telemetry"}})
    expect(tabs).to_have_value("Telemetry")
    action_menu = main.get_by_test_id("action-menu")
    assert [item["text"] for item in action_menu.menu_items()] == ["Open", "Save", "Snap"]
    action_menu.select_menu_item({"metadata": {"action": "save"}})
    assert action_menu.call("get_meta", "last_action") == "Save"
    action_menu.select_menu_item("Snap", checked=True)
    assert action_menu.call("get_meta", "snap_enabled") is True
    touch_target = main.get_by_test_id("touch-target")
    touch_target.tap(index=1)
    assert touch_target.call("get_meta", "touch_pressed", False) is True
    assert touch_target.call("get_meta", "touch_released", False) is True
    assert touch_target.call("get_meta", "touch_index", -1) == 1
    touch_target.touch_drag_to(touch_target, index=2, steps=2)
    assert touch_target.call("get_meta", "touch_dragged", False) is True
    godot.joypad_press("a")
    assert godot.wait_for_function('root.get_meta("joypad_a_count", 0) >= 1') is True
    godot.joypad_axis("left_x", 0.5)
    assert godot.wait_for_function('abs(root.get_meta("joypad_left_x", 0.0) - 0.5) < 0.001') is True
    godot.joypad_axis("left_x", 0.0)
    confirm_dialog = main.get_by_test_id("confirm-dialog")
    main.get_by_test_id("show-confirm").click()
    confirm_dialog.wait_for(state="visible")
    assert confirm_dialog.dialog()["text"] == "Run the agent action?"
    confirm_dialog.accept_dialog()
    confirm_dialog.wait_for(state="hidden")
    assert confirm_dialog.call("get_meta", "result") == "accepted"
    main.get_by_test_id("show-confirm").click()
    confirm_dialog.wait_for(state="visible")
    confirm_dialog.dismiss_dialog()
    confirm_dialog.wait_for(state="hidden")
    assert confirm_dialog.call("get_meta", "result") == "dismissed"
    godot.press("Ctrl+S")
    assert godot.wait_for_function('root.get_meta("save_shortcut_count", 0) >= 1') is True
    godot.press("F4", shift=True)
    assert godot.wait_for_function('root.get_meta("shift_f4_seen", false)') is True
    jump_action = godot.bind_action_key("agent_jump", "J", replace=True, deadzone=0.2)
    assert jump_action["events"][0]["type"] == "key"
    assert godot.input_actions(include_ui=False, prefix="agent_")["count"] == 1
    expect_project.to_have_input_action_event("agent_jump", event_type="key", key="J")
    godot.press("J")
    assert godot.wait_for_function('root.get_meta("agent_jump_count", 0) >= 1') is True
    confirm_action = godot.bind_action_joypad_button("agent_confirm", "a", replace=True)
    assert confirm_action["events"][0]["type"] == "joypad_button"
    expect_project.to_have_input_action_event("agent_confirm", event_type="joypad_button", button="a")
    godot.joypad_press("a")
    assert godot.wait_for_function('root.get_meta("agent_confirm_count", 0) >= 1') is True
    assert godot.input_action_erase("agent_confirm")["erased"] is True
    assert godot.input_action_erase("agent_jump")["erased"] is True
    inventory = main.get_by_test_id("inventory-list")
    expect(inventory).to_have_value("Potion")
    inventory.select_item("Elixir")
    expect(inventory).to_have_value("Elixir")
    inventory.select_item({"metadata": {"kind": "key"}})
    expect(inventory).to_have_value("Key")
    quests = main.get_by_test_id("quest-tree")
    expect(quests).to_have_value("Forest")
    quests.select_tree_item({"path": ["Cave", "Boss"]})
    expect(quests).to_have_value("Boss")
    quests.select_tree_item({"metadata": {"quest": "forest"}})
    expect(quests).to_have_value("Forest")
    button = main.get_by_test_id("counter-button")
    button.wait_for(state="visible")
    expect(button).to_have_text("Clicked 0")
    assert button.evaluate('node.get("text")') == "Clicked 0"
    assert main.locator("role=button").evaluate_all("count") >= 2
    expect(button).not_to_have_text("Clicked 2")
    expect(button).to_be_enabled()
    expect(button).not_to_be_disabled()
    expect(button).to_be_actionable()
    expect(main.locator("role=button").and_(main.get_by_test_id("counter-button"))).to_have_count(1)
    expect(main.locator("role=button").filter(has_text="Clicked", has_not_text="Next")).to_have_count(1)
    expect(main.locator("role=button").nth(0)).to_have_text("Clicked 0")
    button.wait_for_signal("pressed", action=button.click)
    expect(button).to_have_text("Clicked 1")
