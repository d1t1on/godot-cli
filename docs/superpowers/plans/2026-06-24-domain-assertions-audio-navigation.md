# Domain-Specific Assertions: Audio + Navigation (Batch 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `expect_audio` and `expect_navigation` assertion fixtures plus 2 new RPCs (`audio.bus.info`, `navigation.query_path`) to the Godot Playwright test runner.

**Architecture:** Hybrid strategy — new RPCs only for server-side computation (AudioServer bus state, NavigationServer path queries); existing `locator().evaluate()` polling for node-scoped state (AudioStreamPlayer, NavigationAgent, NavigationRegion). Mirrors the existing `expect_physics2d`/`expect_physics3d` pattern.

**Tech Stack:** GDScript (Godot 4.6 addon), Python 3.13 (client + runner + tests), unittest framework.

**Spec:** `docs/superpowers/specs/2026-06-24-domain-assertions-audio-navigation-design.md`

---

## File Structure

| File | Responsibility |
| --- | --- |
| `addons/godot_playwright/godot_playwright_server.gd` | Add `_rpc_audio_bus_info` + `_rpc_navigation_query_path` + dispatch entries + trace events |
| `godot_playwright/client.py` | Add `audio_bus_info` + `navigation_query_path` client methods + `wait_for_*` variants + `AudioExpect` + `NavigationExpect` classes + factory functions |
| `godot_playwright/runner.py` | Register `expect_audio` + `expect_navigation` in fixture registry |
| `godot_playwright/codegen.py` | Add replay mappings for `audio.bus.info` + `navigation.query_path` trace events |
| `godot_playwright/__init__.py` | Export `expect_audio` + `expect_navigation` |
| `tests/test_client.py` | Fake server + expectation unit tests |
| `tests/test_codegen.py` | Codegen replay coverage for 2 new events |
| `tests/test_godot_integration.py` | Live Audio + Navigation integration tests |
| `tests/test_runner.py` | Fixture registration verification |
| `README.md` | Audio + Navigation assertion examples |
| `docs/protocol.md` | `audio.bus.info` + `navigation.query_path` documentation |

---

### Task 1: Add `audio.bus.info` RPC to addon server

**Files:**
- Modify: `addons/godot_playwright/godot_playwright_server.gd` (dispatch table ~line 331, RPC method list ~line 677, new method at end of physics section ~line 2270)

- [ ] **Step 1: Add dispatch table entry**

In `addons/godot_playwright/godot_playwright_server.gd`, find the dispatch table that contains `"physics2d.ray":` (around line 331) and add after the `"physics3d.ray"` entry:

```gdscript
	"audio.bus.info":
		return _rpc_audio_bus_info(params),
```

Make sure the syntax matches the surrounding entries exactly (the dispatch table uses a match-style or if-chain — match the existing pattern).

- [ ] **Step 2: Add to RPC method list**

Find the list that contains `"physics2d.ray"` (around line 677) and add `"audio.bus.info",` in alphabetical-ish order near the other non-physics methods, or right after the physics entries.

- [ ] **Step 3: Implement `_rpc_audio_bus_info`**

Add this method after `_rpc_physics3d_ray` (around line 2270):

```gdscript
func _rpc_audio_bus_info(params: Dictionary) -> Dictionary:
	var bus_index := 0
	if params.has("bus_name"):
		var bus_name := String(params["bus_name"])
		bus_index = AudioServer.get_bus_index(bus_name)
		if bus_index < 0:
			return _fail({"errors": ["Unknown bus name: %s" % bus_name]})
	elif params.has("bus_index"):
		bus_index = int(params["bus_index"])
		if bus_index < 0 or bus_index >= AudioServer.get_bus_count():
			return _fail({"errors": ["Invalid bus index: %d" % bus_index]})

	var bus_name := AudioServer.get_bus_name(bus_index)
	var volume_db := AudioServer.get_bus_volume_db(bus_index)
	var muted := AudioServer.is_bus_mute(bus_index)
	var solo := AudioServer.is_bus_solo(bus_index)
	var effect_count := AudioServer.get_bus_effect_count(bus_index)
	var effects: Array = []
	for i in range(effect_count):
		var effect = AudioServer.get_bus_effect(bus_index, i)
		effects.append({
			"index": i,
			"class": effect.get_class() if effect != null else "",
			"enabled": AudioServer.is_bus_effect_enabled(bus_index, i),
			"resource_name": effect.resource_name if effect != null else "",
		})

	var send_target := ""
	if AudioServer.get_bus_send(bus_index) != null:
		send_target = String(AudioServer.get_bus_send(bus_index).get("name", "")) if AudioServer.get_bus_send(bus_index) is Dictionary else str(AudioServer.get_bus_send(bus_index))

	var children: Array = []
	for i in range(AudioServer.get_bus_count()):
		if i == bus_index:
			continue
		var other_send := AudioServer.get_bus_send(i)
		if other_send != null and String(AudioServer.get_bus_name(other_send)) == bus_name if other_send is int else false:
			children.append({"index": i, "name": AudioServer.get_bus_name(i)})

	_record_event("audio.bus.info", {"bus_name": bus_name, "bus_index": bus_index})
	return _ok({
		"bus": {
			"index": bus_index,
			"name": bus_name,
			"volume_db": volume_db,
			"muted": muted,
			"solo": solo,
			"effect_count": effect_count,
			"effects": effects,
			"send_target": send_target,
			"children": children,
		}
	})
```

Note: The `_fail` and `_ok` helper functions already exist in the server file. If `AudioServer.get_bus_send` doesn't exist in Godot 4.6 (the API may differ), use `AudioServer.get_bus_peak_volume_db` or check the actual API. The key fields that definitely exist: `get_bus_count`, `get_bus_index`, `get_bus_name`, `get_bus_volume_db`, `is_bus_mute`, `is_bus_solo`, `get_bus_effect_count`, `get_bus_effect`, `is_bus_effect_enabled`.

For the `send_target` and `children` routing: In Godot 4.6, bus routing is via `AudioServer.get_bus_send()` which returns the destination bus index. Simplify to:

```gdscript
	var send_target_index := AudioServer.get_bus_send(bus_index)
	var send_target := ""
	if send_target_index >= 0 and send_target_index < AudioServer.get_bus_count():
		send_target = AudioServer.get_bus_name(send_target_index)

	var children: Array = []
	for i in range(AudioServer.get_bus_count()):
		if i == bus_index:
			continue
		if AudioServer.get_bus_send(i) == bus_index:
			children.append({"index": i, "name": AudioServer.get_bus_name(i)})
```

- [ ] **Step 4: Verify addon parses**

Run: `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
Expected: May show preload errors (same as quests module when checked outside project). No NEW parse errors in the `_rpc_audio_bus_info` function.

- [ ] **Step 5: Commit**

```bash
git add addons/godot_playwright/godot_playwright_server.gd
git commit -m "Add audio.bus.info RPC to addon server"
```

---

### Task 2: Add `navigation.query_path` RPC to addon server

**Files:**
- Modify: `addons/godot_playwright/godot_playwright_server.gd`

- [ ] **Step 1: Add dispatch table entry**

Add after the `audio.bus.info` entry:

```gdscript
	"navigation.query_path":
		return _rpc_navigation_query_path(params),
