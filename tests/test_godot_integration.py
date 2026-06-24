from __future__ import annotations

import base64
import shutil
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from godot_playwright import (
    Godot,
    RpcError,
    expect,
    expect_editor,
    expect_filesystem,
    expect_inspector,
    expect_log,
    expect_node_class,
    expect_physics2d,
    expect_physics3d,
    expect_project,
    expect_project_scene,
    expect_resource,
    expect_resource_class,
    expect_scene_file,
    expect_script,
    expect_script_class,
    expect_script_file,
    expect_trace,
)
from godot_playwright.project import init_project


GENERATED_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class GodotIntegrationTests(unittest.TestCase):
    def test_runtime_locator_click_and_expect(self) -> None:
        with temporary_project() as project:
            with Godot(project, mode="runtime", timeout=20, stdout=None) as godot:
                main = godot.locator("#Main")
                viewport = godot.viewport_info()
                original_width = int(viewport["window_size"]["width"])
                original_height = int(viewport["window_size"]["height"])
                self.assertGreater(original_width, 0)
                self.assertGreater(original_height, 0)
                resized = godot.set_viewport_size(900, 700)
                self.assertEqual(int(resized["window_size"]["width"]), 900)
                self.assertEqual(int(resized["window_size"]["height"]), 700)
                self.assertEqual(int(resized["visible_rect"]["width"]), 900)
                self.assertEqual(int(resized["visible_rect"]["height"]), 700)
                godot.wait_for_process_frames(1, timeout=2)
                resized_rect = main.bounds()["rect"]
                self.assertGreaterEqual(int(resized_rect["width"]), 900)
                self.assertGreaterEqual(int(resized_rect["height"]), 700)
                restored = godot.set_viewport_size(original_width, original_height)
                self.assertEqual(int(restored["window_size"]["width"]), original_width)
                self.assertEqual(int(restored["window_size"]["height"]), original_height)
                godot.wait_for_process_frames(1, timeout=2)
                title = main.get_by_text("Godot Playwright")
                self.assertEqual(title.get("text"), "Godot Playwright")
                clock_start = godot.clock()
                process_after = godot.wait_for_process_frames(2, timeout=2)
                self.assertGreaterEqual(process_after["process_frames"], clock_start["process_frames"] + 2)
                process_ticks = int(main.call("get_meta", "process_ticks", 0))
                self.assertGreaterEqual(process_ticks, 1)
                paused = godot.pause()
                self.assertTrue(paused["paused"])
                paused_ticks = int(main.call("get_meta", "process_ticks", 0))
                godot.wait_for_timeout(50)
                self.assertEqual(int(main.call("get_meta", "process_ticks", 0)), paused_ticks)
                stepped = godot.step_frames(1, timeout=2)
                self.assertTrue(stepped["paused"])
                self.assertGreaterEqual(int(main.call("get_meta", "process_ticks", 0)), paused_ticks + 1)
                samples = godot.sample_frames(
                    2,
                    selectors="#CounterButton",
                    expressions={"ticks": 'root.get_meta("process_ticks", 0)'},
                    timeout=2,
                )
                self.assertEqual(samples["count"], 2)
                self.assertEqual(samples["samples"][0]["selector_count"], 1)
                self.assertEqual(samples["samples"][0]["expression_count"], 1)
                godot.resume()
                physics_start = process_after["physics_frames"]
                physics_after = godot.wait_for_physics_frames(1, timeout=2)
                self.assertGreaterEqual(physics_after["physics_frames"], physics_start + 1)
                physics_ticks = int(main.call("get_meta", "physics_ticks", 0))
                self.assertGreaterEqual(physics_ticks, 1)
                point_query = godot.physics2d_point(640, 420, collision_mask=4)
                self.assertGreaterEqual(point_query["count"], 1)
                self.assertEqual(point_query["collisions"][0]["name"], "PhysicsTarget")
                physics_expect = expect_physics2d(godot)
                point_collision = physics_expect.to_have_point_collision(
                    640,
                    420,
                    name="PhysicsTarget",
                    class_name="StaticBody2D",
                    groups=["physics_fixture"],
                    metadata={"test_id": "physics-target"},
                    collision_mask=4,
                    timeout=2,
                )
                self.assertEqual(point_collision["path"], "/root/Main/PhysicsTarget")
                ray_collision = physics_expect.to_have_ray_collision(
                    560,
                    420,
                    720,
                    420,
                    name="PhysicsTarget",
                    collision_mask=4,
                    timeout=2,
                )
                self.assertEqual(ray_collision["name"], "PhysicsTarget")
                physics_expect.not_to_have_point_collision(20, 20, name="PhysicsTarget", collision_mask=4, timeout=2)
                physics_expect.not_to_have_ray_collision(
                    560,
                    360,
                    720,
                    360,
                    name="PhysicsTarget",
                    collision_mask=4,
                    timeout=2,
                )
                point3d_query = godot.physics3d_point(0, 0, 0, collision_mask=8)
                self.assertGreaterEqual(point3d_query["count"], 1)
                self.assertEqual(point3d_query["collisions"][0]["name"], "PhysicsTarget3D")
                physics3d_expect = expect_physics3d(godot)
                point3d_collision = physics3d_expect.to_have_point_collision(
                    0,
                    0,
                    0,
                    name="PhysicsTarget3D",
                    class_name="StaticBody3D",
                    groups=["physics_fixture_3d"],
                    metadata={"test_id": "physics-target-3d"},
                    collision_mask=8,
                    timeout=2,
                )
                self.assertEqual(point3d_collision["path"], "/root/Main/PhysicsTarget3D")
                ray3d_collision = physics3d_expect.to_have_ray_collision(
                    -4,
                    0,
                    0,
                    4,
                    0,
                    0,
                    name="PhysicsTarget3D",
                    collision_mask=8,
                    timeout=2,
                )
                self.assertEqual(ray3d_collision["name"], "PhysicsTarget3D")
                physics3d_expect.not_to_have_point_collision(
                    20,
                    20,
                    20,
                    name="PhysicsTarget3D",
                    collision_mask=8,
                    timeout=2,
                )
                physics3d_expect.not_to_have_ray_collision(
                    -4,
                    4,
                    0,
                    4,
                    4,
                    0,
                    name="PhysicsTarget3D",
                    collision_mask=8,
                    timeout=2,
                )
                camera_viewport = godot.viewport_info()["visible_rect"]
                camera_screen_x = float(camera_viewport["x"]) + float(camera_viewport["width"]) / 2.0
                camera_screen_y = float(camera_viewport["y"]) + float(camera_viewport["height"]) / 2.0
                camera_ray = godot.camera3d_ray(
                    camera_screen_x,
                    camera_screen_y,
                    camera="#AutomationCamera3D",
                    max_distance=50,
                )
                self.assertEqual(camera_ray["camera"]["name"], "AutomationCamera3D")
                self.assertAlmostEqual(float(camera_ray["direction"]["z"]), -1.0, delta=0.01)
                camera_pick = godot.camera3d_pick(
                    camera_screen_x,
                    camera_screen_y,
                    camera="#AutomationCamera3D",
                    collision_mask=8,
                    max_distance=50,
                )
                self.assertTrue(camera_pick["hit"])
                self.assertEqual(camera_pick["collision"]["name"], "PhysicsTarget3D")
                camera_locator = godot.locator("#AutomationCamera3D")
                locator_camera_ray = camera_locator.camera3d_ray(camera_screen_x, camera_screen_y, max_distance=50)
                self.assertEqual(locator_camera_ray["camera"]["name"], "AutomationCamera3D")
                locator_pick = camera_locator.pick_3d(camera_screen_x, camera_screen_y, collision_mask=8, max_distance=50)
                self.assertTrue(locator_pick["hit"])
                self.assertEqual(locator_pick["collision"]["name"], "PhysicsTarget3D")
                hovered_3d = camera_locator.hover_3d(
                    camera_screen_x,
                    camera_screen_y,
                    name="PhysicsTarget3D",
                    collision_mask=8,
                    max_distance=50,
                    timeout=2,
                )
                self.assertEqual(hovered_3d["collision"]["name"], "PhysicsTarget3D")
                self.assertTrue(wait_for_call(main, "get_meta", "physics_target_3d_hovered", False))
                clicked_3d = camera_locator.click_3d(
                    camera_screen_x,
                    camera_screen_y,
                    name="PhysicsTarget3D",
                    collision_mask=8,
                    max_distance=50,
                    timeout=2,
                )
                self.assertEqual(clicked_3d["collision"]["name"], "PhysicsTarget3D")
                click_count_3d = wait_for_call(
                    main,
                    "get_meta",
                    "physics_target_3d_click_count",
                    0,
                    predicate=lambda value: int(value) >= 1,
                )
                self.assertGreaterEqual(int(click_count_3d), 1)
                dragged_3d = camera_locator.drag_3d(
                    camera_screen_x,
                    camera_screen_y,
                    camera_screen_x + 8,
                    camera_screen_y,
                    name="PhysicsTarget3D",
                    collision_mask=8,
                    max_distance=50,
                    steps=2,
                    timeout=2,
                )
                self.assertEqual(dragged_3d["collision"]["name"], "PhysicsTarget3D")
                self.assertTrue(wait_for_call(main, "get_meta", "physics_target_3d_drag_pressed", False))
                self.assertTrue(wait_for_call(main, "get_meta", "physics_target_3d_dragged", False))
                self.assertTrue(wait_for_call(main, "get_meta", "physics_target_3d_drag_released", False))
                picked_collision = physics3d_expect.to_pick_camera_collision(
                    camera_screen_x,
                    camera_screen_y,
                    camera="#AutomationCamera3D",
                    name="PhysicsTarget3D",
                    class_name="StaticBody3D",
                    groups=["physics_fixture_3d"],
                    metadata={"test_id": "physics-target-3d"},
                    collision_mask=8,
                    max_distance=50,
                    timeout=2,
                )
                self.assertEqual(picked_collision["path"], "/root/Main/PhysicsTarget3D")
                locator_picked_collision = expect(camera_locator).to_pick_camera_collision(
                    camera_screen_x,
                    camera_screen_y,
                    name="PhysicsTarget3D",
                    class_name="StaticBody3D",
                    groups=["physics_fixture_3d"],
                    metadata={"test_id": "physics-target-3d"},
                    collision_mask=8,
                    max_distance=50,
                    timeout=2,
                )
                self.assertEqual(locator_picked_collision["path"], "/root/Main/PhysicsTarget3D")
                physics3d_expect.not_to_pick_camera_collision(
                    camera_screen_x,
                    camera_screen_y,
                    camera="#AutomationCamera3D",
                    name="PhysicsTarget3D",
                    collision_mask=16,
                    max_distance=50,
                    timeout=2,
                )
                expect(camera_locator).not_to_pick_camera_collision(
                    camera_screen_x,
                    camera_screen_y,
                    name="PhysicsTarget3D",
                    collision_mask=16,
                    max_distance=50,
                    timeout=2,
                )
                idle_after = godot.wait_for_idle(frames=1, timeout=2)
                self.assertGreaterEqual(idle_after["process_frames"], physics_after["process_frames"] + 1)
                self.assertEqual(godot.evaluate('root.get("name")'), "Main")
                self.assertEqual(godot.evaluate('tree.get_current_scene().get("name")'), "Main")
                waited_ticks = godot.wait_for_function(
                    'root.get_meta("process_ticks", 0) >= min_ticks',
                    min_ticks=process_ticks + 1,
                    timeout=2,
                )
                self.assertTrue(waited_ticks)
                animation_player = godot.locator("#AutomationAnimation")
                animated_label = godot.locator("#AnimatedLabel")
                animation_description = animation_player.animation_describe(include_tracks=True)
                self.assertEqual(animation_description["node"]["class"], "AnimationPlayer")
                self.assertEqual(animation_description["animations"][0]["name"], "fade_in")
                self.assertEqual(animation_description["animations"][0]["track_count"], 1)
                self.assertEqual(animation_description["animations"][0]["tracks"][0]["path"], "AnimatedLabel:modulate:a")
                matched_animation = expect(animation_player).to_have_animation(
                    "fade_in",
                    length=1.0,
                    track_count=1,
                    track={"path": "AnimatedLabel:modulate:a", "key_count": 2},
                    timeout=2,
                )
                self.assertEqual(matched_animation["name"], "fade_in")
                played_animation = animation_player.play_animation("fade_in", speed=0.0)
                self.assertTrue(played_animation["is_playing"])
                self.assertEqual(played_animation["current_animation"], "fade_in")
                expect(animation_player).to_be_playing_animation("fade_in", position=0.0, speed_scale=1.0, timeout=2)
                seeked_animation = animation_player.seek_animation(0.5, update=True)
                self.assertAlmostEqual(float(seeked_animation["position"]), 0.5, delta=0.01)
                expect(animation_player).to_be_playing_animation("fade_in", position=0.5, timeout=2)
                self.assertAlmostEqual(float(animated_label.get("modulate")["a"]), 0.5, delta=0.05)
                advanced_animation = animation_player.advance_animation(0.25)
                self.assertAlmostEqual(float(advanced_animation["position"]), 0.75, delta=0.01)
                self.assertAlmostEqual(float(animated_label.get("modulate")["a"]), 0.75, delta=0.05)
                paused_animation = animation_player.pause_animation()
                self.assertFalse(paused_animation["is_playing"])
                expect(animation_player).not_to_be_playing_animation("fade_in", timeout=2)
                stopped_animation = animation_player.stop_animation()
                self.assertFalse(stopped_animation["is_playing"])
                self.assertAlmostEqual(float(stopped_animation["position"]), 0.0, delta=0.01)
                expect(godot.get_by_role("text", name="Godot Playwright")).to_have_text("Godot Playwright", timeout=2)
                self.assertEqual(godot.locator("text*=Playwright").count(), 1)
                self.assertEqual(godot.locator({"type": "Label", "text": "Godot Playwright"}).count(), 1)
                self.assertEqual(main.get_by_text("Playwright", exact=False).count(), 1)
                main_snapshot = main.snapshot(max_depth=2, include_properties=True)
                self.assertEqual(main_snapshot["name"], "Main")
                expect(main).to_contain_node(name="CounterButton", class_name="Button", max_depth=2, timeout=2)
                expect(main).to_contain_node(properties={"text": "Godot Playwright"}, max_depth=2, timeout=2)
                expect(main).to_contain_text("Godot Playwright", max_depth=2, timeout=2)
                expect(main).not_to_contain_text("Missing Label", max_depth=2, timeout=2)
                expect(main.get_by_test_id("title")).to_have_text("Godot Playwright", timeout=2)
                title.wait_for(state="visible", timeout=2)
                title.set("visible", False)
                expect(title).not_to_be_visible(timeout=2)
                title.wait_for(state="hidden", timeout=2)
                title.set("visible", True)
                expect(title).to_be_visible(timeout=2)
                missing = main.get_by_test_id("missing")
                missing.wait_for(state="detached", timeout=0.2)
                expect(missing).not_to_exist(timeout=0.2)
                expect(missing).to_be_hidden(timeout=0.2)

                self.assertEqual(main.get_by_test_id("counter-button").count(), 1)
                self.assertEqual(godot.locator("test_id=counter-button").count(), 1)
                self.assertEqual(godot.locator({"metadata": {"test_id": "counter-button"}}).count(), 1)
                self.assertEqual(main.get_by_role("button", name="Clicked 0").count(), 1)
                buttons = main.locator("role=button")
                self.assertGreaterEqual(buttons.count(), 2)
                expect(buttons.nth(0, timeout=2)).to_have_text("Clicked 0", timeout=2)
                button_by_role_and_id = buttons.and_(main.get_by_test_id("counter-button"))
                self.assertEqual(button_by_role_and_id.count(), 1)
                button_or_input = main.get_by_test_id("counter-button").or_(main.get_by_test_id("name-input"))
                self.assertEqual(button_or_input.count(), 2)
                clicked_buttons = buttons.filter(has_text="Clicked", has_not_text="Next")
                self.assertEqual(clicked_buttons.count(), 1)
                expect(clicked_buttons.nth(0, timeout=2)).to_have_text("Clicked 0", timeout=2)
                self.assertEqual(buttons.evaluate_all("count"), buttons.count())
                self.assertEqual(buttons.evaluate_all("count + offset", offset=3), buttons.count() + 3)
                self.assertEqual(buttons.evaluate_all('nodes[0].get("text")'), "Clicked 0")
                controls_with_counter = main.locator({"type": "Control"}).filter(has=main.get_by_test_id("counter-button"))
                self.assertEqual(controls_with_counter.count(), 1)
                controls_without_counter = main.locator({"type": "Control"}).filter(
                    has_not=main.get_by_test_id("counter-button")
                )
                self.assertEqual(controls_without_counter.count(), main.locator({"type": "Control"}).count() - 1)
                accept_terms = main.get_by_test_id("accept-terms")
                expect(accept_terms).not_to_be_checked(timeout=2)
                toggled_on = accept_terms.wait_for_signal("toggled", timeout=2, action=accept_terms.check)
                self.assertEqual(toggled_on["args"], [True])
                expect(accept_terms).to_be_checked(timeout=2)
                self.assertTrue(wait_for_call(accept_terms, "get_meta", "last_toggled", False))
                toggled_off = accept_terms.wait_for_signal("toggled", timeout=2, action=accept_terms.uncheck)
                self.assertEqual(toggled_off["args"], [False])
                expect(accept_terms).not_to_be_checked(timeout=2)
                theme_select = main.get_by_test_id("theme-select")
                expect(theme_select).to_have_value("Arcade", timeout=2)
                theme_event = theme_select.wait_for_signal(
                    "item_selected",
                    timeout=2,
                    action=lambda: theme_select.select_option("Story", timeout=2),
                )
                self.assertEqual(theme_event["args"], [1])
                expect(theme_select).to_have_value("Story", timeout=2)
                self.assertEqual(theme_select.call("get_meta", "selected_theme"), "Story")
                selected = theme_select.select_option({"id": 30}, timeout=2)
                self.assertEqual(selected["selected"]["text"], "Simulation")
                expect(theme_select).to_have_value("Simulation", timeout=2)
                theme_select.select_option({"index": 0}, timeout=2)
                expect(theme_select).to_have_value("Arcade", timeout=2)
                volume_slider = main.get_by_test_id("volume-slider")
                expect(volume_slider).to_have_value(25.0, timeout=2)
                volume_event = volume_slider.wait_for_signal("value_changed", timeout=2, action=lambda: volume_slider.set_value(75, timeout=2))
                self.assertEqual(float(volume_event["args"][0]), 75.0)
                expect(volume_slider).to_have_value(75.0, timeout=2)
                self.assertEqual(float(volume_slider.call("get_meta", "volume")), 75.0)
                mode_tabs = main.get_by_test_id("mode-tabs")
                expect(mode_tabs).to_have_value("General", timeout=2)
                tab_event = mode_tabs.wait_for_signal(
                    "tab_changed",
                    timeout=2,
                    action=lambda: mode_tabs.select_tab("Advanced", timeout=2),
                )
                self.assertEqual(tab_event["args"], [1])
                expect(mode_tabs).to_have_value("Advanced", timeout=2)
                self.assertEqual(mode_tabs.call("get_meta", "selected_mode"), "Advanced")
                selected_tab = mode_tabs.select_tab({"metadata": {"mode": "telemetry"}}, timeout=2)
                self.assertEqual(selected_tab["selected"]["text"], "Telemetry")
                expect(mode_tabs).to_have_value("Telemetry", timeout=2)
                mode_tabs.select_tab({"index": 0}, timeout=2)
                expect(mode_tabs).to_have_value("General", timeout=2)
                settings_tabs = main.get_by_test_id("settings-tabs")
                expect(settings_tabs).to_have_value("Overview", timeout=2)
                settings_event = settings_tabs.wait_for_signal(
                    "tab_changed",
                    timeout=2,
                    action=lambda: settings_tabs.select_tab("Details", timeout=2),
                )
                self.assertEqual(settings_event["args"], [1])
                expect(settings_tabs).to_have_value("Details", timeout=2)
                self.assertEqual(settings_tabs.call("get_meta", "selected_panel"), "Details")
                settings_tabs.select_tab({"metadata": {"panel": "overview"}}, timeout=2)
                expect(settings_tabs).to_have_value("Overview", timeout=2)
                action_menu = main.get_by_test_id("action-menu")
                menu_items = action_menu.menu_items(timeout=2)
                self.assertEqual([item["text"] for item in menu_items], ["Open", "Save", "Snap"])
                self.assertEqual(menu_items[1]["metadata"], {"action": "save"})
                selected_menu_item = action_menu.select_menu_item({"metadata": {"action": "save"}}, timeout=2)
                self.assertEqual(selected_menu_item["selected"]["text"], "Save")
                self.assertEqual(wait_for_call(action_menu, "get_meta", "last_action", ""), "Save")
                self.assertEqual(action_menu.call("get_meta", "last_action_id"), 20)
                checked_menu_item = action_menu.select_menu_item("Snap", checked=True, timeout=2)
                self.assertEqual(checked_menu_item["selected"]["checked"], True)
                self.assertEqual(wait_for_call(action_menu, "get_meta", "snap_enabled", False), True)
                inventory_list = main.get_by_test_id("inventory-list")
                expect(inventory_list).to_have_value("Potion", timeout=2)
                item_event = inventory_list.wait_for_signal(
                    "item_selected",
                    timeout=2,
                    action=lambda: inventory_list.select_item("Elixir", timeout=2),
                )
                self.assertEqual(item_event["args"], [1])
                expect(inventory_list).to_have_value("Elixir", timeout=2)
                self.assertEqual(inventory_list.call("get_meta", "selected_item"), "Elixir")
                selected_item = inventory_list.select_item({"metadata": {"kind": "key"}}, timeout=2)
                self.assertEqual(selected_item["selected"]["value"], "Key")
                expect(inventory_list).to_have_value("Key", timeout=2)
                inventory_list.select_item({"index": 0}, timeout=2)
                expect(inventory_list).to_have_value("Potion", timeout=2)
                loadout_list = main.get_by_test_id("loadout-list")
                expect(loadout_list).to_have_value("Sword", timeout=2)
                loadout_event = loadout_list.wait_for_signal(
                    "multi_selected",
                    timeout=2,
                    action=lambda: loadout_list.select_item(["Sword", "Bow"], timeout=2),
                )
                self.assertEqual(loadout_event["args"], [1, True])
                expect(loadout_list).to_have_value(["Sword", "Bow"], timeout=2)
                self.assertEqual(loadout_list.call("get_meta", "selected_loadout"), ["Sword", "Bow"])
                loadout_list.select_item({"metadata": {"slot": "shield"}}, timeout=2)
                expect(loadout_list).to_have_value("Shield", timeout=2)
                quest_tree = main.get_by_test_id("quest-tree")
                expect(quest_tree).to_have_value("Forest", timeout=2)
                quest_event = quest_tree.wait_for_signal(
                    "item_selected",
                    timeout=2,
                    action=lambda: quest_tree.select_tree_item({"path": ["Cave", "Boss"]}, timeout=2),
                )
                self.assertEqual(quest_event["args"], [])
                expect(quest_tree).to_have_value("Boss", timeout=2)
                self.assertEqual(quest_tree.call("get_meta", "selected_quest"), "Boss")
                selected_tree_item = quest_tree.select_tree_item({"metadata": {"quest": "forest"}}, timeout=2)
                self.assertEqual(selected_tree_item["selected"]["value"], "Forest")
                expect(quest_tree).to_have_value("Forest", timeout=2)
                talent_tree = main.get_by_test_id("talent-tree")
                expect(talent_tree).to_have_value("Dash", timeout=2)
                talent_event = talent_tree.wait_for_signal(
                    "multi_selected",
                    timeout=2,
                    action=lambda: talent_tree.select_tree_item(["Dash", "Glide"], timeout=2),
                )
                self.assertEqual(talent_event["args"][1:], [0, True])
                expect(talent_tree).to_have_value(["Dash", "Glide"], timeout=2)
                self.assertEqual(talent_tree.call("get_meta", "selected_talents"), ["Dash", "Glide"])
                talent_tree.select_tree_item({"metadata": {"talent": "wall_jump"}}, timeout=2)
                expect(talent_tree).to_have_value("Wall Jump", timeout=2)
                self.assertEqual(godot.locator({"type": "Button", "properties": {"text": "Clicked 0", "disabled": False}}).count(), 1)
                button = godot.locator("#CounterButton")
                batch_buttons = button.or_(main.get_by_test_id("next-scene"))
                batch_meta = batch_buttons.call_all_values("get_meta", "test_id", "", limit=2)
                self.assertEqual(set(batch_meta), {"counter-button", "next-scene"})
                self.assertEqual(button.get("text"), "Clicked 0")
                self.assertEqual(button.evaluate('node.get("text")'), "Clicked 0")
                self.assertEqual(button.evaluate("node.get_child_count() + bonus", bonus=2), 2)
                self.assertTrue(button.has_method("get_meta"))
                self.assertTrue(button.has_signal("pressed"))
                expect(button).to_have_method("get_meta", timeout=2)
                expect(button).to_have_signal("pressed", timeout=2)
                expect(button).not_to_have_signal("missing_signal", timeout=2)
                self.assertTrue(button.wait_for_function('node.get("text") == expected', expected="Clicked 0", timeout=2))
                expect(button).to_match_expression('node.get("text")', "Clicked 0", timeout=2)
                expect(button).not_to_match_expression('node.get("text")', "Clicked 2", timeout=2)
                expect(button).to_be_visible(timeout=2)
                expect(button).to_be_enabled(timeout=2)
                expect(button).to_be_actionable(timeout=2)
                expect(button).not_to_be_disabled(timeout=2)
                button.set("disabled", True)
                expect(button).to_be_disabled(timeout=2)
                expect(button).not_to_be_enabled(timeout=2)
                expect(button).not_to_be_actionable(timeout=2)
                self.assertFalse(button.is_actionable())
                button.set("disabled", False)
                expect(button).to_be_enabled(timeout=2)
                self.assertEqual(button.values(["text", "disabled"]), {"text": "Clicked 0", "disabled": False})
                button.set_properties({"tooltip_text": "Batch tooltip", "disabled": False})
                expect(button).to_have_properties(
                    {"tooltip_text": "Batch tooltip", "disabled": False},
                    timeout=2,
                )
                expect(button).not_to_have_properties({"tooltip_text": "Other tooltip"}, timeout=2)
                all_buttons = godot.locator({"type": "Button"})
                all_result = all_buttons.set_all_properties({"tooltip_text": "All runtime buttons"})
                self.assertGreaterEqual(all_result["count"], 1)
                expect(all_buttons).to_have_all_properties(
                    {"tooltip_text": "All runtime buttons"},
                    timeout=2,
                )
                button.set_metadata({"agent_tag": "counter", "generated_by": "godot_playwright"})
                self.assertEqual(button.get_meta("agent_tag"), "counter")
                expect(button).to_have_metadata(
                    {"agent_tag": "counter", "generated_by": "godot_playwright"},
                    timeout=2,
                )
                self.assertEqual(godot.locator({"metadata": {"agent_tag": "counter"}}).count(), 1)
                button.remove_meta("agent_tag")
                expect(button).not_to_have_meta("agent_tag", timeout=2)
                godot.trace_start(max_events=50)
                self.assertEqual(godot.evaluate('root.get("name")'), "Main")
                expect_trace(godot).to_have_event("runtime.evaluate", timeout=2)
                self.assertEqual(button.evaluate('node.get("text")'), "Clicked 0")
                expect_trace(godot).to_have_event("node.evaluate", timeout=2)
                signal_event = button.wait_for_signal("pressed", timeout=2, action=button.click)
                self.assertEqual(signal_event["signal"], "pressed")
                expect(button).to_have_property("text", "Clicked 1", timeout=2)
                expect_trace(godot).to_have_event("node.click", data={"strategy": "pressed_signal"}, timeout=2)
                expect_trace(godot).to_have_rpc("node.click", timeout=2)
                events = godot.trace_events()
                event_types = [event["type"] for event in events]
                self.assertIn("node.click", event_types)
                godot.trace_stop()
                godot.log_clear()
                godot.evaluate('print("agent live log marker")')
                log_event = expect_log(godot).to_have_message("agent live log marker", timeout=2)
                self.assertEqual(log_event["severity"], "info")
                godot.evaluate('push_error("agent live error marker")')
                error_event = expect_log(godot).to_have_error("agent live error marker", timeout=2)
                self.assertIn(error_event["kind"], {"ERROR", "USER ERROR"})
                with self.assertRaisesRegex(RpcError, "headless display driver"):
                    godot.screenshot(project / "headless.png")

                hover_target = godot.locator("#HoverTarget")
                hover_target.hover()
                self.assertTrue(wait_for_call(hover_target, "get_meta", "hovered", False))

                drag_source = godot.locator("#DragSource")
                drop_target = godot.locator("#DropTarget")
                drag_source.drag_to(drop_target, steps=3)
                self.assertTrue(wait_for_call(drag_source, "get_meta", "drag_pressed", False))
                self.assertTrue(wait_for_call(drop_target, "get_meta", "dropped", False))

                wheel_target = godot.locator("#WheelTarget")
                wheel_target.scroll(delta_y=3)
                self.assertEqual(
                    wait_for_call(
                        wheel_target,
                        "get_meta",
                        "wheel_delta_y",
                        0.0,
                        predicate=lambda value: float(value) == 3.0,
                    ),
                    3.0,
                )

                touch_target = godot.locator("#TouchTarget")
                touch_target.tap(index=1)
                self.assertTrue(wait_for_call(touch_target, "get_meta", "touch_pressed", False))
                self.assertTrue(wait_for_call(touch_target, "get_meta", "touch_released", False))
                self.assertEqual(touch_target.call("get_meta", "touch_index", -1), 1)
                touch_target.touch_drag_to(touch_target, index=2, steps=2)
                self.assertTrue(wait_for_call(touch_target, "get_meta", "touch_dragged", False))
                relative = touch_target.call("get_meta", "touch_relative", {"x": 0, "y": 0})
                self.assertIn("$type", relative)

                godot.joypad_press("a")
                joypad_a_count = wait_for_call(
                    main,
                    "get_meta",
                    "joypad_a_count",
                    0,
                    predicate=lambda value: int(value) >= 1,
                )
                self.assertGreaterEqual(int(joypad_a_count), 1)
                godot.joypad_axis("left_x", 0.5)
                joypad_left_x = wait_for_call(
                    main,
                    "get_meta",
                    "joypad_left_x",
                    0.0,
                    predicate=lambda value: abs(float(value) - 0.5) < 0.001,
                )
                self.assertAlmostEqual(float(joypad_left_x), 0.5)
                godot.joypad_axis("left_x", 0.0)

                show_confirm = main.get_by_test_id("show-confirm")
                confirm_dialog = main.get_by_test_id("confirm-dialog")
                show_confirm.click()
                confirm_dialog.wait_for(state="visible", timeout=2)
                dialog_summary = confirm_dialog.dialog()
                self.assertEqual(dialog_summary["title"], "Confirm Action")
                self.assertEqual(dialog_summary["text"], "Run the agent action?")
                self.assertEqual(dialog_summary["ok_button"]["text"], "OK")
                self.assertEqual(dialog_summary["cancel_button"]["text"], "Cancel")
                confirmed = confirm_dialog.wait_for_signal(
                    "confirmed",
                    timeout=2,
                    action=confirm_dialog.accept_dialog,
                )
                self.assertEqual(confirmed["signal"], "confirmed")
                confirm_dialog.wait_for(state="hidden", timeout=2)
                self.assertEqual(confirm_dialog.call("get_meta", "result"), "accepted")

                show_confirm.click()
                confirm_dialog.wait_for(state="visible", timeout=2)
                canceled = confirm_dialog.wait_for_signal(
                    "canceled",
                    timeout=2,
                    action=confirm_dialog.dismiss_dialog,
                )
                self.assertEqual(canceled["signal"], "canceled")
                confirm_dialog.wait_for(state="hidden", timeout=2)
                self.assertEqual(confirm_dialog.call("get_meta", "result"), "dismissed")

                godot.press("Ctrl+S")
                self.assertEqual(
                    wait_for_call(main, "get_meta", "save_shortcut_count", 0, predicate=lambda value: int(value) >= 1),
                    1,
                )
                godot.press("F4", shift=True)
                self.assertTrue(wait_for_call(main, "get_meta", "shift_f4_seen", False))

                jump_action = godot.bind_action_key("agent_jump", "J", replace=True, deadzone=0.2)
                self.assertTrue(jump_action["exists"])
                self.assertAlmostEqual(float(jump_action["deadzone"]), 0.2, places=5)
                self.assertEqual(jump_action["events"][0]["type"], "key")
                self.assertEqual(jump_action["events"][0]["key"], "J")
                actions = godot.input_actions(include_ui=False, prefix="agent_")
                self.assertEqual(actions["count"], 1)
                expect_project(godot).to_have_input_action("agent_jump", min_event_count=1, deadzone=0.2, timeout=2)
                jump_event = expect_project(godot).to_have_input_action_event(
                    "agent_jump",
                    event_type="key",
                    key="J",
                    timeout=2,
                )
                self.assertEqual(jump_event["type"], "key")
                godot.press("J")
                self.assertEqual(
                    wait_for_call(main, "get_meta", "agent_jump_count", 0, predicate=lambda value: int(value) >= 1),
                    1,
                )

                confirm_action = godot.bind_action_joypad_button("agent_confirm", "a", replace=True)
                self.assertEqual(confirm_action["events"][0]["type"], "joypad_button")
                confirm_event = expect_project(godot).to_have_input_action_event(
                    "agent_confirm",
                    event_type="joypad_button",
                    button="a",
                    timeout=2,
                )
                self.assertEqual(confirm_event["type"], "joypad_button")
                godot.joypad_press("a")
                self.assertEqual(
                    wait_for_call(main, "get_meta", "agent_confirm_count", 0, predicate=lambda value: int(value) >= 1),
                    1,
                )
                self.assertTrue(godot.input_action_erase("agent_confirm")["erased"])
                self.assertTrue(godot.input_action_erase("agent_jump")["erased"])
                self.assertFalse(godot.input_action_describe("agent_jump")["exists"])
                expect_project(godot).not_to_have_input_action_event("agent_jump", event_type="key", key="J", timeout=2)
                expect_project(godot).not_to_have_input_action("agent_jump", timeout=2)

                name_input = main.get_by_test_id("name-input")
                self.assertEqual(godot.locator({"property": "placeholder_text", "contains": "Nam"}).count(), 1)
                self.assertEqual(main.get_by_placeholder("Nam", exact=False).count(), 1)
                echo = main.get_by_test_id("echo")
                expect(name_input).to_be_editable(timeout=2)
                expect(name_input).to_have_value("", timeout=2)
                name_input.focus()
                expect(name_input).to_be_focused(timeout=2)
                changed = name_input.wait_for_signal(
                    "text_changed",
                    timeout=2,
                    action=lambda: name_input.fill("Ada"),
                )
                self.assertEqual(changed["args"], ["Ada"])
                expect(name_input).to_have_value("Ada", timeout=2)
                expect(echo).to_have_property("text", "Hello Ada", timeout=2)
                submitted = name_input.wait_for_signal(
                    "text_submitted",
                    timeout=2,
                    action=lambda: name_input.press("Enter"),
                )
                self.assertEqual(submitted["args"], ["Ada"])

                scene = godot.change_scene("res://scenes/secondary.tscn", timeout=2)
                self.assertEqual(scene["scene_file_path"], "res://scenes/secondary.tscn")
                expect(godot.locator("#SecondaryTitle")).to_have_property("text", "Secondary Scene", timeout=2)
                back = godot.locator("#BackButton")
                back.wait_for_signal("pressed", timeout=2, action=back.click)
                godot.wait_for_scene("res://scenes/main.tscn", timeout=2)
                expect(godot.locator("#Title")).to_have_property("text", "Godot Playwright", timeout=2)

    def test_editor_can_create_modify_and_save_scene(self) -> None:
        with temporary_project() as project:
            scene_path = "res://scenes/generated_by_agent.tscn"
            with Godot(project, mode="editor", timeout=30, stdout=None) as godot:
                info = godot.rpc("engine.info")
                self.assertTrue(info["editor"])
                protocol = godot.protocol_describe()
                self.assertTrue(protocol["editor"])
                protocol_methods = {entry["method"] for entry in protocol["methods"]}
                self.assertIn("protocol.describe", protocol_methods)
                self.assertIn("editor.filesystem.open", protocol_methods)
                self.assertIn("resource.move", protocol_methods)
                protocol_domains = {entry["name"]: entry for entry in protocol["domains"]}
                self.assertGreaterEqual(protocol_domains["editor"]["count"], 10)
                self.assertIn("resource_safe_move", protocol["features"])
                editor_snapshot = godot.editor_snapshot(max_depth=1)
                self.assertEqual(editor_snapshot["class"], "Panel")
                expect(godot.editor_locator("Panel")).to_exist(timeout=2)
                expect(godot.editor_get_by_role("panel")).to_exist(timeout=2)

                self.assertEqual(godot.project_get_setting("application/config/name"), "Godot Playwright Test")
                godot.project_set_setting("application/config/description", "Created by Godot Playwright", save=True)
                godot.editor_new_scene(class_name="Control", name="AgentScene")
                expect_editor(godot).to_have_edited_scene_name("AgentScene", timeout=5)
                node_classes = godot.node_classes(base_class="Control", name_contains="Label", max_results=20)
                node_class_names = {entry["class"] for entry in node_classes["classes"]}
                self.assertIn("Label", node_class_names)
                expect_node_class(godot, "Label").to_be_listed(base_class="Control", timeout=2)
                label_schema = godot.node_class_describe(
                    "Label",
                    properties=["text"],
                    methods=["set_text"],
                    storage_only=True,
                )
                self.assertTrue(label_schema["is_node"])
                self.assertEqual(label_schema["properties"][0]["name"], "text")
                self.assertEqual(label_schema["methods"][0]["name"], "set_text")
                self.assertEqual(label_schema["methods"][0]["arg_count"], 1)
                self.assertEqual(label_schema["methods"][0]["args"][0]["type_name"], "String")
                button_signal_schema = godot.node_class_describe(
                    "Button",
                    signals=["pressed"],
                    include_methods=False,
                    include_values=False,
                )
                self.assertEqual(button_signal_schema["signals"][0]["name"], "pressed")
                self.assertEqual(button_signal_schema["signals"][0]["arg_count"], 0)
                expect_node_class(godot, "Label").to_have_property("text", type_name="String", storage=True, timeout=2)
                expect_node_class(godot, "Label").to_have_method("get_meta", timeout=2)
                expect_node_class(godot, "Button").to_have_signal("pressed", timeout=2)
                created_label = godot.create_node("edited", "Label", name="StatusLabel")
                self.assertEqual(created_label["name"], "StatusLabel")
                label = godot.locator("#StatusLabel")
                self.assertTrue(godot.editor_history()["can_undo"])
                expect_editor(godot).to_have_undo(timeout=2)
                expect_editor(godot).not_to_have_redo(timeout=2)
                expect_editor(godot).to_match_history({"available": True, "can_undo": True}, timeout=2)
                undone_create = godot.editor_undo()
                self.assertTrue(undone_create["changed"])
                expect_editor(godot).to_have_redo(timeout=2)
                expect(label).not_to_exist(timeout=2)
                redone_create = godot.editor_redo()
                self.assertTrue(redone_create["changed"])
                expect_editor(godot).not_to_have_redo(timeout=2)
                expect(label).to_exist(timeout=2)
                label.set("text", "created by automation", undo_action="Set generated label text")
                expect(label).to_have_property("text", "created by automation", timeout=2)
                undone_text = godot.editor_undo()
                self.assertTrue(undone_text["changed"])
                expect(label).not_to_have_property("text", "created by automation", timeout=2)
                redone_text = godot.editor_redo()
                self.assertTrue(redone_text["changed"])
                expect(label).to_have_property("text", "created by automation", timeout=2)
                label_inspector = godot.inspector("#StatusLabel")
                label_description = label_inspector.describe(properties=["text"])
                self.assertEqual(label_description["properties"][0]["name"], "text")
                self.assertEqual(label_inspector.property("text").value(), "created by automation")
                label_inspector.property("text").set("created via inspector")
                expect(label).to_have_property("text", "created via inspector", timeout=2)
                expect_inspector(label_inspector).to_have_property("text", "created via inspector", timeout=2)
                label_batch = label_inspector.set_properties({"tooltip_text": "Inspector Batch", "visible": True})
                self.assertEqual(label_batch["values"]["tooltip_text"], "Inspector Batch")
                self.assertEqual(
                    label_inspector.values(properties=["text", "tooltip_text"])["tooltip_text"],
                    "Inspector Batch",
                )
                expect_inspector(label_inspector).to_have_properties(
                    {"text": "created via inspector", "tooltip_text": "Inspector Batch"},
                    timeout=2,
                )
                expect_inspector(label_inspector).not_to_have_properties(
                    {"text": "missing text", "tooltip_text": "Inspector Batch"},
                    timeout=2,
                )
                panel = godot.create_node("edited", "VBoxContainer", name="GeneratedPanel")
                self.assertEqual(panel["name"], "GeneratedPanel")
                badge_scene_path = "res://scenes/badge.tscn"
                badge_scene_text = (
                    '[gd_scene format=3]\n\n'
                    '[node name="Badge" type="Label"]\n'
                    'text = "Reusable Badge"\n'
                    'metadata/test_id = "agent-badge"\n'
                )
                godot.fs_write_text(badge_scene_path, badge_scene_text)
                self.assertTrue(godot.fs_exists(badge_scene_path)["exists"])
                badge_instance = godot.instantiate_scene(
                    badge_scene_path,
                    parent="#GeneratedPanel",
                    name="BadgeInstance",
                    index=0,
                )
                self.assertEqual(badge_instance["name"], "BadgeInstance")
                self.assertEqual(badge_instance["source_scene"], badge_scene_path)
                expect(godot.locator("#BadgeInstance")).to_have_property("text", "Reusable Badge", timeout=2)
                reparented_label = godot.reparent_node("#StatusLabel", "#GeneratedPanel", index=0)
                self.assertEqual(reparented_label["new_parent"].rsplit("/", 1)[-1], "GeneratedPanel")
                self.assertEqual(label.evaluate("node.get_parent().name"), "GeneratedPanel")
                duplicated_label = godot.duplicate_node("#StatusLabel", parent="#GeneratedPanel", name="StatusLabelCopy", index=1)
                self.assertEqual(duplicated_label["name"], "StatusLabelCopy")
                label_copy = godot.locator("#StatusLabelCopy")
                label_copy.set("text", "copy created by automation")
                moved_copy = godot.move_node("#StatusLabelCopy", 0)
                self.assertEqual(moved_copy["index"], 0)
                self.assertEqual(label_copy.evaluate("node.get_index()"), 0)
                grouped_label = godot.add_node_group("#StatusLabel", "agent_generated")
                self.assertTrue(grouped_label["added"])
                self.assertIn("agent_generated", grouped_label["groups"])
                self.assertIn("agent_generated", godot.node_groups("#StatusLabel")["groups"])
                expect(label).to_have_group("agent_generated", timeout=2)
                expect(godot.get_by_group("agent_generated")).to_exist(timeout=2)
                temporary_group = godot.add_node_group("#StatusLabel", "temporary_generated", persistent=False)
                self.assertFalse(temporary_group["persistent"])
                removed_group = godot.remove_node_group("#StatusLabel", "temporary_generated")
                self.assertTrue(removed_group["removed"])
                self.assertNotIn("temporary_generated", godot.node_groups("#StatusLabel")["groups"])
                expect(label).not_to_have_group("temporary_generated", timeout=2)
                status_script_path = "res://scripts/generated/status_label.gd"
                status_script_text = (
                    "@tool\n"
                    "extends Label\n\n"
                    "func agent_status() -> String:\n"
                    "\treturn \"%s:%s\" % [name, text]\n"
                )
                godot.fs_write_text(status_script_path, status_script_text)
                expect_script(godot, status_script_path).to_extend("Label", timeout=2)
                expect_script(godot, status_script_path).to_define_function("agent_status", timeout=2)
                attached_script = godot.attach_script("#StatusLabel", status_script_path, inspect=True)
                self.assertEqual(attached_script["script"]["path"], status_script_path)
                expect(label).to_have_script(status_script_path, timeout=2)
                self.assertEqual(label.call("agent_status"), "StatusLabel:created via inspector")
                self.assertEqual(label.get("script")["path"], status_script_path)
                godot.attach_script("#StatusLabelCopy", status_script_path, reload=False)
                expect(label_copy).to_have_script(status_script_path, timeout=2)
                detached_script = godot.detach_script("#StatusLabelCopy")
                self.assertIsNone(detached_script["script"])
                self.assertEqual(detached_script["previous_script"]["path"], status_script_path)
                expect(label_copy).not_to_have_script(timeout=2)
                signal_button = godot.create_node("#GeneratedPanel", "Button", name="SignalButton")
                self.assertEqual(signal_button["name"], "SignalButton")
                signal_button_locator = godot.locator("#SignalButton")
                signal_button_locator.set("text", "Send Signal")
                signal_receiver = godot.create_node("#GeneratedPanel", "Node", name="SignalReceiver")
                self.assertEqual(signal_receiver["name"], "SignalReceiver")
                signal_receiver_path = "res://scripts/generated/signal_receiver.gd"
                signal_receiver_text = (
                    "@tool\n"
                    "extends Node\n\n"
                    "func on_signal_button_pressed() -> void:\n"
                    "\tset_meta(\"pressed_seen\", true)\n\n"
                    "func on_temporary_pressed() -> void:\n"
                    "\tset_meta(\"temporary_seen\", true)\n"
                )
                godot.fs_write_text(signal_receiver_path, signal_receiver_text)
                expect_script(godot, signal_receiver_path).to_define_function("on_signal_button_pressed", timeout=2)
                expect_script(godot, signal_receiver_path).to_define_function("on_temporary_pressed", timeout=2)
                attached_receiver = godot.attach_script("#SignalReceiver", signal_receiver_path, reload=True)
                self.assertEqual(attached_receiver["script"]["path"], signal_receiver_path)
                self.assertEqual(godot.signal_connections("#SignalButton", signal="pressed")["count"], 0)
                persistent_connection = signal_button_locator.connect_signal(
                    "pressed",
                    target="#SignalReceiver",
                    method="on_signal_button_pressed",
                )
                self.assertTrue(persistent_connection["connected"])
                self.assertTrue(persistent_connection["connection"]["persistent"])
                self.assertEqual(persistent_connection["connection"]["target_path"].rsplit("/", 1)[-1], "SignalReceiver")
                self.assertEqual(persistent_connection["connection"]["method"], "on_signal_button_pressed")
                expect(signal_button_locator).to_have_signal_connection(
                    "pressed",
                    target="#SignalReceiver",
                    method="on_signal_button_pressed",
                    persistent=True,
                    timeout=2,
                )
                temporary_connection = godot.signal_connect(
                    "#SignalButton",
                    "pressed",
                    target="#SignalReceiver",
                    method="on_temporary_pressed",
                )
                self.assertTrue(temporary_connection["connected"])
                disconnected_connection = signal_button_locator.disconnect_signal(
                    "pressed",
                    target="#SignalReceiver",
                    method="on_temporary_pressed",
                )
                self.assertTrue(disconnected_connection["removed"])
                pressed_connections = signal_button_locator.signal_connections("pressed")
                self.assertEqual(pressed_connections["count"], 1)
                self.assertEqual(pressed_connections["connections"][0]["method"], "on_signal_button_pressed")
                expect(signal_button_locator).not_to_have_signal_connection(
                    "pressed",
                    target="#SignalReceiver",
                    method="on_temporary_pressed",
                    timeout=0.2,
                )
                receiver_locator = godot.locator("#SignalReceiver")
                receiver_locator.call("set_meta", "pressed_seen", False)
                signal_button_locator.call("emit_signal", "pressed")
                wait_for_call(
                    receiver_locator,
                    "get_meta",
                    "pressed_seen",
                    False,
                    predicate=lambda value: value is True,
                    timeout=2,
                )
                panel_scene_path = "res://scenes/generated_panel.tscn"
                saved_panel_scene = godot.locator("#GeneratedPanel").save_as_scene(panel_scene_path)
                self.assertTrue(saved_panel_scene["saved"])
                self.assertEqual(saved_panel_scene["path"], panel_scene_path)
                self.assertEqual(saved_panel_scene["source"]["name"], "GeneratedPanel")
                self.assertTrue(godot.fs_exists(panel_scene_path)["exists"])
                self.assertEqual(godot.resource_inspect(panel_scene_path)["class"], "PackedScene")
                panel_scene = expect_scene_file(project, panel_scene_path)
                panel_scene.to_be_valid(timeout=2)
                panel_scene.to_have_root(name="GeneratedPanel", class_name="VBoxContainer", timeout=2)
                panel_scene.to_have_node(
                    name="StatusLabel",
                    script=status_script_path,
                    groups=["agent_generated"],
                    timeout=2,
                )
                panel_scene.to_have_node(name="BadgeInstance", instance_path=badge_scene_path, timeout=2)
                panel_scene.to_have_connection(
                    "pressed",
                    from_node="SignalButton",
                    to="SignalReceiver",
                    method="on_signal_button_pressed",
                    timeout=2,
                )
                project_scenes = godot.scene_files(
                    "res://scenes",
                    name="generated_panel.tscn",
                    root_class="VBoxContainer",
                    include_nodes=True,
                    max_results=20,
                )
                self.assertEqual(project_scenes["count"], 1)
                self.assertEqual(project_scenes["scenes"][0]["path"], panel_scene_path)
                self.assertEqual(project_scenes["scenes"][0]["root_name"], "GeneratedPanel")
                self.assertEqual(project_scenes["scenes"][0]["root_class"], "VBoxContainer")
                self.assertGreaterEqual(project_scenes["scenes"][0]["node_count"], 4)
                self.assertTrue(project_scenes["scenes"][0]["ok"])
                expect_project_scene(godot, panel_scene_path).to_be_listed(root_class="VBoxContainer", timeout=2)
                expect_project_scene(godot, panel_scene_path).to_have_root(
                    name="GeneratedPanel",
                    class_name="VBoxContainer",
                    timeout=2,
                )
                expect_project_scene(godot, panel_scene_path).to_have_no_missing_dependencies(timeout=2)
                panel_description = godot.scene_file_describe(panel_scene_path, include_properties=True)
                self.assertEqual(panel_description["root_name"], "GeneratedPanel")
                self.assertGreaterEqual(panel_description["node_count"], 4)
                self.assertGreaterEqual(panel_description["ext_resource_count"], 2)
                self.assertEqual(
                    expect_project_scene(godot, panel_scene_path).to_have_node(
                        name="StatusLabel",
                        script=status_script_path,
                        groups=["agent_generated"],
                        timeout=2,
                    )["script"],
                    status_script_path,
                )
                self.assertEqual(
                    expect_project_scene(godot, panel_scene_path).to_have_node(
                        name="BadgeInstance",
                        instance_path=badge_scene_path,
                        timeout=2,
                    )["instance_path"],
                    badge_scene_path,
                )
                expect_project_scene(godot, panel_scene_path).to_have_connection(
                    "pressed",
                    from_node="SignalButton",
                    to="SignalReceiver",
                    method="on_signal_button_pressed",
                    timeout=2,
                )
                expect_resource(godot, panel_scene_path).to_have_class("PackedScene", timeout=2)
                expect_resource(godot, panel_scene_path).to_have_no_missing_dependencies(timeout=2)
                main_dependencies = godot.resource_dependencies("res://scenes/main.tscn")
                self.assertTrue(main_dependencies["ok"], main_dependencies)
                dependency_paths = {dependency["path"] for dependency in main_dependencies["dependencies"]}
                self.assertIn("res://scripts/main.gd", dependency_paths)
                self.assertIn("res://scenes/secondary.tscn", dependency_paths)
                expect_resource(godot, "res://scenes/main.tscn").to_have_dependency(
                    "res://scripts/main.gd",
                    timeout=2,
                )
                script_references = godot.resource_references(
                    "res://scripts/main.gd",
                    search_path="res://scenes",
                    exists=True,
                    max_results=20,
                )
                self.assertIn("res://scenes/main.tscn", {entry["path"] for entry in script_references["references"]})
                referencing_scene = expect_resource(godot, "res://scripts/main.gd").to_be_referenced_by(
                    "res://scenes/main.tscn",
                    search_path="res://scenes",
                    exists=True,
                    timeout=2,
                )
                self.assertEqual(referencing_scene["path"], "res://scenes/main.tscn")
                resource_classes = godot.resource_classes(name_contains="Gradient", max_results=20)
                resource_class_names = {entry["class"] for entry in resource_classes["classes"]}
                self.assertIn("Gradient", resource_class_names)
                self.assertIn("GradientTexture1D", resource_class_names)
                expect_resource_class(godot, "GradientTexture1D").to_be_listed(timeout=2)
                gradient_texture_schema = godot.resource_class_describe(
                    "GradientTexture1D",
                    properties=["gradient"],
                    storage_only=True,
                )
                self.assertTrue(gradient_texture_schema["is_resource"])
                self.assertEqual(gradient_texture_schema["properties"][0]["name"], "gradient")
                expect_resource_class(godot, "GradientTexture1D").to_have_property(
                    "gradient",
                    storage=True,
                    timeout=2,
                )
                gradient = godot.resource_save(
                    "res://data/agent_gradient.tres",
                    class_name="Gradient",
                    properties={"resource_name": "AgentGradient"},
                    timeout=2,
                )
                self.assertEqual(gradient["class"], "Gradient")
                gradient_texture = godot.resource_save(
                    "res://data/agent_gradient_texture.tres",
                    class_name="GradientTexture1D",
                    properties={
                        "resource_name": "AgentGradientTexture",
                        "gradient": {
                            "$type": "ResourceRef",
                            "path": "res://data/agent_gradient.tres",
                            "class": "Gradient",
                        },
                    },
                    timeout=2,
                )
                self.assertEqual(gradient_texture["resource"]["properties"]["gradient"]["path"], "res://data/agent_gradient.tres")
                self.assertEqual(gradient_texture["dependency_state"]["dependency_count"], 1)
                expect_resource(godot, "res://data/agent_gradient_texture.tres").to_have_dependency(
                    "res://data/agent_gradient.tres",
                    timeout=2,
                )
                gradient_texture_file = godot.resource_file_describe(
                    "res://data/agent_gradient_texture.tres",
                    include_properties=True,
                )
                self.assertEqual(gradient_texture_file["root_class"], "GradientTexture1D")
                self.assertEqual(gradient_texture_file["properties"]["resource_name"], "AgentGradientTexture")
                self.assertEqual(gradient_texture_file["ext_resources"][0]["path"], "res://data/agent_gradient.tres")
                listed_gradient_ext = expect_resource(
                    godot,
                    "res://data/agent_gradient_texture.tres",
                ).to_have_file_ext_resource(
                    path="res://data/agent_gradient.tres",
                    resource_type="Gradient",
                    exists=True,
                    timeout=2,
                )
                self.assertEqual(listed_gradient_ext["path"], "res://data/agent_gradient.tres")
                moved_gradient_path = "res://data/agent_gradient_moved.tres"
                move_preview = godot.resource_move(
                    "res://data/agent_gradient.tres",
                    moved_gradient_path,
                    search_path="res://data",
                    extensions="tres",
                    expected_reference_files=1,
                    expected_replacements=1,
                    dry_run=True,
                    timeout=2,
                )
                self.assertTrue(move_preview["dry_run"])
                self.assertEqual(move_preview["references_before"]["count"], 1)
                self.assertEqual(move_preview["changed_reference_files"], 1)
                self.assertEqual(move_preview["reference_replacements"], 1)
                self.assertIn(moved_gradient_path, move_preview["reference_updates"][0]["text"])
                moved_gradient = godot.resource_move(
                    "res://data/agent_gradient.tres",
                    moved_gradient_path,
                    search_path="res://data",
                    extensions="tres",
                    expected_reference_files=1,
                    expected_replacements=1,
                    dry_run=False,
                    timeout=2,
                )
                self.assertTrue(moved_gradient["moved"])
                self.assertEqual(moved_gradient["source_missing"]["type"], "missing")
                self.assertEqual(moved_gradient["destination_state"]["type"], "file")
                self.assertEqual(moved_gradient["remaining_source_references"]["count"], 0)
                self.assertEqual(moved_gradient["references_after"]["count"], 1)
                expect_resource(godot, moved_gradient_path).to_be_referenced_by(
                    "res://data/agent_gradient_texture.tres",
                    search_path="res://data",
                    resource_type="Gradient",
                    exists=True,
                    timeout=2,
                )
                expect_resource(godot, "res://data/agent_gradient_texture.tres").to_have_dependency(
                    moved_gradient_path,
                    timeout=2,
                )
                moved_gradient_texture_file = godot.resource_file_describe(
                    "res://data/agent_gradient_texture.tres",
                    include_properties=True,
                )
                self.assertEqual(moved_gradient_texture_file["ext_resources"][0]["path"], moved_gradient_path)
                expect_resource(
                    godot,
                    "res://data/agent_gradient_texture.tres",
                ).to_have_file_ext_resource(
                    path=moved_gradient_path,
                    resource_type="Gradient",
                    exists=True,
                    timeout=2,
                )
                inline_gradient = godot.resource_set_properties(
                    "res://data/agent_gradient_texture.tres",
                    {
                        "gradient": {
                            "$type": "SubResource",
                            "class": "Gradient",
                            "resource_name": "InlineGradient",
                        }
                    },
                    timeout=2,
                )
                self.assertEqual(inline_gradient["resource"]["properties"]["gradient"]["class"], "Gradient")
                self.assertEqual(inline_gradient["resource"]["properties"]["gradient"]["resource_name"], "InlineGradient")
                selection = godot.editor_select("#StatusLabel", inspect=True)
                self.assertEqual(selection["count"], 1)
                self.assertEqual(selection["nodes"][0]["name"], "StatusLabel")
                self.assertEqual(godot.editor_selection()["count"], 1)
                inspected_label = godot.editor_inspect(selector="#StatusLabel", property="text")
                self.assertEqual(inspected_label["target"]["name"], "StatusLabel")
                godot.editor_save_scene(scene_path)
                expect_editor(godot).to_have_edited_scene(scene_path, timeout=2)
                opened_scene_file = godot.editor_filesystem_open(scene_path, timeout=2)
                self.assertEqual(opened_scene_file["action"], "scene")
                self.assertEqual(opened_scene_file["editor_status"]["edited_scene_file_path"], scene_path)

                script_path = "res://scripts/generated/agent_tool.gd"
                script_text = (
                    "class_name AgentTool\n"
                    "extends Node\n"
                    "signal tool_ready\n"
                    "@export var enabled := true\n\n"
                    "func generated_value() -> int:\n"
                    "\treturn 42\n"
                )
                godot.fs_write_text(script_path, script_text)
                self.assertTrue(godot.fs_exists(script_path)["exists"])
                self.assertIn("generated_value", godot.fs_read_text(script_path))
                listing = godot.fs_list("res://scripts/generated")
                self.assertIn("agent_tool.gd", listing["files"])
                opened_script = godot.editor_open_script(script_path, line=3)
                self.assertEqual(opened_script["path"], script_path)
                self.assertIn("script_editor", opened_script)
                self.assertIn("available", opened_script["script_editor"])
                script_editor_status = godot.editor_script_status()
                self.assertIn("open_paths", script_editor_status)
                editor_ui = godot.editor_ui_status()
                self.assertIn("has_base_control", editor_ui)
                self.assertIn("can_get_main_screen", editor_ui)
                self.assertIn("bottom_panel", editor_ui)
                expect_editor(godot).to_have_base_control(timeout=2)
                if editor_ui.get("can_set_main_screen") and editor_ui.get("main_screen_name"):
                    original_main_screen = str(editor_ui["main_screen_name"])
                    main_screen_entries = editor_ui.get("main_screens", [])
                    main_screen_names = {
                        str(entry.get("api_name") or entry.get("name") or "")
                        for entry in main_screen_entries
                        if isinstance(entry, dict)
                    }
                    switch_target = "Script" if "Script" in main_screen_names else original_main_screen
                    switched_ui = godot.editor_switch_main_screen(switch_target, timeout=2)
                    self.assertIn("ui_state", switched_ui)
                    expect_editor(godot).to_have_main_screen(switch_target, timeout=2)
                    if switch_target != original_main_screen:
                        godot.editor_switch_main_screen(original_main_screen, timeout=2)
                if isinstance(editor_ui.get("bottom_panel"), dict) and editor_ui["bottom_panel"].get("can_hide"):
                    hidden_panel = godot.editor_hide_bottom_panel(timeout=2)
                    self.assertTrue(hidden_panel["hidden"])
                script_description = godot.editor_script_describe(script_path, include_source=True)
                method_names = {method["name"] for method in script_description["methods"]}
                self.assertIn("generated_value", method_names)
                self.assertEqual(script_description["symbols"]["class_name"], "AgentTool")
                self.assertEqual(script_description["symbols"]["extends"], "Node")
                self.assertIn("generated_value", script_description["source"])
                script_classes = godot.script_classes(class_name="AgentTool", base_class="Node", max_results=20)
                self.assertEqual(script_classes["count"], 1)
                self.assertEqual(script_classes["classes"][0]["path"], script_path)
                self.assertTrue(script_classes["classes"][0]["is_node"])
                self.assertFalse(script_classes["classes"][0]["is_resource"])
                self.assertEqual(script_classes["classes"][0]["signals"][0]["name"], "tool_ready")
                self.assertEqual(script_classes["classes"][0]["variables"][0]["name"], "enabled")
                script_file = godot.script_file_describe(script_path, include_source=True)
                self.assertEqual(script_file["class_name"], "AgentTool")
                self.assertEqual(script_file["extends"], "Node")
                self.assertEqual(script_file["functions"][0]["name"], "generated_value")
                self.assertEqual(script_file["signals"][0]["name"], "tool_ready")
                self.assertEqual(script_file["variables"][0]["name"], "enabled")
                self.assertIn("generated_value", script_file["source"])
                expect_script_class(godot, "AgentTool").to_be_listed(base_class="Node", timeout=2)
                expect_script_class(godot, "AgentTool").to_extend("Node", timeout=2)
                expect_script_class(godot, "AgentTool").to_be_node(timeout=2)
                expect_script_class(godot, "AgentTool").to_have_function("generated_value", timeout=2)
                expect_script(godot, script_path).to_have_class_name("AgentTool", timeout=2)
                expect_script(godot, script_path).to_define_signal("tool_ready", timeout=2)
                expect_script(godot, script_path).to_define_variable("enabled", timeout=2)
                expect_script(godot, script_path).to_extend("Node", timeout=2)
                expect_script(godot, script_path).to_define_function("generated_value", timeout=2)
                expect_script(godot, script_path).to_contain_source("generated_value", timeout=2)
                expect_script_file(project, script_path).to_extend("Node", timeout=2)
                expect_script_file(project, script_path).to_define_function("generated_value", timeout=2)
                script_entry = godot.editor_filesystem_describe(script_path)
                self.assertTrue(script_entry["exists"])
                self.assertEqual(script_entry["kind"], "file")
                found_scripts = godot.editor_filesystem_find(
                    "res://scripts",
                    extension="gd",
                    name="agent_tool.gd",
                )
                self.assertIn(script_path, {entry["path"] for entry in found_scripts["entries"]})
                expect_filesystem(godot, "res://scripts").to_contain("agent_tool.gd", extension="gd", timeout=2)
                expect_filesystem(godot, script_path).to_exist(timeout=2)
                selected_script = godot.editor_filesystem_select(script_path, inspect=True)
                self.assertTrue(selected_script["exists"])
                opened_script_file = godot.editor_filesystem_open(script_path, line=3, timeout=2)
                self.assertEqual(opened_script_file["action"], "script")
                self.assertEqual(opened_script_file["script_state"]["path"], script_path)
                self.assertTrue(opened_script_file["filesystem_state"]["selected"])

                resource_path = "res://data/agent_resource.tres"
                saved_resource = godot.resource_save(
                    resource_path,
                    properties={"resource_name": "AgentResource"},
                )
                self.assertEqual(saved_resource["resource_name"], "AgentResource")
                resource_inspector = godot.inspector(resource_path=resource_path)
                resource_description = resource_inspector.describe(properties=["resource_name"])
                self.assertEqual(resource_description["properties"][0]["name"], "resource_name")
                resource_inspector.property("resource_name").set("AgentResourceV2", save=True)
                self.assertEqual(
                    resource_inspector.values(properties=["resource_name"]),
                    {"resource_name": "AgentResourceV2"},
                )
                resource_batch = resource_inspector.set_properties({"resource_name": "AgentResourceV2"}, save=True)
                self.assertTrue(resource_batch["saved"])
                expect_inspector(resource_inspector).to_have_properties({"resource_name": "AgentResourceV2"}, timeout=2)
                inspected_resource = godot.resource_inspect(
                    resource_path,
                    include_properties=True,
                    properties=["resource_name"],
                )
                self.assertEqual(inspected_resource["properties"]["resource_name"], "AgentResourceV2")
                resource_files = godot.resource_files(
                    "res://data",
                    name="agent_resource.tres",
                    class_name="Resource",
                    resource_name="AgentResourceV2",
                    max_results=20,
                )
                self.assertEqual(resource_files["count"], 1)
                self.assertEqual(resource_files["resources"][0]["path"], resource_path)
                self.assertEqual(resource_files["resources"][0]["resource_name"], "AgentResourceV2")
                self.assertTrue(resource_files["resources"][0]["ok"])
                opened_resource_file = godot.editor_filesystem_open(resource_path, timeout=2)
                self.assertEqual(opened_resource_file["action"], "resource")
                self.assertTrue(opened_resource_file["inspected"])
                self.assertEqual(opened_resource_file["inspector_state"]["target"]["path"], resource_path)
                expect_resource(godot, resource_path).to_be_listed(
                    class_name="Resource",
                    resource_name="AgentResourceV2",
                    timeout=2,
                )
                resource_file = godot.resource_file_describe(resource_path, include_source=True)
                self.assertEqual(resource_file["file_format"], "text")
                self.assertEqual(resource_file["root_class"], "Resource")
                self.assertEqual(resource_file["properties"]["resource_name"], "AgentResourceV2")
                self.assertIn("AgentResourceV2", resource_file["source"])
                expect_resource(godot, resource_path).to_have_class("Resource", timeout=2)
                expect_resource(godot, resource_path).to_have_property("resource_name", "AgentResourceV2", timeout=2)
                expect_resource(godot, resource_path).to_have_file_property(
                    "resource_name",
                    "AgentResourceV2",
                    timeout=2,
                )
                inspected_in_editor = godot.editor_inspect(resource_path=resource_path)
                self.assertEqual(inspected_in_editor["target"]["path"], resource_path)
                scanned = godot.editor_scan_filesystem([script_path, resource_path])
                self.assertTrue(scanned["requested"])
                reimported = godot.resource_reimport([script_path, resource_path])
                self.assertEqual(reimported["paths"], [script_path, resource_path])
                pixel_path = "res://assets/generated_pixel.png"
                written_pixel = godot.fs_write_bytes(pixel_path, GENERATED_PIXEL_PNG)
                self.assertEqual(written_pixel["bytes"], len(GENERATED_PIXEL_PNG))
                self.assertEqual(godot.fs_read_bytes(pixel_path), GENERATED_PIXEL_PNG)
                imported_pixel = godot.resource_reimport(pixel_path, force=True)
                self.assertEqual(imported_pixel["paths"], [pixel_path])
                self.assertTrue(imported_pixel["requested"])
                expect_filesystem(godot, pixel_path).to_exist(timeout=2)
                pixel_texture = wait_for_resource(godot, pixel_path, type_hint="Texture2D", timeout=5)
                self.assertTrue(
                    str(pixel_texture["class"]).endswith("Texture2D") or pixel_texture["class"] == "ImageTexture",
                    pixel_texture,
                )
                pixel_import = godot.wait_for_import(pixel_path, timeout=5)
                self.assertTrue(pixel_import["exists"])
                self.assertTrue(pixel_import["resource_exists"])
                self.assertEqual(pixel_import["importer"], "texture")
                self.assertEqual(pixel_import["source_file"], pixel_path)
                self.assertTrue(pixel_import["source_file_state"]["exists"], pixel_import)
                self.assertTrue(pixel_import["source_file_matches_path"], pixel_import)
                self.assertTrue(str(pixel_import["resource_type"]).endswith("Texture2D"), pixel_import)
                self.assertTrue(pixel_import["dest_files"], pixel_import)
                self.assertTrue(pixel_import["generated_files_ready"], pixel_import)
                self.assertEqual(pixel_import["generated_file_count"], len(pixel_import["generated_files"]))
                self.assertEqual(pixel_import["missing_generated_file_count"], 0, pixel_import)
                self.assertTrue(all(entry["exists"] for entry in pixel_import["generated_files"]), pixel_import)
                self.assertIn("diagnostics", pixel_import)
                self.assertIn("remap", pixel_import["sections"])
                import_listing = godot.resource_imports(
                    "res://assets",
                    importer="texture",
                    generated_files_ready=True,
                    max_results=20,
                )
                self.assertIn(pixel_path, {entry["path"] for entry in import_listing["imports"]})
                listed_pixel_import = expect_resource(godot, pixel_path).to_be_import_listed(
                    importer="texture",
                    generated_files_ready=True,
                    timeout=5,
                )
                self.assertEqual(listed_pixel_import["path"], pixel_path)
                expect_resource(godot, pixel_path).to_be_imported(
                    importer="texture",
                    generated_files_ready=True,
                    timeout=5,
                )
                agent_state_path = "res://scripts/generated/agent_state.gd"
                godot.fs_write_text(
                    agent_state_path,
                    "extends Node\n\nvar value := 7\n\nfunc get_value() -> int:\n\treturn value\n",
                )
                expect_script(godot, agent_state_path).to_define_function("get_value", timeout=2)
                export_presets_before = godot.project_export_presets()
                self.assertEqual(export_presets_before["count"], 0)
                linux_preset = godot.project_set_export_preset(
                    "Agent Linux",
                    "Linux",
                    export_path="build/agent_linux.x86_64",
                    options={"binary_format/embed_pck": False},
                )
                self.assertEqual(linux_preset["index"], 0)
                self.assertEqual(linux_preset["name"], "Agent Linux")
                self.assertEqual(linux_preset["platform"], "Linux")
                self.assertEqual(linux_preset["export_path"], "build/agent_linux.x86_64")
                self.assertFalse(linux_preset["options"]["binary_format/embed_pck"])
                updated_preset = godot.project_set_export_preset(
                    "Agent Linux",
                    "Linux",
                    export_path="build/agent_linux_v2.x86_64",
                    runnable=False,
                    options={"binary_format/embed_pck": False},
                )
                self.assertEqual(updated_preset["index"], 0)
                self.assertFalse(updated_preset["runnable"])
                self.assertEqual(updated_preset["export_path"], "build/agent_linux_v2.x86_64")
                export_presets_after = godot.project_export_presets()
                self.assertTrue(export_presets_after["exists"])
                self.assertEqual(export_presets_after["count"], 1)
                self.assertEqual(export_presets_after["presets"][0]["name"], "Agent Linux")
                expect_project(godot).to_have_export_preset(
                    "Agent Linux",
                    platform="Linux",
                    export_path="build/agent_linux_v2.x86_64",
                    runnable=False,
                    options={"binary_format/embed_pck": False},
                    fields={"script_export_mode": 2},
                    timeout=2,
                )
                expect_project(godot).not_to_have_export_preset("Missing Export", timeout=0.2)
                self.assertEqual(godot.project_main_scene()["path"], "res://scenes/main.tscn")
                main_scene = godot.project_set_main_scene(scene_path, save=True)
                self.assertEqual(main_scene["path"], scene_path)
                expect_project(godot).to_have_main_scene(scene_path, timeout=2)
                autoload = godot.project_add_autoload("AgentState", agent_state_path, save=True)
                self.assertEqual(autoload["path"], agent_state_path)
                self.assertTrue(autoload["singleton"])
                autoloads = godot.project_autoloads()["autoloads"]
                self.assertIn("AgentState", {entry["name"] for entry in autoloads})
                expect_project(godot).to_have_autoload("AgentState", path=agent_state_path, singleton=True, timeout=2)
                project_summary = godot.project_summary(max_results=20, include_input_events=True)
                self.assertTrue(project_summary["ok"], project_summary["diagnostics"])
                self.assertEqual(project_summary["main_scene"]["path"], scene_path)
                self.assertEqual(project_summary["counts"]["autoloads"], 1)
                self.assertEqual(project_summary["counts"]["export_presets"], 1)
                self.assertGreaterEqual(project_summary["counts"]["scenes"], 2)
                self.assertGreaterEqual(project_summary["counts"]["scripts"], 2)
                self.assertGreaterEqual(project_summary["counts"]["resources"], 1)
                self.assertGreaterEqual(project_summary["counts"]["imports"], 1)
                self.assertIn(pixel_path, {entry["path"] for entry in project_summary["resource_imports"]["imports"]})
                project_doctor = godot.project_doctor(max_results=20, include_input_events=True)
                self.assertTrue(project_doctor["ready"], project_doctor["diagnostics"])
                self.assertEqual(project_doctor["project_summary"]["main_scene"]["path"], scene_path)
                doctor_checks = {entry["name"]: entry for entry in project_doctor["checks"]}
                self.assertEqual(doctor_checks["project_summary"]["status"], "pass")
                self.assertEqual(doctor_checks["main_scene"]["status"], "pass")
                self.assertIn("resource_safe_move", project_doctor["protocol"]["features"])
                self.assertIn("Project is ready", project_doctor["next_steps"][0])
                removed_autoload = godot.project_remove_autoload("AgentState", save=True)
                self.assertTrue(removed_autoload["removed"])
                self.assertNotIn("AgentState", {entry["name"] for entry in godot.project_autoloads()["autoloads"]})
                expect_project(godot).not_to_have_autoload("AgentState", timeout=2)
                restored_main_scene = godot.project_set_main_scene("res://scenes/main.tscn", save=True)
                self.assertEqual(restored_main_scene["path"], "res://scenes/main.tscn")
                expect_project(godot).to_have_main_scene("res://scenes/main.tscn", timeout=2)

            saved_scene = project / "scenes" / "generated_by_agent.tscn"
            self.assertTrue(saved_scene.exists())
            text = saved_scene.read_text(encoding="utf-8")
            self.assertIn("GeneratedPanel", text)
            self.assertIn("res://scenes/badge.tscn", text)
            self.assertIn("BadgeInstance", text)
            self.assertIn("StatusLabel", text)
            self.assertIn("StatusLabelCopy", text)
            self.assertIn("agent_generated", text)
            self.assertNotIn("temporary_generated", text)
            self.assertIn("SignalButton", text)
            self.assertIn("SignalReceiver", text)
            self.assertIn("res://scripts/generated/signal_receiver.gd", text)
            self.assertIn("on_signal_button_pressed", text)
            self.assertNotIn("on_temporary_pressed", text)
            self.assertIn("res://scripts/generated/status_label.gd", text)
            self.assertIn("created via inspector", text)
            self.assertIn("copy created by automation", text)
            self.assertIn("Created by Godot Playwright", (project / "project.godot").read_text(encoding="utf-8"))
            status_script = project / "scripts" / "generated" / "status_label.gd"
            self.assertTrue(status_script.exists())
            self.assertIn("agent_status", status_script.read_text(encoding="utf-8"))
            generated_script = project / "scripts" / "generated" / "agent_tool.gd"
            self.assertTrue(generated_script.exists())
            self.assertIn("generated_value", generated_script.read_text(encoding="utf-8"))
            signal_receiver_script = project / "scripts" / "generated" / "signal_receiver.gd"
            self.assertTrue(signal_receiver_script.exists())
            self.assertIn("on_signal_button_pressed", signal_receiver_script.read_text(encoding="utf-8"))
            agent_state_script = project / "scripts" / "generated" / "agent_state.gd"
            self.assertTrue(agent_state_script.exists())
            self.assertIn("get_value", agent_state_script.read_text(encoding="utf-8"))
            generated_resource = project / "data" / "agent_resource.tres"
            self.assertTrue(generated_resource.exists())
            self.assertIn("AgentResourceV2", generated_resource.read_text(encoding="utf-8"))
            generated_pixel = project / "assets" / "generated_pixel.png"
            self.assertTrue(generated_pixel.exists())
            self.assertEqual(generated_pixel.read_bytes(), GENERATED_PIXEL_PNG)
            export_presets = project / "export_presets.cfg"
            self.assertTrue(export_presets.exists())
            export_presets_text = export_presets.read_text(encoding="utf-8")
            self.assertIn('[preset.0]', export_presets_text)
            self.assertIn('name="Agent Linux"', export_presets_text)
            self.assertIn('platform="Linux"', export_presets_text)
            self.assertIn('runnable=false', export_presets_text)
            self.assertIn('export_path="build/agent_linux_v2.x86_64"', export_presets_text)
            self.assertIn('[preset.0.options]', export_presets_text)
            self.assertIn('binary_format/embed_pck=false', export_presets_text)
            project_text = (project / "project.godot").read_text(encoding="utf-8")
            self.assertIn('run/main_scene="res://scenes/main.tscn"', project_text)
            self.assertNotIn("AgentState", project_text)
            badge_scene = project / "scenes" / "badge.tscn"
            self.assertTrue(badge_scene.exists())
            self.assertIn("Reusable Badge", badge_scene.read_text(encoding="utf-8"))
            panel_scene = project / "scenes" / "generated_panel.tscn"
            self.assertTrue(panel_scene.exists())
            panel_scene_text = panel_scene.read_text(encoding="utf-8")
            self.assertIn("GeneratedPanel", panel_scene_text)
            self.assertIn("StatusLabel", panel_scene_text)
            self.assertIn("BadgeInstance", panel_scene_text)
            self.assertIn("SignalButton", panel_scene_text)
            self.assertIn("SignalReceiver", panel_scene_text)
            self.assertIn("res://scripts/generated/signal_receiver.gd", panel_scene_text)
            self.assertIn("on_signal_button_pressed", panel_scene_text)


