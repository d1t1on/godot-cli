from __future__ import annotations

import re
from pathlib import Path

from .install import install_addon


class ProjectError(RuntimeError):
    pass


def init_project(
    project_path: str | Path,
    *,
    name: str = "Godot Playwright Project",
    force: bool = False,
    install: bool = True,
) -> Path:
    project = Path(project_path).expanduser().resolve()
    if project.exists() and not project.is_dir():
        raise ProjectError(f"Project path exists and is not a directory: {project}")
    if project.exists() and any(project.iterdir()) and not force:
        raise ProjectError(f"Project directory is not empty: {project}")

    (project / "scenes").mkdir(parents=True, exist_ok=True)
    (project / "scripts").mkdir(parents=True, exist_ok=True)

    (project / "project.godot").write_text(_project_godot(name), encoding="utf-8")
    (project / "scripts" / "main.gd").write_text(MAIN_GD, encoding="utf-8")
    (project / "scripts" / "secondary.gd").write_text(SECONDARY_GD, encoding="utf-8")
    (project / "scenes" / "main.tscn").write_text(MAIN_TSCN, encoding="utf-8")
    (project / "scenes" / "secondary.tscn").write_text(SECONDARY_TSCN, encoding="utf-8")

    if install:
        install_addon(project, enable=True, autoload=True)
    return project


def slug_name(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_ -]+", "", value).strip()
    return slug or "Godot Playwright Project"


def _project_godot(name: str) -> str:
    safe_name = slug_name(name).replace('"', "'")
    return f"""config_version=5

[application]

config/name="{safe_name}"
run/main_scene="res://scenes/main.tscn"
config/features=PackedStringArray("4.6")
"""