```

- [ ] **Step 2: Add to RPC method list**

Add `"navigation.query_path",` near the other entries.

- [ ] **Step 3: Implement `_rpc_navigation_query_path`**

Add after `_rpc_audio_bus_info`:

```gdscript
func _rpc_navigation_query_path(params: Dictionary) -> Dictionary:
	var dimension := int(params.get("dimension", 3))
	var start_x := float(params.get("start_x", 0.0))
	var start_y := float(params.get("start_y", 0.0))
	var start_z := float(params.get("start_z", 0.0))
	var target_x := float(params.get("target_x", 0.0))
	var target_y := float(params.get("target_y", 0.0))
	var target_z := float(params.get("target_z", 0.0))
	var navigation_layers := int(params.get("navigation_layers", -1))

	var reachable := false
	var points: Array = []
	var path_length := 0.0

	if dimension == 2:
		var start_pos := Vector2(start_x, start_y)
		var target_pos := Vector2(target_x, target_y)
		var map_rid := get_world_2d().get_navigation_map()
		var start_snapped := NavigationServer2D.map_get_closest_point(map_rid, start_pos)
		var target_snapped := NavigationServer2D.map_get_closest_point(map_rid, target_pos)
		var path := NavigationServer2D.get_simple_path(map_rid, start_snapped, target_snapped, true)
		if not path.is_empty():
			reachable = true
			for i in range(path.size()):
				points.append([float(path[i].x), float(path[i].y)])
			for i in range(1, path.size()):
				path_length += path[i].distance_to(path[i - 1])
	elif dimension == 3:
		var start_pos := Vector3(start_x, start_y, start_z)
		var target_pos := Vector3(target_x, target_y, target_z)
		var map_rid := get_world_3d().get_navigation_map()
		var start_snapped := NavigationServer3D.map_get_closest_point(map_rid, start_pos)
		var target_snapped := NavigationServer3D.map_get_closest_point(map_rid, target_pos)
		var path := NavigationServer3D.get_simple_path(map_rid, start_snapped, target_snapped, true)
		if not path.is_empty():
			reachable = true
			for i in range(path.size()):
				points.append([float(path[i].x), float(path[i].y), float(path[i].z)])
			for i in range(1, path.size()):
				path_length += path[i].distance_to(path[i - 1])
	else:
		return _fail({"errors": ["dimension must be 2 or 3"]})

	_record_event("navigation.query_path", {
		"dimension": dimension,
		"reachable": reachable,
		"point_count": points.size(),
		"path_length": path_length,
	})
	return _ok({
		"path": {
			"reachable": reachable,
			"points": points,
			"point_count": points.size(),
			"path_length": path_length,
			"start": [start_x, start_y, start_z] if dimension == 3 else [start_x, start_y],
			"target": [target_x, target_y, target_z] if dimension == 3 else [target_x, target_y],
			"dimension": dimension,
		}
	})
```

Note: `get_world_2d()` / `get_world_3d()` are available on the server node since it extends Node and is in the scene tree. If the server runs in editor mode, use `EditorInterface.get_edited_scene_root().get_world_3d()` or the viewport's world. The `get_simple_path` method is the simplest pathfinding API in Godot 4.6. If `navigation_layers` is specified (> 0), create a `NavigationPathQueryParameters2D/3D` object instead — but for the initial implementation, `get_simple_path` with default layers is sufficient.

- [ ] **Step 4: Verify addon parses**

Run: `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd`
Expected: No new parse errors in `_rpc_navigation_query_path`.

- [ ] **Step 5: Commit**

```bash
git add addons/godot_playwright/godot_playwright_server.gd
git commit -m "Add navigation.query_path RPC to addon server"
```

---

### Task 3: Add Python client methods for `audio.bus.info` and `navigation.query_path`

**Files:**
- Modify: `godot_playwright/client.py` (add after `physics3d_ray` method, around line 670)
- Test: `tests/test_client.py`

- [ ] **Step 1: Write failing tests for client RPC methods**

Add to `tests/test_client.py` in the appropriate test class (the one that tests `physics2d_ray` / `physics3d_ray` — around line 5558):

```python
def test_audio_bus_info_calls_rpc(self) -> None:
    self.set_response("audio.bus.info", {"ok": True, "bus": {"index": 0, "name": "Master", "volume_db": 0.0, "muted": False, "solo": False, "effect_count": 0, "effects": [], "send_target": "", "children": []}})
    result = self.client.audio_bus_info(bus_name="Master")
    self.assertEqual(self.last_rpc_method, "audio.bus.info")
    self.assertEqual(self.last_rpc_params, {"bus_name": "Master"})
    self.assertEqual(result["bus"]["name"], "Master")

def test_audio_bus_info_uses_index_default(self) -> None:
    self.set_response("audio.bus.info", {"ok": True, "bus": {"index": 0, "name": "Master", "volume_db": 0.0, "muted": False, "solo": False, "effect_count": 0, "effects": [], "send_target": "", "children": []}})
    result = self.client.audio_bus_info()
    self.assertEqual(self.last_rpc_params, {"bus_index": 0})
    self.assertTrue(result["ok"])

def test_navigation_query_path_calls_rpc_3d(self) -> None:
    self.set_response("navigation.query_path", {"ok": True, "path": {"reachable": True, "points": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]], "point_count": 2, "path_length": 10.0, "start": [0.0, 0.0, 0.0], "target": [10.0, 0.0, 0.0], "dimension": 3}})
    result = self.client.navigation_query_path(start=(0, 0, 0), target=(10, 0, 0))
    self.assertEqual(self.last_rpc_method, "navigation.query_path")
    self.assertEqual(self.last_rpc_params["start_x"], 0.0)
    self.assertEqual(self.last_rpc_params["target_x"], 10.0)
    self.assertEqual(self.last_rpc_params["dimension"], 3)
    self.assertTrue(result["path"]["reachable"])