class temporary_project:
    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        project = Path(self._tmp.name)
        (project / "scenes").mkdir()
        (project / "scripts").mkdir()
        (project / "project.godot").write_text(
            textwrap.dedent(
                """\
                config_version=5

                [application]

                config/name="Godot Playwright Test"
                run/main_scene="res://scenes/main.tscn"
                config/features=PackedStringArray("4.6")
                """
            ),
            encoding="utf-8",
        )
        (project / "scripts" / "main.gd").write_text(
            textwrap.dedent(
                """\
                extends Control

                var count := 0

                @onready var counter_button: Button = $CounterButton
                @onready var name_input: LineEdit = $NameInput
                @onready var echo_label: Label = $EchoLabel
                @onready var accept_terms: CheckBox = $AcceptTerms
                @onready var theme_select: OptionButton = $ThemeSelect
                @onready var volume_slider: HSlider = $VolumeSlider
                @onready var mode_tabs: TabBar = $ModeTabs
                @onready var settings_tabs: TabContainer = $SettingsTabs
                @onready var action_menu: MenuButton = $ActionMenu
                @onready var inventory_list: ItemList = $InventoryList
                @onready var loadout_list: ItemList = $LoadoutList
                @onready var quest_tree: Tree = $QuestTree
                @onready var talent_tree: Tree = $TalentTree
                @onready var hover_target: ColorRect = $HoverTarget
                @onready var drag_source: ColorRect = $DragSource
                @onready var drop_target: ColorRect = $DropTarget
                @onready var wheel_target: ColorRect = $WheelTarget
                @onready var touch_target: ColorRect = $TouchTarget
                @onready var show_confirm_button: Button = $ShowConfirmButton
                @onready var confirm_dialog: ConfirmationDialog = $ConfirmDialog
                @onready var animation_player: AnimationPlayer = $AutomationAnimation
                @onready var animated_label: Label = $AnimatedLabel
                @onready var physics_target_3d: StaticBody3D = $PhysicsTarget3D


                func _ready() -> void:
                    counter_button.pressed.connect(_on_counter_pressed)
                    name_input.text_changed.connect(_on_name_changed)
                    accept_terms.toggled.connect(_on_accept_terms_toggled)
                    theme_select.add_item("Arcade", 10)
                    theme_select.add_item("Story", 20)
                    theme_select.add_item("Simulation", 30)
                    theme_select.select(0)
                    theme_select.set_meta("selected_theme", "Arcade")
                    theme_select.item_selected.connect(_on_theme_selected)
                    volume_slider.set_meta("volume", volume_slider.value)
                    volume_slider.value_changed.connect(_on_volume_changed)
                    mode_tabs.add_tab("General")
                    mode_tabs.add_tab("Advanced")
                    mode_tabs.add_tab("Telemetry")
                    mode_tabs.set_tab_metadata(0, {"mode": "general"})
                    mode_tabs.set_tab_metadata(1, {"mode": "advanced"})
                    mode_tabs.set_tab_metadata(2, {"mode": "telemetry"})
                    mode_tabs.current_tab = 0
                    mode_tabs.set_meta("selected_mode", "General")
                    mode_tabs.tab_changed.connect(_on_mode_tab_changed)
                    settings_tabs.set_tab_metadata(0, {"panel": "overview"})
                    settings_tabs.set_tab_metadata(1, {"panel": "details"})
                    settings_tabs.current_tab = 0
                    settings_tabs.set_meta("selected_panel", "Overview")
                    settings_tabs.tab_changed.connect(_on_settings_tab_changed)
                    var popup := action_menu.get_popup()
                    popup.add_item("Open", 10)
                    popup.add_item("Save", 20)
                    popup.add_check_item("Snap", 30)
                    popup.set_item_metadata(0, {"action": "open"})
                    popup.set_item_metadata(1, {"action": "save"})
                    popup.set_item_metadata(2, {"action": "snap"})
                    action_menu.set_meta("last_action", "")
                    action_menu.set_meta("last_action_id", 0)
                    action_menu.set_meta("snap_enabled", false)
                    popup.id_pressed.connect(_on_action_menu_id_pressed)
                    inventory_list.add_item("Potion")
                    inventory_list.add_item("Elixir")
                    inventory_list.add_item("Key")
                    inventory_list.set_item_metadata(0, {"kind": "potion"})
                    inventory_list.set_item_metadata(1, {"kind": "elixir"})
                    inventory_list.set_item_metadata(2, {"kind": "key"})
                    inventory_list.select(0)
                    inventory_list.set_meta("selected_item", "Potion")
                    inventory_list.item_selected.connect(_on_inventory_item_selected)
                    loadout_list.select_mode = ItemList.SELECT_MULTI
                    loadout_list.add_item("Sword")
                    loadout_list.add_item("Bow")
                    loadout_list.add_item("Shield")
                    loadout_list.set_item_metadata(0, {"slot": "sword"})
                    loadout_list.set_item_metadata(1, {"slot": "bow"})
                    loadout_list.set_item_metadata(2, {"slot": "shield"})
                    loadout_list.select(0, false)
                    loadout_list.set_meta("selected_loadout", _selected_loadout())
                    loadout_list.multi_selected.connect(_on_loadout_multi_selected)
                    _populate_quest_tree()
                    _populate_talent_tree()
                    set_meta("process_ticks", 0)
                    set_meta("physics_ticks", 0)
                    set_meta("save_shortcut_count", 0)
                    set_meta("shift_f4_seen", false)
                    set_meta("joypad_a_count", 0)
                    set_meta("joypad_left_x", 0.0)
                    set_meta("agent_jump_count", 0)
                    set_meta("agent_confirm_count", 0)
                    set_meta("physics_target_3d_hovered", false)
                    set_meta("physics_target_3d_click_count", 0)
                    set_meta("physics_target_3d_drag_pressed", false)
                    set_meta("physics_target_3d_dragged", false)
                    set_meta("physics_target_3d_drag_released", false)
                    hover_target.mouse_entered.connect(_on_hover_target_mouse_entered)
                    hover_target.gui_input.connect(_on_hover_target_gui_input)
                    drag_source.gui_input.connect(_on_drag_source_gui_input)
                    drop_target.gui_input.connect(_on_drop_target_gui_input)
                    wheel_target.gui_input.connect(_on_wheel_target_gui_input)
                    touch_target.gui_input.connect(_on_touch_target_gui_input)
                    physics_target_3d.input_event.connect(_on_physics_target_3d_input_event)
                    physics_target_3d.mouse_entered.connect(_on_physics_target_3d_mouse_entered)
                    show_confirm_button.pressed.connect(_on_show_confirm_pressed)
                    confirm_dialog.confirmed.connect(_on_confirm_dialog_confirmed)
                    confirm_dialog.canceled.connect(_on_confirm_dialog_canceled)
                    _setup_animation_fixture()


                func _setup_animation_fixture() -> void:
                    animated_label.modulate.a = 0.0
                    var animation := Animation.new()
                    animation.length = 1.0
                    var alpha_track := animation.add_track(Animation.TYPE_VALUE)
                    animation.track_set_path(alpha_track, NodePath("AnimatedLabel:modulate:a"))
                    animation.track_insert_key(alpha_track, 0.0, 0.0)
                    animation.track_insert_key(alpha_track, 1.0, 1.0)
                    var library := AnimationLibrary.new()
                    library.add_animation("fade_in", animation)
                    animation_player.add_animation_library("", library)
                    animation_player.assigned_animation = "fade_in"
                    animation_player.speed_scale = 1.0


                func _on_counter_pressed() -> void:
                    count += 1
                    counter_button.text = "Clicked %s" % count


                func _process(_delta: float) -> void:
                    set_meta("process_ticks", int(get_meta("process_ticks", 0)) + 1)


                func _physics_process(_delta: float) -> void:
                    set_meta("physics_ticks", int(get_meta("physics_ticks", 0)) + 1)


                func _input(event: InputEvent) -> void:
                    if event is InputEventKey and event.pressed and not event.echo:
                        if event.keycode == KEY_S and event.ctrl_pressed:
                            set_meta("save_shortcut_count", int(get_meta("save_shortcut_count", 0)) + 1)
                        if event.keycode == KEY_F4 and event.shift_pressed:
                            set_meta("shift_f4_seen", true)
                    elif event is InputEventJoypadButton and event.pressed and event.button_index == JOY_BUTTON_A:
                        set_meta("joypad_a_count", int(get_meta("joypad_a_count", 0)) + 1)
                    elif event is InputEventJoypadMotion and event.axis == JOY_AXIS_LEFT_X:
                        set_meta("joypad_left_x", event.axis_value)
                    if InputMap.has_action("agent_jump") and event.is_action_pressed("agent_jump"):
                        set_meta("agent_jump_count", int(get_meta("agent_jump_count", 0)) + 1)
                    if InputMap.has_action("agent_confirm") and event.is_action_pressed("agent_confirm"):
                        set_meta("agent_confirm_count", int(get_meta("agent_confirm_count", 0)) + 1)


                func _on_name_changed(new_text: String) -> void:
                    echo_label.text = "Hello %s" % new_text


                func _on_accept_terms_toggled(toggled_on: bool) -> void:
                    accept_terms.set_meta("last_toggled", toggled_on)


                func _on_theme_selected(index: int) -> void:
                    theme_select.set_meta("selected_theme", theme_select.get_item_text(index))


                func _on_volume_changed(value: float) -> void:
                    volume_slider.set_meta("volume", value)


                func _on_mode_tab_changed(tab: int) -> void:
                    mode_tabs.set_meta("selected_mode", mode_tabs.get_tab_title(tab))


                func _on_settings_tab_changed(tab: int) -> void:
                    settings_tabs.set_meta("selected_panel", settings_tabs.get_tab_title(tab))


                func _on_action_menu_id_pressed(id: int) -> void:
                    var popup := action_menu.get_popup()
                    var index := -1
                    for item_index in range(popup.get_item_count()):
                        if popup.get_item_id(item_index) == id:
                            index = item_index
                            break
                    if index >= 0:
                        action_menu.set_meta("last_action", popup.get_item_text(index))
                        action_menu.set_meta("last_action_id", id)
                        if popup.is_item_checkable(index):
                            action_menu.set_meta("snap_enabled", popup.is_item_checked(index))


                func _on_inventory_item_selected(index: int) -> void:
                    inventory_list.set_meta("selected_item", inventory_list.get_item_text(index))


                func _on_loadout_multi_selected(_index: int, _selected: bool) -> void:
                    loadout_list.set_meta("selected_loadout", _selected_loadout())


                func _selected_loadout() -> Array:
                    var texts := []
                    for index in loadout_list.get_selected_items():
                        texts.append(loadout_list.get_item_text(index))
                    return texts


                func _populate_quest_tree() -> void:
                    quest_tree.hide_root = true
                    var root_item := quest_tree.create_item()
                    root_item.set_text(0, "Quests")
                    var forest := quest_tree.create_item(root_item)
                    forest.set_text(0, "Forest")
                    forest.set_metadata(0, {"quest": "forest"})
                    var cave := quest_tree.create_item(root_item)
                    cave.set_text(0, "Cave")
                    cave.set_metadata(0, {"quest": "cave"})
                    var boss := quest_tree.create_item(cave)
                    boss.set_text(0, "Boss")
                    boss.set_metadata(0, {"quest": "boss"})
                    cave.collapsed = false
                    quest_tree.set_selected(forest, 0)
                    quest_tree.set_meta("selected_quest", "Forest")
                    quest_tree.item_selected.connect(_on_quest_tree_selected)


                func _populate_talent_tree() -> void:
                    talent_tree.hide_root = true
                    talent_tree.select_mode = Tree.SELECT_MULTI
                    var root_item := talent_tree.create_item()
                    root_item.set_text(0, "Talents")
                    var movement := talent_tree.create_item(root_item)
                    movement.set_text(0, "Movement")
                    var dash := talent_tree.create_item(movement)
                    dash.set_text(0, "Dash")
                    dash.set_metadata(0, {"talent": "dash"})
                    var glide := talent_tree.create_item(movement)
                    glide.set_text(0, "Glide")
                    glide.set_metadata(0, {"talent": "glide"})
                    var wall_jump := talent_tree.create_item(movement)
                    wall_jump.set_text(0, "Wall Jump")
                    wall_jump.set_metadata(0, {"talent": "wall_jump"})
                    movement.collapsed = false
                    dash.select(0)
                    talent_tree.set_meta("selected_talents", _selected_talents())
                    talent_tree.multi_selected.connect(_on_talent_tree_multi_selected)


                func _on_quest_tree_selected() -> void:
                    var selected := quest_tree.get_selected()
                    if selected != null:
                        quest_tree.set_meta("selected_quest", selected.get_text(quest_tree.get_selected_column()))


                func _on_talent_tree_multi_selected(_item: TreeItem, _column: int, _selected: bool) -> void:
                    talent_tree.set_meta("selected_talents", _selected_talents())


                func _selected_talents() -> Array:
                    var texts := []
                    var item := talent_tree.get_next_selected(null)
                    while item != null:
                        for column in range(talent_tree.columns):
                            if item.is_selected(column):
                                texts.append(item.get_text(column))
                        item = talent_tree.get_next_selected(item)
                    return texts


                func _on_hover_target_mouse_entered() -> void:
                    hover_target.set_meta("hovered", true)


                func _on_hover_target_gui_input(event: InputEvent) -> void:
                    if event is InputEventMouseMotion:
                        hover_target.set_meta("hovered", true)


                func _on_drag_source_gui_input(event: InputEvent) -> void:
                    if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
                        drag_source.set_meta("drag_pressed", true)
                    if event is InputEventMouseMotion and (event.button_mask & MOUSE_BUTTON_MASK_LEFT) != 0:
                        drag_source.set_meta("dragged", true)


                func _on_drop_target_gui_input(event: InputEvent) -> void:
                    if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and not event.pressed:
                        drop_target.set_meta("dropped", true)


                func _on_wheel_target_gui_input(event: InputEvent) -> void:
                    if not (event is InputEventMouseButton and event.pressed):
                        return
                    var delta := float(wheel_target.get_meta("wheel_delta_y", 0.0))
                    if event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
                        wheel_target.set_meta("wheel_delta_y", delta + event.factor)
                    elif event.button_index == MOUSE_BUTTON_WHEEL_UP:
                        wheel_target.set_meta("wheel_delta_y", delta - event.factor)


                func _on_touch_target_gui_input(event: InputEvent) -> void:
                    if event is InputEventScreenTouch and event.pressed:
                        touch_target.set_meta("touch_pressed", true)
                        touch_target.set_meta("touch_index", event.index)
                    elif event is InputEventScreenTouch and not event.pressed:
                        touch_target.set_meta("touch_released", true)
                    elif event is InputEventScreenDrag:
                        touch_target.set_meta("touch_dragged", true)
                        touch_target.set_meta("touch_relative", event.relative)


                func _on_physics_target_3d_mouse_entered() -> void:
                    set_meta("physics_target_3d_hovered", true)


                func _on_physics_target_3d_input_event(_camera: Camera3D, event: InputEvent, position: Vector3, _normal: Vector3, _shape_idx: int) -> void:
                    set_meta("physics_target_3d_last_input_position", position)
                    if event is InputEventMouseMotion:
                        set_meta("physics_target_3d_hovered", true)
                        if (event.button_mask & MOUSE_BUTTON_MASK_LEFT) != 0:
                            set_meta("physics_target_3d_dragged", true)
                    elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
                        set_meta("physics_target_3d_drag_pressed", true)
                        set_meta("physics_target_3d_click_count", int(get_meta("physics_target_3d_click_count", 0)) + 1)
                    elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and not event.pressed:
                        set_meta("physics_target_3d_drag_released", true)


                func _on_show_confirm_pressed() -> void:
                    confirm_dialog.set_meta("result", "")
                    confirm_dialog.popup_centered()


                func _on_confirm_dialog_confirmed() -> void:
                    confirm_dialog.set_meta("result", "accepted")


                func _on_confirm_dialog_canceled() -> void:
                    confirm_dialog.set_meta("result", "dismissed")
                """
            ),
            encoding="utf-8",
        )
        (project / "scenes" / "main.tscn").write_text(
            textwrap.dedent(
                """\
                [gd_scene load_steps=5 format=3]

                [ext_resource type="Script" path="res://scripts/main.gd" id="1_main"]
                [ext_resource type="PackedScene" path="res://scenes/secondary.tscn" id="2_secondary"]

                [sub_resource type="RectangleShape2D" id="RectangleShape2D_physics_target"]
                size = Vector2(80, 40)

                [sub_resource type="BoxShape3D" id="BoxShape3D_physics_target"]
                size = Vector3(2, 2, 2)

                [node name="Main" type="Control"]
                layout_mode = 3
                anchors_preset = 15
                anchor_right = 1.0
                anchor_bottom = 1.0
                grow_horizontal = 2
                grow_vertical = 2
                script = ExtResource("1_main")
                metadata/test_id = "main"

                [node name="Title" type="Label" parent="."]
                layout_mode = 0
                offset_left = 24.0
                offset_top = 24.0
                offset_right = 260.0
                offset_bottom = 58.0
                text = "Godot Playwright"
                metadata/test_id = "title"

                [node name="CounterButton" type="Button" parent="."]
                layout_mode = 0
                offset_left = 24.0
                offset_top = 78.0
                offset_right = 172.0
                offset_bottom = 118.0
                text = "Clicked 0"
                metadata/test_id = "counter-button"

                [node name="NameInput" type="LineEdit" parent="."]
                layout_mode = 0
                offset_left = 24.0
                offset_top = 138.0
                offset_right = 260.0
                offset_bottom = 178.0
                placeholder_text = "Name"
                metadata/test_id = "name-input"

                [node name="EchoLabel" type="Label" parent="."]
                layout_mode = 0
                offset_left = 24.0
                offset_top = 194.0
                offset_right = 320.0
                offset_bottom = 228.0
                text = "Hello"
                metadata/test_id = "echo"

                [node name="AcceptTerms" type="CheckBox" parent="."]
                layout_mode = 0
                offset_left = 24.0
                offset_top = 236.0
                offset_right = 260.0
                offset_bottom = 276.0
                text = "Accept terms"
                metadata/last_toggled = false
                metadata/test_id = "accept-terms"

                [node name="ThemeSelect" type="OptionButton" parent="."]
                layout_mode = 0
                offset_left = 24.0
                offset_top = 284.0
                offset_right = 260.0
                offset_bottom = 324.0
                metadata/test_id = "theme-select"

                [node name="VolumeSlider" type="HSlider" parent="."]
                layout_mode = 0
                offset_left = 24.0
                offset_top = 332.0
                offset_right = 260.0
                offset_bottom = 360.0
                min_value = 0.0
                max_value = 100.0
                value = 25.0
                metadata/test_id = "volume-slider"

                [node name="AnimatedLabel" type="Label" parent="."]
                modulate = Color(1, 1, 1, 0)
                layout_mode = 0
                offset_left = 300.0
                offset_top = 332.0
                offset_right = 500.0
                offset_bottom = 360.0
                text = "Animated"
                metadata/test_id = "animated-label"

                [node name="AutomationAnimation" type="AnimationPlayer" parent="."]
                root_node = NodePath("..")
                metadata/test_id = "automation-animation"

                [node name="ModeTabs" type="TabBar" parent="."]
                layout_mode = 0
                offset_left = 24.0
                offset_top = 376.0
                offset_right = 260.0
                offset_bottom = 416.0
                metadata/test_id = "mode-tabs"

                [node name="SettingsTabs" type="TabContainer" parent="."]
                layout_mode = 0
                offset_left = 540.0
                offset_top = 24.0
                offset_right = 740.0
                offset_bottom = 164.0
                metadata/test_id = "settings-tabs"

                [node name="Overview" type="Control" parent="SettingsTabs"]
                layout_mode = 2

                [node name="Details" type="Control" parent="SettingsTabs"]
                layout_mode = 2

                [node name="ActionMenu" type="MenuButton" parent="."]
                layout_mode = 0
                offset_left = 760.0
                offset_top = 24.0
                offset_right = 900.0
                offset_bottom = 64.0
                text = "Actions"
                metadata/test_id = "action-menu"

                [node name="InventoryList" type="ItemList" parent="."]
                layout_mode = 0
                offset_left = 540.0
                offset_top = 184.0
                offset_right = 740.0
                offset_bottom = 304.0
                metadata/test_id = "inventory-list"

                [node name="LoadoutList" type="ItemList" parent="."]
                layout_mode = 0
                offset_left = 760.0
                offset_top = 24.0
                offset_right = 960.0
                offset_bottom = 144.0
                metadata/test_id = "loadout-list"

                [node name="QuestTree" type="Tree" parent="."]
                layout_mode = 0
                offset_left = 760.0
                offset_top = 164.0
                offset_right = 960.0
                offset_bottom = 304.0
                metadata/test_id = "quest-tree"

                [node name="TalentTree" type="Tree" parent="."]
                layout_mode = 0
                offset_left = 980.0
                offset_top = 24.0
                offset_right = 1180.0
                offset_bottom = 184.0
                metadata/test_id = "talent-tree"

                [node name="NextSceneButton" type="Button" parent="."]
                layout_mode = 0
                offset_left = 24.0
                offset_top = 436.0
                offset_right = 172.0
                offset_bottom = 476.0
                text = "Next Scene"
                metadata/target_scene = ExtResource("2_secondary")
                metadata/test_id = "next-scene"

                [node name="HoverTarget" type="ColorRect" parent="."]
                layout_mode = 0
                offset_left = 320.0
                offset_top = 24.0
                offset_right = 420.0
                offset_bottom = 84.0
                mouse_filter = 0
                color = Color(0.2, 0.4, 0.8, 1)
                metadata/hovered = false

                [node name="DragSource" type="ColorRect" parent="."]
                layout_mode = 0
                offset_left = 320.0
                offset_top = 104.0
                offset_right = 380.0
                offset_bottom = 164.0
                mouse_filter = 0
                color = Color(0.8, 0.25, 0.25, 1)
                metadata/drag_pressed = false
                metadata/dragged = false

                [node name="DropTarget" type="ColorRect" parent="."]
                layout_mode = 0
                offset_left = 440.0
                offset_top = 104.0
                offset_right = 500.0
                offset_bottom = 164.0
                mouse_filter = 0
                color = Color(0.2, 0.65, 0.35, 1)
                metadata/dropped = false

                [node name="WheelTarget" type="ColorRect" parent="."]
                layout_mode = 0
                offset_left = 320.0
                offset_top = 184.0
                offset_right = 420.0
                offset_bottom = 244.0
                mouse_filter = 0
                color = Color(0.95, 0.75, 0.25, 1)
                metadata/wheel_delta_y = 0.0

                [node name="TouchTarget" type="ColorRect" parent="."]
                layout_mode = 0
                offset_left = 440.0
                offset_top = 184.0
                offset_right = 500.0
                offset_bottom = 244.0
                mouse_filter = 0
                color = Color(0.6, 0.25, 0.85, 1)
                metadata/touch_pressed = false
                metadata/touch_released = false
                metadata/touch_dragged = false
                metadata/touch_index = -1

                [node name="ShowConfirmButton" type="Button" parent="."]
                layout_mode = 0
                offset_left = 320.0
                offset_top = 264.0
                offset_right = 500.0
                offset_bottom = 304.0
                text = "Show Confirm"
                metadata/test_id = "show-confirm"

                [node name="ConfirmDialog" type="ConfirmationDialog" parent="."]
                title = "Confirm Action"
                initial_position = 2
                size = Vector2i(320, 120)
                visible = false
                dialog_text = "Run the agent action?"
                metadata/result = ""
                metadata/test_id = "confirm-dialog"

                [node name="PhysicsTarget" type="StaticBody2D" parent="." groups=["physics_fixture"]]
                position = Vector2(640, 420)
                collision_layer = 4
                collision_mask = 0
                metadata/test_id = "physics-target"

                [node name="CollisionShape2D" type="CollisionShape2D" parent="PhysicsTarget"]
                shape = SubResource("RectangleShape2D_physics_target")

                [node name="PhysicsTarget3D" type="StaticBody3D" parent="." groups=["physics_fixture_3d"]]
                position = Vector3(0, 0, 0)
                collision_layer = 8
                collision_mask = 0
                metadata/test_id = "physics-target-3d"

                [node name="CollisionShape3D" type="CollisionShape3D" parent="PhysicsTarget3D"]
                shape = SubResource("BoxShape3D_physics_target")

                [node name="AutomationCamera3D" type="Camera3D" parent="."]
                position = Vector3(0, 0, 10)
                current = true
                metadata/test_id = "automation-camera-3d"
                """
            ),
            encoding="utf-8",
        )
        (project / "scripts" / "secondary.gd").write_text(
            textwrap.dedent(
                """\
                extends Control

                @onready var back_button: Button = $BackButton


                func _ready() -> void:
                    back_button.pressed.connect(_on_back_pressed)


                func _on_back_pressed() -> void:
                    get_tree().change_scene_to_file("res://scenes/main.tscn")
                """
            ),
            encoding="utf-8",
        )
        (project / "scenes" / "secondary.tscn").write_text(
            textwrap.dedent(
                """\
                [gd_scene load_steps=2 format=3]

                [ext_resource type="Script" path="res://scripts/secondary.gd" id="1_secondary"]

                [node name="Secondary" type="Control"]
                layout_mode = 3
                anchors_preset = 15
                anchor_right = 1.0
                anchor_bottom = 1.0
                grow_horizontal = 2
                grow_vertical = 2
                script = ExtResource("1_secondary")

                [node name="SecondaryTitle" type="Label" parent="."]
                layout_mode = 0
                offset_left = 24.0
                offset_top = 24.0
                offset_right = 260.0
                offset_bottom = 58.0
                text = "Secondary Scene"

                [node name="BackButton" type="Button" parent="."]
                layout_mode = 0
                offset_left = 24.0
                offset_top = 78.0
                offset_right = 172.0
                offset_bottom = 118.0
                text = "Back"
                """
            ),
            encoding="utf-8",
        )
        return project

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self._tmp.cleanup()


