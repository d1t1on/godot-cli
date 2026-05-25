extends Control

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
	var popup := action_menu.get_popup()
	popup.add_item("Open", 10)
	popup.add_item("Save", 20)
	popup.add_check_item("Snap", 30)
	popup.set_item_metadata(0, {"action": "open"})
	popup.set_item_metadata(1, {"action": "save"})
	popup.set_item_metadata(2, {"action": "snap"})
	action_menu.set_meta("last_action", "")
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
	_populate_quest_tree()
	set_meta("save_shortcut_count", 0)
	set_meta("shift_f4_seen", false)
	set_meta("joypad_a_count", 0)
	set_meta("joypad_left_x", 0.0)
	set_meta("agent_jump_count", 0)
	set_meta("agent_confirm_count", 0)
	next_scene_button.pressed.connect(_on_next_scene_pressed)
	touch_target.gui_input.connect(_on_touch_target_gui_input)
	show_confirm_button.pressed.connect(_on_show_confirm_pressed)
	confirm_dialog.confirmed.connect(_on_confirm_dialog_confirmed)
	confirm_dialog.canceled.connect(_on_confirm_dialog_canceled)


func _on_counter_pressed() -> void:
	count += 1
	counter_button.text = "Clicked %s" % count


func _on_name_changed(new_text: String) -> void:
	echo_label.text = "Hello %s" % new_text


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


func _on_accept_terms_toggled(toggled_on: bool) -> void:
	accept_terms.set_meta("last_toggled", toggled_on)


func _on_theme_selected(index: int) -> void:
	theme_select.set_meta("selected_theme", theme_select.get_item_text(index))


func _on_volume_changed(value: float) -> void:
	volume_slider.set_meta("volume", value)


func _on_mode_tab_changed(tab: int) -> void:
	mode_tabs.set_meta("selected_mode", mode_tabs.get_tab_title(tab))


func _on_action_menu_id_pressed(id: int) -> void:
	var popup := action_menu.get_popup()
	for index in range(popup.get_item_count()):
		if popup.get_item_id(index) == id:
			action_menu.set_meta("last_action", popup.get_item_text(index))
			if popup.is_item_checkable(index):
				action_menu.set_meta("snap_enabled", popup.is_item_checked(index))
			return


func _on_inventory_item_selected(index: int) -> void:
	inventory_list.set_meta("selected_item", inventory_list.get_item_text(index))


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


func _on_quest_tree_selected() -> void:
	var selected := quest_tree.get_selected()
	if selected != null:
		quest_tree.set_meta("selected_quest", selected.get_text(quest_tree.get_selected_column()))


func _on_next_scene_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/secondary.tscn")


func _on_touch_target_gui_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch and event.pressed:
		touch_target.set_meta("touch_pressed", true)
		touch_target.set_meta("touch_index", event.index)
	elif event is InputEventScreenTouch and not event.pressed:
		touch_target.set_meta("touch_released", true)
	elif event is InputEventScreenDrag:
		touch_target.set_meta("touch_dragged", true)
		touch_target.set_meta("touch_relative", event.relative)


func _on_show_confirm_pressed() -> void:
	confirm_dialog.set_meta("result", "")
	confirm_dialog.popup_centered()


func _on_confirm_dialog_confirmed() -> void:
	confirm_dialog.set_meta("result", "accepted")


func _on_confirm_dialog_canceled() -> void:
	confirm_dialog.set_meta("result", "dismissed")
