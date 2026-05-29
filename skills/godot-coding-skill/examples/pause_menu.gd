class_name PauseMenu
extends Control

signal resume_requested
signal settings_requested
signal quit_requested

@onready var _resume_button: Button = %ResumeButton
@onready var _settings_button: Button = %SettingsButton
@onready var _quit_button: Button = %QuitButton

func _ready() -> void:
    set_meta("test_id", "pause-menu")
    _resume_button.set_meta("test_id", "pause-resume")
    _settings_button.set_meta("test_id", "pause-settings")
    _quit_button.set_meta("test_id", "pause-quit")

    _resume_button.pressed.connect(_on_resume_button_pressed)
    _settings_button.pressed.connect(_on_settings_button_pressed)
    _quit_button.pressed.connect(_on_quit_button_pressed)

func _on_resume_button_pressed() -> void:
    resume_requested.emit()

func _on_settings_button_pressed() -> void:
    settings_requested.emit()

func _on_quit_button_pressed() -> void:
    quit_requested.emit()