def test_navigation_query_path_calls_rpc_2d(self) -> None:
    self.set_response("navigation.query_path", {"ok": True, "path": {"reachable": True, "points": [[0.0, 0.0], [10.0, 0.0]], "point_count": 2, "path_length": 10.0, "start": [0.0, 0.0], "target": [10.0, 0.0], "dimension": 2}})
    result = self.client.navigation_query_path(start=(0, 0), target=(10, 0), dimension=2)
    self.assertEqual(self.last_rpc_params["dimension"], 2)
    self.assertNotIn("start_z", self.last_rpc_params)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m unittest tests.test_client -v -k audio_bus_info 2>&1 | tail -5`
Expected: FAIL with `AttributeError: 'GodotClient' object has no attribute 'audio_bus_info'`

- [ ] **Step 3: Implement client methods**

Add to `godot_playwright/client.py` after the `physics3d_ray` method (around line 670):

```python
    def audio_bus_info(
        self,
        *,
        bus_name: str | None = None,
        bus_index: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if bus_name is not None:
            params["bus_name"] = str(bus_name)
        else:
            params["bus_index"] = int(bus_index if bus_index is not None else 0)
        return self.rpc("audio.bus.info", params)

    def navigation_query_path(
        self,
        start: tuple[float, ...] | list[float],
        target: tuple[float, ...] | list[float],
        *,
        dimension: int = 3,
        navigation_layers: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "dimension": int(dimension),
            "start_x": float(start[0]),
            "start_y": float(start[1]),
            "target_x": float(target[0]),
            "target_y": float(target[1]),
        }
        if dimension == 3:
            params["start_z"] = float(start[2])
            params["target_z"] = float(target[2])
        if navigation_layers is not None:
            params["navigation_layers"] = int(navigation_layers)
        return self.rpc("navigation.query_path", params)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m unittest tests.test_client -v -k "audio_bus_info or navigation_query_path" 2>&1 | tail -10`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add godot_playwright/client.py tests/test_client.py
git commit -m "Add audio_bus_info and navigation_query_path client methods"
```

---

### Task 4: Add `wait_for_audio_bus` and `wait_for_navigation_path` polling helpers

**Files:**
- Modify: `godot_playwright/client.py`
- Test: `tests/test_client.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_client.py`:

```python
def test_wait_for_audio_bus_volume_match(self) -> None:
    self.set_response("audio.bus.info", {"ok": True, "bus": {"index": 0, "name": "Master", "volume_db": -6.0, "muted": False, "solo": False, "effect_count": 0, "effects": [], "send_target": "", "children": []}})
    result = self.client.wait_for_audio_bus(bus_name="Master", volume_db=-6.0, timeout=1.0)
    self.assertTrue(result["ok"])
    self.assertEqual(result["bus"]["volume_db"], -6.0)

def test_wait_for_audio_bus_timeout(self) -> None:
    self.set_response("audio.bus.info", {"ok": True, "bus": {"index": 0, "name": "Master", "volume_db": 0.0, "muted": False, "solo": False, "effect_count": 0, "effects": [], "send_target": "", "children": []}})
    with self.assertRaises(TimeoutError):
        self.client.wait_for_audio_bus(bus_name="Master", volume_db=-100.0, timeout=0.1, interval=0.02)

def test_wait_for_navigation_path_reachable(self) -> None:
    self.set_response("navigation.query_path", {"ok": True, "path": {"reachable": True, "points": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]], "point_count": 2, "path_length": 10.0, "start": [0.0, 0.0, 0.0], "target": [10.0, 0.0, 0.0], "dimension": 3}})
    result = self.client.wait_for_navigation_path(start=(0, 0, 0), target=(10, 0, 0), reachable=True, timeout=1.0)
    self.assertTrue(result["ok"])
    self.assertTrue(result["path"]["reachable"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m unittest tests.test_client -v -k wait_for_audio 2>&1 | tail -5`
Expected: FAIL with `AttributeError`

- [ ] **Step 3: Implement polling helpers**

Add to `godot_playwright/client.py` after the `navigation_query_path` method:

```python
    def wait_for_audio_bus(
        self,
        *,
        bus_name: str | None = None,
        bus_index: int | None = None,
        volume_db: float | None = None,
        muted: bool | None = None,
        solo: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_result: dict[str, Any] = {}
        while True:
            result = self.audio_bus_info(bus_name=bus_name, bus_index=bus_index)
            last_result = result
            if not bool(result.get("ok", False)):
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"audio.bus.info failed: {result.get('errors', [])}")
                time.sleep(interval)
                continue
            bus = result.get("bus", {})
            matched = True
            if volume_db is not None and abs(float(bus.get("volume_db", 0.0)) - volume_db) > 0.1:
                matched = False
            if muted is not None and bool(bus.get("muted", False)) != muted:
                matched = False
            if solo is not None and bool(bus.get("solo", False)) != solo:
                matched = False
            if matched:
                return result
            if time.monotonic() >= deadline:
                observed = {
                    "volume_db": bus.get("volume_db"),
                    "muted": bus.get("muted"),
                    "solo": bus.get("solo"),
                }
                raise TimeoutError(
                    f"Audio bus did not reach expected state within {timeout}s; observed={observed}"
                )
            time.sleep(interval)

    def wait_for_navigation_path(
        self,
        start: tuple[float, ...] | list[float],
        target: tuple[float, ...] | list[float],
        *,
        dimension: int = 3,
        navigation_layers: int | None = None,
        reachable: bool | None = None,
        path_length: float | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_result: dict[str, Any] = {}
        while True:
            result = self.navigation_query_path(start, target, dimension=dimension, navigation_layers=navigation_layers)
            last_result = result
            if not bool(result.get("ok", False)):
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"navigation.query_path failed: {result.get('errors', [])}")
                time.sleep(interval)
                continue
            path = result.get("path", {})
            matched = True
            if reachable is not None and bool(path.get("reachable", False)) != reachable:
                matched = False
            if path_length is not None and abs(float(path.get("path_length", 0.0)) - path_length) > 0.1:
                matched = False
            if matched:
                return result
            if time.monotonic() >= deadline:
                observed = {
                    "reachable": path.get("reachable"),
                    "path_length": path.get("path_length"),
                }
                raise TimeoutError(
                    f"Navigation path did not reach expected state within {timeout}s; observed={observed}"
                )
            time.sleep(interval)
```

Ensure `import time` is at the top of `client.py` (it likely already is).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m unittest tests.test_client -v -k "wait_for_audio or wait_for_navigation" 2>&1 | tail -10`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add godot_playwright/client.py tests/test_client.py
git commit -m "Add wait_for_audio_bus and wait_for_navigation_path polling helpers"
```

---

### Task 5: Implement `AudioExpect` class

**Files:**
- Modify: `godot_playwright/client.py` (add class near `Physics2DExpect` ~line 12391)
- Test: `tests/test_client.py`

- [ ] **Step 1: Write failing tests for bus assertions**

Add to `tests/test_client.py`:

```python
class AudioExpectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _FakeGodotClient()
        self.expect = AudioExpect(self.client)

    def test_to_have_bus_volume_match(self) -> None:
        self.client.set_response("audio.bus.info", {"ok": True, "bus": {"index": 0, "name": "Master", "volume_db": -6.0, "muted": False, "solo": False, "effect_count": 0, "effects": [], "send_target": "", "children": []}})
        result = self.expect.to_have_bus_volume("Master", -6.0, timeout=1.0)
        self.assertTrue(result["ok"])

    def test_to_have_bus_volume_timeout(self) -> None:
        self.client.set_response("audio.bus.info", {"ok": True, "bus": {"index": 0, "name": "Master", "volume_db": 0.0, "muted": False, "solo": False, "effect_count": 0, "effects": [], "send_target": "", "children": []}})
        with self.assertRaises(TimeoutError):
            self.expect.to_have_bus_volume("Master", -100.0, timeout=0.1, interval=0.02)

    def test_to_have_bus_muted(self) -> None:
        self.client.set_response("audio.bus.info", {"ok": True, "bus": {"index": 0, "name": "Master", "volume_db": 0.0, "muted": True, "solo": False, "effect_count": 0, "effects": [], "send_target": "", "children": []}})
        result = self.expect.to_have_bus_muted("Master", timeout=1.0)
        self.assertTrue(result["ok"])

    def test_not_to_have_bus_muted(self) -> None:
        self.client.set_response("audio.bus.info", {"ok": True, "bus": {"index": 0, "name": "Master", "volume_db": 0.0, "muted": False, "solo": False, "effect_count": 0, "effects": [], "send_target": "", "children": []}})
        result = self.expect.not_to_have_bus_muted("Master", timeout=1.0)
        self.assertTrue(result["ok"])

    def test_to_have_bus_effect_with_class(self) -> None:
        self.client.set_response("audio.bus.info", {"ok": True, "bus": {"index": 0, "name": "Master", "volume_db": 0.0, "muted": False, "solo": False, "effect_count": 1, "effects": [{"index": 0, "class": "AudioEffectReverb", "enabled": True, "resource_name": ""}], "send_target": "", "children": []}})
        result = self.expect.to_have_bus_effect("Master", "AudioEffectReverb", timeout=1.0)
        self.assertTrue(result["ok"])

    def test_to_have_bus_effect_enabled_filter(self) -> None:
        self.client.set_response("audio.bus.info", {"ok": True, "bus": {"index": 0, "name": "Master", "volume_db": 0.0, "muted": False, "solo": False, "effect_count": 1, "effects": [{"index": 0, "class": "AudioEffectReverb", "enabled": False, "resource_name": ""}], "send_target": "", "children": []}})
        with self.assertRaises(TimeoutError):
            self.expect.to_have_bus_effect("Master", "AudioEffectReverb", enabled=True, timeout=0.1, interval=0.02)
```

Add `from godot_playwright.client import AudioExpect` to the test file imports (or adjust based on existing import style).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m unittest tests.test_client -v -k AudioExpectTests 2>&1 | tail -5`
Expected: FAIL with `ImportError` or `AttributeError`

- [ ] **Step 3: Implement `AudioExpect` class**

Add to `godot_playwright/client.py` before the `Physics2DExpect` class (around line 12391):

```python
class AudioExpect:
    def __init__(self, client: GodotClient):
        self.client = client

    def to_have_bus_volume(
        self, bus: str, volume_db: float, *, tolerance: float = 0.1, timeout: float = 5.0
    ) -> dict[str, Any]:
        try:
            return self.client.wait_for_audio_bus(bus_name=bus, volume_db=volume_db, timeout=timeout)
        except TimeoutError:
            info = self.client.audio_bus_info(bus_name=bus)
            observed = info.get("bus", {}).get("volume_db")
            raise TimeoutError(
                f"Expected bus '{bus}' volume_db to be {volume_db} (±{tolerance}); observed={observed}"
            ) from None

    def to_have_bus_muted(self, bus: str, *, timeout: float = 5.0) -> dict[str, Any]:
        try:
            return self.client.wait_for_audio_bus(bus_name=bus, muted=True, timeout=timeout)
        except TimeoutError:
            raise TimeoutError(f"Expected bus '{bus}' to be muted within {timeout}s") from None

    def not_to_have_bus_muted(self, bus: str, *, timeout: float = 5.0) -> dict[str, Any]:
        try:
            return self.client.wait_for_audio_bus(bus_name=bus, muted=False, timeout=timeout)
        except TimeoutError:
            raise TimeoutError(f"Expected bus '{bus}' to not be muted within {timeout}s") from None

    def to_have_bus_solo(self, bus: str, *, timeout: float = 5.0) -> dict[str, Any]:
        try:
            return self.client.wait_for_audio_bus(bus_name=bus, solo=True, timeout=timeout)
        except TimeoutError:
            raise TimeoutError(f"Expected bus '{bus}' to be soloed within {timeout}s") from None

    def to_have_bus_effect(
        self, bus: str, effect_class: str, *, enabled: bool | None = None, timeout: float = 5.0
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        interval = 0.05
        while True:
            info = self.client.audio_bus_info(bus_name=bus)
            effects = info.get("bus", {}).get("effects", [])
            for effect in effects:
                if effect.get("class") == effect_class:
                    if enabled is not None and bool(effect.get("enabled")) != enabled:
                        continue
                    return info
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Expected bus '{bus}' to have effect '{effect_class}'"
                    f"{' enabled=' + str(enabled) if enabled is not None else ''}"
                    f" within {timeout}s; effects={effects}"
                )
            time.sleep(interval)

    def to_have_bus(self, bus: str, *, timeout: float = 5.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        interval = 0.05
        while True:
            info = self.client.audio_bus_info(bus_name=bus)
            if bool(info.get("ok", False)):
                return info
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Expected bus '{bus}' to exist within {timeout}s")
            time.sleep(interval)
```

Add the factory function after the class:

```python
def expect_audio(client: GodotClient) -> AudioExpect:
    return AudioExpect(client)
```

- [ ] **Step 4: Run bus assertion tests to verify they pass**

Run: `.venv/bin/python -m unittest tests.test_client -v -k AudioExpectTests 2>&1 | tail -10`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add godot_playwright/client.py tests/test_client.py
git commit -m "Add AudioExpect class with bus assertions"
```

---

### Task 6: Add player node assertions to `AudioExpect`

**Files:**
- Modify: `godot_playwright/client.py` (add methods to `AudioExpect`)
- Test: `tests/test_client.py`

- [ ] **Step 1: Write failing tests for player assertions**

Add to the `AudioExpectTests` class in `tests/test_client.py`:

```python
    def test_to_be_playing(self) -> None:
        self.client.set_response("node.evaluate", {"ok": True, "value": True})
        result = self.expect.to_be_playing("#BgmPlayer", timeout=1.0)
        self.assertTrue(result["ok"])

    def test_not_to_be_playing(self) -> None:
        self.client.set_response("node.evaluate", {"ok": True, "value": False})
        result = self.expect.not_to_be_playing("#BgmPlayer", timeout=1.0)
        self.assertTrue(result["ok"])

    def test_to_have_pitch(self) -> None:
        self.client.set_response("node.evaluate", {"ok": True, "value": 1.5})
        result = self.expect.to_have_pitch("#BgmPlayer", 1.5, timeout=1.0)
        self.assertTrue(result["ok"])

    def test_to_have_volume_db(self) -> None:
        self.client.set_response("node.evaluate", {"ok": True, "value": -3.0})
        result = self.expect.to_have_volume_db("#BgmPlayer", -3.0, timeout=1.0)
        self.assertTrue(result["ok"])
```

Note: These tests use the existing fake server `node.evaluate` response mechanism. The actual `to_be_playing` implementation will use `self.client.locator(selector).evaluate('node.get("playing")')` which internally calls `node.evaluate` RPC.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m unittest tests.test_client -v -k "AudioExpectTests.test_to_be_playing" 2>&1 | tail -5`
Expected: FAIL with `AttributeError`

- [ ] **Step 3: Implement player node assertions**

Add these methods to the `AudioExpect` class in `godot_playwright/client.py`:

```python
    def to_be_playing(self, selector: str | dict, *, timeout: float = 5.0) -> dict[str, Any]:
        locator = self.client.locator(selector)
        return _wait_for_node_value(
            locator, 'node.get("playing")', True, "to be playing", timeout=timeout
        )

    def not_to_be_playing(self, selector: str | dict, *, timeout: float = 5.0) -> dict[str, Any]:
        locator = self.client.locator(selector)
        return _wait_for_node_value(
            locator, 'node.get("playing")', False, "to not be playing", timeout=timeout
        )

    def to_have_stream(
        self, selector: str | dict, stream_path: str, *, timeout: float = 5.0
    ) -> dict[str, Any]:
        locator = self.client.locator(selector)
        return _wait_for_node_value(
            locator,
            'node.get("stream").resource_path if node.get("stream") != null else ""',
            stream_path,
            f"to have stream '{stream_path}'",
            timeout=timeout,
        )

    def to_have_pitch(
        self, selector: str | dict, pitch: float, *, tolerance: float = 0.01, timeout: float = 5.0
    ) -> dict[str, Any]:
        locator = self.client.locator(selector)
        deadline = time.monotonic() + timeout
        interval = 0.05
        while True:
            value = locator.evaluate('node.get("pitch_scale")')
            observed = float(value) if value is not None else None
            if observed is not None and abs(observed - pitch) <= tolerance:
                return {"ok": True, "value": observed}
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Expected {selector} to have pitch {pitch} (±{tolerance}); observed={observed}"
                )
            time.sleep(interval)

    def to_have_volume_db(
        self, selector: str | dict, volume_db: float, *, tolerance: float = 0.1, timeout: float = 5.0
    ) -> dict[str, Any]:
        locator = self.client.locator(selector)
        deadline = time.monotonic() + timeout
        interval = 0.05
        while True:
            value = locator.evaluate('node.get("volume_db")')
            observed = float(value) if value is not None else None
            if observed is not None and abs(observed - volume_db) <= tolerance:
                return {"ok": True, "value": observed}
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Expected {selector} to have volume_db {volume_db} (±{tolerance}); observed={observed}"
                )
            time.sleep(interval)
