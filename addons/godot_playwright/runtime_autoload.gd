extends Node

const ServerScript = preload("res://addons/godot_playwright/godot_playwright_server.gd")

var _server: Node = null


func _ready() -> void:
	_server = ServerScript.new()
	_server.name = "GodotPlaywrightServer"
	add_child(_server)


func _exit_tree() -> void:
	if is_instance_valid(_server):
		_server.shutdown()