def wait_for_call(locator, method: str, *args, timeout: float = 2.0, predicate=None):
    deadline = time.monotonic() + timeout
    last_value = None
    while True:
        last_value = locator.call(method, *args)
        if predicate is None:
            if last_value:
                return last_value
        elif predicate(last_value):
            return last_value
        if time.monotonic() >= deadline:
            raise AssertionError(f"Timed out waiting for {method}{args!r}; last value was {last_value!r}")
        time.sleep(0.05)


def wait_for_resource(godot, path: str, *, type_hint: str = "", timeout: float = 2.0):
    deadline = time.monotonic() + timeout
    last_error = None
    while True:
        try:
            return godot.resource_inspect(path, type_hint=type_hint)
        except RpcError as exc:
            last_error = exc
        if time.monotonic() >= deadline:
            raise AssertionError(f"Timed out waiting for resource {path!r}; last error was {last_error!r}")
        time.sleep(0.05)


def _write_audio_probe(project: Path) -> None:
    scripts_dir = project / "scripts"
    scenes_dir = project / "scenes"
    scripts_dir.mkdir(exist_ok=True)
    scenes_dir.mkdir(exist_ok=True)
    (scripts_dir / "audio_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            var _probe_result: Dictionary = {}


            func _ready() -> void:
                _setup_audio_bus()
                _probe_result = _run_audio_probe()


            func _setup_audio_bus() -> void:
                AudioServer.add_bus()
                var bus_idx := AudioServer.get_bus_count() - 1
                AudioServer.set_bus_name(bus_idx, "TestBus")
                AudioServer.set_bus_send(bus_idx, "Master")
                AudioServer.set_bus_volume_db(bus_idx, -6.0)
                AudioServer.set_bus_mute(bus_idx, true)


            func _run_audio_probe() -> Dictionary:
                var server_node = get_node_or_null("/root/GodotPlaywright")
                if server_node == null:
                    return {"ok": false, "error": "GodotPlaywright autoload not found"}
                var server = server_node.get_node_or_null("GodotPlaywrightServer")
                if server == null:
                    return {"ok": false, "error": "GodotPlaywrightServer node not found"}
                var rpc_result: Dictionary = server.call("_dispatch", "audio.bus.info", {"bus_name": "TestBus"})
                if not rpc_result.has("ok") or not rpc_result["ok"]:
                    return {"ok": false, "error": "RPC returned error", "rpc_result": rpc_result}
                var bus_info: Dictionary = rpc_result.get("value", {}).get("bus", {})
                var volume_db := float(bus_info.get("volume_db", 0.0))
                var muted := bool(bus_info.get("muted", false))
                var volume_ok := absf(volume_db - (-6.0)) < 0.01
                var muted_ok := muted == true
                var ok := volume_ok and muted_ok
                return {
                    "ok": ok,
                    "volume_db": volume_db,
                    "muted": muted,
                    "volume_ok": volume_ok,
                    "muted_ok": muted_ok,
                    "bus_name": str(bus_info.get("name", "")),
                }


            func get_probe_result() -> Dictionary:
                return _probe_result
            """
        ),
        encoding="utf-8",
    )
    (scenes_dir / "audio_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/audio_probe.gd" id="1_probe"]

            [node name="AudioProbe" type="Node"]
            script = ExtResource("1_probe")
            """
        ),
        encoding="utf-8",
    )