```

Add the helper function `_wait_for_node_value` near the top of client.py (or in the AudioExpect section):

```python
def _wait_for_node_value(
    locator: "Locator",
    expression: str,
    expected: Any,
    description: str,
    *,
    timeout: float = 5.0,
    interval: float = 0.05,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        value = locator.evaluate(expression)
        if value == expected:
            return {"ok": True, "value": value}
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Expected {locator} {description}; expected={expected!r}, observed={value!r}"
            )
        time.sleep(interval)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m unittest tests.test_client -v -k AudioExpectTests 2>&1 | tail -10`
Expected: PASS (all AudioExpect tests)

- [ ] **Step 5: Commit**

```bash
git add godot_playwright/client.py tests/test_client.py
git commit -m "Add AudioExpect player node assertions"
```

---

### Task 7: Implement `NavigationExpect` class

**Files:**
- Modify: `godot_playwright/client.py` (add class near `AudioExpect`)
- Test: `tests/test_client.py`

- [ ] **Step 1: Write failing tests for path assertions**

Add to `tests/test_client.py`:

```python
class NavigationExpectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _FakeGodotClient()
        self.expect = NavigationExpect(self.client)

    def test_to_be_reachable(self) -> None:
        self.client.set_response("navigation.query_path", {"ok": True, "path": {"reachable": True, "points": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]], "point_count": 2, "path_length": 10.0, "start": [0.0, 0.0, 0.0], "target": [10.0, 0.0, 0.0], "dimension": 3}})
        result = self.expect.to_be_reachable(start=(0, 0, 0), target=(10, 0, 0), timeout=1.0)
        self.assertTrue(result["ok"])

    def test_not_to_be_reachable(self) -> None:
        self.client.set_response("navigation.query_path", {"ok": True, "path": {"reachable": False, "points": [], "point_count": 0, "path_length": 0.0, "start": [0.0, 0.0, 0.0], "target": [1000.0, 0.0, 0.0], "dimension": 3}})
        result = self.expect.not_to_be_reachable(start=(0, 0, 0), target=(1000, 0, 0), timeout=1.0)
        self.assertTrue(result["ok"])

    def test_to_have_path_length(self) -> None:
        self.client.set_response("navigation.query_path", {"ok": True, "path": {"reachable": True, "points": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]], "point_count": 2, "path_length": 10.0, "start": [0.0, 0.0, 0.0], "target": [10.0, 0.0, 0.0], "dimension": 3}})
        result = self.expect.to_have_path_length(start=(0, 0, 0), target=(10, 0, 0), length=10.0, timeout=1.0)
        self.assertTrue(result["ok"])

    def test_to_have_path_point_count(self) -> None:
        self.client.set_response("navigation.query_path", {"ok": True, "path": {"reachable": True, "points": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]], "point_count": 2, "path_length": 10.0, "start": [0.0, 0.0, 0.0], "target": [10.0, 0.0, 0.0], "dimension": 3}})
        result = self.expect.to_have_path_point_count(start=(0, 0, 0), target=(10, 0, 0), count=2, timeout=1.0)
        self.assertTrue(result["ok"])

    def test_to_have_target_reached(self) -> None:
        self.client.set_response("node.evaluate", {"ok": True, "value": True})
        result = self.expect.to_have_target_reached("#NavAgent", timeout=1.0)
        self.assertTrue(result["ok"])

    def test_to_have_target_distance(self) -> None:
        self.client.set_response("node.evaluate", {"ok": True, "value": 0.0})
        result = self.expect.to_have_target_distance("#NavAgent", 0.0, timeout=1.0)
        self.assertTrue(result["ok"])

    def test_to_have_navigation_mesh(self) -> None:
        self.client.set_response("node.evaluate", {"ok": True, "value": {"resource_path": "res://nav.tres"}})
        result = self.expect.to_have_navigation_mesh("#NavRegion", timeout=1.0)
        self.assertTrue(result["ok"])

    def test_to_have_region_enabled(self) -> None:
        self.client.set_response("node.evaluate", {"ok": True, "value": True})
        result = self.expect.to_have_region_enabled("#NavRegion", timeout=1.0)
        self.assertTrue(result["ok"])
