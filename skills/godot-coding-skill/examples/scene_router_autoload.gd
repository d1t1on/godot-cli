class_name SceneRouter
extends Node

signal transition_started(path: String)
signal transition_failed(path: String, message: String)
signal transition_finished(path: String)

var _busy: bool = false

func goto_scene(path: String) -> void:
    if _busy:
        return
    if not path.begins_with("res://"):
        transition_failed.emit(path, "Only res:// paths are allowed")
        return

    _busy = true
    transition_started.emit(path)

    await get_tree().process_frame
    var error := get_tree().change_scene_to_file(path)
    if error != OK:
        _busy = false
        transition_failed.emit(path, error_string(error))
        return

    await get_tree().process_frame
    _busy = false
    transition_finished.emit(path)