MAIN_GD = """extends Control

var count := 0

@onready var counter_button: Button = $CounterButton
@onready var name_input: LineEdit = $NameInput
@onready var echo_label: Label = $EchoLabel
@onready var accept_terms: CheckBox = $AcceptTerms
@onready var theme_select: OptionButton = $ThemeSelect
@onready var volume_slider: HSlider = $VolumeSlider
@onready var mode_tabs: TabBar = $ModeTabs
@onready var action_menu: MenuButton = $ActionMenu
@onready var inventory_list: ItemList = $InventoryList
@onready var quest_tree: Tree = $QuestTree
@onready var next_scene_button: Button = $NextSceneButton
@onready var touch_target: ColorRect = $TouchTarget
@onready var show_confirm_button: Button = $ShowConfirmButton
@onready var confirm_dialog: ConfirmationDialog = $ConfirmDialog


func _ready() -> void:
\tcounter_button.pressed.connect(_on_counter_pressed)
\tname_input.text_changed.connect(_on_name_changed)
\taccept_terms.toggled.connect(_on_accept_terms_toggled)
\ttheme_select.add_item("Arcade", 10)
\ttheme_select.add_item("Story", 20)
\ttheme_select.add_item("Simulation", 30)
\ttheme_select.select(0)
\ttheme_select.set_meta("selected_theme", "Arcade")
\ttheme_select.item_selected.connect(_on_theme_selected)
\tvolume_slider.set_meta("volume", volume_slider.value)
\tvolume_slider.value_changed.connect(_on_volume_changed)
\tmode_tabs.add_tab("General")
\tmode_tabs.add_tab("Advanced")
\tmode_tabs.add_tab("Telemetry")
\tmode_tabs.set_tab_metadata(0, {"mode": "general"})
\tmode_tabs.set_tab_metadata(1, {"mode": "advanced"})
\tmode_tabs.set_tab_metadata(2, {"mode": "telemetry"})
\tmode_tabs.current_tab = 0
\tmode_tabs.set_meta("selected_mode", "General")
\tmode_tabs.tab_changed.connect(_on_mode_tab_changed)
\tvar popup := action_menu.get_popup()
\tpopup.add_item("Open", 10)
\tpopup.add_item("Save", 20)
\tpopup.add_check_item("Snap", 30)
\tpopup.set_item_metadata(0, {"action": "open"})
\tpopup.set_item_metadata(1, {"action": "save"})
\tpopup.set_item_metadata(2, {"action": "snap"})
\taction_menu.set_meta("last_action", "")
\taction_menu.set_meta("snap_enabled", false)
\tpopup.id_pressed.connect(_on_action_menu_id_pressed)
\tinventory_list.add_item("Potion")
\tinventory_list.add_item("Elixir")
\tinventory_list.add_item("Key")
\tinventory_list.set_item_metadata(0, {"kind": "potion"})
\tinventory_list.set_item_metadata(1, {"kind": "elixir"})
\tinventory_list.set_item_metadata(2, {"kind": "key"})
\tinventory_list.select(0)
\tinventory_list.set_meta("selected_item", "Potion")
\tinventory_list.item_selected.connect(_on_inventory_item_selected)
\t_populate_quest_tree()
\tset_meta("save_shortcut_count", 0)
\tset_meta("shift_f4_seen", false)
\tset_meta("joypad_a_count", 0)
\tset_meta("joypad_left_x", 0.0)
\tset_meta("agent_jump_count", 0)
\tset_meta("agent_confirm_count", 0)
\tnext_scene_button.pressed.connect(_on_next_scene_pressed)
\ttouch_target.gui_input.connect(_on_touch_target_gui_input)
\tshow_confirm_button.pressed.connect(_on_show_confirm_pressed)
\tconfirm_dialog.confirmed.connect(_on_confirm_dialog_confirmed)
\tconfirm_dialog.canceled.connect(_on_confirm_dialog_canceled)


func _on_counter_pressed() -> void:
\tcount += 1
\tcounter_button.text = "Clicked %s" % count


func _on_name_changed(new_text: String) -> void:
\techo_label.text = "Hello %s" % new_text


func _input(event: InputEvent) -> void:
\tif event is InputEventKey and event.pressed and not event.echo:
\t\tif event.keycode == KEY_S and event.ctrl_pressed:
\t\t\tset_meta("save_shortcut_count", int(get_meta("save_shortcut_count", 0)) + 1)
\t\tif event.keycode == KEY_F4 and event.shift_pressed:
\t\t\tset_meta("shift_f4_seen", true)
\telif event is InputEventJoypadButton and event.pressed and event.button_index == JOY_BUTTON_A:
\t\tset_meta("joypad_a_count", int(get_meta("joypad_a_count", 0)) + 1)
\telif event is InputEventJoypadMotion and event.axis == JOY_AXIS_LEFT_X:
\t\tset_meta("joypad_left_x", event.axis_value)
\tif InputMap.has_action("agent_jump") and event.is_action_pressed("agent_jump"):
\t\tset_meta("agent_jump_count", int(get_meta("agent_jump_count", 0)) + 1)
\tif InputMap.has_action("agent_confirm") and event.is_action_pressed("agent_confirm"):
\t\tset_meta("agent_confirm_count", int(get_meta("agent_confirm_count", 0)) + 1)


func _on_accept_terms_toggled(toggled_on: bool) -> void:
\taccept_terms.set_meta("last_toggled", toggled_on)


func _on_theme_selected(index: int) -> void:
\ttheme_select.set_meta("selected_theme", theme_select.get_item_text(index))


func _on_volume_changed(value: float) -> void:
\tvolume_slider.set_meta("volume", value)


func _on_mode_tab_changed(tab: int) -> void:
\tmode_tabs.set_meta("selected_mode", mode_tabs.get_tab_title(tab))


func _on_action_menu_id_pressed(id: int) -> void:
\tvar popup := action_menu.get_popup()
\tfor index in range(popup.get_item_count()):
\t\tif popup.get_item_id(index) == id:
\t\t\taction_menu.set_meta("last_action", popup.get_item_text(index))
\t\t\tif popup.is_item_checkable(index):
\t\t\t\taction_menu.set_meta("snap_enabled", popup.is_item_checked(index))
\t\t\treturn


func _on_inventory_item_selected(index: int) -> void:
\tinventory_list.set_meta("selected_item", inventory_list.get_item_text(index))


func _populate_quest_tree() -> void:
\tquest_tree.hide_root = true
\tvar root_item := quest_tree.create_item()
\troot_item.set_text(0, "Quests")
\tvar forest := quest_tree.create_item(root_item)
\tforest.set_text(0, "Forest")
\tforest.set_metadata(0, {"quest": "forest"})
\tvar cave := quest_tree.create_item(root_item)
\tcave.set_text(0, "Cave")
\tcave.set_metadata(0, {"quest": "cave"})
\tvar boss := quest_tree.create_item(cave)
\tboss.set_text(0, "Boss")
\tboss.set_metadata(0, {"quest": "boss"})
\tcave.collapsed = false
\tquest_tree.set_selected(forest, 0)
\tquest_tree.set_meta("selected_quest", "Forest")
\tquest_tree.item_selected.connect(_on_quest_tree_selected)


func _on_quest_tree_selected() -> void:
\tvar selected := quest_tree.get_selected()
\tif selected != null:
\t\tquest_tree.set_meta("selected_quest", selected.get_text(quest_tree.get_selected_column()))


func _on_next_scene_pressed() -> void:
\tget_tree().change_scene_to_file("res://scenes/secondary.tscn")


func _on_touch_target_gui_input(event: InputEvent) -> void:
\tif event is InputEventScreenTouch and event.pressed:
\t\ttouch_target.set_meta("touch_pressed", true)
\t\ttouch_target.set_meta("touch_index", event.index)
\telif event is InputEventScreenTouch and not event.pressed:
\t\ttouch_target.set_meta("touch_released", true)
\telif event is InputEventScreenDrag:
\t\ttouch_target.set_meta("touch_dragged", true)
\t\ttouch_target.set_meta("touch_relative", event.relative)


func _on_show_confirm_pressed() -> void:
\tconfirm_dialog.set_meta("result", "")
\tconfirm_dialog.popup_centered()


func _on_confirm_dialog_confirmed() -> void:
\tconfirm_dialog.set_meta("result", "accepted")


func _on_confirm_dialog_canceled() -> void:
\tconfirm_dialog.set_meta("result", "dismissed")
"""