```

Add `from godot_playwright.client import NavigationExpect` to imports.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m unittest tests.test_client -v -k NavigationExpectTests 2>&1 | tail -5`
Expected: FAIL with `ImportError` or `AttributeError`

- [ ] **Step 3: Implement `NavigationExpect` class**

Add to `godot_playwright/client.py` after `AudioExpect`:

```python
class NavigationExpect:
    def __init__(self, client: GodotClient):
        self.client = client

    def to_be_reachable(
        self,
        start: tuple[float, ...] | list[float],
        target: tuple[float, ...] | list[float],
        *,
        dimension: int = 3,
        navigation_layers: int | None = None,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        try:
            return self.client.wait_for_navigation_path(
                start, target, dimension=dimension, navigation_layers=navigation_layers,
                reachable=True, timeout=timeout,
            )
        except TimeoutError:
            raise TimeoutError(
                f"Expected path from {start} to {target} to be reachable within {timeout}s"
            ) from None

    def not_to_be_reachable(
        self,
        start: tuple[float, ...] | list[float],
        target: tuple[float, ...] | list[float],
        *,
        dimension: int = 3,
        navigation_layers: int | None = None,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        try:
            return self.client.wait_for_navigation_path(
                start, target, dimension=dimension, navigation_layers=navigation_layers,
                reachable=False, timeout=timeout,
            )
        except TimeoutError:
            raise TimeoutError(
                f"Expected path from {start} to {target} to not be reachable within {timeout}s"
            ) from None

    def to_have_path_length(
        self,
        start: tuple[float, ...] | list[float],
        target: tuple[float, ...] | list[float],
        length: float,
        *,
        tolerance: float = 0.1,
        dimension: int = 3,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        try:
            return self.client.wait_for_navigation_path(
                start, target, dimension=dimension, path_length=length, timeout=timeout,
            )
        except TimeoutError:
            result = self.client.navigation_query_path(start, target, dimension=dimension)
            observed = result.get("path", {}).get("path_length")
            raise TimeoutError(
                f"Expected path length {length} (±{tolerance}); observed={observed}"
            ) from None

    def to_have_path_point_count(
        self,
        start: tuple[float, ...] | list[float],
        target: tuple[float, ...] | list[float],
        count: int,
        *,
        dimension: int = 3,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        interval = 0.05
        while True:
            result = self.client.navigation_query_path(start, target, dimension=dimension)
            observed = int(result.get("path", {}).get("point_count", 0))
            if observed == count:
                return result
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Expected path point count {count}; observed={observed}"
                )
            time.sleep(interval)

    def to_have_target_reached(
        self, selector: str | dict, *, timeout: float = 5.0
    ) -> dict[str, Any]:
        locator = self.client.locator(selector)
        return _wait_for_node_value(
            locator, 'node.get("target_reached")', True, "to have target reached", timeout=timeout
        )

    def to_have_target_distance(
        self, selector: str | dict, distance: float, *, tolerance: float = 0.1, timeout: float = 5.0
    ) -> dict[str, Any]:
        locator = self.client.locator(selector)
        deadline = time.monotonic() + timeout
        interval = 0.05
        while True:
            value = locator.evaluate('node.get("distance_to_target")')
            observed = float(value) if value is not None else None
            if observed is not None and abs(observed - distance) <= tolerance:
                return {"ok": True, "value": observed}
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Expected {selector} target distance {distance} (±{tolerance}); observed={observed}"
                )
            time.sleep(interval)

    def to_have_pathway_point_count(
        self, selector: str | dict, count: int, *, timeout: float = 5.0
    ) -> dict[str, Any]:
        locator = self.client.locator(selector)
        deadline = time.monotonic() + timeout
        interval = 0.05
        while True:
            value = locator.evaluate('node.get("pathway_points").size()')
            observed = int(value) if value is not None else None
            if observed is not None and observed == count:
                return {"ok": True, "value": observed}
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Expected {selector} pathway point count {count}; observed={observed}"
                )
            time.sleep(interval)

    def to_have_navigation_mesh(
        self, selector: str | dict, *, timeout: float = 5.0
    ) -> dict[str, Any]:
        locator = self.client.locator(selector)
        deadline = time.monotonic() + timeout
        interval = 0.05
        while True:
            value = locator.evaluate('node.get("navigation_mesh") != null')
            if bool(value):
                return {"ok": True, "value": True}
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Expected {selector} to have a navigation mesh within {timeout}s")
            time.sleep(interval)

    def to_have_region_enabled(
        self, selector: str | dict, *, timeout: float = 5.0
    ) -> dict[str, Any]:
        locator = self.client.locator(selector)
        return _wait_for_node_value(
            locator, 'node.get("enabled")', True, "to have region enabled", timeout=timeout
        )
```

