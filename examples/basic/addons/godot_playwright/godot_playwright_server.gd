@tool
extends Node

var editor_interface = null
var editor_plugin = null
var bind_host := "127.0.0.1"
var port := 9777
var strict_port := false

var _server := TCPServer.new()
var _connections: Array = []
var _started_ms := 0
var _last_error := ""
var _trace_enabled := false
var _trace_events: Array = []
var _trace_max_events := 1000
var _signal_watches := {}
var _signal_events: Array = []
var _next_signal_watch_id := 1
var _signal_max_events := 1000
var _last_mouse_position := Vector2.ZERO
var _last_touch_positions := {}
var _last_hovered_control = null
var _last_hovered_collision_3d: CollisionObject3D = null
var _editor_filesystem_selected_path := ""
var _frame_step_active := false
var _frame_step_pause_pending := false
var _frame_step_counter := "process_frames"
var _frame_step_target := 0


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_started_ms = Time.get_ticks_msec()
	var env_host := OS.get_environment("GODOT_PLAYWRIGHT_HOST")
	var env_port := OS.get_environment("GODOT_PLAYWRIGHT_PORT")
	var env_strict_port := OS.get_environment("GODOT_PLAYWRIGHT_STRICT_PORT")
	if env_host != "":
		bind_host = env_host
	if env_port.is_valid_int():
		port = int(env_port)
	strict_port = env_strict_port in ["1", "true", "TRUE", "yes", "YES", "on", "ON"]
	start()
	set_process(true)
	set_physics_process(true)


func start() -> bool:
	if _server.is_listening():
		return true
	var error := _server.listen(port, bind_host)
	if error != OK:
		var requested_port := port
		if not strict_port and requested_port != 0:
			var fallback_error := _server.listen(0, bind_host)
			if fallback_error == OK:
				port = _server.get_local_port()
				_last_error = "Failed to listen on %s:%s: %s; fell back to %s:%s" % [bind_host, requested_port, error, bind_host, port]
				push_warning(_last_error)
				print("Godot Playwright listening on http://%s:%s" % [bind_host, port])
				return true
		_last_error = "Failed to listen on %s:%s: %s" % [bind_host, port, error]
		push_error(_last_error)
		return false
	port = _server.get_local_port()
	print("Godot Playwright listening on http://%s:%s" % [bind_host, port])
	return true


func shutdown() -> void:
	_disconnect_all_signal_watches()
	for connection in _connections:
		var peer: StreamPeerTCP = connection.get("peer")
		if peer != null:
			peer.disconnect_from_host()
	_connections.clear()
	if _server.is_listening():
		_server.stop()


func _process(_delta: float) -> void:
	_update_runtime_frame_step()
	if not _server.is_listening():
		return
	while _server.is_connection_available():
		var peer := _server.take_connection()
		if peer == null:
			break
		peer.set_no_delay(true)
		_connections.append({
			"peer": peer,
			"buffer": PackedByteArray(),
			"created_ms": Time.get_ticks_msec(),
		})

	for index in range(_connections.size() - 1, -1, -1):
		if _poll_connection(_connections[index]):
			_connections.remove_at(index)


func _poll_connection(connection: Dictionary) -> bool:
	var peer: StreamPeerTCP = connection.get("peer")
	if peer == null:
		return true
	peer.poll()
	if peer.get_status() == StreamPeerSocket.STATUS_ERROR:
		peer.disconnect_from_host()
		return true

	var available := peer.get_available_bytes()
	if available > 0:
		var data_result := peer.get_partial_data(available)
		if data_result[0] == OK:
			var buffer: PackedByteArray = connection["buffer"]
			buffer.append_array(data_result[1])
			connection["buffer"] = buffer

	var buffer: PackedByteArray = connection["buffer"]
	if _request_is_complete(buffer):
		var response := _handle_raw_request(buffer)
		peer.put_data(response.to_utf8_buffer())
		peer.disconnect_from_host()
		return true

	if Time.get_ticks_msec() - int(connection.get("created_ms", 0)) > 10000:
		peer.disconnect_from_host()
		return true
	return false


func _physics_process(_delta: float) -> void:
	_update_runtime_frame_step()


func _request_is_complete(buffer: PackedByteArray) -> bool:
	var text := buffer.get_string_from_utf8()
	var split := text.find("\r\n\r\n")
	if split == -1:
		return false
	var content_length := _content_length_from_headers(text.substr(0, split))
	return buffer.size() >= split + 4 + content_length


func _content_length_from_headers(header_text: String) -> int:
	for line in header_text.split("\r\n"):
		var lower := line.to_lower()
		if lower.begins_with("content-length:"):
			return int(line.substr(line.find(":") + 1).strip_edges())
	return 0


func _handle_raw_request(buffer: PackedByteArray) -> String:
	var text := buffer.get_string_from_utf8()
	var split := text.find("\r\n\r\n")
	if split == -1:
		return _http_response(400, {"error": "Malformed HTTP request"})

	var header_text := text.substr(0, split)
	var request_line := header_text.split("\r\n")[0]
	var request_parts := request_line.split(" ")
	if request_parts.size() < 2:
		return _http_response(400, {"error": "Malformed HTTP request line"})

	var method := String(request_parts[0])
	var path := String(request_parts[1])
	var content_length := _content_length_from_headers(header_text)
	var body := ""
	if content_length > 0:
		body = text.substr(split + 4, content_length)

	if method == "GET" and path == "/health":
		return _http_response(200, _health_payload())
	if method == "POST" and path == "/rpc":
		return _http_response(200, _handle_rpc(body))
	return _http_response(404, {"error": "Not found"})


func _http_response(status: int, payload: Variant) -> String:
	var body := JSON.stringify(payload)
	var reason := "OK"
	if status == 400:
		reason = "Bad Request"
	elif status == 404:
		reason = "Not Found"
	elif status >= 500:
		reason = "Internal Server Error"
	return (
		"HTTP/1.1 %s %s\r\n" % [status, reason]
		+ "Content-Type: application/json; charset=utf-8\r\n"
		+ "Access-Control-Allow-Origin: *\r\n"
		+ "Connection: close\r\n"
		+ "Content-Length: %s\r\n\r\n" % body.to_utf8_buffer().size()
		+ body
	)


func _handle_rpc(body: String) -> Dictionary:
	var payload = JSON.parse_string(body)
	if typeof(payload) != TYPE_DICTIONARY:
		return _rpc_error(null, -32700, "Invalid JSON-RPC payload")
	var request_id = payload.get("id", null)
	var method := String(payload.get("method", ""))
	var params = payload.get("params", {})
	if typeof(params) != TYPE_DICTIONARY:
		return _rpc_error(request_id, -32602, "params must be an object")

	var started_ms := Time.get_ticks_msec()
	var outcome := _dispatch(method, params)
	_record_event("rpc", {
		"method": method,
		"ok": outcome.get("ok", false),
		"duration_ms": Time.get_ticks_msec() - started_ms,
	})
	if outcome.get("ok", false):
		return {"jsonrpc": "2.0", "id": request_id, "result": outcome.get("value")}
	return _rpc_error(
		request_id,
		int(outcome.get("code", -32000)),
		String(outcome.get("message", "Unknown error")),
		outcome.get("data", null)
	)


func _rpc_error(request_id: Variant, code: int, message: String, data: Variant = null) -> Dictionary:
	var error := {"code": code, "message": message}
	if data != null:
		error["data"] = data
	return {"jsonrpc": "2.0", "id": request_id, "error": error}


func _ok(value: Variant = null) -> Dictionary:
	return {"ok": true, "value": value}


func _fail(message: String, code: int = -32000, data: Variant = null) -> Dictionary:
	return {"ok": false, "code": code, "message": message, "data": data}


func _dispatch(method: String, params: Dictionary) -> Dictionary:
	match method:
		"protocol.describe":
			return _rpc_protocol_describe(params)
		"engine.info":
			return _ok(_engine_info())
		"runtime.clock":
			return _ok(_runtime_clock())
		"runtime.pause":
			return _rpc_runtime_pause()
		"runtime.resume":
			return _rpc_runtime_resume()
		"runtime.step_frames":
			return _rpc_runtime_step_frames(params)
		"runtime.sample_frames":
			return _rpc_runtime_sample_frames(params)
		"runtime.evaluate":
			return _rpc_runtime_evaluate(params)
		"tree.snapshot":
			return _rpc_tree_snapshot(params)
		"node.find":
			return _rpc_node_find(params)
		"node.describe":
			return _rpc_node_describe(params)
		"node.state":
			return _rpc_node_state(params)
		"node.bounds":
			return _rpc_node_bounds(params)
		"node.click":
			return _rpc_node_click(params)
		"node.dialog":
			return _rpc_node_dialog(params)
		"node.accept_dialog":
			return _rpc_node_accept_dialog(params)
		"node.dismiss_dialog":
			return _rpc_node_dismiss_dialog(params)
		"node.focus":
			return _rpc_node_focus(params)
		"node.fill":
			return _rpc_node_fill(params)
		"node.get_property":
			return _rpc_node_get_property(params)
		"node.get_properties":
			return _rpc_node_get_properties(params)
		"node.set_property":
			return _rpc_node_set_property(params)
		"node.set_properties":
			return _rpc_node_set_properties(params)
		"node.set_all_properties":
			return _rpc_node_set_all_properties(params)
		"node.attach_script":
			return _rpc_node_attach_script(params)
		"node.detach_script":
			return _rpc_node_detach_script(params)
		"node.set_value":
			return _rpc_node_set_value(params)
		"node.set_checked":
			return _rpc_node_set_checked(params)
		"node.select_option":
			return _rpc_node_select_option(params)
		"node.select_tab":
			return _rpc_node_select_tab(params)
		"node.menu_items":
			return _rpc_node_menu_items(params)
		"node.select_menu_item":
			return _rpc_node_select_menu_item(params)
		"node.select_item":
			return _rpc_node_select_item(params)
		"node.select_tree_item":
			return _rpc_node_select_tree_item(params)
		"node.call":
			return _rpc_node_call(params)
		"node.call_all":
			return _rpc_node_call_all(params)
		"node.evaluate":
			return _rpc_node_evaluate(params)
		"node.evaluate_all":
			return _rpc_node_evaluate_all(params)
		"animation.describe":
			return _rpc_animation_describe(params)
		"animation.play":
			return _rpc_animation_play(params)
		"animation.stop":
			return _rpc_animation_stop(params)
		"animation.pause":
			return _rpc_animation_pause(params)
		"animation.seek":
			return _rpc_animation_seek(params)
		"animation.advance":
			return _rpc_animation_advance(params)
		"physics2d.point":
			return _rpc_physics2d_point(params)
		"physics2d.ray":
			return _rpc_physics2d_ray(params)
		"physics3d.point":
			return _rpc_physics3d_point(params)
		"physics3d.ray":
			return _rpc_physics3d_ray(params)
		"camera3d.ray":
			return _rpc_camera3d_ray(params)
		"camera3d.pick":
			return _rpc_camera3d_pick(params)
		"node.class.describe":
			return _rpc_node_class_describe(params)
		"node.classes":
			return _rpc_node_classes(params)
		"node.create":
			return _rpc_node_create(params)
		"node.create_tree":
			return _rpc_node_create_tree(params)
		"node.instantiate_scene":
			return _rpc_node_instantiate_scene(params)
		"node.save_as_scene":
			return _rpc_node_save_as_scene(params)
		"node.metadata":
			return _rpc_node_metadata(params)
		"node.set_metadata":
			return _rpc_node_set_metadata(params)
		"node.remove_metadata":
			return _rpc_node_remove_metadata(params)
		"node.groups":
			return _rpc_node_groups(params)
		"node.add_group":
			return _rpc_node_add_group(params)
		"node.remove_group":
			return _rpc_node_remove_group(params)
		"node.reparent":
			return _rpc_node_reparent(params)
		"node.move":
			return _rpc_node_move(params)
		"node.duplicate":
			return _rpc_node_duplicate(params)
		"node.delete":
			return _rpc_node_delete(params)
		"scene.current":
			return _rpc_scene_current()
		"scene.files":
			return _rpc_scene_files(params)
		"scene.file.describe":
			return _rpc_scene_file_describe(params)
		"scene.change":
			return _rpc_scene_change(params)
		"scene.reload":
			return _rpc_scene_reload()
		"scene.new":
			return _rpc_scene_new(params)
		"scene.open":
			return _rpc_scene_open(params)
		"scene.save":
			return _rpc_scene_save(params)
		"editor.play":
			return _rpc_editor_play(params)
		"editor.stop":
			return _rpc_editor_stop()
		"editor.status":
			return _rpc_editor_status()
		"editor.ui.status":
			return _rpc_editor_ui_status()
		"editor.ui.switch_main_screen":
			return _rpc_editor_ui_switch_main_screen(params)
		"editor.ui.hide_bottom_panel":
			return _rpc_editor_ui_hide_bottom_panel()
		"editor.history":
			return _rpc_editor_history(params)
		"editor.undo":
			return _rpc_editor_undo(params)
		"editor.redo":
			return _rpc_editor_redo(params)
		"editor.selection.get":
			return _rpc_editor_selection_get()
		"editor.selection.set":
			return _rpc_editor_selection_set(params)
		"editor.inspect":
			return _rpc_editor_inspect(params)
		"editor.inspector.describe":
			return _rpc_editor_inspector_describe(params)
		"editor.inspector.get_property":
			return _rpc_editor_inspector_get_property(params)
		"editor.inspector.set_property":
			return _rpc_editor_inspector_set_property(params)
		"editor.inspector.set_properties":
			return _rpc_editor_inspector_set_properties(params)
		"editor.script.open":
			return _rpc_editor_script_open(params)
		"editor.script.status":
			return _rpc_editor_script_status()
		"editor.script.describe":
			return _rpc_editor_script_describe(params)
		"script.file.describe":
			return _rpc_script_file_describe(params)
		"script.classes":
			return _rpc_script_classes(params)
		"editor.filesystem.scan":
			return _rpc_editor_filesystem_scan(params)
		"editor.filesystem.describe":
			return _rpc_editor_filesystem_describe(params)
		"editor.filesystem.find":
			return _rpc_editor_filesystem_find(params)
		"editor.filesystem.select":
			return _rpc_editor_filesystem_select(params)
		"editor.filesystem.open":
			return _rpc_editor_filesystem_open(params)
		"input.actions":
			return _rpc_input_actions(params)
		"input.action.describe":
			return _rpc_input_action_describe(params)
		"input.action.configure":
			return _rpc_input_action_configure(params)
		"input.action.erase":
			return _rpc_input_action_erase(params)
		"input.action":
			return _rpc_input_action(params)
		"input.key":
			return _rpc_input_key(params)
		"input.text":
			return _rpc_input_text(params)
		"input.mouse":
			return _rpc_input_mouse(params)
		"input.touch":
			return _rpc_input_touch(params)
		"input.joypad":
			return _rpc_input_joypad(params)
		"viewport.info":
			return _rpc_viewport_info()
		"viewport.set_size":
			return _rpc_viewport_set_size(params)
		"viewport.screenshot":
			return _rpc_viewport_screenshot(params)
		"fs.exists":
			return _rpc_fs_exists(params)
		"fs.info":
			return _rpc_fs_info(params)
		"fs.read_text":
			return _rpc_fs_read_text(params)
		"fs.write_text":
			return _rpc_fs_write_text(params)
		"fs.replace_text":
			return _rpc_fs_replace_text(params)
		"fs.replace_text_many":
			return _rpc_fs_replace_text_many(params)
		"fs.read_bytes":
			return _rpc_fs_read_bytes(params)
		"fs.write_bytes":
			return _rpc_fs_write_bytes(params)
		"fs.mkdir":
			return _rpc_fs_mkdir(params)
		"fs.list":
			return _rpc_fs_list(params)
		"fs.find":
			return _rpc_fs_find(params)
		"fs.grep":
			return _rpc_fs_grep(params)
		"fs.copy":
			return _rpc_fs_copy(params)
		"fs.move":
			return _rpc_fs_move(params)
		"fs.delete":
			return _rpc_fs_delete(params)
		"resource.files":
			return _rpc_resource_files(params)
		"resource.file.describe":
			return _rpc_resource_file_describe(params)
		"resource.save":
			return _rpc_resource_save(params)
		"resource.inspect":
			return _rpc_resource_inspect(params)
		"resource.classes":
			return _rpc_resource_classes(params)
		"resource.class.describe":
			return _rpc_resource_class_describe(params)
		"resource.set_properties":
			return _rpc_resource_set_properties(params)
		"resource.duplicate":
			return _rpc_resource_duplicate(params)
		"resource.dependencies":
			return _rpc_resource_dependencies(params)
		"resource.references":
			return _rpc_resource_references(params)
		"resource.move":
			return _rpc_resource_move(params)
		"resource.imports":
			return _rpc_resource_imports(params)
		"resource.import_metadata":
			return _rpc_resource_import_metadata(params)
		"resource.reimport":
			return _rpc_resource_reimport(params)
		"project.get_setting":
			return _rpc_project_get_setting(params)
		"project.set_setting":
			return _rpc_project_set_setting(params)
		"project.doctor":
			return _rpc_project_doctor(params)
		"project.summary":
			return _rpc_project_summary(params)
		"project.export_presets":
			return _rpc_project_export_presets()
		"project.set_export_preset":
			return _rpc_project_set_export_preset(params)
		"project.main_scene":
			return _rpc_project_main_scene()
		"project.set_main_scene":
			return _rpc_project_set_main_scene(params)
		"project.autoloads":
			return _rpc_project_autoloads()
		"project.add_autoload":
			return _rpc_project_add_autoload(params)
		"project.remove_autoload":
			return _rpc_project_remove_autoload(params)
		"trace.start":
			return _rpc_trace_start(params)
		"trace.stop":
			return _rpc_trace_stop()
		"trace.events":
			return _rpc_trace_events(params)
		"trace.clear":
			return _rpc_trace_clear()
		"signal.watch":
			return _rpc_signal_watch(params)
		"signal.unwatch":
			return _rpc_signal_unwatch(params)
		"signal.events":
			return _rpc_signal_events(params)
		"signal.clear":
			return _rpc_signal_clear(params)
		"signal.connections":
			return _rpc_signal_connections(params)
		"signal.connect":
			return _rpc_signal_connect(params)
		"signal.disconnect":
			return _rpc_signal_disconnect(params)
	return _fail("Unknown method: %s" % method, -32601)


func _health_payload() -> Dictionary:
	return {
		"ok": true,
		"server": "godot-playwright",
		"version": "0.1.0",
		"port": port,
		"strict_port": strict_port,
		"editor": Engine.is_editor_hint(),
		"godot": Engine.get_version_info(),
		"uptime_ms": Time.get_ticks_msec() - _started_ms,
		"last_error": _last_error,
	}


func _rpc_protocol_describe(params: Dictionary) -> Dictionary:
	var methods := _protocol_method_names()
	var method_entries := []
	for method in methods:
		method_entries.append(_protocol_method_entry(String(method)))
	var domains := _protocol_domains(methods)
	var include_methods := bool(params.get("include_methods", true))
	var include_domains := bool(params.get("include_domains", true))
	var include_features := bool(params.get("include_features", true))
	var summary := {
		"server": "godot-playwright",
		"version": "0.1.0",
		"transport": {
			"http": true,
			"jsonrpc": "2.0",
			"health": "/health",
			"rpc": "/rpc",
		},
		"editor": Engine.is_editor_hint(),
		"godot": Engine.get_version_info(),
		"project_path": ProjectSettings.globalize_path("res://"),
		"server_port": port,
		"strict_port": strict_port,
		"uptime_ms": Time.get_ticks_msec() - _started_ms,
		"method_count": methods.size(),
		"domain_count": domains.size(),
		"last_error": _last_error,
	}
	if include_methods:
		summary["methods"] = method_entries
	if include_domains:
		summary["domains"] = domains
	if include_features:
		summary["features"] = _protocol_features()
	_record_event("protocol.describe", {
		"method_count": methods.size(),
		"domain_count": domains.size(),
		"include_methods": include_methods,
		"include_domains": include_domains,
		"include_features": include_features,
	})
	return _ok(summary)


func _protocol_method_names() -> Array:
	return [
		"protocol.describe",
		"engine.info",
		"runtime.clock",
		"runtime.pause",
		"runtime.resume",
		"runtime.step_frames",
		"runtime.sample_frames",
		"runtime.evaluate",
		"tree.snapshot",
		"node.find",
		"node.describe",
		"node.state",
		"node.bounds",
		"node.click",
		"node.dialog",
		"node.accept_dialog",
		"node.dismiss_dialog",
		"node.focus",
		"node.fill",
		"node.get_property",
		"node.get_properties",
		"node.set_property",
		"node.set_properties",
		"node.set_all_properties",
		"node.attach_script",
		"node.detach_script",
		"node.set_value",
		"node.set_checked",
		"node.select_option",
		"node.select_tab",
		"node.menu_items",
		"node.select_menu_item",
		"node.select_item",
		"node.select_tree_item",
		"node.call",
		"node.call_all",
		"node.evaluate",
		"node.evaluate_all",
		"animation.describe",
		"animation.play",
		"animation.stop",
		"animation.pause",
		"animation.seek",
		"animation.advance",
		"physics2d.point",
		"physics2d.ray",
		"physics3d.point",
		"physics3d.ray",
		"camera3d.ray",
		"camera3d.pick",
		"node.class.describe",
		"node.classes",
		"node.create",
		"node.create_tree",
		"node.instantiate_scene",
		"node.save_as_scene",
		"node.metadata",
		"node.set_metadata",
		"node.remove_metadata",
		"node.groups",
		"node.add_group",
		"node.remove_group",
		"node.reparent",
		"node.move",
		"node.duplicate",
		"node.delete",
		"scene.current",
		"scene.files",
		"scene.file.describe",
		"scene.change",
		"scene.reload",
		"scene.new",
		"scene.open",
		"scene.save",
		"editor.play",
		"editor.stop",
		"editor.status",
		"editor.ui.status",
		"editor.ui.switch_main_screen",
		"editor.ui.hide_bottom_panel",
		"editor.history",
		"editor.undo",
		"editor.redo",
		"editor.selection.get",
		"editor.selection.set",
		"editor.inspect",
		"editor.inspector.describe",
		"editor.inspector.get_property",
		"editor.inspector.set_property",
		"editor.inspector.set_properties",
		"editor.script.open",
		"editor.script.status",
		"editor.script.describe",
		"script.file.describe",
		"script.classes",
		"editor.filesystem.scan",
		"editor.filesystem.describe",
		"editor.filesystem.find",
		"editor.filesystem.select",
		"editor.filesystem.open",
		"input.actions",
		"input.action.describe",
		"input.action.configure",
		"input.action.erase",
		"input.action",
		"input.key",
		"input.text",
		"input.mouse",
		"input.touch",
		"input.joypad",
		"viewport.info",
		"viewport.set_size",
		"viewport.screenshot",
		"fs.exists",
		"fs.info",
		"fs.read_text",
		"fs.write_text",
		"fs.replace_text",
		"fs.replace_text_many",
		"fs.read_bytes",
		"fs.write_bytes",
		"fs.mkdir",
		"fs.list",
		"fs.find",
		"fs.grep",
		"fs.copy",
		"fs.move",
		"fs.delete",
		"resource.files",
		"resource.file.describe",
		"resource.save",
		"resource.inspect",
		"resource.classes",
		"resource.class.describe",
		"resource.set_properties",
		"resource.duplicate",
		"resource.dependencies",
		"resource.references",
		"resource.move",
		"resource.imports",
		"resource.import_metadata",
		"resource.reimport",
		"project.get_setting",
		"project.set_setting",
		"project.doctor",
		"project.summary",
		"project.export_presets",
		"project.set_export_preset",
		"project.main_scene",
		"project.set_main_scene",
		"project.autoloads",
		"project.add_autoload",
		"project.remove_autoload",
		"trace.start",
		"trace.stop",
		"trace.events",
		"trace.clear",
		"signal.watch",
		"signal.unwatch",
		"signal.events",
		"signal.clear",
		"signal.connections",
		"signal.connect",
		"signal.disconnect",
	]


func _protocol_method_entry(method: String) -> Dictionary:
	return {
		"method": method,
		"domain": _protocol_method_domain(method),
		"python_helper": _protocol_python_helper(method),
	}


func _protocol_method_domain(method: String) -> String:
	if method.find(".") == -1:
		return method
	return String(method.split(".")[0])


func _protocol_python_helper(method: String) -> String:
	var aliases := {
		"runtime.clock": "clock",
		"runtime.pause": "pause",
		"runtime.resume": "resume",
		"runtime.step_frames": "step_frames",
		"runtime.sample_frames": "sample_frames",
		"runtime.evaluate": "evaluate",
		"tree.snapshot": "snapshot",
		"scene.current": "current_scene",
		"scene.change": "change_scene",
		"scene.reload": "reload_scene",
		"scene.new": "editor_new_scene",
		"scene.open": "editor_open_scene",
		"scene.save": "editor_save_scene",
		"editor.play": "editor_play",
		"editor.stop": "editor_stop",
		"editor.selection.get": "editor_selection",
		"editor.selection.set": "editor_select",
		"editor.script.open": "editor_open_script",
		"editor.filesystem.scan": "editor_scan_filesystem",
		"viewport.info": "viewport_info",
		"viewport.set_size": "set_viewport_size",
		"viewport.screenshot": "screenshot",
		"input.key": "key_down/key_up",
		"input.text": "input_text",
	}
	return String(aliases.get(method, method.replace(".", "_")))


func _protocol_domains(methods: Array) -> Array:
	var by_domain := {}
	for method in methods:
		var method_name := String(method)
		var domain := _protocol_method_domain(method_name)
		if not by_domain.has(domain):
			by_domain[domain] = []
		by_domain[domain].append(method_name)
	var domains := []
	var names := by_domain.keys()
	names.sort()
	for name in names:
		var domain_methods: Array = by_domain[name]
		domain_methods.sort()
		domains.append({
			"name": String(name),
			"count": domain_methods.size(),
			"methods": domain_methods,
		})
	return domains


func _protocol_features() -> Array:
	return [
		"runtime_rpc",
		"editor_rpc",
		"locator_queries",
		"locator_actions",
		"input_synthesis",
		"runtime_frame_control",
		"viewport_screenshot",
		"physics_queries",
		"animation_control",
		"signal_watch_and_connect",
		"trace_recording",
		"trace_codegen",
		"editor_scene_authoring",
		"editor_ui_control",
		"script_editor_control",
		"filesystem_mutation",
		"project_doctor",
		"project_summary",
		"project_settings",
		"export_presets",
		"scene_file_discovery",
		"script_file_describe",
		"script_class_discovery",
		"node_class_schema",
		"resource_class_schema",
		"resource_file_describe",
		"resource_dependency_scan",
		"resource_reference_scan",
		"resource_safe_move",
		"import_metadata",
		"import_asset_discovery",
	]


func _engine_info() -> Dictionary:
	var tree := get_tree()
	var current_scene := tree.get_current_scene()
	var info := _runtime_clock()
	info.merge({
		"godot": Engine.get_version_info(),
		"editor": Engine.is_editor_hint(),
		"project_path": ProjectSettings.globalize_path("res://"),
		"root": str(tree.get_root().get_path()),
		"current_scene": "" if current_scene == null else str(current_scene.get_path()),
		"edited_scene": "" if _edited_scene_root() == null else str(_edited_scene_root().get_path()),
		"open_scenes": [] if editor_interface == null else editor_interface.get_open_scenes(),
		"server_port": port,
	}, true)
	return info


func _runtime_clock() -> Dictionary:
	return {
		"uptime_ms": Time.get_ticks_msec() - _started_ms,
		"process_frames": Engine.get_process_frames(),
		"physics_frames": Engine.get_physics_frames(),
		"drawn_frames": Engine.get_frames_drawn(),
		"physics_ticks_per_second": Engine.physics_ticks_per_second,
		"time_scale": Engine.time_scale,
		"paused": get_tree().paused,
		"step_active": _frame_step_active,
		"step_counter": _frame_step_counter,
		"step_target": _frame_step_target,
	}


func _rpc_runtime_pause() -> Dictionary:
	_frame_step_active = false
	_frame_step_pause_pending = false
	get_tree().paused = true
	_record_event("runtime.pause", _runtime_clock())
	return _ok(_runtime_clock())


func _rpc_runtime_resume() -> Dictionary:
	_frame_step_active = false
	_frame_step_pause_pending = false
	get_tree().paused = false
	_record_event("runtime.resume", _runtime_clock())
	return _ok(_runtime_clock())


func _rpc_runtime_step_frames(params: Dictionary) -> Dictionary:
	var frames := max(0, int(params.get("frames", 1)))
	var physics := bool(params.get("physics", false))
	_frame_step_counter = "physics_frames" if physics else "process_frames"
	var start_frame := _runtime_step_counter_value()
	_frame_step_target = start_frame + frames
	if frames == 0:
		_frame_step_active = false
		_frame_step_pause_pending = false
		get_tree().paused = true
	else:
		_frame_step_active = true
		_frame_step_pause_pending = false
		get_tree().paused = false
	var result := _runtime_clock()
	result["start_frame"] = start_frame
	result["target_frame"] = _frame_step_target
	result["frames"] = frames
	result["physics"] = physics
	_record_event("runtime.step_frames", {
		"frames": frames,
		"physics": physics,
		"start_frame": start_frame,
		"target_frame": _frame_step_target,
	})
	return _ok(result)


func _rpc_runtime_sample_frames(params: Dictionary) -> Dictionary:
	var sample := _runtime_frame_sample(params)
	_record_event("runtime.sample_frames", {
		"sample_count": 1,
		"selector_count": sample.get("selector_count", 0),
		"expression_count": sample.get("expression_count", 0),
	})
	return _ok({
		"samples": [sample],
		"count": 1,
		"requested_frames": max(1, int(params.get("frames", 1))),
	})


func _update_runtime_frame_step() -> void:
	if not _frame_step_active or _frame_step_pause_pending:
		return
	if _runtime_step_counter_value() < _frame_step_target:
		return
	_frame_step_pause_pending = true
	call_deferred("_finish_runtime_frame_step")


func _finish_runtime_frame_step() -> void:
	get_tree().paused = true
	_frame_step_active = false
	_frame_step_pause_pending = false


func _runtime_step_counter_value() -> int:
	if _frame_step_counter == "physics_frames":
		return Engine.get_physics_frames()
	return Engine.get_process_frames()


func _runtime_frame_sample(params: Dictionary) -> Dictionary:
	var root_spec = params.get("root", "edited")
	var sample := {
		"clock": _runtime_clock(),
		"selectors": [],
		"selector_count": 0,
		"expressions": [],
		"expression_count": 0,
	}
	if bool(params.get("include_snapshot", false)):
		var root := _resolve_root(root_spec)
		if root != null:
			sample["snapshot"] = _snapshot_node(root, 0, int(params.get("max_depth", 8)), bool(params.get("include_properties", false)))
	var selectors = params.get("selectors", [])
	if typeof(selectors) != TYPE_ARRAY:
		selectors = [selectors]
	for selector in selectors:
		var node := _resolve_node(selector, root_spec)
		var entry := {"selector": selector, "found": node != null}
		if node != null:
			entry["state"] = _node_state(node)
			entry["bounds"] = _node_bounds(node)
		sample["selectors"].append(entry)
	sample["selector_count"] = sample["selectors"].size()
	var expressions = params.get("expressions", [])
	if typeof(expressions) != TYPE_ARRAY:
		expressions = [expressions]
	for expression in expressions:
		if typeof(expression) == TYPE_STRING:
			var expression_text := String(expression)
			var params_for_expression := {"variables": {}, "root": root_spec}
			sample["expressions"].append({
				"expression": expression_text,
				"result": _runtime_sample_expression(expression_text, params_for_expression),
			})
		elif typeof(expression) == TYPE_DICTIONARY:
			var expression_text := String(expression.get("expression", expression.get("name", "")))
			var params_for_expression := {
				"variables": expression.get("variables", {}),
				"root": expression.get("root", root_spec),
				"show_error": expression.get("show_error", false),
				"const_calls_only": expression.get("const_calls_only", false),
			}
			sample["expressions"].append({
				"name": expression.get("name", expression_text),
				"expression": expression_text,
				"result": _runtime_sample_expression(expression_text, params_for_expression),
			})
	sample["expression_count"] = sample["expressions"].size()
	return sample


func _runtime_sample_expression(expression_text: String, params: Dictionary) -> Dictionary:
	if expression_text == "":
		return {"ok": false, "message": "expression is required"}
	var root := _resolve_root(params.get("root", "edited"))
	if root == null:
		return {"ok": false, "message": "Evaluation root not found"}
	var inputs := _expression_inputs(params, root, null, null)
	if not inputs.get("ok", false):
		return inputs
	return _execute_expression(expression_text, inputs["names"], inputs["values"], root, params)


func _rpc_tree_snapshot(params: Dictionary) -> Dictionary:
	var root := _resolve_root(params.get("root", "edited"))
	if root == null:
		return _fail("Snapshot root not found")
	var max_depth := int(params.get("max_depth", 8))
	var include_properties := bool(params.get("include_properties", false))
	return _ok(_snapshot_node(root, 0, max_depth, include_properties))


func _rpc_node_find(params: Dictionary) -> Dictionary:
	var root := _resolve_root(params.get("root", "edited"))
	if root == null:
		return _fail("Search root not found")
	var limit := int(params.get("limit", 100))
	var nodes := _find_nodes(params.get("selector", {}), root, limit)
	var encoded := []
	for node in nodes:
		encoded.append(_node_summary(node))
	return _ok({"nodes": encoded})


func _rpc_node_describe(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	return _ok(_node_details(node))


func _rpc_node_state(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	return _ok(_node_state(node))


func _rpc_node_bounds(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var bounds := _node_bounds(node)
	if bounds.is_empty():
		return _fail("Node has no 2D bounds")
	return _ok(bounds)


func _rpc_node_click(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	if node is BaseButton:
		if node.disabled:
			return _fail("Button is disabled")
		var summary := _node_summary(node)
		var path := str(node.get_path())
		node.grab_focus()
		node.emit_signal("pressed")
		_record_event("node.click", {
			"path": path,
			"strategy": "pressed_signal",
		})
		return _ok({"strategy": "pressed_signal", "node": summary})

	var bounds := _node_bounds(node)
	if bounds.is_empty():
		return _fail("Node has no clickable bounds")
	var point := _center_from_bounds(bounds)
	_push_mouse_motion(point)
	_push_mouse_button(point, int(params.get("button", MOUSE_BUTTON_LEFT)), true)
	_push_mouse_button(point, int(params.get("button", MOUSE_BUTTON_LEFT)), false)
	_record_event("node.click", {
		"path": str(node.get_path()),
		"strategy": "viewport_input",
		"x": point.x,
		"y": point.y,
	})
	return _ok({"strategy": "viewport_input", "x": point.x, "y": point.y, "node": _node_summary(node)})


func _rpc_node_dialog(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var dialog := _dialog_from_node(node)
	if dialog == null:
		return _fail("Node is not an AcceptDialog")
	return _ok(_dialog_summary(dialog))


func _rpc_node_accept_dialog(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var dialog := _dialog_from_node(node)
	if dialog == null:
		return _fail("Node is not an AcceptDialog")
	var ok_button := dialog.get_ok_button()
	if ok_button != null and ok_button.disabled:
		return _fail("Dialog OK button is disabled")
	if dialog.has_signal("confirmed"):
		dialog.emit_signal("confirmed")
	if bool(params.get("close", true)):
		dialog.hide()
	var summary := _dialog_summary(dialog)
	_record_event("node.accept_dialog", summary)
	return _ok(summary)


func _rpc_node_dismiss_dialog(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var dialog := _dialog_from_node(node)
	if dialog == null:
		return _fail("Node is not an AcceptDialog")
	if dialog.has_method("get_cancel_button"):
		var cancel_button = dialog.call("get_cancel_button")
		if cancel_button is BaseButton and cancel_button.disabled:
			return _fail("Dialog cancel button is disabled")
	if dialog.has_signal("canceled"):
		dialog.emit_signal("canceled")
	if bool(params.get("close", true)):
		dialog.hide()
	var summary := _dialog_summary(dialog)
	_record_event("node.dismiss_dialog", summary)
	return _ok(summary)


func _rpc_node_focus(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	if not (node is Control):
		return _fail("Node is not a Control and cannot receive GUI focus")
	node.grab_focus()
	_record_event("node.focus", {"path": str(node.get_path()), "has_focus": node.has_focus()})
	return _ok({"path": str(node.get_path()), "has_focus": node.has_focus()})


func _rpc_node_fill(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var text := String(params.get("text", ""))
	var property_names := _property_name_set(node)
	if not property_names.has("text"):
		return _fail("Node has no text property")
	if node is Control:
		node.grab_focus()
	node.set("text", text)
	if node is LineEdit:
		node.set_caret_column(text.length())
		node.emit_signal("text_changed", text)
	elif node is TextEdit:
		node.emit_signal("text_changed")
	elif node.has_signal("text_changed"):
		node.emit_signal("text_changed", text)
	_record_event("node.fill", {"path": str(node.get_path()), "text": text})
	return _ok({"path": str(node.get_path()), "text": _encode_value(node.get("text"))})


func _node_bounds(node: Node) -> Dictionary:
	if node is Control:
		var rect: Rect2 = node.get_global_rect()
		return {
			"rect": {
				"x": rect.position.x,
				"y": rect.position.y,
				"width": rect.size.x,
				"height": rect.size.y,
			}
		}
	if node is Node2D:
		return {"point": {"x": node.global_position.x, "y": node.global_position.y}}
	return {}


func _center_from_bounds(bounds: Dictionary) -> Vector2:
	if bounds.has("rect"):
		var rect: Dictionary = bounds["rect"]
		return Vector2(
			float(rect.get("x", 0.0)) + float(rect.get("width", 0.0)) / 2.0,
			float(rect.get("y", 0.0)) + float(rect.get("height", 0.0)) / 2.0
		)
	var point: Dictionary = bounds.get("point", {})
	return Vector2(float(point.get("x", 0.0)), float(point.get("y", 0.0)))


func _rpc_node_get_property(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var property := String(params.get("property", ""))
	if property == "":
		return _fail("property is required", -32602)
	return _ok({"value": _encode_value(node.get(property))})


func _rpc_node_get_properties(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var properties = _property_names_from_param(params.get("properties", null))
	if properties == null:
		return _fail("properties must be an array or string", -32602)
	var values := _selected_properties(node) if properties.is_empty() else _node_property_values(node, properties)
	return _ok({
		"node": _node_summary(node),
		"values": values,
		"count": values.size(),
	})


func _rpc_node_set_property(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var property := String(params.get("property", ""))
	if property == "":
		return _fail("property is required", -32602)
	var previous = node.get(property)
	var value = _decode_value(params.get("value", null))
	var used_undo := false
	if _should_use_editor_undo(params):
		used_undo = _commit_editor_property_action(
			node,
			property,
			value,
			previous,
			String(params.get("undo_action", "Set %s.%s" % [node.name, property]))
		)
	if not used_undo:
		node.set(property, value)
	if editor_interface != null and not used_undo:
		editor_interface.mark_scene_as_unsaved()
	_record_event("node.set_property", {
		"path": str(node.get_path()),
		"property": property,
		"value": _encode_value(node.get(property)),
		"undo": used_undo,
	})
	return _ok(_node_summary(node))


func _rpc_node_set_properties(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var values = params.get("values", params.get("properties", {}))
	if typeof(values) != TYPE_DICTIONARY:
		return _fail("values must be a dictionary", -32602)
	if values.is_empty():
		return _fail("values must not be empty", -32602)
	var decoded_values := _decoded_property_values(values)
	var property_names := decoded_values.keys()
	var previous_values := _raw_node_property_values(node, property_names)
	var used_undo := false
	if _should_use_editor_undo(params):
		used_undo = _commit_editor_properties_action(
			node,
			decoded_values,
			previous_values,
			String(params.get("undo_action", "Set %s properties" % node.name))
		)
	if not used_undo:
		_apply_node_properties(node, decoded_values)
	if editor_interface != null and not used_undo:
		editor_interface.mark_scene_as_unsaved()
	_record_event("node.set_properties", {
		"path": str(node.get_path()),
		"values": values,
		"properties": property_names,
		"count": property_names.size(),
		"undo": used_undo,
	})
	return _ok({
		"node": _node_summary(node),
		"values": _node_property_values(node, property_names),
		"count": property_names.size(),
		"undo": used_undo,
	})


func _rpc_node_set_all_properties(params: Dictionary) -> Dictionary:
	var root := _resolve_root(params.get("root", "edited"))
	if root == null:
		return _fail("Search root not found")
	var values = params.get("values", params.get("properties", {}))
	if typeof(values) != TYPE_DICTIONARY:
		return _fail("values must be a dictionary", -32602)
	if values.is_empty():
		return _fail("values must not be empty", -32602)
	var decoded_values := _decoded_property_values(values)
	var property_names := decoded_values.keys()
	var limit := int(params.get("limit", 0))
	var nodes := _find_nodes(params.get("selector", {}), root, limit)
	var previous_by_node := {}
	for node in nodes:
		previous_by_node[node.get_instance_id()] = _raw_node_property_values(node, property_names)
	var used_undo := false
	if _should_use_editor_undo(params) and not nodes.is_empty():
		used_undo = _commit_editor_nodes_properties_action(
			nodes,
			decoded_values,
			previous_by_node,
			String(params.get("undo_action", "Set properties on %d nodes" % nodes.size()))
		)
	if not used_undo:
		for node in nodes:
			_apply_node_properties(node, decoded_values)
	if editor_interface != null and not used_undo and not nodes.is_empty():
		editor_interface.mark_scene_as_unsaved()
	var encoded_nodes := []
	for node in nodes:
		var summary := _node_summary(node)
		summary["values"] = _node_property_values(node, property_names)
		encoded_nodes.append(summary)
	_record_event("node.set_all_properties", {
		"root": str(root.get_path()),
		"selector": params.get("selector", {}),
		"values": values,
		"limit": limit,
		"properties": property_names,
		"count": nodes.size(),
		"undo": used_undo,
	})
	return _ok({
		"nodes": encoded_nodes,
		"count": nodes.size(),
		"properties": property_names,
		"property_count": property_names.size(),
		"undo": used_undo,
	})


func _rpc_node_attach_script(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var path := String(params.get("path", params.get("script_path", "")))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	if not ResourceLoader.exists(path):
		return _fail("Script resource not found: %s" % path)
	var cache_mode := ResourceLoader.CACHE_MODE_REPLACE if bool(params.get("reload", true)) else ResourceLoader.CACHE_MODE_REUSE
	var script := ResourceLoader.load(path, "Script", cache_mode)
	if script == null or not (script is Script):
		return _fail("Resource is not a Script: %s" % path)
	if bool(params.get("reload", true)) and script is GDScript:
		var source := FileAccess.get_file_as_string(path)
		if FileAccess.get_open_error() == OK:
			(script as GDScript).source_code = source
		var reload_error = (script as GDScript).reload(false)
		if reload_error != OK and reload_error != ERR_ALREADY_IN_USE:
			return _fail("Failed to reload script %s: %s" % [path, reload_error])
	node.set_script(script)
	if editor_interface != null:
		editor_interface.mark_scene_as_unsaved()
	if bool(params.get("inspect", false)):
		_inspect_object(node, "script")
	var summary := _node_summary(node)
	summary["script"] = _resource_summary(script)
	_record_event("node.attach_script", {
		"path": str(node.get_path()),
		"script": path,
		"inspect": bool(params.get("inspect", false)),
		"reload": bool(params.get("reload", true)),
	})
	return _ok(summary)


func _rpc_node_detach_script(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var previous = node.get_script()
	node.set_script(null)
	if editor_interface != null:
		editor_interface.mark_scene_as_unsaved()
	if bool(params.get("inspect", false)):
		_inspect_object(node, "script")
	var summary := _node_summary(node)
	summary["script"] = null
	summary["previous_script"] = _resource_summary(previous) if previous is Resource else null
	_record_event("node.detach_script", {
		"path": str(node.get_path()),
		"previous_script": "" if not (previous is Resource) else (previous as Resource).resource_path,
		"inspect": bool(params.get("inspect", false)),
	})
	return _ok(summary)


func _rpc_node_set_value(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	if not (node is Range):
		return _fail("Node is not a Range control")
	if _node_has_property(node, "editable") and not bool(node.get("editable")):
		return _fail("Range control is not editable")
	var value := float(params.get("value", 0.0))
	var previous := float(node.get("value"))
	var changed := previous != value
	if changed:
		if node is Control:
			node.grab_focus()
		node.set("value", value)
		if editor_interface != null:
			editor_interface.mark_scene_as_unsaved()
	var actual = _encode_value(node.get("value"))
	_record_event("node.set_value", {
		"path": str(node.get_path()),
		"value": actual,
		"previous": previous,
		"changed": changed,
	})
	return _ok({
		"path": str(node.get_path()),
		"value": actual,
		"previous": previous,
		"changed": changed,
		"node": _node_summary(node),
	})


func _rpc_node_set_checked(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	if node is BaseButton and node.disabled:
		return _fail("Button is disabled")
	if not _node_is_checkable(node):
		return _fail("Node is not checkable")
	var property_name := _node_checked_property(node)
	if property_name == "":
		return _fail("Node has no checked property")

	var checked := bool(params.get("checked", true))
	var previous := bool(node.get(property_name))
	var changed := previous != checked
	if changed:
		if node is Control:
			node.grab_focus()
		node.set(property_name, checked)
		if node.has_signal("pressed"):
			node.emit_signal("pressed")
		if editor_interface != null:
			editor_interface.mark_scene_as_unsaved()

	_record_event("node.set_checked", {
		"path": str(node.get_path()),
		"checked": checked,
		"previous": previous,
		"changed": changed,
	})
	return _ok({
		"path": str(node.get_path()),
		"checked": bool(node.get(property_name)),
		"previous": previous,
		"changed": changed,
		"node": _node_summary(node),
	})


func _rpc_node_select_option(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	if not (node is OptionButton):
		return _fail("Node is not an OptionButton")
	if node.disabled:
		return _fail("OptionButton is disabled")
	var option_button := node as OptionButton
	var option_spec = params.get("option", params)
	var selected_index := _option_button_find_index(option_button, option_spec)
	if selected_index < 0:
		return _fail("Option not found", -32000, {"option": option_spec})

	var previous := _option_button_selection(option_button)
	var changed := int(previous.get("index", -1)) != selected_index
	if changed:
		option_button.grab_focus()
		option_button.select(selected_index)
		if option_button.has_signal("item_selected"):
			option_button.emit_signal("item_selected", selected_index)
		if editor_interface != null:
			editor_interface.mark_scene_as_unsaved()
	var selected := _option_button_selection(option_button)
	_record_event("node.select_option", {
		"path": str(option_button.get_path()),
		"selected": selected,
		"previous": previous,
		"changed": changed,
	})
	return _ok({
		"path": str(option_button.get_path()),
		"selected": selected,
		"previous": previous,
		"changed": changed,
		"node": _node_summary(option_button),
	})


func _rpc_node_select_tab(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	if not (node is TabBar or node is TabContainer):
		return _fail("Node is not a TabBar or TabContainer")
	var tab_spec = params.get("tab", params)
	var selected_index := _tab_find_index(node, tab_spec)
	if selected_index < 0:
		return _fail("Tab not found or not selectable", -32000, {"tab": tab_spec})

	var previous := _tab_selection(node)
	var changed := int(previous.get("index", -1)) != selected_index
	if changed:
		if node is Control:
			var control := node as Control
			if control.focus_mode != Control.FOCUS_NONE:
				control.grab_focus()
		_tab_set_current(node, selected_index)
		if editor_interface != null:
			editor_interface.mark_scene_as_unsaved()
	var selected := _tab_selection(node)
	_record_event("node.select_tab", {
		"path": str(node.get_path()),
		"selected": selected,
		"previous": previous,
		"changed": changed,
	})
	return _ok({
		"path": str(node.get_path()),
		"selected": selected,
		"previous": previous,
		"changed": changed,
		"node": _node_summary(node),
	})


func _rpc_node_menu_items(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var popup_menu := _popup_menu_from_node(node)
	if popup_menu == null:
		return _fail("Node is not a PopupMenu or MenuButton")
	return _ok({
		"path": str(popup_menu.get_path()),
		"node": _node_summary(popup_menu),
		"owner": _node_summary(node) if node != popup_menu else null,
		"items": _popup_menu_items(popup_menu),
		"count": popup_menu.get_item_count(),
		"focused": _popup_menu_focused_item(popup_menu),
	})


func _rpc_node_select_menu_item(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	if node is MenuButton and node.disabled:
		return _fail("MenuButton is disabled")
	var popup_menu := _popup_menu_from_node(node)
	if popup_menu == null:
		return _fail("Node is not a PopupMenu or MenuButton")
	var item_spec = params.get("item", params)
	var selected_index := _popup_menu_find_index(popup_menu, item_spec)
	if selected_index < 0:
		return _fail("Menu item not found or not selectable", -32000, {"item": item_spec})

	var previous := _popup_menu_focused_item(popup_menu)
	var previous_checked := popup_menu.is_item_checked(selected_index)
	if params.has("checked"):
		if not popup_menu.is_item_checkable(selected_index):
			return _fail("Menu item is not checkable", -32000, {"item": item_spec})
		var checked := bool(params["checked"])
		if checked and popup_menu.is_item_radio_checkable(selected_index):
			for index in range(popup_menu.get_item_count()):
				if index != selected_index and popup_menu.is_item_radio_checkable(index):
					popup_menu.set_item_checked(index, false)
		popup_menu.set_item_checked(selected_index, checked)

	if node is Control:
		var control := node as Control
		if control.focus_mode == Control.FOCUS_CLICK or control.focus_mode == Control.FOCUS_ALL:
			control.grab_focus()
	popup_menu.set_focused_item(selected_index)
	if popup_menu.has_signal("index_pressed"):
		popup_menu.emit_signal("index_pressed", selected_index)
	if popup_menu.has_signal("id_pressed"):
		popup_menu.emit_signal("id_pressed", popup_menu.get_item_id(selected_index))
	if bool(params.get("close", true)):
		popup_menu.hide()
	if editor_interface != null:
		editor_interface.mark_scene_as_unsaved()

	var selected := _popup_menu_item(popup_menu, selected_index)
	var changed := (
		previous == null
		or int(previous.get("index", -1)) != selected_index
		or previous_checked != bool(selected.get("checked", false))
	)
	_record_event("node.select_menu_item", {
		"path": str(popup_menu.get_path()),
		"selected": selected,
		"previous": previous,
		"changed": changed,
	})
	return _ok({
		"path": str(popup_menu.get_path()),
		"selected": selected,
		"previous": previous,
		"changed": changed,
		"value": selected.get("text", ""),
		"node": _node_summary(popup_menu),
		"owner": _node_summary(node) if node != popup_menu else null,
	})


func _rpc_node_select_item(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	if not (node is ItemList):
		return _fail("Node is not an ItemList")
	var item_list := node as ItemList
	var item_spec = params.get("item", params.get("items", params))
	var selected_indices := _item_list_find_indices(item_list, item_spec)
	if selected_indices.is_empty():
		return _fail("Item not found or not selectable", -32000, {"item": item_spec})
	if selected_indices.size() > 1 and item_list.select_mode != ItemList.SELECT_MULTI:
		return _fail("ItemList does not allow multiple selection", -32000, {"item": item_spec})

	var replace := bool(params.get("replace", true))
	var previous := _item_list_selection(item_list)
	var previous_index_set := _index_set(previous.get("indices", []))
	if replace:
		item_list.deselect_all()
	for index in selected_indices:
		item_list.select(int(index), selected_indices.size() == 1 and replace)
	if item_list.focus_mode != Control.FOCUS_NONE:
		item_list.grab_focus()
	var selected := _item_list_selection(item_list)
	var changed := not _encoded_values_equal(previous.get("indices", []), selected.get("indices", []))
	if changed:
		_emit_item_list_selection_signals(item_list, previous_index_set, _index_set(selected.get("indices", [])))
		if editor_interface != null:
			editor_interface.mark_scene_as_unsaved()
	_record_event("node.select_item", {
		"path": str(item_list.get_path()),
		"selected": selected,
		"previous": previous,
		"changed": changed,
	})
	return _ok({
		"path": str(item_list.get_path()),
		"selected": selected,
		"previous": previous,
		"changed": changed,
		"value": selected.get("value", null),
		"node": _node_summary(item_list),
	})


func _rpc_node_select_tree_item(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	if not (node is Tree):
		return _fail("Node is not a Tree")
	var tree := node as Tree
	var item_spec = params.get("item", params.get("items", params))
	var selected_entries := _tree_find_entries(tree, item_spec)
	if selected_entries.is_empty():
		return _fail("Tree item not found or not selectable", -32000, {"item": item_spec})
	if selected_entries.size() > 1 and tree.select_mode != Tree.SELECT_MULTI:
		return _fail("Tree does not allow multiple selection", -32000, {"item": item_spec})

	var replace := bool(params.get("replace", true))
	var previous := _tree_selection(tree)
	if replace:
		tree.deselect_all()
	for entry in selected_entries:
		var item := entry["item"] as TreeItem
		var column := int(entry["column"])
		if tree.select_mode == Tree.SELECT_MULTI:
			item.select(column)
		else:
			tree.set_selected(item, column)
	if tree.focus_mode != Control.FOCUS_NONE:
		tree.grab_focus()
	var selected := _tree_selection(tree)
	var changed := not _encoded_values_equal(previous.get("keys", []), selected.get("keys", []))
	if changed:
		if tree.select_mode == Tree.SELECT_MULTI:
			_emit_tree_multi_selection_signals(tree, previous, selected)
		if editor_interface != null:
			editor_interface.mark_scene_as_unsaved()
	_record_event("node.select_tree_item", {
		"path": str(tree.get_path()),
		"selected": _tree_selection_public(selected),
		"previous": _tree_selection_public(previous),
		"changed": changed,
	})
	return _ok({
		"path": str(tree.get_path()),
		"selected": _tree_selection_public(selected),
		"previous": _tree_selection_public(previous),
		"changed": changed,
		"value": selected.get("value", null),
		"node": _node_summary(tree),
	})


func _rpc_node_call(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var method := String(params.get("method", ""))
	if method == "":
		return _fail("method is required", -32602)
	if not node.has_method(method):
		return _fail("Node %s has no method %s" % [node.get_path(), method])
	var args := []
	for arg in params.get("args", []):
		args.append(_decode_value(arg))
	return _ok({"value": _encode_value(node.callv(method, args))})


func _rpc_node_call_all(params: Dictionary) -> Dictionary:
	var root := _resolve_root(params.get("root", "edited"))
	if root == null:
		return _fail("Search root not found")
	var method := String(params.get("method", ""))
	if method == "":
		return _fail("method is required", -32602)
	var args := []
	for arg in params.get("args", []):
		args.append(_decode_value(arg))
	var limit := int(params.get("limit", 0))
	var strict := bool(params.get("strict", true))
	var nodes := _find_nodes(params.get("selector", {}), root, limit)
	var results := []
	var values := []
	var error_count := 0
	for index in range(nodes.size()):
		var node: Node = nodes[index]
		var entry := {
			"ok": true,
			"index": index,
			"node": _node_summary(node),
			"value": null,
		}
		if not node.has_method(method):
			error_count += 1
			entry["ok"] = false
			entry["message"] = "Node %s has no method %s" % [node.get_path(), method]
		else:
			entry["value"] = _encode_value(node.callv(method, args))
		values.append(entry.get("value", null))
		results.append(entry)
	_record_event("node.call_all", {
		"root": str(root.get_path()),
		"selector": params.get("selector", {}),
		"method": method,
		"count": nodes.size(),
		"error_count": error_count,
	})
	var payload := {
		"results": results,
		"values": values,
		"count": results.size(),
		"error_count": error_count,
	}
	if strict and error_count > 0:
		return _fail("node.call_all failed for %d node(s)" % error_count, -32000, payload)
	return _ok(payload)


func _rpc_node_evaluate(params: Dictionary) -> Dictionary:
	var root := _resolve_root(params.get("root", "edited"))
	if root == null:
		return _fail("Search root not found")
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var expression := String(params.get("expression", ""))
	if expression == "":
		return _fail("expression is required", -32602)
	var inputs := _expression_inputs(params, root, node, null)
	if not inputs.get("ok", false):
		return inputs
	var result := _execute_expression(expression, inputs["names"], inputs["values"], node, params)
	if result.get("ok", false):
		_record_event("node.evaluate", {
			"path": str(node.get_path()),
			"expression": expression,
		})
	return result


func _rpc_node_evaluate_all(params: Dictionary) -> Dictionary:
	var root := _resolve_root(params.get("root", "edited"))
	if root == null:
		return _fail("Search root not found")
	var expression := String(params.get("expression", ""))
	if expression == "":
		return _fail("expression is required", -32602)
	var limit := int(params.get("limit", 0))
	var nodes := _find_nodes(params.get("selector", {}), root, limit)
	var inputs := _expression_inputs(params, root, null, nodes)
	if not inputs.get("ok", false):
		return inputs
	var result := _execute_expression(expression, inputs["names"], inputs["values"], root, params)
	if result.get("ok", false):
		_record_event("node.evaluate_all", {
			"root": str(root.get_path()),
			"selector": params.get("selector", {}),
			"count": nodes.size(),
			"expression": expression,
		})
	return result


func _rpc_runtime_evaluate(params: Dictionary) -> Dictionary:
	var root := _resolve_root(params.get("root", "edited"))
	if root == null:
		return _fail("Evaluation root not found")
	var expression := String(params.get("expression", ""))
	if expression == "":
		return _fail("expression is required", -32602)
	var inputs := _expression_inputs(params, root, null, null)
	if not inputs.get("ok", false):
		return inputs
	var result := _execute_expression(expression, inputs["names"], inputs["values"], root, params)
	if result.get("ok", false):
		_record_event("runtime.evaluate", {
			"root": str(root.get_path()),
			"expression": expression,
		})
	return result


func _expression_inputs(params: Dictionary, root: Node, node: Node, nodes: Variant) -> Dictionary:
	var input_names := PackedStringArray()
	var input_values := []
	if node != null:
		input_names.append("node")
		input_values.append(node)
	if typeof(nodes) == TYPE_ARRAY:
		input_names.append("nodes")
		input_values.append(nodes)
		input_names.append("count")
		input_values.append(nodes.size())
	input_names.append("tree")
	input_values.append(get_tree())
	input_names.append("root")
	input_values.append(root)

	var variables = params.get("variables", params.get("vars", {}))
	if typeof(variables) != TYPE_DICTIONARY:
		return _fail("variables must be a dictionary", -32602)
	for key in variables.keys():
		var name := String(key)
		if name == "":
			return _fail("variable names must not be empty", -32602)
		if input_names.has(name):
			return _fail("variable name conflicts with reserved input: %s" % name, -32602)
		input_names.append(name)
		input_values.append(_decode_value(variables[key]))
	return {"ok": true, "names": input_names, "values": input_values}


func _execute_expression(
	expression_text: String,
	input_names: PackedStringArray,
	input_values: Array,
	base_instance: Object,
	params: Dictionary
) -> Dictionary:
	var expression := Expression.new()
	var parse_error := expression.parse(expression_text, input_names)
	if parse_error != OK:
		return _fail(
			"Expression parse failed: %s" % expression.get_error_text(),
			-32602,
			{"error": parse_error}
		)
	var value = expression.execute(
		input_values,
		base_instance,
		bool(params.get("show_error", false)),
		bool(params.get("const_calls_only", false))
	)
	if expression.has_execute_failed():
		return _fail("Expression execution failed: %s" % expression.get_error_text())
	return _ok({"value": _encode_value(value)})


func _animation_position_from_params(params: Dictionary) -> float:
	if params.has("position"):
		return float(params["position"])
	if params.has("seek"):
		return float(params["seek"])
	if params.has("time"):
		return float(params["time"])
	return float(params.get("seconds", 0.0))


func _animation_player_summary(player: AnimationPlayer, include_tracks: bool = false) -> Dictionary:
	var animations := []
	for raw_name in player.get_animation_list():
		var name := String(raw_name)
		var animation := player.get_animation(StringName(name))
		var entry := {
			"name": name,
			"length": 0.0,
			"loop_mode": 0,
			"track_count": 0,
		}
		if animation != null:
			entry["length"] = animation.length
			entry["loop_mode"] = int(animation.loop_mode)
			entry["track_count"] = animation.get_track_count()
			if include_tracks:
				entry["tracks"] = _animation_track_summaries(animation)
		animations.append(entry)
	var current_animation := String(player.current_animation)
	var assigned_animation := String(player.assigned_animation)
	var position := 0.0
	var length := 0.0
	if current_animation != "":
		position = player.current_animation_position
		length = player.current_animation_length
	elif assigned_animation != "" and player.has_animation(StringName(assigned_animation)):
		var assigned := player.get_animation(StringName(assigned_animation))
		if assigned != null:
			length = assigned.length
	return {
		"node": _node_summary(player),
		"animations": animations,
		"animation_count": animations.size(),
		"current_animation": current_animation,
		"assigned_animation": assigned_animation,
		"is_playing": player.is_playing(),
		"position": position,
		"length": length,
		"speed_scale": player.speed_scale,
		"playback_active": player.playback_active,
		"autoplay": String(player.autoplay),
		"root_node": String(player.root_node),
	}


func _animation_track_summaries(animation: Animation) -> Array:
	var tracks := []
	for index in range(animation.get_track_count()):
		tracks.append({
			"index": index,
			"type": animation.track_get_type(index),
			"path": String(animation.track_get_path(index)),
			"enabled": animation.track_is_enabled(index),
			"key_count": animation.track_get_key_count(index),
		})
	return tracks


func _rpc_animation_describe(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if node == null:
		return _fail("AnimationPlayer node not found")
	if not (node is AnimationPlayer):
		return _fail("Node is not an AnimationPlayer: %s" % node.get_class(), -32602)
	return _ok(_animation_player_summary(node as AnimationPlayer, bool(params.get("include_tracks", false))))


func _rpc_animation_play(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if node == null:
		return _fail("AnimationPlayer node not found")
	if not (node is AnimationPlayer):
		return _fail("Node is not an AnimationPlayer: %s" % node.get_class(), -32602)
	var player := node as AnimationPlayer
	var animation_name := String(params.get("animation", params.get("name", "")))
	if animation_name != "" and not player.has_animation(StringName(animation_name)):
		return _fail("AnimationPlayer %s has no animation %s" % [player.get_path(), animation_name], -32602)
	var custom_blend := float(params.get("custom_blend", params.get("blend", -1.0)))
	var custom_speed := float(params.get("custom_speed", params.get("speed", 1.0)))
	var from_end := bool(params.get("from_end", false))
	player.play(StringName(animation_name), custom_blend, custom_speed, from_end)
	if params.has("position") or params.has("seek") or params.has("time") or params.has("seconds"):
		var position := _animation_position_from_params(params)
		player.seek(position, bool(params.get("update", true)), bool(params.get("update_only", false)))
	_record_event("animation.play", {
		"path": str(player.get_path()),
		"animation": animation_name,
		"custom_blend": custom_blend,
		"custom_speed": custom_speed,
		"from_end": from_end,
	})
	return _ok(_animation_player_summary(player, bool(params.get("include_tracks", false))))


func _rpc_animation_stop(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if node == null:
		return _fail("AnimationPlayer node not found")
	if not (node is AnimationPlayer):
		return _fail("Node is not an AnimationPlayer: %s" % node.get_class(), -32602)
	var player := node as AnimationPlayer
	var keep_state := bool(params.get("keep_state", false))
	player.stop(keep_state)
	_record_event("animation.stop", {"path": str(player.get_path()), "keep_state": keep_state})
	return _ok(_animation_player_summary(player, bool(params.get("include_tracks", false))))


func _rpc_animation_pause(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if node == null:
		return _fail("AnimationPlayer node not found")
	if not (node is AnimationPlayer):
		return _fail("Node is not an AnimationPlayer: %s" % node.get_class(), -32602)
	var player := node as AnimationPlayer
	if player.has_method("pause"):
		player.call("pause")
	else:
		player.playback_active = false
	_record_event("animation.pause", {"path": str(player.get_path())})
	return _ok(_animation_player_summary(player, bool(params.get("include_tracks", false))))


func _rpc_animation_seek(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if node == null:
		return _fail("AnimationPlayer node not found")
	if not (node is AnimationPlayer):
		return _fail("Node is not an AnimationPlayer: %s" % node.get_class(), -32602)
	var player := node as AnimationPlayer
	if not (params.has("position") or params.has("seek") or params.has("time") or params.has("seconds")):
		return _fail("position is required", -32602)
	var position := _animation_position_from_params(params)
	var update := bool(params.get("update", true))
	var update_only := bool(params.get("update_only", false))
	player.seek(position, update, update_only)
	_record_event("animation.seek", {
		"path": str(player.get_path()),
		"position": position,
		"update": update,
		"update_only": update_only,
	})
	return _ok(_animation_player_summary(player, bool(params.get("include_tracks", false))))


func _rpc_animation_advance(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if node == null:
		return _fail("AnimationPlayer node not found")
	if not (node is AnimationPlayer):
		return _fail("Node is not an AnimationPlayer: %s" % node.get_class(), -32602)
	var player := node as AnimationPlayer
	var delta := float(params.get("delta", params.get("seconds", params.get("time", 0.0))))
	var current_animation := String(player.current_animation)
	if current_animation == "":
		var assigned_animation := String(player.assigned_animation)
		if assigned_animation != "" and player.has_animation(StringName(assigned_animation)):
			player.play(StringName(assigned_animation), -1.0, 0.0)
	var start_position := 0.0
	if String(player.current_animation) != "":
		start_position = player.current_animation_position
	var target_position := start_position + delta
	var update := bool(params.get("update", true))
	var update_only := bool(params.get("update_only", false))
	player.seek(target_position, update, update_only)
	_record_event("animation.advance", {
		"path": str(player.get_path()),
		"delta": delta,
		"start_position": start_position,
		"position": target_position,
		"update": update,
		"update_only": update_only,
	})
	return _ok(_animation_player_summary(player, bool(params.get("include_tracks", false))))


func _rpc_physics2d_point(params: Dictionary) -> Dictionary:
	var position := _vector2_from_params(params, "position", Vector2(float(params.get("x", 0.0)), float(params.get("y", 0.0))))
	var query := PhysicsPointQueryParameters2D.new()
	query.position = position
	query.collide_with_bodies = bool(params.get("collide_with_bodies", true))
	query.collide_with_areas = bool(params.get("collide_with_areas", true))
	if params.has("collision_mask"):
		query.collision_mask = int(params["collision_mask"])
	var max_results := max(1, int(params.get("max_results", 32)))
	var results := get_viewport().world_2d.direct_space_state.intersect_point(query, max_results)
	var collisions := []
	for result in results:
		if result is Dictionary:
			collisions.append(_physics2d_collision_summary(result, position))
	_record_event("physics2d.point", {"position": _encode_value(position), "count": collisions.size()})
	return _ok({
		"position": _encode_value(position),
		"collisions": collisions,
		"count": collisions.size(),
	})


func _rpc_physics2d_ray(params: Dictionary) -> Dictionary:
	var from := _vector2_from_params(params, "from", Vector2(float(params.get("from_x", 0.0)), float(params.get("from_y", 0.0))))
	var to := _vector2_from_params(params, "to", Vector2(float(params.get("to_x", 0.0)), float(params.get("to_y", 0.0))))
	var query := PhysicsRayQueryParameters2D.create(from, to)
	query.collide_with_bodies = bool(params.get("collide_with_bodies", true))
	query.collide_with_areas = bool(params.get("collide_with_areas", true))
	if params.has("collision_mask"):
		query.collision_mask = int(params["collision_mask"])
	var result := get_viewport().world_2d.direct_space_state.intersect_ray(query)
	var hit := not result.is_empty()
	var collision := {} if not hit else _physics2d_collision_summary(result, Vector2.ZERO)
	_record_event("physics2d.ray", {"from": _encode_value(from), "to": _encode_value(to), "hit": hit})
	return _ok({
		"from": _encode_value(from),
		"to": _encode_value(to),
		"hit": hit,
		"collision": collision,
	})


func _physics2d_collision_summary(result: Dictionary, fallback_position: Vector2) -> Dictionary:
	var summary := {
		"position": _encode_value(result.get("position", fallback_position)),
		"normal": _encode_value(result.get("normal", Vector2.ZERO)),
		"shape": int(result.get("shape", -1)),
		"collider_id": int(result.get("collider_id", 0)),
	}
	if result.has("rid"):
		summary["rid"] = str(result["rid"])
	var collider = result.get("collider", null)
	if collider is Node:
		var node := collider as Node
		summary["collider"] = _node_summary(node)
		summary["name"] = node.name
		summary["class"] = node.get_class()
		summary["path"] = str(node.get_path())
		summary["groups"] = _node_group_names(node)
		summary["metadata"] = _node_metadata_summary(node)
	elif collider != null:
		summary["collider"] = _encode_value(collider)
	return summary


func _vector2_from_params(params: Dictionary, key: String, fallback: Vector2) -> Vector2:
	if not params.has(key):
		return fallback
	var value = params[key]
	if typeof(value) == TYPE_VECTOR2:
		return value
	if typeof(value) == TYPE_DICTIONARY:
		var dictionary: Dictionary = value
		if dictionary.has("$type"):
			var decoded = _decode_value(dictionary)
			if typeof(decoded) == TYPE_VECTOR2:
				return decoded
		return Vector2(float(dictionary.get("x", fallback.x)), float(dictionary.get("y", fallback.y)))
	if typeof(value) == TYPE_ARRAY:
		var array: Array = value
		if array.size() >= 2:
			return Vector2(float(array[0]), float(array[1]))
	return fallback


func _rpc_physics3d_point(params: Dictionary) -> Dictionary:
	var position := _vector3_from_params(params, "position", Vector3(float(params.get("x", 0.0)), float(params.get("y", 0.0)), float(params.get("z", 0.0))))
	var query := PhysicsPointQueryParameters3D.new()
	query.position = position
	query.collide_with_bodies = bool(params.get("collide_with_bodies", true))
	query.collide_with_areas = bool(params.get("collide_with_areas", true))
	if params.has("collision_mask"):
		query.collision_mask = int(params["collision_mask"])
	var max_results := max(1, int(params.get("max_results", 32)))
	var results := get_viewport().world_3d.direct_space_state.intersect_point(query, max_results)
	var collisions := []
	for result in results:
		if result is Dictionary:
			collisions.append(_physics3d_collision_summary(result, position))
	_record_event("physics3d.point", {"position": _encode_value(position), "count": collisions.size()})
	return _ok({
		"position": _encode_value(position),
		"collisions": collisions,
		"count": collisions.size(),
	})


func _rpc_physics3d_ray(params: Dictionary) -> Dictionary:
	var from := _vector3_from_params(params, "from", Vector3(float(params.get("from_x", 0.0)), float(params.get("from_y", 0.0)), float(params.get("from_z", 0.0))))
	var to := _vector3_from_params(params, "to", Vector3(float(params.get("to_x", 0.0)), float(params.get("to_y", 0.0)), float(params.get("to_z", 0.0))))
	var query := PhysicsRayQueryParameters3D.create(from, to)
	query.collide_with_bodies = bool(params.get("collide_with_bodies", true))
	query.collide_with_areas = bool(params.get("collide_with_areas", true))
	if params.has("collision_mask"):
		query.collision_mask = int(params["collision_mask"])
	var result := get_viewport().world_3d.direct_space_state.intersect_ray(query)
	var hit := not result.is_empty()
	var collision := {} if not hit else _physics3d_collision_summary(result, Vector3.ZERO)
	_record_event("physics3d.ray", {"from": _encode_value(from), "to": _encode_value(to), "hit": hit})
	return _ok({
		"from": _encode_value(from),
		"to": _encode_value(to),
		"hit": hit,
		"collision": collision,
	})


func _rpc_camera3d_ray(params: Dictionary) -> Dictionary:
	var projection := _camera3d_projection(params)
	if projection.has("error"):
		return _fail(String(projection["error"]), -32602)
	var summary := _camera3d_ray_summary(projection)
	_record_event("camera3d.ray", {
		"camera": summary["camera"],
		"screen_position": summary["screen_position"],
		"origin": summary["origin"],
		"direction": summary["direction"],
		"to": summary["to"],
		"max_distance": summary["max_distance"],
	})
	return _ok(summary)


func _rpc_camera3d_pick(params: Dictionary) -> Dictionary:
	var projection := _camera3d_projection(params)
	if projection.has("error"):
		return _fail(String(projection["error"]), -32602)
	var query := PhysicsRayQueryParameters3D.create(projection["origin"], projection["to"])
	query.collide_with_bodies = bool(params.get("collide_with_bodies", true))
	query.collide_with_areas = bool(params.get("collide_with_areas", true))
	if params.has("collision_mask"):
		query.collision_mask = int(params["collision_mask"])
	var camera := projection["camera"] as Camera3D
	var world := camera.get_world_3d()
	if world == null:
		return _fail("Camera3D has no 3D world", -32602)
	var result := world.direct_space_state.intersect_ray(query)
	var hit := not result.is_empty()
	var summary := _camera3d_ray_summary(projection)
	summary["hit"] = hit
	summary["collision"] = {} if not hit else _physics3d_collision_summary(result, projection["to"])
	_record_event("camera3d.pick", {
		"camera": summary["camera"],
		"screen_position": summary["screen_position"],
		"hit": hit,
	})
	return _ok(summary)


func _camera3d_projection(params: Dictionary) -> Dictionary:
	var camera := _camera3d_from_params(params)
	if camera == null:
		return {"error": "Camera3D not found; provide a camera selector or make a Camera3D current"}
	var fallback_position := Vector2(
		float(params.get("x", params.get("screen_x", 0.0))),
		float(params.get("y", params.get("screen_y", 0.0)))
	)
	var screen_position := _vector2_from_params(
		params,
		"screen_position",
		_vector2_from_params(params, "position", fallback_position)
	)
	var max_distance := max(0.001, float(params.get("max_distance", 1000.0)))
	var origin: Vector3 = camera.project_ray_origin(screen_position)
	var direction: Vector3 = camera.project_ray_normal(screen_position).normalized()
	var to: Vector3 = origin + direction * max_distance
	return {
		"camera": camera,
		"screen_position": screen_position,
		"origin": origin,
		"direction": direction,
		"to": to,
		"max_distance": max_distance,
	}


func _camera3d_from_params(params: Dictionary) -> Camera3D:
	var camera_selector = params.get("camera", params.get("selector", params.get("node", null)))
	if camera_selector != null:
		var node := _resolve_node(camera_selector, params.get("root", "edited"))
		if node is Camera3D:
			return node as Camera3D
		return null
	var current := get_viewport().get_camera_3d()
	if current != null:
		return current
	var root := _resolve_root(params.get("root", "edited"))
	if root == null:
		return null
	var cameras := _find_nodes({"type": "Camera3D"}, root, 1)
	if cameras.is_empty() or not (cameras[0] is Camera3D):
		return null
	return cameras[0] as Camera3D


func _camera3d_ray_summary(projection: Dictionary) -> Dictionary:
	var camera := projection["camera"] as Camera3D
	return {
		"camera": _node_summary(camera),
		"screen_position": _encode_value(projection["screen_position"]),
		"origin": _encode_value(projection["origin"]),
		"direction": _encode_value(projection["direction"]),
		"to": _encode_value(projection["to"]),
		"max_distance": float(projection["max_distance"]),
	}


func _physics3d_collision_summary(result: Dictionary, fallback_position: Vector3) -> Dictionary:
	var summary := {
		"position": _encode_value(result.get("position", fallback_position)),
		"normal": _encode_value(result.get("normal", Vector3.ZERO)),
		"shape": int(result.get("shape", -1)),
		"collider_id": int(result.get("collider_id", 0)),
	}
	if result.has("face_index"):
		summary["face_index"] = int(result["face_index"])
	if result.has("rid"):
		summary["rid"] = str(result["rid"])
	var collider = result.get("collider", null)
	if collider is Node:
		var node := collider as Node
		summary["collider"] = _node_summary(node)
		summary["name"] = node.name
		summary["class"] = node.get_class()
		summary["path"] = str(node.get_path())
		summary["groups"] = _node_group_names(node)
		summary["metadata"] = _node_metadata_summary(node)
	elif collider != null:
		summary["collider"] = _encode_value(collider)
	return summary


func _vector3_from_params(params: Dictionary, key: String, fallback: Vector3) -> Vector3:
	if not params.has(key):
		return fallback
	var value = params[key]
	if typeof(value) == TYPE_VECTOR3:
		return value
	if typeof(value) == TYPE_DICTIONARY:
		var dictionary: Dictionary = value
		if dictionary.has("$type"):
			var decoded = _decode_value(dictionary)
			if typeof(decoded) == TYPE_VECTOR3:
				return decoded
		return Vector3(
			float(dictionary.get("x", fallback.x)),
			float(dictionary.get("y", fallback.y)),
			float(dictionary.get("z", fallback.z))
		)
	if typeof(value) == TYPE_ARRAY:
		var array: Array = value
		if array.size() >= 3:
			return Vector3(float(array[0]), float(array[1]), float(array[2]))
	return fallback


func _rpc_node_classes(params: Dictionary) -> Dictionary:
	var base_class := String(params.get("base_class", "Node"))
	if base_class == "":
		base_class = "Node"
	if not ClassDB.class_exists(base_class) and base_class != "Node":
		return _fail("Base class not found: %s" % base_class, -32602)
	if base_class != "Object" and base_class != "Node" and not ClassDB.is_parent_class(base_class, "Node"):
		return _fail("Base class is not a Node class: %s" % base_class, -32602)
	var name_contains := String(params.get("name_contains", ""))
	var include_abstract := bool(params.get("include_abstract", false))
	var include_disabled := bool(params.get("include_disabled", false))
	var include_property_counts := bool(params.get("include_property_counts", true))
	var max_results := max(1, int(params.get("max_results", 200)))
	var classes := []
	var total_matches := 0
	for raw_class_name in ClassDB.get_class_list():
		var node_class_name := String(raw_class_name)
		if node_class_name == "":
			continue
		var is_node_class := node_class_name == "Node" or ClassDB.is_parent_class(node_class_name, "Node")
		if not is_node_class:
			continue
		if base_class != "" and base_class != "Object" and node_class_name != base_class and not ClassDB.is_parent_class(node_class_name, base_class):
			continue
		if name_contains != "" and not node_class_name.contains(name_contains):
			continue
		var can_instantiate := node_class_name == "Node" or ClassDB.can_instantiate(node_class_name)
		if not include_abstract and not can_instantiate:
			continue
		var enabled := true
		if ClassDB.has_method("is_class_enabled"):
			enabled = bool(ClassDB.is_class_enabled(node_class_name))
		if not include_disabled and not enabled:
			continue
		total_matches += 1
		if classes.size() >= max_results:
			continue
		classes.append(_node_class_list_entry(node_class_name, include_property_counts))
	classes.sort_custom(func(a, b): return String(a.get("class", "")) < String(b.get("class", "")))
	var summary := {
		"base_class": base_class,
		"name_contains": name_contains,
		"include_abstract": include_abstract,
		"include_disabled": include_disabled,
		"include_property_counts": include_property_counts,
		"classes": classes,
		"count": classes.size(),
		"total_matches": total_matches,
		"truncated": total_matches > classes.size(),
		"max_results": max_results,
	}
	_record_event("node.classes", {
		"base_class": base_class,
		"name_contains": name_contains,
		"count": classes.size(),
		"total_matches": total_matches,
		"truncated": total_matches > classes.size(),
	})
	return _ok(summary)


func _rpc_node_class_describe(params: Dictionary) -> Dictionary:
	var requested_class := String(params.get("class", params.get("type", params.get("class_name", "Node"))))
	if requested_class == "":
		requested_class = "Node"
	var exists := requested_class == "Node" or ClassDB.class_exists(requested_class)
	var can_instantiate := requested_class == "Node" or (exists and ClassDB.can_instantiate(requested_class))
	var is_node_class := requested_class == "Node" or (exists and ClassDB.is_parent_class(requested_class, "Node"))
	var summary := {
		"requested_class": requested_class,
		"class": requested_class,
		"exists": exists,
		"can_instantiate": can_instantiate,
		"is_node": is_node_class,
		"properties": [],
		"property_count": 0,
		"storage_property_count": 0,
		"editor_property_count": 0,
		"methods": [],
		"method_count": 0,
		"signals": [],
		"signal_count": 0,
		"values": {},
	}
	if not exists or not can_instantiate or not is_node_class:
		return _ok(summary)
	var node = ClassDB.instantiate(requested_class)
	if not (node is Node):
		summary["can_instantiate"] = false
		summary["is_node"] = false
		return _ok(summary)
	summary["class"] = node.get_class()
	var property_filter := _string_filter_array(params.get("properties", []))
	var name_contains := String(params.get("name_contains", ""))
	var include_internal := bool(params.get("include_internal", false))
	var storage_only := bool(params.get("storage_only", false))
	var include_values := bool(params.get("include_values", true))
	var include_methods := bool(params.get("include_methods", true))
	var include_signals := bool(params.get("include_signals", true))
	var method_filter := _string_filter_array(params.get("methods", []))
	var signal_filter := _string_filter_array(params.get("signals", []))
	var method_contains := String(params.get("method_contains", ""))
	var signal_contains := String(params.get("signal_contains", ""))
	var max_methods := max(1, int(params.get("max_methods", 200)))
	var max_signals := max(1, int(params.get("max_signals", 200)))
	var properties := []
	var values := {}
	var storage_count := 0
	var editor_count := 0
	for info in node.get_property_list():
		if typeof(info) != TYPE_DICTIONARY:
			continue
		var name := String(info.get("name", ""))
		if name == "":
			continue
		if not include_internal and name.begins_with("_"):
			continue
		if not property_filter.is_empty() and not property_filter.has(name):
			continue
		if name_contains != "" and not name.contains(name_contains):
			continue
		var property_summary := _node_property_schema(node, info, include_values)
		if storage_only and not bool(property_summary.get("storage", false)):
			continue
		if bool(property_summary.get("storage", false)):
			storage_count += 1
		if bool(property_summary.get("editor_visible", false)):
			editor_count += 1
		properties.append(property_summary)
		if include_values:
			values[name] = property_summary.get("value", null)
	var methods := []
	var method_total := 0
	if include_methods:
		for info in node.get_method_list():
			if typeof(info) != TYPE_DICTIONARY:
				continue
			var method_name := String(info.get("name", ""))
			if method_name == "":
				continue
			if not include_internal and method_name.begins_with("_"):
				continue
			if not method_filter.is_empty() and not method_filter.has(method_name):
				continue
			if method_contains != "" and not method_name.contains(method_contains):
				continue
			method_total += 1
			if methods.size() >= max_methods:
				continue
			methods.append(_api_info_summary(info))
	var signals := []
	var signal_total := 0
	if include_signals:
		for info in node.get_signal_list():
			if typeof(info) != TYPE_DICTIONARY:
				continue
			var signal_name := String(info.get("name", ""))
			if signal_name == "":
				continue
			if not include_internal and signal_name.begins_with("_"):
				continue
			if not signal_filter.is_empty() and not signal_filter.has(signal_name):
				continue
			if signal_contains != "" and not signal_name.contains(signal_contains):
				continue
			signal_total += 1
			if signals.size() >= max_signals:
				continue
			signals.append(_api_info_summary(info))
	node.free()
	summary["properties"] = properties
	summary["property_count"] = properties.size()
	summary["storage_property_count"] = storage_count
	summary["editor_property_count"] = editor_count
	summary["methods"] = methods
	summary["method_count"] = method_total
	summary["methods_truncated"] = method_total > methods.size()
	summary["max_methods"] = max_methods
	summary["signals"] = signals
	summary["signal_count"] = signal_total
	summary["signals_truncated"] = signal_total > signals.size()
	summary["max_signals"] = max_signals
	if include_values:
		summary["values"] = values
	_record_event("node.class.describe", {
		"class": requested_class,
		"property_count": properties.size(),
		"method_count": method_total,
		"signal_count": signal_total,
		"storage_only": storage_only,
		"include_methods": include_methods,
		"include_signals": include_signals,
	})
	return _ok(summary)


func _rpc_node_create(params: Dictionary) -> Dictionary:
	var parent := _resolve_node(params.get("parent", "edited"), params.get("root", "edited"))
	if parent == null:
		return _fail("Parent node not found")
	var node_class := String(params.get("class", params.get("type", "Node")))
	if not ClassDB.class_exists(node_class) or not ClassDB.can_instantiate(node_class):
		return _fail("Cannot instantiate class: %s" % node_class)
	var node = ClassDB.instantiate(node_class)
	if not (node is Node):
		return _fail("Class is not a Node: %s" % node_class)
	var name := String(params.get("name", node_class))
	if name != "":
		node.name = name
	var owner_scene := _edited_scene_root()
	var used_undo := false
	if _should_use_editor_undo(params):
		used_undo = _commit_editor_create_node_action(
			parent,
			node,
			owner_scene if bool(params.get("owner_scene", true)) else null,
			String(params.get("undo_action", "Create %s" % node.name))
		)
	if not used_undo:
		parent.add_child(node)
		if bool(params.get("owner_scene", true)) and owner_scene != null and node != owner_scene:
			node.owner = owner_scene
	if editor_interface != null and not used_undo:
		editor_interface.mark_scene_as_unsaved()
	_record_event("node.create", {
		"path": str(node.get_path()),
		"class": node_class,
		"name": node.name,
		"parent": str(parent.get_path()),
		"owner_scene": bool(params.get("owner_scene", true)),
		"undo": used_undo,
	})
	return _ok(_node_summary(node))


func _rpc_node_create_tree(params: Dictionary) -> Dictionary:
	var parent := _resolve_node(params.get("parent", "edited"), params.get("root", "edited"))
	if parent == null:
		return _fail("Parent node not found")
	var raw_nodes = params.get("nodes", params.get("children", null))
	if typeof(raw_nodes) == TYPE_NIL and params.has("node"):
		raw_nodes = [params["node"]]
	elif typeof(raw_nodes) == TYPE_NIL and params.has("spec"):
		raw_nodes = [params["spec"]]
	if typeof(raw_nodes) == TYPE_DICTIONARY:
		raw_nodes = [raw_nodes]
	if typeof(raw_nodes) != TYPE_ARRAY or raw_nodes.is_empty():
		return _fail("nodes must be a non-empty array", -32602)
	var max_nodes := max(1, int(params.get("max_nodes", 100)))
	var owner_scene := _edited_scene_root()
	var summaries := []
	for raw_spec in raw_nodes:
		if typeof(raw_spec) != TYPE_DICTIONARY:
			return _fail("Each node spec must be an object", -32602)
		var result := _create_node_tree_from_spec(
			parent,
			raw_spec,
			owner_scene,
			bool(params.get("owner_scene", true)),
			summaries,
			max_nodes,
			bool(params.get("persistent_groups", true)),
			bool(params.get("reload_scripts", true))
		)
		if not bool(result.get("ok", false)):
			return _fail(String(result.get("message", "Failed to create node tree")), int(result.get("code", -32000)), result.get("data", null))
	if editor_interface != null:
		editor_interface.mark_scene_as_unsaved()
	_record_event("node.create_tree", {
		"parent": str(parent.get_path()),
		"nodes": raw_nodes,
		"owner_scene": bool(params.get("owner_scene", true)),
		"persistent_groups": bool(params.get("persistent_groups", true)),
		"reload_scripts": bool(params.get("reload_scripts", true)),
		"max_nodes": max_nodes,
		"count": summaries.size(),
	})
	return _ok({
		"parent": _node_summary(parent),
		"nodes": summaries,
		"count": summaries.size(),
	})


func _create_node_tree_from_spec(
	parent: Node,
	spec: Dictionary,
	owner_scene: Node,
	owner_scene_enabled: bool,
	summaries: Array,
	max_nodes: int,
	persistent_groups: bool,
	reload_scripts: bool
) -> Dictionary:
	if summaries.size() >= max_nodes:
		return {"ok": false, "code": -32602, "message": "node tree exceeds max_nodes: %s" % max_nodes}
	var node_class := String(spec.get("class", spec.get("type", "Node")))
	if not ClassDB.class_exists(node_class) or not ClassDB.can_instantiate(node_class):
		return {"ok": false, "code": -32602, "message": "Cannot instantiate class: %s" % node_class}
	var node = ClassDB.instantiate(node_class)
	if not (node is Node):
		return {"ok": false, "code": -32602, "message": "Class is not a Node: %s" % node_class}
	var created_node := node as Node
	var name := String(spec.get("name", node_class))
	if name != "":
		created_node.name = name
	parent.add_child(created_node)
	if spec.has("index"):
		parent.move_child(created_node, int(spec["index"]))
	if owner_scene_enabled and owner_scene != null and created_node != owner_scene:
		created_node.owner = owner_scene
	var properties = spec.get("properties", {})
	if typeof(properties) != TYPE_DICTIONARY:
		return {"ok": false, "code": -32602, "message": "properties must be an object"}
	for property in properties.keys():
		created_node.set(String(property), _decode_value(properties[property]))
	var metadata = spec.get("metadata", spec.get("meta", {}))
	if typeof(metadata) != TYPE_DICTIONARY:
		return {"ok": false, "code": -32602, "message": "metadata must be an object"}
	for metadata_name in metadata.keys():
		created_node.set_meta(StringName(String(metadata_name)), _decode_value(metadata[metadata_name]))
	var groups = spec.get("groups", [])
	if typeof(groups) == TYPE_STRING:
		groups = [groups]
	if typeof(groups) != TYPE_ARRAY:
		return {"ok": false, "code": -32602, "message": "groups must be an array or string"}
	for group_name in groups:
		created_node.add_to_group(StringName(String(group_name)), persistent_groups)
	var script_path := String(spec.get("script", spec.get("script_path", "")))
	if script_path != "":
		var script_error := _attach_script_to_node(created_node, script_path, reload_scripts)
		if script_error != "":
			return {"ok": false, "code": -32602, "message": script_error}
	var summary := _node_summary(created_node)
	if not (properties as Dictionary).is_empty():
		var property_values := {}
		for property in (properties as Dictionary).keys():
			property_values[String(property)] = _encode_value(created_node.get(String(property)))
		summary["properties"] = property_values
	if not (metadata as Dictionary).is_empty():
		summary["metadata"] = _node_metadata_summary(created_node)
	if script_path != "":
		var script = created_node.get_script()
		summary["script"] = _resource_summary(script) if script is Resource else null
	summaries.append(summary)
	var children = spec.get("children", [])
	if typeof(children) != TYPE_ARRAY:
		return {"ok": false, "code": -32602, "message": "children must be an array"}
	for child_spec in children:
		if typeof(child_spec) != TYPE_DICTIONARY:
			return {"ok": false, "code": -32602, "message": "Each child node spec must be an object"}
		var child_result := _create_node_tree_from_spec(
			created_node,
			child_spec,
			owner_scene,
			owner_scene_enabled,
			summaries,
			max_nodes,
			persistent_groups,
			reload_scripts
		)
		if not bool(child_result.get("ok", false)):
			return child_result
	return {"ok": true, "node": created_node}


func _attach_script_to_node(node: Node, path: String, reload: bool) -> String:
	var path_error := _validate_res_path(path)
	if path_error != "":
		return path_error
	if not ResourceLoader.exists(path):
		return "Script resource not found: %s" % path
	var cache_mode := ResourceLoader.CACHE_MODE_REPLACE if reload else ResourceLoader.CACHE_MODE_REUSE
	var script := ResourceLoader.load(path, "Script", cache_mode)
	if script == null or not (script is Script):
		return "Resource is not a Script: %s" % path
	if reload and script is GDScript:
		var source := FileAccess.get_file_as_string(path)
		if FileAccess.get_open_error() == OK:
			(script as GDScript).source_code = source
		var reload_error = (script as GDScript).reload(false)
		if reload_error != OK and reload_error != ERR_ALREADY_IN_USE:
			return "Failed to reload script %s: %s" % [path, reload_error]
	node.set_script(script)
	return ""


func _rpc_node_instantiate_scene(params: Dictionary) -> Dictionary:
	var parent := _resolve_node(params.get("parent", "edited"), params.get("root", "edited"))
	if parent == null:
		return _fail("Parent node not found")
	var path := String(params.get("path", params.get("scene", "")))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var extension := path.get_extension().to_lower()
	if extension != "tscn" and extension != "scn":
		return _fail("Scene path must be a .tscn or .scn resource: %s" % path, -32602)
	if not ResourceLoader.exists(path):
		return _fail("Scene resource not found: %s" % path, -32602)
	var resource := ResourceLoader.load(path, "PackedScene")
	if resource == null or not (resource is PackedScene):
		return _fail("Resource is not a PackedScene: %s" % path)
	var instance = (resource as PackedScene).instantiate()
	if instance == null or not (instance is Node):
		return _fail("Failed to instantiate scene: %s" % path)
	var node := instance as Node
	var name := String(params.get("name", ""))
	if name != "":
		node.name = name
	parent.add_child(node)
	if params.has("index"):
		parent.move_child(node, int(params["index"]))
	var owner_scene := _edited_scene_root()
	if bool(params.get("owner_scene", true)) and owner_scene != null and node != owner_scene:
		node.owner = owner_scene
	if editor_interface != null:
		editor_interface.mark_scene_as_unsaved()
	var summary := _node_summary(node)
	summary["source_scene"] = path
	summary["packed_scene"] = _resource_summary(resource)
	_record_event("node.instantiate_scene", {
		"path": str(node.get_path()),
		"source_scene": path,
		"parent": str(parent.get_path()),
		"name": node.name,
		"index": node.get_index(true),
		"owner_scene": bool(params.get("owner_scene", true)),
	})
	return _ok(summary)


func _rpc_node_save_as_scene(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var path := String(params.get("path", params.get("scene", "")))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var extension := path.get_extension().to_lower()
	if extension != "tscn" and extension != "scn":
		return _fail("Scene path must be a .tscn or .scn resource: %s" % path, -32602)
	if FileAccess.file_exists(path) and not bool(params.get("overwrite", true)):
		return _fail("File already exists: %s" % path, -32602)
	var dir_error := _ensure_res_parent_dir(path)
	if dir_error != OK:
		return _fail("Failed to create parent directories for %s: %s" % [path, dir_error])

	var previous_owners := {}
	_assign_pack_owner_recursive(node, node, previous_owners)
	var packed_scene := PackedScene.new()
	var pack_error := packed_scene.pack(node)
	_restore_node_owners(previous_owners)
	if pack_error != OK:
		return _fail("Failed to pack node %s as scene: %s" % [node.get_path(), pack_error])
	var save_error := ResourceSaver.save(packed_scene, path)
	if save_error != OK:
		return _fail("Failed to save scene %s: %s" % [path, save_error])
	_scan_editor_filesystem(path)
	_record_event("node.save_as_scene", {
		"path": path,
		"source": str(node.get_path()),
		"overwrite": bool(params.get("overwrite", true)),
		"child_count": node.get_child_count(),
	})
	return _ok({
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"source": _node_summary(node),
		"packed_scene": _resource_summary(packed_scene),
		"saved": true,
	})


func _rpc_node_metadata(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var names = _property_names_from_param(params.get("names", params.get("name", null)))
	if names == null:
		return _fail("names must be an array or string", -32602)
	var metadata := _node_metadata_summary(node) if names.is_empty() else _node_metadata_values(node, names)
	return _ok({
		"node": _node_summary(node),
		"metadata": metadata,
		"values": metadata,
		"count": metadata.size(),
	})


func _rpc_node_set_metadata(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var values := {}
	if params.has("values") or params.has("metadata"):
		var raw_values = params.get("values", params.get("metadata", {}))
		if typeof(raw_values) != TYPE_DICTIONARY:
			return _fail("values must be a dictionary", -32602)
		if raw_values.is_empty():
			return _fail("values must not be empty", -32602)
		values = _decoded_property_values(raw_values)
	else:
		var name := String(params.get("name", "")).strip_edges()
		if name == "":
			return _fail("name is required", -32602)
		if not params.has("value"):
			return _fail("value is required", -32602)
		values[name] = _decode_value(params.get("value"))
	var names := values.keys()
	var previous := _node_metadata_previous(node, names)
	var used_undo := false
	if _should_use_editor_undo(params):
		used_undo = _commit_editor_metadata_set_action(
			node,
			values,
			previous,
			String(params.get("undo_action", "Set %s metadata" % node.name))
		)
	if not used_undo:
		_apply_node_metadata(node, values)
	if editor_interface != null and not used_undo:
		editor_interface.mark_scene_as_unsaved()
	var metadata := _node_metadata_values(node, names)
	_record_event("node.set_metadata", {
		"path": str(node.get_path()),
		"values": values,
		"names": names,
		"count": names.size(),
		"undo": used_undo,
	})
	return _ok({
		"node": _node_summary(node),
		"metadata": metadata,
		"values": metadata,
		"count": metadata.size(),
		"undo": used_undo,
	})


func _rpc_node_remove_metadata(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var names = _property_names_from_param(params.get("names", params.get("name", null)))
	if names == null:
		return _fail("names must be an array or string", -32602)
	if names.is_empty():
		return _fail("name is required", -32602)
	var previous := _node_metadata_previous(node, names)
	var used_undo := false
	if _should_use_editor_undo(params):
		used_undo = _commit_editor_metadata_remove_action(
			node,
			names,
			previous,
			String(params.get("undo_action", "Remove %s metadata" % node.name))
		)
	if not used_undo:
		_remove_node_metadata(node, names)
	if editor_interface != null and not used_undo:
		editor_interface.mark_scene_as_unsaved()
	var removed := []
	for name in names:
		var info: Dictionary = previous.get(String(name), {})
		if bool(info.get("exists", false)):
			removed.append(String(name))
	_record_event("node.remove_metadata", {
		"path": str(node.get_path()),
		"names": names,
		"removed": removed,
		"undo": used_undo,
	})
	return _ok({
		"node": _node_summary(node),
		"removed": removed,
		"metadata": _node_metadata_summary(node),
		"count": removed.size(),
		"undo": used_undo,
	})


func _rpc_node_groups(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var groups := _node_group_names(node, bool(params.get("include_internal", false)))
	return _ok({
		"node": _node_summary(node),
		"groups": groups,
		"count": groups.size(),
	})


func _rpc_node_add_group(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var group := String(params.get("group", "")).strip_edges()
	if group == "":
		return _fail("group is required", -32602)
	var persistent := bool(params.get("persistent", true))
	var previous := node.is_in_group(group)
	node.add_to_group(group, persistent)
	if editor_interface != null:
		editor_interface.mark_scene_as_unsaved()
	var groups := _node_group_names(node, bool(params.get("include_internal", false)))
	_record_event("node.add_group", {
		"path": str(node.get_path()),
		"group": group,
		"persistent": persistent,
		"previous": previous,
	})
	return _ok({
		"node": _node_summary(node),
		"group": group,
		"added": not previous,
		"persistent": persistent,
		"groups": groups,
		"count": groups.size(),
	})


func _rpc_node_remove_group(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var group := String(params.get("group", "")).strip_edges()
	if group == "":
		return _fail("group is required", -32602)
	var previous := node.is_in_group(group)
	if previous:
		node.remove_from_group(group)
		if editor_interface != null:
			editor_interface.mark_scene_as_unsaved()
	var groups := _node_group_names(node, bool(params.get("include_internal", false)))
	_record_event("node.remove_group", {
		"path": str(node.get_path()),
		"group": group,
		"previous": previous,
	})
	return _ok({
		"node": _node_summary(node),
		"group": group,
		"removed": previous,
		"groups": groups,
		"count": groups.size(),
	})


func _rpc_node_reparent(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var new_parent := _resolve_node(params.get("parent", params.get("new_parent", "edited")), params.get("root", "edited"))
	if new_parent == null:
		return _fail("New parent node not found")
	if node == new_parent:
		return _fail("Cannot reparent a node under itself", -32602)
	if _node_is_ancestor(node, new_parent):
		return _fail("Cannot reparent a node under its own descendant", -32602)
	var old_path := str(node.get_path())
	var old_parent := node.get_parent()
	var old_parent_path := "" if old_parent == null else str(old_parent.get_path())
	var keep_global_transform := bool(params.get("keep_global_transform", true))
	if node.has_method("reparent"):
		node.call("reparent", new_parent, keep_global_transform)
	else:
		if old_parent != null:
			old_parent.remove_child(node)
		new_parent.add_child(node)
	if params.has("index"):
		new_parent.move_child(node, int(params["index"]))
	if bool(params.get("owner_scene", true)):
		_assign_owner_scene_recursive(node)
	if editor_interface != null:
		editor_interface.mark_scene_as_unsaved()
	var summary := _node_summary(node)
	_record_event("node.reparent", {
		"old_path": old_path,
		"new_path": str(node.get_path()),
		"old_parent": old_parent_path,
		"new_parent": str(new_parent.get_path()),
		"index": node.get_index(true),
		"keep_global_transform": keep_global_transform,
		"owner_scene": bool(params.get("owner_scene", true)),
	})
	summary["old_path"] = old_path
	summary["old_parent"] = old_parent_path
	summary["new_parent"] = str(new_parent.get_path())
	return _ok(summary)


func _rpc_node_move(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var parent := node.get_parent()
	if parent == null:
		return _fail("Node has no parent")
	if not params.has("index"):
		return _fail("index is required", -32602)
	var index := int(params["index"])
	if index < 0 or index >= parent.get_child_count():
		return _fail("index out of range: %s" % index, -32602)
	var old_index := node.get_index()
	parent.move_child(node, index)
	if editor_interface != null:
		editor_interface.mark_scene_as_unsaved()
	var summary := _node_summary(node)
	summary["old_index"] = old_index
	summary["index"] = node.get_index()
	_record_event("node.move", {
		"path": str(node.get_path()),
		"parent": str(parent.get_path()),
		"old_index": old_index,
		"index": node.get_index(),
	})
	return _ok(summary)


func _rpc_node_duplicate(params: Dictionary) -> Dictionary:
	var source := _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
	if source == null:
		return _fail("Node not found")
	var parent := _resolve_node(params.get("parent", "edited" if source.get_parent() == null else str(source.get_parent().get_path())), params.get("root", "edited"))
	if parent == null:
		return _fail("Parent node not found")
	var duplicate: Node
	if params.has("flags"):
		duplicate = source.duplicate(int(params["flags"]))
	else:
		duplicate = source.duplicate()
	if duplicate == null:
		return _fail("Failed to duplicate node")
	var name := String(params.get("name", ""))
	if name != "":
		duplicate.name = name
	parent.add_child(duplicate)
	if params.has("index"):
		parent.move_child(duplicate, int(params["index"]))
	if bool(params.get("owner_scene", true)):
		_assign_owner_scene_recursive(duplicate)
	if editor_interface != null:
		editor_interface.mark_scene_as_unsaved()
	_record_event("node.duplicate", {
		"source": str(source.get_path()),
		"path": str(duplicate.get_path()),
		"parent": str(parent.get_path()),
		"name": duplicate.name,
		"index": duplicate.get_index(),
		"owner_scene": bool(params.get("owner_scene", true)),
		"flags": params.get("flags", null),
	})
	var summary := _node_summary(duplicate)
	summary["source"] = _node_summary(source)
	return _ok(summary)


func _rpc_node_delete(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var path := str(node.get_path())
	var parent := node.get_parent()
	if parent != null:
		parent.remove_child(node)
	node.queue_free()
	if editor_interface != null:
		editor_interface.mark_scene_as_unsaved()
	_record_event("node.delete", {"path": path})
	return _ok({"deleted": path})


func _rpc_scene_current() -> Dictionary:
	return _ok(_current_scene_info())


func _rpc_scene_files(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", "res://"))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var max_results := max(1, int(params.get("max_results", 200)))
	var max_scan_results := max(max_results, int(params.get("max_scan_results", max_results * 20)))
	var extensions := _string_filter_array(params.get("extensions", params.get("extension", [])))
	if extensions.is_empty():
		extensions = ["tscn", "scn"]
	for index in range(extensions.size()):
		extensions[index] = String(extensions[index]).trim_prefix(".").to_lower()
	var name_filter := String(params.get("name", ""))
	var name_contains := String(params.get("name_contains", ""))
	var root_name := String(params.get("root_name", ""))
	var root_class := String(params.get("root_class", params.get("class", params.get("class_name", ""))))
	var include_dependencies := bool(params.get("include_dependencies", true))
	var include_nodes := bool(params.get("include_nodes", false))
	var entries := []
	_collect_filesystem_entries(
		path,
		bool(params.get("recursive", true)),
		false,
		bool(params.get("include_hidden", false)),
		{},
		max_scan_results,
		entries
	)
	var scenes := []
	var total_matches := 0
	var scanned := 0
	for entry in entries:
		if not bool(entry.get("is_file", false)):
			continue
		var scene_path := String(entry.get("path", ""))
		var extension := scene_path.get_extension().to_lower()
		if not extensions.has(extension):
			continue
		scanned += 1
		var scene := _scene_file_summary(scene_path, include_dependencies, include_nodes, false, false, false)
		if name_filter != "" and String(scene.get("name", "")) != name_filter:
			continue
		if name_contains != "" and not String(scene.get("name", "")).contains(name_contains) and not scene_path.contains(name_contains):
			continue
		if root_name != "" and String(scene.get("root_name", "")) != root_name:
			continue
		if root_class != "" and String(scene.get("root_class", "")) != root_class:
			continue
		total_matches += 1
		if scenes.size() >= max_results:
			continue
		scenes.append(scene)
	scenes.sort_custom(func(a, b): return String(a.get("path", "")) < String(b.get("path", "")))
	var summary := {
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"recursive": bool(params.get("recursive", true)),
		"include_hidden": bool(params.get("include_hidden", false)),
		"include_dependencies": include_dependencies,
		"include_nodes": include_nodes,
		"extensions": extensions,
		"name": name_filter,
		"name_contains": name_contains,
		"root_name": root_name,
		"root_class": root_class,
		"scenes": scenes,
		"count": scenes.size(),
		"total_matches": total_matches,
		"truncated": total_matches > scenes.size(),
		"max_results": max_results,
		"scanned": scanned,
		"max_scan_results": max_scan_results,
		"scan_truncated": entries.size() >= max_scan_results,
	}
	_record_event("scene.files", {
		"path": path,
		"name": name_filter,
		"name_contains": name_contains,
		"root_name": root_name,
		"root_class": root_class,
		"count": scenes.size(),
		"total_matches": total_matches,
		"truncated": total_matches > scenes.size(),
	})
	return _ok(summary)


func _rpc_scene_file_describe(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	if not FileAccess.file_exists(path):
		return _fail("Scene file not found: %s" % path)
	var extension := path.get_extension().to_lower()
	if not extension in ["tscn", "scn"]:
		return _fail("Scene file must be .tscn or .scn: %s" % path, -32602)
	var include_dependencies := bool(params.get("include_dependencies", true))
	var include_nodes := bool(params.get("include_nodes", true))
	var include_properties := bool(params.get("include_properties", false))
	var include_resources := bool(params.get("include_resources", true))
	var include_connections := bool(params.get("include_connections", true))
	var summary := _scene_file_summary(
		path,
		include_dependencies,
		include_nodes,
		include_properties,
		include_resources,
		include_connections
	)
	if bool(params.get("include_source", false)):
		summary["source"] = FileAccess.get_file_as_string(path)
	_record_event("scene.file.describe", {
		"path": path,
		"root_name": String(summary.get("root_name", "")),
		"root_class": String(summary.get("root_class", "")),
		"node_count": int(summary.get("node_count", 0)),
		"connection_count": int(summary.get("connection_count", 0)),
	})
	return _ok(summary)


func _rpc_scene_change(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	if path == "":
		return _fail("path is required", -32602)
	if editor_interface != null and bool(params.get("editor_open", false)):
		editor_interface.open_scene_from_path(path)
		_record_event("scene.change", {"path": path, "mode": "editor_open"})
		return _ok(_current_scene_info())
	var error := get_tree().change_scene_to_file(path)
	if error != OK:
		return _fail("Failed to change scene to %s: %s" % [path, error])
	_record_event("scene.change", {"path": path, "mode": "runtime"})
	return _ok({"requested_path": path, "error": error})


func _rpc_scene_reload() -> Dictionary:
	var error := get_tree().reload_current_scene()
	if error != OK:
		return _fail("Failed to reload current scene: %s" % error)
	_record_event("scene.reload", {})
	return _ok({"reloaded": true})


func _current_scene_info() -> Dictionary:
	var current := get_tree().get_current_scene()
	if current == null:
		return {"path": "", "name": "", "scene_file_path": "", "class": ""}
	return {
		"path": str(current.get_path()),
		"name": current.name,
		"scene_file_path": current.scene_file_path,
		"class": current.get_class(),
	}


func _rpc_scene_new(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("scene.new requires the editor plugin")
	var node_class := String(params.get("class", "Node2D"))
	if not ClassDB.can_instantiate(node_class):
		return _fail("Cannot instantiate class: %s" % node_class)
	var root = ClassDB.instantiate(node_class)
	if not (root is Node):
		return _fail("Class is not a Node: %s" % node_class)
	root.name = String(params.get("name", "Main"))
	if bool(params.get("close_existing", true)) and editor_interface.get_edited_scene_root() != null:
		var close_error: int = editor_interface.close_scene()
		if close_error != OK:
			return _fail("Failed to close current scene before creating a new one: %s" % close_error)
	editor_interface.add_root_node(root)
	if not root.is_inside_tree():
		return _fail("Failed to add root node; editor still has an active root")
	editor_interface.mark_scene_as_unsaved()
	_record_event("scene.new", {
		"path": str(root.get_path()),
		"class": node_class,
		"name": root.name,
		"close_existing": bool(params.get("close_existing", true)),
	})
	return _ok(_node_summary(root))


func _rpc_scene_open(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("scene.open requires the editor plugin")
	var path := String(params.get("path", ""))
	if path == "":
		return _fail("path is required", -32602)
	editor_interface.open_scene_from_path(path)
	_record_event("scene.open", {"path": path})
	return _ok({"path": path})


func _rpc_scene_save(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("scene.save requires the editor plugin")
	var path := String(params.get("path", ""))
	var error := OK
	if path == "":
		error = editor_interface.save_scene()
		if error != OK:
			return _fail("Failed to save scene: %s" % error)
	else:
		editor_interface.save_scene_as(path, false)
		if not FileAccess.file_exists(path):
			return _fail("Scene save did not produce a file: %s" % path)
	_record_event("scene.save", {"path": path})
	return _ok({"saved": true, "path": path})


func _rpc_editor_play(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("editor.play requires the editor plugin")
	var scene := String(params.get("scene", "current"))
	if scene == "main":
		editor_interface.play_main_scene()
	elif scene == "current":
		editor_interface.play_current_scene()
	else:
		editor_interface.play_custom_scene(scene)
	_record_event("editor.play", {"scene": scene})
	return _ok({"playing": true, "scene": scene})


func _rpc_editor_stop() -> Dictionary:
	if editor_interface == null:
		return _fail("editor.stop requires the editor plugin")
	editor_interface.stop_playing_scene()
	_record_event("editor.stop", {})
	return _ok({"playing": false})


func _rpc_editor_status() -> Dictionary:
	return _ok(_editor_status_payload())


func _rpc_editor_ui_status() -> Dictionary:
	return _ok(_editor_ui_status_payload())


func _rpc_editor_ui_switch_main_screen(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("editor.ui.switch_main_screen requires the editor plugin")
	if not editor_interface.has_method("set_main_screen_editor"):
		return _fail("EditorInterface.set_main_screen_editor is unavailable")
	var name := String(params.get("name", params.get("screen", ""))).strip_edges()
	if name == "":
		return _fail("name is required", -32602)
	var before := _editor_ui_status_payload()
	editor_interface.call("set_main_screen_editor", name)
	var after := _editor_ui_status_payload()
	var result := {
		"name": name,
		"requested": name,
		"before": before,
		"ui": after,
		"main_screen": after.get("main_screen", {}),
		"main_screen_name": after.get("main_screen_name", ""),
		"main_screen_path": after.get("main_screen_path", ""),
		"changed": String(before.get("main_screen_name", "")) != String(after.get("main_screen_name", "")) or String(before.get("main_screen_path", "")) != String(after.get("main_screen_path", "")),
		"matched": _editor_ui_main_screen_name_matches(after, name),
	}
	_record_event("editor.ui.switch_main_screen", {
		"name": name,
		"main_screen_name": result.get("main_screen_name", ""),
		"matched": result.get("matched", false),
	})
	return _ok(result)


func _rpc_editor_ui_hide_bottom_panel() -> Dictionary:
	if editor_plugin == null:
		return _fail("editor.ui.hide_bottom_panel requires the editor plugin")
	if not editor_plugin.has_method("hide_bottom_panel"):
		return _fail("EditorPlugin.hide_bottom_panel is unavailable")
	var before := _editor_ui_status_payload()
	editor_plugin.call("hide_bottom_panel")
	var after := _editor_ui_status_payload()
	var result := {
		"hidden": true,
		"before": before,
		"ui": after,
		"bottom_panel": after.get("bottom_panel", {}),
	}
	var bottom_panel = after.get("bottom_panel", {})
	var can_read_visibility := false
	if bottom_panel is Dictionary:
		can_read_visibility = bool(bottom_panel.get("can_read_visibility", false))
	_record_event("editor.ui.hide_bottom_panel", {
		"hidden": true,
		"can_read_visibility": can_read_visibility,
	})
	return _ok(result)


func _rpc_editor_history(params: Dictionary) -> Dictionary:
	var context := _editor_undo_context(params)
	if not bool(context.get("ok", false)):
		return _fail(String(context.get("error", "Editor undo history is unavailable")))
	return _ok(_editor_undo_summary(context))


func _rpc_editor_undo(params: Dictionary) -> Dictionary:
	var context := _editor_undo_context(params)
	if not bool(context.get("ok", false)):
		return _fail(String(context.get("error", "Editor undo history is unavailable")))
	var before := _editor_undo_summary(context)
	if bool(before.get("can_undo", false)):
		context["history"].call("undo")
	var after := _editor_undo_summary(context)
	after["action"] = "undo"
	after["changed"] = bool(before.get("can_undo", false))
	after["before"] = before
	_record_event("editor.undo", {
		"history_id": after.get("history_id", 0),
		"root": params.get("root", "edited"),
		"selector": params.get("selector", null),
		"changed": after.get("changed", false),
	})
	return _ok(after)


func _rpc_editor_redo(params: Dictionary) -> Dictionary:
	var context := _editor_undo_context(params)
	if not bool(context.get("ok", false)):
		return _fail(String(context.get("error", "Editor undo history is unavailable")))
	var before := _editor_undo_summary(context)
	if bool(before.get("can_redo", false)):
		context["history"].call("redo")
	var after := _editor_undo_summary(context)
	after["action"] = "redo"
	after["changed"] = bool(before.get("can_redo", false))
	after["before"] = before
	_record_event("editor.redo", {
		"history_id": after.get("history_id", 0),
		"root": params.get("root", "edited"),
		"selector": params.get("selector", null),
		"changed": after.get("changed", false),
	})
	return _ok(after)


func _editor_status_payload() -> Dictionary:
	var edited := _edited_scene_root()
	var status := {
		"editor": editor_interface != null,
		"open_scenes": [] if editor_interface == null else editor_interface.get_open_scenes(),
		"edited_scene": "" if edited == null else str(edited.get_path()),
		"edited_scene_name": "" if edited == null else edited.name,
		"edited_scene_file_path": "" if edited == null else edited.scene_file_path,
		"selection": {"nodes": [], "count": 0},
		"playing": false,
		"playing_scene": "",
		"ui": _editor_ui_status_payload(),
		"script_editor": _editor_script_status_payload(),
	}
	if editor_interface == null:
		return status
	status["selection"] = _editor_selection_payload()
	if editor_interface.has_method("is_playing_scene"):
		status["playing"] = bool(editor_interface.call("is_playing_scene"))
	if editor_interface.has_method("get_playing_scene"):
		status["playing_scene"] = String(editor_interface.call("get_playing_scene"))
	return status


func _editor_ui_status_payload() -> Dictionary:
	var status := {
		"available": editor_interface != null,
		"has_base_control": false,
		"base_control": {},
		"can_get_main_screen": false,
		"can_set_main_screen": false,
		"can_list_main_screens": false,
		"main_screen": {},
		"main_screen_name": "",
		"main_screen_api_name": "",
		"main_screen_path": "",
		"main_screen_container": {},
		"main_screens": [],
		"main_screens_source": "unsupported",
		"main_screens_heuristic": false,
		"bottom_panel": {},
		"capabilities": {},
	}
	var base = null
	if editor_interface != null and editor_interface.has_method("get_base_control"):
		base = editor_interface.call("get_base_control")
	if base is Node:
		status["has_base_control"] = true
		status["base_control"] = _editor_ui_node_status(base)

	if editor_interface != null:
		status["can_get_main_screen"] = editor_interface.has_method("get_editor_main_screen")
		status["can_set_main_screen"] = editor_interface.has_method("set_main_screen_editor")
		if bool(status["can_get_main_screen"]):
			var main_screen = editor_interface.call("get_editor_main_screen")
			if main_screen is Node:
				var container_status := _editor_ui_node_status(main_screen)
				var active_screen := _editor_active_main_screen_payload(main_screen)
				status["main_screen_container"] = container_status
				status["main_screen"] = active_screen.get("node", container_status)
				status["main_screen_name"] = active_screen.get("api_name", String((main_screen as Node).name))
				status["main_screen_api_name"] = active_screen.get("api_name", "")
				status["main_screen_path"] = active_screen.get("path", str((main_screen as Node).get_path()))
				var candidates := _editor_main_screen_candidates(main_screen)
				status["main_screens"] = candidates.get("screens", [])
				status["main_screens_source"] = candidates.get("source", "unsupported")
				status["main_screens_heuristic"] = bool(candidates.get("heuristic", false))

	status["bottom_panel"] = _editor_bottom_panel_status_payload(base)
	status["capabilities"] = _editor_ui_capabilities()
	return status


func _editor_active_main_screen_payload(main_screen: Node) -> Dictionary:
	for child in main_screen.get_children():
		if not (child is Control):
			continue
		var summary := _editor_ui_node_status(child)
		if not bool(summary.get("visible_in_tree", false)):
			continue
		var api_name := _editor_main_screen_api_name_for_node(child)
		if api_name == "":
			api_name = String(child.name)
		summary["api_name"] = api_name
		return {
			"api_name": api_name,
			"path": str((child as Node).get_path()),
			"node": summary,
			"source": "visible_main_screen_child",
			"heuristic": true,
		}
	return {
		"api_name": String(main_screen.name),
		"path": str(main_screen.get_path()),
		"node": _editor_ui_node_status(main_screen),
		"source": "get_editor_main_screen",
		"heuristic": true,
	}


func _editor_main_screen_api_name_for_node(node: Node) -> String:
	return _editor_main_screen_api_name_for_node_depth(node, 0, 4)


func _editor_main_screen_api_name_for_node_depth(node: Node, depth: int, max_depth: int) -> String:
	if node.is_class("CanvasItemEditor"):
		return "2D"
	if node.is_class("Node3DEditor"):
		return "3D"
	if node.is_class("ScriptEditor"):
		return "Script"
	if node.is_class("EditorAssetLibrary"):
		return "AssetLib"
	if node.is_class("GameView"):
		return "Game"
	if depth >= max_depth:
		return ""
	for child in node.get_children():
		if not (child is Node):
			continue
		var child_api_name := _editor_main_screen_api_name_for_node_depth(child, depth + 1, max_depth)
		if child_api_name != "":
			return child_api_name
	return ""


func _editor_ui_main_screen_name_matches(status: Dictionary, expected: String) -> bool:
	var expected_text := expected.strip_edges()
	if expected_text == "":
		return false
	var candidates := [
		status.get("main_screen_name", ""),
		status.get("main_screen_api_name", ""),
		status.get("main_screen_path", ""),
	]
	var main_screen = status.get("main_screen", {})
	if main_screen is Dictionary:
		candidates.append(main_screen.get("name", ""))
		candidates.append(main_screen.get("api_name", ""))
		candidates.append(main_screen.get("path", ""))
		candidates.append(main_screen.get("class", ""))
	for candidate in candidates:
		var candidate_text := String(candidate)
		if candidate_text == expected_text:
			return true
		if candidate_text.get_file() == expected_text:
			return true
	return false


func _editor_ui_capabilities() -> Dictionary:
	return {
		"get_base_control": editor_interface != null and editor_interface.has_method("get_base_control"),
		"get_editor_main_screen": editor_interface != null and editor_interface.has_method("get_editor_main_screen"),
		"set_main_screen_editor": editor_interface != null and editor_interface.has_method("set_main_screen_editor"),
		"bottom_panel_make_visible": editor_plugin != null and editor_plugin.has_method("make_bottom_panel_item_visible"),
		"bottom_panel_hide": editor_plugin != null and editor_plugin.has_method("hide_bottom_panel"),
		"bottom_panel_list_items": false,
		"bottom_panel_read_visibility": false,
	}


func _editor_ui_node_status(node: Node) -> Dictionary:
	var summary := _node_summary(node)
	var visible := true
	var visible_in_tree := true
	if node is CanvasItem:
		visible = (node as CanvasItem).visible
		visible_in_tree = (node as CanvasItem).is_visible_in_tree()
	elif node is Window:
		visible = (node as Window).visible
		visible_in_tree = visible
	summary["visible"] = visible
	summary["visible_in_tree"] = visible_in_tree
	var bounds := _node_bounds(node)
	if not bounds.is_empty():
		summary["bounds"] = bounds
	return summary


func _editor_main_screen_candidates(main_screen: Node) -> Dictionary:
	var screens := []
	for child in main_screen.get_children():
		if screens.size() >= 32:
			break
		if not (child is Control):
			continue
		var summary := _editor_ui_node_status(child)
		var api_name := _editor_main_screen_api_name_for_node(child)
		if api_name != "":
			summary["api_name"] = api_name
		summary["selected"] = bool(summary.get("visible_in_tree", false))
		screens.append(summary)
	return {
		"screens": screens,
		"source": "get_editor_main_screen_children",
		"heuristic": true,
	}


func _editor_bottom_panel_status_payload(base: Variant = null) -> Dictionary:
	var can_make_visible: bool = editor_plugin != null and editor_plugin.has_method("make_bottom_panel_item_visible")
	var can_hide: bool = editor_plugin != null and editor_plugin.has_method("hide_bottom_panel")
	var payload := {
		"available": can_make_visible or can_hide,
		"can_make_visible": can_make_visible,
		"can_hide": can_hide,
		"can_list_items": false,
		"can_read_visibility": false,
		"visible": null,
		"items": [],
		"hints": [],
		"hint_count": 0,
	}
	if base is Node:
		var hints := []
		_collect_editor_ui_name_hints(base, ["bottom", "panel"], hints, 12, 0, 8)
		payload["hints"] = hints
		payload["hint_count"] = hints.size()
	return payload


func _collect_editor_ui_name_hints(node: Node, needles: Array, entries: Array, limit: int, depth: int, max_depth: int) -> void:
	if entries.size() >= limit or depth > max_depth:
		return
	var haystack := ("%s %s" % [String(node.name), node.get_class()]).to_lower()
	var matched := false
	for needle in needles:
		if haystack.contains(String(needle).to_lower()):
			matched = true
			break
	if matched:
		entries.append(_editor_ui_node_status(node))
		if entries.size() >= limit:
			return
	for child in node.get_children():
		if child is Node:
			_collect_editor_ui_name_hints(child, needles, entries, limit, depth + 1, max_depth)
			if entries.size() >= limit:
				return


func _editor_undo_manager() -> Variant:
	if editor_interface == null:
		return null
	if not editor_interface.has_method("get_editor_undo_redo"):
		return null
	return editor_interface.call("get_editor_undo_redo")


func _editor_undo_context(params: Dictionary = {}) -> Dictionary:
	if editor_interface == null:
		return {"ok": false, "error": "editor undo/redo requires the editor plugin"}
	var manager = _editor_undo_manager()
	if manager == null:
		return {"ok": false, "error": "EditorInterface.get_editor_undo_redo is unavailable"}
	var target: Object = null
	var history_id := int(params.get("history_id", -1))
	if history_id < 0:
		if params.has("selector") or params.has("node"):
			target = _resolve_node(params.get("selector", params.get("node", {})), params.get("root", "edited"))
			if target == null:
				return {"ok": false, "error": "Undo history target node not found"}
		else:
			target = _edited_scene_root()
		if target != null and manager.has_method("get_object_history_id"):
			history_id = int(manager.call("get_object_history_id", target))
		else:
			history_id = 0
	var history = null
	if manager.has_method("get_history_undo_redo"):
		history = manager.call("get_history_undo_redo", history_id)
	else:
		history = manager
	if history == null:
		return {"ok": false, "error": "UndoRedo history is unavailable for id %s" % history_id}
	return {
		"ok": true,
		"manager": manager,
		"history": history,
		"history_id": history_id,
		"target": target,
	}


func _editor_undo_summary(context: Dictionary) -> Dictionary:
	var history = context.get("history", null)
	var target = context.get("target", null)
	var summary := {
		"available": history != null,
		"history_id": int(context.get("history_id", 0)),
		"can_undo": false,
		"can_redo": false,
		"version": -1,
		"current_action_name": "",
		"target": null,
	}
	if target is Object and is_instance_valid(target):
		if target is Node:
			summary["target"] = _node_summary(target)
		elif target is Resource:
			summary["target"] = _resource_summary(target)
	if history == null:
		return summary
	if history.has_method("has_undo"):
		summary["can_undo"] = bool(history.call("has_undo"))
	if history.has_method("has_redo"):
		summary["can_redo"] = bool(history.call("has_redo"))
	if history.has_method("get_version"):
		summary["version"] = int(history.call("get_version"))
	if history.has_method("get_current_action_name"):
		summary["current_action_name"] = String(history.call("get_current_action_name"))
	return summary


func _should_use_editor_undo(params: Dictionary) -> bool:
	return editor_interface != null and bool(params.get("undo", true))


func _commit_editor_property_action(node: Node, property: String, value: Variant, previous: Variant, action_name: String) -> bool:
	var manager = _editor_undo_manager()
	if manager == null or not manager.has_method("create_action"):
		return false
	manager.call("create_action", action_name)
	manager.call("add_do_property", node, property, value)
	manager.call("add_undo_property", node, property, previous)
	if editor_interface != null:
		manager.call("add_do_method", editor_interface, "mark_scene_as_unsaved")
		manager.call("add_undo_method", editor_interface, "mark_scene_as_unsaved")
	manager.call("commit_action")
	return true


func _commit_editor_properties_action(node: Node, values: Dictionary, previous_values: Dictionary, action_name: String) -> bool:
	var previous_by_node := {}
	previous_by_node[node.get_instance_id()] = previous_values
	return _commit_editor_nodes_properties_action(
		[node],
		values,
		previous_by_node,
		action_name
	)


func _commit_editor_nodes_properties_action(nodes: Array, values: Dictionary, previous_by_node: Dictionary, action_name: String) -> bool:
	var manager = _editor_undo_manager()
	if manager == null or not manager.has_method("create_action"):
		return false
	manager.call("create_action", action_name)
	for node in nodes:
		if not (node is Node):
			continue
		var node_previous: Dictionary = previous_by_node.get(node.get_instance_id(), {})
		for property in values.keys():
			var property_name := String(property)
			manager.call("add_do_property", node, property_name, values[property])
			manager.call("add_undo_property", node, property_name, node_previous.get(property_name, null))
	if editor_interface != null:
		manager.call("add_do_method", editor_interface, "mark_scene_as_unsaved")
		manager.call("add_undo_method", editor_interface, "mark_scene_as_unsaved")
	manager.call("commit_action")
	return true


func _commit_editor_metadata_set_action(node: Node, values: Dictionary, previous: Dictionary, action_name: String) -> bool:
	var manager = _editor_undo_manager()
	if manager == null or not manager.has_method("create_action"):
		return false
	manager.call("create_action", action_name)
	for name in values.keys():
		var metadata_name := StringName(String(name))
		var previous_info: Dictionary = previous.get(String(name), {})
		manager.call("add_do_method", node, "set_meta", metadata_name, values[name])
		if bool(previous_info.get("exists", false)):
			manager.call("add_undo_method", node, "set_meta", metadata_name, previous_info.get("value"))
		else:
			manager.call("add_undo_method", node, "remove_meta", metadata_name)
	if editor_interface != null:
		manager.call("add_do_method", editor_interface, "mark_scene_as_unsaved")
		manager.call("add_undo_method", editor_interface, "mark_scene_as_unsaved")
	manager.call("commit_action")
	return true


func _commit_editor_metadata_remove_action(node: Node, names: Array, previous: Dictionary, action_name: String) -> bool:
	var manager = _editor_undo_manager()
	if manager == null or not manager.has_method("create_action"):
		return false
	manager.call("create_action", action_name)
	for name in names:
		var metadata_name := StringName(String(name))
		var previous_info: Dictionary = previous.get(String(name), {})
		manager.call("add_do_method", node, "remove_meta", metadata_name)
		if bool(previous_info.get("exists", false)):
			manager.call("add_undo_method", node, "set_meta", metadata_name, previous_info.get("value"))
		else:
			manager.call("add_undo_method", node, "remove_meta", metadata_name)
	if editor_interface != null:
		manager.call("add_do_method", editor_interface, "mark_scene_as_unsaved")
		manager.call("add_undo_method", editor_interface, "mark_scene_as_unsaved")
	manager.call("commit_action")
	return true


func _commit_editor_create_node_action(parent: Node, node: Node, owner_scene: Variant, action_name: String) -> bool:
	var manager = _editor_undo_manager()
	if manager == null or not manager.has_method("create_action"):
		return false
	manager.call("create_action", action_name)
	manager.call("add_do_method", parent, "add_child", node)
	manager.call("add_do_method", self, "_set_node_owner_for_undo", node, owner_scene)
	manager.call("add_do_reference", node)
	manager.call("add_undo_method", parent, "remove_child", node)
	if editor_interface != null:
		manager.call("add_do_method", editor_interface, "mark_scene_as_unsaved")
		manager.call("add_undo_method", editor_interface, "mark_scene_as_unsaved")
	manager.call("commit_action")
	return node.is_inside_tree()


func _set_node_owner_for_undo(node: Variant, owner_scene: Variant) -> void:
	if node is Node and is_instance_valid(node):
		if owner_scene is Node and is_instance_valid(owner_scene) and node != owner_scene:
			node.owner = owner_scene


func _rpc_editor_selection_get() -> Dictionary:
	if editor_interface == null:
		return _fail("editor.selection.get requires the editor plugin")
	return _ok(_editor_selection_payload())


func _editor_selection_payload() -> Dictionary:
	var nodes := []
	if editor_interface == null or not editor_interface.has_method("get_selection"):
		return {"nodes": nodes, "count": 0}
	var selection = editor_interface.call("get_selection")
	if selection == null:
		return {"nodes": nodes, "count": 0}
	for node in selection.call("get_selected_nodes"):
		if node is Node:
			nodes.append(_node_summary(node))
	return {"nodes": nodes, "count": nodes.size()}


func _rpc_editor_selection_set(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("editor.selection.set requires the editor plugin")
	var selection = editor_interface.call("get_selection")
	if selection == null:
		return _fail("Editor selection is unavailable")
	var selectors = params.get("selectors", [])
	if typeof(selectors) != TYPE_ARRAY:
		return _fail("selectors must be an array", -32602)
	if selectors.is_empty():
		if params.has("selector"):
			selectors = [params.get("selector")]
		elif params.has("path"):
			selectors = [{"path": String(params.get("path", ""))}]
	if selectors.is_empty():
		return _fail("selector, path, or selectors is required", -32602)

	var root_spec = params.get("root", "edited")
	var nodes := []
	for selector in selectors:
		var node := _resolve_node(selector, root_spec)
		if node == null:
			return _fail("Node not found for selection: %s" % str(selector))
		nodes.append(node)

	if selection.has_method("clear"):
		selection.call("clear")
	for node in nodes:
		selection.call("add_node", node)
	if bool(params.get("inspect", false)) and not nodes.is_empty():
		_inspect_object(nodes[0], String(params.get("property", "")), bool(params.get("inspector_only", false)))
	var encoded := []
	for node in nodes:
		encoded.append(_node_summary(node))
	_record_event("editor.selection.set", {
		"selectors": selectors,
		"root": root_spec,
		"inspect": bool(params.get("inspect", false)),
		"property": String(params.get("property", "")),
		"inspector_only": bool(params.get("inspector_only", false)),
		"count": encoded.size(),
		"nodes": encoded,
	})
	return _ok({"nodes": encoded, "count": encoded.size()})


func _rpc_editor_inspect(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("editor.inspect requires the editor plugin")
	var target = _editor_target_from_params(params)
	if target == null:
		return _fail("Inspectable target not found")
	var for_property := String(params.get("property", params.get("for_property", "")))
	var inspector_only := bool(params.get("inspector_only", false))
	if not _inspect_object(target, for_property, inspector_only):
		return _fail("EditorInterface.inspect_object is unavailable")
	_record_event("editor.inspect", {
		"selector": params.get("selector", null),
		"path": params.get("path", ""),
		"resource_path": params.get("resource_path", ""),
		"root": params.get("root", "edited"),
		"selected": bool(params.get("selected", false)),
		"target": _object_summary(target),
		"property": for_property,
		"inspector_only": inspector_only,
	})
	return _ok({
		"target": _object_summary(target),
		"property": for_property,
		"inspector_only": inspector_only,
	})


func _rpc_editor_inspector_describe(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("editor.inspector.describe requires the editor plugin")
	var target = _editor_target_from_params_or_selection(params)
	if target == null:
		return _fail("Inspectable target not found")
	var properties := _inspector_property_summaries(
		target,
		bool(params.get("include_values", true)),
		params.get("properties", []),
		String(params.get("name_contains", "")),
		bool(params.get("include_internal", false))
	)
	if bool(params.get("inspect", false)):
		_inspect_object(target, String(params.get("property", "")), bool(params.get("inspector_only", false)))
	return _ok({
		"target": _object_summary(target),
		"properties": properties,
		"count": properties.size(),
	})


func _rpc_editor_inspector_get_property(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("editor.inspector.get_property requires the editor plugin")
	var target = _editor_target_from_params_or_selection(params)
	if target == null:
		return _fail("Inspectable target not found")
	var property := String(params.get("property", ""))
	if property == "":
		return _fail("property is required", -32602)
	return _ok({
		"target": _object_summary(target),
		"property": _inspector_property_summary(target, property, true),
		"value": _encode_value(target.get(property)),
	})


func _rpc_editor_inspector_set_property(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("editor.inspector.set_property requires the editor plugin")
	var target = _editor_target_from_params_or_selection(params)
	if target == null:
		return _fail("Inspectable target not found")
	var property := String(params.get("property", ""))
	if property == "":
		return _fail("property is required", -32602)
	if not params.has("value"):
		return _fail("value is required", -32602)
	target.set(property, _decode_value(params.get("value")))
	var saved := false
	if target is Node and editor_interface != null:
		editor_interface.mark_scene_as_unsaved()
	elif target is Resource:
		if bool(params.get("save", false)) and target.resource_path != "":
			var save_error := ResourceSaver.save(target, target.resource_path)
			if save_error != OK:
				return _fail("Failed to save resource %s: %s" % [target.resource_path, save_error])
			_scan_editor_filesystem(target.resource_path)
			saved = true
	if bool(params.get("inspect", true)):
		_inspect_object(target, property, bool(params.get("inspector_only", false)))
	_record_event("editor.inspector.set_property", {
		"selector": params.get("selector", null),
		"path": params.get("path", ""),
		"resource_path": params.get("resource_path", ""),
		"root": params.get("root", "edited"),
		"target": _object_summary(target),
		"property": property,
		"value": params.get("value"),
		"save": bool(params.get("save", false)),
		"inspect": bool(params.get("inspect", true)),
		"inspector_only": bool(params.get("inspector_only", false)),
		"saved": saved,
	})
	return _ok({
		"target": _object_summary(target),
		"property": _inspector_property_summary(target, property, true),
		"value": _encode_value(target.get(property)),
		"saved": saved,
	})


func _rpc_editor_inspector_set_properties(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("editor.inspector.set_properties requires the editor plugin")
	var target = _editor_target_from_params_or_selection(params)
	if target == null:
		return _fail("Inspectable target not found")
	var values = params.get("values", params.get("properties", {}))
	if typeof(values) != TYPE_DICTIONARY:
		return _fail("values must be a dictionary", -32602)
	if values.is_empty():
		return _fail("values must not be empty", -32602)
	var property_names := []
	for key in values.keys():
		var property := String(key)
		property_names.append(property)
		target.set(property, _decode_value(values[key]))
	var saved := false
	if target is Node and editor_interface != null:
		editor_interface.mark_scene_as_unsaved()
	elif target is Resource:
		if bool(params.get("save", false)) and target.resource_path != "":
			var save_error := ResourceSaver.save(target, target.resource_path)
			if save_error != OK:
				return _fail("Failed to save resource %s: %s" % [target.resource_path, save_error])
			_scan_editor_filesystem(target.resource_path)
			saved = true
	if bool(params.get("inspect", true)):
		_inspect_object(target, String(property_names[0]), bool(params.get("inspector_only", false)))
	var properties := []
	var encoded_values := {}
	for property in property_names:
		properties.append(_inspector_property_summary(target, property, true))
		encoded_values[property] = _encode_value(target.get(property))
	_record_event("editor.inspector.set_properties", {
		"selector": params.get("selector", null),
		"path": params.get("path", ""),
		"resource_path": params.get("resource_path", ""),
		"root": params.get("root", "edited"),
		"target": _object_summary(target),
		"values": values,
		"properties": property_names,
		"count": property_names.size(),
		"save": bool(params.get("save", false)),
		"inspect": bool(params.get("inspect", true)),
		"inspector_only": bool(params.get("inspector_only", false)),
		"saved": saved,
	})
	return _ok({
		"target": _object_summary(target),
		"properties": properties,
		"values": encoded_values,
		"count": property_names.size(),
		"saved": saved,
	})


func _rpc_editor_script_open(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("editor.script.open requires the editor plugin")
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	if not ResourceLoader.exists(path):
		return _fail("Script resource not found: %s" % path)
	var script := ResourceLoader.load(path)
	if script == null or not (script is Script):
		return _fail("Resource is not a Script: %s" % path)
	var line := int(params.get("line", -1))
	var column := int(params.get("column", 0))
	if DisplayServer.get_name() == "headless" and not bool(params.get("force", false)):
		_record_event("editor.script.open", {
			"path": path,
			"line": line,
			"column": column,
			"grab_focus": bool(params.get("grab_focus", true)),
			"force": bool(params.get("force", false)),
			"restore_external_editor": bool(params.get("restore_external_editor", false)),
			"opened": false,
			"reason": "headless",
		})
		return _ok({
			"script": _resource_summary(script),
			"path": path,
			"line": line,
			"column": column,
			"opened": false,
			"reason": "headless",
			"script_editor": _editor_script_status_payload(),
		})
	if not editor_interface.has_method("edit_script"):
		return _fail("EditorInterface.edit_script is unavailable")
	var grab_focus := bool(params.get("grab_focus", true))
	var forced_internal := _set_external_script_editor(false)
	editor_interface.callv("edit_script", [script, line, column, grab_focus])
	if bool(params.get("restore_external_editor", false)) and not forced_internal.is_empty():
		_restore_external_script_editor(forced_internal)
	_record_event("editor.script.open", {
		"path": path,
		"line": line,
		"column": column,
		"grab_focus": grab_focus,
		"force": bool(params.get("force", false)),
		"restore_external_editor": bool(params.get("restore_external_editor", false)),
	})
	return _ok({
		"script": _resource_summary(script),
		"path": path,
		"line": line,
		"column": column,
		"opened": true,
		"forced_internal_editor": not forced_internal.is_empty(),
		"script_editor": _editor_script_status_payload(),
	})


func _rpc_editor_script_status() -> Dictionary:
	return _ok(_editor_script_status_payload())


func _editor_script_status_payload() -> Dictionary:
	var payload := {
		"available": false,
		"has_script_editor": false,
		"can_list_open_scripts": false,
		"can_get_current_script": false,
		"open_scripts": [],
		"open_paths": [],
		"open_count": 0,
		"current_script": {},
		"current_path": "",
	}
	if editor_interface == null:
		return payload
	if not editor_interface.has_method("get_script_editor"):
		return payload
	var script_editor = editor_interface.call("get_script_editor")
	if script_editor == null:
		return payload
	payload["available"] = true
	payload["has_script_editor"] = true
	payload["can_list_open_scripts"] = script_editor.has_method("get_open_scripts")
	payload["can_get_current_script"] = script_editor.has_method("get_current_script")
	var open_scripts := []
	var open_paths := []
	if script_editor.has_method("get_open_scripts"):
		for item in script_editor.call("get_open_scripts"):
			if item is Resource:
				var summary := _resource_summary(item)
				open_scripts.append(summary)
				var script_path := String(summary.get("path", ""))
				if script_path != "":
					open_paths.append(script_path)
			elif item != null:
				open_scripts.append(_encode_value(item))
	payload["open_scripts"] = open_scripts
	payload["open_paths"] = open_paths
	payload["open_count"] = open_scripts.size()
	if script_editor.has_method("get_current_script"):
		var current = script_editor.call("get_current_script")
		if current is Resource:
			var current_summary := _resource_summary(current)
			payload["current_script"] = current_summary
			payload["current_path"] = String(current_summary.get("path", ""))
	return payload


func _rpc_editor_script_describe(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("editor.script.describe requires the editor plugin")
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	if not ResourceLoader.exists(path):
		return _fail("Script resource not found: %s" % path)
	var script := ResourceLoader.load(path)
	if script == null or not (script is Script):
		return _fail("Resource is not a Script: %s" % path)
	var source := FileAccess.get_file_as_string(path)
	var summary := _resource_summary(script)
	summary["path"] = path
	summary["global_path"] = ProjectSettings.globalize_path(path)
	summary["methods"] = _script_method_summaries(script, source)
	summary["properties"] = _script_member_summaries(script, source)
	summary["signals"] = _script_signal_summaries(script, source)
	summary["symbols"] = _script_symbols_from_source(source)
	if bool(params.get("include_source", false)):
		summary["source"] = source
	return _ok(summary)


func _rpc_script_file_describe(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	if not FileAccess.file_exists(path):
		return _fail("Script file not found: %s" % path)
	if path.get_extension().to_lower() != "gd":
		return _fail("Script file must be .gd: %s" % path, -32602)
	var summary := _script_file_summary(path, bool(params.get("include_source", false)))
	_record_event("script.file.describe", {
		"path": path,
		"class_name": String(summary.get("class_name", "")),
		"extends": String(summary.get("extends", "")),
		"function_count": int(summary.get("function_count", 0)),
		"include_source": bool(params.get("include_source", false)),
	})
	return _ok(summary)


func _rpc_script_classes(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", "res://"))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var max_results := max(1, int(params.get("max_results", 200)))
	var max_scan_results := max(max_results, int(params.get("max_scan_results", max_results * 20)))
	var include_anonymous := bool(params.get("include_anonymous", false))
	var class_filter := String(params.get("class_name", params.get("class", "")))
	var name_contains := String(params.get("name_contains", ""))
	var extends_filter := String(params.get("extends", ""))
	var base_class := String(params.get("base_class", ""))
	var filters := {"extension": "gd"}
	var entries := []
	_collect_filesystem_entries(
		path,
		bool(params.get("recursive", true)),
		false,
		bool(params.get("include_hidden", false)),
		filters,
		max_scan_results,
		entries
	)
	var parsed_entries := []
	var class_extends := {}
	var class_paths := {}
	var path_classes := {}
	for entry in entries:
		if not bool(entry.get("is_file", false)):
			continue
		var script_path := String(entry.get("path", ""))
		var source := FileAccess.get_file_as_string(script_path)
		var open_error := FileAccess.get_open_error()
		if open_error != OK:
			continue
		var symbols := _script_symbols_from_source(source)
		var script_class_name := String(symbols.get("class_name", ""))
		var script_extends := String(symbols.get("extends", ""))
		var parsed := {
			"path": script_path,
			"source": source,
			"symbols": symbols,
			"class_name": script_class_name,
			"extends": script_extends,
		}
		parsed_entries.append(parsed)
		if script_class_name != "":
			class_extends[script_class_name] = script_extends
			class_paths[script_class_name] = script_path
			path_classes[script_path] = script_class_name
	var classes := []
	var total_matches := 0
	for parsed in parsed_entries:
		var script_class_name := String(parsed.get("class_name", ""))
		if script_class_name == "" and not include_anonymous:
			continue
		var script_path := String(parsed.get("path", ""))
		var display_name := script_class_name if script_class_name != "" else script_path.get_file().get_basename()
		var script_extends := String(parsed.get("extends", ""))
		var parent_name := _script_resolved_extends_name(script_extends, path_classes)
		if class_filter != "" and script_class_name != class_filter:
			continue
		if name_contains != "" and not display_name.contains(name_contains) and not script_path.contains(name_contains):
			continue
		if extends_filter != "" and not _script_extends_matches(script_extends, extends_filter, path_classes):
			continue
		if base_class != "" and not _script_class_matches_base(script_class_name, script_extends, base_class, class_extends, path_classes):
			continue
		total_matches += 1
		if classes.size() >= max_results:
			continue
		var symbols: Dictionary = parsed.get("symbols", {})
		var is_node_class := _script_extends_or_is_class(script_class_name, script_extends, "Node", class_extends, path_classes)
		var is_resource_class := _script_extends_or_is_class(script_class_name, script_extends, "Resource", class_extends, path_classes)
		var class_entry := {
			"path": script_path,
			"global_path": ProjectSettings.globalize_path(script_path),
			"class": script_class_name,
			"class_name": script_class_name,
			"name": display_name,
			"language": "GDScript",
			"extends": script_extends,
			"parent": parent_name,
			"is_node": is_node_class,
			"is_resource": is_resource_class,
			"is_custom": script_class_name != "",
			"functions": symbols.get("functions", []),
			"function_count": Array(symbols.get("functions", [])).size(),
			"signals": symbols.get("signals", []),
			"signal_count": Array(symbols.get("signals", [])).size(),
			"variables": symbols.get("variables", []),
			"variable_count": Array(symbols.get("variables", [])).size(),
			"constants": symbols.get("constants", []),
			"constant_count": Array(symbols.get("constants", [])).size(),
		}
		classes.append(class_entry)
	classes.sort_custom(func(a, b): return String(a.get("name", a.get("path", ""))) < String(b.get("name", b.get("path", ""))))
	var summary := {
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"recursive": bool(params.get("recursive", true)),
		"include_hidden": bool(params.get("include_hidden", false)),
		"include_anonymous": include_anonymous,
		"class_name": class_filter,
		"name_contains": name_contains,
		"extends": extends_filter,
		"base_class": base_class,
		"classes": classes,
		"count": classes.size(),
		"total_matches": total_matches,
		"truncated": total_matches > classes.size(),
		"max_results": max_results,
		"scanned": parsed_entries.size(),
		"max_scan_results": max_scan_results,
		"scan_truncated": entries.size() >= max_scan_results,
	}
	_record_event("script.classes", {
		"path": path,
		"class_name": class_filter,
		"name_contains": name_contains,
		"extends": extends_filter,
		"base_class": base_class,
		"count": classes.size(),
		"total_matches": total_matches,
		"truncated": total_matches > classes.size(),
	})
	return _ok(summary)


func _rpc_editor_filesystem_scan(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("editor.filesystem.scan requires the editor plugin")
	var raw_paths = params.get("paths", [])
	if typeof(raw_paths) != TYPE_ARRAY:
		raw_paths = [params.get("path", "")]
	var paths := []
	for item in raw_paths:
		var path := String(item)
		if path == "":
			continue
		var path_error := _validate_res_path(path)
		if path_error != "":
			return _fail(path_error, -32602)
		paths.append(path)
	var requested := false
	if paths.is_empty():
		requested = _scan_editor_filesystem("")
	else:
		for path in paths:
			requested = _scan_editor_filesystem(path) or requested
	_record_event("editor.filesystem.scan", {"paths": paths, "requested": requested})
	return _ok({"paths": paths, "requested": requested})


func _rpc_editor_filesystem_describe(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("editor.filesystem.describe requires the editor plugin")
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	return _ok(_filesystem_entry(path))


func _rpc_editor_filesystem_find(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("editor.filesystem.find requires the editor plugin")
	var path := String(params.get("path", "res://"))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var recursive := bool(params.get("recursive", true))
	var include_dirs := bool(params.get("include_dirs", false))
	var include_hidden := bool(params.get("include_hidden", false))
	var max_results := max(1, int(params.get("max_results", 500)))
	var filters := {
		"name": String(params.get("name", "")),
		"name_contains": String(params.get("name_contains", "")),
		"extension": String(params.get("extension", "")),
		"resource_type": String(params.get("resource_type", "")),
	}
	var entries := []
	_collect_filesystem_entries(path, recursive, include_dirs, include_hidden, filters, max_results, entries)
	return _ok({"path": path, "entries": entries, "count": entries.size()})


func _rpc_editor_filesystem_select(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("editor.filesystem.select requires the editor plugin")
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var entry := _filesystem_entry(path)
	if not bool(entry.get("exists", false)):
		return _fail("Path not found: %s" % path)
	var selected := false
	if editor_interface.has_method("select_file"):
		editor_interface.call("select_file", path)
		selected = true
		_editor_filesystem_selected_path = path
	if bool(params.get("inspect", false)) and bool(entry.get("is_resource", false)):
		var resource := ResourceLoader.load(path)
		if resource != null:
			_inspect_object(resource)
	_record_event("editor.filesystem.select", {"path": path, "inspect": bool(params.get("inspect", false)), "selected": selected})
	entry["selected"] = selected
	return _ok(entry)


func _rpc_editor_filesystem_open(params: Dictionary) -> Dictionary:
	if editor_interface == null:
		return _fail("editor.filesystem.open requires the editor plugin")
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var entry := _filesystem_entry(path)
	if not bool(entry.get("exists", false)):
		return _fail("Path not found: %s" % path)
	var selected := false
	if editor_interface.has_method("select_file"):
		editor_interface.call("select_file", path)
		_editor_filesystem_selected_path = path
		selected = true
	var mode := String(params.get("mode", "auto")).to_lower()
	if not mode in ["auto", "scene", "script", "resource", "inspect", "select"]:
		return _fail("mode must be auto, scene, script, resource, inspect, or select", -32602)
	var action := mode
	if mode == "auto":
		action = _editor_filesystem_open_action(entry)
	var result := {
		"path": path,
		"mode": mode,
		"action": action,
		"selected": selected,
		"entry": entry,
		"opened": false,
		"inspected": false,
	}
	if action == "scene":
		if not bool(entry.get("is_file", false)):
			return _fail("Scene open requires a file: %s" % path, -32602)
		editor_interface.open_scene_from_path(path)
		result["opened"] = true
		result["scene"] = {"path": path}
	elif action == "script":
		var script_params := {
			"path": path,
			"line": int(params.get("line", -1)),
			"column": int(params.get("column", 0)),
			"grab_focus": bool(params.get("grab_focus", true)),
			"force": bool(params.get("force", false)),
			"restore_external_editor": bool(params.get("restore_external_editor", false)),
		}
		var script_result := _rpc_editor_script_open(script_params)
		if not bool(script_result.get("ok", false)):
			return script_result
		var script_value = script_result.get("value", {})
		if typeof(script_value) == TYPE_DICTIONARY:
			result["script"] = script_value
			result["opened"] = bool(script_value.get("opened", false))
	elif action == "resource" or action == "inspect":
		if not bool(entry.get("is_resource", false)):
			return _fail("Resource inspect requires a loadable resource: %s" % path, -32602)
		var resource := ResourceLoader.load(path)
		if resource == null:
			return _fail("Failed to load resource: %s" % path)
		result["resource"] = _resource_summary(resource)
		result["inspected"] = _inspect_object(
			resource,
			String(params.get("property", "")),
			bool(params.get("inspector_only", false))
		)
	elif action == "select":
		pass
	else:
		return _fail("Unsupported editor filesystem open action: %s" % action, -32602)
	result["entry"] = _filesystem_entry(path)
	_record_event("editor.filesystem.open", {
		"path": path,
		"mode": mode,
		"action": action,
		"selected": selected,
		"opened": bool(result.get("opened", false)),
		"inspected": bool(result.get("inspected", false)),
		"line": int(params.get("line", -1)),
		"column": int(params.get("column", 0)),
		"force": bool(params.get("force", false)),
	})
	return _ok(result)


func _editor_filesystem_open_action(entry: Dictionary) -> String:
	if bool(entry.get("is_directory", false)):
		return "select"
	var extension := String(entry.get("extension", "")).to_lower()
	var resource_type := String(entry.get("resource_type", ""))
	if extension in ["tscn", "scn"] or resource_type == "PackedScene":
		return "scene"
	if extension == "gd" or resource_type == "GDScript":
		return "script"
	if bool(entry.get("is_resource", false)):
		return "resource"
	return "select"


func _rpc_input_actions(params: Dictionary) -> Dictionary:
	var include_events := bool(params.get("include_events", true))
	var include_ui := bool(params.get("include_ui", true))
	var prefix := String(params.get("prefix", ""))
	var actions := []
	for action in InputMap.get_actions():
		var action_name := String(action)
		if not include_ui and action_name.begins_with("ui_"):
			continue
		if prefix != "" and not action_name.begins_with(prefix):
			continue
		actions.append(_input_action_summary(StringName(action_name), include_events))
	return _ok({"actions": actions, "count": actions.size()})


func _rpc_input_action_describe(params: Dictionary) -> Dictionary:
	var action := String(params.get("action", params.get("name", "")))
	if action == "":
		return _fail("action is required", -32602)
	return _ok(_input_action_summary(StringName(action), bool(params.get("include_events", true))))


func _rpc_input_action_configure(params: Dictionary) -> Dictionary:
	var action := String(params.get("action", params.get("name", "")))
	if action == "":
		return _fail("action is required", -32602)
	var action_name := StringName(action)
	var created := false
	if not InputMap.has_action(action_name):
		if not bool(params.get("create", true)):
			return _fail("Input action not found: %s" % action, -32602)
		InputMap.add_action(action_name, float(params.get("deadzone", 0.5)))
		created = true
	elif params.has("deadzone"):
		InputMap.action_set_deadzone(action_name, float(params.get("deadzone", 0.5)))

	var replaced := bool(params.get("replace", params.get("clear", false)))
	if replaced:
		InputMap.action_erase_events(action_name)

	var event_specs := _input_event_specs_from_params(params)
	var added_events := []
	var existing_events := []
	for spec in event_specs:
		var event := _input_event_from_spec(spec)
		if event == null:
			return _fail("Could not create input event from spec: %s" % str(spec), -32602)
		var summary := _input_event_summary(event)
		if InputMap.action_has_event(action_name, event):
			existing_events.append(summary)
		else:
			InputMap.action_add_event(action_name, event)
			added_events.append(summary)

	var result := _input_action_summary(action_name, true)
	result["created"] = created
	result["replaced"] = replaced
	result["added_events"] = added_events
	result["existing_events"] = existing_events
	_record_event("input.action.configure", {
		"action": action,
		"deadzone": params.get("deadzone", null),
		"events": event_specs,
		"replace": replaced,
		"create": bool(params.get("create", true)),
		"created": created,
		"replaced": replaced,
		"added_events": added_events.size(),
		"existing_events": existing_events.size(),
	})
	return _ok(result)


func _rpc_input_action_erase(params: Dictionary) -> Dictionary:
	var action := String(params.get("action", params.get("name", "")))
	if action == "":
		return _fail("action is required", -32602)
	var action_name := StringName(action)
	if not InputMap.has_action(action_name):
		return _ok({"action": action, "exists": false, "erased": false, "events_erased": 0})

	var event_specs := _input_event_specs_from_params(params)
	var erased_events := []
	if not event_specs.is_empty():
		for spec in event_specs:
			var event := _input_event_from_spec(spec)
			if event == null:
				return _fail("Could not create input event from spec: %s" % str(spec), -32602)
			if InputMap.action_has_event(action_name, event):
				InputMap.action_erase_event(action_name, event)
				erased_events.append(_input_event_summary(event))
	elif bool(params.get("events_only", params.get("clear_events", false))):
		for event in InputMap.action_get_events(action_name):
			erased_events.append(_input_event_summary(event))
		InputMap.action_erase_events(action_name)
	else:
		for event in InputMap.action_get_events(action_name):
			erased_events.append(_input_event_summary(event))
		InputMap.erase_action(action_name)
		_record_event("input.action.erase", {
			"action": action,
			"events": event_specs,
			"events_only": bool(params.get("events_only", params.get("clear_events", false))),
			"erased": true,
			"events_erased": erased_events.size(),
		})
		return _ok({"action": action, "exists": false, "erased": true, "events_erased": erased_events.size()})

	var result := _input_action_summary(action_name, true)
	result["erased"] = false
	result["events_erased"] = erased_events.size()
	result["erased_events"] = erased_events
	_record_event("input.action.erase", {
		"action": action,
		"events": event_specs,
		"events_only": bool(params.get("events_only", params.get("clear_events", false))),
		"erased": false,
		"events_erased": erased_events.size(),
	})
	return _ok(result)


func _rpc_input_action(params: Dictionary) -> Dictionary:
	var action := String(params.get("action", ""))
	if action == "":
		return _fail("action is required", -32602)
	var pressed := bool(params.get("pressed", true))
	var strength := float(params.get("strength", 1.0))
	if pressed:
		Input.action_press(action, strength)
	else:
		Input.action_release(action)
	_record_event("input.action", {
		"action": action,
		"pressed": pressed,
		"strength": strength,
	})
	return _ok({"action": action, "pressed": pressed})


func _rpc_input_joypad(params: Dictionary) -> Dictionary:
	var event_type := String(params.get("type", ""))
	if event_type == "":
		event_type = "axis" if params.has("axis") or params.has("axis_index") else "button"
	var device := int(params.get("device", 0))
	match event_type:
		"button", "down", "up":
			var button = params.get("button", params.get("button_index", ""))
			var button_index := _joy_button_from_value(button)
			if button_index < 0:
				return _fail("Could not resolve joypad button: %s" % str(button), -32602)
			var pressed := bool(params.get("pressed", event_type != "up"))
			var pressure := float(params.get("pressure", params.get("strength", 1.0 if pressed else 0.0)))
			var event := InputEventJoypadButton.new()
			event.device = device
			event.button_index = button_index
			event.pressed = pressed
			event.pressure = pressure
			Input.parse_input_event(event)
			_record_event("input.joypad", {
				"type": "button",
				"device": device,
				"button": str(button),
				"button_index": button_index,
				"pressed": pressed,
				"pressure": pressure,
			})
			return _ok({
				"type": "button",
				"device": device,
				"button": str(button),
				"button_index": button_index,
				"pressed": pressed,
				"pressure": pressure,
			})
		"axis", "motion":
			var axis = params.get("axis", params.get("axis_index", ""))
			var axis_index := _joy_axis_from_value(axis)
			if axis_index < 0:
				return _fail("Could not resolve joypad axis: %s" % str(axis), -32602)
			var value := float(params.get("value", params.get("axis_value", 0.0)))
			var event := InputEventJoypadMotion.new()
			event.device = device
			event.axis = axis_index
			event.axis_value = value
			Input.parse_input_event(event)
			_record_event("input.joypad", {
				"type": "axis",
				"device": device,
				"axis": str(axis),
				"axis_index": axis_index,
				"value": value,
			})
			return _ok({
				"type": "axis",
				"device": device,
				"axis": str(axis),
				"axis_index": axis_index,
				"value": value,
			})

	return _fail("Unknown joypad input type: %s" % event_type, -32602)


func _rpc_input_key(params: Dictionary) -> Dictionary:
	var parsed := _parse_key_spec(params)
	var key = parsed.get("key", "")
	var modifiers: Dictionary = parsed.get("modifiers", {})
	var pressed := bool(params.get("pressed", true))
	var echo := bool(params.get("echo", false))
	var keycode := _keycode_from_value(key)
	var unicode := int(params.get("unicode", 0))
	if unicode == 0 and typeof(key) == TYPE_STRING and String(key).length() == 1 and not _modifiers_block_text(modifiers):
		unicode = String(key).unicode_at(0)
	if keycode == 0 and unicode == 0:
		return _fail("Could not resolve key: %s" % str(params.get("key", "")), -32602)
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.unicode = unicode
	event.pressed = pressed
	event.echo = echo
	event.shift_pressed = bool(modifiers.get("shift", false))
	event.ctrl_pressed = bool(modifiers.get("ctrl", false))
	event.alt_pressed = bool(modifiers.get("alt", false))
	event.meta_pressed = bool(modifiers.get("meta", false))
	Input.parse_input_event(event)
	_record_event("input.key", {
		"key": str(params.get("key", key)),
		"resolved_key": str(key),
		"keycode": keycode,
		"unicode": unicode,
		"pressed": pressed,
		"modifiers": modifiers,
	})
	return _ok({
		"key": str(params.get("key", key)),
		"resolved_key": str(key),
		"keycode": keycode,
		"unicode": unicode,
		"pressed": pressed,
		"modifiers": modifiers,
	})


func _rpc_input_text(params: Dictionary) -> Dictionary:
	var text := String(params.get("text", ""))
	get_viewport().push_text_input(text)
	_record_event("input.text", {"text": text})
	return _ok({"text": text})


func _input_action_summary(action: StringName, include_events: bool = true) -> Dictionary:
	var action_name := String(action)
	var exists := InputMap.has_action(action)
	var summary := {
		"name": action_name,
		"exists": exists,
		"pressed": false,
		"strength": 0.0,
	}
	if not exists:
		summary["deadzone"] = null
		summary["events"] = []
		summary["event_count"] = 0
		return summary
	summary["pressed"] = Input.is_action_pressed(action)
	summary["strength"] = Input.get_action_strength(action)
	summary["deadzone"] = InputMap.action_get_deadzone(action)
	if include_events:
		var events := []
		for event in InputMap.action_get_events(action):
			events.append(_input_event_summary(event))
		summary["events"] = events
		summary["event_count"] = events.size()
	return summary


func _input_event_specs_from_params(params: Dictionary) -> Array:
	var specs := []
	if params.has("events"):
		var events = params["events"]
		if typeof(events) == TYPE_ARRAY:
			for event in events:
				specs.append(event)
		else:
			specs.append(events)
	if params.has("event"):
		specs.append(params["event"])
	return specs


func _input_event_from_spec(spec: Variant) -> InputEvent:
	if spec is InputEvent:
		return spec as InputEvent
	if typeof(spec) == TYPE_STRING:
		return _input_event_from_spec({"type": "key", "key": String(spec)})
	if typeof(spec) != TYPE_DICTIONARY:
		return null
	var data: Dictionary = spec
	var event_type := _normalize_input_event_type(String(data.get("type", data.get("kind", ""))))
	if event_type == "":
		if data.has("key") or data.has("keycode"):
			event_type = "key"
		elif data.has("button") or data.has("button_index"):
			event_type = "mousebutton"
		elif data.has("axis") or data.has("axis_index"):
			event_type = "joypadaxis"

	match event_type:
		"key", "keyboard":
			var parsed := _parse_key_spec(data)
			var key = parsed.get("key", data.get("keycode", ""))
			var keycode := _keycode_from_value(key)
			if keycode == 0:
				return null
			var modifiers: Dictionary = parsed.get("modifiers", {})
			var event := InputEventKey.new()
			event.device = int(data.get("device", -1))
			event.keycode = keycode
			event.physical_keycode = int(data.get("physical_keycode", keycode))
			event.unicode = int(data.get("unicode", 0))
			event.pressed = bool(data.get("pressed", false))
			event.echo = bool(data.get("echo", false))
			event.shift_pressed = bool(modifiers.get("shift", false))
			event.ctrl_pressed = bool(modifiers.get("ctrl", false))
			event.alt_pressed = bool(modifiers.get("alt", false))
			event.meta_pressed = bool(modifiers.get("meta", false))
			return event
		"mouse", "mousebutton", "button":
			var button = data.get("button", data.get("button_index", MOUSE_BUTTON_LEFT))
			var button_index := _mouse_button_from_value(button)
			if button_index <= 0:
				return null
			var event := InputEventMouseButton.new()
			event.device = int(data.get("device", -1))
			event.button_index = button_index
			event.pressed = bool(data.get("pressed", false))
			event.factor = float(data.get("factor", 1.0))
			event.double_click = bool(data.get("double_click", false))
			return event
		"joypadbutton", "joybutton", "gamepadbutton":
			var button = data.get("button", data.get("button_index", ""))
			var button_index := _joy_button_from_value(button)
			if button_index < 0:
				return null
			var event := InputEventJoypadButton.new()
			event.device = int(data.get("device", -1))
			event.button_index = button_index
			event.pressed = bool(data.get("pressed", false))
			event.pressure = float(data.get("pressure", data.get("strength", 1.0)))
			return event
		"joypadaxis", "joyaxis", "gamepadaxis", "axis":
			var axis = data.get("axis", data.get("axis_index", ""))
			var axis_index := _joy_axis_from_value(axis)
			if axis_index < 0:
				return null
			var event := InputEventJoypadMotion.new()
			event.device = int(data.get("device", -1))
			event.axis = axis_index
			event.axis_value = float(data.get("value", data.get("axis_value", 1.0)))
			return event
	return null


func _normalize_input_event_type(value: String) -> String:
	return value.strip_edges().to_lower().replace("-", "").replace("_", "").replace(" ", "")


func _input_event_summary(event: InputEvent) -> Dictionary:
	var summary := {
		"class": event.get_class(),
		"device": event.device,
		"text": event.as_text(),
	}
	if event is InputEventKey:
		var key_event := event as InputEventKey
		summary["type"] = "key"
		summary["keycode"] = key_event.keycode
		summary["key"] = OS.get_keycode_string(key_event.keycode)
		summary["physical_keycode"] = key_event.physical_keycode
		summary["unicode"] = key_event.unicode
		summary["pressed"] = key_event.pressed
		summary["modifiers"] = {
			"shift": key_event.shift_pressed,
			"ctrl": key_event.ctrl_pressed,
			"alt": key_event.alt_pressed,
			"meta": key_event.meta_pressed,
		}
	elif event is InputEventMouseButton:
		var mouse_event := event as InputEventMouseButton
		summary["type"] = "mouse_button"
		summary["button_index"] = mouse_event.button_index
		summary["button"] = _mouse_button_name(mouse_event.button_index)
		summary["pressed"] = mouse_event.pressed
		summary["factor"] = mouse_event.factor
		summary["double_click"] = mouse_event.double_click
	elif event is InputEventJoypadButton:
		var button_event := event as InputEventJoypadButton
		summary["type"] = "joypad_button"
		summary["button_index"] = button_event.button_index
		summary["pressed"] = button_event.pressed
		summary["pressure"] = button_event.pressure
	elif event is InputEventJoypadMotion:
		var axis_event := event as InputEventJoypadMotion
		summary["type"] = "joypad_axis"
		summary["axis"] = axis_event.axis
		summary["value"] = axis_event.axis_value
	return summary


func _keycode_from_value(value: Variant) -> int:
	if typeof(value) == TYPE_INT or typeof(value) == TYPE_FLOAT:
		return int(value)
	var text := String(value)
	if text == "":
		return 0
	var keycode := OS.find_keycode_from_string(text)
	if keycode == 0:
		keycode = OS.find_keycode_from_string(text.to_upper())
	if keycode == 0 and text.length() == 1:
		keycode = OS.find_keycode_from_string(text.to_upper())
	return keycode


func _joy_button_from_value(value: Variant) -> int:
	if typeof(value) == TYPE_INT or typeof(value) == TYPE_FLOAT:
		return int(value)
	var normalized := _normalize_joy_name(value)
	match normalized:
		"a", "cross", "south", "bottom":
			return JOY_BUTTON_A
		"b", "circle", "east", "rightface":
			return JOY_BUTTON_B
		"x", "square", "west", "leftface":
			return JOY_BUTTON_X
		"y", "triangle", "north", "top":
			return JOY_BUTTON_Y
		"back", "select", "view", "share":
			return JOY_BUTTON_BACK
		"guide", "home":
			return JOY_BUTTON_GUIDE
		"start", "menu", "options", "option":
			return JOY_BUTTON_START
		"leftstick", "lstick", "ls", "l3":
			return JOY_BUTTON_LEFT_STICK
		"rightstick", "rstick", "rs", "r3":
			return JOY_BUTTON_RIGHT_STICK
		"leftshoulder", "leftbumper", "lb", "l1":
			return JOY_BUTTON_LEFT_SHOULDER
		"rightshoulder", "rightbumper", "rb", "r1":
			return JOY_BUTTON_RIGHT_SHOULDER
		"dpup", "dpadup", "hatup", "up":
			return JOY_BUTTON_DPAD_UP
		"dpdown", "dpaddown", "hatdown", "down":
			return JOY_BUTTON_DPAD_DOWN
		"dpleft", "dpadleft", "hatleft", "left":
			return JOY_BUTTON_DPAD_LEFT
		"dpright", "dpadright", "hatright", "right":
			return JOY_BUTTON_DPAD_RIGHT
	return -1


func _joy_axis_from_value(value: Variant) -> int:
	if typeof(value) == TYPE_INT or typeof(value) == TYPE_FLOAT:
		return int(value)
	var normalized := _normalize_joy_name(value)
	match normalized:
		"leftx", "leftstickx", "leftanalogx", "lx":
			return JOY_AXIS_LEFT_X
		"lefty", "leftsticky", "leftanalogy", "ly":
			return JOY_AXIS_LEFT_Y
		"rightx", "rightstickx", "rightanalogx", "rx":
			return JOY_AXIS_RIGHT_X
		"righty", "rightsticky", "rightanalogy", "ry":
			return JOY_AXIS_RIGHT_Y
		"lefttrigger", "lefttriggervalue", "ltrigger", "lt", "l2":
			return JOY_AXIS_TRIGGER_LEFT
		"righttrigger", "righttriggervalue", "rtrigger", "rt", "r2":
			return JOY_AXIS_TRIGGER_RIGHT
	return -1


func _mouse_button_from_value(value: Variant) -> int:
	if typeof(value) == TYPE_INT or typeof(value) == TYPE_FLOAT:
		return int(value)
	var normalized := String(value).strip_edges().to_lower().replace("-", "").replace("_", "").replace(" ", "")
	match normalized:
		"left", "primary":
			return MOUSE_BUTTON_LEFT
		"right", "secondary":
			return MOUSE_BUTTON_RIGHT
		"middle", "aux":
			return MOUSE_BUTTON_MIDDLE
		"wheelup", "scrollup":
			return MOUSE_BUTTON_WHEEL_UP
		"wheeldown", "scrolldown":
			return MOUSE_BUTTON_WHEEL_DOWN
		"wheelleft", "scrollleft":
			return MOUSE_BUTTON_WHEEL_LEFT
		"wheelright", "scrollright":
			return MOUSE_BUTTON_WHEEL_RIGHT
	return 0


func _mouse_button_name(button_index: int) -> String:
	match button_index:
		MOUSE_BUTTON_LEFT:
			return "left"
		MOUSE_BUTTON_RIGHT:
			return "right"
		MOUSE_BUTTON_MIDDLE:
			return "middle"
		MOUSE_BUTTON_WHEEL_UP:
			return "wheel_up"
		MOUSE_BUTTON_WHEEL_DOWN:
			return "wheel_down"
		MOUSE_BUTTON_WHEEL_LEFT:
			return "wheel_left"
		MOUSE_BUTTON_WHEEL_RIGHT:
			return "wheel_right"
	return str(button_index)


func _normalize_joy_name(value: Variant) -> String:
	return String(value).strip_edges().to_lower().replace("-", "").replace("_", "").replace(" ", "")


func _parse_key_spec(params: Dictionary) -> Dictionary:
	var key = params.get("key", "")
	var modifiers := {
		"shift": false,
		"ctrl": false,
		"alt": false,
		"meta": false,
	}
	if typeof(key) == TYPE_STRING:
		var parts := String(key).split("+", false)
		if parts.size() > 1:
			var remaining := []
			for part in parts:
				var normalized := _normalize_modifier_name(String(part))
				if normalized == "":
					remaining.append(String(part))
				else:
					modifiers[normalized] = true
			if not remaining.is_empty():
				key = remaining[remaining.size() - 1]

	var param_modifiers = params.get("modifiers", [])
	if typeof(param_modifiers) == TYPE_STRING:
		param_modifiers = String(param_modifiers).split("+", false)
	if typeof(param_modifiers) == TYPE_ARRAY:
		for modifier in param_modifiers:
			var normalized := _normalize_modifier_name(String(modifier))
			if normalized != "":
				modifiers[normalized] = true
	for source_name in ["shift", "shift_pressed"]:
		if params.has(source_name):
			modifiers["shift"] = bool(params[source_name])
	for source_name in ["ctrl", "control", "ctrl_pressed", "control_pressed"]:
		if params.has(source_name):
			modifiers["ctrl"] = bool(params[source_name])
	for source_name in ["alt", "option", "alt_pressed", "option_pressed"]:
		if params.has(source_name):
			modifiers["alt"] = bool(params[source_name])
	for source_name in ["meta", "cmd", "command", "meta_pressed", "command_pressed"]:
		if params.has(source_name):
			modifiers["meta"] = bool(params[source_name])
	if params.has("command_or_control") or params.has("cmd_or_ctrl"):
		var enabled := bool(params.get("command_or_control", params.get("cmd_or_ctrl", false)))
		if OS.get_name() == "macOS":
			modifiers["meta"] = enabled
		else:
			modifiers["ctrl"] = enabled
	return {"key": key, "modifiers": modifiers}


func _normalize_modifier_name(value: String) -> String:
	var normalized := value.strip_edges().to_lower().replace("-", "").replace("_", "")
	match normalized:
		"shift":
			return "shift"
		"ctrl", "control":
			return "ctrl"
		"alt", "option":
			return "alt"
		"meta", "cmd", "command", "super", "win", "windows":
			return "meta"
		"cmdorctrl", "commandorcontrol", "controlorcommand":
			return "meta" if OS.get_name() == "macOS" else "ctrl"
	return ""


func _modifiers_block_text(modifiers: Dictionary) -> bool:
	return bool(modifiers.get("ctrl", false)) or bool(modifiers.get("alt", false)) or bool(modifiers.get("meta", false))


func _rpc_input_mouse(params: Dictionary) -> Dictionary:
	var position := Vector2(float(params.get("x", 0.0)), float(params.get("y", 0.0)))
	var event_type := String(params.get("type", ""))
	if event_type == "":
		event_type = "move" if bool(params.get("motion", false)) else "button"

	match event_type:
		"move", "motion":
			_push_mouse_motion(position, int(params.get("button_mask", 0)))
			_record_event("input.mouse", {
				"type": "move",
				"x": position.x,
				"y": position.y,
				"motion": true,
			})
			return _ok({"type": "move", "x": position.x, "y": position.y, "motion": true})
		"down", "up", "button":
			var event := _push_mouse_button(
				position,
				int(params.get("button", MOUSE_BUTTON_LEFT)),
				bool(params.get("pressed", event_type != "up"))
			)
			_record_event("input.mouse", {
				"type": "button",
				"x": event.position.x,
				"y": event.position.y,
				"button": event.button_index,
				"pressed": event.pressed,
			})
			return _ok({
				"type": "button",
				"x": event.position.x,
				"y": event.position.y,
				"button": event.button_index,
				"pressed": event.pressed,
			})
		"click":
			var button := int(params.get("button", MOUSE_BUTTON_LEFT))
			_push_mouse_motion(position)
			_push_mouse_button(position, button, true)
			_push_mouse_button(position, button, false)
			_record_event("input.mouse", {
				"type": "click",
				"x": position.x,
				"y": position.y,
				"button": button,
			})
			return _ok({"type": "click", "x": position.x, "y": position.y, "button": button})
		"wheel", "scroll":
			var delta_x := float(params.get("delta_x", params.get("dx", 0.0)))
			var delta_y := float(params.get("delta_y", params.get("dy", 0.0)))
			if delta_x == 0.0 and delta_y == 0.0:
				return _fail("delta_x or delta_y is required for wheel input", -32602)
			var events := _push_mouse_wheel(position, delta_x, delta_y)
			_record_event("input.mouse", {
				"type": "wheel",
				"x": position.x,
				"y": position.y,
				"delta_x": delta_x,
				"delta_y": delta_y,
				"events": events,
			})
			return _ok({
				"type": "wheel",
				"x": position.x,
				"y": position.y,
				"delta_x": delta_x,
				"delta_y": delta_y,
				"events": events,
			})

	return _fail("Unknown mouse input type: %s" % event_type, -32602)


func _rpc_input_touch(params: Dictionary) -> Dictionary:
	var position := Vector2(float(params.get("x", 0.0)), float(params.get("y", 0.0)))
	var index := int(params.get("index", 0))
	var event_type := String(params.get("type", ""))
	if event_type == "":
		event_type = "down" if bool(params.get("pressed", true)) else "up"

	match event_type:
		"down", "press":
			var down := _push_screen_touch(position, index, true)
			_record_event("input.touch", {
				"type": "down",
				"x": down.position.x,
				"y": down.position.y,
				"index": down.index,
				"pressed": down.pressed,
			})
			return _ok({"type": "down", "x": down.position.x, "y": down.position.y, "index": down.index, "pressed": down.pressed})
		"up", "release":
			var up := _push_screen_touch(position, index, false)
			_record_event("input.touch", {
				"type": "up",
				"x": up.position.x,
				"y": up.position.y,
				"index": up.index,
				"pressed": up.pressed,
			})
			return _ok({"type": "up", "x": up.position.x, "y": up.position.y, "index": up.index, "pressed": up.pressed})
		"tap":
			var tap_down := _push_screen_touch(position, index, true)
			var tap_up := _push_screen_touch(position, index, false)
			_record_event("input.touch", {
				"type": "tap",
				"x": position.x,
				"y": position.y,
				"index": index,
			})
			return _ok({
				"type": "tap",
				"x": position.x,
				"y": position.y,
				"index": index,
				"events": [
					_screen_touch_summary(tap_down),
					_screen_touch_summary(tap_up),
				],
			})
		"move", "drag":
			var drag := _push_screen_drag(position, index)
			_record_event("input.touch", {
				"type": "drag",
				"x": drag.position.x,
				"y": drag.position.y,
				"index": drag.index,
				"relative": {"x": drag.relative.x, "y": drag.relative.y},
			})
			return _ok({
				"type": "drag",
				"x": drag.position.x,
				"y": drag.position.y,
				"index": drag.index,
				"relative": {"x": drag.relative.x, "y": drag.relative.y},
			})

	return _fail("Unknown touch input type: %s" % event_type, -32602)


func _push_mouse_motion(position: Vector2, button_mask: int = 0) -> InputEventMouseMotion:
	var motion := InputEventMouseMotion.new()
	motion.position = position
	motion.global_position = position
	motion.relative = position - _last_mouse_position
	motion.velocity = motion.relative
	motion.button_mask = button_mask
	get_viewport().push_input(motion, true)
	_dispatch_control_mouse_event(position, motion)
	_dispatch_collision_object_3d_mouse_event(position, motion)
	_last_mouse_position = position
	return motion


func _push_mouse_button(
	position: Vector2,
	button: int,
	pressed: bool,
	button_mask: int = -1,
	factor: float = 1.0
) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.position = position
	event.global_position = position
	event.button_index = button
	event.pressed = pressed
	event.factor = factor
	if button_mask >= 0:
		event.button_mask = button_mask
	else:
		event.button_mask = _mouse_button_mask(event.button_index) if event.pressed else 0
	get_viewport().push_input(event, true)
	if not event.pressed and not _is_wheel_button(event.button_index):
		_dispatch_control_mouse_event(position, event)
	if not _is_wheel_button(event.button_index):
		_dispatch_collision_object_3d_mouse_event(position, event)
	_last_mouse_position = position
	return event


func _push_screen_touch(position: Vector2, index: int, pressed: bool) -> InputEventScreenTouch:
	var event := InputEventScreenTouch.new()
	event.index = index
	event.position = position
	event.pressed = pressed
	get_viewport().push_input(event, true)
	_dispatch_control_touch_event(position, event)
	if pressed:
		_last_touch_positions[index] = position
	else:
		_last_touch_positions.erase(index)
	return event


func _push_screen_drag(position: Vector2, index: int) -> InputEventScreenDrag:
	var previous := _last_touch_positions.get(index, position)
	var event := InputEventScreenDrag.new()
	event.index = index
	event.position = position
	event.relative = position - previous
	event.velocity = event.relative
	get_viewport().push_input(event, true)
	_dispatch_control_touch_event(position, event)
	_last_touch_positions[index] = position
	return event


func _screen_touch_summary(event: InputEventScreenTouch) -> Dictionary:
	return {
		"index": event.index,
		"pressed": event.pressed,
		"x": event.position.x,
		"y": event.position.y,
	}


func _dispatch_control_mouse_event(position: Vector2, event: InputEvent) -> void:
	if DisplayServer.get_name() != "headless":
		return
	var control := _control_at_position(position)
	if control == null:
		if _last_hovered_control != null and is_instance_valid(_last_hovered_control):
			_last_hovered_control.emit_signal("mouse_exited")
		_last_hovered_control = null
		return
	if event is InputEventMouseMotion and _last_hovered_control != control:
		if _last_hovered_control != null and is_instance_valid(_last_hovered_control):
			_last_hovered_control.emit_signal("mouse_exited")
		control.emit_signal("mouse_entered")
		_last_hovered_control = control
	if control.has_signal("gui_input"):
		control.emit_signal("gui_input", event)


func _dispatch_collision_object_3d_mouse_event(position: Vector2, event: InputEvent) -> void:
	if DisplayServer.get_name() != "headless":
		return
	var camera := get_viewport().get_camera_3d()
	if camera == null:
		_emit_collision_object_3d_mouse_exit()
		return
	var world := camera.get_world_3d()
	if world == null:
		_emit_collision_object_3d_mouse_exit()
		return
	var origin: Vector3 = camera.project_ray_origin(position)
	var direction: Vector3 = camera.project_ray_normal(position).normalized()
	var query := PhysicsRayQueryParameters3D.create(origin, origin + direction * 1000.0)
	query.collide_with_bodies = true
	query.collide_with_areas = true
	var result := world.direct_space_state.intersect_ray(query)
	if result.is_empty():
		_emit_collision_object_3d_mouse_exit()
		return
	var collider = result.get("collider", null)
	if not (collider is CollisionObject3D):
		_emit_collision_object_3d_mouse_exit()
		return
	var collision_object := collider as CollisionObject3D
	if event is InputEventMouseMotion and _last_hovered_collision_3d != collision_object:
		_emit_collision_object_3d_mouse_exit()
		if collision_object.has_signal("mouse_entered"):
			collision_object.emit_signal("mouse_entered")
		_last_hovered_collision_3d = collision_object
	if collision_object.has_signal("input_event"):
		collision_object.emit_signal(
			"input_event",
			camera,
			event,
			result.get("position", origin),
			result.get("normal", Vector3.ZERO),
			int(result.get("shape", -1))
		)


func _emit_collision_object_3d_mouse_exit() -> void:
	if _last_hovered_collision_3d == null or not is_instance_valid(_last_hovered_collision_3d):
		_last_hovered_collision_3d = null
		return
	if _last_hovered_collision_3d.has_signal("mouse_exited"):
		_last_hovered_collision_3d.emit_signal("mouse_exited")
	_last_hovered_collision_3d = null


func _dispatch_control_touch_event(position: Vector2, event: InputEvent) -> void:
	if DisplayServer.get_name() != "headless":
		return
	var control := _control_at_position(position)
	if control == null:
		return
	if control.has_signal("gui_input"):
		control.emit_signal("gui_input", event)


func _control_at_position(position: Vector2) -> Control:
	var root := get_tree().get_current_scene()
	if root == null:
		root = _edited_scene_root()
	if root == null:
		root = get_tree().get_root()
	return _control_at_position_recursive(root, position, null)


func _control_at_position_recursive(node: Node, position: Vector2, current: Control) -> Control:
	if node is Control and node.visible:
		var rect: Rect2 = node.get_global_rect()
		if rect.has_point(position):
			current = node
	for child in node.get_children():
		current = _control_at_position_recursive(child, position, current)
	return current


func _push_mouse_wheel(position: Vector2, delta_x: float, delta_y: float) -> Array:
	var events := []
	if delta_y < 0.0:
		events.append(_mouse_button_summary(
			_push_mouse_button(position, MOUSE_BUTTON_WHEEL_UP, true, 0, abs(delta_y))
		))
	elif delta_y > 0.0:
		events.append(_mouse_button_summary(
			_push_mouse_button(position, MOUSE_BUTTON_WHEEL_DOWN, true, 0, delta_y)
		))

	if delta_x < 0.0:
		events.append(_mouse_button_summary(
			_push_mouse_button(position, MOUSE_BUTTON_WHEEL_LEFT, true, 0, abs(delta_x))
		))
	elif delta_x > 0.0:
		events.append(_mouse_button_summary(
			_push_mouse_button(position, MOUSE_BUTTON_WHEEL_RIGHT, true, 0, delta_x)
		))
	return events


func _mouse_button_summary(event: InputEventMouseButton) -> Dictionary:
	return {
		"button": event.button_index,
		"pressed": event.pressed,
		"factor": event.factor,
	}


func _is_wheel_button(button: int) -> bool:
	return (
		button == MOUSE_BUTTON_WHEEL_UP
		or button == MOUSE_BUTTON_WHEEL_DOWN
		or button == MOUSE_BUTTON_WHEEL_LEFT
		or button == MOUSE_BUTTON_WHEEL_RIGHT
	)


func _mouse_button_mask(button: int) -> int:
	match button:
		MOUSE_BUTTON_LEFT:
			return MOUSE_BUTTON_MASK_LEFT
		MOUSE_BUTTON_RIGHT:
			return MOUSE_BUTTON_MASK_RIGHT
		MOUSE_BUTTON_MIDDLE:
			return MOUSE_BUTTON_MASK_MIDDLE
		MOUSE_BUTTON_WHEEL_UP:
			return 0
		MOUSE_BUTTON_WHEEL_DOWN:
			return 0
	return 0


func _rpc_viewport_info() -> Dictionary:
	return _ok(_viewport_info())


func _rpc_viewport_set_size(params: Dictionary) -> Dictionary:
	var width := int(params.get("width", 0))
	var height := int(params.get("height", 0))
	if width <= 0 or height <= 0:
		return _fail("width and height must be positive", -32602)
	var window := get_window()
	if window == null:
		return _fail("Active window is unavailable")
	var previous := _viewport_info()
	window.size = Vector2i(width, height)
	var current := _viewport_info()
	_record_event("viewport.set_size", {
		"previous": previous,
		"current": current,
	})
	return _ok(current)


func _viewport_info() -> Dictionary:
	var window := get_window()
	var window_size := Vector2i.ZERO
	if window != null:
		window_size = window.size
	var visible_rect := get_viewport().get_visible_rect()
	return {
		"display_server": DisplayServer.get_name(),
		"window_size": {
			"width": window_size.x,
			"height": window_size.y,
		},
		"visible_rect": {
			"x": visible_rect.position.x,
			"y": visible_rect.position.y,
			"width": visible_rect.size.x,
			"height": visible_rect.size.y,
		},
		"mouse_position": {
			"x": _last_mouse_position.x,
			"y": _last_mouse_position.y,
		},
	}


func _rpc_viewport_screenshot(params: Dictionary) -> Dictionary:
	if DisplayServer.get_name() == "headless":
		return _fail("Viewport screenshots are unavailable with the headless display driver; run without --headless or use scene snapshots")
	var path := String(params.get("path", "user://godot_playwright_screenshot.png"))
	var image := get_viewport().get_texture().get_image()
	if image == null:
		return _fail("Viewport screenshot image is unavailable")
	var error := image.save_png(path)
	if error != OK:
		return _fail("Failed to save screenshot: %s" % error)
	_record_event("viewport.screenshot", {
		"path": path,
		"width": image.get_width(),
		"height": image.get_height(),
	})
	return _ok({
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"width": image.get_width(),
		"height": image.get_height(),
	})


func _rpc_fs_exists(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var is_file := FileAccess.file_exists(path)
	var is_dir := DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(path))
	return _ok({
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"exists": is_file or is_dir,
		"type": "file" if is_file else ("directory" if is_dir else "missing"),
	})


func _rpc_fs_info(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	return _ok(_filesystem_entry(path))


func _rpc_fs_read_text(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	if not FileAccess.file_exists(path):
		return _fail("File not found: %s" % path)
	var text := FileAccess.get_file_as_string(path)
	var open_error := FileAccess.get_open_error()
	if open_error != OK:
		return _fail("Failed to read %s: %s" % [path, open_error])
	_record_event("fs.read_text", {"path": path, "bytes": text.to_utf8_buffer().size()})
	return _ok({
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"text": text,
		"bytes": text.to_utf8_buffer().size(),
	})


func _rpc_fs_write_text(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	if FileAccess.file_exists(path) and not bool(params.get("overwrite", true)):
		return _fail("File already exists: %s" % path)
	if bool(params.get("create_dirs", true)):
		var dir_error := _ensure_res_parent_dir(path)
		if dir_error != OK:
			return _fail("Failed to create parent directories for %s: %s" % [path, dir_error])
	var text := String(params.get("text", ""))
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return _fail("Failed to open %s for writing: %s" % [path, FileAccess.get_open_error()])
	file.store_string(text)
	file.close()
	_scan_editor_filesystem(path)
	_record_event("fs.write_text", {"path": path, "bytes": text.to_utf8_buffer().size()})
	return _ok({
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"bytes": text.to_utf8_buffer().size(),
	})


func _rpc_fs_replace_text(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	if not FileAccess.file_exists(path):
		return _fail("File not found: %s" % path)
	if bool(params.get("require_text_file", true)) and not _is_text_search_path(path):
		return _fail("Refusing to replace text in non-text path: %s" % path, -32602)
	var old_text := String(params.get("old_text", params.get("search", "")))
	if old_text == "":
		return _fail("old_text is required", -32602)
	if not params.has("new_text") and not params.has("replace"):
		return _fail("new_text is required", -32602)
	var new_text := String(params.get("new_text", params.get("replace", "")))
	var expected_replacements := int(params.get("expected_replacements", 1))
	if expected_replacements < -1:
		return _fail("expected_replacements must be >= -1", -32602)
	var max_replacements := int(params.get("max_replacements", 0))
	if max_replacements < 0:
		return _fail("max_replacements must be >= 0", -32602)
	var source := FileAccess.get_file_as_string(path)
	var open_error := FileAccess.get_open_error()
	if open_error != OK:
		return _fail("Failed to read %s: %s" % [path, open_error])
	var before_summary := _file_summary(path)
	var replacement := _replace_text_with_evidence(
		source,
		old_text,
		new_text,
		bool(params.get("case_sensitive", true)),
		max_replacements,
		max(0, int(params.get("max_preview", 20)))
	)
	var match_count := int(replacement.get("match_count", 0))
	if expected_replacements >= 0 and match_count != expected_replacements:
		return _fail(
			"Expected %s replacements in %s, found %s" % [expected_replacements, path, match_count],
			-32000,
			{
				"path": path,
				"expected_replacements": expected_replacements,
				"match_count": match_count,
				"edits": replacement.get("edits", []),
			}
		)
	if max_replacements > 0 and match_count > max_replacements:
		return _fail(
			"Replacement count %s exceeds max_replacements %s in %s" % [match_count, max_replacements, path],
			-32000,
			{
				"path": path,
				"max_replacements": max_replacements,
				"match_count": match_count,
				"edits": replacement.get("edits", []),
			}
		)
	var after_text := String(replacement.get("text", source))
	var dry_run := bool(params.get("dry_run", false))
	if not dry_run and after_text != source:
		var file := FileAccess.open(path, FileAccess.WRITE)
		if file == null:
			return _fail("Failed to open %s for writing: %s" % [path, FileAccess.get_open_error()])
		file.store_string(after_text)
		file.close()
		_scan_editor_filesystem(path)
	var after_summary := _file_summary(path) if not dry_run else {
		"path": path,
		"name": path.get_file(),
		"global_path": ProjectSettings.globalize_path(path),
		"exists": true,
		"bytes": after_text.to_utf8_buffer().size(),
	}
	var result := {
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"case_sensitive": bool(params.get("case_sensitive", true)),
		"dry_run": dry_run,
		"changed": after_text != source,
		"match_count": match_count,
		"replacements": match_count,
		"bytes_before": source.to_utf8_buffer().size(),
		"bytes_after": after_text.to_utf8_buffer().size(),
		"file_before": before_summary,
		"file_after": after_summary,
		"edits": replacement.get("edits", []),
	}
	if bool(params.get("include_text", false)):
		result["text"] = after_text
	_record_event("fs.replace_text", {
		"path": path,
		"old_text": old_text,
		"new_text": new_text,
		"expected_replacements": expected_replacements,
		"case_sensitive": bool(params.get("case_sensitive", true)),
		"max_replacements": max_replacements,
		"require_text_file": bool(params.get("require_text_file", true)),
		"max_preview": max(0, int(params.get("max_preview", 20))),
		"replacements": match_count,
		"dry_run": dry_run,
	})
	return _ok(result)


func _rpc_fs_replace_text_many(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", "res://"))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var old_text := String(params.get("old_text", params.get("search", "")))
	if old_text == "":
		return _fail("old_text is required", -32602)
	if not params.has("new_text") and not params.has("replace"):
		return _fail("new_text is required", -32602)
	var new_text := String(params.get("new_text", params.get("replace", "")))
	var dry_run := bool(params.get("dry_run", true))
	var expected_files := int(params.get("expected_files", -1))
	if expected_files < -1:
		return _fail("expected_files must be >= -1", -32602)
	var expected_replacements := int(params.get("expected_replacements", -1))
	if expected_replacements < -1:
		return _fail("expected_replacements must be >= -1", -32602)
	if not dry_run and expected_files < 0 and expected_replacements < 0:
		return _fail("expected_files or expected_replacements is required when dry_run is false", -32602)
	var max_files := max(1, int(params.get("max_files", 500)))
	var max_replacements_per_file := int(params.get("max_replacements_per_file", 100))
	if max_replacements_per_file < 0:
		return _fail("max_replacements_per_file must be >= 0", -32602)
	var max_total_replacements := int(params.get("max_total_replacements", 500))
	if max_total_replacements < 0:
		return _fail("max_total_replacements must be >= 0", -32602)
	var filters := {
		"name": String(params.get("name", "")),
		"name_contains": String(params.get("name_contains", "")),
		"extension": String(params.get("extension", "")),
		"resource_type": String(params.get("resource_type", "")),
	}
	var entries := []
	_collect_filesystem_entries(
		path,
		bool(params.get("recursive", true)),
		false,
		bool(params.get("include_hidden", false)),
		filters,
		max_files,
		entries
	)
	var changes := []
	var files_checked := 0
	var total_replacements := 0
	var case_sensitive := bool(params.get("case_sensitive", true))
	var include_text := bool(params.get("include_text", false))
	var include_binary := bool(params.get("include_binary", false))
	var max_preview := max(0, int(params.get("max_preview", 20)))
	for entry in entries:
		if not bool(entry.get("is_file", false)):
			continue
		var file_path := String(entry.get("path", ""))
		if not include_binary and not _is_text_search_path(file_path):
			continue
		var source := FileAccess.get_file_as_string(file_path)
		var open_error := FileAccess.get_open_error()
		if open_error != OK:
			return _fail("Failed to read %s: %s" % [file_path, open_error])
		files_checked += 1
		var replacement := _replace_text_with_evidence(
			source,
			old_text,
			new_text,
			case_sensitive,
			0,
			max_preview
		)
		var match_count := int(replacement.get("match_count", 0))
		if match_count <= 0:
			continue
		if max_replacements_per_file > 0 and match_count > max_replacements_per_file:
			return _fail(
				"Replacement count %s exceeds max_replacements_per_file %s in %s" % [match_count, max_replacements_per_file, file_path],
				-32000,
				{
					"path": file_path,
					"max_replacements_per_file": max_replacements_per_file,
					"match_count": match_count,
					"edits": replacement.get("edits", []),
				}
			)
		total_replacements += match_count
		if max_total_replacements > 0 and total_replacements > max_total_replacements:
			return _fail(
				"Replacement count %s exceeds max_total_replacements %s" % [total_replacements, max_total_replacements],
				-32000,
				{
					"path": path,
					"max_total_replacements": max_total_replacements,
					"match_count": total_replacements,
					"last_path": file_path,
				}
			)
		var after_text := String(replacement.get("text", source))
		var before_summary := _file_summary(file_path)
		var after_summary := _file_summary(file_path) if not dry_run else {
			"path": file_path,
			"name": file_path.get_file(),
			"global_path": ProjectSettings.globalize_path(file_path),
			"exists": true,
			"bytes": after_text.to_utf8_buffer().size(),
		}
		var change := {
			"path": file_path,
			"global_path": ProjectSettings.globalize_path(file_path),
			"changed": after_text != source,
			"match_count": match_count,
			"replacements": match_count,
			"bytes_before": source.to_utf8_buffer().size(),
			"bytes_after": after_text.to_utf8_buffer().size(),
			"file_before": before_summary,
			"file_after": after_summary,
			"edits": replacement.get("edits", []),
			"_text": after_text,
		}
		if include_text:
			change["text"] = after_text
		changes.append(change)
	var changed_files := changes.size()
	if expected_files >= 0 and changed_files != expected_files:
		return _fail(
			"Expected %s changed files under %s, found %s" % [expected_files, path, changed_files],
			-32000,
			{
				"path": path,
				"expected_files": expected_files,
				"changed_files": changed_files,
				"replacements": total_replacements,
				"changes": _public_bulk_replace_changes(changes),
			}
		)
	if expected_replacements >= 0 and total_replacements != expected_replacements:
		return _fail(
			"Expected %s replacements under %s, found %s" % [expected_replacements, path, total_replacements],
			-32000,
			{
				"path": path,
				"expected_replacements": expected_replacements,
				"replacements": total_replacements,
				"changed_files": changed_files,
				"changes": _public_bulk_replace_changes(changes),
			}
		)
	if not dry_run:
		for change in changes:
			var file_path := String(change.get("path", ""))
			var file := FileAccess.open(file_path, FileAccess.WRITE)
			if file == null:
				return _fail("Failed to open %s for writing: %s" % [file_path, FileAccess.get_open_error()])
			file.store_string(String(change.get("_text", "")))
			file.close()
			_scan_editor_filesystem(file_path)
		for change in changes:
			change["file_after"] = _file_summary(String(change.get("path", "")))
	var public_changes := _public_bulk_replace_changes(changes)
	_record_event("fs.replace_text_many", {
		"path": path,
		"old_text": old_text,
		"new_text": new_text,
		"expected_files": expected_files,
		"expected_replacements": expected_replacements,
		"case_sensitive": case_sensitive,
		"recursive": bool(params.get("recursive", true)),
		"include_hidden": bool(params.get("include_hidden", false)),
		"include_binary": include_binary,
		"name": String(params.get("name", "")),
		"name_contains": String(params.get("name_contains", "")),
		"extension": String(params.get("extension", "")),
		"resource_type": String(params.get("resource_type", "")),
		"max_files": max_files,
		"max_replacements_per_file": max_replacements_per_file,
		"max_total_replacements": max_total_replacements,
		"max_preview": max_preview,
		"changed_files": changed_files,
		"replacements": total_replacements,
		"dry_run": dry_run,
	})
	return _ok({
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"case_sensitive": case_sensitive,
		"dry_run": dry_run,
		"files_checked": files_checked,
		"changed_files": changed_files,
		"count": changed_files,
		"replacements": total_replacements,
		"changes": public_changes,
	})


func _rpc_fs_read_bytes(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	if not FileAccess.file_exists(path):
		return _fail("File not found: %s" % path)
	var buffer := FileAccess.get_file_as_bytes(path)
	var open_error := FileAccess.get_open_error()
	if open_error != OK:
		return _fail("Failed to read %s: %s" % [path, open_error])
	var max_bytes := int(params.get("max_bytes", 0))
	if max_bytes > 0 and buffer.size() > max_bytes:
		return _fail("File exceeds max_bytes: %s > %s" % [buffer.size(), max_bytes])
	_record_event("fs.read_bytes", {"path": path, "bytes": buffer.size()})
	return _ok({
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"base64": Marshalls.raw_to_base64(buffer),
		"bytes": buffer.size(),
	})


func _rpc_fs_write_bytes(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	if not params.has("base64"):
		return _fail("base64 is required", -32602)
	if FileAccess.file_exists(path) and not bool(params.get("overwrite", true)):
		return _fail("File already exists: %s" % path)
	if bool(params.get("create_dirs", true)):
		var dir_error := _ensure_res_parent_dir(path)
		if dir_error != OK:
			return _fail("Failed to create parent directories for %s: %s" % [path, dir_error])
	var encoded := String(params.get("base64", ""))
	var buffer := Marshalls.base64_to_raw(encoded)
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return _fail("Failed to open %s for writing: %s" % [path, FileAccess.get_open_error()])
	file.store_buffer(buffer)
	file.close()
	_scan_editor_filesystem(path)
	_record_event("fs.write_bytes", {"path": path, "bytes": buffer.size()})
	return _ok({
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"bytes": buffer.size(),
	})


func _rpc_fs_mkdir(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var error := DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(path))
	if error != OK:
		return _fail("Failed to create directory %s: %s" % [path, error])
	_scan_editor_filesystem(path)
	_record_event("fs.mkdir", {"path": path})
	return _ok({"path": path, "global_path": ProjectSettings.globalize_path(path)})


func _rpc_fs_list(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", "res://"))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var dir := DirAccess.open(path)
	if dir == null:
		return _fail("Directory not found: %s" % path)
	var include_hidden := bool(params.get("include_hidden", false))
	var files := []
	var directories := []
	dir.list_dir_begin()
	var name := dir.get_next()
	while name != "":
		if include_hidden or not name.begins_with("."):
			if dir.current_is_dir():
				directories.append(name)
			else:
				files.append(name)
		name = dir.get_next()
	dir.list_dir_end()
	files.sort()
	directories.sort()
	return _ok({
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"files": files,
		"directories": directories,
	})


func _rpc_fs_find(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", "res://"))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var max_results := max(1, int(params.get("max_results", 500)))
	var filters := {
		"name": String(params.get("name", "")),
		"name_contains": String(params.get("name_contains", "")),
		"extension": String(params.get("extension", "")),
		"resource_type": String(params.get("resource_type", "")),
	}
	var entries := []
	_collect_filesystem_entries(
		path,
		bool(params.get("recursive", true)),
		bool(params.get("include_dirs", false)),
		bool(params.get("include_hidden", false)),
		filters,
		max_results,
		entries
	)
	return _ok({
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"count": entries.size(),
		"entries": entries,
	})


func _rpc_fs_grep(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", "res://"))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var query := String(params.get("query", params.get("text", "")))
	if query == "":
		return _fail("query is required", -32602)
	var max_files := max(1, int(params.get("max_files", 500)))
	var max_results := max(1, int(params.get("max_results", 500)))
	var max_matches_per_file := max(1, int(params.get("max_matches_per_file", 20)))
	var filters := {
		"name": String(params.get("name", "")),
		"name_contains": String(params.get("name_contains", "")),
		"extension": String(params.get("extension", "")),
		"resource_type": String(params.get("resource_type", "")),
	}
	var entries := []
	_collect_filesystem_entries(
		path,
		bool(params.get("recursive", true)),
		false,
		bool(params.get("include_hidden", false)),
		filters,
		max_files,
		entries
	)
	var matches := []
	var files_checked := 0
	for entry in entries:
		if matches.size() >= max_results:
			break
		if not bool(entry.get("is_file", false)):
			continue
		var file_path := String(entry.get("path", ""))
		if not bool(params.get("include_binary", false)) and not _is_text_search_path(file_path):
			continue
		files_checked += 1
		_grep_file(
			file_path,
			query,
			bool(params.get("case_sensitive", true)),
			max(0, int(params.get("context_lines", 0))),
			max_matches_per_file,
			max_results,
			matches
		)
	_record_event("fs.grep", {"path": path, "query": query, "count": matches.size()})
	return _ok({
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"query": query,
		"case_sensitive": bool(params.get("case_sensitive", true)),
		"count": matches.size(),
		"files_checked": files_checked,
		"matches": matches,
	})


func _rpc_fs_copy(params: Dictionary) -> Dictionary:
	var source := String(params.get("source", params.get("from", "")))
	var destination := String(params.get("destination", params.get("to", "")))
	var source_error := _validate_res_path(source)
	if source_error != "":
		return _fail(source_error, -32602)
	var destination_error := _validate_res_path(destination)
	if destination_error != "":
		return _fail(destination_error, -32602)
	if not FileAccess.file_exists(source):
		return _fail("Source file not found: %s" % source)
	if FileAccess.file_exists(destination) or DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(destination)):
		if not bool(params.get("overwrite", true)):
			return _fail("Destination already exists: %s" % destination)
		var remove_error := _remove_res_path(destination)
		if remove_error != OK:
			return _fail("Failed to remove destination %s: %s" % [destination, remove_error])
	if bool(params.get("create_dirs", true)):
		var dir_error := _ensure_res_parent_dir(destination)
		if dir_error != OK:
			return _fail("Failed to create parent directories for %s: %s" % [destination, dir_error])
	var error := DirAccess.copy_absolute(ProjectSettings.globalize_path(source), ProjectSettings.globalize_path(destination))
	if error != OK:
		return _fail("Failed to copy %s to %s: %s" % [source, destination, error])
	_scan_editor_filesystem(source.get_base_dir())
	_scan_editor_filesystem(destination)
	_record_event("fs.copy", {"source": source, "destination": destination})
	return _ok({
		"source": source,
		"destination": destination,
		"global_source": ProjectSettings.globalize_path(source),
		"global_destination": ProjectSettings.globalize_path(destination),
		"type": "file",
		"bytes": _file_summary(destination).get("bytes", -1),
	})


func _rpc_fs_move(params: Dictionary) -> Dictionary:
	var source := String(params.get("source", params.get("from", "")))
	var destination := String(params.get("destination", params.get("to", "")))
	var source_error := _validate_res_path(source)
	if source_error != "":
		return _fail(source_error, -32602)
	var destination_error := _validate_res_path(destination)
	if destination_error != "":
		return _fail(destination_error, -32602)
	if source == "res://":
		return _fail("Refusing to move project root", -32602)
	var source_is_file := FileAccess.file_exists(source)
	var source_is_dir := DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(source))
	if not source_is_file and not source_is_dir:
		return _fail("Source path not found: %s" % source)
	if FileAccess.file_exists(destination) or DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(destination)):
		if not bool(params.get("overwrite", true)):
			return _fail("Destination already exists: %s" % destination)
		var remove_error := _remove_res_path(destination)
		if remove_error != OK:
			return _fail("Failed to remove destination %s: %s" % [destination, remove_error])
	if bool(params.get("create_dirs", true)):
		var dir_error := _ensure_res_parent_dir(destination)
		if dir_error != OK:
			return _fail("Failed to create parent directories for %s: %s" % [destination, dir_error])
	var error := DirAccess.rename_absolute(ProjectSettings.globalize_path(source), ProjectSettings.globalize_path(destination))
	if error != OK:
		return _fail("Failed to move %s to %s: %s" % [source, destination, error])
	_scan_editor_filesystem(source.get_base_dir())
	_scan_editor_filesystem(destination)
	_record_event("fs.move", {"source": source, "destination": destination})
	return _ok({
		"source": source,
		"destination": destination,
		"global_source": ProjectSettings.globalize_path(source),
		"global_destination": ProjectSettings.globalize_path(destination),
		"type": "file" if source_is_file else "directory",
		"bytes": _file_summary(destination).get("bytes", -1) if source_is_file else -1,
	})


func _rpc_fs_delete(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	if path == "res://":
		return _fail("Refusing to delete project root", -32602)
	var global_path := ProjectSettings.globalize_path(path)
	var parent := path.get_base_dir()
	var name := path.get_file()
	var dir := DirAccess.open(parent)
	if dir == null:
		return _fail("Parent directory not found: %s" % parent)
	var existed := FileAccess.file_exists(path) or DirAccess.dir_exists_absolute(global_path)
	if not existed:
		return _fail("Path not found: %s" % path)
	var error := dir.remove(name)
	if error != OK:
		return _fail("Failed to delete %s: %s" % [path, error])
	_scan_editor_filesystem(parent)
	_record_event("fs.delete", {"path": path})
	return _ok({"path": path, "deleted": true})


func _rpc_resource_save(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var resource_class := String(params.get("class", params.get("type", "Resource")))
	var resource = Resource.new()
	if resource_class != "Resource":
		if not ClassDB.class_exists(resource_class) or not ClassDB.can_instantiate(resource_class):
			return _fail("Cannot instantiate resource class: %s" % resource_class)
		resource = ClassDB.instantiate(resource_class)
	if not (resource is Resource):
		return _fail("Class is not a Resource: %s" % resource_class)
	var properties = params.get("properties", {})
	if typeof(properties) != TYPE_DICTIONARY:
		return _fail("properties must be an object", -32602)
	var property_error := _validate_resource_graph_properties(properties)
	if property_error != "":
		return _fail(property_error, -32602)
	for property in properties.keys():
		resource.set(String(property), _decode_value(properties[property]))
	var dir_error := _ensure_res_parent_dir(path)
	if dir_error != OK:
		return _fail("Failed to create parent directories for %s: %s" % [path, dir_error])
	var save_error := ResourceSaver.save(resource, path)
	if save_error != OK:
		return _fail("Failed to save resource %s: %s" % [path, save_error])
	_scan_editor_filesystem(path)
	_record_event("resource.save", {"path": path, "class": resource.get_class(), "properties": properties})
	var summary := _resource_summary(resource)
	summary["path"] = path
	summary["global_path"] = ProjectSettings.globalize_path(path)
	summary["dependency_state"] = _resource_dependencies_payload(path, false)
	return _ok(summary)


func _rpc_resource_set_properties(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	if not ResourceLoader.exists(path):
		return _fail("Resource not found: %s" % path)
	var properties = params.get("properties", {})
	if typeof(properties) != TYPE_DICTIONARY:
		return _fail("properties must be an object", -32602)
	if properties.is_empty():
		return _fail("properties must not be empty", -32602)
	var property_error := _validate_resource_graph_properties(properties)
	if property_error != "":
		return _fail(property_error, -32602)
	var type_hint := String(params.get("type_hint", ""))
	var resource := ResourceLoader.load(path, type_hint)
	if resource == null:
		return _fail("Failed to load resource: %s" % path)
	var property_names := _property_name_set(resource)
	if bool(params.get("require_existing_properties", true)):
		for property in properties.keys():
			var name := String(property)
			if not property_names.has(name):
				return _fail("Resource property not found: %s" % name, -32602)
	var previous := {}
	for property in properties.keys():
		var name := String(property)
		previous[name] = _encode_value(resource.get(name))
	for property in properties.keys():
		resource.set(String(property), _decode_value(properties[property]))
	var current := {}
	for property in properties.keys():
		var name := String(property)
		current[name] = _encode_value(resource.get(name))
	var saved := bool(params.get("save", true))
	if saved:
		var save_error := ResourceSaver.save(resource, path)
		if save_error != OK:
			return _fail("Failed to save resource %s: %s" % [path, save_error])
		_scan_editor_filesystem(path)
	if bool(params.get("inspect", false)):
		_inspect_object(resource)
	var summary := _resource_summary(resource)
	summary["previous"] = previous
	summary["properties"] = current
	summary["saved"] = saved
	if saved:
		summary["dependency_state"] = _resource_dependencies_payload(path, false)
	_record_event("resource.set_properties", {
		"path": path,
		"properties": properties,
		"type_hint": type_hint,
		"saved": saved,
		"save": saved,
		"require_existing_properties": bool(params.get("require_existing_properties", true)),
		"inspect": bool(params.get("inspect", false)),
	})
	return _ok(summary)


func _rpc_resource_duplicate(params: Dictionary) -> Dictionary:
	var source := String(params.get("source", params.get("from", "")))
	var destination := String(params.get("destination", params.get("to", "")))
	var source_error := _validate_res_path(source)
	if source_error != "":
		return _fail(source_error, -32602)
	var destination_error := _validate_res_path(destination)
	if destination_error != "":
		return _fail(destination_error, -32602)
	if source == destination:
		return _fail("source and destination must differ", -32602)
	if not ResourceLoader.exists(source):
		return _fail("Source resource not found: %s" % source)
	if FileAccess.file_exists(destination) and not bool(params.get("overwrite", true)):
		return _fail("Destination already exists: %s" % destination, -32602)
	var type_hint := String(params.get("type_hint", ""))
	var source_resource := ResourceLoader.load(source, type_hint)
	if source_resource == null:
		return _fail("Failed to load source resource: %s" % source)
	var duplicated = source_resource.duplicate(bool(params.get("deep", true)))
	if duplicated == null or not (duplicated is Resource):
		return _fail("Failed to duplicate resource: %s" % source)
	var resource := duplicated as Resource
	var properties = params.get("properties", {})
	if typeof(properties) != TYPE_DICTIONARY:
		return _fail("properties must be an object", -32602)
	var property_error := _validate_resource_graph_properties(properties)
	if property_error != "":
		return _fail(property_error, -32602)
	var property_names := _property_name_set(resource)
	if bool(params.get("require_existing_properties", true)):
		for property in properties.keys():
			var name := String(property)
			if not property_names.has(name):
				return _fail("Resource property not found: %s" % name, -32602)
	var previous := {}
	for property in properties.keys():
		var name := String(property)
		previous[name] = _encode_value(resource.get(name))
	for property in properties.keys():
		resource.set(String(property), _decode_value(properties[property]))
	var current := {}
	for property in properties.keys():
		var name := String(property)
		current[name] = _encode_value(resource.get(name))
	var dir_error := _ensure_res_parent_dir(destination)
	if dir_error != OK:
		return _fail("Failed to create parent directories for %s: %s" % [destination, dir_error])
	var save_error := ResourceSaver.save(resource, destination)
	if save_error != OK:
		return _fail("Failed to save resource %s: %s" % [destination, save_error])
	_scan_editor_filesystem(destination)
	if bool(params.get("inspect", false)):
		_inspect_object(resource)
	var summary := _resource_summary(resource)
	summary["path"] = destination
	summary["global_path"] = ProjectSettings.globalize_path(destination)
	summary["source"] = _resource_summary(source_resource)
	summary["source_path"] = source
	summary["destination"] = destination
	summary["global_destination"] = ProjectSettings.globalize_path(destination)
	summary["previous"] = previous
	summary["properties"] = current
	summary["deep"] = bool(params.get("deep", true))
	summary["saved"] = true
	summary["dependency_state"] = _resource_dependencies_payload(destination, false)
	_record_event("resource.duplicate", {
		"source": source,
		"destination": destination,
		"class": resource.get_class(),
		"properties": properties,
		"type_hint": type_hint,
		"deep": bool(params.get("deep", true)),
		"overwrite": bool(params.get("overwrite", true)),
		"require_existing_properties": bool(params.get("require_existing_properties", true)),
		"inspect": bool(params.get("inspect", false)),
	})
	return _ok(summary)


func _rpc_resource_files(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", "res://"))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var max_results := max(1, int(params.get("max_results", 200)))
	var max_scan_results := max(max_results, int(params.get("max_scan_results", max_results * 20)))
	var extensions := _string_filter_array(params.get("extensions", params.get("extension", [])))
	if extensions.is_empty():
		extensions = ["tres", "res"]
	for index in range(extensions.size()):
		extensions[index] = String(extensions[index]).trim_prefix(".").to_lower()
	var name_filter := String(params.get("name", ""))
	var name_contains := String(params.get("name_contains", ""))
	var class_filter := String(params.get("class", params.get("class_name", params.get("type", params.get("type_hint", "")))))
	var resource_name := String(params.get("resource_name", ""))
	var include_dependencies := bool(params.get("include_dependencies", true))
	var include_properties := bool(params.get("include_properties", false))
	var entries := []
	_collect_filesystem_entries(
		path,
		bool(params.get("recursive", true)),
		false,
		bool(params.get("include_hidden", false)),
		{},
		max_scan_results,
		entries
	)
	var resources := []
	var total_matches := 0
	var scanned := 0
	for entry in entries:
		if not bool(entry.get("is_file", false)):
			continue
		var resource_path := String(entry.get("path", ""))
		var extension := resource_path.get_extension().to_lower()
		if not extensions.has(extension):
			continue
		scanned += 1
		var resource := _resource_file_summary(resource_path, include_dependencies, include_properties)
		if name_filter != "" and String(resource.get("name", "")) != name_filter:
			continue
		if name_contains != "" and not String(resource.get("name", "")).contains(name_contains) and not resource_path.contains(name_contains):
			continue
		if class_filter != "" and not _resource_class_matches_filter(String(resource.get("class", "")), class_filter):
			continue
		if resource_name != "" and String(resource.get("resource_name", "")) != resource_name:
			continue
		total_matches += 1
		if resources.size() >= max_results:
			continue
		resources.append(resource)
	resources.sort_custom(func(a, b): return String(a.get("path", "")) < String(b.get("path", "")))
	var summary := {
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"recursive": bool(params.get("recursive", true)),
		"include_hidden": bool(params.get("include_hidden", false)),
		"include_dependencies": include_dependencies,
		"include_properties": include_properties,
		"extensions": extensions,
		"name": name_filter,
		"name_contains": name_contains,
		"class": class_filter,
		"class_name": class_filter,
		"resource_name": resource_name,
		"resources": resources,
		"count": resources.size(),
		"total_matches": total_matches,
		"truncated": total_matches > resources.size(),
		"max_results": max_results,
		"scanned": scanned,
		"max_scan_results": max_scan_results,
		"scan_truncated": entries.size() >= max_scan_results,
	}
	_record_event("resource.files", {
		"path": path,
		"name": name_filter,
		"name_contains": name_contains,
		"class": class_filter,
		"resource_name": resource_name,
		"count": resources.size(),
		"total_matches": total_matches,
		"truncated": total_matches > resources.size(),
	})
	return _ok(summary)


func _rpc_resource_file_describe(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	if not FileAccess.file_exists(path):
		return _fail("Resource file not found: %s" % path)
	var extension := path.get_extension().to_lower()
	if not extension in ["tres", "res"]:
		return _fail("Resource file must be .tres or .res: %s" % path, -32602)
	var include_dependencies := bool(params.get("include_dependencies", true))
	var include_properties := bool(params.get("include_properties", true))
	var include_resources := bool(params.get("include_resources", true))
	var summary := _resource_file_description(
		path,
		include_dependencies,
		include_properties,
		include_resources
	)
	if bool(params.get("include_source", false)) and extension == "tres":
		summary["source"] = FileAccess.get_file_as_string(path)
	_record_event("resource.file.describe", {
		"path": path,
		"root_class": String(summary.get("root_class", "")),
		"property_count": int(summary.get("property_count", 0)),
		"ext_resource_count": int(summary.get("ext_resource_count", 0)),
		"sub_resource_count": int(summary.get("sub_resource_count", 0)),
	})
	return _ok(summary)


func _rpc_resource_inspect(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	if not ResourceLoader.exists(path):
		return _fail("Resource not found: %s" % path)
	var type_hint := String(params.get("type_hint", ""))
	var resource := ResourceLoader.load(path, type_hint)
	if resource == null:
		return _fail("Failed to load resource: %s" % path)
	var summary := _resource_summary(resource)
	if bool(params.get("include_properties", false)):
		var requested = params.get("properties", [])
		var properties := {}
		if typeof(requested) == TYPE_ARRAY and not requested.is_empty():
			for property in requested:
				properties[String(property)] = _encode_value(resource.get(String(property)))
		else:
			properties = _selected_resource_properties(resource)
		summary["properties"] = properties
	return _ok(summary)


func _rpc_resource_classes(params: Dictionary) -> Dictionary:
	var base_class := String(params.get("base_class", "Resource"))
	if base_class == "":
		base_class = "Resource"
	if not ClassDB.class_exists(base_class) and base_class != "Resource":
		return _fail("Base class not found: %s" % base_class, -32602)
	var name_contains := String(params.get("name_contains", ""))
	var include_abstract := bool(params.get("include_abstract", false))
	var include_disabled := bool(params.get("include_disabled", false))
	var include_property_counts := bool(params.get("include_property_counts", true))
	var max_results := max(1, int(params.get("max_results", 200)))
	var classes := []
	var total_matches := 0
	for raw_class_name in ClassDB.get_class_list():
		var resource_class_name := String(raw_class_name)
		if resource_class_name == "":
			continue
		if base_class != "" and resource_class_name != base_class and not ClassDB.is_parent_class(resource_class_name, base_class):
			continue
		if name_contains != "" and not resource_class_name.contains(name_contains):
			continue
		var can_instantiate := resource_class_name == "Resource" or ClassDB.can_instantiate(resource_class_name)
		if not include_abstract and not can_instantiate:
			continue
		var enabled := true
		if ClassDB.has_method("is_class_enabled"):
			enabled = bool(ClassDB.is_class_enabled(resource_class_name))
		if not include_disabled and not enabled:
			continue
		total_matches += 1
		if classes.size() >= max_results:
			continue
		classes.append(_resource_class_list_entry(resource_class_name, include_property_counts))
	classes.sort_custom(func(a, b): return String(a.get("class", "")) < String(b.get("class", "")))
	var summary := {
		"base_class": base_class,
		"name_contains": name_contains,
		"include_abstract": include_abstract,
		"include_disabled": include_disabled,
		"include_property_counts": include_property_counts,
		"classes": classes,
		"count": classes.size(),
		"total_matches": total_matches,
		"truncated": total_matches > classes.size(),
		"max_results": max_results,
	}
	_record_event("resource.classes", {
		"base_class": base_class,
		"name_contains": name_contains,
		"count": classes.size(),
		"total_matches": total_matches,
		"truncated": total_matches > classes.size(),
	})
	return _ok(summary)


func _rpc_resource_class_describe(params: Dictionary) -> Dictionary:
	var requested_class := String(params.get("class", params.get("type", params.get("class_name", "Resource"))))
	if requested_class == "":
		requested_class = "Resource"
	var exists := requested_class == "Resource" or ClassDB.class_exists(requested_class)
	var can_instantiate := requested_class == "Resource" or (exists and ClassDB.can_instantiate(requested_class))
	var is_resource_class := requested_class == "Resource" or (exists and ClassDB.is_parent_class(requested_class, "Resource"))
	var summary := {
		"requested_class": requested_class,
		"class": requested_class,
		"exists": exists,
		"can_instantiate": can_instantiate,
		"is_resource": is_resource_class,
		"properties": [],
		"property_count": 0,
		"storage_property_count": 0,
		"editor_property_count": 0,
		"values": {},
	}
	if not exists or not can_instantiate or not is_resource_class:
		return _ok(summary)
	var resource := _instantiate_resource_class(requested_class)
	if resource == null:
		summary["can_instantiate"] = false
		return _ok(summary)
	summary["class"] = resource.get_class()
	var property_filter := _string_filter_array(params.get("properties", []))
	var name_contains := String(params.get("name_contains", ""))
	var include_internal := bool(params.get("include_internal", false))
	var storage_only := bool(params.get("storage_only", false))
	var include_values := bool(params.get("include_values", true))
	var properties := []
	var values := {}
	var storage_count := 0
	var editor_count := 0
	for info in resource.get_property_list():
		if typeof(info) != TYPE_DICTIONARY:
			continue
		var name := String(info.get("name", ""))
		if name == "":
			continue
		if not include_internal and name.begins_with("_"):
			continue
		if not property_filter.is_empty() and not property_filter.has(name):
			continue
		if name_contains != "" and not name.contains(name_contains):
			continue
		var property_summary := _resource_property_schema(resource, info, include_values)
		if storage_only and not bool(property_summary.get("storage", false)):
			continue
		if bool(property_summary.get("storage", false)):
			storage_count += 1
		if bool(property_summary.get("editor_visible", false)):
			editor_count += 1
		properties.append(property_summary)
		if include_values:
			values[name] = property_summary.get("value", null)
	summary["properties"] = properties
	summary["property_count"] = properties.size()
	summary["storage_property_count"] = storage_count
	summary["editor_property_count"] = editor_count
	if include_values:
		summary["values"] = values
	_record_event("resource.class.describe", {
		"class": requested_class,
		"property_count": properties.size(),
		"storage_only": storage_only,
	})
	return _ok(summary)


func _rpc_resource_dependencies(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var summary := _resource_dependencies_payload(path, true)
	return _ok(summary)


func _rpc_resource_references(params: Dictionary) -> Dictionary:
	var target_path := String(params.get("path", params.get("target_path", params.get("target", ""))))
	var target_uid := String(params.get("uid", ""))
	if target_path == "" and target_uid == "":
		return _fail("path or uid is required", -32602)
	if target_path != "":
		var target_error := _validate_res_path(target_path)
		if target_error != "":
			return _fail(target_error, -32602)
	var search_path := String(params.get("search_path", "res://"))
	var search_error := _validate_res_path(search_path)
	if search_error != "":
		return _fail(search_error, -32602)
	var max_results := max(1, int(params.get("max_results", 200)))
	var max_scan_results := max(max_results, int(params.get("max_scan_results", max_results * 20)))
	var extensions := _normalized_extension_filter(
		params.get("extensions", params.get("extension", [])),
		["tscn", "scn", "tres", "res"]
	)
	var dependency_type := String(params.get("dependency_type", params.get("type", "")))
	var resource_type := String(params.get("resource_type", ""))
	var exists_filter = params.get("exists", null)
	var summary := _resource_references_payload(
		target_path,
		target_uid,
		search_path,
		dependency_type,
		resource_type,
		exists_filter,
		extensions,
		bool(params.get("recursive", true)),
		bool(params.get("include_hidden", false)),
		max_results,
		max_scan_results
	)
	_record_event("resource.references", {
		"path": target_path,
		"uid": target_uid,
		"search_path": search_path,
		"count": int(summary.get("count", 0)),
		"total_matches": int(summary.get("total_matches", 0)),
		"truncated": bool(summary.get("truncated", false)),
	})
	return _ok(summary)


func _rpc_resource_move(params: Dictionary) -> Dictionary:
	var source := String(params.get("source", params.get("from", params.get("path", ""))))
	var destination := String(params.get("destination", params.get("to", "")))
	var source_error := _validate_res_path(source)
	if source_error != "":
		return _fail(source_error, -32602)
	var destination_error := _validate_res_path(destination)
	if destination_error != "":
		return _fail(destination_error, -32602)
	if source == "res://":
		return _fail("Refusing to move project root", -32602)
	if source == destination:
		return _fail("source and destination must differ", -32602)
	if not FileAccess.file_exists(source):
		if DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(source)):
			return _fail("resource.move only moves files; use fs.move for directories", -32602)
		return _fail("Source file not found: %s" % source)
	if DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(destination)):
		return _fail("Destination is a directory: %s" % destination, -32602)
	var destination_exists := FileAccess.file_exists(destination)
	var overwrite := bool(params.get("overwrite", true))
	if destination_exists and not overwrite:
		return _fail("Destination already exists: %s" % destination)
	var dry_run := bool(params.get("dry_run", false))
	var update_references := bool(params.get("update_references", true))
	var search_path := String(params.get("search_path", "res://"))
	var search_error := _validate_res_path(search_path)
	if search_error != "":
		return _fail(search_error, -32602)
	var recursive := bool(params.get("recursive", true))
	var include_hidden := bool(params.get("include_hidden", false))
	var extensions := _normalized_extension_filter(
		params.get("extensions", params.get("extension", [])),
		["tscn", "tres"]
	)
	var max_reference_files := max(1, int(params.get("max_reference_files", params.get("max_results", 200))))
	var max_scan_results := max(max_reference_files, int(params.get("max_scan_results", max_reference_files * 20)))
	var max_replacements_per_file := int(params.get("max_replacements_per_file", 100))
	if max_replacements_per_file < 0:
		return _fail("max_replacements_per_file must be >= 0", -32602)
	var max_total_replacements := int(params.get("max_total_replacements", 500))
	if max_total_replacements < 0:
		return _fail("max_total_replacements must be >= 0", -32602)
	var expected_reference_files := int(params.get("expected_reference_files", params.get("expected_files", -1)))
	if expected_reference_files < -1:
		return _fail("expected_reference_files must be >= -1", -32602)
	var expected_replacements := int(params.get("expected_replacements", -1))
	if expected_replacements < -1:
		return _fail("expected_replacements must be >= -1", -32602)
	var max_preview := max(0, int(params.get("max_preview", 20)))
	var include_text := bool(params.get("include_text", false))
	var references_before := {}
	var reference_updates := []
	var unpatched_references := []
	var total_replacements := 0
	if update_references:
		references_before = _resource_references_payload(
			source,
			"",
			search_path,
			"",
			"",
			null,
			extensions,
			recursive,
			include_hidden,
			max_reference_files,
			max_scan_results
		)
		if bool(references_before.get("truncated", false)) and not bool(params.get("allow_truncated", false)):
			return _fail(
				"Reference scan for %s was truncated; raise max_reference_files or pass allow_truncated=true" % source,
				-32000,
				references_before
			)
		if bool(references_before.get("scan_truncated", false)) and not bool(params.get("allow_scan_truncated", false)):
			return _fail(
				"Reference filesystem scan for %s was truncated; raise max_scan_results or pass allow_scan_truncated=true" % source,
				-32000,
				references_before
			)
		for reference in references_before.get("references", []):
			var reference_path := String(reference.get("path", ""))
			if reference_path == "":
				continue
			if not _is_text_search_path(reference_path):
				var non_text: Dictionary = reference.duplicate()
				non_text["reason"] = "non_text_reference_file"
				unpatched_references.append(non_text)
				continue
			var reference_text := FileAccess.get_file_as_string(reference_path)
			var open_error := FileAccess.get_open_error()
			if open_error != OK:
				return _fail("Failed to read %s: %s" % [reference_path, open_error])
			var replacement := _replace_text_with_evidence(
				reference_text,
				source,
				destination,
				true,
				0,
				max_preview
			)
			var match_count := int(replacement.get("match_count", 0))
			if match_count <= 0:
				var missing_text: Dictionary = reference.duplicate()
				missing_text["reason"] = "path_text_not_found"
				unpatched_references.append(missing_text)
				continue
			if max_replacements_per_file > 0 and match_count > max_replacements_per_file:
				return _fail(
					"Replacement count %s exceeds max_replacements_per_file %s in %s" % [match_count, max_replacements_per_file, reference_path],
					-32000,
					{
						"path": reference_path,
						"max_replacements_per_file": max_replacements_per_file,
						"match_count": match_count,
						"edits": replacement.get("edits", []),
					}
				)
			total_replacements += match_count
			if max_total_replacements > 0 and total_replacements > max_total_replacements:
				return _fail(
					"Replacement count %s exceeds max_total_replacements %s" % [total_replacements, max_total_replacements],
					-32000,
					{
						"source": source,
						"destination": destination,
						"max_total_replacements": max_total_replacements,
						"match_count": total_replacements,
						"last_path": reference_path,
					}
				)
			var after_text := String(replacement.get("text", reference_text))
			var write_path := destination if reference_path == source else reference_path
			var after_summary := {
				"path": write_path,
				"name": write_path.get_file(),
				"global_path": ProjectSettings.globalize_path(write_path),
				"exists": true,
				"bytes": after_text.to_utf8_buffer().size(),
			}
			var change := {
				"path": reference_path,
				"write_path": write_path,
				"global_path": ProjectSettings.globalize_path(reference_path),
				"changed": after_text != reference_text,
				"match_count": match_count,
				"replacements": match_count,
				"bytes_before": reference_text.to_utf8_buffer().size(),
				"bytes_after": after_text.to_utf8_buffer().size(),
				"file_before": _file_summary(reference_path),
				"file_after": after_summary,
				"dependency": reference.get("dependency", {}),
				"edits": replacement.get("edits", []),
				"_text": after_text,
			}
			if include_text:
				change["text"] = after_text
			reference_updates.append(change)
	if expected_reference_files >= 0 and reference_updates.size() != expected_reference_files:
		return _fail(
			"Expected %s reference files for %s, found %s" % [expected_reference_files, source, reference_updates.size()],
			-32000,
			{
				"source": source,
				"destination": destination,
				"expected_reference_files": expected_reference_files,
				"changed_reference_files": reference_updates.size(),
				"references_before": references_before,
				"reference_updates": _public_bulk_replace_changes(reference_updates),
			}
		)
	if expected_replacements >= 0 and total_replacements != expected_replacements:
		return _fail(
			"Expected %s reference replacements for %s, found %s" % [expected_replacements, source, total_replacements],
			-32000,
			{
				"source": source,
				"destination": destination,
				"expected_replacements": expected_replacements,
				"reference_replacements": total_replacements,
				"references_before": references_before,
				"reference_updates": _public_bulk_replace_changes(reference_updates),
			}
		)
	if not dry_run and not unpatched_references.is_empty() and not bool(params.get("allow_unpatched", false)):
		return _fail(
			"Some references to %s could not be patched; run dry_run for details or pass allow_unpatched=true" % source,
			-32000,
			{"source": source, "destination": destination, "unpatched_references": unpatched_references}
		)
	var source_before := _file_summary(source)
	var destination_before := _file_summary(destination)
	if not dry_run:
		if bool(params.get("create_dirs", true)):
			var dir_error := _ensure_res_parent_dir(destination)
			if dir_error != OK:
				return _fail("Failed to create parent directories for %s: %s" % [destination, dir_error])
		if destination_exists:
			var remove_error := _remove_res_path(destination)
			if remove_error != OK:
				return _fail("Failed to remove destination %s: %s" % [destination, remove_error])
		var move_error := DirAccess.rename_absolute(ProjectSettings.globalize_path(source), ProjectSettings.globalize_path(destination))
		if move_error != OK:
			return _fail("Failed to move %s to %s: %s" % [source, destination, move_error])
		_scan_editor_filesystem(source.get_base_dir())
		_scan_editor_filesystem(destination)
		for change in reference_updates:
			var write_path := String(change.get("write_path", change.get("path", "")))
			var file := FileAccess.open(write_path, FileAccess.WRITE)
			if file == null:
				return _fail("Failed to open %s for writing: %s" % [write_path, FileAccess.get_open_error()])
			file.store_string(String(change.get("_text", "")))
			file.close()
			_scan_editor_filesystem(write_path)
		for change in reference_updates:
			change["file_after"] = _file_summary(String(change.get("write_path", change.get("path", ""))))
	var references_after := {}
	var remaining_source_references := {}
	if update_references and not dry_run:
		references_after = _resource_references_payload(
			destination,
			"",
			search_path,
			"",
			"",
			null,
			extensions,
			recursive,
			include_hidden,
			max_reference_files,
			max_scan_results
		)
		remaining_source_references = _resource_references_payload(
			source,
			"",
			search_path,
			"",
			"",
			null,
			extensions,
			recursive,
			include_hidden,
			max_reference_files,
			max_scan_results
		)
	var destination_after := _file_summary(destination) if not dry_run else {
		"path": destination,
		"name": destination.get_file(),
		"global_path": ProjectSettings.globalize_path(destination),
		"exists": true,
		"bytes": int(source_before.get("bytes", -1)),
		"modified_time": 0,
	}
	_record_event("resource.move", {
		"source": source,
		"destination": destination,
		"update_references": update_references,
		"dry_run": dry_run,
		"search_path": search_path,
		"extensions": extensions,
		"expected_reference_files": expected_reference_files,
		"expected_replacements": expected_replacements,
		"changed_reference_files": reference_updates.size(),
		"reference_replacements": total_replacements,
		"overwrite": overwrite,
		"create_dirs": bool(params.get("create_dirs", true)),
		"max_reference_files": max_reference_files,
		"max_scan_results": max_scan_results,
	})
	return _ok({
		"source": source,
		"destination": destination,
		"global_source": ProjectSettings.globalize_path(source),
		"global_destination": ProjectSettings.globalize_path(destination),
		"type": "file",
		"dry_run": dry_run,
		"moved": not dry_run,
		"update_references": update_references,
		"search_path": search_path,
		"recursive": recursive,
		"include_hidden": include_hidden,
		"extensions": extensions,
		"overwrite": overwrite,
		"would_overwrite": destination_exists,
		"source_before": source_before,
		"destination_before": destination_before,
		"destination_after": destination_after,
		"bytes": int(destination_after.get("bytes", -1)),
		"references_before": references_before,
		"references_after": references_after,
		"remaining_source_references": remaining_source_references,
		"reference_updates": _public_bulk_replace_changes(reference_updates),
		"changed_reference_files": reference_updates.size(),
		"reference_replacements": total_replacements,
		"unpatched_references": unpatched_references,
		"unpatched_reference_count": unpatched_references.size(),
		"max_reference_files": max_reference_files,
		"max_replacements_per_file": max_replacements_per_file,
		"max_total_replacements": max_total_replacements,
	})


func _resource_references_payload(
	target_path: String,
	target_uid: String,
	search_path: String,
	dependency_type: String,
	resource_type: String,
	exists_filter: Variant,
	extensions: Array,
	recursive: bool,
	include_hidden: bool,
	max_results: int,
	max_scan_results: int
) -> Dictionary:
	var entries := []
	_collect_filesystem_entries(
		search_path,
		recursive,
		false,
		include_hidden,
		{},
		max_scan_results,
		entries
	)
	var references := []
	var total_matches := 0
	var scanned := 0
	for entry in entries:
		if not bool(entry.get("is_file", false)):
			continue
		var file_path := String(entry.get("path", ""))
		var extension := file_path.get_extension().to_lower()
		if not extensions.has(extension):
			continue
		scanned += 1
		if not FileAccess.file_exists(file_path) and not ResourceLoader.exists(file_path):
			continue
		for raw_dependency in ResourceLoader.get_dependencies(file_path):
			var dependency := _resource_dependency_summary(String(raw_dependency))
			if not _resource_dependency_matches_reference(
				dependency,
				target_path,
				target_uid,
				dependency_type,
				resource_type,
				exists_filter
			):
				continue
			total_matches += 1
			if references.size() < max_results:
				references.append({
					"path": file_path,
					"name": file_path.get_file(),
					"global_path": ProjectSettings.globalize_path(file_path),
					"extension": extension,
					"resource_type": _resource_type_for_path(file_path),
					"dependency": dependency,
				})
			break
	references.sort_custom(func(a, b): return String(a.get("path", "")) < String(b.get("path", "")))
	var summary := {
		"path": target_path,
		"target_path": target_path,
		"uid": target_uid,
		"target_uid": target_uid,
		"search_path": search_path,
		"global_search_path": ProjectSettings.globalize_path(search_path),
		"recursive": recursive,
		"include_hidden": include_hidden,
		"extensions": extensions,
		"dependency_type": dependency_type,
		"resource_type": resource_type,
		"exists": exists_filter,
		"references": references,
		"count": references.size(),
		"total_matches": total_matches,
		"truncated": total_matches > references.size(),
		"max_results": max_results,
		"scanned": scanned,
		"max_scan_results": max_scan_results,
		"scan_truncated": entries.size() >= max_scan_results,
	}
	return summary


func _rpc_resource_imports(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", "res://"))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var max_results := max(1, int(params.get("max_results", 200)))
	var max_scan_results := max(max_results, int(params.get("max_scan_results", max_results * 20)))
	var extensions := _string_filter_array(params.get("extensions", params.get("extension", [])))
	if extensions.is_empty():
		extensions = _importable_resource_extensions()
	for index in range(extensions.size()):
		extensions[index] = String(extensions[index]).trim_prefix(".").to_lower()
	var name_filter := String(params.get("name", ""))
	var name_contains := String(params.get("name_contains", ""))
	var importer_filter := String(params.get("importer", ""))
	var resource_type_filter := String(params.get("resource_type", params.get("type", "")))
	var generated_ready_filter = params.get("generated_files_ready", null)
	var imported_filter = params.get("imported", null)
	var ok_filter = params.get("ok", null)
	var include_missing_metadata := bool(params.get("include_missing_metadata", true))
	var entries := []
	_collect_filesystem_entries(
		path,
		bool(params.get("recursive", true)),
		false,
		bool(params.get("include_hidden", false)),
		{},
		max_scan_results,
		entries
	)
	var imports := []
	var total_matches := 0
	var scanned := 0
	for entry in entries:
		if not bool(entry.get("is_file", false)):
			continue
		var source_path := String(entry.get("path", ""))
		if source_path.ends_with(".import"):
			continue
		var extension := source_path.get_extension().to_lower()
		if not extensions.has(extension):
			continue
		scanned += 1
		var import_summary := _resource_import_metadata_entry(source_path)
		if not include_missing_metadata and not bool(import_summary.get("exists", false)):
			continue
		if name_filter != "" and source_path.get_file() != name_filter:
			continue
		if name_contains != "" and not source_path.get_file().contains(name_contains) and not source_path.contains(name_contains):
			continue
		if importer_filter != "" and String(import_summary.get("importer", "")) != importer_filter:
			continue
		if resource_type_filter != "" and String(import_summary.get("resource_type", "")) != resource_type_filter and String(import_summary.get("type", "")) != resource_type_filter:
			continue
		if generated_ready_filter != null and bool(import_summary.get("generated_files_ready", false)) != bool(generated_ready_filter):
			continue
		if imported_filter != null and bool(import_summary.get("imported", false)) != bool(imported_filter):
			continue
		if ok_filter != null and bool(import_summary.get("ok", false)) != bool(ok_filter):
			continue
		total_matches += 1
		if imports.size() >= max_results:
			continue
		imports.append(import_summary)
	imports.sort_custom(func(a, b): return String(a.get("path", "")) < String(b.get("path", "")))
	var summary := {
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"recursive": bool(params.get("recursive", true)),
		"include_hidden": bool(params.get("include_hidden", false)),
		"include_missing_metadata": include_missing_metadata,
		"extensions": extensions,
		"name": name_filter,
		"name_contains": name_contains,
		"importer": importer_filter,
		"resource_type": resource_type_filter,
		"generated_files_ready": generated_ready_filter,
		"imported": imported_filter,
		"ok": ok_filter,
		"imports": imports,
		"count": imports.size(),
		"total_matches": total_matches,
		"truncated": total_matches > imports.size(),
		"max_results": max_results,
		"scanned": scanned,
		"max_scan_results": max_scan_results,
		"scan_truncated": entries.size() >= max_scan_results,
	}
	_record_event("resource.imports", {
		"path": path,
		"importer": importer_filter,
		"resource_type": resource_type_filter,
		"count": imports.size(),
		"total_matches": total_matches,
		"truncated": total_matches > imports.size(),
	})
	return _ok(summary)


func _resource_import_metadata_entry(path: String) -> Dictionary:
	var result := _rpc_resource_import_metadata({"path": path})
	if bool(result.get("ok", false)):
		var value = result.get("value", {})
		if typeof(value) == TYPE_DICTIONARY:
			return value
	return {
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"source_exists": FileAccess.file_exists(path),
		"import_path": "%s.import" % path,
		"exists": false,
		"imported": false,
		"resource_exists": ResourceLoader.exists(path),
		"resource_type": _resource_type_for_path(path),
		"importer": "",
		"type": "",
		"generated_files_ready": false,
		"generated_file_count": 0,
		"diagnostics": [{"kind": "IMPORT_METADATA_ERROR", "severity": "error", "path": path}],
		"diagnostic_count": 1,
		"error_count": 1,
		"warning_count": 0,
		"ok": false,
	}


func _importable_resource_extensions() -> Array:
	return [
		"apng",
		"bmp",
		"exr",
		"fbx",
		"glb",
		"gltf",
		"hdr",
		"jpg",
		"jpeg",
		"mp3",
		"obj",
		"ogg",
		"otf",
		"png",
		"svg",
		"tga",
		"ttf",
		"wav",
		"webp",
		"woff",
		"woff2",
	]


func _resource_file_summary(path: String, include_dependencies: bool, include_properties: bool) -> Dictionary:
	var entry := _filesystem_entry(path)
	var file_exists := bool(entry.get("is_file", false))
	var resource_exists := ResourceLoader.exists(path)
	var resource: Resource = null
	if resource_exists:
		resource = ResourceLoader.load(path)
	var resource_class := String(entry.get("resource_type", ""))
	var resource_name := ""
	if resource != null:
		resource_class = resource.get_class()
		resource_name = resource.resource_name
	var summary := {
		"path": path,
		"name": path.get_file(),
		"global_path": ProjectSettings.globalize_path(path),
		"exists": file_exists or resource_exists,
		"file_exists": file_exists,
		"resource_exists": resource_exists,
		"load_error": resource_exists and resource == null,
		"extension": path.get_extension().to_lower(),
		"class": resource_class,
		"class_name": resource_class,
		"type": resource_class,
		"resource_type": resource_class,
		"resource_name": resource_name,
		"ok": (file_exists or resource_exists) and not (resource_exists and resource == null),
	}
	if include_properties and resource != null:
		summary["properties"] = _selected_resource_properties(resource)
	if include_dependencies:
		var dependency_state := _resource_dependencies_payload(path, false)
		summary["dependencies"] = dependency_state.get("dependencies", [])
		summary["dependency_count"] = int(dependency_state.get("dependency_count", 0))
		summary["missing"] = dependency_state.get("missing", [])
		summary["missing_count"] = int(dependency_state.get("missing_count", 0))
		summary["ok"] = bool(summary.get("ok", false)) and bool(dependency_state.get("ok", false))
	return summary


func _resource_file_description(
	path: String,
	include_dependencies: bool,
	include_properties: bool,
	include_resources: bool
) -> Dictionary:
	var summary := _resource_file_summary(path, include_dependencies, false)
	var extension := path.get_extension().to_lower()
	summary["file_format"] = "text" if extension == "tres" else "binary"
	summary["is_resource_file"] = extension in ["tres", "res"]
	summary["root_class"] = String(summary.get("class", ""))
	summary["root_type"] = String(summary.get("class", ""))
	summary["script_class"] = ""
	summary["resource_uid"] = ""
	summary["load_steps"] = 0
	summary["format"] = 0
	summary["header"] = {}
	summary["root"] = {}
	summary["property_count"] = 0
	if include_properties:
		summary["properties"] = {}
	if include_resources:
		summary["ext_resources"] = []
		summary["ext_resource_count"] = 0
		summary["sub_resources"] = []
		summary["sub_resource_count"] = 0
	if extension == "tres":
		var source := FileAccess.get_file_as_string(path)
		var open_error := FileAccess.get_open_error()
		summary["open_error"] = int(open_error)
		if open_error == OK:
			var text_summary := _text_resource_file_summary(source, include_properties, include_resources)
			for key in text_summary.keys():
				summary[key] = text_summary[key]
		else:
			summary["read_error"] = int(open_error)
			summary["ok"] = false
	return summary


func _text_resource_file_summary(source: String, include_properties: bool, include_resources: bool) -> Dictionary:
	var header := {}
	var root := {}
	var ext_resources := []
	var sub_resources := []
	var current := {}
	var current_section := ""
	var lines := source.split("\n")
	for index in range(lines.size()):
		var line := String(lines[index]).strip_edges()
		if line == "" or line.begins_with(";"):
			continue
		if line.begins_with("["):
			current = {}
			current_section = ""
			if line.begins_with("[gd_resource"):
				header = _resource_header_summary(_scene_tag_attributes(line), index + 1)
			elif line.begins_with("[ext_resource "):
				ext_resources.append(_scene_ext_resource_summary(_scene_tag_attributes(line), index + 1))
			elif line.begins_with("[sub_resource "):
				var sub_resource := _scene_sub_resource_summary(_scene_tag_attributes(line), index + 1)
				sub_resources.append(sub_resource)
				current = sub_resource
				current_section = "sub_resource"
			elif line.begins_with("[resource"):
				root = _resource_root_summary(_scene_tag_attributes(line), index + 1, header)
				current = root
				current_section = "resource"
			continue
		if include_properties and current_section in ["resource", "sub_resource"] and line.find("=") != -1:
			var equals := line.find("=")
			var property_name := line.substr(0, equals).strip_edges()
			var raw_value := line.substr(equals + 1).strip_edges()
			var properties: Dictionary = current.get("properties", {})
			properties[property_name] = _scene_property_value(raw_value)
			current["properties"] = properties
			current["property_count"] = properties.size()
	if root.is_empty():
		root = _resource_root_summary({}, 0, header)
	var ext_by_id := {}
	for resource in ext_resources:
		var resource_id := String(resource.get("id", ""))
		if resource_id != "":
			ext_by_id[resource_id] = resource
	_resource_finalize_root_summary(root, ext_by_id, include_properties)
	var root_class := String(root.get("type", ""))
	var summary := {
		"header": header,
		"root": root,
		"root_class": root_class,
		"root_type": root_class,
		"script_class": String(header.get("script_class", "")),
		"resource_uid": String(header.get("uid", "")),
		"load_steps": int(header.get("load_steps", 0)),
		"format": int(header.get("format", 0)),
		"property_count": int(root.get("property_count", 0)),
	}
	if include_properties:
		summary["properties"] = root.get("properties", {})
	if include_resources:
		summary["ext_resources"] = ext_resources
		summary["ext_resource_count"] = ext_resources.size()
		summary["sub_resources"] = sub_resources if include_properties else _scene_public_sub_resources(sub_resources)
		summary["sub_resource_count"] = sub_resources.size()
	return summary


func _resource_header_summary(attrs: Dictionary, line_number: int) -> Dictionary:
	return {
		"type": String(attrs.get("type", "")),
		"class": String(attrs.get("type", "")),
		"script_class": String(attrs.get("script_class", "")),
		"load_steps": _safe_int(attrs.get("load_steps", 0)),
		"format": _safe_int(attrs.get("format", 0)),
		"uid": String(attrs.get("uid", "")),
		"line": line_number,
	}


func _resource_root_summary(attrs: Dictionary, line_number: int, header: Dictionary) -> Dictionary:
	var type_name := String(attrs.get("type", header.get("type", "")))
	return {
		"type": type_name,
		"class": type_name,
		"script_class": String(header.get("script_class", "")),
		"line": line_number,
		"properties": {},
		"property_count": 0,
		"script": "",
	}


func _resource_finalize_root_summary(root: Dictionary, ext_by_id: Dictionary, include_properties: bool) -> void:
	if include_properties:
		var properties: Dictionary = root.get("properties", {})
		var script_resource := _scene_reference_resource(properties.get("script", null), ext_by_id)
		if not script_resource.is_empty():
			root["script"] = String(script_resource.get("path", ""))
	else:
		root.erase("properties")


func _safe_int(value: Variant) -> int:
	if value == null:
		return 0
	var text := str(value)
	if text.is_valid_int():
		return int(text)
	return 0


func _resource_class_matches_filter(actual_class: String, expected_class: String) -> bool:
	if expected_class == "":
		return true
	if actual_class == expected_class:
		return true
	if actual_class == "" or expected_class == "":
		return false
	if ClassDB.class_exists(actual_class) and ClassDB.class_exists(expected_class):
		return ClassDB.is_parent_class(actual_class, expected_class)
	return false


func _resource_dependencies_payload(path: String, record: bool = true) -> Dictionary:
	var file_exists := FileAccess.file_exists(path)
	var resource_exists := ResourceLoader.exists(path)
	var dependencies := []
	if file_exists or resource_exists:
		for raw_dependency in ResourceLoader.get_dependencies(path):
			dependencies.append(_resource_dependency_summary(String(raw_dependency)))
	var missing := []
	for dependency in dependencies:
		if bool(dependency.get("checked", false)) and not bool(dependency.get("exists", false)):
			missing.append(dependency)
	var summary := {
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"exists": file_exists or resource_exists,
		"file_exists": file_exists,
		"resource_exists": resource_exists,
		"ok": (file_exists or resource_exists) and missing.is_empty(),
		"dependencies": dependencies,
		"dependency_count": dependencies.size(),
		"missing": missing,
		"missing_count": missing.size(),
	}
	if record:
		_record_event("resource.dependencies", {
			"path": path,
			"dependency_count": dependencies.size(),
			"missing_count": missing.size(),
		})
	return summary


func _rpc_resource_import_metadata(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var import_path := "%s.import" % path
	var import_path_error := _validate_res_path(import_path)
	if import_path_error != "":
		return _fail(import_path_error, -32602)
	var source_exists := FileAccess.file_exists(path)
	var import_exists := FileAccess.file_exists(import_path)
	var source_file_state := _file_summary(path)
	var import_file_state := _file_summary(import_path)
	var diagnostics := []
	var summary := {
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"source_exists": source_exists,
		"import_path": import_path,
		"import_file": import_file_state,
		"source_file_state": source_file_state,
		"exists": import_exists,
		"imported": false,
		"resource_exists": ResourceLoader.exists(path),
		"resource_type": _resource_type_for_path(path),
		"importer": "",
		"type": "",
		"uid": "",
		"source_file": "",
		"source_file_matches_path": true,
		"dest_files": [],
		"generated_files": [],
		"generated_files_ready": false,
		"generated_file_count": 0,
		"missing_generated_files": [],
		"missing_generated_file_count": 0,
		"stale_generated_files": [],
		"stale_generated_file_count": 0,
		"import_file_stale": false,
		"parse_error": OK,
		"remap": {},
		"deps": {},
		"params": {},
		"sections": {},
		"diagnostics": diagnostics,
		"diagnostic_count": 0,
		"error_count": 0,
		"warning_count": 0,
		"ok": false,
	}
	if not source_exists:
		diagnostics.append({
			"kind": "IMPORT_SOURCE_MISSING",
			"severity": "error",
			"path": path,
			"message": "Import source file is missing: %s" % path,
		})
	if not import_exists:
		diagnostics.append({
			"kind": "IMPORT_FILE_MISSING",
			"severity": "warning" if source_exists else "error",
			"path": import_path,
			"source": path,
			"message": "Import metadata file is missing: %s" % import_path,
		})
		_set_import_metadata_diagnostics(summary, diagnostics)
		_record_event("resource.import_metadata", {
			"path": path,
			"exists": false,
			"diagnostic_count": diagnostics.size(),
		})
		return _ok(summary)
	var config := ConfigFile.new()
	var load_error := config.load(import_path)
	if load_error != OK:
		summary["parse_error"] = load_error
		diagnostics.append({
			"kind": "IMPORT_METADATA_PARSE_ERROR",
			"severity": "error",
			"path": import_path,
			"source": path,
			"message": "Failed to read import metadata %s: %s" % [import_path, load_error],
			"code": load_error,
		})
		_set_import_metadata_diagnostics(summary, diagnostics)
		_record_event("resource.import_metadata", {
			"path": path,
			"exists": import_exists,
			"diagnostic_count": diagnostics.size(),
		})
		return _ok(summary)
	var sections := {}
	for section in config.get_sections():
		var section_values := {}
		for key in config.get_section_keys(section):
			section_values[String(key)] = _encode_value(config.get_value(section, key))
		sections[String(section)] = section_values
	var remap = sections.get("remap", {})
	var deps = sections.get("deps", {})
	var params_section = sections.get("params", {})
	var dest_files := []
	if typeof(deps) == TYPE_DICTIONARY:
		var raw_dest_files = deps.get("dest_files", [])
		if typeof(raw_dest_files) == TYPE_ARRAY:
			for item in raw_dest_files:
				dest_files.append(String(item))
		elif typeof(raw_dest_files) == TYPE_STRING and String(raw_dest_files) != "":
			dest_files.append(String(raw_dest_files))
	var generated_files := []
	var missing_generated_files := []
	var stale_generated_files := []
	var generated_files_ready := not dest_files.is_empty()
	var source_file := String(deps.get("source_file", "")) if typeof(deps) == TYPE_DICTIONARY else ""
	var effective_source_file := source_file if source_file != "" else path
	var effective_source_state := _file_summary(effective_source_file)
	var source_modified_time := int(effective_source_state.get("modified_time", 0))
	var import_modified_time := int(import_file_state.get("modified_time", 0))
	var import_file_stale := source_modified_time > 0 and import_modified_time > 0 and import_modified_time < source_modified_time
	if source_file != "" and source_file != path:
		diagnostics.append({
			"kind": "IMPORT_SOURCE_MISMATCH",
			"severity": "warning",
			"path": import_path,
			"source": path,
			"source_file": source_file,
			"message": "Import metadata source_file %s does not match requested path %s" % [source_file, path],
		})
	if not bool(effective_source_state.get("exists", false)) and not (effective_source_file == path and not source_exists):
		diagnostics.append({
			"kind": "IMPORT_SOURCE_MISSING",
			"severity": "error",
			"path": effective_source_file,
			"source": path,
			"message": "Import source file is missing: %s" % effective_source_file,
		})
	if import_file_stale:
		diagnostics.append({
			"kind": "IMPORT_FILE_STALE",
			"severity": "warning",
			"path": import_path,
			"source": effective_source_file,
			"message": "Import metadata is older than its source file",
			"source_modified_time": source_modified_time,
			"import_modified_time": import_modified_time,
		})
	for dest_file in dest_files:
		var file_summary := _file_summary(String(dest_file))
		generated_files.append(file_summary)
		if not bool(file_summary.get("exists", false)):
			generated_files_ready = false
			missing_generated_files.append(file_summary)
			diagnostics.append({
				"kind": "GENERATED_IMPORT_FILE_MISSING",
				"severity": "error",
				"path": String(dest_file),
				"source": path,
				"message": "Generated import file is missing: %s" % String(dest_file),
			})
		elif source_modified_time > 0 and int(file_summary.get("modified_time", 0)) > 0 and int(file_summary.get("modified_time", 0)) < source_modified_time:
			stale_generated_files.append(file_summary)
			diagnostics.append({
				"kind": "GENERATED_IMPORT_FILE_STALE",
				"severity": "warning",
				"path": String(dest_file),
				"source": effective_source_file,
				"message": "Generated import file is older than its source file",
				"source_modified_time": source_modified_time,
				"generated_modified_time": int(file_summary.get("modified_time", 0)),
			})
	if dest_files.is_empty():
		diagnostics.append({
			"kind": "IMPORT_DEST_FILES_MISSING",
			"severity": "warning",
			"path": import_path,
			"source": path,
			"message": "Import metadata does not list generated destination files",
		})
	var resource_type := String(remap.get("type", "")) if typeof(remap) == TYPE_DICTIONARY else ""
	if resource_type == "":
		resource_type = _resource_type_for_path(path)
	var importer := String(remap.get("importer", "")) if typeof(remap) == TYPE_DICTIONARY else ""
	if importer == "":
		diagnostics.append({
			"kind": "IMPORTER_MISSING",
			"severity": "warning",
			"path": import_path,
			"source": path,
			"message": "Import metadata does not declare a remap/importer value",
		})
	summary["sections"] = sections
	summary["remap"] = remap if typeof(remap) == TYPE_DICTIONARY else {}
	summary["deps"] = deps if typeof(deps) == TYPE_DICTIONARY else {}
	summary["params"] = params_section if typeof(params_section) == TYPE_DICTIONARY else {}
	summary["importer"] = importer
	summary["type"] = resource_type
	summary["resource_type"] = resource_type
	summary["uid"] = String(remap.get("uid", "")) if typeof(remap) == TYPE_DICTIONARY else ""
	summary["source_file"] = source_file
	summary["source_file_state"] = effective_source_state
	summary["source_file_matches_path"] = source_file == "" or source_file == path
	summary["dest_files"] = dest_files
	summary["generated_files"] = generated_files
	summary["generated_files_ready"] = generated_files_ready
	summary["generated_file_count"] = generated_files.size()
	summary["missing_generated_files"] = missing_generated_files
	summary["missing_generated_file_count"] = missing_generated_files.size()
	summary["stale_generated_files"] = stale_generated_files
	summary["stale_generated_file_count"] = stale_generated_files.size()
	summary["import_file_stale"] = import_file_stale
	summary["resource_exists"] = ResourceLoader.exists(path)
	if not bool(summary.get("resource_exists", false)):
		diagnostics.append({
			"kind": "IMPORTED_RESOURCE_NOT_LOADABLE",
			"severity": "error",
			"path": path,
			"message": "Imported resource is not loadable through ResourceLoader: %s" % path,
		})
	summary["imported"] = bool(summary.get("resource_exists", false)) and generated_files_ready
	_set_import_metadata_diagnostics(summary, diagnostics)
	_record_event("resource.import_metadata", {
		"path": path,
		"exists": import_exists,
		"resource_type": resource_type,
		"diagnostic_count": diagnostics.size(),
	})
	return _ok(summary)


func _rpc_resource_reimport(params: Dictionary) -> Dictionary:
	var raw_paths = params.get("paths", null)
	if typeof(raw_paths) == TYPE_NIL:
		raw_paths = [params.get("path", "")]
	elif typeof(raw_paths) != TYPE_ARRAY:
		raw_paths = [raw_paths]
	elif raw_paths.is_empty() and params.has("path"):
		raw_paths = [params.get("path", "")]
	var paths := []
	for item in raw_paths:
		var path := String(item)
		var path_error := _validate_res_path(path)
		if path_error != "":
			return _fail(path_error, -32602)
		paths.append(path)
	if paths.is_empty():
		return _fail("path or paths is required", -32602)
	var requested := false
	var force := bool(params.get("force", false))
	var force_reimport_paths := []
	var scan_required := false
	var source_files := []
	var import_files := []
	for path in paths:
		source_files.append(_file_summary(path))
		import_files.append(_file_summary("%s.import" % path))
		requested = _scan_editor_filesystem(path) or requested
		if force:
			if FileAccess.file_exists("%s.import" % path):
				force_reimport_paths.append(path)
			else:
				scan_required = true
	if editor_interface != null:
		var filesystem = editor_interface.get_resource_filesystem()
		if filesystem != null:
			if force and not force_reimport_paths.is_empty() and filesystem.has_method("reimport_files"):
				filesystem.call("reimport_files", force_reimport_paths)
				requested = true
			if (scan_required or not requested) and filesystem.has_method("scan"):
				filesystem.call("scan")
				requested = true
	_record_event("resource.reimport", {
		"paths": paths,
		"requested": requested,
		"force": force,
		"force_reimport_count": force_reimport_paths.size(),
	})
	return _ok({
		"paths": paths,
		"requested": requested,
		"force": force,
		"force_reimport_paths": force_reimport_paths,
		"force_reimport_count": force_reimport_paths.size(),
		"scan_required": scan_required,
		"source_files": source_files,
		"import_files": import_files,
	})


func _rpc_project_get_setting(params: Dictionary) -> Dictionary:
	var name := String(params.get("name", ""))
	if name == "":
		return _fail("name is required", -32602)
	return _ok({"name": name, "value": _encode_value(ProjectSettings.get_setting(name))})


func _rpc_project_set_setting(params: Dictionary) -> Dictionary:
	var name := String(params.get("name", ""))
	if name == "":
		return _fail("name is required", -32602)
	ProjectSettings.set_setting(name, _decode_value(params.get("value", null)))
	var save_error := _save_project_settings_if_requested(params)
	if save_error != OK:
		return _fail("Failed to save project settings: %s" % save_error)
	_record_event("project.set_setting", {
		"name": name,
		"value": params.get("value", null),
		"save": bool(params.get("save", false)),
		"saved": bool(params.get("save", false)),
	})
	return _ok({"name": name, "saved": bool(params.get("save", false))})


func _rpc_project_summary(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", "res://"))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var max_results := max(1, int(params.get("max_results", 50)))
	var include_input_events := bool(params.get("include_input_events", false))
	var include_imports := bool(params.get("include_imports", true))
	var main_scene := _rpc_payload_value(_rpc_project_main_scene(), {})
	var autoloads := _rpc_payload_value(_rpc_project_autoloads(), {"autoloads": [], "count": 0})
	var export_presets := _rpc_payload_value(_rpc_project_export_presets(), {"presets": [], "count": 0})
	var input_actions := _rpc_payload_value(_rpc_input_actions({
		"include_events": include_input_events,
		"include_ui": bool(params.get("include_ui_actions", true)),
	}), {"actions": [], "count": 0})
	var scene_files := _rpc_payload_value(_rpc_scene_files({
		"path": path,
		"include_dependencies": true,
		"include_nodes": false,
		"max_results": max_results,
	}), {"scenes": [], "count": 0, "total_matches": 0})
	var script_classes := _rpc_payload_value(_rpc_script_classes({
		"path": path,
		"include_anonymous": true,
		"max_results": max_results,
	}), {"classes": [], "count": 0, "total_matches": 0})
	var resource_files := _rpc_payload_value(_rpc_resource_files({
		"path": path,
		"include_dependencies": true,
		"include_properties": false,
		"max_results": max_results,
	}), {"resources": [], "count": 0, "total_matches": 0})
	var import_assets := {"imports": [], "count": 0, "total_matches": 0}
	if include_imports:
		import_assets = _rpc_payload_value(_rpc_resource_imports({
			"path": path,
			"include_missing_metadata": true,
			"max_results": max_results,
		}), import_assets)
	var diagnostics := []
	if String(main_scene.get("path", "")) == "":
		diagnostics.append({
			"kind": "MAIN_SCENE_NOT_CONFIGURED",
			"severity": "warning",
			"message": "application/run/main_scene is not configured",
		})
	elif not bool(main_scene.get("exists", false)):
		diagnostics.append({
			"kind": "MAIN_SCENE_NOT_LOADABLE",
			"severity": "error",
			"path": String(main_scene.get("path", "")),
			"message": "Configured main scene is not loadable",
		})
	for scene in scene_files.get("scenes", []):
		if typeof(scene) == TYPE_DICTIONARY and int(scene.get("missing_count", 0)) > 0:
			diagnostics.append({
				"kind": "SCENE_MISSING_DEPENDENCIES",
				"severity": "error",
				"path": String(scene.get("path", "")),
				"missing_count": int(scene.get("missing_count", 0)),
				"message": "Scene has missing dependencies",
			})
	for resource in resource_files.get("resources", []):
		if typeof(resource) == TYPE_DICTIONARY and int(resource.get("missing_count", 0)) > 0:
			diagnostics.append({
				"kind": "RESOURCE_MISSING_DEPENDENCIES",
				"severity": "error",
				"path": String(resource.get("path", "")),
				"missing_count": int(resource.get("missing_count", 0)),
				"message": "Resource has missing dependencies",
			})
	for imported in import_assets.get("imports", []):
		if typeof(imported) != TYPE_DICTIONARY:
			continue
		if int(imported.get("error_count", 0)) > 0:
			diagnostics.append({
				"kind": "IMPORT_ERRORS",
				"severity": "error",
				"path": String(imported.get("path", "")),
				"error_count": int(imported.get("error_count", 0)),
				"message": "Imported asset has import diagnostics",
			})
	var error_count := 0
	var warning_count := 0
	for diagnostic in diagnostics:
		if typeof(diagnostic) != TYPE_DICTIONARY:
			continue
		if String(diagnostic.get("severity", "")) == "error":
			error_count += 1
		elif String(diagnostic.get("severity", "")) == "warning":
			warning_count += 1
	var counts := {
		"scenes": int(scene_files.get("total_matches", scene_files.get("count", 0))),
		"scripts": int(script_classes.get("total_matches", script_classes.get("count", 0))),
		"resources": int(resource_files.get("total_matches", resource_files.get("count", 0))),
		"imports": int(import_assets.get("total_matches", import_assets.get("count", 0))),
		"autoloads": int(autoloads.get("count", 0)),
		"export_presets": int(export_presets.get("count", 0)),
		"input_actions": int(input_actions.get("count", 0)),
		"diagnostics": diagnostics.size(),
		"errors": error_count,
		"warnings": warning_count,
	}
	var summary := {
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"max_results": max_results,
		"main_scene": main_scene,
		"autoloads": autoloads,
		"export_presets": export_presets,
		"input_actions": input_actions,
		"scene_files": scene_files,
		"script_classes": script_classes,
		"resource_files": resource_files,
		"resource_imports": import_assets,
		"counts": counts,
		"diagnostics": diagnostics,
		"diagnostic_count": diagnostics.size(),
		"error_count": error_count,
		"warning_count": warning_count,
		"ok": error_count == 0,
	}
	_record_event("project.summary", {
		"path": path,
		"max_results": max_results,
		"ok": bool(summary.get("ok", false)),
		"diagnostic_count": diagnostics.size(),
	})
	return _ok(summary)


func _rpc_project_doctor(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", "res://"))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var max_results := max(1, int(params.get("max_results", 50)))
	var protocol := _rpc_payload_value(_rpc_protocol_describe({
		"include_methods": bool(params.get("include_protocol_methods", false)),
		"include_domains": true,
		"include_features": true,
	}), {})
	var engine := _engine_info()
	var project := _rpc_payload_value(_rpc_project_summary({
		"path": path,
		"max_results": max_results,
		"include_input_events": bool(params.get("include_input_events", false)),
		"include_ui_actions": bool(params.get("include_ui_actions", true)),
		"include_imports": bool(params.get("include_imports", true)),
	}), {})
	var editor_status := {}
	if Engine.is_editor_hint():
		editor_status = _rpc_payload_value(_rpc_editor_status(), {})
	var checks := []
	_project_doctor_add_check(
		checks,
		"protocol_surface",
		"pass" if int(protocol.get("method_count", 0)) >= 100 else "warn",
		"Protocol exposes %s RPC methods across %s domains" % [
			int(protocol.get("method_count", 0)),
			int(protocol.get("domain_count", 0)),
		],
		{"method_count": int(protocol.get("method_count", 0)), "domain_count": int(protocol.get("domain_count", 0))}
	)
	var godot_version = engine.get("godot", {})
	var godot_major := int(godot_version.get("major", 0)) if typeof(godot_version) == TYPE_DICTIONARY else 0
	_project_doctor_add_check(
		checks,
		"godot_version",
		"pass" if godot_major >= 4 else "fail",
		"Godot major version is %s" % godot_major,
		{"godot": godot_version}
	)
	_project_doctor_add_check(
		checks,
		"project_summary",
		"pass" if bool(project.get("ok", false)) else "fail",
		"Project summary has %s errors and %s warnings" % [
			int(project.get("error_count", 0)),
			int(project.get("warning_count", 0)),
		],
		{"error_count": int(project.get("error_count", 0)), "warning_count": int(project.get("warning_count", 0))}
	)
	var main_scene := project.get("main_scene", {})
	var main_scene_path := String(main_scene.get("path", "")) if typeof(main_scene) == TYPE_DICTIONARY else ""
	var main_scene_exists := bool(main_scene.get("exists", false)) if typeof(main_scene) == TYPE_DICTIONARY else false
	var main_scene_status := "pass" if main_scene_path != "" and main_scene_exists else ("warn" if main_scene_path == "" else "fail")
	_project_doctor_add_check(
		checks,
		"main_scene",
		main_scene_status,
		"Main scene is %s" % ("configured and loadable" if main_scene_status == "pass" else ("not configured" if main_scene_path == "" else "not loadable")),
		{"path": main_scene_path, "exists": main_scene_exists}
	)
	var counts := project.get("counts", {})
	var scene_count := int(counts.get("scenes", 0)) if typeof(counts) == TYPE_DICTIONARY else 0
	var script_count := int(counts.get("scripts", 0)) if typeof(counts) == TYPE_DICTIONARY else 0
	var resource_count := int(counts.get("resources", 0)) if typeof(counts) == TYPE_DICTIONARY else 0
	_project_doctor_add_check(
		checks,
		"project_content",
		"pass" if scene_count > 0 or script_count > 0 or resource_count > 0 else "warn",
		"Project has %s scenes, %s script classes, and %s resources" % [scene_count, script_count, resource_count],
		{"scenes": scene_count, "scripts": script_count, "resources": resource_count}
	)
	var import_count := int(counts.get("imports", 0)) if typeof(counts) == TYPE_DICTIONARY else 0
	var import_status := "pass"
	if int(project.get("error_count", 0)) > 0:
		import_status = "fail"
	elif import_count == 0:
		import_status = "warn"
	_project_doctor_add_check(
		checks,
		"imports",
		import_status,
		"Project import scan found %s importable assets" % import_count,
		{"imports": import_count}
	)
	if Engine.is_editor_hint():
		_project_doctor_add_check(
			checks,
			"editor_session",
			"pass" if bool(editor_status.get("available", false)) else "warn",
			"Editor session is %s" % ("available" if bool(editor_status.get("available", false)) else "not fully available"),
			{"status": editor_status}
		)
	var fail_count := 0
	var warn_count := 0
	for check in checks:
		if typeof(check) != TYPE_DICTIONARY:
			continue
		var status := String(check.get("status", ""))
		if status == "fail":
			fail_count += 1
		elif status == "warn":
			warn_count += 1
	var diagnostics := []
	for diagnostic in project.get("diagnostics", []):
		if typeof(diagnostic) == TYPE_DICTIONARY:
			diagnostics.append(diagnostic)
	var next_steps := _project_doctor_next_steps(checks, diagnostics)
	var result := {
		"path": path,
		"global_path": ProjectSettings.globalize_path(path),
		"ok": fail_count == 0,
		"ready": fail_count == 0,
		"status": "ready" if fail_count == 0 else "blocked",
		"check_count": checks.size(),
		"fail_count": fail_count,
		"warning_count": warn_count,
		"checks": checks,
		"diagnostics": diagnostics,
		"diagnostic_count": diagnostics.size(),
		"next_steps": next_steps,
		"protocol": protocol,
		"engine": engine,
		"editor_status": editor_status,
		"project_summary": project,
	}
	_record_event("project.doctor", {
		"path": path,
		"ok": bool(result.get("ok", false)),
		"fail_count": fail_count,
		"warning_count": warn_count,
		"diagnostic_count": diagnostics.size(),
	})
	return _ok(result)


func _project_doctor_add_check(checks: Array, name: String, status: String, message: String, evidence: Dictionary) -> void:
	checks.append({
		"name": name,
		"status": status,
		"ok": status != "fail",
		"message": message,
		"evidence": evidence,
	})


func _project_doctor_next_steps(checks: Array, diagnostics: Array) -> Array:
	var steps := []
	for diagnostic in diagnostics:
		if typeof(diagnostic) != TYPE_DICTIONARY:
			continue
		match String(diagnostic.get("kind", "")):
			"MAIN_SCENE_NOT_CONFIGURED":
				steps.append("Set a main scene with project_set_main_scene(...) before runtime validation.")
			"MAIN_SCENE_NOT_LOADABLE":
				steps.append("Fix or recreate the configured main scene before running gameplay probes.")
			"SCENE_MISSING_DEPENDENCIES":
				steps.append("Inspect scene dependencies with resource_dependencies(...) and repair missing references.")
			"RESOURCE_MISSING_DEPENDENCIES":
				steps.append("Inspect resource dependencies with resource_dependencies(...) and repair missing references.")
			"IMPORT_ERRORS":
				steps.append("Run resource_import_metadata(...) or resource_reimport(...) for assets with import diagnostics.")
	for check in checks:
		if typeof(check) != TYPE_DICTIONARY:
			continue
		if String(check.get("status", "")) != "warn":
			continue
		match String(check.get("name", "")):
			"main_scene":
				steps.append("Configure a main scene when runtime launch coverage is required.")
			"imports":
				steps.append("Add or reimport external assets if the project should exercise import/export workflows.")
			"project_content":
				steps.append("Create or inspect scenes/scripts/resources before attempting authoring workflows.")
	if steps.is_empty():
		steps.append("Project is ready for editor authoring, runtime probing, trace recording, and validation.")
	return _unique_strings(steps)


func _unique_strings(values: Array) -> Array:
	var seen := {}
	var result := []
	for value in values:
		var text := String(value)
		if text == "" or seen.has(text):
			continue
		seen[text] = true
		result.append(text)
	return result


func _rpc_payload_value(result: Dictionary, fallback: Dictionary) -> Dictionary:
	if bool(result.get("ok", false)) and typeof(result.get("value", null)) == TYPE_DICTIONARY:
		return result.get("value", {})
	return fallback


func _rpc_project_export_presets() -> Dictionary:
	var config_result := _load_export_presets_config()
	if not bool(config_result.get("ok", false)):
		return _fail(String(config_result.get("error", "")))
	var config: ConfigFile = config_result["config"]
	var presets := _export_preset_summaries(config)
	return _ok({
		"path": "res://export_presets.cfg",
		"global_path": ProjectSettings.globalize_path("res://export_presets.cfg"),
		"exists": FileAccess.file_exists("res://export_presets.cfg"),
		"presets": presets,
		"count": presets.size(),
	})


func _rpc_project_set_export_preset(params: Dictionary) -> Dictionary:
	var name := String(params.get("name", ""))
	if name == "":
		return _fail("name is required", -32602)
	var config_result := _load_export_presets_config()
	if not bool(config_result.get("ok", false)):
		return _fail(String(config_result.get("error", "")))
	var config: ConfigFile = config_result["config"]
	var index := int(params.get("index", -1))
	var previous: Variant = null
	if index < 0:
		index = _find_export_preset_index(config, name)
	if index >= 0 and config.has_section("preset.%s" % index):
		previous = _export_preset_summary(config, index)
		if not bool(params.get("overwrite", true)):
			return _fail("Export preset already exists: %s" % name, -32602)
	if index < 0:
		index = _next_export_preset_index(config)
	var platform := String(params.get("platform", ""))
	if platform == "":
		if previous != null and typeof(previous) == TYPE_DICTIONARY:
			platform = String(previous.get("platform", ""))
		if platform == "":
			return _fail("platform is required", -32602)
	var section := "preset.%s" % index
	var options_section := "%s.options" % section
	var fields := {
		"name": name,
		"platform": platform,
		"runnable": bool(params.get("runnable", true)),
		"dedicated_server": bool(params.get("dedicated_server", false)),
		"custom_features": String(params.get("custom_features", "")),
		"export_filter": String(params.get("export_filter", "all_resources")),
		"include_filter": String(params.get("include_filter", "")),
		"exclude_filter": String(params.get("exclude_filter", "")),
		"export_path": String(params.get("export_path", "")),
		"encryption_include_filters": String(params.get("encryption_include_filters", "")),
		"encryption_exclude_filters": String(params.get("encryption_exclude_filters", "")),
		"encrypt_pck": bool(params.get("encrypt_pck", false)),
		"encrypt_directory": bool(params.get("encrypt_directory", false)),
		"script_export_mode": int(params.get("script_export_mode", 2)),
	}
	var extra_fields = params.get("fields", {})
	if typeof(extra_fields) == TYPE_DICTIONARY:
		for key in extra_fields.keys():
			fields[String(key)] = _decode_value(extra_fields[key])
	for key in fields.keys():
		config.set_value(section, String(key), fields[key])
	var options = params.get("options", {})
	if typeof(options) != TYPE_DICTIONARY:
		return _fail("options must be an object", -32602)
	for key in options.keys():
		config.set_value(options_section, String(key), _decode_value(options[key]))
	var save_error := config.save("res://export_presets.cfg")
	if save_error != OK:
		return _fail("Failed to save export_presets.cfg: %s" % save_error)
	_scan_editor_filesystem("res://export_presets.cfg")
	var summary := _export_preset_summary(config, index)
	summary["previous"] = previous
	summary["saved"] = true
	_record_event("project.set_export_preset", {
		"index": index,
		"name": name,
		"platform": platform,
		"export_path": String(params.get("export_path", "")),
		"runnable": bool(params.get("runnable", true)),
		"dedicated_server": bool(params.get("dedicated_server", false)),
		"custom_features": String(params.get("custom_features", "")),
		"export_filter": String(params.get("export_filter", "all_resources")),
		"include_filter": String(params.get("include_filter", "")),
		"exclude_filter": String(params.get("exclude_filter", "")),
		"encryption_include_filters": String(params.get("encryption_include_filters", "")),
		"encryption_exclude_filters": String(params.get("encryption_exclude_filters", "")),
		"encrypt_pck": bool(params.get("encrypt_pck", false)),
		"encrypt_directory": bool(params.get("encrypt_directory", false)),
		"script_export_mode": int(params.get("script_export_mode", 2)),
		"options": params.get("options", {}),
		"fields": params.get("fields", {}),
		"overwrite": bool(params.get("overwrite", true)),
	})
	return _ok(summary)


func _rpc_project_main_scene() -> Dictionary:
	var path := String(ProjectSettings.get_setting("application/run/main_scene"))
	return _ok({
		"path": path,
		"exists": path != "" and ResourceLoader.exists(path),
	})


func _rpc_project_set_main_scene(params: Dictionary) -> Dictionary:
	var path := String(params.get("path", params.get("scene", "")))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	var extension := path.get_extension().to_lower()
	if extension != "tscn" and extension != "scn":
		return _fail("Main scene must be a .tscn or .scn resource: %s" % path, -32602)
	if bool(params.get("require_exists", true)) and not ResourceLoader.exists(path):
		return _fail("Scene resource not found: %s" % path, -32602)
	ProjectSettings.set_setting("application/run/main_scene", path)
	var save_error := _save_project_settings_if_requested(params)
	if save_error != OK:
		return _fail("Failed to save project settings: %s" % save_error)
	_record_event("project.set_main_scene", {
		"path": path,
		"save": bool(params.get("save", false)),
		"saved": bool(params.get("save", false)),
		"require_exists": bool(params.get("require_exists", true)),
	})
	return _ok({"path": path, "exists": ResourceLoader.exists(path), "saved": bool(params.get("save", false))})


func _rpc_project_autoloads() -> Dictionary:
	var entries := []
	for info in ProjectSettings.get_property_list():
		var setting_name := String(info.get("name", ""))
		if not setting_name.begins_with("autoload/"):
			continue
		var name := setting_name.trim_prefix("autoload/")
		entries.append(_project_autoload_summary(name))
	entries.sort_custom(func(a, b): return String(a.get("name", "")) < String(b.get("name", "")))
	return _ok({"autoloads": entries, "count": entries.size()})


func _rpc_project_add_autoload(params: Dictionary) -> Dictionary:
	var name := String(params.get("name", ""))
	var name_error := _validate_autoload_name(name)
	if name_error != "":
		return _fail(name_error, -32602)
	var path := String(params.get("path", ""))
	var path_error := _validate_res_path(path)
	if path_error != "":
		return _fail(path_error, -32602)
	if bool(params.get("require_exists", true)) and not ResourceLoader.exists(path):
		return _fail("Autoload resource not found: %s" % path, -32602)
	var singleton := bool(params.get("singleton", true))
	var setting_name := "autoload/%s" % name
	var value := ("%s%s" % ["*" if singleton else "", path])
	var previous: Variant = null
	if ProjectSettings.has_setting(setting_name):
		previous = _project_autoload_summary(name)
		if not bool(params.get("overwrite", true)):
			return _fail("Autoload already exists: %s" % name, -32602)
	ProjectSettings.set_setting(setting_name, value)
	ProjectSettings.set_as_basic(setting_name, true)
	var order := int(params.get("order", -1))
	if order >= 0:
		ProjectSettings.set_order(setting_name, order)
	var save_error := _save_project_settings_if_requested(params)
	if save_error != OK:
		return _fail("Failed to save project settings: %s" % save_error)
	var summary := _project_autoload_summary(name)
	summary["previous"] = previous
	summary["saved"] = bool(params.get("save", false))
	_record_event("project.add_autoload", {
		"name": name,
		"path": path,
		"singleton": singleton,
		"save": bool(params.get("save", false)),
		"saved": bool(params.get("save", false)),
		"overwrite": bool(params.get("overwrite", true)),
		"require_exists": bool(params.get("require_exists", true)),
		"order": params.get("order", null),
	})
	return _ok(summary)


func _rpc_project_remove_autoload(params: Dictionary) -> Dictionary:
	var name := String(params.get("name", ""))
	var name_error := _validate_autoload_name(name)
	if name_error != "":
		return _fail(name_error, -32602)
	var setting_name := "autoload/%s" % name
	if not ProjectSettings.has_setting(setting_name):
		return _ok({"name": name, "exists": false, "removed": false, "saved": false})
	var previous := _project_autoload_summary(name)
	ProjectSettings.clear(setting_name)
	var save_error := _save_project_settings_if_requested(params)
	if save_error != OK:
		return _fail("Failed to save project settings: %s" % save_error)
	_record_event("project.remove_autoload", {
		"name": name,
		"save": bool(params.get("save", false)),
		"saved": bool(params.get("save", false)),
	})
	return _ok({
		"name": name,
		"exists": false,
		"removed": true,
		"previous": previous,
		"saved": bool(params.get("save", false)),
	})


func _save_project_settings_if_requested(params: Dictionary) -> int:
	if not bool(params.get("save", false)):
		return OK
	return ProjectSettings.save()


func _validate_autoload_name(name: String) -> String:
	if name == "":
		return "name is required"
	if not name.is_valid_identifier():
		return "Autoload name must be a valid identifier: %s" % name
	return ""


func _project_autoload_summary(name: String) -> Dictionary:
	var setting_name := "autoload/%s" % name
	var raw := String(ProjectSettings.get_setting(setting_name))
	var singleton := raw.begins_with("*")
	var path := raw.trim_prefix("*")
	return {
		"name": name,
		"setting": setting_name,
		"path": path,
		"raw": raw,
		"singleton": singleton,
		"exists": ProjectSettings.has_setting(setting_name),
		"resource_exists": path != "" and ResourceLoader.exists(path),
	}


func _load_export_presets_config() -> Dictionary:
	var config := ConfigFile.new()
	if not FileAccess.file_exists("res://export_presets.cfg"):
		return {"ok": true, "config": config}
	var load_error := config.load("res://export_presets.cfg")
	if load_error != OK:
		return {"ok": false, "error": "Failed to load export_presets.cfg: %s" % load_error}
	return {"ok": true, "config": config}


func _export_preset_summaries(config: ConfigFile) -> Array:
	var indexes := []
	for section in config.get_sections():
		var section_name := String(section)
		if not section_name.begins_with("preset.") or section_name.ends_with(".options"):
			continue
		var index_text := section_name.trim_prefix("preset.")
		if index_text.is_valid_int():
			indexes.append(int(index_text))
	indexes.sort()
	var presets := []
	for index in indexes:
		presets.append(_export_preset_summary(config, int(index)))
	return presets


func _export_preset_summary(config: ConfigFile, index: int) -> Dictionary:
	var section := "preset.%s" % index
	var options_section := "%s.options" % section
	var options := {}
	if config.has_section(options_section):
		for key in config.get_section_keys(options_section):
			options[String(key)] = _encode_value(config.get_value(options_section, key))
	return {
		"index": index,
		"name": String(config.get_value(section, "name", "")),
		"platform": String(config.get_value(section, "platform", "")),
		"runnable": bool(config.get_value(section, "runnable", false)),
		"dedicated_server": bool(config.get_value(section, "dedicated_server", false)),
		"custom_features": String(config.get_value(section, "custom_features", "")),
		"export_filter": String(config.get_value(section, "export_filter", "")),
		"include_filter": String(config.get_value(section, "include_filter", "")),
		"exclude_filter": String(config.get_value(section, "exclude_filter", "")),
		"export_path": String(config.get_value(section, "export_path", "")),
		"encryption_include_filters": String(config.get_value(section, "encryption_include_filters", "")),
		"encryption_exclude_filters": String(config.get_value(section, "encryption_exclude_filters", "")),
		"encrypt_pck": bool(config.get_value(section, "encrypt_pck", false)),
		"encrypt_directory": bool(config.get_value(section, "encrypt_directory", false)),
		"script_export_mode": int(config.get_value(section, "script_export_mode", 2)),
		"options": options,
	}


func _find_export_preset_index(config: ConfigFile, name: String) -> int:
	for preset in _export_preset_summaries(config):
		if String(preset.get("name", "")) == name:
			return int(preset.get("index", -1))
	return -1


func _next_export_preset_index(config: ConfigFile) -> int:
	var next_index := 0
	for preset in _export_preset_summaries(config):
		next_index = max(next_index, int(preset.get("index", -1)) + 1)
	return next_index


func _validate_res_path(path: String) -> String:
	if path == "":
		return "path is required"
	if not path.begins_with("res://"):
		return "Only res:// project paths are allowed"
	var rest := path.substr(6)
	for part in rest.split("/"):
		if part == "..":
			return "Path traversal is not allowed: %s" % path
	return ""


func _editor_target_from_params(params: Dictionary) -> Object:
	if params.has("resource_path"):
		return _load_resource_target(String(params.get("resource_path", "")))
	if params.has("path"):
		var path := String(params.get("path", ""))
		if path.begins_with("res://"):
			return _load_resource_target(path)
		if path.begins_with("/"):
			return get_node_or_null(NodePath(path))
	if params.has("selector"):
		return _resolve_node(params.get("selector"), params.get("root", "edited"))
	if bool(params.get("selected", false)):
		return _first_editor_selected_node()
	return null


func _editor_target_from_params_or_selection(params: Dictionary) -> Object:
	var target := _editor_target_from_params(params)
	if target != null:
		return target
	return _first_editor_selected_node()


func _first_editor_selected_node() -> Node:
	if editor_interface == null or not editor_interface.has_method("get_selection"):
		return null
	var selection = editor_interface.call("get_selection")
	if selection == null:
		return null
	var nodes = selection.call("get_selected_nodes")
	if typeof(nodes) != TYPE_ARRAY or nodes.is_empty():
		return null
	if nodes[0] is Node:
		return nodes[0]
	return null


func _load_resource_target(path: String) -> Resource:
	var path_error := _validate_res_path(path)
	if path_error != "":
		return null
	if not ResourceLoader.exists(path):
		return null
	return ResourceLoader.load(path)


func _inspect_object(target: Object, for_property: String = "", inspector_only: bool = false) -> bool:
	if editor_interface == null or target == null:
		return false
	if DisplayServer.get_name() == "headless" and target is Script:
		return true
	if not editor_interface.has_method("inspect_object"):
		return false
	editor_interface.callv("inspect_object", [target, for_property, inspector_only])
	return true


func _set_external_script_editor(enabled: bool) -> Dictionary:
	if editor_interface == null or not editor_interface.has_method("get_editor_settings"):
		return {}
	var settings = editor_interface.call("get_editor_settings")
	if settings == null or not settings.has_method("set_setting"):
		return {}
	var changed := {}
	var keys := ["text_editor/external/use_external_editor"]
	for key in keys:
		var had_setting: bool = settings.has_method("has_setting") and bool(settings.call("has_setting", key))
		var previous = null
		if had_setting and settings.has_method("get_setting"):
			previous = settings.call("get_setting", key)
		settings.call("set_setting", key, enabled)
		if had_setting:
			changed[key] = previous
		elif settings.has_method("get_setting"):
			changed[key] = settings.call("get_setting", key)
	return changed


func _restore_external_script_editor(changed: Dictionary) -> void:
	if changed.is_empty() or editor_interface == null or not editor_interface.has_method("get_editor_settings"):
		return
	var settings = editor_interface.call("get_editor_settings")
	if settings == null or not settings.has_method("set_setting"):
		return
	for key in changed.keys():
		settings.call("set_setting", String(key), changed[key])


func _object_summary(target: Object) -> Dictionary:
	if target == null:
		return {}
	if target is Node:
		var node_summary := _node_summary(target)
		node_summary["$type"] = "Node"
		return node_summary
	if target is Resource:
		var resource_summary := _resource_summary(target)
		resource_summary["$type"] = "Resource"
		return resource_summary
	return {
		"$type": "Object",
		"class": target.get_class(),
		"id": target.get_instance_id(),
	}


func _inspector_property_summaries(
	target: Object,
	include_values: bool,
	requested: Variant,
	name_contains: String,
	include_internal: bool
) -> Array:
	var requested_names := {}
	if typeof(requested) == TYPE_ARRAY:
		for item in requested:
			requested_names[String(item)] = true
	elif typeof(requested) == TYPE_STRING and String(requested) != "":
		requested_names[String(requested)] = true
	var properties := []
	for info in target.get_property_list():
		var name := String(info.get("name", ""))
		if name == "":
			continue
		if not requested_names.is_empty() and not requested_names.has(name):
			continue
		if name_contains != "" and name.find(name_contains) == -1:
			continue
		if not include_internal and not _property_is_editor_visible(info):
			continue
		properties.append(_inspector_property_summary_from_info(target, info, include_values))
	return properties


func _inspector_property_summary(target: Object, property: String, include_value: bool) -> Dictionary:
	for info in target.get_property_list():
		if String(info.get("name", "")) == property:
			return _inspector_property_summary_from_info(target, info, include_value)
	return {
		"name": property,
		"value": _encode_value(target.get(property)) if include_value else null,
		"exists": false,
	}


func _inspector_property_summary_from_info(target: Object, info: Dictionary, include_value: bool) -> Dictionary:
	var name := String(info.get("name", ""))
	var type_id := int(info.get("type", TYPE_NIL))
	var summary := {
		"name": name,
		"type": type_id,
		"type_name": _variant_type_name(type_id),
		"hint": int(info.get("hint", 0)),
		"hint_string": String(info.get("hint_string", "")),
		"usage": int(info.get("usage", 0)),
		"editor_visible": _property_is_editor_visible(info),
		"exists": true,
	}
	if include_value:
		summary["value"] = _encode_value(target.get(name))
	return summary


func _property_is_editor_visible(info: Dictionary) -> bool:
	return (int(info.get("usage", 0)) & PROPERTY_USAGE_EDITOR) != 0


func _variant_type_name(type_id: int) -> String:
	match type_id:
		TYPE_NIL:
			return "Nil"
		TYPE_BOOL:
			return "bool"
		TYPE_INT:
			return "int"
		TYPE_FLOAT:
			return "float"
		TYPE_STRING:
			return "String"
		TYPE_VECTOR2:
			return "Vector2"
		TYPE_VECTOR2I:
			return "Vector2i"
		TYPE_RECT2:
			return "Rect2"
		TYPE_VECTOR3:
			return "Vector3"
		TYPE_VECTOR3I:
			return "Vector3i"
		TYPE_COLOR:
			return "Color"
		TYPE_STRING_NAME:
			return "StringName"
		TYPE_NODE_PATH:
			return "NodePath"
		TYPE_OBJECT:
			return "Object"
		TYPE_ARRAY:
			return "Array"
		TYPE_DICTIONARY:
			return "Dictionary"
	return str(type_id)


func _ensure_res_parent_dir(path: String) -> int:
	var base_dir := path.get_base_dir()
	if base_dir == "" or base_dir == "res://":
		return OK
	return DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(base_dir))


func _remove_res_path(path: String) -> int:
	var parent := path.get_base_dir()
	if parent == "":
		parent = "res://"
	var dir := DirAccess.open(parent)
	if dir == null:
		return ERR_CANT_OPEN
	return dir.remove(path.get_file())


func _scan_editor_filesystem(path: String = "") -> bool:
	if editor_interface == null:
		return false
	var filesystem = editor_interface.get_resource_filesystem()
	if filesystem == null:
		return false
	if path != "" and filesystem.has_method("update_file") and FileAccess.file_exists(path):
		filesystem.call("update_file", path)
		return true
	if filesystem.has_method("scan"):
		filesystem.call("scan")
		return true
	return false


func _file_summary(path: String) -> Dictionary:
	var exists := FileAccess.file_exists(path)
	var bytes := -1
	var modified_time := 0
	if exists:
		var file := FileAccess.open(path, FileAccess.READ)
		if file != null:
			bytes = file.get_length()
			file.close()
		modified_time = int(FileAccess.get_modified_time(path))
	return {
		"path": path,
		"name": path.get_file(),
		"global_path": ProjectSettings.globalize_path(path),
		"exists": exists,
		"bytes": bytes,
		"modified_time": modified_time,
	}


func _set_import_metadata_diagnostics(summary: Dictionary, diagnostics: Array) -> void:
	var error_count := 0
	var warning_count := 0
	for diagnostic in diagnostics:
		if typeof(diagnostic) != TYPE_DICTIONARY:
			continue
		var severity := String(diagnostic.get("severity", ""))
		if severity == "error":
			error_count += 1
		elif severity == "warning":
			warning_count += 1
	summary["diagnostics"] = diagnostics
	summary["diagnostic_count"] = diagnostics.size()
	summary["error_count"] = error_count
	summary["warning_count"] = warning_count
	summary["ok"] = error_count == 0 and bool(summary.get("exists", false)) and bool(summary.get("source_exists", false)) and bool(summary.get("resource_exists", false)) and bool(summary.get("generated_files_ready", false))


func _filesystem_entry(path: String) -> Dictionary:
	var global_path := ProjectSettings.globalize_path(path)
	var is_file := FileAccess.file_exists(path)
	var is_dir := DirAccess.dir_exists_absolute(global_path)
	var resource_type := "" if not is_file else _resource_type_for_path(path)
	var bytes := -1
	if is_file:
		bytes = int(_file_summary(path).get("bytes", -1))
	return {
		"path": path,
		"name": "res://" if path == "res://" else path.get_file(),
		"global_path": global_path,
		"exists": is_file or is_dir,
		"kind": "file" if is_file else ("directory" if is_dir else "missing"),
		"type": "file" if is_file else ("directory" if is_dir else "missing"),
		"is_file": is_file,
		"is_directory": is_dir,
		"is_resource": is_file and ResourceLoader.exists(path),
		"resource_type": resource_type,
		"extension": path.get_extension(),
		"bytes": bytes,
		"selected": (is_file or is_dir) and path == _editor_filesystem_selected_path,
	}


func _scene_file_summary(
	path: String,
	include_dependencies: bool,
	include_nodes: bool,
	include_properties: bool,
	include_resources: bool,
	include_connections: bool
) -> Dictionary:
	var entry := _filesystem_entry(path)
	var extension := path.get_extension().to_lower()
	var resource_type := String(entry.get("resource_type", ""))
	var summary := {
		"path": path,
		"name": path.get_file(),
		"global_path": ProjectSettings.globalize_path(path),
		"exists": bool(entry.get("exists", false)),
		"file_exists": bool(entry.get("is_file", false)),
		"resource_exists": bool(entry.get("is_resource", false)),
		"resource_type": resource_type,
		"extension": extension,
		"is_scene": extension in ["tscn", "scn"] and (resource_type == "" or resource_type == "PackedScene"),
		"root_name": "",
		"root_class": "",
		"node_count": 0,
		"ok": bool(entry.get("is_file", false)),
	}
	if extension == "tscn" and bool(entry.get("is_file", false)):
		var source := FileAccess.get_file_as_string(path)
		var open_error := FileAccess.get_open_error()
		if open_error == OK:
			var text_summary := _text_scene_file_summary(
				source,
				include_nodes,
				include_properties,
				include_resources,
				include_connections
			)
			for key in text_summary.keys():
				summary[key] = text_summary[key]
		else:
			summary["read_error"] = int(open_error)
	if include_dependencies:
		var dependencies := _resource_dependencies_payload(path, false)
		summary["dependencies"] = dependencies.get("dependencies", [])
		summary["dependency_count"] = int(dependencies.get("dependency_count", 0))
		summary["missing"] = dependencies.get("missing", [])
		summary["missing_count"] = int(dependencies.get("missing_count", 0))
		summary["ok"] = bool(summary.get("ok", false)) and bool(dependencies.get("ok", false))
	return summary


func _text_scene_file_summary(
	source: String,
	include_nodes: bool,
	include_properties: bool,
	include_resources: bool,
	include_connections: bool
) -> Dictionary:
	var nodes := []
	var root := {}
	var ext_resources := []
	var sub_resources := []
	var connections := []
	var current := {}
	var current_section := ""
	var lines := source.split("\n")
	for index in range(lines.size()):
		var line := String(lines[index]).strip_edges()
		if line == "" or line.begins_with(";"):
			continue
		if line.begins_with("["):
			current = {}
			current_section = ""
			if line.begins_with("[ext_resource "):
				var attrs := _scene_tag_attributes(line)
				ext_resources.append(_scene_ext_resource_summary(attrs, index + 1))
			elif line.begins_with("[sub_resource "):
				var attrs := _scene_tag_attributes(line)
				var sub_resource := _scene_sub_resource_summary(attrs, index + 1)
				sub_resources.append(sub_resource)
				current = sub_resource
				current_section = "sub_resource"
			elif line.begins_with("[node "):
				var attrs := _scene_tag_attributes(line)
				var node := _scene_node_summary(attrs, index + 1, nodes.size())
				if root.is_empty() and String(node.get("parent", "")) == "":
					root = node
				nodes.append(node)
				current = node
				current_section = "node"
			elif line.begins_with("[connection "):
				if include_connections:
					var attrs := _scene_tag_attributes(line)
					connections.append(_scene_connection_summary(attrs, index + 1))
			continue
		if include_properties and current_section in ["node", "sub_resource"] and line.find("=") != -1:
			var equals := line.find("=")
			var property_name := line.substr(0, equals).strip_edges()
			var raw_value := line.substr(equals + 1).strip_edges()
			var properties: Dictionary = current.get("properties", {})
			properties[property_name] = _scene_property_value(raw_value)
			current["properties"] = properties
			current["property_count"] = properties.size()
	if root.is_empty() and not nodes.is_empty():
		root = nodes[0]
	var ext_by_id := {}
	for resource in ext_resources:
		var resource_id := String(resource.get("id", ""))
		if resource_id != "":
			ext_by_id[resource_id] = resource
	for node in nodes:
		_scene_finalize_node_summary(node, root, ext_by_id, include_properties)
	var summary := {
		"root_name": String(root.get("name", "")),
		"root_class": String(root.get("class", "")),
		"node_count": nodes.size(),
	}
	if include_nodes:
		summary["nodes"] = nodes
	if include_resources:
		summary["ext_resources"] = ext_resources
		summary["ext_resource_count"] = ext_resources.size()
		summary["sub_resources"] = sub_resources if include_properties else _scene_public_sub_resources(sub_resources)
		summary["sub_resource_count"] = sub_resources.size()
	if include_connections:
		summary["connections"] = connections
		summary["connection_count"] = connections.size()
	return summary


func _scene_tag_attributes(line: String) -> Dictionary:
	var attrs := {}
	var body := line.strip_edges().trim_prefix("[").trim_suffix("]")
	var cursor := body.find(" ")
	if cursor == -1:
		return attrs
	cursor += 1
	while cursor < body.length():
		while cursor < body.length() and body.substr(cursor, 1) == " ":
			cursor += 1
		if cursor >= body.length():
			break
		var equals := body.find("=", cursor)
		if equals == -1:
			break
		var key := body.substr(cursor, equals - cursor).strip_edges()
		cursor = equals + 1
		if cursor >= body.length():
			attrs[key] = ""
			break
		var value := ""
		var marker := body.substr(cursor, 1)
		if marker == "\"" or marker == "'":
			var end := body.find(marker, cursor + 1)
			if end == -1:
				value = body.substr(cursor + 1)
				cursor = body.length()
			else:
				value = body.substr(cursor + 1, end - cursor - 1)
				cursor = end + 1
		else:
			var next_space := body.find(" ", cursor)
			if next_space == -1:
				value = body.substr(cursor)
				cursor = body.length()
			else:
				value = body.substr(cursor, next_space - cursor)
				cursor = next_space + 1
		if key != "":
			attrs[key] = value
	return attrs


func _scene_ext_resource_summary(attrs: Dictionary, line_number: int) -> Dictionary:
	var path := String(attrs.get("path", ""))
	var exists := false
	var global_path := ""
	if path.begins_with("res://"):
		exists = FileAccess.file_exists(path)
		global_path = ProjectSettings.globalize_path(path)
	return {
		"id": String(attrs.get("id", "")),
		"type": String(attrs.get("type", "")),
		"path": path,
		"uid": String(attrs.get("uid", "")),
		"line": line_number,
		"global_path": global_path,
		"exists": exists,
	}


func _scene_sub_resource_summary(attrs: Dictionary, line_number: int) -> Dictionary:
	return {
		"id": String(attrs.get("id", "")),
		"type": String(attrs.get("type", "")),
		"line": line_number,
		"properties": {},
		"property_count": 0,
	}


func _scene_node_summary(attrs: Dictionary, line_number: int, index: int) -> Dictionary:
	var parent := String(attrs.get("parent", ""))
	return {
		"name": String(attrs.get("name", "")),
		"class": String(attrs.get("type", "")),
		"type": String(attrs.get("type", "")),
		"parent": parent,
		"parent_path": "",
		"path": "",
		"scene_path": "",
		"instance": _scene_property_value(String(attrs.get("instance", ""))) if attrs.has("instance") else null,
		"instance_path": "",
		"groups": _scene_string_array(String(attrs.get("groups", ""))),
		"line": line_number,
		"index": index,
		"properties": {},
		"property_count": 0,
	}


func _scene_connection_summary(attrs: Dictionary, line_number: int) -> Dictionary:
	return {
		"signal": String(attrs.get("signal", "")),
		"from": String(attrs.get("from", "")),
		"to": String(attrs.get("to", "")),
		"method": String(attrs.get("method", "")),
		"flags": _scene_property_value(String(attrs.get("flags", ""))) if attrs.has("flags") else null,
		"line": line_number,
	}


func _scene_finalize_node_summary(node: Dictionary, root: Dictionary, ext_by_id: Dictionary, include_properties: bool) -> void:
	var root_name := String(root.get("name", ""))
	var parent := String(node.get("parent", ""))
	var name := String(node.get("name", ""))
	var scene_path := _scene_node_path(root_name, parent, name)
	var parent_path := _scene_parent_path(root_name, parent)
	node["scene_path"] = scene_path
	node["path"] = "/%s" % scene_path if scene_path != "" else ""
	node["parent_path"] = "/%s" % parent_path if parent_path != "" else ""
	var instance = node.get("instance", null)
	var instance_resource := _scene_reference_resource(instance, ext_by_id)
	if not instance_resource.is_empty():
		node["instance_path"] = String(instance_resource.get("path", ""))
	if include_properties:
		var properties: Dictionary = node.get("properties", {})
		var script_resource := _scene_reference_resource(properties.get("script", null), ext_by_id)
		if not script_resource.is_empty():
			node["script"] = String(script_resource.get("path", ""))
	else:
		node.erase("properties")


func _scene_reference_resource(value: Variant, ext_by_id: Dictionary) -> Dictionary:
	if typeof(value) != TYPE_DICTIONARY:
		return {}
	var dictionary: Dictionary = value
	if String(dictionary.get("$type", "")) != "ExtResource":
		return {}
	return ext_by_id.get(String(dictionary.get("id", "")), {})


func _scene_public_sub_resources(sub_resources: Array) -> Array:
	var public := []
	for resource in sub_resources:
		if typeof(resource) != TYPE_DICTIONARY:
			continue
		var dictionary: Dictionary = resource
		public.append({
			"id": String(dictionary.get("id", "")),
			"type": String(dictionary.get("type", "")),
			"line": int(dictionary.get("line", 0)),
			"property_count": int(dictionary.get("property_count", 0)),
		})
	return public


func _scene_node_path(root_name: String, parent: String, name: String) -> String:
	if parent == "":
		return name
	if root_name == "":
		return name
	if parent == ".":
		return "%s/%s" % [root_name, name]
	return "%s/%s/%s" % [root_name, parent.strip_edges().trim_prefix("/").trim_suffix("/"), name]


func _scene_parent_path(root_name: String, parent: String) -> String:
	if parent == "":
		return ""
	if root_name == "":
		return parent
	if parent == ".":
		return root_name
	return "%s/%s" % [root_name, parent.strip_edges().trim_prefix("/").trim_suffix("/")]


func _scene_property_value(raw_value: String) -> Variant:
	var value := raw_value.strip_edges()
	if value == "":
		return ""
	if value.begins_with("\"") and value.ends_with("\"") and value.length() >= 2:
		return value.substr(1, value.length() - 2)
	if value == "true":
		return true
	if value == "false":
		return false
	if value.is_valid_int():
		return int(value)
	if value.is_valid_float():
		return float(value)
	if value.begins_with("ExtResource("):
		return {"$type": "ExtResource", "id": _scene_reference_id(value), "raw": value}
	if value.begins_with("SubResource("):
		return {"$type": "SubResource", "id": _scene_reference_id(value), "raw": value}
	return {"raw": value}


func _scene_reference_id(value: String) -> String:
	var start := value.find("\"")
	if start != -1:
		var end := value.find("\"", start + 1)
		if end != -1:
			return value.substr(start + 1, end - start - 1)
	start = value.find("(")
	var end_paren := value.find(")", start + 1)
	if start != -1 and end_paren != -1:
		return value.substr(start + 1, end_paren - start - 1).strip_edges()
	return ""


func _scene_string_array(value: String) -> Array:
	var items := []
	var text := value.strip_edges()
	if text == "":
		return items
	var cursor := 0
	while cursor < text.length():
		var start := text.find("\"", cursor)
		if start == -1:
			break
		var end := text.find("\"", start + 1)
		if end == -1:
			break
		items.append(text.substr(start + 1, end - start - 1))
		cursor = end + 1
	return items


func _resource_type_for_path(path: String) -> String:
	if path.begins_with("res://") and not FileAccess.file_exists(path):
		return ""
	if path.begins_with("res://"):
		var file := FileAccess.open(path, FileAccess.READ)
		if file == null:
			return ""
		file.close()
	var extension := path.get_extension().to_lower()
	match extension:
		"tscn", "scn":
			return "PackedScene"
		"gd":
			return "GDScript"
		"gdshader", "shader":
			return "Shader"
		"tres", "material", "theme":
			var source := FileAccess.get_file_as_string(path)
			if FileAccess.get_open_error() == OK:
				var text_summary := _text_resource_file_summary(source, false, false)
				var root_class := String(text_summary.get("root_class", ""))
				if root_class != "":
					return root_class
			return "Resource"
	if not ResourceLoader.exists(path):
		return ""
	var resource := ResourceLoader.load(path)
	if resource == null:
		return ""
	return resource.get_class()


func _resource_dependency_summary(raw_dependency: String) -> Dictionary:
	var path := _dependency_path_from_string(raw_dependency)
	var uid := _dependency_uid_from_string(raw_dependency)
	var type_name := _dependency_type_from_string(raw_dependency, path, uid)
	var file_exists := false
	var resource_exists := false
	var global_path := ""
	if path != "":
		file_exists = FileAccess.file_exists(path)
		resource_exists = ResourceLoader.exists(path)
		global_path = ProjectSettings.globalize_path(path)
	elif uid != "":
		resource_exists = ResourceLoader.exists(uid)
	var exists := file_exists or resource_exists
	return {
		"raw": raw_dependency,
		"path": path,
		"uid": uid,
		"type": type_name,
		"global_path": global_path,
		"exists": exists,
		"file_exists": file_exists,
		"resource_exists": resource_exists,
		"checked": path != "",
		"resource_type": _resource_type_for_path(path) if path != "" and resource_exists else "",
	}


func _resource_dependency_matches_reference(
	dependency: Dictionary,
	target_path: String,
	target_uid: String,
	dependency_type: String,
	resource_type: String,
	exists_filter: Variant
) -> bool:
	if target_path != "" and String(dependency.get("path", "")) != target_path:
		return false
	if target_uid != "" and String(dependency.get("uid", "")) != target_uid:
		return false
	if dependency_type != "" and String(dependency.get("type", "")) != dependency_type:
		return false
	if resource_type != "" and String(dependency.get("resource_type", "")) != resource_type:
		return false
	if exists_filter != null and bool(dependency.get("exists", false)) != bool(exists_filter):
		return false
	return true


func _dependency_path_from_string(raw_dependency: String) -> String:
	for part in raw_dependency.split("::"):
		var text := String(part)
		if text.begins_with("res://"):
			return text
	var start := raw_dependency.find("res://")
	if start == -1:
		return ""
	var tail := raw_dependency.substr(start)
	var end := tail.find("::")
	if end == -1:
		return tail
	return tail.substr(0, end)


func _dependency_uid_from_string(raw_dependency: String) -> String:
	for part in raw_dependency.split("::"):
		var text := String(part)
		if text.begins_with("uid://"):
			return text
	var start := raw_dependency.find("uid://")
	if start == -1:
		return ""
	var tail := raw_dependency.substr(start)
	var end := tail.find("::")
	if end == -1:
		return tail
	return tail.substr(0, end)


func _dependency_type_from_string(raw_dependency: String, path: String, uid: String) -> String:
	var parts := raw_dependency.split("::")
	for index in range(parts.size() - 1, -1, -1):
		var text := String(parts[index])
		if text == "" or text == path or text == uid:
			continue
		if text.begins_with("res://") or text.begins_with("uid://"):
			continue
		return text
	return ""


func _collect_filesystem_entries(
	path: String,
	recursive: bool,
	include_dirs: bool,
	include_hidden: bool,
	filters: Dictionary,
	max_results: int,
	entries: Array
) -> void:
	if entries.size() >= max_results:
		return
	var entry := _filesystem_entry(path)
	if bool(entry.get("is_file", false)):
		if _matches_filesystem_filters(entry, filters):
			entries.append(entry)
		return
	if not bool(entry.get("is_directory", false)):
		return
	if include_dirs and _matches_filesystem_filters(entry, filters):
		entries.append(entry)
		if entries.size() >= max_results:
			return
	var dir := DirAccess.open(path)
	if dir == null:
		return
	dir.list_dir_begin()
	var name := dir.get_next()
	while name != "":
		if include_hidden or not name.begins_with("."):
			var child_path := path.path_join(name)
			if dir.current_is_dir():
				if recursive:
					_collect_filesystem_entries(child_path, recursive, include_dirs, include_hidden, filters, max_results, entries)
				elif include_dirs:
					var child_dir_entry := _filesystem_entry(child_path)
					if _matches_filesystem_filters(child_dir_entry, filters):
						entries.append(child_dir_entry)
			else:
				var child_entry := _filesystem_entry(child_path)
				if _matches_filesystem_filters(child_entry, filters):
					entries.append(child_entry)
		if entries.size() >= max_results:
			break
		name = dir.get_next()
	dir.list_dir_end()


func _matches_filesystem_filters(entry: Dictionary, filters: Dictionary) -> bool:
	var name := String(entry.get("name", ""))
	var exact_name := String(filters.get("name", ""))
	if exact_name != "" and name != exact_name:
		return false
	var contains := String(filters.get("name_contains", ""))
	if contains != "" and name.find(contains) == -1:
		return false
	var extension := String(filters.get("extension", "")).trim_prefix(".")
	if extension != "" and String(entry.get("extension", "")) != extension:
		return false
	var resource_type := String(filters.get("resource_type", ""))
	if resource_type != "" and String(entry.get("resource_type", "")) != resource_type:
		return false
	return true


func _is_text_search_path(path: String) -> bool:
	var extension := path.get_extension().to_lower()
	if extension == "":
		return true
	return [
		"cfg",
		"csv",
		"gd",
		"gdshader",
		"import",
		"json",
		"material",
		"md",
		"shader",
		"theme",
		"tres",
		"tscn",
		"txt",
		"translation",
	].has(extension)


func _grep_file(
	path: String,
	query: String,
	case_sensitive: bool,
	context_lines: int,
	max_matches_per_file: int,
	max_results: int,
	matches: Array
) -> void:
	if matches.size() >= max_results:
		return
	var source := FileAccess.get_file_as_string(path)
	var open_error := FileAccess.get_open_error()
	if open_error != OK:
		return
	var lines := source.split("\n")
	var needle := query if case_sensitive else query.to_lower()
	var file_matches := 0
	for index in range(lines.size()):
		if matches.size() >= max_results or file_matches >= max_matches_per_file:
			break
		var line := String(lines[index]).trim_suffix("\r")
		var haystack := line if case_sensitive else line.to_lower()
		var column := haystack.find(needle)
		while column >= 0:
			matches.append({
				"path": path,
				"global_path": ProjectSettings.globalize_path(path),
				"line": index + 1,
				"column": column,
				"text": line,
				"before": _grep_context(lines, max(0, index - context_lines), index),
				"after": _grep_context(lines, index + 1, min(lines.size(), index + 1 + context_lines)),
			})
			file_matches += 1
			if matches.size() >= max_results or file_matches >= max_matches_per_file:
				break
			column = haystack.find(needle, column + max(1, needle.length()))


func _grep_context(lines: PackedStringArray, start: int, end: int) -> Array:
	var context := []
	for index in range(start, end):
		context.append({"line": index + 1, "text": String(lines[index]).trim_suffix("\r")})
	return context


func _public_bulk_replace_changes(changes: Array) -> Array:
	var public_changes := []
	for change in changes:
		var public_change: Dictionary = change.duplicate()
		public_change.erase("_text")
		public_changes.append(public_change)
	return public_changes


func _replace_text_with_evidence(
	source: String,
	old_text: String,
	new_text: String,
	case_sensitive: bool,
	max_replacements: int,
	max_preview: int
) -> Dictionary:
	var search_source := source if case_sensitive else source.to_lower()
	var needle := old_text if case_sensitive else old_text.to_lower()
	var positions := []
	var cursor := 0
	while true:
		var position := search_source.find(needle, cursor)
		if position < 0:
			break
		positions.append(position)
		cursor = position + max(1, needle.length())
	var replace_count := positions.size()
	if max_replacements > 0:
		replace_count = min(replace_count, max_replacements)
	var output := ""
	var source_cursor := 0
	for index in range(replace_count):
		var position := int(positions[index])
		output += source.substr(source_cursor, position - source_cursor)
		output += new_text
		source_cursor = position + old_text.length()
	output += source.substr(source_cursor)
	var edits := []
	var delta := 0
	for index in range(min(max_preview, positions.size())):
		var before_position := int(positions[index])
		var after_position := before_position + delta
		var before := _text_line_at_offset(source, before_position)
		var after := _text_line_at_offset(output, after_position)
		edits.append({
			"line": before.get("line", 1),
			"column": before.get("column", 0),
			"before": before,
			"after": after,
		})
		if index < replace_count:
			delta += new_text.length() - old_text.length()
	return {
		"text": output,
		"match_count": positions.size(),
		"replacements": replace_count,
		"edits": edits,
	}


func _text_line_at_offset(text: String, offset: int) -> Dictionary:
	var safe_offset := min(max(offset, 0), text.length())
	var line := 1
	var line_start := 0
	var cursor := 0
	while true:
		var newline := text.find("\n", cursor)
		if newline < 0 or newline >= safe_offset:
			break
		line += 1
		line_start = newline + 1
		cursor = newline + 1
	var line_end := text.find("\n", line_start)
	if line_end < 0:
		line_end = text.length()
	return {
		"line": line,
		"column": safe_offset - line_start,
		"text": text.substr(line_start, line_end - line_start).trim_suffix("\r"),
	}


func _resource_summary(resource: Resource) -> Dictionary:
	return {
		"path": resource.resource_path,
		"global_path": "" if resource.resource_path == "" else ProjectSettings.globalize_path(resource.resource_path),
		"class": resource.get_class(),
		"resource_name": resource.resource_name,
	}


func _resource_property_schema(resource: Resource, info: Dictionary, include_value: bool) -> Dictionary:
	var name := String(info.get("name", ""))
	var usage := int(info.get("usage", 0))
	var type_id := int(info.get("type", TYPE_NIL))
	var summary := {
		"name": name,
		"type": type_id,
		"type_name": _variant_type_name(type_id),
		"hint": int(info.get("hint", PROPERTY_HINT_NONE)),
		"hint_string": String(info.get("hint_string", "")),
		"usage": usage,
		"storage": (usage & PROPERTY_USAGE_STORAGE) != 0,
		"editor_visible": _property_is_editor_visible(info),
		"exists": _property_name_set(resource).has(name),
	}
	if include_value:
		summary["value"] = _encode_value(resource.get(name))
	return summary


func _node_property_schema(node: Node, info: Dictionary, include_value: bool) -> Dictionary:
	var name := String(info.get("name", ""))
	var usage := int(info.get("usage", 0))
	var type_id := int(info.get("type", TYPE_NIL))
	var summary := {
		"name": name,
		"type": type_id,
		"type_name": _variant_type_name(type_id),
		"hint": int(info.get("hint", PROPERTY_HINT_NONE)),
		"hint_string": String(info.get("hint_string", "")),
		"usage": usage,
		"storage": (usage & PROPERTY_USAGE_STORAGE) != 0,
		"editor_visible": _property_is_editor_visible(info),
		"exists": _property_name_set(node).has(name),
	}
	if include_value:
		summary["value"] = _encode_value(node.get(name))
	return summary


func _api_info_summary(info: Dictionary) -> Dictionary:
	var summary := {}
	for key in ["name", "flags", "id", "usage", "default_value"]:
		if info.has(key):
			summary[key] = _encode_value(info[key])
	if info.has("type"):
		summary["type"] = int(info.get("type", TYPE_NIL))
		summary["type_name"] = _variant_type_name(int(info.get("type", TYPE_NIL)))
	if info.has("args"):
		var args := _api_argument_summaries(info.get("args", []))
		summary["args"] = args
		summary["arg_count"] = args.size()
	if info.has("default_args"):
		var default_args = info.get("default_args", [])
		summary["default_args"] = _encode_value(default_args)
		summary["default_arg_count"] = default_args.size() if typeof(default_args) == TYPE_ARRAY else 0
	if info.has("return"):
		summary["return"] = _api_type_summary(info.get("return", {}))
	return summary


func _api_argument_summaries(args: Variant) -> Array:
	var summaries := []
	if typeof(args) != TYPE_ARRAY:
		return summaries
	for arg in args:
		summaries.append(_api_type_summary(arg))
	return summaries


func _api_type_summary(value: Variant) -> Variant:
	if typeof(value) == TYPE_DICTIONARY:
		var info: Dictionary = value
		var summary := {}
		for key in ["name", "class_name", "hint", "hint_string", "usage", "default_value"]:
			if info.has(key):
				summary[key] = _encode_value(info[key])
		if info.has("type"):
			summary["type"] = int(info.get("type", TYPE_NIL))
			summary["type_name"] = _variant_type_name(int(info.get("type", TYPE_NIL)))
		return summary
	if typeof(value) == TYPE_INT:
		var type_id := int(value)
		return {"type": type_id, "type_name": _variant_type_name(type_id)}
	return _encode_value(value)


func _resource_class_list_entry(resource_class_name: String, include_property_counts: bool) -> Dictionary:
	var can_instantiate := resource_class_name == "Resource" or ClassDB.can_instantiate(resource_class_name)
	var enabled := true
	if ClassDB.has_method("is_class_enabled"):
		enabled = bool(ClassDB.is_class_enabled(resource_class_name))
	var entry := {
		"class": resource_class_name,
		"name": resource_class_name,
		"parent": "" if resource_class_name == "Object" else String(ClassDB.get_parent_class(resource_class_name)),
		"is_resource": resource_class_name == "Resource" or ClassDB.is_parent_class(resource_class_name, "Resource"),
		"can_instantiate": can_instantiate,
		"enabled": enabled,
		"api_type": int(ClassDB.class_get_api_type(resource_class_name)),
	}
	if include_property_counts:
		var storage_count := 0
		var editor_count := 0
		var property_count := 0
		for info in ClassDB.class_get_property_list(resource_class_name, false):
			if typeof(info) != TYPE_DICTIONARY:
				continue
			property_count += 1
			var usage := int(info.get("usage", 0))
			if (usage & PROPERTY_USAGE_STORAGE) != 0:
				storage_count += 1
			if _property_is_editor_visible(info):
				editor_count += 1
		entry["property_count"] = property_count
		entry["storage_property_count"] = storage_count
		entry["editor_property_count"] = editor_count
	return entry


func _node_class_list_entry(node_class_name: String, include_property_counts: bool) -> Dictionary:
	var can_instantiate := node_class_name == "Node" or ClassDB.can_instantiate(node_class_name)
	var enabled := true
	if ClassDB.has_method("is_class_enabled"):
		enabled = bool(ClassDB.is_class_enabled(node_class_name))
	var entry := {
		"class": node_class_name,
		"name": node_class_name,
		"parent": "" if node_class_name == "Object" else String(ClassDB.get_parent_class(node_class_name)),
		"is_node": node_class_name == "Node" or ClassDB.is_parent_class(node_class_name, "Node"),
		"can_instantiate": can_instantiate,
		"enabled": enabled,
		"api_type": int(ClassDB.class_get_api_type(node_class_name)),
	}
	if include_property_counts:
		var storage_count := 0
		var editor_count := 0
		var property_count := 0
		for info in ClassDB.class_get_property_list(node_class_name, false):
			if typeof(info) != TYPE_DICTIONARY:
				continue
			property_count += 1
			var usage := int(info.get("usage", 0))
			if (usage & PROPERTY_USAGE_STORAGE) != 0:
				storage_count += 1
			if _property_is_editor_visible(info):
				editor_count += 1
		entry["property_count"] = property_count
		entry["storage_property_count"] = storage_count
		entry["editor_property_count"] = editor_count
	return entry


func _string_filter_array(value: Variant) -> Array:
	var result := []
	if typeof(value) == TYPE_STRING:
		var text := String(value)
		if text != "":
			result.append(text)
		return result
	if typeof(value) != TYPE_ARRAY:
		return result
	for item in value:
		var text := String(item)
		if text != "":
			result.append(text)
	return result


func _normalized_extension_filter(value: Variant, default_extensions: Array) -> Array:
	var extensions := _string_filter_array(value)
	if extensions.is_empty():
		extensions = default_extensions.duplicate()
	for index in range(extensions.size()):
		extensions[index] = String(extensions[index]).trim_prefix(".").to_lower()
	return extensions


func _validate_resource_graph_properties(properties: Dictionary) -> String:
	for property in properties.keys():
		var error := _validate_resource_graph_value(properties[property], String(property))
		if error != "":
			return error
	return ""


func _validate_resource_graph_value(value: Variant, context: String) -> String:
	if typeof(value) == TYPE_ARRAY:
		for index in range(value.size()):
			var error := _validate_resource_graph_value(value[index], "%s[%s]" % [context, index])
			if error != "":
				return error
		return ""
	if typeof(value) != TYPE_DICTIONARY:
		return ""
	var dictionary: Dictionary = value
	if not dictionary.has("$type"):
		for key in dictionary.keys():
			var error := _validate_resource_graph_value(dictionary[key], "%s.%s" % [context, key])
			if error != "":
				return error
		return ""
	var type_name := String(dictionary.get("$type", ""))
	if type_name in ["ResourceRef", "ExtResource"]:
		var resource_path := String(dictionary.get("path", dictionary.get("resource_path", "")))
		if resource_path == "":
			return "%s ResourceRef requires path" % context
		var path_error := _validate_res_path(resource_path)
		if path_error != "":
			return "%s %s" % [context, path_error]
		if not ResourceLoader.exists(resource_path):
			return "%s resource reference not found: %s" % [context, resource_path]
		return ""
	if type_name in ["Resource", "SubResource"]:
		var resource_path := String(dictionary.get("path", dictionary.get("resource_path", "")))
		if resource_path != "":
			var path_error := _validate_res_path(resource_path)
			if path_error != "":
				return "%s %s" % [context, path_error]
			if not ResourceLoader.exists(resource_path):
				return "%s resource reference not found: %s" % [context, resource_path]
			return ""
		var resource_class_name := String(dictionary.get("class", dictionary.get("class_name", "Resource")))
		if not _resource_class_can_instantiate(resource_class_name):
			return "%s cannot instantiate resource class: %s" % [context, resource_class_name]
		var nested_properties = dictionary.get("properties", {})
		if typeof(nested_properties) != TYPE_DICTIONARY:
			return "%s properties must be an object" % context
		return _validate_resource_graph_value(nested_properties, "%s.properties" % context)
	return ""


func _resource_class_can_instantiate(resource_class_name: String) -> bool:
	if resource_class_name == "Resource":
		return true
	if not ClassDB.class_exists(resource_class_name) or not ClassDB.can_instantiate(resource_class_name):
		return false
	var instance = ClassDB.instantiate(resource_class_name)
	return instance is Resource


func _instantiate_resource_class(resource_class_name: String) -> Resource:
	if resource_class_name == "" or resource_class_name == "Resource":
		return Resource.new()
	var instance = ClassDB.instantiate(resource_class_name)
	if instance is Resource:
		return instance
	return null


func _selected_resource_properties(resource: Resource) -> Dictionary:
	var properties := {}
	for info in resource.get_property_list():
		var name := String(info.get("name", ""))
		if name == "" or name.begins_with("_"):
			continue
		if name in ["resource_path", "resource_local_to_scene", "resource_scene_unique_id", "script"]:
			continue
		var usage := int(info.get("usage", 0))
		if (usage & PROPERTY_USAGE_STORAGE) == 0:
			continue
		properties[name] = _encode_value(resource.get(name))
	return properties


func _script_file_summary(path: String, include_source: bool) -> Dictionary:
	var source := FileAccess.get_file_as_string(path)
	var open_error := FileAccess.get_open_error()
	var symbols := _script_symbols_from_source(source) if open_error == OK else _script_symbols_from_source("")
	var file_exists := FileAccess.file_exists(path)
	var resource_exists := ResourceLoader.exists(path)
	var script: Script = null
	if resource_exists:
		var loaded = ResourceLoader.load(path)
		if loaded is Script:
			script = loaded
	var methods := []
	var properties := []
	var signals := []
	if script != null and open_error == OK:
		methods = _script_method_summaries(script, source)
		properties = _script_member_summaries(script, source)
		signals = _script_signal_summaries(script, source)
	else:
		methods = symbols.get("functions", [])
		properties = symbols.get("variables", [])
		signals = symbols.get("signals", [])
	var script_class := script.get_class() if script != null else ("GDScript" if file_exists else "")
	var script_class_name := String(symbols.get("class_name", ""))
	var script_extends := String(symbols.get("extends", ""))
	var summary := {
		"path": path,
		"name": path.get_file(),
		"global_path": ProjectSettings.globalize_path(path),
		"exists": file_exists,
		"file_exists": file_exists,
		"resource_exists": resource_exists,
		"load_error": resource_exists and script == null,
		"extension": path.get_extension().to_lower(),
		"language": "GDScript",
		"class": script_class,
		"class_name": script_class_name,
		"extends": script_extends,
		"methods": methods,
		"method_count": methods.size(),
		"functions": symbols.get("functions", []),
		"function_count": Array(symbols.get("functions", [])).size(),
		"properties": properties,
		"property_count": properties.size(),
		"variables": symbols.get("variables", []),
		"variable_count": Array(symbols.get("variables", [])).size(),
		"constants": symbols.get("constants", []),
		"constant_count": Array(symbols.get("constants", [])).size(),
		"signals": signals,
		"signal_count": signals.size(),
		"symbols": symbols,
		"ok": file_exists and open_error == OK and not (resource_exists and script == null),
		"open_error": open_error,
	}
	if include_source:
		summary["source"] = source
	return summary


func _script_method_summaries(script: Script, source: String) -> Array:
	var methods := []
	if script.has_method("get_script_method_list"):
		for info in script.call("get_script_method_list"):
			if typeof(info) == TYPE_DICTIONARY:
				methods.append(_script_api_summary(info))
	if methods.is_empty():
		for symbol in _script_symbols_from_source(source).get("functions", []):
			methods.append(symbol)
	return methods


func _script_member_summaries(script: Script, source: String) -> Array:
	var properties := []
	if script.has_method("get_script_property_list"):
		for info in script.call("get_script_property_list"):
			if typeof(info) == TYPE_DICTIONARY:
				properties.append(_script_api_summary(info))
	if properties.is_empty():
		for symbol in _script_symbols_from_source(source).get("variables", []):
			properties.append(symbol)
	return properties


func _script_signal_summaries(script: Script, source: String) -> Array:
	var signals := []
	if script.has_method("get_script_signal_list"):
		for info in script.call("get_script_signal_list"):
			if typeof(info) == TYPE_DICTIONARY:
				signals.append(_script_api_summary(info))
	if signals.is_empty():
		for symbol in _script_symbols_from_source(source).get("signals", []):
			signals.append(symbol)
	return signals


func _script_api_summary(info: Dictionary) -> Dictionary:
	return _api_info_summary(info)


func _script_symbols_from_source(source: String) -> Dictionary:
	var symbols := {
		"class_name": "",
		"extends": "",
		"functions": [],
		"variables": [],
		"constants": [],
		"signals": [],
	}
	var lines := source.split("\n")
	for index in range(lines.size()):
		var raw_line := String(lines[index])
		var line := raw_line.strip_edges()
		if line == "" or line.begins_with("#"):
			continue
		if line.begins_with("class_name "):
			symbols["class_name"] = _symbol_name_after_prefix(line, "class_name ")
		elif line.begins_with("extends "):
			symbols["extends"] = _symbol_name_after_prefix(line, "extends ")
		elif line.begins_with("func "):
			symbols["functions"].append(_named_symbol(line, "func ", index + 1))
		elif line.begins_with("static func "):
			var symbol := _named_symbol(line, "static func ", index + 1)
			symbol["static"] = true
			symbols["functions"].append(symbol)
		elif line.begins_with("var "):
			symbols["variables"].append(_named_symbol(line, "var ", index + 1))
		elif line.begins_with("@export var "):
			var exported := _named_symbol(line, "@export var ", index + 1)
			exported["exported"] = true
			symbols["variables"].append(exported)
		elif line.begins_with("const "):
			symbols["constants"].append(_named_symbol(line, "const ", index + 1))
		elif line.begins_with("signal "):
			symbols["signals"].append(_named_symbol(line, "signal ", index + 1))
	return symbols


func _symbol_name_after_prefix(line: String, prefix: String) -> String:
	var value := line.substr(prefix.length()).strip_edges()
	if value.begins_with("\"") or value.begins_with("'"):
		var quote := value.substr(0, 1)
		var quote_end := value.find(quote, 1)
		if quote_end != -1:
			return value.substr(1, quote_end - 1).strip_edges()
	for separator in [" ", "(", ":", "=", "\t"]:
		var at := value.find(separator)
		if at != -1:
			value = value.substr(0, at)
	return value.strip_edges()


func _named_symbol(line: String, prefix: String, line_number: int) -> Dictionary:
	return {
		"name": _symbol_name_after_prefix(line, prefix),
		"line": line_number,
		"signature": line,
	}


func _script_resolved_extends_name(extends_name: String, path_classes: Dictionary) -> String:
	var text := extends_name.strip_edges()
	if text.begins_with("res://"):
		return String(path_classes.get(text, text))
	return text


func _script_extends_matches(extends_name: String, expected: String, path_classes: Dictionary) -> bool:
	var expected_text := expected.strip_edges()
	if expected_text == "":
		return true
	var actual := extends_name.strip_edges()
	if actual == expected_text:
		return true
	return _script_resolved_extends_name(actual, path_classes) == expected_text


func _script_class_matches_base(
	script_class_name: String,
	extends_name: String,
	base_class: String,
	class_extends: Dictionary,
	path_classes: Dictionary
) -> bool:
	var base := base_class.strip_edges()
	if base == "" or base == "Object":
		return true
	if script_class_name != "" and script_class_name == base:
		return true
	return _script_inherits_from(extends_name, base, class_extends, path_classes, {})


func _script_extends_or_is_class(
	script_class_name: String,
	extends_name: String,
	base_class: String,
	class_extends: Dictionary,
	path_classes: Dictionary
) -> bool:
	var base := base_class.strip_edges()
	if base == "" or base == "Object":
		return true
	if script_class_name != "" and script_class_name == base:
		return true
	return _script_inherits_from(extends_name, base, class_extends, path_classes, {})


func _script_inherits_from(
	script_class_name: String,
	base_class: String,
	class_extends: Dictionary,
	path_classes: Dictionary,
	seen: Dictionary
) -> bool:
	var current := _script_resolved_extends_name(script_class_name.strip_edges(), path_classes)
	var base := base_class.strip_edges()
	if current == "" or base == "":
		return false
	if current == base:
		return true
	if ClassDB.class_exists(current):
		if ClassDB.class_exists(base) and ClassDB.is_parent_class(current, base):
			return true
		if base == "Object":
			return true
	if seen.has(current):
		return false
	seen[current] = true
	var parent := String(class_extends.get(current, ""))
	if parent == "":
		return false
	return _script_inherits_from(parent, base, class_extends, path_classes, seen)


func _rpc_trace_start(params: Dictionary) -> Dictionary:
	if bool(params.get("clear", true)):
		_trace_events.clear()
	_trace_enabled = true
	_trace_max_events = max(1, int(params.get("max_events", _trace_max_events)))
	_record_event("trace.start", {"max_events": _trace_max_events})
	return _ok({"enabled": true, "events": _trace_events.size(), "max_events": _trace_max_events})


func _rpc_trace_stop() -> Dictionary:
	_record_event("trace.stop", {})
	_trace_enabled = false
	return _ok({"enabled": false, "events": _trace_events.size()})


func _rpc_trace_events(params: Dictionary) -> Dictionary:
	var events := []
	for event in _trace_events:
		events.append(event)
	if bool(params.get("clear", false)):
		_trace_events.clear()
	return _ok({"enabled": _trace_enabled, "events": events})


func _rpc_trace_clear() -> Dictionary:
	_trace_events.clear()
	return _ok({"enabled": _trace_enabled, "events": 0})


func _rpc_signal_watch(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", {}), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var signal_name := String(params.get("signal", ""))
	if signal_name == "":
		return _fail("signal is required", -32602)
	if not node.has_signal(signal_name):
		return _fail("Node %s has no signal %s" % [node.get_path(), signal_name])

	var watch_id := "signal-%s" % _next_signal_watch_id
	_next_signal_watch_id += 1
	var callback := Callable(self, "_on_watched_signal").bind(watch_id)
	var error := node.connect(signal_name, callback)
	if error != OK:
		return _fail("Failed to connect signal %s: %s" % [signal_name, error])

	var watch := {
		"id": watch_id,
		"node": node,
		"path": str(node.get_path()),
		"signal": signal_name,
		"callback": callback,
		"once": bool(params.get("once", false)),
		"created_ms": Time.get_ticks_msec(),
	}
	_signal_watches[watch_id] = watch
	_record_event("signal.watch", {
		"id": watch_id,
		"path": watch["path"],
		"signal": signal_name,
		"once": watch["once"],
	})
	return _ok(_signal_watch_summary(watch))


func _rpc_signal_unwatch(params: Dictionary) -> Dictionary:
	var watch_id := String(params.get("watch_id", params.get("id", "")))
	if watch_id == "":
		return _fail("watch_id is required", -32602)
	if not _signal_watches.has(watch_id):
		return _ok({"watch_id": watch_id, "removed": false})
	_disconnect_signal_watch(watch_id)
	_record_event("signal.unwatch", {"id": watch_id})
	return _ok({"watch_id": watch_id, "removed": true})


func _rpc_signal_events(params: Dictionary) -> Dictionary:
	var watch_id := String(params.get("watch_id", ""))
	var clear := bool(params.get("clear", false))
	var events := []
	var remaining := []
	for event in _signal_events:
		if watch_id == "" or String(event.get("watch_id", "")) == watch_id:
			events.append(event)
			if not clear:
				remaining.append(event)
		else:
			remaining.append(event)
	if clear:
		_signal_events = remaining
	return _ok({"events": events, "watch_count": _signal_watches.size()})


func _rpc_signal_clear(params: Dictionary) -> Dictionary:
	var watch_id := String(params.get("watch_id", ""))
	if watch_id == "":
		_signal_events.clear()
	else:
		var remaining := []
		for event in _signal_events:
			if String(event.get("watch_id", "")) != watch_id:
				remaining.append(event)
		_signal_events = remaining
	return _ok({"events": _signal_events.size()})


func _rpc_signal_connections(params: Dictionary) -> Dictionary:
	var node := _resolve_node(params.get("selector", params.get("source", {})), params.get("root", "edited"))
	if node == null:
		return _fail("Node not found")
	var requested_signal := String(params.get("signal", ""))
	var connections := []
	if requested_signal != "":
		if not node.has_signal(requested_signal):
			return _fail("Node %s has no signal %s" % [node.get_path(), requested_signal])
		for info in node.get_signal_connection_list(requested_signal):
			if typeof(info) == TYPE_DICTIONARY:
				connections.append(_signal_connection_summary(node, requested_signal, info))
	else:
		for signal_info in node.get_signal_list():
			if typeof(signal_info) != TYPE_DICTIONARY:
				continue
			var signal_name := String(signal_info.get("name", ""))
			if signal_name == "":
				continue
			for info in node.get_signal_connection_list(signal_name):
				if typeof(info) == TYPE_DICTIONARY:
					connections.append(_signal_connection_summary(node, signal_name, info))
	return _ok({
		"node": _node_summary(node),
		"signal": requested_signal,
		"connections": connections,
		"count": connections.size(),
	})


func _rpc_signal_connect(params: Dictionary) -> Dictionary:
	var source := _resolve_node(params.get("selector", params.get("source", {})), params.get("root", "edited"))
	if source == null:
		return _fail("Source node not found")
	var signal_name := String(params.get("signal", ""))
	if signal_name == "":
		return _fail("signal is required", -32602)
	if not source.has_signal(signal_name):
		return _fail("Node %s has no signal %s" % [source.get_path(), signal_name])
	var target := _resolve_signal_target(params, source)
	if target == null:
		return _fail("Target node not found")
	var method := String(params.get("method", ""))
	if method == "":
		return _fail("method is required", -32602)
	if bool(params.get("validate_method", true)) and not _node_has_callable_method(target, method):
		return _fail("Target node %s has no method %s" % [target.get_path(), method], -32602)

	var callable := Callable(target, method)
	var binds := []
	if params.has("binds"):
		if typeof(params["binds"]) != TYPE_ARRAY:
			return _fail("binds must be an array", -32602)
		for item in params["binds"]:
			binds.append(_decode_value(item))
		if not binds.is_empty():
			callable = callable.bindv(binds)

	var existing_info := _find_signal_connection(source, signal_name, target, method, _encode_value(binds))
	var had_existing := not existing_info.is_empty()
	if had_existing and bool(params.get("replace", false)):
		source.disconnect(signal_name, callable)
		had_existing = false
	elif had_existing:
		return _ok({
			"source": _node_summary(source),
			"target": _node_summary(target),
			"signal": signal_name,
			"method": method,
			"connected": false,
			"already_connected": true,
			"connection": _signal_connection_summary(source, signal_name, existing_info),
			"connections": _signal_connections_for(source, signal_name),
		})

	var flags := _signal_connect_flags(params)
	var error := source.connect(signal_name, callable, flags)
	if error != OK:
		return _fail("Failed to connect signal %s: %s" % [signal_name, error])
	if editor_interface != null:
		editor_interface.mark_scene_as_unsaved()
	var connection_info := _find_signal_connection(source, signal_name, target, method, _encode_value(binds))
	var summary := {} if connection_info.is_empty() else _signal_connection_summary(source, signal_name, connection_info)
	_record_event("signal.connect", {
		"source": str(source.get_path()),
		"target": str(target.get_path()),
		"signal": signal_name,
		"method": method,
		"flags": flags,
	})
	return _ok({
		"source": _node_summary(source),
		"target": _node_summary(target),
		"signal": signal_name,
		"method": method,
		"connected": true,
		"already_connected": false,
		"connection": summary,
		"connections": _signal_connections_for(source, signal_name),
	})


func _rpc_signal_disconnect(params: Dictionary) -> Dictionary:
	var source := _resolve_node(params.get("selector", params.get("source", {})), params.get("root", "edited"))
	if source == null:
		return _fail("Source node not found")
	var signal_name := String(params.get("signal", ""))
	if signal_name == "":
		return _fail("signal is required", -32602)
	if not source.has_signal(signal_name):
		return _fail("Node %s has no signal %s" % [source.get_path(), signal_name])
	var target := _resolve_signal_target(params, source)
	if target == null:
		return _fail("Target node not found")
	var method := String(params.get("method", ""))
	if method == "":
		return _fail("method is required", -32602)
	var binds := []
	if params.has("binds"):
		if typeof(params["binds"]) != TYPE_ARRAY:
			return _fail("binds must be an array", -32602)
		for item in params["binds"]:
			binds.append(_decode_value(item))
	var encoded_binds := _encode_value(binds)
	var connection_info := _find_signal_connection(source, signal_name, target, method, encoded_binds)
	if connection_info.is_empty():
		return _ok({
			"source": _node_summary(source),
			"target": _node_summary(target),
			"signal": signal_name,
			"method": method,
			"removed": false,
			"connections": _signal_connections_for(source, signal_name),
		})
	var callable := Callable(target, method)
	if not binds.is_empty():
		callable = callable.bindv(binds)
	source.disconnect(signal_name, callable)
	if editor_interface != null:
		editor_interface.mark_scene_as_unsaved()
	_record_event("signal.disconnect", {
		"source": str(source.get_path()),
		"target": str(target.get_path()),
		"signal": signal_name,
		"method": method,
	})
	return _ok({
		"source": _node_summary(source),
		"target": _node_summary(target),
		"signal": signal_name,
		"method": method,
		"removed": true,
		"connection": _signal_connection_summary(source, signal_name, connection_info),
		"connections": _signal_connections_for(source, signal_name),
	})


func _on_watched_signal(...args) -> void:
	if args.is_empty():
		return
	var watch_id := String(args.pop_back())
	if not _signal_watches.has(watch_id):
		return
	var watch: Dictionary = _signal_watches[watch_id]
	var event := {
		"watch_id": watch_id,
		"signal": watch.get("signal", ""),
		"path": watch.get("path", ""),
		"args": _encode_value(args),
		"ts_ms": Time.get_ticks_msec(),
		"uptime_ms": Time.get_ticks_msec() - _started_ms,
	}
	_signal_events.append(event)
	while _signal_events.size() > _signal_max_events:
		_signal_events.remove_at(0)
	_record_event("signal.event", event)
	if bool(watch.get("once", false)):
		_disconnect_signal_watch(watch_id)


func _signal_watch_summary(watch: Dictionary) -> Dictionary:
	return {
		"watch_id": watch.get("id", ""),
		"path": watch.get("path", ""),
		"signal": watch.get("signal", ""),
		"once": watch.get("once", false),
	}


func _disconnect_signal_watch(watch_id: String) -> void:
	if not _signal_watches.has(watch_id):
		return
	var watch: Dictionary = _signal_watches[watch_id]
	var node = watch.get("node")
	var signal_name := String(watch.get("signal", ""))
	var callback: Callable = watch.get("callback", Callable())
	if node != null and is_instance_valid(node) and signal_name != "" and callback.is_valid():
		if node.is_connected(signal_name, callback):
			node.disconnect(signal_name, callback)
	_signal_watches.erase(watch_id)


func _disconnect_all_signal_watches() -> void:
	var ids := []
	for watch_id in _signal_watches.keys():
		ids.append(String(watch_id))
	for watch_id in ids:
		_disconnect_signal_watch(watch_id)


func _resolve_signal_target(params: Dictionary, source: Node) -> Node:
	var target_spec = params.get("target", params.get("receiver", params.get("target_node", null)))
	if target_spec == null:
		return source
	if typeof(target_spec) == TYPE_STRING and String(target_spec) == "":
		return source
	return _resolve_node(target_spec, params.get("target_root", params.get("root", "edited")))


func _signal_connect_flags(params: Dictionary) -> int:
	var flags := int(params.get("flags", 0))
	if bool(params.get("persistent", editor_interface != null)):
		flags = flags | Object.CONNECT_PERSIST
	if bool(params.get("deferred", false)):
		flags = flags | Object.CONNECT_DEFERRED
	if bool(params.get("one_shot", params.get("oneshot", false))):
		flags = flags | Object.CONNECT_ONE_SHOT
	if bool(params.get("reference_counted", false)):
		flags = flags | Object.CONNECT_REFERENCE_COUNTED
	return flags


func _signal_connections_for(source: Node, signal_name: String) -> Array:
	var connections := []
	for info in source.get_signal_connection_list(signal_name):
		if typeof(info) == TYPE_DICTIONARY:
			connections.append(_signal_connection_summary(source, signal_name, info))
	return connections


func _find_signal_connection(
	source: Node,
	signal_name: String,
	target: Node,
	method: String,
	encoded_binds: Variant
) -> Dictionary:
	for info in source.get_signal_connection_list(signal_name):
		if typeof(info) != TYPE_DICTIONARY:
			continue
		var callable: Callable = info.get("callable", Callable())
		if callable.get_object() != target:
			continue
		if String(callable.get_method()) != method:
			continue
		if not _encoded_values_equal(_callable_bound_arguments(callable), encoded_binds):
			continue
		return info
	return {}


func _signal_connection_summary(source: Node, signal_name: String, info: Dictionary) -> Dictionary:
	var callable: Callable = info.get("callable", Callable())
	var flags := int(info.get("flags", 0))
	var target = callable.get_object()
	var target_path := ""
	var target_class := ""
	var target_id := 0
	if target != null and is_instance_valid(target):
		target_class = target.get_class()
		target_id = target.get_instance_id()
		if target is Node:
			target_path = str((target as Node).get_path())
	return {
		"source_path": str(source.get_path()),
		"source_class": source.get_class(),
		"signal": signal_name,
		"target_path": target_path,
		"target_class": target_class,
		"target_id": target_id,
		"method": String(callable.get_method()),
		"binds": _callable_bound_arguments(callable),
		"flags": flags,
		"persistent": (flags & Object.CONNECT_PERSIST) != 0,
		"deferred": (flags & Object.CONNECT_DEFERRED) != 0,
		"one_shot": (flags & Object.CONNECT_ONE_SHOT) != 0,
		"reference_counted": (flags & Object.CONNECT_REFERENCE_COUNTED) != 0,
		"valid": callable.is_valid(),
		"callable": str(callable),
	}


func _callable_bound_arguments(callable: Callable) -> Array:
	var binds := []
	for item in callable.get_bound_arguments():
		binds.append(_encode_value(item))
	return binds


func _node_has_callable_method(node: Node, method: String) -> bool:
	if node.has_method(method):
		return true
	var script = node.get_script()
	if script == null or not (script is Script):
		return false
	return _script_has_method_name(script as Script, method)


func _script_has_method_name(script: Script, method: String) -> bool:
	if script.has_method("get_script_method_list"):
		for info in script.call("get_script_method_list"):
			if typeof(info) == TYPE_DICTIONARY and String(info.get("name", "")) == method:
				return true
	var source := ""
	if script.resource_path != "" and FileAccess.file_exists(script.resource_path):
		source = FileAccess.get_file_as_string(script.resource_path)
	for symbol in _script_symbols_from_source(source).get("functions", []):
		if typeof(symbol) == TYPE_DICTIONARY and String(symbol.get("name", "")) == method:
			return true
	return false


func _record_event(kind: String, data: Dictionary = {}) -> void:
	if not _trace_enabled:
		return
	_trace_events.append({
		"ts_ms": Time.get_ticks_msec(),
		"uptime_ms": Time.get_ticks_msec() - _started_ms,
		"type": kind,
		"data": _encode_value(data),
	})
	while _trace_events.size() > _trace_max_events:
		_trace_events.remove_at(0)


func _edited_scene_root() -> Node:
	if editor_interface != null:
		var edited = editor_interface.get_edited_scene_root()
		if edited != null:
			return edited
	return null


func _editor_root() -> Node:
	if editor_interface != null and editor_interface.has_method("get_base_control"):
		var base = editor_interface.call("get_base_control")
		if base is Node:
			return base
	return get_tree().get_root()


func _default_root() -> Node:
	var edited := _edited_scene_root()
	if edited != null:
		return edited
	var current := get_tree().get_current_scene()
	if current != null:
		return current
	return get_tree().get_root()


func _node_is_ancestor(ancestor: Node, node: Node) -> bool:
	var current := node.get_parent()
	while current != null:
		if current == ancestor:
			return true
		current = current.get_parent()
	return false


func _assign_owner_scene_recursive(node: Node) -> void:
	var owner_scene := _edited_scene_root()
	if owner_scene == null:
		return
	_assign_owner_recursive(node, owner_scene)


func _assign_owner_recursive(node: Node, owner_scene: Node) -> void:
	if node != owner_scene:
		node.owner = owner_scene
	for child in node.get_children():
		if child is Node:
			_assign_owner_recursive(child, owner_scene)


func _assign_pack_owner_recursive(node: Node, pack_root: Node, previous_owners: Dictionary) -> void:
	if node != pack_root:
		previous_owners[node.get_instance_id()] = {"node": node, "owner": node.owner}
		node.owner = pack_root
	for child in node.get_children():
		if child is Node:
			_assign_pack_owner_recursive(child, pack_root, previous_owners)


func _restore_node_owners(previous_owners: Dictionary) -> void:
	for entry in previous_owners.values():
		if typeof(entry) != TYPE_DICTIONARY:
			continue
		var node = entry.get("node")
		if node != null and is_instance_valid(node):
			(node as Node).owner = entry.get("owner", null)


func _resolve_root(root_spec: Variant) -> Node:
	if root_spec == null:
		return _default_root()
	if typeof(root_spec) == TYPE_STRING:
		var value := String(root_spec)
		if value == "" or value == "edited" or value == "scene":
			return _default_root()
		if value == "editor" or value == "ui":
			return _editor_root()
		if value == "root":
			return get_tree().get_root()
	if typeof(root_spec) == TYPE_DICTIONARY and root_spec.has("selector"):
		return _resolve_node(root_spec["selector"], root_spec.get("root", "edited"))
	return _resolve_node(root_spec, "root")


func _resolve_node(selector: Variant, root_spec: Variant = "edited") -> Node:
	if selector is Node:
		return selector
	if typeof(selector) == TYPE_DICTIONARY and selector.has("selector"):
		return _resolve_node(selector["selector"], selector.get("root", root_spec))
	if typeof(selector) == TYPE_STRING:
		var text := String(selector)
		if text == "edited" or text == "scene":
			return _default_root()
		if text == "root":
			return get_tree().get_root()
		if text.begins_with("/"):
			return get_node_or_null(NodePath(text))

	var root := _resolve_root(root_spec)
	if root == null:
		return null

	if typeof(selector) == TYPE_DICTIONARY and selector.has("path"):
		var path := String(selector["path"])
		if path.begins_with("/"):
			return get_node_or_null(NodePath(path))
		if root.has_node(NodePath(path)):
			return root.get_node(NodePath(path))

	if typeof(selector) == TYPE_STRING:
		var string_selector := String(selector)
		if root.has_node(NodePath(string_selector)):
			return root.get_node(NodePath(string_selector))

	var nodes := _find_nodes(selector, root, 1)
	if nodes.is_empty():
		return null
	return nodes[0]


func _find_nodes(selector: Variant, root: Node, limit: int) -> Array:
	var found := []
	_visit_find(root, selector, found, limit)
	return found


func _visit_find(node: Node, selector: Variant, found: Array, limit: int) -> void:
	if limit > 0 and found.size() >= limit:
		return
	if _matches_selector(node, selector):
		found.append(node)
	for child in node.get_children():
		if child is Node:
			_visit_find(child, selector, found, limit)


func _matches_selector(node: Node, selector: Variant) -> bool:
	if typeof(selector) == TYPE_DICTIONARY:
		if selector.has("all") and not _selector_list_matches_all(node, selector["all"]):
			return false
		if selector.has("and") and not _selector_list_matches_all(node, selector["and"]):
			return false
		if selector.has("any") and not _selector_list_matches_any(node, selector["any"]):
			return false
		if selector.has("or") and not _selector_list_matches_any(node, selector["or"]):
			return false
		if selector.has("not") and _matches_selector(node, selector["not"]):
			return false
		if selector.has("base") and not _matches_selector(node, selector["base"]):
			return false
		if selector.has("name") and node.name != String(selector["name"]):
			return false
		if selector.has("role") and not _node_role_matches(node, String(selector["role"])):
			return false
		if selector.has("role_name") and not _node_accessible_name_matches(node, selector["role_name"]):
			return false
		if selector.has("name_contains") and not _node_accessible_name_contains(node, selector["name_contains"]):
			return false
		if selector.has("test_id") and not _node_metadata_matches(node, "test_id", selector["test_id"]):
			return false
		if selector.has("testid") and not _node_metadata_matches(node, "test_id", selector["testid"]):
			return false
		if selector.has("type") and not node.is_class(String(selector["type"])):
			return false
		if selector.has("class") and not node.is_class(String(selector["class"])):
			return false
		if selector.has("group") and not node.is_in_group(String(selector["group"])):
			return false
		if selector.has("path") and str(node.get_path()) != String(selector["path"]):
			return false
		if selector.has("text") and not _node_property_matches(node, "text", selector["text"]):
			return false
		if selector.has("text_contains") and not _node_property_contains(node, "text", selector["text_contains"]):
			return false
		if selector.has("placeholder") and not _node_property_matches(node, "placeholder_text", selector["placeholder"]):
			return false
		if selector.has("placeholder_contains") and not _node_property_contains(node, "placeholder_text", selector["placeholder_contains"]):
			return false
		if selector.has("property"):
			var property_name := String(selector["property"])
			if selector.has("value") and not _node_property_matches(node, property_name, selector["value"]):
				return false
			if selector.has("contains") and not _node_property_contains(node, property_name, selector["contains"]):
				return false
			if not selector.has("value") and not selector.has("contains") and not _node_has_property(node, property_name):
				return false
		if selector.has("properties"):
			var expected_properties = selector["properties"]
			if typeof(expected_properties) != TYPE_DICTIONARY:
				return false
			for property_name in expected_properties.keys():
				if not _node_property_matches(node, String(property_name), expected_properties[property_name]):
					return false
		if selector.has("metadata") or selector.has("meta"):
			var expected_metadata = selector.get("metadata", selector.get("meta", {}))
			if typeof(expected_metadata) != TYPE_DICTIONARY:
				return false
			for metadata_name in expected_metadata.keys():
				if not _node_metadata_matches(node, String(metadata_name), expected_metadata[metadata_name]):
					return false
		if selector.has("has_text") and not _node_or_descendants_text_contains(node, selector["has_text"]):
			return false
		if selector.has("has_text_exact") and not _node_or_descendants_text_matches(node, selector["has_text_exact"]):
			return false
		if selector.has("has_not_text") and _node_or_descendants_text_contains(node, selector["has_not_text"]):
			return false
		if selector.has("has") and not _node_descendants_match(node, selector["has"]):
			return false
		if selector.has("has_not") and _node_descendants_match(node, selector["has_not"]):
			return false
		return true

	if typeof(selector) != TYPE_STRING:
		return false
	var text := String(selector)
	if text == "":
		return false
	if text.begins_with("#"):
		return node.name == text.substr(1)
	if text.begins_with("."):
		return node.is_in_group(text.substr(1))
	if text.begins_with("type="):
		return node.is_class(text.substr(5))
	if text.begins_with("class="):
		return node.is_class(text.substr(6))
	if text.begins_with("name="):
		return node.name == text.substr(5)
	if text.begins_with("role="):
		return _node_role_matches(node, text.substr(5))
	if text.begins_with("test_id="):
		return _node_metadata_matches(node, "test_id", text.substr(8))
	if text.begins_with("testid="):
		return _node_metadata_matches(node, "test_id", text.substr(7))
	if text.begins_with("path="):
		return str(node.get_path()) == text.substr(5)
	if text.begins_with("text="):
		return _node_property_matches(node, "text", text.substr(5))
	if text.begins_with("text*="):
		return _node_property_contains(node, "text", text.substr(6))
	if text.begins_with("placeholder="):
		return _node_property_matches(node, "placeholder_text", text.substr(12))
	if text.begins_with("placeholder*="):
		return _node_property_contains(node, "placeholder_text", text.substr(13))
	if text.begins_with("tooltip="):
		return _node_property_matches(node, "tooltip_text", text.substr(8))
	if text.begins_with("tooltip*="):
		return _node_property_contains(node, "tooltip_text", text.substr(9))
	return node.name == text or node.is_class(text)


func _selector_list_matches_all(node: Node, selectors: Variant) -> bool:
	if typeof(selectors) != TYPE_ARRAY:
		return false
	for inner_selector in selectors:
		if not _matches_selector(node, inner_selector):
			return false
	return true


func _selector_list_matches_any(node: Node, selectors: Variant) -> bool:
	if typeof(selectors) != TYPE_ARRAY:
		return false
	for inner_selector in selectors:
		if _matches_selector(node, inner_selector):
			return true
	return false


func _node_role_matches(node: Node, expected_role: String) -> bool:
	var expected := _normalize_role(expected_role)
	var actual := _node_role(node)
	if actual == expected:
		return true
	if expected == "label" and actual == "text":
		return true
	if expected == "text-box" and actual == "textbox":
		return true
	if expected == "menuitem" and actual == "menu-item":
		return true
	return false


func _normalize_role(role: String) -> String:
	return role.strip_edges().to_lower().replace("_", "-")


func _node_role(node: Node) -> String:
	if node is CheckBox or node is CheckButton:
		return "checkbox"
	if node is PopupMenu:
		return "menu"
	if node is OptionButton:
		return "combobox"
	if node is MenuButton:
		return "button"
	if node is BaseButton:
		return "button"
	if node is LineEdit or node is TextEdit:
		return "textbox"
	if node is RichTextLabel or node is Label:
		return "text"
	if node is Slider:
		return "slider"
	if node is SpinBox:
		return "spinbutton"
	if node is ProgressBar:
		return "progressbar"
	if node is ItemList or node is Tree:
		return "list"
	if node is TabBar:
		return "tablist"
	if node is TabContainer:
		return "tabpanel"
	if node is Window:
		return "window"
	if node is Panel or node is PanelContainer:
		return "panel"
	if node is Control:
		return "control"
	return node.get_class().to_lower()


func _node_accessible_name_matches(node: Node, expected: Variant) -> bool:
	for candidate in _node_accessible_names(node):
		if _encoded_values_equal(candidate, expected):
			return true
	return false


func _node_accessible_name_contains(node: Node, expected: Variant) -> bool:
	var needle := String(expected)
	for candidate in _node_accessible_names(node):
		if String(candidate).contains(needle):
			return true
	return false


func _node_accessible_names(node: Node) -> Array:
	var names := []
	for property_name in ["text", "placeholder_text", "tooltip_text"]:
		if _node_has_property(node, property_name):
			var value = _encode_value(node.get(property_name))
			if String(value) != "":
				names.append(value)
	names.append(node.name)
	return names


func _node_or_descendants_text_matches(node: Node, expected: Variant) -> bool:
	if _node_accessible_name_matches(node, expected):
		return true
	for child in node.get_children():
		if child is Node and _node_or_descendants_text_matches(child, expected):
			return true
	return false


func _node_or_descendants_text_contains(node: Node, expected: Variant) -> bool:
	if _node_accessible_name_contains(node, expected):
		return true
	for child in node.get_children():
		if child is Node and _node_or_descendants_text_contains(child, expected):
			return true
	return false


func _node_descendants_match(node: Node, selector: Variant) -> bool:
	for child in node.get_children():
		if not (child is Node):
			continue
		if _matches_selector(child, selector):
			return true
		if _node_descendants_match(child, selector):
			return true
	return false


func _node_is_checkable(node: Node) -> bool:
	if not (node is BaseButton):
		return false
	if node is CheckBox or node is CheckButton:
		return true
	if _node_has_property(node, "toggle_mode"):
		return bool(node.get("toggle_mode"))
	return false


func _node_checked_property(node: Node) -> String:
	var property_names := _property_name_set(node)
	if property_names.has("button_pressed"):
		return "button_pressed"
	if property_names.has("pressed"):
		return "pressed"
	return ""


func _option_button_find_index(node: OptionButton, spec: Variant) -> int:
	if typeof(spec) == TYPE_DICTIONARY:
		if spec.has("index"):
			return _option_button_valid_index(node, int(spec["index"]))
		if spec.has("id"):
			return _option_button_find_id(node, int(spec["id"]))
		if spec.has("text"):
			return _option_button_find_text(node, String(spec["text"]), false)
		if spec.has("label"):
			return _option_button_find_text(node, String(spec["label"]), false)
		if spec.has("value"):
			return _option_button_find_text(node, String(spec["value"]), false)
		if spec.has("text_contains"):
			return _option_button_find_text(node, String(spec["text_contains"]), true)
		return -1
	if typeof(spec) == TYPE_INT or typeof(spec) == TYPE_FLOAT:
		return _option_button_valid_index(node, int(spec))
	return _option_button_find_text(node, String(spec), false)


func _option_button_valid_index(node: OptionButton, index: int) -> int:
	if index < 0 or index >= node.get_item_count():
		return -1
	return index


func _option_button_find_id(node: OptionButton, id: int) -> int:
	for index in range(node.get_item_count()):
		if node.get_item_id(index) == id:
			return index
	return -1


func _option_button_find_text(node: OptionButton, text: String, contains: bool) -> int:
	for index in range(node.get_item_count()):
		var item_text := node.get_item_text(index)
		if contains and item_text.contains(text):
			return index
		if not contains and item_text == text:
			return index
	return -1


func _option_button_selection(node: OptionButton) -> Dictionary:
	var index := node.get_selected()
	var selection := {
		"index": index,
		"id": null,
		"text": "",
	}
	if index >= 0 and index < node.get_item_count():
		selection["id"] = node.get_item_id(index)
		selection["text"] = node.get_item_text(index)
	return selection


func _tab_find_index(node: Node, spec: Variant) -> int:
	if typeof(spec) == TYPE_DICTIONARY:
		if spec.has("index"):
			return _tab_valid_index(node, int(spec["index"]))
		if spec.has("metadata"):
			return _tab_find_metadata(node, spec["metadata"])
		if spec.has("meta"):
			return _tab_find_metadata(node, spec["meta"])
		if spec.has("title"):
			return _tab_find_text(node, String(spec["title"]), false)
		if spec.has("text"):
			return _tab_find_text(node, String(spec["text"]), false)
		if spec.has("label"):
			return _tab_find_text(node, String(spec["label"]), false)
		if spec.has("value"):
			return _tab_find_text(node, String(spec["value"]), false)
		if spec.has("title_contains"):
			return _tab_find_text(node, String(spec["title_contains"]), true)
		if spec.has("text_contains"):
			return _tab_find_text(node, String(spec["text_contains"]), true)
		return -1
	if typeof(spec) == TYPE_INT or typeof(spec) == TYPE_FLOAT:
		return _tab_valid_index(node, int(spec))
	return _tab_find_text(node, String(spec), false)


func _tab_valid_index(node: Node, index: int) -> int:
	if not _tab_index_in_bounds(node, index):
		return -1
	if _tab_is_disabled(node, index) or _tab_is_hidden(node, index):
		return -1
	return index


func _tab_index_in_bounds(node: Node, index: int) -> bool:
	return index >= 0 and index < _tab_count(node)


func _tab_find_text(node: Node, text: String, contains: bool) -> int:
	for index in range(_tab_count(node)):
		if _tab_valid_index(node, index) < 0:
			continue
		var tab_text := _tab_title(node, index)
		if contains and tab_text.contains(text):
			return index
		if not contains and tab_text == text:
			return index
	return -1


func _tab_find_metadata(node: Node, expected: Variant) -> int:
	for index in range(_tab_count(node)):
		if _tab_valid_index(node, index) < 0:
			continue
		if _encoded_values_equal(_encode_value(_tab_metadata(node, index)), expected):
			return index
	return -1


func _tab_selection(node: Node) -> Dictionary:
	var index := _tab_current(node)
	var selection := {
		"index": index,
		"text": "",
		"title": "",
		"metadata": null,
		"disabled": false,
		"hidden": false,
		"control": null,
	}
	if _tab_index_in_bounds(node, index):
		var title := _tab_title(node, index)
		selection["text"] = title
		selection["title"] = title
		selection["metadata"] = _encode_value(_tab_metadata(node, index))
		selection["disabled"] = _tab_is_disabled(node, index)
		selection["hidden"] = _tab_is_hidden(node, index)
		var control := _tab_control(node, index)
		if control != null:
			selection["control"] = _node_summary(control)
	return selection


func _tab_count(node: Node) -> int:
	if node is TabBar:
		return (node as TabBar).get_tab_count()
	if node is TabContainer:
		return (node as TabContainer).get_tab_count()
	return 0


func _tab_current(node: Node) -> int:
	if node is TabBar:
		return (node as TabBar).current_tab
	if node is TabContainer:
		return (node as TabContainer).current_tab
	return -1


func _tab_set_current(node: Node, index: int) -> void:
	if node is TabBar:
		(node as TabBar).current_tab = index
	elif node is TabContainer:
		(node as TabContainer).current_tab = index


func _tab_title(node: Node, index: int) -> String:
	if node is TabBar:
		return (node as TabBar).get_tab_title(index)
	if node is TabContainer:
		return (node as TabContainer).get_tab_title(index)
	return ""


func _tab_metadata(node: Node, index: int) -> Variant:
	if node is TabBar:
		return (node as TabBar).get_tab_metadata(index)
	if node is TabContainer:
		return (node as TabContainer).get_tab_metadata(index)
	return null


func _tab_is_disabled(node: Node, index: int) -> bool:
	if node is TabBar:
		return (node as TabBar).is_tab_disabled(index)
	if node is TabContainer:
		return (node as TabContainer).is_tab_disabled(index)
	return false


func _tab_is_hidden(node: Node, index: int) -> bool:
	if node is TabBar:
		return (node as TabBar).is_tab_hidden(index)
	if node is TabContainer:
		return (node as TabContainer).is_tab_hidden(index)
	return false


func _tab_control(node: Node, index: int) -> Node:
	if node is TabContainer:
		return (node as TabContainer).get_tab_control(index)
	return null


func _popup_menu_from_node(node: Node) -> PopupMenu:
	if node is PopupMenu:
		return node as PopupMenu
	if node is MenuButton:
		return (node as MenuButton).get_popup()
	return null


func _popup_menu_items(node: PopupMenu) -> Array:
	var items := []
	for index in range(node.get_item_count()):
		items.append(_popup_menu_item(node, index))
	return items


func _popup_menu_focused_item(node: PopupMenu) -> Variant:
	var focused_index := node.get_focused_item()
	if focused_index < 0 or focused_index >= node.get_item_count():
		return null
	return _popup_menu_item(node, focused_index)


func _popup_menu_item(node: PopupMenu, index: int) -> Dictionary:
	return {
		"index": index,
		"id": node.get_item_id(index),
		"text": node.get_item_text(index),
		"metadata": _encode_value(node.get_item_metadata(index)),
		"disabled": node.is_item_disabled(index),
		"separator": _popup_menu_is_item_separator(node, index),
		"checkable": node.is_item_checkable(index),
		"radio_checkable": node.is_item_radio_checkable(index),
		"checked": node.is_item_checked(index),
	}


func _popup_menu_find_index(node: PopupMenu, spec: Variant) -> int:
	if typeof(spec) == TYPE_DICTIONARY:
		if spec.has("index"):
			return _popup_menu_valid_index(node, int(spec["index"]))
		if spec.has("id"):
			return _popup_menu_find_id(node, int(spec["id"]))
		if spec.has("metadata"):
			return _popup_menu_find_metadata(node, spec["metadata"])
		if spec.has("meta"):
			return _popup_menu_find_metadata(node, spec["meta"])
		if spec.has("text"):
			return _popup_menu_find_text(node, String(spec["text"]), false)
		if spec.has("label"):
			return _popup_menu_find_text(node, String(spec["label"]), false)
		if spec.has("value"):
			return _popup_menu_find_text(node, String(spec["value"]), false)
		if spec.has("text_contains"):
			return _popup_menu_find_text(node, String(spec["text_contains"]), true)
		return -1
	if typeof(spec) == TYPE_INT or typeof(spec) == TYPE_FLOAT:
		return _popup_menu_valid_index(node, int(spec))
	return _popup_menu_find_text(node, String(spec), false)


func _popup_menu_valid_index(node: PopupMenu, index: int) -> int:
	if index < 0 or index >= node.get_item_count():
		return -1
	if node.is_item_disabled(index) or _popup_menu_is_item_separator(node, index):
		return -1
	return index


func _popup_menu_find_id(node: PopupMenu, id: int) -> int:
	for index in range(node.get_item_count()):
		if _popup_menu_valid_index(node, index) < 0:
			continue
		if node.get_item_id(index) == id:
			return index
	return -1


func _popup_menu_find_text(node: PopupMenu, text: String, contains: bool) -> int:
	for index in range(node.get_item_count()):
		if _popup_menu_valid_index(node, index) < 0:
			continue
		var item_text := node.get_item_text(index)
		if contains and item_text.contains(text):
			return index
		if not contains and item_text == text:
			return index
	return -1


func _popup_menu_find_metadata(node: PopupMenu, expected: Variant) -> int:
	for index in range(node.get_item_count()):
		if _popup_menu_valid_index(node, index) < 0:
			continue
		if _encoded_values_equal(_encode_value(node.get_item_metadata(index)), expected):
			return index
	return -1


func _popup_menu_is_item_separator(node: PopupMenu, index: int) -> bool:
	if node.has_method("is_item_separator"):
		return bool(node.call("is_item_separator", index))
	return false


func _dialog_from_node(node: Node) -> AcceptDialog:
	if node is AcceptDialog:
		return node as AcceptDialog
	return null


func _dialog_summary(dialog: AcceptDialog) -> Dictionary:
	return {
		"path": str(dialog.get_path()),
		"node": _node_summary(dialog),
		"title": dialog.title,
		"text": dialog.get_text(),
		"visible": dialog.visible,
		"exclusive": dialog.exclusive,
		"ok_button": _dialog_button_summary(dialog.get_ok_button()),
		"cancel_button": _dialog_button_summary(dialog.call("get_cancel_button") if dialog.has_method("get_cancel_button") else null),
	}


func _dialog_button_summary(button: Variant) -> Variant:
	if not (button is BaseButton):
		return null
	var base_button := button as BaseButton
	return {
		"name": base_button.name,
		"path": str(base_button.get_path()),
		"text": base_button.text,
		"disabled": base_button.disabled,
		"visible": base_button.visible,
	}


func _item_list_find_indices(node: ItemList, spec: Variant) -> Array:
	if typeof(spec) == TYPE_ARRAY:
		var indices := []
		for item_spec in spec:
			var index := _item_list_find_index(node, item_spec)
			if index < 0:
				return []
			if not indices.has(index):
				indices.append(index)
		return indices
	var index := _item_list_find_index(node, spec)
	if index < 0:
		return []
	return [index]


func _item_list_find_index(node: ItemList, spec: Variant) -> int:
	if typeof(spec) == TYPE_DICTIONARY:
		if spec.has("index"):
			return _item_list_valid_index(node, int(spec["index"]))
		if spec.has("metadata"):
			return _item_list_find_metadata(node, spec["metadata"])
		if spec.has("meta"):
			return _item_list_find_metadata(node, spec["meta"])
		if spec.has("text"):
			return _item_list_find_text(node, String(spec["text"]), false)
		if spec.has("label"):
			return _item_list_find_text(node, String(spec["label"]), false)
		if spec.has("value"):
			return _item_list_find_text(node, String(spec["value"]), false)
		if spec.has("text_contains"):
			return _item_list_find_text(node, String(spec["text_contains"]), true)
		return -1
	if typeof(spec) == TYPE_INT or typeof(spec) == TYPE_FLOAT:
		return _item_list_valid_index(node, int(spec))
	return _item_list_find_text(node, String(spec), false)


func _item_list_valid_index(node: ItemList, index: int) -> int:
	if index < 0 or index >= node.get_item_count():
		return -1
	if node.is_item_disabled(index) or not node.is_item_selectable(index):
		return -1
	return index


func _item_list_find_text(node: ItemList, text: String, contains: bool) -> int:
	for index in range(node.get_item_count()):
		if _item_list_valid_index(node, index) < 0:
			continue
		var item_text := node.get_item_text(index)
		if contains and item_text.contains(text):
			return index
		if not contains and item_text == text:
			return index
	return -1


func _item_list_find_metadata(node: ItemList, expected: Variant) -> int:
	for index in range(node.get_item_count()):
		if _item_list_valid_index(node, index) < 0:
			continue
		if _encoded_values_equal(_encode_value(node.get_item_metadata(index)), expected):
			return index
	return -1


func _item_list_selection(node: ItemList) -> Dictionary:
	var selected_indices := []
	var texts := []
	var items := []
	for selected_index in node.get_selected_items():
		var index := int(selected_index)
		selected_indices.append(index)
		var item := _item_list_item(node, index)
		items.append(item)
		texts.append(item.get("text", ""))
	var value = null
	if texts.size() == 1:
		value = texts[0]
	elif texts.size() > 1:
		value = texts
	return {
		"indices": selected_indices,
		"texts": texts,
		"items": items,
		"value": value,
	}


func _item_list_item(node: ItemList, index: int) -> Dictionary:
	return {
		"index": index,
		"text": node.get_item_text(index),
		"metadata": _encode_value(node.get_item_metadata(index)),
		"disabled": node.is_item_disabled(index),
		"selectable": node.is_item_selectable(index),
	}


func _index_set(indices: Variant) -> Dictionary:
	var index_set := {}
	if typeof(indices) != TYPE_ARRAY:
		return index_set
	for index in indices:
		index_set[int(index)] = true
	return index_set


func _emit_item_list_selection_signals(node: ItemList, previous_indices: Dictionary, selected_indices: Dictionary) -> void:
	if node.select_mode == ItemList.SELECT_MULTI:
		for index in previous_indices.keys():
			if not selected_indices.has(index) and node.has_signal("multi_selected"):
				node.emit_signal("multi_selected", int(index), false)
	for index in selected_indices.keys():
		if previous_indices.has(index):
			continue
		if node.select_mode == ItemList.SELECT_MULTI and node.has_signal("multi_selected"):
			node.emit_signal("multi_selected", int(index), true)
		elif node.has_signal("item_selected"):
			node.emit_signal("item_selected", int(index))


func _tree_find_entries(tree: Tree, spec: Variant) -> Array:
	if typeof(spec) == TYPE_ARRAY:
		var entries := []
		var seen := {}
		for item_spec in spec:
			var entry := _tree_find_entry(tree, item_spec)
			if entry.is_empty():
				return []
			var key := _tree_item_key(tree, entry["item"], int(entry["column"]))
			if not seen.has(key):
				entries.append(entry)
				seen[key] = true
		return entries
	var entry := _tree_find_entry(tree, spec)
	if entry.is_empty():
		return []
	return [entry]


func _tree_find_entry(tree: Tree, spec: Variant) -> Dictionary:
	if typeof(spec) == TYPE_DICTIONARY:
		var column := int(spec.get("column", 0))
		if spec.has("index"):
			return _tree_find_flat_index(tree, int(spec["index"]), column)
		if spec.has("index_path"):
			return _tree_find_index_path(tree, spec["index_path"], column)
		if spec.has("path"):
			return _tree_find_path(tree, spec["path"], column)
		if spec.has("metadata"):
			return _tree_find_metadata(tree, spec["metadata"], column)
		if spec.has("meta"):
			return _tree_find_metadata(tree, spec["meta"], column)
		if spec.has("text"):
			return _tree_find_text(tree, String(spec["text"]), column, false)
		if spec.has("label"):
			return _tree_find_text(tree, String(spec["label"]), column, false)
		if spec.has("value"):
			return _tree_find_text(tree, String(spec["value"]), column, false)
		if spec.has("text_contains"):
			return _tree_find_text(tree, String(spec["text_contains"]), column, true)
		return {}
	if typeof(spec) == TYPE_INT or typeof(spec) == TYPE_FLOAT:
		return _tree_find_flat_index(tree, int(spec), 0)
	return _tree_find_text(tree, String(spec), 0, false)


func _tree_find_flat_index(tree: Tree, wanted_index: int, column: int) -> Dictionary:
	if wanted_index < 0:
		return {}
	var selectable_index := 0
	for item in _tree_items(tree):
		var tree_item := item as TreeItem
		if not _tree_item_can_select(tree_item, column):
			continue
		if selectable_index == wanted_index:
			return {"item": tree_item, "column": column}
		selectable_index += 1
	return {}


func _tree_find_index_path(tree: Tree, index_path: Variant, column: int) -> Dictionary:
	if typeof(index_path) != TYPE_ARRAY:
		return {}
	var item := tree.get_root()
	if item == null:
		return {}
	if tree.is_root_hidden():
		item = _tree_child_at(item, int(index_path[0])) if index_path.size() > 0 else null
		for depth in range(1, index_path.size()):
			item = _tree_child_at(item, int(index_path[depth])) if item != null else null
	else:
		for depth in range(index_path.size()):
			item = _tree_child_at(item, int(index_path[depth])) if item != null else null
	if item == null or not _tree_item_can_select(item, column):
		return {}
	return {"item": item, "column": column}


func _tree_find_path(tree: Tree, path: Variant, column: int) -> Dictionary:
	if typeof(path) != TYPE_ARRAY:
		return {}
	var expected_path := []
	for value in path:
		expected_path.append(String(value))
	if expected_path.is_empty():
		return {}
	for item in _tree_items(tree):
		var tree_item := item as TreeItem
		if not _tree_item_can_select(tree_item, column):
			continue
		if _string_array_ends_with(_tree_item_text_path(tree, tree_item, column), expected_path):
			return {"item": tree_item, "column": column}
	return {}


func _tree_find_text(tree: Tree, text: String, column: int, contains: bool) -> Dictionary:
	for item in _tree_items(tree):
		var tree_item := item as TreeItem
		if not _tree_item_can_select(tree_item, column):
			continue
		var item_text := tree_item.get_text(column)
		if contains and item_text.contains(text):
			return {"item": tree_item, "column": column}
		if not contains and item_text == text:
			return {"item": tree_item, "column": column}
	return {}


func _tree_find_metadata(tree: Tree, expected: Variant, column: int) -> Dictionary:
	for item in _tree_items(tree):
		var tree_item := item as TreeItem
		if not _tree_item_can_select(tree_item, column):
			continue
		if _encoded_values_equal(_encode_value(tree_item.get_metadata(column)), expected):
			return {"item": tree_item, "column": column}
	return {}


func _tree_items(tree: Tree) -> Array:
	var root_item := tree.get_root()
	if root_item == null:
		return []
	var items := []
	if tree.is_root_hidden():
		for child in root_item.get_children():
			_tree_append_items(child, items)
	else:
		_tree_append_items(root_item, items)
	return items


func _tree_append_items(item: TreeItem, items: Array) -> void:
	if item == null:
		return
	items.append(item)
	for child in item.get_children():
		_tree_append_items(child, items)


func _tree_child_at(item: TreeItem, child_index: int) -> TreeItem:
	if item == null or child_index < 0:
		return null
	var children := item.get_children()
	if child_index >= children.size():
		return null
	return children[child_index]


func _tree_item_can_select(item: TreeItem, column: int) -> bool:
	return item != null and item.is_visible_in_tree() and item.is_selectable(column)


func _tree_selection(tree: Tree) -> Dictionary:
	var entries := []
	var texts := []
	var keys := []
	var item := tree.get_next_selected(null)
	while item != null:
		for column in range(tree.get_columns()):
			if item.is_selected(column):
				var entry := _tree_item_entry(tree, item, column)
				entries.append(entry)
				texts.append(entry.get("text", ""))
				keys.append(_tree_item_key(tree, item, column))
		item = tree.get_next_selected(item)
	var value = null
	if texts.size() == 1:
		value = texts[0]
	elif texts.size() > 1:
		value = texts
	return {
		"items": entries,
		"texts": texts,
		"keys": keys,
		"value": value,
	}


func _tree_selection_public(selection: Dictionary) -> Dictionary:
	return {
		"items": selection.get("items", []),
		"texts": selection.get("texts", []),
		"value": selection.get("value", null),
	}


func _tree_item_entry(tree: Tree, item: TreeItem, column: int) -> Dictionary:
	return {
		"column": column,
		"text": item.get_text(column),
		"path": _tree_item_text_path(tree, item, column),
		"index_path": _tree_item_index_path(tree, item),
		"metadata": _encode_value(item.get_metadata(column)),
		"selected": item.is_selected(column),
		"selectable": item.is_selectable(column),
		"visible": item.is_visible(),
		"visible_in_tree": item.is_visible_in_tree(),
		"collapsed": item.is_collapsed(),
	}


func _tree_item_text_path(tree: Tree, item: TreeItem, column: int) -> Array:
	var path := []
	var current := item
	while current != null:
		if current != tree.get_root() or not tree.is_root_hidden():
			path.push_front(current.get_text(column))
		current = current.get_parent()
	return path


func _tree_item_index_path(tree: Tree, item: TreeItem) -> Array:
	var path := []
	var current := item
	while current != null:
		if current != tree.get_root() or not tree.is_root_hidden():
			path.push_front(current.get_index())
		current = current.get_parent()
	return path


func _tree_item_key(tree: Tree, item: TreeItem, column: int) -> String:
	return "%s:%s" % [JSON.stringify(_tree_item_index_path(tree, item)), column]


func _tree_selection_key_set(selection: Dictionary) -> Dictionary:
	var key_set := {}
	for key in selection.get("keys", []):
		key_set[String(key)] = true
	return key_set


func _emit_tree_multi_selection_signals(tree: Tree, previous: Dictionary, selected: Dictionary) -> void:
	var previous_keys := _tree_selection_key_set(previous)
	var selected_keys := _tree_selection_key_set(selected)
	for selection in previous.get("items", []):
		var key := "%s:%s" % [JSON.stringify(selection.get("index_path", [])), int(selection.get("column", 0))]
		if previous_keys.has(key) and not selected_keys.has(key):
			var item := _tree_find_by_index_path(tree, selection.get("index_path", []))
			if item != null and tree.has_signal("multi_selected"):
				tree.emit_signal("multi_selected", item, int(selection.get("column", 0)), false)
	for selection in selected.get("items", []):
		var key := "%s:%s" % [JSON.stringify(selection.get("index_path", [])), int(selection.get("column", 0))]
		if not previous_keys.has(key) and selected_keys.has(key):
			var item := _tree_find_by_index_path(tree, selection.get("index_path", []))
			if item != null and tree.has_signal("multi_selected"):
				tree.emit_signal("multi_selected", item, int(selection.get("column", 0)), true)


func _tree_find_by_index_path(tree: Tree, index_path: Variant) -> TreeItem:
	if typeof(index_path) != TYPE_ARRAY:
		return null
	var item := tree.get_root()
	if item == null:
		return null
	for depth in range(index_path.size()):
		if tree.is_root_hidden() or depth > 0:
			item = _tree_child_at(item, int(index_path[depth])) if item != null else null
		else:
			if int(index_path[depth]) != item.get_index():
				return null
	return item


func _string_array_ends_with(actual: Array, expected_suffix: Array) -> bool:
	if expected_suffix.size() > actual.size():
		return false
	var start := actual.size() - expected_suffix.size()
	for index in range(expected_suffix.size()):
		if String(actual[start + index]) != String(expected_suffix[index]):
			return false
	return true


func _node_has_property(node: Node, property_name: String) -> bool:
	return _property_name_set(node).has(property_name)


func _node_property_matches(node: Node, property_name: String, expected: Variant) -> bool:
	if not _node_has_property(node, property_name):
		return false
	return _encoded_values_equal(_encode_value(node.get(property_name)), expected)


func _node_property_contains(node: Node, property_name: String, expected: Variant) -> bool:
	if not _node_has_property(node, property_name):
		return false
	return String(_encode_value(node.get(property_name))).contains(String(expected))


func _node_metadata_matches(node: Node, metadata_name: String, expected: Variant) -> bool:
	if not node.has_meta(metadata_name):
		return false
	return _encoded_values_equal(_encode_value(node.get_meta(metadata_name)), expected)


func _encoded_values_equal(actual: Variant, expected: Variant) -> bool:
	if typeof(actual) == TYPE_DICTIONARY and typeof(expected) == TYPE_DICTIONARY:
		for key in expected.keys():
			if not actual.has(key):
				return false
			if not _encoded_values_equal(actual[key], expected[key]):
				return false
		return true
	if typeof(actual) == TYPE_ARRAY and typeof(expected) == TYPE_ARRAY:
		if actual.size() != expected.size():
			return false
		for index in range(actual.size()):
			if not _encoded_values_equal(actual[index], expected[index]):
				return false
		return true
	return actual == expected


func _snapshot_node(node: Node, depth: int, max_depth: int, include_properties: bool) -> Dictionary:
	var data := _node_summary(node)
	if include_properties:
		data["properties"] = _selected_properties(node)
	var children := []
	if depth < max_depth:
		for child in node.get_children():
			if child is Node:
				children.append(_snapshot_node(child, depth + 1, max_depth, include_properties))
	data["children"] = children
	return data


func _node_summary(node: Node) -> Dictionary:
	var parent := node.get_parent()
	return {
		"name": node.name,
		"class": node.get_class(),
		"path": str(node.get_path()),
		"parent": "" if parent == null else str(parent.get_path()),
		"index": node.get_index(true),
		"groups": _node_group_names(node),
		"owner": "" if node.owner == null else str(node.owner.get_path()),
		"child_count": node.get_child_count(),
	}


func _node_metadata_summary(node: Node) -> Dictionary:
	var metadata := {}
	for metadata_name in node.get_meta_list():
		metadata[String(metadata_name)] = _encode_value(node.get_meta(StringName(metadata_name)))
	return metadata


func _node_metadata_values(node: Node, names: Array) -> Dictionary:
	var metadata := {}
	for name in names:
		var metadata_name := String(name)
		if node.has_meta(metadata_name):
			metadata[metadata_name] = _encode_value(node.get_meta(StringName(metadata_name)))
	return metadata


func _node_metadata_previous(node: Node, names: Array) -> Dictionary:
	var previous := {}
	for name in names:
		var metadata_name := String(name)
		var exists := node.has_meta(metadata_name)
		previous[metadata_name] = {
			"exists": exists,
			"value": node.get_meta(StringName(metadata_name)) if exists else null,
		}
	return previous


func _apply_node_metadata(node: Node, values: Dictionary) -> void:
	for name in values.keys():
		node.set_meta(StringName(String(name)), values[name])


func _remove_node_metadata(node: Node, names: Array) -> void:
	for name in names:
		var metadata_name := StringName(String(name))
		if node.has_meta(metadata_name):
			node.remove_meta(metadata_name)


func _node_group_names(node: Node, include_internal: bool = false) -> Array:
	var groups := []
	for group_name in node.get_groups():
		var name := String(group_name)
		if not include_internal and name.begins_with("_"):
			continue
		groups.append(name)
	groups.sort()
	return groups


func _node_state(node: Node) -> Dictionary:
	var property_names := _property_name_set(node)
	var visible := true
	var visible_in_tree := true
	if node is CanvasItem:
		visible = node.visible
		visible_in_tree = node.is_visible_in_tree()
	elif node is Window:
		visible = (node as Window).visible
		visible_in_tree = visible

	var bounds := _node_bounds(node)
	var has_bounds := not bounds.is_empty()
	var enabled := true
	if property_names.has("disabled"):
		enabled = not bool(node.get("disabled"))

	var focusable := false
	var focused := false
	var receives_input := visible_in_tree and has_bounds
	if node is Control:
		focused = node.has_focus()
		focusable = node.focus_mode != Control.FOCUS_NONE
		receives_input = receives_input and node.mouse_filter != Control.MOUSE_FILTER_IGNORE

	var editable := false
	if property_names.has("editable"):
		editable = bool(node.get("editable")) and enabled
	elif node is LineEdit or node is TextEdit:
		editable = enabled

	var value = null
	if node is LineEdit or node is TextEdit:
		value = _encode_value(node.get("text"))
	elif node is OptionButton:
		value = _option_button_selection(node).get("text", "")
	elif node is TabBar or node is TabContainer:
		value = _tab_selection(node).get("text", "")
	elif node is ItemList:
		value = _item_list_selection(node).get("value", null)
	elif node is Tree:
		value = _tree_selection(node).get("value", null)
	elif node is PopupMenu:
		var focused_item = _popup_menu_focused_item(node)
		if focused_item != null:
			value = focused_item.get("text", "")
	elif property_names.has("value"):
		value = _encode_value(node.get("value"))

	var text = null
	if property_names.has("text"):
		text = _encode_value(node.get("text"))

	var checked = null
	if property_names.has("button_pressed"):
		checked = _encode_value(node.get("button_pressed"))
	elif property_names.has("pressed"):
		checked = _encode_value(node.get("pressed"))

	var actionable := visible_in_tree and enabled and has_bounds and receives_input
	return {
		"node": _node_summary(node),
		"visible": visible,
		"visible_in_tree": visible_in_tree,
		"enabled": enabled,
		"disabled": not enabled,
		"editable": editable,
		"focused": focused,
		"focusable": focusable,
		"has_bounds": has_bounds,
		"receives_input": receives_input,
		"actionable": actionable,
		"text": text,
		"value": value,
		"checked": checked,
	}


func _node_details(node: Node) -> Dictionary:
	var details := _node_summary(node)
	details["properties"] = _selected_properties(node)
	details["methods"] = _public_method_names(node)
	details["signals"] = _public_signal_names(node)
	var popup_menu := _popup_menu_from_node(node)
	if popup_menu != null:
		details["menu_items"] = _popup_menu_items(popup_menu)
	var dialog := _dialog_from_node(node)
	if dialog != null:
		details["dialog"] = _dialog_summary(dialog)
	return details


func _selected_properties(node: Node) -> Dictionary:
	var names := [
		"name",
		"visible",
		"position",
		"global_position",
		"rotation",
		"scale",
		"text",
		"placeholder_text",
		"disabled",
		"editable",
		"button_pressed",
		"pressed",
		"value",
		"current_tab",
		"tab_count",
		"item_count",
		"select_mode",
		"columns",
		"modulate",
	]
	var values := {}
	var property_names := _property_name_set(node)
	for name in names:
		if property_names.has(name):
			values[name] = _encode_value(node.get(name))
	return values


func _property_names_from_param(raw: Variant) -> Variant:
	var names := []
	if raw == null:
		return names
	var raw_type := typeof(raw)
	if raw_type == TYPE_STRING or raw_type == TYPE_STRING_NAME:
		var single := String(raw)
		if single == "":
			return null
		names.append(single)
		return names
	if raw_type == TYPE_ARRAY or raw_type == TYPE_PACKED_STRING_ARRAY:
		for item in raw:
			var name := String(item)
			if name == "":
				return null
			names.append(name)
		return names
	return null


func _decoded_property_values(values: Dictionary) -> Dictionary:
	var decoded := {}
	for key in values.keys():
		var property := String(key)
		decoded[property] = _decode_value(values[key])
	return decoded


func _raw_node_property_values(node: Node, properties: Array) -> Dictionary:
	var values := {}
	for property in properties:
		values[String(property)] = node.get(String(property))
	return values


func _node_property_values(node: Node, properties: Array) -> Dictionary:
	var values := {}
	for property in properties:
		var name := String(property)
		values[name] = _encode_value(node.get(name))
	return values


func _apply_node_properties(node: Node, values: Dictionary) -> void:
	for property in values.keys():
		node.set(String(property), values[property])


func _property_name_set(object: Object) -> Dictionary:
	var property_names := {}
	for info in object.get_property_list():
		property_names[String(info.get("name", ""))] = true
	return property_names


func _public_method_names(object: Object) -> Array:
	var names := []
	for info in object.get_method_list():
		var name := String(info.get("name", ""))
		if not name.begins_with("_"):
			names.append(name)
	return names


func _public_signal_names(object: Object) -> Array:
	var names := []
	for info in object.get_signal_list():
		names.append(String(info.get("name", "")))
	return names


func _encode_value(value: Variant) -> Variant:
	match typeof(value):
		TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_FLOAT, TYPE_STRING:
			return value
		TYPE_STRING_NAME:
			return String(value)
		TYPE_NODE_PATH:
			return {"$type": "NodePath", "path": String(value)}
		TYPE_VECTOR2:
			return {"$type": "Vector2", "x": value.x, "y": value.y}
		TYPE_VECTOR2I:
			return {"$type": "Vector2i", "x": value.x, "y": value.y}
		TYPE_VECTOR3:
			return {"$type": "Vector3", "x": value.x, "y": value.y, "z": value.z}
		TYPE_VECTOR3I:
			return {"$type": "Vector3i", "x": value.x, "y": value.y, "z": value.z}
		TYPE_RECT2:
			return {
				"$type": "Rect2",
				"x": value.position.x,
				"y": value.position.y,
				"width": value.size.x,
				"height": value.size.y,
			}
		TYPE_COLOR:
			return {"$type": "Color", "r": value.r, "g": value.g, "b": value.b, "a": value.a}
		TYPE_ARRAY:
			var array := []
			for item in value:
				array.append(_encode_value(item))
			return array
		TYPE_PACKED_STRING_ARRAY:
			var packed_array := []
			for item in value:
				packed_array.append(String(item))
			return packed_array
		TYPE_DICTIONARY:
			var dictionary := {}
			for key in value.keys():
				dictionary[String(key)] = _encode_value(value[key])
			return dictionary
		TYPE_OBJECT:
			if value == null:
				return null
			if value is Node:
				return {
					"$type": "Node",
					"path": str(value.get_path()),
					"class": value.get_class(),
				}
			if value is Resource:
				var summary := {
					"$type": "Resource",
					"path": value.resource_path,
					"class": value.get_class(),
					"resource_name": value.resource_name,
				}
				return summary
			return {"$type": "Object", "class": value.get_class(), "id": value.get_instance_id()}
	return str(value)


func _decode_value(value: Variant) -> Variant:
	if typeof(value) == TYPE_ARRAY:
		var array := []
		for item in value:
			array.append(_decode_value(item))
		return array
	if typeof(value) != TYPE_DICTIONARY:
		return value
	if not value.has("$type"):
		var dictionary := {}
		for key in value.keys():
			dictionary[key] = _decode_value(value[key])
		return dictionary

	var type_name := String(value.get("$type"))
	match type_name:
		"ResourceRef", "ExtResource":
			var resource_path := String(value.get("path", value.get("resource_path", "")))
			var type_hint := String(value.get("type_hint", value.get("class", "")))
			return ResourceLoader.load(resource_path, type_hint)
		"Resource", "SubResource":
			var resource_path := String(value.get("path", value.get("resource_path", "")))
			if resource_path != "":
				var type_hint := String(value.get("type_hint", value.get("class", "")))
				return ResourceLoader.load(resource_path, type_hint)
			var resource := _instantiate_resource_class(String(value.get("class", value.get("class_name", "Resource"))))
			if resource == null:
				return null
			if value.has("resource_name"):
				resource.resource_name = String(value.get("resource_name", ""))
			var properties = value.get("properties", {})
			if typeof(properties) == TYPE_DICTIONARY:
				for property in properties.keys():
					resource.set(String(property), _decode_value(properties[property]))
			return resource
		"NodePath":
			return NodePath(String(value.get("path", "")))
		"Vector2":
			return Vector2(float(value.get("x", 0.0)), float(value.get("y", 0.0)))
		"Vector2i":
			return Vector2i(int(value.get("x", 0)), int(value.get("y", 0)))
		"Vector3":
			return Vector3(float(value.get("x", 0.0)), float(value.get("y", 0.0)), float(value.get("z", 0.0)))
		"Vector3i":
			return Vector3i(int(value.get("x", 0)), int(value.get("y", 0)), int(value.get("z", 0)))
		"Rect2":
			return Rect2(
				float(value.get("x", 0.0)),
				float(value.get("y", 0.0)),
				float(value.get("width", 0.0)),
				float(value.get("height", 0.0))
			)
		"Color":
			return Color(
				float(value.get("r", 0.0)),
				float(value.get("g", 0.0)),
				float(value.get("b", 0.0)),
				float(value.get("a", 1.0))
			)
	return value