SECONDARY_GD = """extends Control

@onready var back_button: Button = $BackButton


func _ready() -> void:
\tback_button.pressed.connect(_on_back_pressed)


func _on_back_pressed() -> void:
\tget_tree().change_scene_to_file("res://scenes/main.tscn")
"""


MAIN_TSCN = """[gd_scene load_steps=3 format=3]

[ext_resource type="Script" path="res://scripts/main.gd" id="1_main"]
[ext_resource type="PackedScene" path="res://scenes/secondary.tscn" id="2_secondary"]

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

[node name="ModeTabs" type="TabBar" parent="."]
layout_mode = 0
offset_left = 24.0
offset_top = 376.0
offset_right = 260.0
offset_bottom = 416.0
metadata/test_id = "mode-tabs"

[node name="ActionMenu" type="MenuButton" parent="."]
layout_mode = 0
offset_left = 320.0
offset_top = 324.0
offset_right = 500.0
offset_bottom = 364.0
text = "Actions"
metadata/test_id = "action-menu"

[node name="InventoryList" type="ItemList" parent="."]
layout_mode = 0
offset_left = 320.0
offset_top = 24.0
offset_right = 500.0
offset_bottom = 144.0
metadata/test_id = "inventory-list"

[node name="QuestTree" type="Tree" parent="."]
layout_mode = 0
offset_left = 320.0
offset_top = 164.0
offset_right = 500.0
offset_bottom = 304.0
metadata/test_id = "quest-tree"

[node name="TouchTarget" type="ColorRect" parent="."]
layout_mode = 0
offset_left = 320.0
offset_top = 376.0
offset_right = 380.0
offset_bottom = 416.0
mouse_filter = 0
color = Color(0.6, 0.25, 0.85, 1)
metadata/touch_pressed = false
metadata/touch_released = false
metadata/touch_dragged = false
metadata/touch_index = -1
metadata/test_id = "touch-target"

[node name="ShowConfirmButton" type="Button" parent="."]
layout_mode = 0
offset_left = 390.0
offset_top = 376.0
offset_right = 500.0
offset_bottom = 416.0
text = "Show Confirm"
metadata/test_id = "show-confirm"

[node name="NextSceneButton" type="Button" parent="."]
layout_mode = 0
offset_left = 24.0
offset_top = 436.0
offset_right = 172.0
offset_bottom = 476.0
text = "Next Scene"
metadata/target_scene = ExtResource("2_secondary")
metadata/test_id = "next-scene"

[node name="ConfirmDialog" type="ConfirmationDialog" parent="."]
title = "Confirm Action"
initial_position = 2
size = Vector2i(320, 120)
visible = false
dialog_text = "Run the agent action?"
metadata/result = ""
metadata/test_id = "confirm-dialog"
"""


SECONDARY_TSCN = """[gd_scene load_steps=2 format=3]

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