Add the factory function:

```python
def expect_navigation(client: GodotClient) -> NavigationExpect:
    return NavigationExpect(client)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m unittest tests.test_client -v -k NavigationExpectTests 2>&1 | tail -10`
Expected: PASS (all NavigationExpect tests)

- [ ] **Step 5: Commit**

```bash
git add godot_playwright/client.py tests/test_client.py
git commit -m "Add NavigationExpect class with path and node assertions"
```

---

### Task 8: Register fixtures in runner and export from package

**Files:**
- Modify: `godot_playwright/runner.py` (fixture registry ~line 1423)
- Modify: `godot_playwright/__init__.py`
- Test: `tests/test_runner.py`

- [ ] **Step 1: Write failing test for fixture registration**

Add to `tests/test_runner.py`:

```python
def test_expect_audio_fixture_registered(self) -> None:
    # Verify expect_audio appears in the runner fixture registry
    from godot_playwright.runner import _fixture_registry_keys
    # Or use whatever method the existing tests use to verify fixture registration
    # Check the existing test_runner.py patterns for expect_physics2d registration
```

Look at the existing `test_runner.py` for how `expect_physics2d` registration is tested, and mirror that pattern.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_runner -v -k expect_audio 2>&1 | tail -5`
Expected: FAIL

- [ ] **Step 3: Register fixtures in runner**

In `godot_playwright/runner.py`, find the fixture registry dictionary (around line 1423 where `"expect_physics2d": expect_physics2d(godot),` appears). Add:

```python
        "expect_audio": expect_audio(godot),
        "expect_navigation": expect_navigation(godot),
```

Add the imports at the top of `runner.py`:

```python
from .client import expect_audio, expect_navigation
```

(Match the existing import style for `expect_physics2d`, `expect_physics3d`.)

- [ ] **Step 4: Export from `__init__.py`**

In `godot_playwright/__init__.py`, add to the import block (around line 37-38 where `expect_physics2d` is imported):

```python
from .client import expect_audio, expect_navigation
```

And add to the `__all__` list (around line 163-164):

```python
    "expect_audio",
    "expect_navigation",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m unittest tests.test_runner -v -k "expect_audio or expect_navigation" 2>&1 | tail -10`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add godot_playwright/runner.py godot_playwright/__init__.py tests/test_runner.py
git commit -m "Register expect_audio and expect_navigation fixtures"
```

