@tool
extends EditorPlugin

const ServerScript = preload("res://addons/godot_playwright/godot_playwright_server.gd")

var _server: Node = null


func _enter_tree() -> void:
	_server = ServerScript.new()
	_server.name = "GodotPlaywrightServer"
	_server.editor_interface = get_editor_interface()
	_server.editor_plugin = self
	add_child(_server)


func _exit_tree() -> void:
	if is_instance_valid(_server):
		_server.shutdown()
		_server.queue_free()
	_server = null