def _write_navigation_probe(project: Path) -> None:
    scripts_dir = project / "scripts"
    scenes_dir = project / "scenes"
    scripts_dir.mkdir(exist_ok=True)
    scenes_dir.mkdir(exist_ok=True)
    (scripts_dir / "navigation_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node3D

            var _probe_result: Dictionary = {}
            var _region: NavigationRegion3D = null


            func _ready() -> void:
                _setup_navigation()
                for _i in range(10):
                    await get_tree().process_frame
                _probe_result = _run_navigation_probe()


            func _setup_navigation() -> void:
                _region = NavigationRegion3D.new()
                var nav_mesh := NavigationMesh.new()
                var vertices := PackedVector3Array([
                    Vector3(-10.0, 0.0, -10.0),
                    Vector3(10.0, 0.0, -10.0),
                    Vector3(10.0, 0.0, 10.0),
                    Vector3(-10.0, 0.0, 10.0),
                ])
                nav_mesh.set_vertices(vertices)
                nav_mesh.add_polygon(PackedInt32Array([0, 1, 2, 3]))
                _region.navigation_mesh = nav_mesh
                add_child(_region)


            func _run_navigation_probe() -> Dictionary:
                var server_node = get_node_or_null("/root/GodotPlaywright")
                if server_node == null:
                    return {"ok": false, "error": "GodotPlaywright autoload not found"}
                var server = server_node.get_node_or_null("GodotPlaywrightServer")
                if server == null:
                    return {"ok": false, "error": "GodotPlaywrightServer node not found"}
                var rpc_result: Dictionary = server.call("_dispatch", "navigation.query_path", {
                    "dimension": 3,
                    "start_x": 0.0, "start_y": 0.0, "start_z": 0.0,
                    "target_x": 5.0, "target_y": 0.0, "target_z": 5.0,
                })
                if not rpc_result.has("ok") or not rpc_result["ok"]:
                    return {"ok": false, "error": "RPC returned error", "rpc_result": rpc_result}
                var path_info: Dictionary = rpc_result.get("value", {}).get("path", {})
                var reachable := bool(path_info.get("reachable", false))
                var point_count := int(path_info.get("point_count", 0))
                var path_length := float(path_info.get("path_length", 0.0))
                var ok := reachable and point_count >= 2
                return {
                    "ok": ok,
                    "reachable": reachable,
                    "point_count": point_count,
                    "path_length": path_length,
                }


            func get_probe_result() -> Dictionary:
                return _probe_result
            """
        ),
        encoding="utf-8",
    )
    (scenes_dir / "navigation_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/navigation_probe.gd" id="1_probe"]

            [node name="NavigationProbe" type="Node3D"]
            script = ExtResource("1_probe")
            """
        ),
        encoding="utf-8",
    )


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class DomainAssertionsAudioTests(unittest.TestCase):
    def test_audio_bus_info_rpc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = init_project(Path(tmp) / "project", name="Audio Probe")
            _write_audio_probe(project)
            project_godot = project / "project.godot"
            project_text = project_godot.read_text(encoding="utf-8")
            project_text = project_text.replace(
                'run/main_scene="res://scenes/main.tscn"',
                'run/main_scene="res://scenes/audio_probe.tscn"',
            )
            project_godot.write_text(project_text, encoding="utf-8")

            with Godot(project, mode="runtime", timeout=20, stdout=None) as godot:
                probe_node = godot.locator("#AudioProbe")
                godot.wait_for_process_frames(3, timeout=5)
                result = probe_node.call("get_probe_result")
                self.assertTrue(result["ok"], f"Audio probe failed: {result}")
                self.assertAlmostEqual(float(result["volume_db"]), -6.0, delta=0.01)
                self.assertTrue(bool(result["muted"]))


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class DomainAssertionsNavigationTests(unittest.TestCase):
    def test_navigation_query_path_rpc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = init_project(Path(tmp) / "project", name="Navigation Probe")
            _write_navigation_probe(project)
            project_godot = project / "project.godot"
            project_text = project_godot.read_text(encoding="utf-8")
            project_text = project_text.replace(
                'run/main_scene="res://scenes/main.tscn"',
                'run/main_scene="res://scenes/navigation_probe.tscn"',
            )
            project_godot.write_text(project_text, encoding="utf-8")

            with Godot(project, mode="runtime", timeout=20, stdout=None) as godot:
                probe_node = godot.locator("#NavigationProbe")
                godot.wait_for_process_frames(5, timeout=5)
                result = probe_node.call("get_probe_result")
                self.assertTrue(result["ok"], f"Navigation probe failed: {result}")
                self.assertTrue(bool(result["reachable"]))
                self.assertGreaterEqual(int(result["point_count"]), 2)