---

### Task 9: Add codegen replay for new trace events

**Files:**
- Modify: `godot_playwright/codegen.py` (add after `physics3d.ray` replay ~line 377)
- Test: `tests/test_codegen.py`

- [ ] **Step 1: Write failing test for codegen replay**

Add to `tests/test_codegen.py`:

```python
def test_codegen_replays_audio_bus_info(self) -> None:
    trace = {"type": "audio.bus.info", "data": {"bus_name": "Master", "bus_index": 0}}
    result = _replay_event(trace)
    assert "godot.audio_bus_info" in result
    assert "bus_name=\"Master\"" in result

def test_codegen_replays_navigation_query_path(self) -> None:
    trace = {"type": "navigation.query_path", "data": {"dimension": 3, "reachable": True, "point_count": 2, "path_length": 10.0, "start": [0.0, 0.0, 0.0], "target": [10.0, 0.0, 0.0]}}
    result = _replay_event(trace)
    assert "godot.navigation_query_path" in result
```

Note: Check the existing `tests/test_codegen.py` for the exact `_replay_event` function name and test pattern, then mirror it.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_codegen -v -k "audio_bus_info or navigation_query_path" 2>&1 | tail -5`
Expected: FAIL

- [ ] **Step 3: Implement codegen replay**

In `godot_playwright/codegen.py`, after the `physics3d.ray` replay block (around line 377), add:

```python
    if event_type == "audio.bus.info":
        kwargs = []
        if "bus_name" in data:
            kwargs.append(f'bus_name="{data["bus_name"]}"')
        if "bus_index" in data:
            kwargs.append(f'bus_index={data["bus_index"]}')
        return _call("godot.audio_bus_info", [], kwargs)
    if event_type == "navigation.query_path":
        start = data.get("start", [0.0, 0.0, 0.0])
        target = data.get("target", [0.0, 0.0, 0.0])
        dimension = int(data.get("dimension", 3))
        kwargs = [f"dimension={dimension}"]
        return _call(
            "godot.navigation_query_path",
            [list(start), list(target)],
            kwargs,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m unittest tests.test_codegen -v -k "audio_bus_info or navigation_query_path" 2>&1 | tail -10`
Expected: PASS

Also run the codegen coverage test to ensure the new events are classified:

Run: `.venv/bin/python -m unittest tests.test_codegen -v 2>&1 | tail -10`
Expected: PASS (the codegen coverage test may need updating if it asserts all addon events are replayable — check and update if needed)

- [ ] **Step 5: Commit**

```bash
git add godot_playwright/codegen.py tests/test_codegen.py
git commit -m "Add codegen replay for audio.bus.info and navigation.query_path"
```

---

### Task 10: Add live integration tests

**Files:**
- Modify: `tests/test_godot_integration.py`
- Test: self (live Godot tests)

- [ ] **Step 1: Write live Audio integration test**

Add to `tests/test_godot_integration.py`:

```python
@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class DomainAssertionsAudioTests(unittest.TestCase):
    def test_audio_bus_info_and_player_assertions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = init_project(Path(tmp) / "project", name="Audio Assertion Probe")
            _write_audio_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/audio_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#AudioProbe").call("run_probe")

        self.assertTrue(result["ok"], result)
```

Add the probe writer helper:

```python
def _write_audio_probe(project: Path) -> None:
    (project / "scripts" / "audio_probe.gd").write_text(
        textwrap.dedent("""\
            extends Node

            func run_probe() -> Dictionary:
                var errors: Array[String] = []
                # Add a custom bus
                AudioServer.add_bus()
                var bus_idx := AudioServer.get_bus_count() - 1
                AudioServer.set_bus_name(bus_idx, "TestBus")
                AudioServer.set_bus_send(bus_idx, "Master")
                AudioServer.set_bus_volume_db(bus_idx, -6.0)
                AudioServer.set_bus_mute(bus_idx, true)

                # Query via the addon RPC
                var result := _query_bus("TestBus")
                if not bool(result.get("ok", false)):
                    errors.append("audio.bus.info failed: %s" % str(result.get("errors", [])))
                    return {"ok": false, "errors": errors}
                var bus: Dictionary = result.get("bus", {})
                _assert_float(-6.0, float(bus.get("volume_db", 0.0)), "volume_db", errors)
                _assert_bool(true, bool(bus.get("muted", false)), "muted", errors)
                return {"ok": errors.is_empty(), "errors": errors}

            func _query_bus(bus_name: String) -> Dictionary:
                # Use the protocol client if available, otherwise direct RPC
                # This probe runs in runtime mode where the addon autoload is active
                var rpc_result := _do_rpc("audio.bus.info", {"bus_name": bus_name})
                return rpc_result

            func _do_rpc(method: String, params: Dictionary) -> Dictionary:
                # Access the autoload server and call its dispatch directly
                var server := get_node_or_null("/root/GodotPlaywright")
                if server == null:
                    return {"ok": false, "errors": ["GodotPlaywright autoload not found"]}
                return server.dispatch_rpc(method, params)

            func _assert_float(expected: float, actual: float, label: String, errors: Array[String]) -> void:
                if abs(expected - actual) > 0.1:
                    errors.append("%s: expected %f, got %f" % [label, expected, actual])

            func _assert_bool(expected: bool, actual: bool, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %s, got %s" % [label, expected, actual])
            """),
        encoding="utf-8",
    )
    (project / "scenes" / "audio_probe.tscn").write_text(
        textwrap.dedent("""\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/audio_probe.gd" id="1_probe_script"]

            [node name="AudioProbe" type="Node"]
            script = ExtResource("1_probe_script")
            """),
        encoding="utf-8",
    )
```

Note: The exact RPC dispatch mechanism may differ. Check how existing integration probes in `test_godot_integration.py` call addon RPCs from within a probe script, and mirror that pattern. The key is that the GodotPlaywright autoload server exposes a `dispatch_rpc` method or similar.

- [ ] **Step 2: Write live Navigation integration test**

Add to `tests/test_godot_integration.py`:

```python
@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class DomainAssertionsNavigationTests(unittest.TestCase):
    def test_navigation_path_reachability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = init_project(Path(tmp) / "project", name="Navigation Assertion Probe")
            _write_navigation_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/navigation_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#NavigationProbe").call("run_probe")

        self.assertTrue(result["ok"], result)
```

Add the probe writer (creates a NavigationRegion3D with a simple navmesh):

```python
def _write_navigation_probe(project: Path) -> None:
    (project / "scripts" / "navigation_probe.gd").write_text(
        textwrap.dedent("""\
            extends Node

            func run_probe() -> Dictionary:
                var errors: Array[String] = []
                # Create a simple NavigationRegion3D with a plane navmesh
                var region := NavigationRegion3D.new()
                add_child(region)
                var mesh := NavigationMesh.new()
                var verts := PackedVector3Array([Vector3(-10, 0, -10), Vector3(10, 0, -10), Vector3(10, 0, 10), Vector3(-10, 0, 10)])
                mesh.vertices = verts
                var polygon := PackedInt32Array([0, 1, 2, 3])
                mesh.add_polygon(polygon)
                region.navigation_mesh = mesh
                # Wait for the navigation server to process
                await get_tree().process_frame
                await get_tree().process_frame

                # Query path via addon RPC
                var result := _do_rpc("navigation.query_path", {
                    "start_x": 0.0, "start_y": 0.0, "start_z": 0.0,
                    "target_x": 5.0, "target_y": 0.0, "target_z": 5.0,
                    "dimension": 3,
                })
                if not bool(result.get("ok", false)):
                    errors.append("navigation.query_path failed: %s" % str(result.get("errors", [])))
                    return {"ok": false, "errors": errors}
                var path: Dictionary = result.get("path", {})
                _assert_bool(true, bool(path.get("reachable", false)), "reachable", errors)
                _assert_int(2, int(path.get("point_count", 0)), "point_count", errors)
                return {"ok": errors.is_empty(), "errors": errors}

            func _do_rpc(method: String, params: Dictionary) -> Dictionary:
                var server := get_node_or_null("/root/GodotPlaywright")
                if server == null:
                    return {"ok": false, "errors": ["GodotPlaywright autoload not found"]}
                return server.dispatch_rpc(method, params)

            func _assert_bool(expected: bool, actual: bool, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %s, got %s" % [label, expected, actual])

            func _assert_int(expected: int, actual: int, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %d, got %d" % [label, expected, actual])
            """),
        encoding="utf-8",
    )
    (project / "scenes" / "navigation_probe.tscn").write_text(
        textwrap.dedent("""\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/navigation_probe.gd" id="1_probe_script"]

            [node name="NavigationProbe" type="Node"]
            script = ExtResource("1_probe_script")
            """),
        encoding="utf-8",
    )
```

- [ ] **Step 3: Run live integration tests**

Run: `.venv/bin/python -m unittest tests.test_godot_integration -v -k "DomainAssertions" 2>&1 | tail -15`
Expected: PASS (may need debugging of the probe scripts — fix the GDScript, not the test assertions, if they fail due to real bugs)

- [ ] **Step 4: Commit**

```bash
git add tests/test_godot_integration.py
git commit -m "Add live Audio and Navigation integration tests"
```

---

### Task 11: Update README.md and docs/protocol.md

**Files:**
- Modify: `README.md`
- Modify: `docs/protocol.md`

- [ ] **Step 1: Add README assertion examples**

In `README.md`, find the section that shows physics assertion examples (search for `expect_physics2d`). Add after that section:

```markdown
Audio assertions check AudioServer bus state and AudioStreamPlayer node state:

```python
def test_audio(godot, expect_audio):
    player = godot.locator("#BgmPlayer")
    player.call("play")
    expect_audio.to_be_playing("#BgmPlayer")
    expect_audio.to_have_bus_volume("Master", 0.0, tolerance=0.1)
    godot.evaluate('AudioServer.set_bus_mute(AudioServer.get_bus_index("Music"), true)')
    expect_audio.to_have_bus_muted("Music", timeout=1.0)
    expect_audio.to_have_pitch("#BgmPlayer", 1.0)
    expect_audio.to_have_volume_db("#BgmPlayer", 0.0)
```

Navigation assertions check path reachability and NavigationAgent/Region node state:

```python
def test_navigation(godot, expect_navigation):
    expect_navigation.to_be_reachable(start=(0, 0, 0), target=(10, 0, 0))
    expect_navigation.to_have_path_length(start=(0, 0, 0), target=(10, 0, 0), length=10.0, tolerance=0.5)
    agent = godot.locator("#NavAgent")
    expect_navigation.to_have_target_reached("#NavAgent", timeout=5.0)
    expect_navigation.to_have_target_distance("#NavAgent", 0.0, tolerance=0.1)
    expect_navigation.to_have_navigation_mesh("#NavRegion")
    expect_navigation.to_have_region_enabled("#NavRegion")
```
```

- [ ] **Step 2: Add protocol.md documentation**

In `docs/protocol.md`, add entries for the two new RPCs in the appropriate section:

```markdown
### `audio.bus.info`

Query AudioServer bus state by name or index.

Parameters:
- `bus_name` (String, optional): resolve bus by name (takes precedence)
- `bus_index` (int, optional, default 0): resolve bus by index

Returns bus snapshot with `index`, `name`, `volume_db`, `muted`, `solo`,
`effect_count`, `effects` array, `send_target`, and `children` array.

### `navigation.query_path`

Query navigation path reachability through NavigationServer.

Parameters:
- `start_x`, `start_y`, `start_z` (float): start position (z ignored for 2D)
- `target_x`, `target_y`, `target_z` (float): target position (z ignored for 2D)
- `dimension` (int, default 3): 2 or 3
- `navigation_layers` (int, optional): layer bitmask filter

Returns path object with `reachable`, `points`, `point_count`, `path_length`,
`start`, `target`, and `dimension`.
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/protocol.md
git commit -m "Document audio and navigation assertion APIs"
```

---

### Task 12: Full suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run addon check**

Run: `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd 2>&1 | grep "Parse Error" | grep -v "Preload file"`
Expected: No output (preload path errors are expected, same as existing modules)

- [ ] **Step 2: Run py_compile**

Run: `.venv/bin/python -m py_compile godot_playwright/*.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py tests/test_runner.py`
Expected: No errors

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/python -m unittest discover -s tests 2>&1 | tail -5`
Expected: `OK` with all tests passing (previous count + new tests)

- [ ] **Step 4: Verify no type suppressions**

Run: `grep -rn "as any\|@ts-ignore\|# type: ignore" godot_playwright/*.py tests/test_*.py | grep -v ".venv"`
Expected: No output

- [ ] **Step 5: Final commit if any fixes were needed**

If any fixes were applied during verification:
```bash
git add -A
git commit -m "Fix verification issues for domain assertions"
```

---

## Self-Review Notes

- **Spec coverage**: All items from the spec are covered — 2 RPCs (Tasks 1-2), client methods (Task 3), wait helpers (Task 4), AudioExpect bus + player (Tasks 5-6), NavigationExpect path + node (Task 7), runner registration + exports (Task 8), codegen (Task 9), integration tests (Task 10), docs (Task 11), verification (Task 12).
- **Placeholder scan**: No TBD/TODO. All code blocks contain actual implementation code. Probe scripts may need adjustment based on the actual addon dispatch API (the `dispatch_rpc` method name should be verified against the actual server implementation).
- **Type consistency**: `AudioExpect` and `NavigationExpect` method signatures match across tasks. `_wait_for_node_value` helper is defined in Task 6 and used in Tasks 6-7.
- **Scope**: Single batch (Audio + Navigation). Subsequent batches (Animation/Material/Physics) are explicitly out of scope per the spec.
