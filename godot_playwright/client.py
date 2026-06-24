from __future__ import annotations

import base64
import http.client
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .install import install_addon
from .process import isolated_godot_env

MOUSE_BUTTON_LEFT = 1
MOUSE_BUTTON_RIGHT = 2
MOUSE_BUTTON_MIDDLE = 3

MOUSE_BUTTON_MASKS = {
    MOUSE_BUTTON_LEFT: 1,
    MOUSE_BUTTON_RIGHT: 2,
    MOUSE_BUTTON_MIDDLE: 4,
}

_UNSET = object()

_MOUSE_BUTTON_ALIASES = {
    "left": 1,
    "primary": 1,
    "right": 2,
    "secondary": 2,
    "middle": 3,
    "aux": 3,
    "wheelup": 4,
    "scrollup": 4,
    "wheeldown": 5,
    "scrolldown": 5,
    "wheelleft": 6,
    "scrollleft": 6,
    "wheelright": 7,
    "scrollright": 7,
}

_JOY_BUTTON_ALIASES = {
    "a": 0,
    "cross": 0,
    "south": 0,
    "bottom": 0,
    "b": 1,
    "circle": 1,
    "east": 1,
    "rightface": 1,
    "x": 2,
    "square": 2,
    "west": 2,
    "leftface": 2,
    "y": 3,
    "triangle": 3,
    "north": 3,
    "top": 3,
    "back": 4,
    "select": 4,
    "view": 4,
    "share": 4,
    "guide": 5,
    "home": 5,
    "start": 6,
    "menu": 6,
    "options": 6,
    "option": 6,
    "leftstick": 7,
    "lstick": 7,
    "ls": 7,
    "l3": 7,
    "rightstick": 8,
    "rstick": 8,
    "rs": 8,
    "r3": 8,
    "leftshoulder": 9,
    "leftbumper": 9,
    "lb": 9,
    "l1": 9,
    "rightshoulder": 10,
    "rightbumper": 10,
    "rb": 10,
    "r1": 10,
    "dpup": 11,
    "dpadup": 11,
    "hatup": 11,
    "up": 11,
    "dpdown": 12,
    "dpaddown": 12,
    "hatdown": 12,
    "down": 12,
    "dpleft": 13,
    "dpadleft": 13,
    "hatleft": 13,
    "left": 13,
    "dpright": 14,
    "dpadright": 14,
    "hatright": 14,
    "right": 14,
}

_JOY_AXIS_ALIASES = {
    "leftx": 0,
    "leftstickx": 0,
    "leftanalogx": 0,
    "lx": 0,
    "lefty": 1,
    "leftsticky": 1,
    "leftanalogy": 1,
    "ly": 1,
    "rightx": 2,
    "rightstickx": 2,
    "rightanalogx": 2,
    "rx": 2,
    "righty": 3,
    "rightsticky": 3,
    "rightanalogy": 3,
    "ry": 3,
    "lefttrigger": 4,
    "lefttriggervalue": 4,
    "ltrigger": 4,
    "lt": 4,
    "l2": 4,
    "righttrigger": 5,
    "righttriggervalue": 5,
    "rtrigger": 5,
    "rt": 5,
    "r2": 5,
}

_INPUT_EVENT_TYPE_ALIASES = {
    "key": {"key", "keyboard"},
    "mouse_button": {"mouse", "mousebutton", "button"},
    "joypad_button": {"joypadbutton", "joybutton", "gamepadbutton"},
    "joypad_axis": {"joypadaxis", "joyaxis", "gamepadaxis", "axis"},
}

_MODIFIER_ALIASES = {
    "shift": "shift",
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "option": "alt",
    "meta": "meta",
    "cmd": "meta",
    "command": "meta",
    "super": "meta",
    "commandorcontrol": "command_or_control",
}

_LOG_DIAGNOSTIC_RE = re.compile(r"^\s*(SCRIPT ERROR|USER ERROR|USER WARNING|ERROR|WARNING):\s*(.*)$")
_LOG_SOURCE_RE = re.compile(r"^\s*at:\s*(?P<source>.+?)\s*\((?P<path>.+?):(?P<line>\d+)\)\s*$")


class _GodotLogCollector:
    def __init__(self, *, tee: Any = None, max_events: int = 5000):
        self.tee = tee
        self.max_events = max(1, int(max_events))
        self._events: list[dict[str, Any]] = []
        self._lines: list[str] = []
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._started = time.monotonic()
        self._next_index = 0

    def start(self, stream: Any) -> None:
        self._thread = threading.Thread(target=self._read_loop, args=(stream,), daemon=True)
        self._thread.start()

    def close(self, timeout: float = 2.0) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def events(self, *, clear: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            events = [dict(event) for event in self._events]
            if clear:
                self._events.clear()
                self._lines.clear()
            return events

    def text(self) -> str:
        with self._lock:
            return "".join(self._lines)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._lines.clear()

    def _read_loop(self, stream: Any) -> None:
        try:
            for line in stream:
                self._write_tee(line)
                self._append_line(str(line))
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _write_tee(self, line: str) -> None:
        if self.tee is None:
            return
        try:
            if isinstance(self.tee, int):
                os.write(self.tee, line.encode("utf-8", errors="replace"))
            else:
                self.tee.write(line)
                flush = getattr(self.tee, "flush", None)
                if callable(flush):
                    flush()
        except Exception:
            pass

    def _append_line(self, line: str) -> None:
        event = _parse_log_line(line, index=self._next_index, elapsed_ms=(time.monotonic() - self._started) * 1000)
        self._next_index += 1
        with self._lock:
            self._lines.append(line)
            self._events.append(event)
            _attach_source_to_previous_diagnostic(self._events)
            while len(self._events) > self.max_events:
                self._events.pop(0)
            while len(self._lines) > self.max_events:
                self._lines.pop(0)


def _parse_log_line(line: str, *, index: int, elapsed_ms: float) -> dict[str, Any]:
    raw = line.rstrip("\r\n")
    event: dict[str, Any] = {
        "index": index,
        "elapsed_ms": round(elapsed_ms, 3),
        "severity": "info",
        "kind": "log",
        "message": raw,
        "raw": raw,
    }
    diagnostic = _LOG_DIAGNOSTIC_RE.match(raw)
    if diagnostic:
        kind = diagnostic.group(1)
        event["kind"] = kind
        event["severity"] = "warning" if "WARNING" in kind else "error"
        event["message"] = diagnostic.group(2).strip()
    source = _LOG_SOURCE_RE.match(raw)
    if source:
        event["kind"] = "source"
        event["source"] = source.group("source")
        event["path"] = source.group("path")
        event["line"] = int(source.group("line"))
    return event


def _attach_source_to_previous_diagnostic(events: list[dict[str, Any]]) -> None:
    if not events:
        return
    source_event = events[-1]
    if source_event.get("kind") != "source":
        return
    for event in reversed(events[:-1]):
        if event.get("severity") in {"error", "warning"} and "path" not in event:
            event["source"] = source_event.get("source", "")
            event["path"] = source_event.get("path", "")
            event["line"] = source_event.get("line", 0)
            return


def _log_event_matches(
    event: dict[str, Any],
    *,
    severity: str | None = None,
    kind: str | None = None,
    text: str | None = None,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> bool:
    if severity is not None and event.get("severity") != severity:
        return False
    if kind is not None and event.get("kind") != kind:
        return False
    if text is not None:
        needle = str(text)
        haystack = f"{event.get('message', '')}\n{event.get('raw', '')}"
        if needle not in haystack:
            return False
    return predicate is None or predicate(event)


class GodotPlaywrightError(RuntimeError):
    pass


class RpcError(GodotPlaywrightError):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"Godot RPC error {code}: {message}")
        self.code = code
        self.data = data


class GodotClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 9777, timeout: float = 5.0):
        self.host = host
        self.port = int(port)
        self.timeout = timeout
        self._next_id = 1
        self._log_collector: Any = None

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def rpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        request_id = self._next_id
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }
        response = self._request("POST", "/rpc", payload, timeout=timeout)
        if "error" in response:
            error = response["error"]
            raise RpcError(
                int(error.get("code", -32000)),
                str(error.get("message", "Unknown RPC error")),
                error.get("data"),
            )
        return response.get("result")

    def wait_for_ready(self, timeout: float = 15.0, interval: float = 0.1) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_error: BaseException | None = None
        while time.monotonic() < deadline:
            try:
                return self.health()
            except (OSError, GodotPlaywrightError) as exc:
                last_error = exc
                time.sleep(interval)
        raise GodotPlaywrightError(
            f"Godot Playwright server did not become ready on {self.host}:{self.port}"
        ) from last_error

    def engine_info(self) -> dict[str, Any]:
        return self.rpc("engine.info")

    def protocol_describe(
        self,
        *,
        include_methods: bool = True,
        include_domains: bool = True,
        include_features: bool = True,
    ) -> dict[str, Any]:
        return self.rpc(
            "protocol.describe",
            {
                "include_methods": include_methods,
                "include_domains": include_domains,
                "include_features": include_features,
            },
        )

    def wait_for_engine_info(
        self,
        expected: dict[str, Any] | None = None,
        *,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.engine_info()
            expected_ok = expected is None or _dict_contains(last, expected)
            predicate_ok = predicate is None or predicate(last)
            if expected_ok and predicate_ok:
                return last
            if time.monotonic() >= deadline:
                raise GodotPlaywrightError(
                    f"Timed out waiting for engine info expected={expected!r}; last={last!r}"
                )
            time.sleep(interval)

    def locator(self, selector: str | dict[str, Any], *, root: str | dict[str, Any] | None = None) -> "Locator":
        return Locator(self, selector, root=root)

    def get_by_role(
        self,
        role: str,
        *,
        name: str | None = None,
        name_contains: str | None = None,
        root: str | dict[str, Any] | None = None,
    ) -> "Locator":
        return Locator(self, _role_selector(role, name=name, name_contains=name_contains), root=root)

    def get_by_group(
        self,
        group: str,
        *,
        root: str | dict[str, Any] | None = None,
    ) -> "Locator":
        return Locator(self, _group_selector(group), root=root)

    def get_by_text(
        self,
        text: str,
        *,
        exact: bool = True,
        root: str | dict[str, Any] | None = None,
    ) -> "Locator":
        return Locator(self, _text_selector(text, exact=exact), root=root)

    def get_by_placeholder(
        self,
        text: str,
        *,
        exact: bool = True,
        root: str | dict[str, Any] | None = None,
    ) -> "Locator":
        return Locator(self, _property_text_selector("placeholder", text, exact=exact), root=root)

    def get_by_tooltip(
        self,
        text: str,
        *,
        exact: bool = True,
        root: str | dict[str, Any] | None = None,
    ) -> "Locator":
        return Locator(self, _property_text_selector("tooltip", text, exact=exact), root=root)

    def get_by_test_id(
        self,
        test_id: str,
        *,
        key: str = "test_id",
        root: str | dict[str, Any] | None = None,
    ) -> "Locator":
        return Locator(self, _test_id_selector(test_id, key=key), root=root)

    def inspector(
        self,
        selector: str | dict[str, Any] | None = None,
        *,
        path: str | None = None,
        resource_path: str | None = None,
        root: str | dict[str, Any] | None = None,
    ) -> "Inspector":
        return Inspector(self, selector=selector, path=path, resource_path=resource_path, root=root)

    def editor_locator(self, selector: str | dict[str, Any], *, root: str | dict[str, Any] | None = None) -> "Locator":
        return Locator(self, selector, root=root or "editor")

    def editor_get_by_role(
        self,
        role: str,
        *,
        name: str | None = None,
        name_contains: str | None = None,
        root: str | dict[str, Any] | None = None,
    ) -> "Locator":
        return Locator(self, _role_selector(role, name=name, name_contains=name_contains), root=root or "editor")

    def editor_get_by_group(
        self,
        group: str,
        *,
        root: str | dict[str, Any] | None = None,
    ) -> "Locator":
        return self.get_by_group(group, root=root or "editor")

    def editor_get_by_text(
        self,
        text: str,
        *,
        exact: bool = True,
        root: str | dict[str, Any] | None = None,
    ) -> "Locator":
        return self.get_by_text(text, exact=exact, root=root or "editor")

    def editor_get_by_tooltip(
        self,
        text: str,
        *,
        exact: bool = True,
        root: str | dict[str, Any] | None = None,
    ) -> "Locator":
        return self.get_by_tooltip(text, exact=exact, root=root or "editor")

    def editor_get_by_test_id(
        self,
        test_id: str,
        *,
        key: str = "test_id",
        root: str | dict[str, Any] | None = None,
    ) -> "Locator":
        return self.get_by_test_id(test_id, key=key, root=root or "editor")

    def snapshot(
        self,
        *,
        root: str | dict[str, Any] | None = None,
        max_depth: int = 8,
        include_properties: bool = False,
    ) -> dict[str, Any]:
        return self.rpc(
            "tree.snapshot",
            {
                "root": root or "edited",
                "max_depth": max_depth,
                "include_properties": include_properties,
            },
        )

    def editor_snapshot(
        self,
        *,
        max_depth: int = 8,
        include_properties: bool = False,
    ) -> dict[str, Any]:
        return self.snapshot(root="editor", max_depth=max_depth, include_properties=include_properties)

    def screenshot(self, path: str | Path) -> dict[str, Any]:
        return self.rpc("viewport.screenshot", {"path": str(path)})

    def wait_for_screenshot(
        self,
        path: str | Path,
        *,
        width: int | None = None,
        height: int | None = None,
        min_width: int | None = None,
        min_height: int | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.screenshot(path)
                if _screenshot_result_matches(
                    last,
                    width=width,
                    height=height,
                    min_width=min_width,
                    min_height=min_height,
                    require_file=True,
                ):
                    return last
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            if time.monotonic() >= deadline:
                detail = f"last_error={last_error!r}" if last_error is not None else f"last={last!r}"
                raise AssertionError(
                    "Expected viewport screenshot "
                    f"path={str(path)!r} width={width!r} height={height!r} "
                    f"min_width={min_width!r} min_height={min_height!r}; {detail}"
                )
            time.sleep(interval)

    def physics2d_point(
        self,
        x: float,
        y: float,
        *,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_results: int = 32,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "x": float(x),
            "y": float(y),
            "collide_with_bodies": collide_with_bodies,
            "collide_with_areas": collide_with_areas,
            "max_results": int(max_results),
        }
        if collision_mask is not None:
            params["collision_mask"] = int(collision_mask)
        return self.rpc("physics2d.point", params)

    def physics2d_ray(
        self,
        from_x: float,
        from_y: float,
        to_x: float,
        to_y: float,
        *,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "from_x": float(from_x),
            "from_y": float(from_y),
            "to_x": float(to_x),
            "to_y": float(to_y),
            "collide_with_bodies": collide_with_bodies,
            "collide_with_areas": collide_with_areas,
        }
        if collision_mask is not None:
            params["collision_mask"] = int(collision_mask)
        return self.rpc("physics2d.ray", params)

    def physics3d_point(
        self,
        x: float,
        y: float,
        z: float,
        *,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_results: int = 32,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "x": float(x),
            "y": float(y),
            "z": float(z),
            "collide_with_bodies": collide_with_bodies,
            "collide_with_areas": collide_with_areas,
            "max_results": int(max_results),
        }
        if collision_mask is not None:
            params["collision_mask"] = int(collision_mask)
        return self.rpc("physics3d.point", params)

    def physics3d_ray(
        self,
        from_x: float,
        from_y: float,
        from_z: float,
        to_x: float,
        to_y: float,
        to_z: float,
        *,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "from_x": float(from_x),
            "from_y": float(from_y),
            "from_z": float(from_z),
            "to_x": float(to_x),
            "to_y": float(to_y),
            "to_z": float(to_z),
            "collide_with_bodies": collide_with_bodies,
            "collide_with_areas": collide_with_areas,
        }
        if collision_mask is not None:
            params["collision_mask"] = int(collision_mask)
        return self.rpc("physics3d.ray", params)

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

    def camera3d_ray(
        self,
        screen_x: float,
        screen_y: float,
        *,
        camera: str | dict[str, Any] | None = None,
        root: str | dict[str, Any] | None = None,
        max_distance: float = 1000.0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "x": float(screen_x),
            "y": float(screen_y),
            "max_distance": float(max_distance),
        }
        if camera is not None:
            params["camera"] = camera
        if root is not None:
            params["root"] = root
        return self.rpc("camera3d.ray", params)

    def camera3d_pick(
        self,
        screen_x: float,
        screen_y: float,
        *,
        camera: str | dict[str, Any] | None = None,
        root: str | dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_distance: float = 1000.0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "x": float(screen_x),
            "y": float(screen_y),
            "collide_with_bodies": collide_with_bodies,
            "collide_with_areas": collide_with_areas,
            "max_distance": float(max_distance),
        }
        if camera is not None:
            params["camera"] = camera
        if root is not None:
            params["root"] = root
        if collision_mask is not None:
            params["collision_mask"] = int(collision_mask)
        return self.rpc("camera3d.pick", params)

    def viewport_info(self) -> dict[str, Any]:
        return self.rpc("viewport.info")

    def set_viewport_size(self, width: int, height: int) -> dict[str, Any]:
        return self.rpc("viewport.set_size", {"width": int(width), "height": int(height)})

    def wait_for_viewport_size(
        self,
        width: int,
        height: int,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.viewport_info()
            if _viewport_size_matches(last, width, height):
                return last
            if time.monotonic() >= deadline:
                raise GodotPlaywrightError(
                    f"Timed out waiting for viewport size {int(width)}x{int(height)}; last={last!r}"
                )
            time.sleep(interval)

    def evaluate(
        self,
        expression: str,
        variables: dict[str, Any] | None = None,
        *,
        root: str | dict[str, Any] | None = None,
        **inputs: Any,
    ) -> Any:
        result = self.rpc(
            "runtime.evaluate",
            {
                "root": root or "edited",
                "expression": expression,
                "variables": _merged_variables(variables, inputs),
            },
        )
        return result.get("value")

    def wait_for_function(
        self,
        expression: str,
        variables: dict[str, Any] | None = None,
        *,
        root: str | dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
        predicate: Callable[[Any], bool] | None = None,
        **inputs: Any,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last_value: Any = None
        while True:
            last_value = self.evaluate(expression, variables, root=root, **inputs)
            if predicate is not None:
                if predicate(last_value):
                    return last_value
            elif last_value:
                return last_value
            if time.monotonic() >= deadline:
                raise GodotPlaywrightError(
                    f"Timed out waiting for function {expression!r}; last value was {last_value!r}"
                )
            time.sleep(interval)

    def clock(self) -> dict[str, Any]:
        return self.rpc("runtime.clock")

    def pause(self) -> dict[str, Any]:
        return self.rpc("runtime.pause")

    def resume(self) -> dict[str, Any]:
        return self.rpc("runtime.resume")

    def step_frames(
        self,
        frames: int = 1,
        *,
        physics: bool = False,
        timeout: float = 5.0,
        interval: float = 0.01,
    ) -> dict[str, Any]:
        if frames < 0:
            raise ValueError("frames must be >= 0")
        scheduled = self.rpc("runtime.step_frames", {"frames": int(frames), "physics": bool(physics)})
        counter_name = "physics_frames" if physics else "process_frames"
        target = int(scheduled.get("target_frame", scheduled.get("step_target", 0)))
        deadline = time.monotonic() + timeout
        last = scheduled
        while True:
            last = self.clock()
            if int(last.get(counter_name, 0)) >= target and not bool(last.get("step_active", False)):
                result = dict(last)
                result["scheduled"] = scheduled
                return result
            if time.monotonic() >= deadline:
                raise GodotPlaywrightError(
                    f"Timed out stepping {frames} {counter_name} to {target}; last={last!r} scheduled={scheduled!r}"
                )
            time.sleep(interval)

    def sample_frames(
        self,
        frames: int,
        *,
        selectors: list[str | dict[str, Any]] | str | dict[str, Any] | None = None,
        expressions: list[str | dict[str, Any]] | dict[str, Any] | str | None = None,
        include_snapshot: bool = False,
        root: str | dict[str, Any] | None = None,
        max_depth: int = 8,
        include_properties: bool = False,
        physics: bool = False,
        timeout: float = 5.0,
        interval: float = 0.01,
        restore: bool = True,
    ) -> dict[str, Any]:
        if frames < 1:
            raise ValueError("frames must be >= 1")
        start = self.clock()
        was_paused = bool(start.get("paused", False))
        samples: list[dict[str, Any]] = []
        self.pause()
        try:
            params = {
                "frames": 1,
                "selectors": _frame_sample_sequence(selectors),
                "expressions": _frame_sample_expressions(expressions),
                "include_snapshot": include_snapshot,
                "root": root or "edited",
                "max_depth": max_depth,
                "include_properties": include_properties,
            }
            for index in range(frames):
                payload = self.rpc("runtime.sample_frames", params)
                for sample in payload.get("samples", []):
                    if isinstance(sample, dict):
                        sample = dict(sample)
                        sample["sample_index"] = len(samples)
                        samples.append(sample)
                if index < frames - 1:
                    self.step_frames(1, physics=physics, timeout=timeout, interval=interval)
        finally:
            if restore and not was_paused:
                self.resume()
        return {
            "samples": samples,
            "count": len(samples),
            "frames": int(frames),
            "physics": bool(physics),
            "started_paused": was_paused,
            "restored": bool(restore and not was_paused),
        }

    def wait_for_process_frames(
        self,
        frames: int = 1,
        *,
        timeout: float = 5.0,
        interval: float = 0.01,
    ) -> dict[str, Any]:
        return self._wait_for_clock_delta("process_frames", frames, timeout=timeout, interval=interval)

    def wait_for_physics_frames(
        self,
        frames: int = 1,
        *,
        timeout: float = 5.0,
        interval: float = 0.01,
    ) -> dict[str, Any]:
        return self._wait_for_clock_delta("physics_frames", frames, timeout=timeout, interval=interval)

    def wait_for_idle(
        self,
        frames: int = 2,
        *,
        timeout: float = 5.0,
        interval: float = 0.01,
    ) -> dict[str, Any]:
        return self.wait_for_process_frames(frames, timeout=timeout, interval=interval)

    def wait_for_timeout(self, milliseconds: int | float) -> dict[str, Any]:
        time.sleep(max(0.0, float(milliseconds)) / 1000.0)
        return self.clock()

    def log_events(
        self,
        *,
        severity: str | None = None,
        kind: str | None = None,
        text: str | None = None,
        clear: bool = False,
    ) -> list[dict[str, Any]]:
        if self._log_collector is None:
            return []
        events = [
            event
            for event in self._log_collector.events(clear=clear)
            if _log_event_matches(event, severity=severity, kind=kind, text=text)
        ]
        return events

    def log_text(self) -> str:
        if self._log_collector is None:
            return ""
        return str(self._log_collector.text())

    def log_clear(self) -> dict[str, Any]:
        if self._log_collector is not None:
            self._log_collector.clear()
        return {"cleared": True}

    def wait_for_log(
        self,
        text: str | None = None,
        *,
        severity: str | None = None,
        kind: str | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_events: list[dict[str, Any]] = []
        while True:
            last_events = self.log_events(severity=severity, kind=kind, text=text)
            for event in last_events:
                if predicate is None or predicate(event):
                    return event
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected Godot log text={text!r} severity={severity!r} kind={kind!r}; got {last_events!r}"
                )
            time.sleep(interval)

    def animation_describe(
        self,
        selector: str | dict[str, Any],
        *,
        root: str | dict[str, Any] | None = None,
        include_tracks: bool = False,
    ) -> dict[str, Any]:
        return self.rpc(
            "animation.describe",
            {
                "selector": selector,
                "root": root or "edited",
                "include_tracks": include_tracks,
            },
        )

    def animation_play(
        self,
        selector: str | dict[str, Any],
        animation: str = "",
        *,
        root: str | dict[str, Any] | None = None,
        blend: float = -1.0,
        speed: float = 1.0,
        from_end: bool = False,
        position: float | None = None,
        update: bool = True,
        update_only: bool = False,
        include_tracks: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "selector": selector,
            "root": root or "edited",
            "animation": animation,
            "blend": blend,
            "speed": speed,
            "from_end": from_end,
            "update": update,
            "update_only": update_only,
            "include_tracks": include_tracks,
        }
        if position is not None:
            params["position"] = position
        return self.rpc("animation.play", params)

    def animation_stop(
        self,
        selector: str | dict[str, Any],
        *,
        root: str | dict[str, Any] | None = None,
        keep_state: bool = False,
        include_tracks: bool = False,
    ) -> dict[str, Any]:
        return self.rpc(
            "animation.stop",
            {
                "selector": selector,
                "root": root or "edited",
                "keep_state": keep_state,
                "include_tracks": include_tracks,
            },
        )

    def animation_pause(
        self,
        selector: str | dict[str, Any],
        *,
        root: str | dict[str, Any] | None = None,
        include_tracks: bool = False,
    ) -> dict[str, Any]:
        return self.rpc(
            "animation.pause",
            {
                "selector": selector,
                "root": root or "edited",
                "include_tracks": include_tracks,
            },
        )

    def animation_seek(
        self,
        selector: str | dict[str, Any],
        position: float,
        *,
        root: str | dict[str, Any] | None = None,
        update: bool = True,
        update_only: bool = False,
        include_tracks: bool = False,
    ) -> dict[str, Any]:
        return self.rpc(
            "animation.seek",
            {
                "selector": selector,
                "root": root or "edited",
                "position": position,
                "update": update,
                "update_only": update_only,
                "include_tracks": include_tracks,
            },
        )

    def animation_advance(
        self,
        selector: str | dict[str, Any],
        delta: float,
        *,
        root: str | dict[str, Any] | None = None,
        update: bool = True,
        update_only: bool = False,
        include_tracks: bool = False,
    ) -> dict[str, Any]:
        return self.rpc(
            "animation.advance",
            {
                "selector": selector,
                "root": root or "edited",
                "delta": delta,
                "update": update,
                "update_only": update_only,
                "include_tracks": include_tracks,
            },
        )

    def _wait_for_clock_delta(
        self,
        counter_name: str,
        frames: int,
        *,
        timeout: float,
        interval: float,
    ) -> dict[str, Any]:
        if frames < 0:
            raise ValueError("frames must be >= 0")
        start = self.clock()
        start_value = int(start.get(counter_name, 0))
        target = start_value + frames
        deadline = time.monotonic() + timeout
        last = start
        while True:
            last = self.clock()
            if int(last.get(counter_name, 0)) >= target:
                return last
            if time.monotonic() >= deadline:
                raise GodotPlaywrightError(
                    f"Timed out waiting for {frames} {counter_name} from {start_value}; last={last!r}"
                )
            time.sleep(interval)

    def editor_status(self) -> dict[str, Any]:
        return self.rpc("editor.status")

    def editor_ui_status(self) -> dict[str, Any]:
        return self.rpc("editor.ui.status")

    def wait_for_editor_ui(
        self,
        expected: dict[str, Any] | None = None,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if expected is not None and not expected:
            raise ValueError("expected must not be empty")
        if expected is None:
            return self.editor_ui_status()
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.editor_ui_status()
            if _dict_contains(last, expected):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected editor UI status to include {expected!r}; last={last!r}")
            time.sleep(interval)

    def wait_for_editor_main_screen(
        self,
        name: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.editor_ui_status()
            if _editor_ui_main_screen_matches(last, name):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected editor main screen {name!r}; last={last!r}")
            time.sleep(interval)

    def editor_switch_main_screen(
        self,
        name: str,
        *,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc("editor.ui.switch_main_screen", {"name": name})
        if wait:
            result = dict(result)
            result["ui_state"] = self.wait_for_editor_main_screen(name, timeout=timeout, interval=interval)
        return result

    def editor_hide_bottom_panel(
        self,
        *,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc("editor.ui.hide_bottom_panel")
        if wait:
            result = dict(result)
            result["ui_state"] = self.wait_for_editor_ui(
                {"bottom_panel": {"can_hide": True}},
                timeout=timeout,
                interval=interval,
            )
        return result

    def editor_play(
        self,
        scene: str = "current",
        *,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected_scene = self._editor_play_wait_scene(scene) if wait else None
        result = self.rpc("editor.play", {"scene": scene})
        if wait:
            status = self.wait_for_editor_playing(expected_scene, timeout=timeout, interval=interval)
            result = dict(result)
            result.update(status)
            result["editor_status"] = status
        return result

    def editor_stop(
        self,
        *,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc("editor.stop")
        if wait:
            status = self.wait_for_editor_stopped(timeout=timeout, interval=interval)
            result = dict(result)
            result.update(status)
            result["editor_status"] = status
        return result

    def wait_for_editor_playing(
        self,
        scene: str | None = None,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.editor_status()
            playing_ok = bool(last.get("playing"))
            scene_ok = scene is None or _editor_value_matches(last.get("playing_scene", ""), scene)
            if playing_ok and scene_ok:
                return last
            if time.monotonic() >= deadline:
                detail = "" if scene is None else f" {scene!r}"
                raise GodotPlaywrightError(
                    f"Timed out waiting for editor to be playing{detail}; last status was {last!r}"
                )
            time.sleep(interval)

    def wait_for_editor_stopped(
        self,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.editor_status()
            if not bool(last.get("playing")):
                return last
            if time.monotonic() >= deadline:
                raise GodotPlaywrightError(f"Timed out waiting for editor to stop; last status was {last!r}")
            time.sleep(interval)

    def _editor_play_wait_scene(self, scene: str) -> str | None:
        if scene == "current":
            status = self.editor_status()
            return str(status.get("edited_scene_file_path") or "") or None
        if scene == "main":
            main_scene = self.project_main_scene()
            return str(main_scene.get("path") or "") or None
        return scene

    def editor_history(
        self,
        selector: str | dict[str, Any] | None = None,
        *,
        root: str | dict[str, Any] | None = None,
        history_id: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"root": root or "edited"}
        if selector is not None:
            params["selector"] = selector
        if history_id is not None:
            params["history_id"] = history_id
        return self.rpc("editor.history", params)

    def wait_for_editor_history(
        self,
        expected: dict[str, Any] | None = None,
        *,
        selector: str | dict[str, Any] | None = None,
        root: str | dict[str, Any] | None = None,
        history_id: int | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if expected is not None and not expected:
            raise ValueError("expected must not be empty")
        if expected is None:
            return self.editor_history(selector=selector, root=root or "edited", history_id=history_id)
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.editor_history(selector=selector, root=root or "edited", history_id=history_id)
            if _dict_contains(last, expected):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected editor history to include {expected!r}; last={last!r}")
            time.sleep(interval)

    def editor_undo(
        self,
        selector: str | dict[str, Any] | None = None,
        *,
        root: str | dict[str, Any] | None = None,
        history_id: int | None = None,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"root": root or "edited"}
        if selector is not None:
            params["selector"] = selector
        if history_id is not None:
            params["history_id"] = history_id
        result = self.rpc("editor.undo", params)
        if wait:
            result = dict(result)
            result["history_state"] = self.wait_for_editor_history(
                _editor_history_readback_expected(result),
                selector=selector,
                root=root or "edited",
                history_id=history_id,
                timeout=timeout,
                interval=interval,
            )
        return result

    def editor_redo(
        self,
        selector: str | dict[str, Any] | None = None,
        *,
        root: str | dict[str, Any] | None = None,
        history_id: int | None = None,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"root": root or "edited"}
        if selector is not None:
            params["selector"] = selector
        if history_id is not None:
            params["history_id"] = history_id
        result = self.rpc("editor.redo", params)
        if wait:
            result = dict(result)
            result["history_state"] = self.wait_for_editor_history(
                _editor_history_readback_expected(result),
                selector=selector,
                root=root or "edited",
                history_id=history_id,
                timeout=timeout,
                interval=interval,
            )
        return result

    def editor_selection(self) -> dict[str, Any]:
        return self.rpc("editor.selection.get")

    def wait_for_editor_selection(
        self,
        expected: int | str | list[str] | tuple[str, ...] | set[str] | None = None,
        *,
        exact: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if expected is None:
            return self.editor_selection()
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.editor_selection()
            if _editor_selection_matches(last, expected, exact=exact):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected editor selection {_editor_selection_expectation_summary(expected, exact=exact)}; "
                    f"last={last!r}"
                )
            time.sleep(interval)

    def editor_select(
        self,
        selector: str | dict[str, Any] | list[str | dict[str, Any]],
        *,
        root: str | dict[str, Any] | None = None,
        inspect: bool = False,
        property: str = "",
        inspector_only: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"root": root or "edited", "inspect": inspect, "property": property, "inspector_only": inspector_only}
        if isinstance(selector, list):
            params["selectors"] = selector
        else:
            params["selector"] = selector
        result = self.rpc("editor.selection.set", params)
        if wait:
            result = dict(result)
            result["selection_state"] = self.wait_for_editor_selection(
                _editor_selection_expected_from_selector(selector),
                exact=True,
                timeout=timeout,
                interval=interval,
            )
        return result

    def editor_inspect(
        self,
        selector: str | dict[str, Any] | None = None,
        *,
        path: str | None = None,
        resource_path: str | None = None,
        root: str | dict[str, Any] | None = None,
        property: str = "",
        inspector_only: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "root": root or "edited",
            "property": property,
            "inspector_only": inspector_only,
        }
        if selector is not None:
            params["selector"] = selector
        if path is not None:
            params["path"] = path
        if resource_path is not None:
            params["resource_path"] = resource_path
        result = self.rpc("editor.inspect", params)
        if wait:
            result = dict(result)
            result["inspector_state"] = self.inspector(
                selector,
                path=path,
                resource_path=resource_path,
                root=root,
            ).wait_for_description(
                properties=[property] if property else None,
                timeout=timeout,
                interval=interval,
            )
        return result

    def editor_inspector_describe(
        self,
        selector: str | dict[str, Any] | None = None,
        *,
        path: str | None = None,
        resource_path: str | None = None,
        root: str | dict[str, Any] | None = None,
        include_values: bool = True,
        properties: list[str] | None = None,
        name_contains: str = "",
        include_internal: bool = False,
    ) -> dict[str, Any]:
        return self.inspector(
            selector,
            path=path,
            resource_path=resource_path,
            root=root,
        ).describe(
            include_values=include_values,
            properties=properties,
            name_contains=name_contains,
            include_internal=include_internal,
        )

    def editor_inspector_get_property(
        self,
        property_name: str,
        selector: str | dict[str, Any] | None = None,
        *,
        path: str | None = None,
        resource_path: str | None = None,
        root: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.inspector(selector, path=path, resource_path=resource_path, root=root).get(property_name)

    def editor_inspector_set_property(
        self,
        property_name: str,
        value: Any,
        selector: str | dict[str, Any] | None = None,
        *,
        path: str | None = None,
        resource_path: str | None = None,
        root: str | dict[str, Any] | None = None,
        save: bool = False,
        inspect: bool = True,
        inspector_only: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.inspector(selector, path=path, resource_path=resource_path, root=root).set(
            property_name,
            value,
            save=save,
            inspect=inspect,
            inspector_only=inspector_only,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def editor_inspector_values(
        self,
        selector: str | dict[str, Any] | None = None,
        *,
        path: str | None = None,
        resource_path: str | None = None,
        root: str | dict[str, Any] | None = None,
        properties: list[str] | tuple[str, ...] | None = None,
        name_contains: str = "",
        include_internal: bool = False,
    ) -> dict[str, Any]:
        return self.inspector(selector, path=path, resource_path=resource_path, root=root).values(
            properties=properties,
            name_contains=name_contains,
            include_internal=include_internal,
        )

    def editor_inspector_set_properties(
        self,
        values: dict[str, Any],
        selector: str | dict[str, Any] | None = None,
        *,
        path: str | None = None,
        resource_path: str | None = None,
        root: str | dict[str, Any] | None = None,
        save: bool = False,
        inspect: bool = True,
        inspector_only: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.inspector(selector, path=path, resource_path=resource_path, root=root).set_properties(
            values,
            save=save,
            inspect=inspect,
            inspector_only=inspector_only,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def editor_open_script(
        self,
        path: str,
        *,
        line: int = -1,
        column: int = 0,
        grab_focus: bool = True,
        force: bool = False,
        restore_external_editor: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "path": path,
            "line": line,
            "column": column,
            "grab_focus": grab_focus,
        }
        if force:
            params["force"] = force
        if restore_external_editor:
            params["restore_external_editor"] = restore_external_editor
        result = self.rpc("editor.script.open", params)
        if wait:
            result = dict(result)
            result["script_state"] = self.wait_for_script(path, timeout=timeout, interval=interval)
            if bool(result.get("opened", True)):
                result["script_editor"] = self.wait_for_editor_script(
                    path,
                    current=grab_focus,
                    timeout=timeout,
                    interval=interval,
                )
            elif "script_editor" not in result:
                result["script_editor"] = self.editor_script_status()
        return result

    def editor_script_status(self) -> dict[str, Any]:
        return self.rpc("editor.script.status")

    def wait_for_editor_script(
        self,
        path: str,
        *,
        current: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.editor_script_status()
            open_paths = [str(item) for item in last.get("open_paths", [])]
            open_ok = path in open_paths
            current_ok = not current or str(last.get("current_path", "")) == path
            if open_ok and current_ok:
                return last
            if time.monotonic() >= deadline:
                raise GodotPlaywrightError(
                    f"Timed out waiting for editor script {path!r} current={current!r}; "
                    f"open_paths={open_paths!r} current_path={last.get('current_path', '')!r} last={last!r}"
                )
            time.sleep(interval)

    def editor_script_describe(
        self,
        path: str,
        *,
        include_source: bool = False,
    ) -> dict[str, Any]:
        return self.rpc("editor.script.describe", {"path": path, "include_source": include_source})

    def script_file_describe(
        self,
        path: str,
        *,
        include_source: bool = False,
    ) -> dict[str, Any]:
        return self.rpc("script.file.describe", {"path": path, "include_source": include_source})

    def script_classes(
        self,
        *,
        path: str = "res://",
        class_name: str = "",
        name_contains: str = "",
        extends: str = "",
        base_class: str = "",
        include_anonymous: bool = False,
        recursive: bool = True,
        include_hidden: bool = False,
        max_results: int = 200,
        max_scan_results: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "path": path,
            "class_name": class_name,
            "name_contains": name_contains,
            "extends": extends,
            "base_class": base_class,
            "include_anonymous": include_anonymous,
            "recursive": recursive,
            "include_hidden": include_hidden,
            "max_results": int(max_results),
        }
        if max_scan_results is not None:
            params["max_scan_results"] = int(max_scan_results)
        return self.rpc("script.classes", params)

    def wait_for_script(
        self,
        path: str,
        *,
        extends: str | None = None,
        functions: list[str] | tuple[str, ...] | None = None,
        source_contains: str | list[str] | tuple[str, ...] | None = None,
        include_source: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected_functions = list(functions or [])
        expected_source = _string_list(source_contains)
        include_source = include_source or bool(expected_source)
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.script_file_describe(path, include_source=include_source)
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                extends_ok = extends is None or _script_extends(last) == extends
                function_names = _script_function_names(last)
                functions_ok = all(name in function_names for name in expected_functions)
                source = str(last.get("source", ""))
                source_ok = all(text in source for text in expected_source)
                if extends_ok and functions_ok and source_ok:
                    return last
            if time.monotonic() >= deadline:
                raise GodotPlaywrightError(
                    f"Timed out waiting for script {path!r} extends={extends!r} "
                    f"functions={expected_functions!r} source_contains={expected_source!r}; "
                    f"last={last!r} error={last_error!r}"
                )
            time.sleep(interval)

    def editor_scan_filesystem(
        self,
        paths: str | list[str] | None = None,
        *,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if paths is None:
            return self.rpc("editor.filesystem.scan")
        if isinstance(paths, str):
            result = self.rpc("editor.filesystem.scan", {"path": paths})
            if wait:
                result = dict(result)
                result["filesystem_state"] = self.wait_for_editor_filesystem_entry(
                    paths,
                    timeout=timeout,
                    interval=interval,
                )
            return result
        result = self.rpc("editor.filesystem.scan", {"paths": paths})
        if wait:
            result = dict(result)
            result["filesystem_states"] = {
                path: self.wait_for_editor_filesystem_entry(
                    path,
                    timeout=timeout,
                    interval=interval,
                )
                for path in paths
            }
        return result

    def editor_filesystem_describe(self, path: str) -> dict[str, Any]:
        return self.rpc("editor.filesystem.describe", {"path": path})

    def editor_filesystem_find(
        self,
        path: str = "res://",
        *,
        recursive: bool = True,
        include_dirs: bool = False,
        include_hidden: bool = False,
        name: str = "",
        name_contains: str = "",
        extension: str = "",
        resource_type: str = "",
        max_results: int = 500,
    ) -> dict[str, Any]:
        return self.rpc(
            "editor.filesystem.find",
            {
                "path": path,
                "recursive": recursive,
                "include_dirs": include_dirs,
                "include_hidden": include_hidden,
                "name": name,
                "name_contains": name_contains,
                "extension": extension,
                "resource_type": resource_type,
                "max_results": max_results,
            },
        )

    def wait_for_editor_filesystem_entry(
        self,
        path: str,
        *,
        resource_type: str | None = None,
        kind: str | None = None,
        is_file: bool | None = None,
        is_directory: bool | None = None,
        selected: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.editor_filesystem_describe(path)
            if _editor_filesystem_entry_matches(
                last,
                resource_type=resource_type,
                kind=kind,
                is_file=is_file,
                is_directory=is_directory,
                selected=selected,
            ):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected editor filesystem entry {path!r}"
                    f"{_editor_filesystem_filter_summary(resource_type=resource_type, kind=kind, is_file=is_file, is_directory=is_directory, selected=selected)}; "
                    f"last={last!r}"
                )
            time.sleep(interval)

    def wait_for_editor_filesystem_selection(
        self,
        path: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.wait_for_editor_filesystem_entry(
            path,
            selected=True,
            timeout=timeout,
            interval=interval,
        )

    def wait_for_editor_filesystem_missing(
        self,
        path: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.editor_filesystem_describe(path)
            if not bool(last.get("exists")):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected editor filesystem entry {path!r} to be missing; last={last!r}")
            time.sleep(interval)

    def wait_for_editor_filesystem_find(
        self,
        path: str = "res://",
        *,
        recursive: bool = True,
        include_dirs: bool = False,
        include_hidden: bool = False,
        name: str = "",
        name_contains: str = "",
        extension: str = "",
        resource_type: str = "",
        min_count: int = 1,
        max_count: int | None = None,
        max_results: int = 500,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if min_count < 0:
            raise ValueError("min_count must be >= 0")
        if max_count is not None:
            if max_count < 0:
                raise ValueError("max_count must be >= 0")
            if max_count < min_count:
                raise ValueError("max_count must be >= min_count")
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.editor_filesystem_find(
                path,
                recursive=recursive,
                include_dirs=include_dirs,
                include_hidden=include_hidden,
                name=name,
                name_contains=name_contains,
                extension=extension,
                resource_type=resource_type,
                max_results=max_results,
            )
            count = _editor_filesystem_find_count(last)
            if count >= min_count and (max_count is None or count <= max_count):
                return last
            if time.monotonic() >= deadline:
                expected_count = (
                    f"to have at least {min_count} entries"
                    if max_count is None
                    else f"to have between {min_count} and {max_count} entries"
                )
                raise AssertionError(
                    f"Expected editor filesystem search {path!r}"
                    f"{_editor_filesystem_filter_summary(resource_type=resource_type)} "
                    f"name={name!r} name_contains={name_contains!r} extension={extension!r} "
                    f"{expected_count}; got {count}: {last.get('entries', [])!r}"
                )
            time.sleep(interval)

    def editor_filesystem_select(
        self,
        path: str,
        *,
        inspect: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc("editor.filesystem.select", {"path": path, "inspect": inspect})
        if wait:
            result = dict(result)
            result["filesystem_state"] = self.wait_for_editor_filesystem_selection(
                path,
                timeout=timeout,
                interval=interval,
            )
        return result

    def editor_filesystem_open(
        self,
        path: str,
        *,
        mode: str = "auto",
        line: int = -1,
        column: int = 0,
        grab_focus: bool = True,
        force: bool = False,
        restore_external_editor: bool = False,
        property: str = "",
        inspector_only: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "path": path,
            "mode": mode,
            "line": line,
            "column": column,
            "grab_focus": grab_focus,
            "property": property,
            "inspector_only": inspector_only,
        }
        if force:
            params["force"] = force
        if restore_external_editor:
            params["restore_external_editor"] = restore_external_editor
        result = self.rpc("editor.filesystem.open", params)
        if wait:
            result = dict(result)
            result["filesystem_state"] = self.wait_for_editor_filesystem_selection(
                path,
                timeout=timeout,
                interval=interval,
            )
            action = str(result.get("action", ""))
            if action == "scene":
                result["editor_status"] = self.wait_for_editor_scene(path, timeout=timeout, interval=interval)
            elif action == "script":
                result["script_state"] = self.wait_for_script(path, timeout=timeout, interval=interval)
                script_result = result.get("script", {})
                if isinstance(script_result, dict) and bool(script_result.get("opened", True)):
                    result["script_editor"] = self.wait_for_editor_script(
                        path,
                        current=grab_focus,
                        timeout=timeout,
                        interval=interval,
                    )
                elif isinstance(script_result, dict) and "script_editor" in script_result:
                    result["script_editor"] = script_result["script_editor"]
            elif action in {"resource", "inspect"} and bool(result.get("inspected", False)):
                result["inspector_state"] = self.inspector(resource_path=path).wait_for_description(
                    properties=[property] if property else None,
                    timeout=timeout,
                    interval=interval,
                )
        return result

    def fs_exists(self, path: str) -> dict[str, Any]:
        return self.rpc("fs.exists", {"path": path})

    def fs_info(self, path: str) -> dict[str, Any]:
        return self.rpc("fs.info", {"path": path})

    def fs_read_text(self, path: str) -> str:
        result = self.rpc("fs.read_text", {"path": path})
        return str(result.get("text", ""))

    def fs_write_text(
        self,
        path: str,
        text: str,
        *,
        overwrite: bool = True,
        create_dirs: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc(
            "fs.write_text",
            {
                "path": path,
                "text": text,
                "overwrite": overwrite,
                "create_dirs": create_dirs,
            },
        )
        if wait:
            result = dict(result)
            result.update(self._post_write_file_evidence(path, timeout=timeout, interval=interval))
            result["text"] = self._wait_for_text_file(path, text, timeout=timeout, interval=interval)
        return result

    def fs_replace_text(
        self,
        path: str,
        old_text: str,
        new_text: str,
        *,
        expected_replacements: int = 1,
        case_sensitive: bool = True,
        max_replacements: int = 0,
        dry_run: bool = False,
        require_text_file: bool = True,
        max_preview: int = 20,
        include_text: bool | None = None,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc(
            "fs.replace_text",
            {
                "path": path,
                "old_text": old_text,
                "new_text": new_text,
                "expected_replacements": expected_replacements,
                "case_sensitive": case_sensitive,
                "max_replacements": max_replacements,
                "dry_run": dry_run,
                "require_text_file": require_text_file,
                "max_preview": max_preview,
                "include_text": wait if include_text is None else include_text,
            },
        )
        if wait and not dry_run:
            result = dict(result)
            result.update(self._post_write_file_evidence(path, timeout=timeout, interval=interval))
            if "text" in result:
                result["text"] = self._wait_for_text_file(
                    path,
                    str(result["text"]),
                    timeout=timeout,
                    interval=interval,
                )
        return result

    def fs_replace_text_many(
        self,
        old_text: str,
        new_text: str,
        path: str = "res://",
        *,
        expected_files: int = -1,
        expected_replacements: int = -1,
        case_sensitive: bool = True,
        recursive: bool = True,
        include_hidden: bool = False,
        include_binary: bool = False,
        name: str = "",
        name_contains: str = "",
        extension: str = "",
        resource_type: str = "",
        dry_run: bool = True,
        max_files: int = 500,
        max_replacements_per_file: int = 100,
        max_total_replacements: int = 500,
        max_preview: int = 20,
        include_text: bool | None = None,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc(
            "fs.replace_text_many",
            {
                "path": path,
                "old_text": old_text,
                "new_text": new_text,
                "expected_files": expected_files,
                "expected_replacements": expected_replacements,
                "case_sensitive": case_sensitive,
                "recursive": recursive,
                "include_hidden": include_hidden,
                "include_binary": include_binary,
                "name": name,
                "name_contains": name_contains,
                "extension": extension,
                "resource_type": resource_type,
                "dry_run": dry_run,
                "max_files": max_files,
                "max_replacements_per_file": max_replacements_per_file,
                "max_total_replacements": max_total_replacements,
                "max_preview": max_preview,
                "include_text": wait if include_text is None else include_text,
            },
        )
        if wait and not dry_run:
            result = dict(result)
            verified_changes: list[dict[str, Any]] = []
            for change in result.get("changes", []):
                if not isinstance(change, dict):
                    continue
                path_value = str(change.get("path", ""))
                verified = dict(change)
                verified.update(self._post_write_file_evidence(path_value, timeout=timeout, interval=interval))
                if "text" in verified:
                    verified["text"] = self._wait_for_text_file(
                        path_value,
                        str(verified["text"]),
                        timeout=timeout,
                        interval=interval,
                    )
                verified_changes.append(verified)
            result["changes"] = verified_changes
        return result

    def fs_read_bytes(self, path: str, *, max_bytes: int = 0) -> bytes:
        result = self.rpc("fs.read_bytes", {"path": path, "max_bytes": max_bytes})
        return base64.b64decode(str(result.get("base64", "")))

    def fs_write_bytes(
        self,
        path: str,
        data: bytes | bytearray | memoryview,
        *,
        overwrite: bool = True,
        create_dirs: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        raw = bytes(data)
        result = self.rpc(
            "fs.write_bytes",
            {
                "path": path,
                "base64": base64.b64encode(raw).decode("ascii"),
                "overwrite": overwrite,
                "create_dirs": create_dirs,
            },
        )
        if wait:
            result = dict(result)
            result.update(self._post_write_file_evidence(path, timeout=timeout, interval=interval))
        return result

    def write_script(
        self,
        path: str,
        source: str,
        *,
        overwrite: bool = True,
        create_dirs: bool = True,
        extends: str | None = None,
        functions: list[str] | tuple[str, ...] | None = None,
        source_contains: str | list[str] | tuple[str, ...] | None = None,
        open_editor: bool = False,
        line: int = -1,
        column: int = 0,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.fs_write_text(
            path,
            source,
            overwrite=overwrite,
            create_dirs=create_dirs,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )
        if wait:
            result = dict(result)
            if path.startswith("res://"):
                result["editor_filesystem"] = self.wait_for_editor_filesystem_entry(
                    path,
                    resource_type="GDScript",
                    is_file=True,
                    timeout=timeout,
                    interval=interval,
                )
            result["script"] = self.wait_for_script(
                path,
                extends=extends,
                functions=functions,
                source_contains=source_contains,
                include_source=source_contains is not None,
                timeout=timeout,
                interval=interval,
            )
            if open_editor:
                result["opened_script"] = self.editor_open_script(
                    path,
                    line=line,
                    column=column,
                    timeout=timeout,
                    interval=interval,
                )
        return result

    def _post_write_file_evidence(self, path: str, *, timeout: float, interval: float) -> dict[str, Any]:
        evidence: dict[str, Any] = {"file": self.wait_for_file(path, timeout=timeout, interval=interval)}
        if path.startswith("res://"):
            try:
                evidence["editor_filesystem_scan"] = self.editor_scan_filesystem(path, timeout=timeout, interval=interval)
                evidence["editor_filesystem"] = self.wait_for_editor_filesystem_entry(
                    path,
                    is_file=True,
                    timeout=timeout,
                    interval=interval,
                )
            except GodotPlaywrightError as exc:
                evidence["editor_filesystem_error"] = str(exc)
        return evidence

    def _wait_for_text_file(
        self,
        path: str,
        expected: str,
        *,
        timeout: float,
        interval: float,
    ) -> str:
        deadline = time.monotonic() + timeout
        last = ""
        while True:
            last = self.fs_read_text(path)
            if last == expected:
                return last
            if time.monotonic() >= deadline:
                raise GodotPlaywrightError(
                    f"Timed out waiting for filesystem text {path!r} to match written content; last={last!r}"
                )
            time.sleep(interval)

    def fs_mkdir(
        self,
        path: str,
        *,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc("fs.mkdir", {"path": path})
        if wait:
            result = dict(result)
            result["directory"] = self.wait_for_directory(path, timeout=timeout, interval=interval)
            if path.startswith("res://"):
                try:
                    result["editor_filesystem_scan"] = self.editor_scan_filesystem(path, timeout=timeout, interval=interval)
                    result["editor_filesystem"] = self.wait_for_editor_filesystem_entry(
                        path,
                        is_directory=True,
                        timeout=timeout,
                        interval=interval,
                    )
                except GodotPlaywrightError as exc:
                    result["editor_filesystem_error"] = str(exc)
        return result

    def fs_list(self, path: str = "res://", *, include_hidden: bool = False) -> dict[str, Any]:
        return self.rpc("fs.list", {"path": path, "include_hidden": include_hidden})

    def fs_find(
        self,
        path: str = "res://",
        *,
        recursive: bool = True,
        include_dirs: bool = False,
        include_hidden: bool = False,
        name: str = "",
        name_contains: str = "",
        extension: str = "",
        resource_type: str = "",
        max_results: int = 500,
    ) -> dict[str, Any]:
        return self.rpc(
            "fs.find",
            {
                "path": path,
                "recursive": recursive,
                "include_dirs": include_dirs,
                "include_hidden": include_hidden,
                "name": name,
                "name_contains": name_contains,
                "extension": extension,
                "resource_type": resource_type,
                "max_results": max_results,
            },
        )

    def fs_grep(
        self,
        query: str,
        path: str = "res://",
        *,
        case_sensitive: bool = True,
        recursive: bool = True,
        include_hidden: bool = False,
        include_binary: bool = False,
        name: str = "",
        name_contains: str = "",
        extension: str = "",
        resource_type: str = "",
        context_lines: int = 0,
        max_files: int = 500,
        max_results: int = 500,
        max_matches_per_file: int = 20,
    ) -> dict[str, Any]:
        return self.rpc(
            "fs.grep",
            {
                "path": path,
                "query": query,
                "case_sensitive": case_sensitive,
                "recursive": recursive,
                "include_hidden": include_hidden,
                "include_binary": include_binary,
                "name": name,
                "name_contains": name_contains,
                "extension": extension,
                "resource_type": resource_type,
                "context_lines": context_lines,
                "max_files": max_files,
                "max_results": max_results,
                "max_matches_per_file": max_matches_per_file,
            },
        )

    def fs_copy(
        self,
        source: str,
        destination: str,
        *,
        overwrite: bool = True,
        create_dirs: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc(
            "fs.copy",
            {
                "source": source,
                "destination": destination,
                "overwrite": overwrite,
                "create_dirs": create_dirs,
            },
        )
        if wait:
            result = dict(result)
            result["source_state"] = self.wait_for_file(source, timeout=timeout, interval=interval)
            result.update(
                self._post_relocate_fs_evidence(
                    source,
                    destination,
                    destination_type=str(result.get("type", "file")),
                    source_missing=False,
                    timeout=timeout,
                    interval=interval,
                )
            )
        return result

    def fs_move(
        self,
        source: str,
        destination: str,
        *,
        overwrite: bool = True,
        create_dirs: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc(
            "fs.move",
            {
                "source": source,
                "destination": destination,
                "overwrite": overwrite,
                "create_dirs": create_dirs,
            },
        )
        if wait:
            result = dict(result)
            result["source_missing"] = self.wait_for_fs_path(
                source,
                state="missing",
                timeout=timeout,
                interval=interval,
            )
            result.update(
                self._post_relocate_fs_evidence(
                    source,
                    destination,
                    destination_type=str(result.get("type", "any")),
                    source_missing=True,
                    timeout=timeout,
                    interval=interval,
                )
            )
        return result

    def _post_relocate_fs_evidence(
        self,
        source: str,
        destination: str,
        *,
        destination_type: str,
        source_missing: bool,
        timeout: float,
        interval: float,
    ) -> dict[str, Any]:
        path_type = destination_type if destination_type in {"file", "directory"} else None
        evidence: dict[str, Any] = {
            "destination_state": self.wait_for_fs_path(
                destination,
                path_type=path_type,
                timeout=timeout,
                interval=interval,
            )
        }
        if source.startswith("res://") or destination.startswith("res://"):
            try:
                evidence["editor_filesystem_scan"] = self.editor_scan_filesystem(
                    [_res_parent_path(source), destination],
                    timeout=timeout,
                    interval=interval,
                )
                if path_type == "directory":
                    evidence["editor_destination"] = self.wait_for_editor_filesystem_entry(
                        destination,
                        is_directory=True,
                        timeout=timeout,
                        interval=interval,
                    )
                else:
                    evidence["editor_destination"] = self.wait_for_editor_filesystem_entry(
                        destination,
                        is_file=True,
                        timeout=timeout,
                        interval=interval,
                    )
                if source_missing:
                    evidence["editor_source"] = self.wait_for_editor_filesystem_missing(
                        source,
                        timeout=timeout,
                        interval=interval,
                    )
                else:
                    evidence["editor_source"] = self.wait_for_editor_filesystem_entry(
                        source,
                        is_file=True,
                        timeout=timeout,
                        interval=interval,
                    )
            except GodotPlaywrightError as exc:
                evidence["editor_filesystem_error"] = str(exc)
        return evidence

    def fs_delete(
        self,
        path: str,
        *,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc("fs.delete", {"path": path})
        if wait:
            result = dict(result)
            result["missing"] = self.wait_for_fs_path(path, state="missing", timeout=timeout, interval=interval)
            if path.startswith("res://"):
                try:
                    result["editor_filesystem_scan"] = self.editor_scan_filesystem(
                        _res_parent_path(path),
                        timeout=timeout,
                        interval=interval,
                    )
                    result["editor_filesystem"] = self.wait_for_editor_filesystem_missing(
                        path,
                        timeout=timeout,
                        interval=interval,
                    )
                except GodotPlaywrightError as exc:
                    result["editor_filesystem_error"] = str(exc)
        return result

    def wait_for_fs_path(
        self,
        path: str,
        *,
        state: str = "exists",
        path_type: str | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if state not in {"exists", "missing"}:
            raise ValueError("state must be 'exists' or 'missing'")
        if path_type not in {None, "any", "file", "directory"}:
            raise ValueError("path_type must be None, 'any', 'file', or 'directory'")
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.fs_exists(path)
            if _fs_path_matches(last, state=state, path_type=path_type):
                return last
            if time.monotonic() >= deadline:
                type_detail = "" if path_type in {None, "any"} else f" {path_type}"
                raise GodotPlaywrightError(
                    f"Timed out waiting for filesystem path {path!r} to be {state}{type_detail}; last={last!r}"
                )
            time.sleep(interval)

    def wait_for_file(self, path: str, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self.wait_for_fs_path(path, path_type="file", timeout=timeout, interval=interval)

    def wait_for_directory(self, path: str, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self.wait_for_fs_path(path, path_type="directory", timeout=timeout, interval=interval)

    def wait_for_files(
        self,
        paths: list[str] | tuple[str, ...] | set[str],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected = [str(path) for path in paths]
        deadline = time.monotonic() + timeout
        last_entries: list[dict[str, Any]] = []
        while True:
            last_entries = [self.fs_exists(path) for path in expected]
            if all(_fs_path_matches(entry, state="exists", path_type="file") for entry in last_entries):
                return {"paths": expected, "entries": last_entries, "count": len(last_entries)}
            if time.monotonic() >= deadline:
                missing = [entry for entry in last_entries if not _fs_path_matches(entry, state="exists", path_type="file")]
                raise GodotPlaywrightError(f"Timed out waiting for files {expected!r}; missing={missing!r}")
            time.sleep(interval)

    def resource_save(
        self,
        path: str,
        *,
        class_name: str = "Resource",
        properties: dict[str, Any] | None = None,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected_properties = properties or {}
        readback_properties = _resource_readback_expected_properties(expected_properties)
        result = self.rpc(
            "resource.save",
            {
                "path": path,
                "class": class_name,
                "properties": expected_properties,
            },
        )
        if wait:
            result = dict(result)
            saved_path = str(result.get("path") or path)
            if saved_path.startswith("res://"):
                result["file"] = self.wait_for_file(saved_path, timeout=timeout, interval=interval)
            result["resource"] = self.wait_for_resource(
                saved_path,
                class_name=class_name,
                properties=readback_properties,
                timeout=timeout,
                interval=interval,
            )
            if saved_path.startswith("res://"):
                try:
                    result["editor_filesystem_scan"] = self.editor_scan_filesystem(
                        saved_path,
                        timeout=timeout,
                        interval=interval,
                    )
                    result["editor_filesystem"] = self.wait_for_editor_filesystem_entry(
                        saved_path,
                        is_file=True,
                        timeout=timeout,
                        interval=interval,
                    )
                except GodotPlaywrightError as exc:
                    result["editor_filesystem_error"] = str(exc)
        return result

    def resource_set_properties(
        self,
        path: str,
        properties: dict[str, Any],
        *,
        type_hint: str = "",
        save: bool = True,
        require_existing_properties: bool = True,
        inspect: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc(
            "resource.set_properties",
            {
                "path": path,
                "properties": properties,
                "type_hint": type_hint,
                "save": save,
                "require_existing_properties": require_existing_properties,
                "inspect": inspect,
            },
        )
        if wait:
            result = dict(result)
            resource_class = str(result.get("class", "")) or None
            readback_properties = _resource_readback_expected_properties(properties)
            result["resource"] = self.wait_for_resource(
                path,
                class_name=resource_class,
                properties=readback_properties,
                type_hint=type_hint,
                timeout=timeout,
                interval=interval,
            )
            if save and path.startswith("res://"):
                result["file"] = self.wait_for_file(path, timeout=timeout, interval=interval)
                try:
                    result["editor_filesystem_scan"] = self.editor_scan_filesystem(
                        path,
                        timeout=timeout,
                        interval=interval,
                    )
                    result["editor_filesystem"] = self.wait_for_editor_filesystem_entry(
                        path,
                        is_file=True,
                        timeout=timeout,
                        interval=interval,
                    )
                except GodotPlaywrightError as exc:
                    result["editor_filesystem_error"] = str(exc)
        return result

    def resource_duplicate(
        self,
        source: str,
        destination: str,
        *,
        properties: dict[str, Any] | None = None,
        type_hint: str = "",
        deep: bool = True,
        overwrite: bool = True,
        require_existing_properties: bool = True,
        inspect: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected_properties = properties or {}
        readback_properties = _resource_readback_expected_properties(expected_properties)
        result = self.rpc(
            "resource.duplicate",
            {
                "source": source,
                "destination": destination,
                "properties": expected_properties,
                "type_hint": type_hint,
                "deep": deep,
                "overwrite": overwrite,
                "require_existing_properties": require_existing_properties,
                "inspect": inspect,
            },
        )
        if wait:
            result = dict(result)
            resource_class = str(result.get("class", "")) or None
            result["source_resource"] = self.resource_inspect(
                source,
                include_properties=bool(expected_properties),
                properties=list(expected_properties),
                type_hint=type_hint,
            )
            result["resource"] = self.wait_for_resource(
                destination,
                class_name=resource_class,
                properties=readback_properties,
                type_hint=type_hint,
                timeout=timeout,
                interval=interval,
            )
            if destination.startswith("res://"):
                result["file"] = self.wait_for_file(destination, timeout=timeout, interval=interval)
                try:
                    result["editor_filesystem_scan"] = self.editor_scan_filesystem(
                        destination,
                        timeout=timeout,
                        interval=interval,
                    )
                    result["editor_filesystem"] = self.wait_for_editor_filesystem_entry(
                        destination,
                        is_file=True,
                        timeout=timeout,
                        interval=interval,
                    )
                except GodotPlaywrightError as exc:
                    result["editor_filesystem_error"] = str(exc)
        return result

    def resource_inspect(
        self,
        path: str,
        *,
        include_properties: bool = False,
        properties: list[str] | None = None,
        type_hint: str = "",
    ) -> dict[str, Any]:
        return self.rpc(
            "resource.inspect",
            {
                "path": path,
                "include_properties": include_properties,
                "properties": properties or [],
                "type_hint": type_hint,
            },
        )

    def resource_files(
        self,
        path: str = "res://",
        *,
        name: str = "",
        name_contains: str = "",
        resource_name: str = "",
        class_name: str = "",
        extensions: list[str] | tuple[str, ...] | str | None = None,
        include_dependencies: bool = True,
        include_properties: bool = False,
        recursive: bool = True,
        include_hidden: bool = False,
        max_results: int = 200,
        max_scan_results: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "path": path,
            "name": name,
            "name_contains": name_contains,
            "resource_name": resource_name,
            "class_name": class_name,
            "include_dependencies": include_dependencies,
            "include_properties": include_properties,
            "recursive": recursive,
            "include_hidden": include_hidden,
            "max_results": int(max_results),
        }
        if extensions is not None:
            params["extensions"] = [extensions] if isinstance(extensions, str) else list(extensions)
        if max_scan_results is not None:
            params["max_scan_results"] = int(max_scan_results)
        return self.rpc("resource.files", params)

    def resource_file_describe(
        self,
        path: str,
        *,
        include_properties: bool = True,
        include_resources: bool = True,
        include_dependencies: bool = True,
        include_source: bool = False,
    ) -> dict[str, Any]:
        return self.rpc(
            "resource.file.describe",
            {
                "path": path,
                "include_properties": include_properties,
                "include_resources": include_resources,
                "include_dependencies": include_dependencies,
                "include_source": include_source,
            },
        )

    def resource_class_describe(
        self,
        class_name: str = "Resource",
        *,
        include_values: bool = True,
        include_internal: bool = False,
        storage_only: bool = False,
        properties: list[str] | tuple[str, ...] | None = None,
        name_contains: str = "",
    ) -> dict[str, Any]:
        return self.rpc(
            "resource.class.describe",
            {
                "class": class_name,
                "include_values": include_values,
                "include_internal": include_internal,
                "storage_only": storage_only,
                "properties": list(properties or []),
                "name_contains": name_contains,
            },
        )

    def resource_schema(self, class_name: str = "Resource", **kwargs: Any) -> dict[str, Any]:
        return self.resource_class_describe(class_name, **kwargs)

    def resource_classes(
        self,
        *,
        base_class: str = "Resource",
        name_contains: str = "",
        include_abstract: bool = False,
        include_disabled: bool = False,
        include_property_counts: bool = True,
        max_results: int = 200,
    ) -> dict[str, Any]:
        return self.rpc(
            "resource.classes",
            {
                "base_class": base_class,
                "name_contains": name_contains,
                "include_abstract": include_abstract,
                "include_disabled": include_disabled,
                "include_property_counts": include_property_counts,
                "max_results": max_results,
            },
        )

    def node_classes(
        self,
        *,
        base_class: str = "Node",
        name_contains: str = "",
        include_abstract: bool = False,
        include_disabled: bool = False,
        include_property_counts: bool = True,
        max_results: int = 200,
    ) -> dict[str, Any]:
        return self.rpc(
            "node.classes",
            {
                "base_class": base_class,
                "name_contains": name_contains,
                "include_abstract": include_abstract,
                "include_disabled": include_disabled,
                "include_property_counts": include_property_counts,
                "max_results": max_results,
            },
        )

    def node_class_describe(
        self,
        class_name: str = "Node",
        *,
        include_values: bool = True,
        include_internal: bool = False,
        storage_only: bool = False,
        properties: list[str] | tuple[str, ...] | None = None,
        name_contains: str = "",
        include_methods: bool = True,
        include_signals: bool = True,
        methods: list[str] | tuple[str, ...] | None = None,
        signals: list[str] | tuple[str, ...] | None = None,
        method_contains: str = "",
        signal_contains: str = "",
        max_methods: int = 200,
        max_signals: int = 200,
    ) -> dict[str, Any]:
        return self.rpc(
            "node.class.describe",
            {
                "class": class_name,
                "include_values": include_values,
                "include_internal": include_internal,
                "storage_only": storage_only,
                "properties": list(properties or []),
                "name_contains": name_contains,
                "include_methods": include_methods,
                "include_signals": include_signals,
                "methods": list(methods or []),
                "signals": list(signals or []),
                "method_contains": method_contains,
                "signal_contains": signal_contains,
                "max_methods": max_methods,
                "max_signals": max_signals,
            },
        )

    def node_schema(self, class_name: str = "Node", **kwargs: Any) -> dict[str, Any]:
        return self.node_class_describe(class_name, **kwargs)

    def wait_for_resource(
        self,
        path: str,
        *,
        class_name: str | None = None,
        properties: dict[str, Any] | None = None,
        type_hint: str = "",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected_properties = properties or {}
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.resource_inspect(
                    path,
                    type_hint=type_hint,
                    include_properties=bool(expected_properties),
                    properties=list(expected_properties),
                )
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                class_ok = class_name is None or last.get("class") == class_name
                props_ok = not expected_properties or _dict_contains(_resource_properties(last), expected_properties)
                if _resource_state_exists(last) and class_ok and props_ok:
                    return last
            if time.monotonic() >= deadline:
                raise GodotPlaywrightError(
                    f"Timed out waiting for resource {path!r} class={class_name!r} "
                    f"properties={expected_properties!r}; last={last!r} error={last_error!r}"
                )
            time.sleep(interval)

    def resource_dependencies(self, path: str) -> dict[str, Any]:
        return self.rpc("resource.dependencies", {"path": path})

    def resource_references(
        self,
        path: str = "",
        *,
        uid: str = "",
        search_path: str = "res://",
        dependency_type: str = "",
        resource_type: str = "",
        exists: bool | None = None,
        extensions: list[str] | tuple[str, ...] | str | None = None,
        recursive: bool = True,
        include_hidden: bool = False,
        max_results: int = 200,
        max_scan_results: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "path": path,
            "uid": uid,
            "search_path": search_path,
            "dependency_type": dependency_type,
            "resource_type": resource_type,
            "recursive": recursive,
            "include_hidden": include_hidden,
            "max_results": int(max_results),
        }
        if exists is not None:
            params["exists"] = exists
        if extensions is not None:
            params["extensions"] = [extensions] if isinstance(extensions, str) else list(extensions)
        if max_scan_results is not None:
            params["max_scan_results"] = int(max_scan_results)
        return self.rpc("resource.references", params)

    def resource_move(
        self,
        source: str,
        destination: str,
        *,
        update_references: bool = True,
        dry_run: bool = False,
        search_path: str = "res://",
        extensions: list[str] | tuple[str, ...] | str | None = None,
        recursive: bool = True,
        include_hidden: bool = False,
        overwrite: bool = True,
        create_dirs: bool = True,
        expected_reference_files: int = -1,
        expected_replacements: int = -1,
        max_reference_files: int = 200,
        max_scan_results: int | None = None,
        max_replacements_per_file: int = 100,
        max_total_replacements: int = 500,
        max_preview: int = 20,
        include_text: bool | None = None,
        allow_truncated: bool = False,
        allow_scan_truncated: bool = False,
        allow_unpatched: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "source": source,
            "destination": destination,
            "update_references": update_references,
            "dry_run": dry_run,
            "search_path": search_path,
            "recursive": recursive,
            "include_hidden": include_hidden,
            "overwrite": overwrite,
            "create_dirs": create_dirs,
            "expected_reference_files": expected_reference_files,
            "expected_replacements": expected_replacements,
            "max_reference_files": max_reference_files,
            "max_replacements_per_file": max_replacements_per_file,
            "max_total_replacements": max_total_replacements,
            "max_preview": max_preview,
            "include_text": wait if include_text is None else include_text,
            "allow_truncated": allow_truncated,
            "allow_scan_truncated": allow_scan_truncated,
            "allow_unpatched": allow_unpatched,
        }
        if extensions is not None:
            params["extensions"] = [extensions] if isinstance(extensions, str) else list(extensions)
        if max_scan_results is not None:
            params["max_scan_results"] = int(max_scan_results)
        result = self.rpc("resource.move", params)
        if wait and not dry_run:
            result = dict(result)
            result["source_missing"] = self.wait_for_fs_path(
                source,
                state="missing",
                timeout=timeout,
                interval=interval,
            )
            result.update(
                self._post_relocate_fs_evidence(
                    source,
                    destination,
                    destination_type="file",
                    source_missing=True,
                    timeout=timeout,
                    interval=interval,
                )
            )
            if update_references:
                verified_updates: list[dict[str, Any]] = []
                for change in result.get("reference_updates", []):
                    if not isinstance(change, dict):
                        continue
                    write_path = str(change.get("write_path", change.get("path", "")))
                    verified = dict(change)
                    if write_path:
                        verified.update(self._post_write_file_evidence(write_path, timeout=timeout, interval=interval))
                        if "text" in verified:
                            verified["text"] = self._wait_for_text_file(
                                write_path,
                                str(verified["text"]),
                                timeout=timeout,
                                interval=interval,
                            )
                    verified_updates.append(verified)
                result["reference_updates"] = verified_updates
                try:
                    result["references_after"] = self.resource_references(
                        destination,
                        search_path=search_path,
                        extensions=extensions,
                        recursive=recursive,
                        include_hidden=include_hidden,
                        max_results=max_reference_files,
                        max_scan_results=max_scan_results,
                    )
                    result["remaining_source_references"] = self.resource_references(
                        source,
                        search_path=search_path,
                        extensions=extensions,
                        recursive=recursive,
                        include_hidden=include_hidden,
                        max_results=max_reference_files,
                        max_scan_results=max_scan_results,
                    )
                except GodotPlaywrightError as exc:
                    result["reference_verification_error"] = str(exc)
        return result

    def resource_import_metadata(self, path: str) -> dict[str, Any]:
        return self.rpc("resource.import_metadata", {"path": path})

    def resource_imports(
        self,
        path: str = "res://",
        *,
        name: str = "",
        name_contains: str = "",
        importer: str = "",
        resource_type: str = "",
        extensions: list[str] | tuple[str, ...] | str | None = None,
        generated_files_ready: bool | None = None,
        imported: bool | None = None,
        ok: bool | None = None,
        include_missing_metadata: bool = True,
        recursive: bool = True,
        include_hidden: bool = False,
        max_results: int = 200,
        max_scan_results: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "path": path,
            "name": name,
            "name_contains": name_contains,
            "importer": importer,
            "resource_type": resource_type,
            "include_missing_metadata": include_missing_metadata,
            "recursive": recursive,
            "include_hidden": include_hidden,
            "max_results": int(max_results),
        }
        if extensions is not None:
            params["extensions"] = [extensions] if isinstance(extensions, str) else list(extensions)
        if generated_files_ready is not None:
            params["generated_files_ready"] = generated_files_ready
        if imported is not None:
            params["imported"] = imported
        if ok is not None:
            params["ok"] = ok
        if max_scan_results is not None:
            params["max_scan_results"] = int(max_scan_results)
        return self.rpc("resource.imports", params)

    def resource_reimport(
        self,
        paths: str | list[str],
        *,
        force: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
        require_resource: bool = True,
    ) -> dict[str, Any]:
        path_list = [paths] if isinstance(paths, str) else list(paths)
        if isinstance(paths, str):
            result = self.rpc("resource.reimport", {"path": paths, "force": force})
        else:
            result = self.rpc("resource.reimport", {"paths": paths, "force": force})
        if wait:
            result = dict(result)
            filesystem_states = {
                path: self.wait_for_editor_filesystem_entry(
                    path,
                    is_file=True,
                    timeout=timeout,
                    interval=interval,
                )
                for path in path_list
                if str(path).startswith("res://")
            }
            if isinstance(paths, str):
                if paths in filesystem_states:
                    result["editor_filesystem"] = filesystem_states[paths]
            else:
                result["editor_filesystem_states"] = filesystem_states
            imports = [
                self.wait_for_import(
                    path,
                    timeout=timeout,
                    interval=interval,
                    require_resource=require_resource,
                )
                for path in path_list
                if _resource_path_uses_import_metadata(path)
            ]
            result["imports"] = imports
            result["import_count"] = len(imports)
        return result

    def wait_for_import(
        self,
        path: str,
        *,
        importer: str | None = None,
        resource_type: str | None = None,
        generated_files_ready: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
        require_resource: bool = True,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.resource_import_metadata(path)
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if _resource_import_wait_matches(
                    last,
                    importer=importer,
                    resource_type=resource_type,
                    generated_files_ready=generated_files_ready,
                    require_resource=require_resource,
                ):
                    return last
            if time.monotonic() >= deadline:
                detail = last if last else repr(last_error)
                raise GodotPlaywrightError(
                    f"Timed out waiting for import {path!r} with "
                    f"{_resource_import_filter_summary(importer=importer, resource_type=resource_type, generated_files_ready=generated_files_ready, require_resource=require_resource)}; "
                    f"diagnostics={_resource_import_diagnostic_summary(last)!r}; last={detail!r}"
                )
            time.sleep(interval)

    def create_node(
        self,
        parent: str | dict[str, Any] = "edited",
        class_name: str = "Node",
        *,
        name: str = "",
        root: str | dict[str, Any] | None = None,
        owner_scene: bool = True,
        undo: bool | None = None,
        undo_action: str = "",
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "parent": parent,
            "root": root or "edited",
            "class": class_name,
            "name": name,
            "owner_scene": owner_scene,
        }
        if undo is not None:
            params["undo"] = undo
        if undo_action:
            params["undo_action"] = undo_action
        result = self.rpc("node.create", params)
        if wait:
            result = dict(result)
            result["node_state"] = self.wait_for_node(
                {"path": str(result.get("path", ""))},
                root="root",
                expected={"name": result.get("name"), "class": result.get("class")},
                timeout=timeout,
                interval=interval,
            )
        return result

    def create_node_tree(
        self,
        nodes: list[dict[str, Any]] | tuple[dict[str, Any], ...] | dict[str, Any],
        *,
        parent: str | dict[str, Any] = "edited",
        root: str | dict[str, Any] | None = None,
        owner_scene: bool = True,
        persistent_groups: bool = True,
        reload_scripts: bool = True,
        max_nodes: int = 100,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        node_specs: Any = [nodes] if isinstance(nodes, dict) else list(nodes)
        result = self.rpc(
            "node.create_tree",
            {
                "parent": parent,
                "root": root or "edited",
                "nodes": node_specs,
                "owner_scene": owner_scene,
                "persistent_groups": persistent_groups,
                "reload_scripts": reload_scripts,
                "max_nodes": max_nodes,
            },
        )
        if wait:
            result = dict(result)
            verified_nodes: list[dict[str, Any]] = []
            for node in result.get("nodes", []):
                if not isinstance(node, dict):
                    continue
                path = str(node.get("path", ""))
                verified = dict(node)
                verified["node_state"] = self.wait_for_node(
                    {"path": path},
                    root="root",
                    expected={"name": node.get("name"), "class": node.get("class")},
                    timeout=timeout,
                    interval=interval,
                )
                properties = node.get("properties", {})
                if isinstance(properties, dict) and properties:
                    verified["properties_state"] = self.wait_for_node_properties(
                        {"path": path},
                        properties,
                        root="root",
                        timeout=timeout,
                        interval=interval,
                    )
                metadata = node.get("metadata", {})
                if isinstance(metadata, dict) and metadata:
                    verified["metadata_state"] = self.wait_for_node_metadata(
                        {"path": path},
                        metadata,
                        root="root",
                        timeout=timeout,
                        interval=interval,
                    )
                for group in node.get("groups", []) or []:
                    verified.setdefault("group_states", {})[str(group)] = self.wait_for_node_group(
                        {"path": path},
                        str(group),
                        root="root",
                        timeout=timeout,
                        interval=interval,
                    )
                script_path = _script_resource_path(node.get("script"))
                if script_path:
                    verified["script_state"] = self.wait_for_node_script(
                        {"path": path},
                        path=script_path,
                        root="root",
                        timeout=timeout,
                        interval=interval,
                    )
                verified_nodes.append(verified)
            result["nodes"] = verified_nodes
        return result

    def instantiate_scene(
        self,
        path: str,
        *,
        parent: str | dict[str, Any] = "edited",
        root: str | dict[str, Any] | None = None,
        name: str = "",
        index: int | None = None,
        owner_scene: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "path": path,
            "parent": parent,
            "root": root or "edited",
            "name": name,
            "owner_scene": owner_scene,
        }
        if index is not None:
            params["index"] = index
        result = self.rpc("node.instantiate_scene", params)
        if wait:
            expected: dict[str, Any] = {"name": result.get("name"), "path": result.get("path")}
            if index is not None:
                expected["index"] = index
            result = dict(result)
            result["node_state"] = self.wait_for_node(
                {"path": str(result.get("path", ""))},
                root="root",
                expected=expected,
                timeout=timeout,
                interval=interval,
            )
        return result

    def wait_for_node(
        self,
        selector: str | dict[str, Any],
        *,
        state: str = "attached",
        expected: dict[str, Any] | None = None,
        root: str | dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if state not in {"attached", "detached"}:
            raise ValueError("state must be 'attached' or 'detached'")
        locator = self.locator(selector, root=root or "edited")
        if state == "detached":
            locator.wait_for(state="detached", timeout=timeout, interval=interval)
            return {"selector": selector, "state": "detached"}

        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = locator.describe()
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if expected is None or _dict_contains(last, expected):
                    return last
            if time.monotonic() >= deadline:
                detail = last if last else repr(last_error)
                raise GodotPlaywrightError(
                    f"Timed out waiting for node {selector!r} state={state!r} expected={expected!r}; last={detail!r}"
                )
            time.sleep(interval)

    def set_node_property(
        self,
        selector: str | dict[str, Any],
        property_name: str,
        value: Any,
        *,
        root: str | dict[str, Any] | None = None,
        undo: bool | None = None,
        undo_action: str = "",
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "selector": selector,
            "root": root or "edited",
            "property": property_name,
            "value": value,
        }
        if undo is not None:
            params["undo"] = undo
        if undo_action:
            params["undo_action"] = undo_action
        result = self.rpc("node.set_property", params)
        if wait:
            result = dict(result)
            result["property_state"] = {
                "property": property_name,
                "value": self.wait_for_node_property(
                    selector,
                    property_name,
                    value,
                    root=root or "edited",
                    timeout=timeout,
                    interval=interval,
                ),
            }
        return result

    def set_node_properties(
        self,
        selector: str | dict[str, Any],
        values: dict[str, Any],
        *,
        root: str | dict[str, Any] | None = None,
        undo: bool | None = None,
        undo_action: str = "",
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if not values:
            raise ValueError("values must not be empty")
        params: dict[str, Any] = {
            "selector": selector,
            "root": root or "edited",
            "values": dict(values),
        }
        if undo is not None:
            params["undo"] = undo
        if undo_action:
            params["undo_action"] = undo_action
        result = self.rpc("node.set_properties", params)
        if wait:
            result = dict(result)
            result["properties_state"] = self.wait_for_node_properties(
                selector,
                values,
                root=root or "edited",
                timeout=timeout,
                interval=interval,
            )
        return result

    def wait_for_node_property(
        self,
        selector: str | dict[str, Any],
        property_name: str,
        expected: Any = _UNSET,
        *,
        root: str | dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> Any:
        locator = self.locator(selector, root=root or "edited")
        if expected is _UNSET:
            return locator.get(property_name)
        return locator.wait_for_property(property_name, expected, timeout=timeout, interval=interval)

    def wait_for_node_properties(
        self,
        selector: str | dict[str, Any],
        expected: dict[str, Any],
        *,
        root: str | dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.locator(selector, root=root or "edited").wait_for_properties(
            expected,
            timeout=timeout,
            interval=interval,
        )

    def set_node_metadata(
        self,
        selector: str | dict[str, Any],
        values: dict[str, Any],
        *,
        root: str | dict[str, Any] | None = None,
        undo: bool | None = None,
        undo_action: str = "",
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if not values:
            raise ValueError("values must not be empty")
        params: dict[str, Any] = {
            "selector": selector,
            "root": root or "edited",
            "values": dict(values),
        }
        if undo is not None:
            params["undo"] = undo
        if undo_action:
            params["undo_action"] = undo_action
        result = self.rpc("node.set_metadata", params)
        if wait:
            result = dict(result)
            result["metadata_state"] = self.wait_for_node_metadata(
                selector,
                values,
                root=root or "edited",
                timeout=timeout,
                interval=interval,
            )
        return result

    def remove_node_metadata(
        self,
        selector: str | dict[str, Any],
        names: list[str] | tuple[str, ...] | str,
        *,
        root: str | dict[str, Any] | None = None,
        undo: bool | None = None,
        undo_action: str = "",
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        name_list = [names] if isinstance(names, str) else list(names)
        if not name_list or any(not name for name in name_list):
            raise ValueError("names must not be empty")
        params: dict[str, Any] = {
            "selector": selector,
            "root": root or "edited",
            "names": name_list,
        }
        if undo is not None:
            params["undo"] = undo
        if undo_action:
            params["undo_action"] = undo_action
        result = self.rpc("node.remove_metadata", params)
        if wait:
            result = dict(result)
            for name in name_list:
                self.wait_for_node_meta(
                    selector,
                    name,
                    state="missing",
                    root=root or "edited",
                    timeout=timeout,
                    interval=interval,
                )
            result["metadata_state"] = self.locator(selector, root=root or "edited").metadata(name_list)
        return result

    def wait_for_node_meta(
        self,
        selector: str | dict[str, Any],
        name: str,
        expected: Any = _UNSET,
        *,
        state: str = "present",
        root: str | dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> Any:
        if state not in {"present", "missing"}:
            raise ValueError("state must be 'present' or 'missing'")
        locator = self.locator(selector, root=root or "edited")
        if state == "missing":
            return locator.wait_for_meta_not(name, timeout=timeout, interval=interval)
        return locator.wait_for_meta(name, expected, timeout=timeout, interval=interval)

    def wait_for_node_metadata(
        self,
        selector: str | dict[str, Any],
        expected: dict[str, Any],
        *,
        root: str | dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.locator(selector, root=root or "edited").wait_for_metadata(
            expected,
            timeout=timeout,
            interval=interval,
        )

    def save_node_as_scene(
        self,
        selector: str | dict[str, Any],
        path: str,
        *,
        root: str | dict[str, Any] | None = None,
        overwrite: bool = True,
    ) -> dict[str, Any]:
        return self.rpc(
            "node.save_as_scene",
            {
                "selector": selector,
                "root": root or "edited",
                "path": path,
                "overwrite": overwrite,
            },
        )

    def node_groups(
        self,
        selector: str | dict[str, Any],
        *,
        root: str | dict[str, Any] | None = None,
        include_internal: bool = False,
    ) -> dict[str, Any]:
        return self.rpc(
            "node.groups",
            {
                "selector": selector,
                "root": root or "edited",
                "include_internal": include_internal,
            },
        )

    def add_node_group(
        self,
        selector: str | dict[str, Any],
        group: str,
        *,
        root: str | dict[str, Any] | None = None,
        persistent: bool = True,
        include_internal: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc(
            "node.add_group",
            {
                "selector": selector,
                "root": root or "edited",
                "group": group,
                "persistent": persistent,
                "include_internal": include_internal,
            },
        )
        if wait:
            result = dict(result)
            result["groups_state"] = self.wait_for_node_group(
                selector,
                group,
                root=root or "edited",
                include_internal=include_internal,
                timeout=timeout,
                interval=interval,
            )
        return result

    def remove_node_group(
        self,
        selector: str | dict[str, Any],
        group: str,
        *,
        root: str | dict[str, Any] | None = None,
        include_internal: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc(
            "node.remove_group",
            {
                "selector": selector,
                "root": root or "edited",
                "group": group,
                "include_internal": include_internal,
            },
        )
        if wait:
            result = dict(result)
            result["groups_state"] = self.wait_for_node_group(
                selector,
                group,
                state="missing",
                root=root or "edited",
                include_internal=include_internal,
                timeout=timeout,
                interval=interval,
            )
        return result

    def wait_for_node_group(
        self,
        selector: str | dict[str, Any],
        group: str,
        *,
        state: str = "present",
        root: str | dict[str, Any] | None = None,
        include_internal: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if state not in {"present", "missing"}:
            raise ValueError("state must be 'present' or 'missing'")
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_groups: list[str] = []
        while True:
            last = self.node_groups(selector, root=root or "edited", include_internal=include_internal)
            last_groups = [str(item) for item in last.get("groups", [])]
            if state == "present" and group in last_groups:
                return last
            if state == "missing" and group not in last_groups:
                return last
            if time.monotonic() >= deadline:
                expectation = "to be in" if state == "present" else "not to be in"
                raise AssertionError(
                    f"Expected {selector!r} {expectation} group {group!r}; groups={last_groups!r}"
                )
            time.sleep(interval)

    def reparent_node(
        self,
        selector: str | dict[str, Any],
        parent: str | dict[str, Any],
        *,
        root: str | dict[str, Any] | None = None,
        index: int | None = None,
        keep_global_transform: bool = True,
        owner_scene: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "selector": selector,
            "parent": parent,
            "root": root or "edited",
            "keep_global_transform": keep_global_transform,
            "owner_scene": owner_scene,
        }
        if index is not None:
            params["index"] = index
        result = self.rpc("node.reparent", params)
        if wait:
            expected: dict[str, Any] = {"path": result.get("path"), "parent": result.get("new_parent")}
            if index is not None:
                expected["index"] = index
            result = dict(result)
            result["node_state"] = self.wait_for_node(
                {"path": str(result.get("path", ""))},
                root="root",
                expected=expected,
                timeout=timeout,
                interval=interval,
            )
        return result

    def move_node(
        self,
        selector: str | dict[str, Any],
        index: int,
        *,
        root: str | dict[str, Any] | None = None,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc("node.move", {"selector": selector, "root": root or "edited", "index": index})
        if wait:
            result = dict(result)
            result["node_state"] = self.wait_for_node(
                {"path": str(result.get("path", ""))},
                root="root",
                expected={"path": result.get("path"), "index": index},
                timeout=timeout,
                interval=interval,
            )
        return result

    def duplicate_node(
        self,
        selector: str | dict[str, Any],
        *,
        parent: str | dict[str, Any] | None = None,
        root: str | dict[str, Any] | None = None,
        name: str = "",
        index: int | None = None,
        flags: int | None = None,
        owner_scene: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "selector": selector,
            "root": root or "edited",
            "owner_scene": owner_scene,
        }
        if parent is not None:
            params["parent"] = parent
        if name:
            params["name"] = name
        if index is not None:
            params["index"] = index
        if flags is not None:
            params["flags"] = flags
        result = self.rpc("node.duplicate", params)
        if wait:
            expected: dict[str, Any] = {"name": result.get("name"), "path": result.get("path")}
            if index is not None:
                expected["index"] = index
            result = dict(result)
            result["node_state"] = self.wait_for_node(
                {"path": str(result.get("path", ""))},
                root="root",
                expected=expected,
                timeout=timeout,
                interval=interval,
            )
        return result

    def attach_script(
        self,
        selector: str | dict[str, Any],
        path: str,
        *,
        root: str | dict[str, Any] | None = None,
        inspect: bool = False,
        reload: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc(
            "node.attach_script",
            {
                "selector": selector,
                "root": root or "edited",
                "path": path,
                "inspect": inspect,
                "reload": reload,
            },
        )
        if wait:
            result = dict(result)
            result["script_state"] = self.wait_for_node_script(
                selector,
                path=path,
                root=root or "edited",
                timeout=timeout,
                interval=interval,
            )
        return result

    def detach_script(
        self,
        selector: str | dict[str, Any],
        *,
        root: str | dict[str, Any] | None = None,
        inspect: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc(
            "node.detach_script",
            {
                "selector": selector,
                "root": root or "edited",
                "inspect": inspect,
            },
        )
        if wait:
            result = dict(result)
            result["script_state"] = self.wait_for_node_script(
                selector,
                state="detached",
                root=root or "edited",
                timeout=timeout,
                interval=interval,
            )
        return result

    def wait_for_node_script(
        self,
        selector: str | dict[str, Any],
        *,
        path: str | None = None,
        state: str = "attached",
        root: str | dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if state not in {"attached", "detached"}:
            raise ValueError("state must be 'attached' or 'detached'")
        deadline = time.monotonic() + timeout
        last_script: Any = None
        last_path = ""
        locator = self.locator(selector, root=root or "edited")
        while True:
            last_script = locator.get("script")
            last_path = _script_resource_path(last_script)
            if state == "detached":
                if not last_path:
                    return {"selector": selector, "state": state, "path": "", "script": last_script}
            elif path is None:
                if last_path:
                    return {"selector": selector, "state": state, "path": last_path, "script": last_script}
            elif last_path == path:
                return {"selector": selector, "state": state, "path": last_path, "script": last_script}
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected node {selector!r} script state={state!r} path={path!r}; "
                    f"last_path={last_path!r} script={last_script!r}"
                )
            time.sleep(interval)

    def delete_node(
        self,
        selector: str | dict[str, Any],
        *,
        root: str | dict[str, Any] | None = None,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc("node.delete", {"selector": selector, "root": root or "edited"})
        if wait:
            result = dict(result)
            result["node_state"] = self.wait_for_node(
                {"path": str(result.get("deleted", ""))},
                state="detached",
                root="root",
                timeout=timeout,
                interval=interval,
            )
        return result

    def current_scene(self) -> dict[str, Any]:
        return self.rpc("scene.current")

    def scene_files(
        self,
        path: str = "res://",
        *,
        name: str = "",
        name_contains: str = "",
        root_name: str = "",
        root_class: str = "",
        extensions: list[str] | tuple[str, ...] | str | None = None,
        include_dependencies: bool = True,
        include_nodes: bool = False,
        recursive: bool = True,
        include_hidden: bool = False,
        max_results: int = 200,
        max_scan_results: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "path": path,
            "name": name,
            "name_contains": name_contains,
            "root_name": root_name,
            "root_class": root_class,
            "include_dependencies": include_dependencies,
            "include_nodes": include_nodes,
            "recursive": recursive,
            "include_hidden": include_hidden,
            "max_results": int(max_results),
        }
        if extensions is not None:
            params["extensions"] = [extensions] if isinstance(extensions, str) else list(extensions)
        if max_scan_results is not None:
            params["max_scan_results"] = int(max_scan_results)
        return self.rpc("scene.files", params)

    def scene_file_describe(
        self,
        path: str,
        *,
        include_nodes: bool = True,
        include_properties: bool = False,
        include_resources: bool = True,
        include_connections: bool = True,
        include_dependencies: bool = True,
        include_source: bool = False,
    ) -> dict[str, Any]:
        return self.rpc(
            "scene.file.describe",
            {
                "path": path,
                "include_nodes": include_nodes,
                "include_properties": include_properties,
                "include_resources": include_resources,
                "include_connections": include_connections,
                "include_dependencies": include_dependencies,
                "include_source": include_source,
            },
        )

    def change_scene(self, path: str, *, wait: bool = True, timeout: float = 5.0) -> dict[str, Any]:
        result = self.rpc("scene.change", {"path": path})
        if wait:
            return self.wait_for_scene(path, timeout=timeout)
        return result

    def reload_scene(self, *, wait: bool = True, timeout: float = 5.0) -> dict[str, Any]:
        before = self.current_scene()
        result = self.rpc("scene.reload")
        if wait and before.get("scene_file_path"):
            return self.wait_for_scene(str(before["scene_file_path"]), timeout=timeout)
        return result

    def wait_for_scene(
        self,
        path: str | None = None,
        *,
        name: str | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.current_scene()
            path_ok = path is None or last.get("scene_file_path") == path
            name_ok = name is None or last.get("name") == name
            if path_ok and name_ok:
                return last
            if time.monotonic() >= deadline:
                expected = path if path is not None else name
                raise GodotPlaywrightError(f"Timed out waiting for scene {expected!r}; last scene was {last!r}")
            time.sleep(interval)

    def wait_for_scene_not(
        self,
        path: str | None = None,
        *,
        name: str | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if path is None and name is None:
            raise ValueError("path or name is required")
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.current_scene()
            path_ok = path is None or last.get("scene_file_path") != path
            name_ok = name is None or last.get("name") != name
            if path_ok and name_ok:
                return last
            if time.monotonic() >= deadline:
                expected = path if path is not None else name
                raise GodotPlaywrightError(f"Timed out waiting for scene not to be {expected!r}; last scene was {last!r}")
            time.sleep(interval)

    def editor_new_scene(
        self,
        *,
        class_name: str = "Node2D",
        name: str = "Main",
        close_existing: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_result: dict[str, Any] = {}
        last_status: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                result = self.rpc(
                    "scene.new",
                    {
                        "class": class_name,
                        "name": name,
                        "close_existing": close_existing,
                    },
                )
                if not wait:
                    return result
                last_result = dict(result)
                attempt_deadline = min(deadline, time.monotonic() + max(interval * 5, 0.75))
                matched_since: float | None = None
                stable_seconds = max(interval * 3, 0.3)
                while True:
                    last_status = self.editor_status()
                    if _editor_value_matches(last_status.get("edited_scene_name", ""), name):
                        if matched_since is None:
                            matched_since = time.monotonic()
                        if time.monotonic() - matched_since >= stable_seconds:
                            last_result["editor_status"] = last_status
                            return last_result
                    else:
                        matched_since = None
                    if time.monotonic() >= attempt_deadline:
                        break
                    time.sleep(interval)
            except GodotPlaywrightError as exc:
                last_error = exc
            if time.monotonic() >= deadline:
                detail = f"last_error={last_error!r}" if last_error is not None else f"last_status={last_status!r}"
                raise GodotPlaywrightError(
                    f"Timed out creating edited scene {name!r} class={class_name!r}; "
                    f"last_result={last_result!r} {detail}"
                ) from last_error
            time.sleep(interval)

    def editor_open_scene(
        self,
        path: str,
        *,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc("scene.open", {"path": path})
        if wait:
            result = dict(result)
            editor_status = self.wait_for_editor_scene(path, timeout=timeout, interval=interval)
            result.update(editor_status)
            result["editor_status"] = editor_status
        return result

    def editor_save_scene(
        self,
        path: str = "",
        *,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params = {"path": path} if path else {}
        result = self.rpc("scene.save", params)
        if wait:
            result = dict(result)
            saved_path = str(result.get("path") or path)
            if saved_path:
                result["editor_status"] = self.wait_for_editor_scene(saved_path, timeout=timeout, interval=interval)
                if saved_path.startswith("res://"):
                    result["file"] = self.wait_for_file(saved_path, timeout=timeout, interval=interval)
                    result["editor_filesystem_scan"] = self.editor_scan_filesystem(
                        saved_path,
                        timeout=timeout,
                        interval=interval,
                    )
                    result["editor_filesystem"] = self.wait_for_editor_filesystem_entry(
                        saved_path,
                        is_file=True,
                        timeout=timeout,
                        interval=interval,
                    )
        return result

    def wait_for_editor_scene(
        self,
        path: str | None = None,
        *,
        name: str | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.editor_status()
            path_ok = path is None or _editor_status_matches_edited_scene(last, path)
            name_ok = name is None or _editor_value_matches(last.get("edited_scene_name", ""), name)
            if path_ok and name_ok:
                return last
            if time.monotonic() >= deadline:
                expected = path if path is not None else name
                raise GodotPlaywrightError(f"Timed out waiting for edited scene {expected!r}; last status was {last!r}")
            time.sleep(interval)

    def project_get_setting(self, name: str) -> Any:
        result = self.rpc("project.get_setting", {"name": name})
        return result.get("value")

    def project_set_setting(
        self,
        name: str,
        value: Any,
        *,
        save: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc("project.set_setting", {"name": name, "value": value, "save": save})
        if wait:
            result = dict(result)
            result["setting"] = {
                "name": name,
                "value": self.wait_for_project_setting(name, value, timeout=timeout, interval=interval),
            }
        return result

    def wait_for_project_setting(
        self,
        name: str,
        expected: Any = _UNSET,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last: Any = None
        while True:
            last = self.project_get_setting(name)
            if expected is _UNSET or last == expected:
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected project setting {name!r} to be {expected!r}; got {last!r}")
            time.sleep(interval)

    def project_summary(
        self,
        path: str = "res://",
        *,
        max_results: int = 50,
        include_input_events: bool = False,
        include_ui_actions: bool = True,
        include_imports: bool = True,
    ) -> dict[str, Any]:
        return self.rpc(
            "project.summary",
            {
                "path": path,
                "max_results": int(max_results),
                "include_input_events": include_input_events,
                "include_ui_actions": include_ui_actions,
                "include_imports": include_imports,
            },
        )

    def project_doctor(
        self,
        path: str = "res://",
        *,
        max_results: int = 50,
        include_input_events: bool = False,
        include_ui_actions: bool = True,
        include_imports: bool = True,
        include_protocol_methods: bool = False,
    ) -> dict[str, Any]:
        return self.rpc(
            "project.doctor",
            {
                "path": path,
                "max_results": int(max_results),
                "include_input_events": include_input_events,
                "include_ui_actions": include_ui_actions,
                "include_imports": include_imports,
                "include_protocol_methods": include_protocol_methods,
            },
        )

    def project_export_presets(self) -> dict[str, Any]:
        return self.rpc("project.export_presets")

    def project_set_export_preset(
        self,
        name: str,
        platform: str,
        *,
        index: int | None = None,
        export_path: str = "",
        runnable: bool = True,
        dedicated_server: bool = False,
        custom_features: str = "",
        export_filter: str = "all_resources",
        include_filter: str = "",
        exclude_filter: str = "",
        encryption_include_filters: str = "",
        encryption_exclude_filters: str = "",
        encrypt_pck: bool = False,
        encrypt_directory: bool = False,
        script_export_mode: int = 2,
        options: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        overwrite: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected_options = options or {}
        expected_fields = fields or {}
        params: dict[str, Any] = {
            "name": name,
            "platform": platform,
            "export_path": export_path,
            "runnable": runnable,
            "dedicated_server": dedicated_server,
            "custom_features": custom_features,
            "export_filter": export_filter,
            "include_filter": include_filter,
            "exclude_filter": exclude_filter,
            "encryption_include_filters": encryption_include_filters,
            "encryption_exclude_filters": encryption_exclude_filters,
            "encrypt_pck": encrypt_pck,
            "encrypt_directory": encrypt_directory,
            "script_export_mode": script_export_mode,
            "options": expected_options,
            "fields": expected_fields,
            "overwrite": overwrite,
        }
        if index is not None:
            params["index"] = index
        result = self.rpc("project.set_export_preset", params)
        if wait:
            result = dict(result)
            result["preset_state"] = self.wait_for_export_preset(
                name,
                platform=platform,
                export_path=export_path,
                runnable=runnable,
                options=expected_options or None,
                fields=expected_fields or None,
                timeout=timeout,
                interval=interval,
            )
        return result

    def wait_for_export_preset(
        self,
        name: str,
        *,
        platform: str | None = None,
        export_path: str | None = None,
        runnable: bool | None = None,
        options: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.project_export_presets()
            entry = _project_export_preset_entry(
                last,
                name,
                platform=platform,
                export_path=export_path,
                runnable=runnable,
                options=options,
                fields=fields,
            )
            if entry is not None:
                return entry
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected export preset {name!r}"
                    f"{_project_export_preset_filter_summary(platform=platform, export_path=export_path, runnable=runnable, options=options, fields=fields)}; "
                    f"last={last!r}"
                )
            time.sleep(interval)

    def project_main_scene(self) -> dict[str, Any]:
        return self.rpc("project.main_scene")

    def project_set_main_scene(
        self,
        path: str,
        *,
        save: bool = False,
        require_exists: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc(
            "project.set_main_scene",
            {"path": path, "save": save, "require_exists": require_exists},
        )
        if wait:
            result = dict(result)
            result["main_scene"] = self.wait_for_project_main_scene(path, timeout=timeout, interval=interval)
        return result

    def wait_for_project_main_scene(
        self,
        path: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.project_main_scene()
            if last.get("path") == path:
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected project main scene {path!r}; last={last!r}")
            time.sleep(interval)

    def project_autoloads(self) -> dict[str, Any]:
        return self.rpc("project.autoloads")

    def project_add_autoload(
        self,
        name: str,
        path: str,
        *,
        singleton: bool = True,
        save: bool = False,
        overwrite: bool = True,
        require_exists: bool = True,
        order: int | None = None,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "name": name,
            "path": path,
            "singleton": singleton,
            "save": save,
            "overwrite": overwrite,
            "require_exists": require_exists,
        }
        if order is not None:
            params["order"] = order
        result = self.rpc("project.add_autoload", params)
        if wait:
            result = dict(result)
            result["autoload_state"] = self.wait_for_project_autoload(
                name,
                path=path,
                singleton=singleton,
                timeout=timeout,
                interval=interval,
            )
        return result

    def project_remove_autoload(
        self,
        name: str,
        *,
        save: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc("project.remove_autoload", {"name": name, "save": save})
        if wait:
            result = dict(result)
            result["autoload_state"] = self.wait_for_project_autoload(
                name,
                state="missing",
                timeout=timeout,
                interval=interval,
            )
        return result

    def wait_for_project_autoload(
        self,
        name: str,
        *,
        path: str | None = None,
        singleton: bool | None = None,
        state: str = "present",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if state not in {"present", "missing"}:
            raise ValueError("state must be 'present' or 'missing'")
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.project_autoloads()
            entry = _project_autoload_entry(last, name, path=path, singleton=singleton)
            if state == "present" and entry is not None:
                return entry
            if state == "missing" and entry is None:
                return {"name": name, "state": "missing", "autoloads": last.get("autoloads", [])}
            if time.monotonic() >= deadline:
                if state == "present":
                    raise AssertionError(
                        f"Expected project autoload {name!r}"
                        f"{_project_autoload_filter_summary(path=path, singleton=singleton)}; last={last!r}"
                    )
                raise AssertionError(
                    f"Expected project not to have autoload {name!r}"
                    f"{_project_autoload_filter_summary(path=path, singleton=singleton)}; last={last!r}"
                )
            time.sleep(interval)

    def input_actions(
        self,
        *,
        include_events: bool = True,
        include_ui: bool = True,
        prefix: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"include_events": include_events, "include_ui": include_ui}
        if prefix is not None:
            params["prefix"] = prefix
        return self.rpc("input.actions", params)

    def input_action_describe(self, action: str, *, include_events: bool = True) -> dict[str, Any]:
        return self.rpc("input.action.describe", {"action": action, "include_events": include_events})

    def input_action_configure(
        self,
        action: str,
        *,
        deadzone: float | None = None,
        events: list[dict[str, Any] | str] | tuple[dict[str, Any] | str, ...] | dict[str, Any] | str | None = None,
        replace: bool = False,
        create: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "action": action,
            "replace": replace,
            "create": create,
        }
        if deadzone is not None:
            params["deadzone"] = deadzone
        if events is not None:
            params["events"] = list(events) if isinstance(events, tuple) else events
        result = self.rpc("input.action.configure", params)
        if wait:
            result = dict(result)
            result["action_state"] = self.wait_for_input_action_config(
                action,
                event_count=int(result.get("event_count", 0)),
                deadzone=float(result["deadzone"]) if result.get("deadzone") is not None else None,
                timeout=timeout,
                interval=interval,
            )
        return result

    def input_action_set_events(
        self,
        action: str,
        events: list[dict[str, Any] | str] | tuple[dict[str, Any] | str, ...] | dict[str, Any] | str,
        *,
        deadzone: float | None = None,
        create: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.input_action_configure(
            action,
            deadzone=deadzone,
            events=events,
            replace=True,
            create=create,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def input_action_erase(
        self,
        action: str,
        *,
        events: list[dict[str, Any] | str] | tuple[dict[str, Any] | str, ...] | dict[str, Any] | str | None = None,
        events_only: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"action": action, "events_only": events_only}
        if events is not None:
            params["events"] = list(events) if isinstance(events, tuple) else events
        result = self.rpc("input.action.erase", params)
        if wait:
            result = dict(result)
            if result.get("exists"):
                result["action_state"] = self.wait_for_input_action_config(
                    action,
                    event_count=int(result.get("event_count", 0)),
                    deadzone=float(result["deadzone"]) if result.get("deadzone") is not None else None,
                    timeout=timeout,
                    interval=interval,
                )
            else:
                result["action_state"] = self.wait_for_input_action_config(
                    action,
                    state="missing",
                    timeout=timeout,
                    interval=interval,
                )
        return result

    def wait_for_input_action_config(
        self,
        action: str,
        *,
        state: str = "present",
        event_count: int | None = None,
        min_event_count: int | None = None,
        deadzone: float | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if state not in {"present", "missing"}:
            raise ValueError("state must be 'present' or 'missing'")
        if event_count is not None and min_event_count is not None:
            raise ValueError("Use event_count or min_event_count, not both")
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.input_action_describe(action)
            if state == "missing":
                if not bool(last.get("exists")):
                    return last
            elif _input_action_matches(
                last,
                event_count=event_count,
                min_event_count=min_event_count,
                deadzone=deadzone,
            ):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected input action {action!r} to be {state}"
                    f"{_input_action_filter_summary(event_count=event_count, min_event_count=min_event_count, deadzone=deadzone)}; "
                    f"last={last!r}"
                )
            time.sleep(interval)

    def input_key_event(
        self,
        key: str | int,
        *,
        modifiers: list[str] | tuple[str, ...] | str | None = None,
        shift: bool = False,
        ctrl: bool = False,
        alt: bool = False,
        meta: bool = False,
        command_or_control: bool = False,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {"type": "key", "key": key}
        if modifiers is not None:
            event["modifiers"] = modifiers
        if shift:
            event["shift"] = True
        if ctrl:
            event["ctrl"] = True
        if alt:
            event["alt"] = True
        if meta:
            event["meta"] = True
        if command_or_control:
            event["command_or_control"] = True
        return event

    def input_mouse_button_event(self, button: str | int = MOUSE_BUTTON_LEFT) -> dict[str, Any]:
        return {"type": "mouse_button", "button": button}

    def input_joypad_button_event(self, button: str | int, *, device: int = -1) -> dict[str, Any]:
        return {"type": "joypad_button", "button": button, "device": device}

    def input_joypad_axis_event(self, axis: str | int, value: float = 1.0, *, device: int = -1) -> dict[str, Any]:
        return {"type": "joypad_axis", "axis": axis, "value": value, "device": device}

    def bind_action_key(
        self,
        action: str,
        key: str | int,
        *,
        replace: bool = False,
        deadzone: float | None = None,
        modifiers: list[str] | tuple[str, ...] | str | None = None,
        shift: bool = False,
        ctrl: bool = False,
        alt: bool = False,
        meta: bool = False,
        command_or_control: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.input_action_configure(
            action,
            deadzone=deadzone,
            events=[
                self.input_key_event(
                    key,
                    modifiers=modifiers,
                    shift=shift,
                    ctrl=ctrl,
                    alt=alt,
                    meta=meta,
                    command_or_control=command_or_control,
                )
            ],
            replace=replace,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def bind_action_mouse_button(
        self,
        action: str,
        button: str | int = MOUSE_BUTTON_LEFT,
        *,
        replace: bool = False,
        deadzone: float | None = None,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.input_action_configure(
            action,
            deadzone=deadzone,
            events=[self.input_mouse_button_event(button)],
            replace=replace,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def bind_action_joypad_button(
        self,
        action: str,
        button: str | int,
        *,
        replace: bool = False,
        deadzone: float | None = None,
        device: int = -1,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.input_action_configure(
            action,
            deadzone=deadzone,
            events=[self.input_joypad_button_event(button, device=device)],
            replace=replace,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def bind_action_joypad_axis(
        self,
        action: str,
        axis: str | int,
        value: float = 1.0,
        *,
        replace: bool = False,
        deadzone: float | None = None,
        device: int = -1,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.input_action_configure(
            action,
            deadzone=deadzone,
            events=[self.input_joypad_axis_event(axis, value, device=device)],
            replace=replace,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def input_action(
        self,
        action: str,
        pressed: bool,
        strength: float = 1.0,
        *,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.rpc(
            "input.action",
            {"action": action, "pressed": pressed, "strength": strength},
        )
        if wait:
            result = dict(result)
            result["pressed_state"] = self.wait_for_input_action(
                action,
                pressed=pressed,
                strength=strength if pressed else 0.0,
                timeout=timeout,
                interval=interval,
            )
        return result

    def action_down(
        self,
        action: str,
        *,
        strength: float = 1.0,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.input_action(
            action,
            True,
            strength,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def action_up(
        self,
        action: str,
        *,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.input_action(
            action,
            False,
            0.0,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def press_action(
        self,
        action: str,
        *,
        strength: float = 1.0,
        frames: int = 1,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        down = self.action_down(action, strength=strength, wait=wait, timeout=timeout, interval=interval)
        self.wait_for_process_frames(frames, timeout=timeout)
        up = self.action_up(action, wait=wait, timeout=timeout, interval=interval)
        return {"action": action, "down": down, "up": up, "frames": frames}

    def wait_for_input_action(
        self,
        action: str,
        *,
        pressed: bool | None = None,
        strength: float | None = None,
        min_strength: float | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if strength is not None and min_strength is not None:
            raise ValueError("Use strength or min_strength, not both")
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.input_action_describe(action, include_events=False)
            if _input_action_state_matches(
                last,
                pressed=pressed,
                strength=strength,
                min_strength=min_strength,
            ):
                return last
            if time.monotonic() >= deadline:
                raise GodotPlaywrightError(
                    f"Timed out waiting for input action {action!r}"
                    f"{_input_action_state_filter_summary(pressed=pressed, strength=strength, min_strength=min_strength)}; "
                    f"last={last!r}"
                )
            time.sleep(interval)

    def input_key(
        self,
        key: str | int,
        *,
        pressed: bool = True,
        unicode: int = 0,
        echo: bool = False,
        modifiers: list[str] | tuple[str, ...] | str | None = None,
        shift: bool = False,
        ctrl: bool = False,
        alt: bool = False,
        meta: bool = False,
        command_or_control: bool = False,
    ) -> Any:
        params: dict[str, Any] = {"key": key, "pressed": pressed, "unicode": unicode, "echo": echo}
        if modifiers is not None:
            params["modifiers"] = modifiers
        if shift:
            params["shift"] = True
        if ctrl:
            params["ctrl"] = True
        if alt:
            params["alt"] = True
        if meta:
            params["meta"] = True
        if command_or_control:
            params["command_or_control"] = True
        return self.rpc("input.key", params)

    def key_down(
        self,
        key: str | int,
        *,
        modifiers: list[str] | tuple[str, ...] | str | None = None,
        shift: bool = False,
        ctrl: bool = False,
        alt: bool = False,
        meta: bool = False,
        command_or_control: bool = False,
    ) -> Any:
        return self.input_key(
            key,
            pressed=True,
            modifiers=modifiers,
            shift=shift,
            ctrl=ctrl,
            alt=alt,
            meta=meta,
            command_or_control=command_or_control,
        )

    def key_up(
        self,
        key: str | int,
        *,
        modifiers: list[str] | tuple[str, ...] | str | None = None,
        shift: bool = False,
        ctrl: bool = False,
        alt: bool = False,
        meta: bool = False,
        command_or_control: bool = False,
    ) -> Any:
        return self.input_key(
            key,
            pressed=False,
            modifiers=modifiers,
            shift=shift,
            ctrl=ctrl,
            alt=alt,
            meta=meta,
            command_or_control=command_or_control,
        )

    def press(
        self,
        key: str | int,
        *,
        modifiers: list[str] | tuple[str, ...] | str | None = None,
        shift: bool = False,
        ctrl: bool = False,
        alt: bool = False,
        meta: bool = False,
        command_or_control: bool = False,
    ) -> None:
        self.key_down(
            key,
            modifiers=modifiers,
            shift=shift,
            ctrl=ctrl,
            alt=alt,
            meta=meta,
            command_or_control=command_or_control,
        )
        self.key_up(
            key,
            modifiers=modifiers,
            shift=shift,
            ctrl=ctrl,
            alt=alt,
            meta=meta,
            command_or_control=command_or_control,
        )

    def input_text(self, text: str) -> Any:
        return self.rpc("input.text", {"text": text})

    def input_mouse(
        self,
        x: float,
        y: float,
        *,
        type: str = "button",
        button: int = MOUSE_BUTTON_LEFT,
        pressed: bool = True,
        button_mask: int = 0,
        delta_x: float = 0.0,
        delta_y: float = 0.0,
    ) -> Any:
        return self.rpc(
            "input.mouse",
            {
                "type": type,
                "x": x,
                "y": y,
                "button": button,
                "pressed": pressed,
                "button_mask": button_mask,
                "delta_x": delta_x,
                "delta_y": delta_y,
            },
        )

    def mouse_move(self, x: float, y: float, *, button_mask: int = 0) -> Any:
        return self.input_mouse(x, y, type="move", button_mask=button_mask)

    def mouse_down(self, x: float, y: float, *, button: int = MOUSE_BUTTON_LEFT) -> Any:
        return self.input_mouse(x, y, type="down", button=button, pressed=True)

    def mouse_up(self, x: float, y: float, *, button: int = MOUSE_BUTTON_LEFT) -> Any:
        return self.input_mouse(x, y, type="up", button=button, pressed=False)

    def mouse_click(self, x: float, y: float, *, button: int = MOUSE_BUTTON_LEFT) -> Any:
        return self.input_mouse(x, y, type="click", button=button)

    def mouse_wheel(self, x: float, y: float, *, delta_x: float = 0.0, delta_y: float = 0.0) -> Any:
        return self.input_mouse(x, y, type="wheel", delta_x=delta_x, delta_y=delta_y)

    def input_touch(self, x: float, y: float, *, type: str = "tap", index: int = 0) -> Any:
        return self.rpc("input.touch", {"type": type, "x": x, "y": y, "index": index})

    def touch_down(self, x: float, y: float, *, index: int = 0) -> Any:
        return self.input_touch(x, y, type="down", index=index)

    def touch_up(self, x: float, y: float, *, index: int = 0) -> Any:
        return self.input_touch(x, y, type="up", index=index)

    def touch_move(self, x: float, y: float, *, index: int = 0) -> Any:
        return self.input_touch(x, y, type="drag", index=index)

    def tap(self, x: float, y: float, *, index: int = 0) -> Any:
        return self.input_touch(x, y, type="tap", index=index)

    def input_joypad(
        self,
        *,
        type: str = "button",
        button: str | int | None = None,
        axis: str | int | None = None,
        value: float = 0.0,
        device: int = 0,
        pressed: bool = True,
        pressure: float | None = None,
    ) -> Any:
        params: dict[str, Any] = {"type": type, "device": device}
        if button is not None:
            params["button"] = button
        if axis is not None:
            params["axis"] = axis
            params["value"] = value
        if type in {"button", "down", "up"} or button is not None:
            params["pressed"] = pressed
            if pressure is not None:
                params["pressure"] = pressure
        return self.rpc("input.joypad", params)

    def joypad_button(
        self,
        button: str | int,
        *,
        pressed: bool = True,
        pressure: float | None = None,
        device: int = 0,
    ) -> Any:
        return self.input_joypad(
            type="button",
            button=button,
            pressed=pressed,
            pressure=pressure,
            device=device,
        )

    def joypad_button_down(
        self,
        button: str | int,
        *,
        pressure: float | None = None,
        device: int = 0,
    ) -> Any:
        return self.input_joypad(
            type="down",
            button=button,
            pressed=True,
            pressure=pressure,
            device=device,
        )

    def joypad_button_up(self, button: str | int, *, device: int = 0) -> Any:
        return self.input_joypad(type="up", button=button, pressed=False, device=device)

    def joypad_press(
        self,
        button: str | int,
        *,
        pressure: float | None = None,
        device: int = 0,
    ) -> None:
        self.joypad_button_down(button, pressure=pressure, device=device)
        self.joypad_button_up(button, device=device)

    def joypad_axis(self, axis: str | int, value: float, *, device: int = 0) -> Any:
        return self.input_joypad(type="axis", axis=axis, value=value, device=device)

    def trace_start(self, *, clear: bool = True, max_events: int = 1000) -> dict[str, Any]:
        return self.rpc("trace.start", {"clear": clear, "max_events": max_events})

    def trace_stop(self) -> dict[str, Any]:
        return self.rpc("trace.stop")

    def trace_events(
        self,
        *,
        event_type: str | None = None,
        data: dict[str, Any] | None = None,
        clear: bool = False,
    ) -> list[dict[str, Any]]:
        result = self.rpc("trace.events", {"clear": clear})
        events = [event for event in result.get("events", []) if isinstance(event, dict)]
        if event_type is None and data is None:
            return events
        return [
            event
            for event in events
            if _trace_event_matches(event, event_type=event_type, data=data)
        ]

    def trace_count(
        self,
        event_type: str | None = None,
        *,
        data: dict[str, Any] | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
    ) -> int:
        return len(self._matching_trace_events(event_type=event_type, data=data, predicate=predicate))

    def wait_for_trace_event(
        self,
        event_type: str | None = None,
        *,
        data: dict[str, Any] | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_events: list[dict[str, Any]] = []
        while True:
            last_events = self.trace_events(event_type=event_type, data=data)
            for event in last_events:
                if predicate is None or predicate(event):
                    return event
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected trace event type={event_type!r} data={data!r}; got {last_events!r}"
                )
            time.sleep(interval)

    def wait_for_trace_count(
        self,
        expected: int,
        event_type: str | None = None,
        *,
        data: dict[str, Any] | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        at_least: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[dict[str, Any]]:
        if expected < 0:
            raise ValueError("expected must be >= 0")
        deadline = time.monotonic() + timeout
        last_events: list[dict[str, Any]] = []
        while True:
            last_events = self._matching_trace_events(event_type=event_type, data=data, predicate=predicate)
            count = len(last_events)
            matched = count >= expected if at_least else count == expected
            if matched:
                return last_events
            if time.monotonic() >= deadline:
                mode = "at least " if at_least else ""
                raise AssertionError(
                    f"Expected {mode}{expected} trace events type={event_type!r} data={data!r}; "
                    f"got {count}: {last_events!r}"
                )
            time.sleep(interval)

    def wait_for_trace_sequence(
        self,
        event_types: list[str] | tuple[str, ...],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[dict[str, Any]]:
        expected = [str(event_type) for event_type in event_types]
        deadline = time.monotonic() + timeout
        last_events: list[dict[str, Any]] = []
        while True:
            last_events = self.trace_events()
            matched = _trace_event_sequence(last_events, expected)
            if matched is not None:
                return matched
            if time.monotonic() >= deadline:
                got = [str(event.get("type", "")) for event in last_events]
                raise AssertionError(f"Expected trace event sequence {expected!r}; got {got!r}")
            time.sleep(interval)

    def trace_clear(self) -> dict[str, Any]:
        return self.rpc("trace.clear")

    def _matching_trace_events(
        self,
        *,
        event_type: str | None = None,
        data: dict[str, Any] | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
    ) -> list[dict[str, Any]]:
        return [
            event
            for event in self.trace_events(event_type=event_type, data=data)
            if predicate is None or predicate(event)
        ]

    def signal_watch(
        self,
        selector: str | dict[str, Any],
        signal: str,
        *,
        root: str | dict[str, Any] | None = None,
        once: bool = False,
    ) -> dict[str, Any]:
        return self.rpc(
            "signal.watch",
            {
                "selector": selector,
                "root": root or "edited",
                "signal": signal,
                "once": once,
            },
        )

    def signal_unwatch(self, watch_id: str) -> dict[str, Any]:
        return self.rpc("signal.unwatch", {"watch_id": watch_id})

    def signal_events(self, *, watch_id: str | None = None, clear: bool = False) -> list[dict[str, Any]]:
        result = self.rpc("signal.events", {"watch_id": watch_id or "", "clear": clear})
        return list(result.get("events", []))

    def signal_clear(self, *, watch_id: str | None = None) -> dict[str, Any]:
        return self.rpc("signal.clear", {"watch_id": watch_id or ""})

    def _matching_signal_events(
        self,
        *,
        watch_id: str | None = None,
        signal: str | None = None,
        path: str | None = None,
        fields: dict[str, Any] | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
    ) -> list[dict[str, Any]]:
        return [
            event
            for event in self.signal_events(watch_id=watch_id, clear=False)
            if _signal_event_matches(event, signal=signal, path=path, fields=fields, predicate=predicate)
        ]

    def signal_count(
        self,
        *,
        watch_id: str | None = None,
        signal: str | None = None,
        path: str | None = None,
        fields: dict[str, Any] | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
    ) -> int:
        return len(
            self._matching_signal_events(
                watch_id=watch_id,
                signal=signal,
                path=path,
                fields=fields,
                predicate=predicate,
            )
        )

    def wait_for_signal_count(
        self,
        expected: int,
        *,
        watch_id: str | None = None,
        signal: str | None = None,
        path: str | None = None,
        fields: dict[str, Any] | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        at_least: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[dict[str, Any]]:
        deadline = time.monotonic() + timeout
        last_events: list[dict[str, Any]] = []
        while True:
            last_events = self._matching_signal_events(
                watch_id=watch_id,
                signal=signal,
                path=path,
                fields=fields,
                predicate=predicate,
            )
            actual = len(last_events)
            if actual == expected or (at_least and actual >= expected):
                return last_events
            if time.monotonic() >= deadline:
                mode = "at least " if at_least else ""
                raise AssertionError(
                    f"Expected {mode}{expected} signal events watch_id={watch_id!r} "
                    f"signal={signal!r} path={path!r} fields={fields!r}; got {actual}: {last_events!r}"
                )
            time.sleep(interval)

    def wait_for_signal_sequence(
        self,
        expected: list[str | dict[str, Any]] | tuple[str | dict[str, Any], ...],
        *,
        watch_id: str | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
        clear: bool = False,
    ) -> list[dict[str, Any]]:
        expected_items = list(expected)
        deadline = time.monotonic() + timeout
        last_events: list[dict[str, Any]] = []
        while True:
            last_events = self.signal_events(watch_id=watch_id, clear=False)
            matched = _signal_event_sequence(last_events, expected_items)
            if matched is not None:
                if clear:
                    self.signal_clear(watch_id=watch_id)
                return matched
            if time.monotonic() >= deadline:
                got = [
                    {"signal": event.get("signal", ""), "path": event.get("path", "")}
                    for event in last_events
                ]
                raise AssertionError(
                    f"Expected signal event sequence {expected_items!r} watch_id={watch_id!r}; got {got!r}"
                )
            time.sleep(interval)

    def wait_for_signal(
        self,
        selector: str | dict[str, Any],
        signal: str,
        *,
        root: str | dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
        action: Callable[[], Any] | None = None,
        once: bool = True,
    ) -> dict[str, Any]:
        watch = self.signal_watch(selector, signal, root=root, once=once)
        watch_id = str(watch["watch_id"])
        try:
            if action is not None:
                action()
            return self.wait_for_signal_event(
                watch_id=watch_id,
                signal=signal,
                timeout=timeout,
                interval=interval,
                clear=True,
            )
        finally:
            self.signal_unwatch(watch_id)

    def wait_for_signal_event(
        self,
        *,
        watch_id: str | None = None,
        signal: str | None = None,
        path: str | None = None,
        fields: dict[str, Any] | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
        clear: bool = True,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_events: list[dict[str, Any]] = []
        while True:
            last_events = self.signal_events(watch_id=watch_id, clear=False)
            for event in last_events:
                if _signal_event_matches(event, signal=signal, path=path, fields=fields, predicate=predicate):
                    if clear:
                        self.signal_clear(watch_id=watch_id)
                    return event
            if time.monotonic() >= deadline:
                raise GodotPlaywrightError(
                    f"Timed out waiting for signal event watch_id={watch_id!r} signal={signal!r} "
                    f"path={path!r} fields={fields!r}; got {last_events!r}"
                )
            time.sleep(interval)

    def signal_connections(
        self,
        selector: str | dict[str, Any],
        *,
        signal: str = "",
        root: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.rpc(
            "signal.connections",
            {
                "selector": selector,
                "root": root or "edited",
                "signal": signal,
            },
        )

    def wait_for_signal_connection(
        self,
        selector: str | dict[str, Any],
        signal: str,
        *,
        target: str | dict[str, Any] | None = None,
        method: str | None = None,
        persistent: bool | None = None,
        state: str = "connected",
        root: str | dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if state not in {"connected", "disconnected"}:
            raise ValueError("state must be 'connected' or 'disconnected'")
        deadline = time.monotonic() + timeout
        last_connections: list[dict[str, Any]] = []
        while True:
            result = self.signal_connections(selector, signal=signal, root=root or "edited")
            last_connections = [item for item in result.get("connections", []) if isinstance(item, dict)]
            matched = next(
                (
                    connection
                    for connection in last_connections
                    if _signal_connection_matches(
                        connection,
                        signal=signal,
                        target=target,
                        method=method,
                        persistent=persistent,
                    )
                ),
                None,
            )
            if state == "connected" and matched is not None:
                return {"state": state, "connection": matched, "connections": last_connections}
            if state == "disconnected" and matched is None:
                return {"state": state, "connection": None, "connections": last_connections}
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected signal connection on {selector!r} "
                    f"{_signal_connection_filter_summary(signal, target=target, method=method, persistent=persistent)} "
                    f"to be {state}; connections={last_connections!r}"
                )
            time.sleep(interval)

    def signal_connect(
        self,
        selector: str | dict[str, Any],
        signal: str,
        *,
        target: str | dict[str, Any] | None = None,
        method: str,
        root: str | dict[str, Any] | None = None,
        target_root: str | dict[str, Any] | None = None,
        binds: list[Any] | None = None,
        flags: int | None = None,
        persistent: bool | None = True,
        deferred: bool = False,
        one_shot: bool = False,
        reference_counted: bool = False,
        replace: bool = False,
        validate_method: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "selector": selector,
            "root": root or "edited",
            "signal": signal,
            "method": method,
            "binds": binds or [],
            "deferred": deferred,
            "one_shot": one_shot,
            "reference_counted": reference_counted,
            "replace": replace,
            "validate_method": validate_method,
        }
        if target is not None:
            params["target"] = target
        if target_root is not None:
            params["target_root"] = target_root
        if flags is not None:
            params["flags"] = flags
        if persistent is not None:
            params["persistent"] = persistent
        result = self.rpc("signal.connect", params)
        if wait:
            result = dict(result)
            result["connection_state"] = self.wait_for_signal_connection(
                selector,
                signal,
                target=target,
                method=method,
                persistent=persistent,
                root=root or "edited",
                timeout=timeout,
                interval=interval,
            )
        return result

    def signal_disconnect(
        self,
        selector: str | dict[str, Any],
        signal: str,
        *,
        target: str | dict[str, Any] | None = None,
        method: str,
        root: str | dict[str, Any] | None = None,
        target_root: str | dict[str, Any] | None = None,
        binds: list[Any] | None = None,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "selector": selector,
            "root": root or "edited",
            "signal": signal,
            "method": method,
            "binds": binds or [],
        }
        if target is not None:
            params["target"] = target
        if target_root is not None:
            params["target_root"] = target_root
        result = self.rpc("signal.disconnect", params)
        if wait:
            result = dict(result)
            result["connection_state"] = self.wait_for_signal_connection(
                selector,
                signal,
                target=target,
                method=method,
                state="disconnected",
                root=root or "edited",
                timeout=timeout,
                interval=interval,
            )
        return result

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(body))

        connection = http.client.HTTPConnection(self.host, self.port, timeout=timeout or self.timeout)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            data = response.read()
        except (OSError, http.client.HTTPException) as exc:
            raise GodotPlaywrightError(f"Request to Godot failed: {exc}") from exc
        finally:
            connection.close()

        if response.status < 200 or response.status >= 300:
            raise GodotPlaywrightError(f"HTTP {response.status} from Godot: {data[:200]!r}")
        try:
            decoded = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise GodotPlaywrightError(f"Invalid JSON from Godot: {data[:200]!r}") from exc
        if not isinstance(decoded, dict):
            raise GodotPlaywrightError(f"Expected JSON object from Godot, got {type(decoded).__name__}")
        return decoded


class Locator:
    def __init__(
        self,
        client: GodotClient,
        selector: str | dict[str, Any],
        *,
        root: str | dict[str, Any] | None = None,
    ):
        self.client = client
        self.selector = selector
        self.root = root

    def locator(self, selector: str | dict[str, Any]) -> "Locator":
        return Locator(self.client, selector, root=self._root_spec())

    def get_by_role(
        self,
        role: str,
        *,
        name: str | None = None,
        name_contains: str | None = None,
    ) -> "Locator":
        return Locator(
            self.client,
            _role_selector(role, name=name, name_contains=name_contains),
            root=self._root_spec(),
        )

    def get_by_group(self, group: str) -> "Locator":
        return Locator(self.client, _group_selector(group), root=self._root_spec())

    def get_by_text(self, text: str, *, exact: bool = True) -> "Locator":
        return Locator(self.client, _text_selector(text, exact=exact), root=self._root_spec())

    def get_by_placeholder(self, text: str, *, exact: bool = True) -> "Locator":
        return Locator(
            self.client,
            _property_text_selector("placeholder", text, exact=exact),
            root=self._root_spec(),
        )

    def get_by_tooltip(self, text: str, *, exact: bool = True) -> "Locator":
        return Locator(
            self.client,
            _property_text_selector("tooltip", text, exact=exact),
            root=self._root_spec(),
        )

    def get_by_test_id(self, test_id: str, *, key: str = "test_id") -> "Locator":
        return Locator(self.client, _test_id_selector(test_id, key=key), root=self._root_spec())

    def and_(self, selector: "Locator | str | dict[str, Any]") -> "Locator":
        return Locator(
            self.client,
            {"all": [self.selector, _inner_selector(selector)]},
            root=self.root,
        )

    def or_(self, selector: "Locator | str | dict[str, Any]") -> "Locator":
        return Locator(
            self.client,
            {"any": [self.selector, _inner_selector(selector)]},
            root=self.root,
        )

    def filter(
        self,
        *,
        has_text: str | None = None,
        has_text_exact: str | None = None,
        has_not_text: str | None = None,
        has: "Locator | str | dict[str, Any] | None" = None,
        has_not: "Locator | str | dict[str, Any] | None" = None,
    ) -> "Locator":
        selector: dict[str, Any] = {"base": self.selector}
        if has_text is not None:
            selector["has_text"] = has_text
        if has_text_exact is not None:
            selector["has_text_exact"] = has_text_exact
        if has_not_text is not None:
            selector["has_not_text"] = has_not_text
        if has is not None:
            selector["has"] = _inner_selector(has)
        if has_not is not None:
            selector["has_not"] = _inner_selector(has_not)
        return Locator(self.client, selector, root=self.root)

    def nth(self, index: int, *, timeout: float = 5.0, interval: float = 0.05) -> "Locator":
        deadline = time.monotonic() + timeout
        last_count = 0
        while True:
            nodes = self.find(limit=0)
            last_count = len(nodes)
            resolved_index = index if index >= 0 else last_count + index
            if 0 <= resolved_index < last_count:
                path = str(nodes[resolved_index].get("path", ""))
                if path:
                    return Locator(self.client, {"path": path}, root="root")
            if time.monotonic() >= deadline:
                raise GodotPlaywrightError(
                    f"Node index {index} not found for selector {self.selector!r}; count={last_count}"
                )
            time.sleep(interval)

    def first_locator(self, *, timeout: float = 5.0, interval: float = 0.05) -> "Locator":
        return self.nth(0, timeout=timeout, interval=interval)

    def last(self, *, timeout: float = 5.0, interval: float = 0.05) -> "Locator":
        return self.nth(-1, timeout=timeout, interval=interval)

    def all(self) -> list["Locator"]:
        locators: list[Locator] = []
        for node in self.find(limit=0):
            path = str(node.get("path", ""))
            if path:
                locators.append(Locator(self.client, {"path": path}, root="root"))
        return locators

    def all_text_contents(self) -> list[Any]:
        return [locator.get("text") for locator in self.all()]

    def text_contents(self) -> list[str]:
        return _normalize_text_list(self.all_text_contents())

    def wait_for_texts(
        self,
        expected: list[str] | tuple[str, ...],
        *,
        contains: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[str]:
        expected_texts = _normalize_text_list(expected)
        deadline = time.monotonic() + timeout
        last_texts: list[str] = []
        while True:
            last_texts = self.text_contents()
            if _text_list_matches(last_texts, expected_texts, contains=contains):
                return last_texts
            if time.monotonic() >= deadline:
                mode = "to contain" if contains else "to equal"
                raise AssertionError(
                    f"Expected {self.selector!r} text contents {mode} {expected_texts!r}; got {last_texts!r}"
                )
            time.sleep(interval)

    def wait_for_texts_not(
        self,
        unexpected: list[str] | tuple[str, ...],
        *,
        contains: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[str]:
        unexpected_texts = _normalize_text_list(unexpected)
        deadline = time.monotonic() + timeout
        last_texts: list[str] = []
        while True:
            last_texts = self.text_contents()
            if not _text_list_matches(last_texts, unexpected_texts, contains=contains):
                return last_texts
            if time.monotonic() >= deadline:
                mode = "to contain" if contains else "to equal"
                raise AssertionError(
                    f"Expected {self.selector!r} text contents not {mode} {unexpected_texts!r}; got {last_texts!r}"
                )
            time.sleep(interval)

    def first(self, timeout: float = 0.0) -> dict[str, Any]:
        result = self.wait_for(timeout=timeout)
        if result is None:
            raise GodotPlaywrightError(f"Node not found for selector {self.selector!r}")
        return result

    def wait_for(
        self,
        timeout: float = 5.0,
        interval: float = 0.05,
        *,
        state: str = "attached",
    ) -> dict[str, Any] | None:
        if state not in {"attached", "detached", "visible", "hidden"}:
            raise ValueError("state must be one of: attached, detached, visible, hidden")
        deadline = time.monotonic() + timeout
        last_result: list[dict[str, Any]] = []
        last_state: dict[str, Any] | None = None
        while True:
            last_result = self.find(limit=1)
            if state == "attached" and last_result:
                return last_result[0]
            if state == "detached" and not last_result:
                return None
            if state in {"visible", "hidden"}:
                if not last_result:
                    if state == "hidden":
                        return None
                else:
                    try:
                        last_state = self.state()
                    except RpcError as exc:
                        if "Node not found" not in str(exc):
                            raise
                        last_result = []
                        if state == "hidden":
                            return None
                        last_state = None
                        time.sleep(interval)
                        continue
                    visible = bool(last_state.get("visible_in_tree", False))
                    if state == "visible" and visible:
                        return last_state
                    if state == "hidden" and not visible:
                        return last_state
            if time.monotonic() >= deadline:
                detail = f"; count={len(last_result)}"
                if last_state is not None:
                    detail += f"; visible_in_tree={last_state.get('visible_in_tree')!r}"
                raise GodotPlaywrightError(
                    f"Timed out waiting for selector {self.selector!r} to be {state}{detail}"
                )
            time.sleep(interval)

    def find(self, limit: int = 100) -> list[dict[str, Any]]:
        result = self.client.rpc(
            "node.find",
            {"selector": self.selector, "root": self.root or "edited", "limit": limit},
        )
        return list(result.get("nodes", []))

    def count(self) -> int:
        return len(self.find(limit=0))

    def wait_for_count(
        self,
        expected: int | None = None,
        *,
        min_count: int | None = None,
        max_count: int | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> int:
        if expected is not None and (min_count is not None or max_count is not None):
            raise ValueError("Use expected or min_count/max_count, not both")
        if expected is not None:
            min_count = int(expected)
            max_count = int(expected)
        if min_count is None and max_count is None:
            raise ValueError("expected, min_count, or max_count is required")
        if min_count is not None and max_count is not None and int(min_count) > int(max_count):
            raise ValueError("min_count must be <= max_count")
        deadline = time.monotonic() + timeout
        last_count = -1
        while True:
            last_count = self.count()
            if _count_matches(last_count, min_count=min_count, max_count=max_count):
                return last_count
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.selector!r} count {_count_filter_summary(min_count=min_count, max_count=max_count)}; "
                    f"got {last_count}"
                )
            time.sleep(interval)

    def exists(self) -> bool:
        return bool(self.find(limit=1))

    def state(self) -> dict[str, Any]:
        return self.client.rpc(
            "node.state",
            {"selector": self.selector, "root": self.root or "edited"},
        )

    def is_visible(self) -> bool:
        return bool(self.state().get("visible_in_tree", False))

    def is_enabled(self) -> bool:
        return bool(self.state().get("enabled", False))

    def is_disabled(self) -> bool:
        return bool(self.state().get("disabled", False))

    def is_editable(self) -> bool:
        return bool(self.state().get("editable", False))

    def is_focused(self) -> bool:
        return bool(self.state().get("focused", False))

    def is_actionable(self) -> bool:
        return bool(self.state().get("actionable", False))

    def is_checked(self) -> bool:
        return bool(self.state().get("checked", False))

    def input_value(self) -> Any:
        return self.state().get("value")

    def describe(self) -> dict[str, Any]:
        return self.client.rpc(
            "node.describe",
            {"selector": self.selector, "root": self.root or "edited"},
        )

    def snapshot(self, *, max_depth: int = 8, include_properties: bool = False) -> dict[str, Any]:
        return self.client.snapshot(
            root=self._root_spec(),
            max_depth=max_depth,
            include_properties=include_properties,
        )

    def snapshot_nodes(self, *, max_depth: int = 8, include_properties: bool = False) -> list[dict[str, Any]]:
        return _snapshot_nodes(self.snapshot(max_depth=max_depth, include_properties=include_properties))

    def snapshot_texts(self, *, max_depth: int = 8) -> list[str]:
        texts: list[str] = []
        for node in self.snapshot_nodes(max_depth=max_depth, include_properties=True):
            properties = node.get("properties", {})
            if isinstance(properties, dict) and properties.get("text") is not None:
                texts.append(str(properties.get("text")))
        return texts

    def methods(self) -> list[str]:
        return _symbol_names(self.describe().get("methods", []))

    def signals(self) -> list[str]:
        return _symbol_names(self.describe().get("signals", []))

    def has_method(self, name: str) -> bool:
        return name in self.methods()

    def has_signal(self, name: str) -> bool:
        return name in self.signals()

    def bounds(self) -> dict[str, Any]:
        return self.client.rpc("node.bounds", {"selector": self.selector, "root": self.root or "edited"})

    def center(self) -> tuple[float, float]:
        return _center_from_bounds(self.bounds())

    def wait_for_bounds(
        self,
        expected: dict[str, Any] | None = None,
        *,
        x: float | None = None,
        y: float | None = None,
        width: float | None = None,
        height: float | None = None,
        tolerance: float = 0.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        fields = _bounds_expected_fields(expected, x=x, y=y, width=width, height=height)
        deadline = time.monotonic() + timeout
        last_bounds: dict[str, Any] = {}
        while True:
            last_bounds = self.bounds()
            if _bounds_matches(last_bounds, *fields, tolerance=tolerance):
                return last_bounds
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.selector!r} bounds{_bounds_filter_summary(*fields, tolerance=tolerance)}; "
                    f"got {_bounds_geometry_summary(last_bounds)!r}; last={last_bounds!r}"
                )
            time.sleep(interval)

    def wait_for_position(
        self,
        x: float,
        y: float,
        *,
        tolerance: float = 0.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.wait_for_bounds(x=x, y=y, tolerance=tolerance, timeout=timeout, interval=interval)

    def wait_for_size(
        self,
        width: float,
        height: float,
        *,
        tolerance: float = 0.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.wait_for_bounds(width=width, height=height, tolerance=tolerance, timeout=timeout, interval=interval)

    def wait_for_center(
        self,
        x: float,
        y: float,
        *,
        tolerance: float = 0.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> tuple[float, float]:
        deadline = time.monotonic() + timeout
        last_bounds: dict[str, Any] = {}
        last_center: tuple[float, float] | None = None
        while True:
            last_bounds = self.bounds()
            try:
                last_center = _center_from_bounds(last_bounds)
            except GodotPlaywrightError:
                last_center = None
            if last_center is not None and _numbers_match(last_center[0], x, tolerance) and _numbers_match(
                last_center[1], y, tolerance
            ):
                return last_center
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.selector!r} center ({x}, {y}) +/- {tolerance}; "
                    f"got {last_center!r}; last={last_bounds!r}"
                )
            time.sleep(interval)

    def wait_for_within_viewport(
        self,
        *,
        tolerance: float = 0.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_bounds: dict[str, Any] = {}
        last_viewport: dict[str, Any] = {}
        while True:
            last_bounds = self.bounds()
            last_viewport = self.client.viewport_info()
            if _bounds_within_viewport(last_bounds, last_viewport, tolerance=tolerance):
                return {"bounds": last_bounds, "viewport": last_viewport}
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.selector!r} bounds to be within viewport +/- {tolerance}; "
                    f"bounds={_bounds_geometry_summary(last_bounds)!r}; viewport={_viewport_visible_rect(last_viewport)!r}"
                )
            time.sleep(interval)

    def get(self, property_name: str) -> Any:
        result = self.client.rpc(
            "node.get_property",
            {
                "selector": self.selector,
                "root": self.root or "edited",
                "property": property_name,
            },
        )
        return result.get("value")

    def values(
        self,
        properties: list[str] | tuple[str, ...] | str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"selector": self.selector, "root": self.root or "edited"}
        if properties is not None:
            params["properties"] = [properties] if isinstance(properties, str) else list(properties)
        result = self.client.rpc("node.get_properties", params)
        return dict(result.get("values", {}))

    def get_properties(
        self,
        properties: list[str] | tuple[str, ...] | str | None = None,
    ) -> dict[str, Any]:
        return self.values(properties)

    def all_values(
        self,
        properties: list[str] | tuple[str, ...] | str | None = None,
        *,
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        for node in self.find(limit=limit):
            path = str(node.get("path", ""))
            if path:
                values.append(Locator(self.client, {"path": path}, root="root").values(properties))
        return values

    def metadata(
        self,
        names: list[str] | tuple[str, ...] | str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"selector": self.selector, "root": self.root or "edited"}
        if names is not None:
            params["names"] = [names] if isinstance(names, str) else list(names)
        result = self.client.rpc("node.metadata", params)
        return dict(result.get("metadata", result.get("values", {})))

    def get_meta(self, name: str, default: Any = None) -> Any:
        values = self.metadata(name)
        return values.get(name, default)

    def set(
        self,
        property_name: str,
        value: Any,
        *,
        undo: bool | None = None,
        undo_action: str = "",
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> "Locator":
        self.client.set_node_property(
            self.selector,
            property_name,
            value,
            root=self.root or "edited",
            undo=undo,
            undo_action=undo_action,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )
        return self

    def set_properties(
        self,
        values: dict[str, Any],
        *,
        undo: bool | None = None,
        undo_action: str = "",
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> "Locator":
        self.client.set_node_properties(
            self.selector,
            values,
            root=self.root or "edited",
            undo=undo,
            undo_action=undo_action,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )
        return self

    def set_all_properties(
        self,
        values: dict[str, Any],
        *,
        undo: bool | None = None,
        undo_action: str = "",
        limit: int = 0,
    ) -> dict[str, Any]:
        if not values:
            raise ValueError("values must not be empty")
        params: dict[str, Any] = {
            "selector": self.selector,
            "root": self.root or "edited",
            "values": dict(values),
            "limit": limit,
        }
        if undo is not None:
            params["undo"] = undo
        if undo_action:
            params["undo_action"] = undo_action
        return self.client.rpc("node.set_all_properties", params)

    def set_meta(
        self,
        name: str,
        value: Any,
        *,
        undo: bool | None = None,
        undo_action: str = "",
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> "Locator":
        if not name:
            raise ValueError("name must not be empty")
        self.client.set_node_metadata(
            self.selector,
            {name: value},
            root=self.root or "edited",
            undo=undo,
            undo_action=undo_action,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )
        return self

    def set_metadata(
        self,
        values: dict[str, Any],
        *,
        undo: bool | None = None,
        undo_action: str = "",
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> "Locator":
        self.client.set_node_metadata(
            self.selector,
            values,
            root=self.root or "edited",
            undo=undo,
            undo_action=undo_action,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )
        return self

    def remove_meta(
        self,
        names: list[str] | tuple[str, ...] | str,
        *,
        undo: bool | None = None,
        undo_action: str = "",
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> "Locator":
        self.client.remove_node_metadata(
            self.selector,
            names,
            root=self.root or "edited",
            undo=undo,
            undo_action=undo_action,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )
        return self

    def create_child(
        self,
        class_name: str = "Node",
        *,
        name: str = "",
        owner_scene: bool = True,
        undo: bool | None = None,
        undo_action: str = "",
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.create_node(
            self.selector,
            class_name,
            name=name,
            root=self.root or "edited",
            owner_scene=owner_scene,
            undo=undo,
            undo_action=undo_action,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def instantiate_scene(
        self,
        path: str,
        *,
        name: str = "",
        index: int | None = None,
        owner_scene: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.instantiate_scene(
            path,
            parent=self.selector,
            root=self.root or "edited",
            name=name,
            index=index,
            owner_scene=owner_scene,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def group_info(self, *, include_internal: bool = False) -> dict[str, Any]:
        return self.client.node_groups(
            self.selector,
            root=self.root or "edited",
            include_internal=include_internal,
        )

    def groups(self, *, include_internal: bool = False) -> list[str]:
        return [str(group) for group in self.group_info(include_internal=include_internal).get("groups", [])]

    def add_group(
        self,
        group: str,
        *,
        persistent: bool = True,
        include_internal: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.add_node_group(
            self.selector,
            group,
            root=self.root or "edited",
            persistent=persistent,
            include_internal=include_internal,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def remove_group(
        self,
        group: str,
        *,
        include_internal: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.remove_node_group(
            self.selector,
            group,
            root=self.root or "edited",
            include_internal=include_internal,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def reparent(
        self,
        parent: "Locator | str | dict[str, Any]",
        *,
        index: int | None = None,
        keep_global_transform: bool = True,
        owner_scene: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.reparent_node(
            self.selector,
            _inner_selector(parent),
            root=self.root or "edited",
            index=index,
            keep_global_transform=keep_global_transform,
            owner_scene=owner_scene,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def move(
        self,
        index: int,
        *,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.move_node(
            self.selector,
            index,
            root=self.root or "edited",
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def duplicate(
        self,
        *,
        parent: "Locator | str | dict[str, Any] | None" = None,
        name: str = "",
        index: int | None = None,
        flags: int | None = None,
        owner_scene: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.duplicate_node(
            self.selector,
            parent=_inner_selector(parent) if parent is not None else None,
            root=self.root or "edited",
            name=name,
            index=index,
            flags=flags,
            owner_scene=owner_scene,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def attach_script(
        self,
        path: str,
        *,
        inspect: bool = False,
        reload: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.attach_script(
            self.selector,
            path,
            root=self.root or "edited",
            inspect=inspect,
            reload=reload,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def detach_script(
        self,
        *,
        inspect: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.detach_script(
            self.selector,
            root=self.root or "edited",
            inspect=inspect,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def delete(
        self,
        *,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.delete_node(
            self.selector,
            root=self.root or "edited",
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def set_value(self, value: int | float, *, timeout: float = 5.0) -> dict[str, Any]:
        self.wait_for_state("actionable", True, timeout=timeout)
        result = self.client.rpc(
            "node.set_value",
            {"selector": self.selector, "root": self.root or "edited", "value": value},
        )
        self.wait_for_value(result.get("value", value), timeout=timeout)
        return result

    def set_checked(self, checked: bool, *, timeout: float = 5.0) -> "Locator":
        self.wait_for_state("actionable", True, timeout=timeout)
        self.client.rpc(
            "node.set_checked",
            {"selector": self.selector, "root": self.root or "edited", "checked": checked},
        )
        self.wait_for_state("checked", checked, timeout=timeout)
        return self

    def check(self, *, timeout: float = 5.0) -> "Locator":
        return self.set_checked(True, timeout=timeout)

    def uncheck(self, *, timeout: float = 5.0) -> "Locator":
        return self.set_checked(False, timeout=timeout)

    def select_option(
        self,
        option: str | int | dict[str, Any],
        *,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        self.wait_for_state("actionable", True, timeout=timeout)
        return self.client.rpc(
            "node.select_option",
            {"selector": self.selector, "root": self.root or "edited", "option": option},
        )

    def select_tab(
        self,
        tab: str | int | dict[str, Any],
        *,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        self.wait_for_state("actionable", True, timeout=timeout)
        return self.client.rpc(
            "node.select_tab",
            {"selector": self.selector, "root": self.root or "edited", "tab": tab},
        )

    def menu_items(self, *, timeout: float = 5.0) -> list[dict[str, Any]]:
        self.wait_for(timeout=timeout, state="attached")
        result = self.client.rpc(
            "node.menu_items",
            {"selector": self.selector, "root": self.root or "edited"},
        )
        return list(result.get("items", []))

    def select_menu_item(
        self,
        item: str | int | dict[str, Any],
        *,
        checked: bool | None = None,
        close: bool = True,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        self.wait_for(timeout=timeout, state="attached")
        params: dict[str, Any] = {
            "selector": self.selector,
            "root": self.root or "edited",
            "item": item,
            "close": close,
        }
        if checked is not None:
            params["checked"] = checked
        return self.client.rpc("node.select_menu_item", params)

    def select_item(
        self,
        item: str | int | dict[str, Any] | list[str | int | dict[str, Any]],
        *,
        replace: bool = True,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        self.wait_for_state("actionable", True, timeout=timeout)
        result = self.client.rpc(
            "node.select_item",
            {
                "selector": self.selector,
                "root": self.root or "edited",
                "item": item,
                "replace": replace,
            },
        )
        if "value" in result:
            self.wait_for_value(result["value"], timeout=timeout)
        return result

    def select_tree_item(
        self,
        item: str | int | dict[str, Any] | list[str | int | dict[str, Any]],
        *,
        replace: bool = True,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        self.wait_for_state("actionable", True, timeout=timeout)
        result = self.client.rpc(
            "node.select_tree_item",
            {
                "selector": self.selector,
                "root": self.root or "edited",
                "item": item,
                "replace": replace,
            },
        )
        if "value" in result:
            self.wait_for_value(result["value"], timeout=timeout)
        return result

    def call(self, method: str, *args: Any) -> Any:
        result = self.client.rpc(
            "node.call",
            {
                "selector": self.selector,
                "root": self.root or "edited",
                "method": method,
                "args": list(args),
            },
        )
        return result.get("value")

    def call_all(
        self,
        method: str,
        *args: Any,
        limit: int = 0,
        strict: bool = True,
    ) -> list[dict[str, Any]]:
        result = self.client.rpc(
            "node.call_all",
            {
                "selector": self.selector,
                "root": self.root or "edited",
                "method": method,
                "args": list(args),
                "limit": limit,
                "strict": strict,
            },
        )
        return list(result.get("results", []))

    def call_all_values(
        self,
        method: str,
        *args: Any,
        limit: int = 0,
        strict: bool = True,
    ) -> list[Any]:
        return [entry.get("value") for entry in self.call_all(method, *args, limit=limit, strict=strict)]

    def evaluate(
        self,
        expression: str,
        variables: dict[str, Any] | None = None,
        **inputs: Any,
    ) -> Any:
        result = self.client.rpc(
            "node.evaluate",
            {
                "selector": self.selector,
                "root": self.root or "edited",
                "expression": expression,
                "variables": _merged_variables(variables, inputs),
            },
        )
        return result.get("value")

    def evaluate_all(
        self,
        expression: str,
        variables: dict[str, Any] | None = None,
        *,
        limit: int = 0,
        **inputs: Any,
    ) -> Any:
        result = self.client.rpc(
            "node.evaluate_all",
            {
                "selector": self.selector,
                "root": self.root or "edited",
                "expression": expression,
                "variables": _merged_variables(variables, inputs),
                "limit": limit,
            },
        )
        return result.get("value")

    def wait_for_function(
        self,
        expression: str,
        variables: dict[str, Any] | None = None,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
        predicate: Callable[[Any], bool] | None = None,
        **inputs: Any,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last_value: Any = None
        while True:
            last_value = self.evaluate(expression, variables, **inputs)
            if predicate is not None:
                if predicate(last_value):
                    return last_value
            elif last_value:
                return last_value
            if time.monotonic() >= deadline:
                raise GodotPlaywrightError(
                    f"Timed out waiting for {self.selector!r} function {expression!r}; last value was {last_value!r}"
                )
            time.sleep(interval)

    def wait_for_expression(
        self,
        expression: str,
        expected: Any,
        variables: dict[str, Any] | None = None,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
        **inputs: Any,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last_value: Any = None
        while True:
            last_value = self.evaluate(expression, variables, **inputs)
            if last_value == expected:
                return last_value
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.selector!r} expression {expression!r} to be {expected!r}; got {last_value!r}"
                )
            time.sleep(interval)

    def wait_for_expression_not(
        self,
        expression: str,
        unexpected: Any,
        variables: dict[str, Any] | None = None,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
        **inputs: Any,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last_value: Any = None
        while True:
            last_value = self.evaluate(expression, variables, **inputs)
            if last_value != unexpected:
                return last_value
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.selector!r} expression {expression!r} not to be {unexpected!r}"
                )
            time.sleep(interval)

    def click(self, *, button: int = 1, timeout: float = 5.0) -> None:
        self.wait_for_state("actionable", True, timeout=timeout)
        self.client.rpc(
            "node.click",
            {"selector": self.selector, "root": self.root or "edited", "button": button},
        )

    def dialog(self) -> dict[str, Any]:
        return self.client.rpc(
            "node.dialog",
            {"selector": self.selector, "root": self.root or "edited"},
        )

    def accept_dialog(self, *, close: bool = True, timeout: float = 5.0) -> dict[str, Any]:
        self.wait_for(state="visible", timeout=timeout)
        return self.client.rpc(
            "node.accept_dialog",
            {"selector": self.selector, "root": self.root or "edited", "close": close},
        )

    def dismiss_dialog(self, *, close: bool = True, timeout: float = 5.0) -> dict[str, Any]:
        self.wait_for(state="visible", timeout=timeout)
        return self.client.rpc(
            "node.dismiss_dialog",
            {"selector": self.selector, "root": self.root or "edited", "close": close},
        )

    def hover(self, *, timeout: float = 5.0) -> None:
        self.wait_for_state("visible_in_tree", True, timeout=timeout)
        x, y = _center_from_bounds(self.bounds())
        self.client.mouse_move(x, y)

    def drag_to(
        self,
        target: "Locator | str | dict[str, Any]",
        *,
        button: int = MOUSE_BUTTON_LEFT,
        steps: int = 10,
        timeout: float = 5.0,
    ) -> None:
        target_locator = target if isinstance(target, Locator) else self.client.locator(target, root=self.root)
        self.wait_for_state("actionable", True, timeout=timeout)
        target_locator.wait_for_state("actionable", True, timeout=timeout)
        start_x, start_y = _center_from_bounds(self.bounds())
        end_x, end_y = _center_from_bounds(target_locator.bounds())
        button_mask = MOUSE_BUTTON_MASKS.get(button, 0)

        self.client.mouse_move(start_x, start_y)
        self.client.mouse_down(start_x, start_y, button=button)
        step_count = max(1, int(steps))
        for index in range(1, step_count + 1):
            fraction = index / step_count
            self.client.mouse_move(
                start_x + (end_x - start_x) * fraction,
                start_y + (end_y - start_y) * fraction,
                button_mask=button_mask,
            )
        self.client.mouse_up(end_x, end_y, button=button)

    def scroll(self, *, delta_x: float = 0.0, delta_y: float = 0.0, timeout: float = 5.0) -> None:
        self.wait_for_state("visible_in_tree", True, timeout=timeout)
        x, y = _center_from_bounds(self.bounds())
        self.client.mouse_wheel(x, y, delta_x=delta_x, delta_y=delta_y)

    def tap(self, *, index: int = 0, timeout: float = 5.0) -> None:
        self.wait_for_state("visible_in_tree", True, timeout=timeout)
        x, y = _center_from_bounds(self.bounds())
        self.client.tap(x, y, index=index)

    def touch_drag_to(
        self,
        target: "Locator | str | dict[str, Any]",
        *,
        index: int = 0,
        steps: int = 10,
        timeout: float = 5.0,
    ) -> None:
        target_locator = target if isinstance(target, Locator) else self.client.locator(target, root=self.root)
        self.wait_for_state("visible_in_tree", True, timeout=timeout)
        target_locator.wait_for_state("visible_in_tree", True, timeout=timeout)
        start_x, start_y = _center_from_bounds(self.bounds())
        end_x, end_y = _center_from_bounds(target_locator.bounds())
        self.client.touch_down(start_x, start_y, index=index)
        step_count = max(1, int(steps))
        for step in range(1, step_count + 1):
            fraction = step / step_count
            self.client.touch_move(
                start_x + (end_x - start_x) * fraction,
                start_y + (end_y - start_y) * fraction,
                index=index,
            )
        self.client.touch_up(end_x, end_y, index=index)

    def focus(self, *, timeout: float = 5.0) -> None:
        self.wait_for_state("focusable", True, timeout=timeout)
        self.client.rpc(
            "node.focus",
            {"selector": self.selector, "root": self.root or "edited"},
        )

    def fill(self, text: str, *, timeout: float = 5.0) -> None:
        self.wait_for_state("editable", True, timeout=timeout)
        self.client.rpc(
            "node.fill",
            {"selector": self.selector, "root": self.root or "edited", "text": text},
        )

    def press(
        self,
        key: str | int,
        *,
        timeout: float = 5.0,
        modifiers: list[str] | tuple[str, ...] | str | None = None,
        shift: bool = False,
        ctrl: bool = False,
        alt: bool = False,
        meta: bool = False,
        command_or_control: bool = False,
    ) -> None:
        self.focus(timeout=timeout)
        self.client.press(
            key,
            modifiers=modifiers,
            shift=shift,
            ctrl=ctrl,
            alt=alt,
            meta=meta,
            command_or_control=command_or_control,
        )

    def type(self, text: str, *, timeout: float = 5.0) -> None:
        self.focus(timeout=timeout)
        self.client.input_text(text)

    def wait_for_signal(
        self,
        signal: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
        action: Callable[[], Any] | None = None,
    ) -> dict[str, Any]:
        return self.client.wait_for_signal(
            self.selector,
            signal,
            root=self.root or "edited",
            timeout=timeout,
            interval=interval,
            action=action,
            once=True,
        )

    def signal_connections(self, signal: str = "") -> dict[str, Any]:
        return self.client.signal_connections(self.selector, signal=signal, root=self.root or "edited")

    def connect_signal(
        self,
        signal: str,
        *,
        target: "Locator | str | dict[str, Any] | None" = None,
        method: str,
        target_root: str | dict[str, Any] | None = None,
        binds: list[Any] | None = None,
        flags: int | None = None,
        persistent: bool | None = True,
        deferred: bool = False,
        one_shot: bool = False,
        reference_counted: bool = False,
        replace: bool = False,
        validate_method: bool = True,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.signal_connect(
            self.selector,
            signal,
            target=_inner_selector(target) if target is not None else None,
            method=method,
            root=self.root or "edited",
            target_root=target_root,
            binds=binds,
            flags=flags,
            persistent=persistent,
            deferred=deferred,
            one_shot=one_shot,
            reference_counted=reference_counted,
            replace=replace,
            validate_method=validate_method,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def disconnect_signal(
        self,
        signal: str,
        *,
        target: "Locator | str | dict[str, Any] | None" = None,
        method: str,
        target_root: str | dict[str, Any] | None = None,
        binds: list[Any] | None = None,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.signal_disconnect(
            self.selector,
            signal,
            target=_inner_selector(target) if target is not None else None,
            method=method,
            root=self.root or "edited",
            target_root=target_root,
            binds=binds,
            wait=wait,
            timeout=timeout,
            interval=interval,
        )

    def save_as_scene(self, path: str, *, overwrite: bool = True) -> dict[str, Any]:
        return self.client.save_node_as_scene(
            self.selector,
            path,
            root=self.root or "edited",
            overwrite=overwrite,
        )

    def animation_describe(self, *, include_tracks: bool = False) -> dict[str, Any]:
        return self.client.animation_describe(
            self.selector,
            root=self.root or "edited",
            include_tracks=include_tracks,
        )

    def camera3d_ray(self, screen_x: float, screen_y: float, *, max_distance: float = 1000.0) -> dict[str, Any]:
        return self.client.camera3d_ray(
            screen_x,
            screen_y,
            camera=self.selector,
            root=self.root or "edited",
            max_distance=max_distance,
        )

    def camera3d_pick(
        self,
        screen_x: float,
        screen_y: float,
        *,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_distance: float = 1000.0,
    ) -> dict[str, Any]:
        return self.client.camera3d_pick(
            screen_x,
            screen_y,
            camera=self.selector,
            root=self.root or "edited",
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            max_distance=max_distance,
        )

    def pick_3d(
        self,
        screen_x: float,
        screen_y: float,
        *,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_distance: float = 1000.0,
    ) -> dict[str, Any]:
        return self.camera3d_pick(
            screen_x,
            screen_y,
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            max_distance=max_distance,
        )

    def hover_3d(
        self,
        screen_x: float,
        screen_y: float,
        *,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_distance: float = 1000.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        pick = self._wait_for_3d_pick(
            screen_x,
            screen_y,
            name=name,
            path=path,
            class_name=class_name,
            groups=groups,
            metadata=metadata,
            fields=fields,
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            max_distance=max_distance,
            timeout=timeout,
            interval=interval,
        )
        self.client.mouse_move(screen_x, screen_y)
        return pick

    def click_3d(
        self,
        screen_x: float,
        screen_y: float,
        *,
        button: int = MOUSE_BUTTON_LEFT,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_distance: float = 1000.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        pick = self._wait_for_3d_pick(
            screen_x,
            screen_y,
            name=name,
            path=path,
            class_name=class_name,
            groups=groups,
            metadata=metadata,
            fields=fields,
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            max_distance=max_distance,
            timeout=timeout,
            interval=interval,
        )
        self.client.mouse_click(screen_x, screen_y, button=button)
        return pick

    def drag_3d(
        self,
        screen_x: float,
        screen_y: float,
        to_x: float,
        to_y: float,
        *,
        button: int = MOUSE_BUTTON_LEFT,
        steps: int = 10,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_distance: float = 1000.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        pick = self._wait_for_3d_pick(
            screen_x,
            screen_y,
            name=name,
            path=path,
            class_name=class_name,
            groups=groups,
            metadata=metadata,
            fields=fields,
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            max_distance=max_distance,
            timeout=timeout,
            interval=interval,
        )
        button_mask = MOUSE_BUTTON_MASKS.get(button, 0)
        self.client.mouse_move(screen_x, screen_y)
        self.client.mouse_down(screen_x, screen_y, button=button)
        step_count = max(1, int(steps))
        for index in range(1, step_count + 1):
            fraction = index / step_count
            self.client.mouse_move(
                screen_x + (to_x - screen_x) * fraction,
                screen_y + (to_y - screen_y) * fraction,
                button_mask=button_mask,
            )
        self.client.mouse_up(to_x, to_y, button=button)
        return pick

    def _wait_for_3d_pick(
        self,
        screen_x: float,
        screen_y: float,
        *,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_distance: float = 1000.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.camera3d_pick(
                screen_x,
                screen_y,
                collision_mask=collision_mask,
                collide_with_bodies=collide_with_bodies,
                collide_with_areas=collide_with_areas,
                max_distance=max_distance,
            )
            if bool(last.get("hit")) and _physics2d_collision_matches(
                last.get("collision", {}),
                name=name,
                path=path,
                class_name=class_name,
                groups=groups,
                metadata=metadata,
                fields=fields,
            ):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected 3D camera pick ({screen_x}, {screen_y}) to collide"
                    f"{_physics2d_filter_summary(name=name, path=path, class_name=class_name, groups=groups, metadata=metadata, fields=fields)}; "
                    f"last={last!r}"
                )
            time.sleep(interval)

    def play_animation(
        self,
        animation: str = "",
        *,
        blend: float = -1.0,
        speed: float = 1.0,
        from_end: bool = False,
        position: float | None = None,
        update: bool = True,
        update_only: bool = False,
        include_tracks: bool = False,
    ) -> dict[str, Any]:
        return self.client.animation_play(
            self.selector,
            animation,
            root=self.root or "edited",
            blend=blend,
            speed=speed,
            from_end=from_end,
            position=position,
            update=update,
            update_only=update_only,
            include_tracks=include_tracks,
        )

    def stop_animation(self, *, keep_state: bool = False, include_tracks: bool = False) -> dict[str, Any]:
        return self.client.animation_stop(
            self.selector,
            root=self.root or "edited",
            keep_state=keep_state,
            include_tracks=include_tracks,
        )

    def pause_animation(self, *, include_tracks: bool = False) -> dict[str, Any]:
        return self.client.animation_pause(
            self.selector,
            root=self.root or "edited",
            include_tracks=include_tracks,
        )

    def seek_animation(
        self,
        position: float,
        *,
        update: bool = True,
        update_only: bool = False,
        include_tracks: bool = False,
    ) -> dict[str, Any]:
        return self.client.animation_seek(
            self.selector,
            position,
            root=self.root or "edited",
            update=update,
            update_only=update_only,
            include_tracks=include_tracks,
        )

    def advance_animation(
        self,
        delta: float,
        *,
        update: bool = True,
        update_only: bool = False,
        include_tracks: bool = False,
    ) -> dict[str, Any]:
        return self.client.animation_advance(
            self.selector,
            delta,
            root=self.root or "edited",
            update=update,
            update_only=update_only,
            include_tracks=include_tracks,
        )

    def wait_for_property(
        self,
        property_name: str,
        expected: Any,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last_value: Any = None
        while True:
            last_value = self.get(property_name)
            if last_value == expected:
                return last_value
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.selector!r}.{property_name} to be {expected!r}, got {last_value!r}"
                )
            time.sleep(interval)

    def wait_for_property_not(
        self,
        property_name: str,
        unexpected: Any,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last_value: Any = None
        while True:
            last_value = self.get(property_name)
            if last_value != unexpected:
                return last_value
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.selector!r}.{property_name} not to be {unexpected!r}"
                )
            time.sleep(interval)

    def wait_for_properties(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if not expected:
            raise ValueError("expected must not be empty")
        deadline = time.monotonic() + timeout
        last_values: dict[str, Any] = {}
        while True:
            last_values = self.values(list(expected))
            if _dict_contains(last_values, expected):
                return last_values
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.selector!r} properties to include {expected!r}; got {last_values!r}"
                )
            time.sleep(interval)

    def wait_for_properties_not(
        self,
        unexpected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if not unexpected:
            raise ValueError("unexpected must not be empty")
        deadline = time.monotonic() + timeout
        last_values: dict[str, Any] = {}
        while True:
            last_values = self.values(list(unexpected))
            if not _dict_contains(last_values, unexpected):
                return last_values
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.selector!r} properties not to include {unexpected!r}; got {last_values!r}"
                )
            time.sleep(interval)

    def wait_for_all_properties(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[dict[str, Any]]:
        if not expected:
            raise ValueError("expected must not be empty")
        deadline = time.monotonic() + timeout
        last_values: list[dict[str, Any]] = []
        while True:
            last_values = self.all_values(list(expected))
            if last_values and all(_dict_contains(values, expected) for values in last_values):
                return last_values
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected all {self.selector!r} matches to include {expected!r}; got {last_values!r}"
                )
            time.sleep(interval)

    def wait_for_all_properties_not(
        self,
        unexpected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[dict[str, Any]]:
        if not unexpected:
            raise ValueError("unexpected must not be empty")
        deadline = time.monotonic() + timeout
        last_values: list[dict[str, Any]] = []
        while True:
            last_values = self.all_values(list(unexpected))
            if not last_values or all(not _dict_contains(values, unexpected) for values in last_values):
                return last_values
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected all {self.selector!r} matches not to include {unexpected!r}; got {last_values!r}"
                )
            time.sleep(interval)

    def wait_for_meta(
        self,
        name: str,
        expected: Any = _UNSET,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last_values: dict[str, Any] = {}
        while True:
            last_values = self.metadata(name)
            if name in last_values and (expected is _UNSET or last_values[name] == expected):
                return last_values[name]
            if time.monotonic() >= deadline:
                suffix = "" if expected is _UNSET else f" to be {expected!r}"
                raise AssertionError(
                    f"Expected {self.selector!r} metadata {name!r}{suffix}; got {last_values!r}"
                )
            time.sleep(interval)

    def wait_for_meta_not(
        self,
        name: str,
        unexpected: Any = _UNSET,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_values: dict[str, Any] = {}
        while True:
            last_values = self.metadata(name)
            if name not in last_values:
                return last_values
            if unexpected is not _UNSET and last_values.get(name) != unexpected:
                return last_values
            if time.monotonic() >= deadline:
                suffix = "" if unexpected is _UNSET else f" to be {unexpected!r}"
                raise AssertionError(
                    f"Expected {self.selector!r} metadata {name!r} not{suffix}; got {last_values!r}"
                )
            time.sleep(interval)

    def wait_for_metadata(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if not expected:
            raise ValueError("expected must not be empty")
        deadline = time.monotonic() + timeout
        last_values: dict[str, Any] = {}
        while True:
            last_values = self.metadata(list(expected))
            if _dict_contains(last_values, expected):
                return last_values
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.selector!r} metadata to include {expected!r}; got {last_values!r}"
                )
            time.sleep(interval)

    def wait_for_metadata_not(
        self,
        unexpected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if not unexpected:
            raise ValueError("unexpected must not be empty")
        deadline = time.monotonic() + timeout
        last_values: dict[str, Any] = {}
        while True:
            last_values = self.metadata(list(unexpected))
            if not _dict_contains(last_values, unexpected):
                return last_values
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.selector!r} metadata not to include {unexpected!r}; got {last_values!r}"
                )
            time.sleep(interval)

    def wait_for_state(
        self,
        state_name: str,
        expected: Any = True,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_state: dict[str, Any] = {}
        while True:
            last_state = self.state()
            if last_state.get(state_name) == expected:
                return last_state
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.selector!r} state {state_name!r} to be {expected!r}, "
                    f"got {last_state.get(state_name)!r}; last={last_state!r}"
                )
            time.sleep(interval)

    def wait_for_states(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if not expected:
            raise ValueError("expected must not be empty")
        deadline = time.monotonic() + timeout
        last_state: dict[str, Any] = {}
        while True:
            last_state = self.state()
            if _dict_contains(last_state, expected):
                return last_state
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.selector!r} state to include {expected!r}; last={last_state!r}"
                )
            time.sleep(interval)

    def wait_for_states_not(
        self,
        unexpected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if not unexpected:
            raise ValueError("unexpected must not be empty")
        deadline = time.monotonic() + timeout
        last_state: dict[str, Any] = {}
        while True:
            last_state = self.state()
            if not _dict_contains(last_state, unexpected):
                return last_state
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.selector!r} state not to include {unexpected!r}; last={last_state!r}"
                )
            time.sleep(interval)

    def wait_for_value(
        self,
        expected: Any,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last_value: Any = None
        while True:
            last_value = self.input_value()
            if last_value == expected:
                return last_value
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected {self.selector!r} value to be {expected!r}, got {last_value!r}")
            time.sleep(interval)

    def wait_for_value_not(
        self,
        unexpected: Any,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last_value: Any = None
        while True:
            last_value = self.input_value()
            if last_value != unexpected:
                return last_value
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected {self.selector!r} value not to be {unexpected!r}")
            time.sleep(interval)

    def _root_spec(self) -> dict[str, Any]:
        return {"selector": self.selector, "root": self.root or "edited"}


class Inspector:
    def __init__(
        self,
        client: GodotClient,
        *,
        selector: str | dict[str, Any] | None = None,
        path: str | None = None,
        resource_path: str | None = None,
        root: str | dict[str, Any] | None = None,
    ):
        self.client = client
        self.selector = selector
        self.path = path
        self.resource_path = resource_path
        self.root = root

    def describe(
        self,
        *,
        include_values: bool = True,
        properties: list[str] | None = None,
        name_contains: str = "",
        include_internal: bool = False,
        inspect: bool = False,
        property: str = "",
        inspector_only: bool = False,
    ) -> dict[str, Any]:
        params = self._base_params()
        params.update(
            {
                "include_values": include_values,
                "properties": properties or [],
                "name_contains": name_contains,
                "include_internal": include_internal,
                "inspect": inspect,
                "property": property,
                "inspector_only": inspector_only,
            }
        )
        return self.client.rpc("editor.inspector.describe", params)

    def get(self, property_name: str) -> dict[str, Any]:
        params = self._base_params()
        params["property"] = property_name
        return self.client.rpc("editor.inspector.get_property", params)

    def value(self, property_name: str) -> Any:
        return self.get(property_name).get("value")

    def values(
        self,
        properties: list[str] | tuple[str, ...] | None = None,
        *,
        name_contains: str = "",
        include_internal: bool = False,
    ) -> dict[str, Any]:
        description = self.describe(
            include_values=True,
            properties=list(properties or []),
            name_contains=name_contains,
            include_internal=include_internal,
        )
        values: dict[str, Any] = {}
        for property_info in description.get("properties", []):
            if isinstance(property_info, dict) and property_info.get("exists", True):
                values[str(property_info.get("name", ""))] = property_info.get("value")
        return values

    def wait_for_description(
        self,
        *,
        properties: list[str] | tuple[str, ...] | None = None,
        include_values: bool = True,
        name_contains: str = "",
        include_internal: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected_properties = [str(name) for name in list(properties or []) if str(name)]
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.describe(
                include_values=include_values,
                properties=expected_properties,
                name_contains=name_contains,
                include_internal=include_internal,
            )
            if not expected_properties:
                return last
            property_names = {
                str(property_info.get("name", ""))
                for property_info in last.get("properties", [])
                if isinstance(property_info, dict) and property_info.get("exists", True)
            }
            if all(name in property_names for name in expected_properties):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected inspector description to include properties {expected_properties!r}; last={last!r}"
                )
            time.sleep(interval)

    def wait_for_property(
        self,
        property_name: str,
        expected: Any = _UNSET,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            result = self.get(property_name)
            last = dict(result.get("property", {}))
            if last.get("exists", False) and (expected is _UNSET or last.get("value") == expected):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected inspector property {property_name!r} to be {expected!r}; last={last!r}"
                )
            time.sleep(interval)

    def wait_for_properties(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if not expected:
            raise ValueError("expected must not be empty")
        deadline = time.monotonic() + timeout
        last_values: dict[str, Any] = {}
        while True:
            last_values = self.values(properties=list(expected))
            if _dict_contains(last_values, expected):
                return last_values
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected inspector properties to include {expected!r}; got {last_values!r}"
                )
            time.sleep(interval)

    def set(
        self,
        property_name: str,
        value: Any,
        *,
        save: bool = False,
        inspect: bool = True,
        inspector_only: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        params = self._base_params()
        params.update(
            {
                "property": property_name,
                "value": value,
                "save": save,
                "inspect": inspect,
                "inspector_only": inspector_only,
            }
        )
        result = self.client.rpc("editor.inspector.set_property", params)
        if wait:
            result = dict(result)
            result["property_state"] = self.wait_for_property(
                property_name,
                value,
                timeout=timeout,
                interval=interval,
            )
        return result

    def set_properties(
        self,
        values: dict[str, Any],
        *,
        save: bool = False,
        inspect: bool = True,
        inspector_only: bool = False,
        wait: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if not values:
            raise ValueError("values must not be empty")
        params = self._base_params()
        params.update(
            {
                "values": dict(values),
                "save": save,
                "inspect": inspect,
                "inspector_only": inspector_only,
            }
        )
        result = self.client.rpc("editor.inspector.set_properties", params)
        if wait:
            result = dict(result)
            result["properties_state"] = self.wait_for_properties(
                values,
                timeout=timeout,
                interval=interval,
            )
        return result

    def property(self, property_name: str) -> "InspectorProperty":
        return InspectorProperty(self, property_name)

    def _base_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {"root": self.root or "edited"}
        if self.selector is not None:
            params["selector"] = self.selector
        if self.path is not None:
            params["path"] = self.path
        if self.resource_path is not None:
            params["resource_path"] = self.resource_path
        return params


class InspectorProperty:
    def __init__(self, inspector: Inspector, property_name: str):
        self.inspector = inspector
        self.property_name = property_name

    def describe(self, **kwargs: Any) -> dict[str, Any]:
        return self.inspector.describe(properties=[self.property_name], **kwargs)

    def get(self) -> dict[str, Any]:
        return self.inspector.get(self.property_name)

    def value(self) -> Any:
        return self.inspector.value(self.property_name)

    def set(self, value: Any, **kwargs: Any) -> dict[str, Any]:
        return self.inspector.set(self.property_name, value, **kwargs)


def _center_from_bounds(bounds: dict[str, Any]) -> tuple[float, float]:
    rect = _bounds_rect(bounds)
    if rect is not None:
        return (rect["x"] + rect["width"] / 2.0, rect["y"] + rect["height"] / 2.0)
    point = _bounds_point(bounds)
    if point is not None:
        return point
    raise GodotPlaywrightError(f"Node bounds do not include a rect or point: {bounds!r}")


def _bounds_expected_fields(
    expected: dict[str, Any] | None = None,
    *,
    x: float | None = None,
    y: float | None = None,
    width: float | None = None,
    height: float | None = None,
) -> tuple[float | None, float | None, float | None, float | None]:
    if expected is None:
        return (
            _optional_float(x),
            _optional_float(y),
            _optional_float(width),
            _optional_float(height),
        )
    if not isinstance(expected, dict):
        raise TypeError("expected must be a bounds dict")
    source: Any = expected
    if isinstance(expected.get("rect"), dict):
        source = expected["rect"]
    elif isinstance(expected.get("point"), dict):
        source = expected["point"]
    if not isinstance(source, dict):
        raise TypeError("expected must contain bounds fields")
    return (
        _optional_float(x if x is not None else source.get("x")),
        _optional_float(y if y is not None else source.get("y")),
        _optional_float(width if width is not None else source.get("width")),
        _optional_float(height if height is not None else source.get("height")),
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _numbers_match(actual: Any, expected: float, tolerance: float = 0.0) -> bool:
    try:
        return abs(float(actual) - float(expected)) <= float(tolerance)
    except (TypeError, ValueError):
        return False


def _bounds_rect(bounds: dict[str, Any]) -> dict[str, float] | None:
    rect = bounds.get("rect")
    if not isinstance(rect, dict):
        return None
    try:
        return {
            "x": float(rect.get("x")),
            "y": float(rect.get("y")),
            "width": float(rect.get("width")),
            "height": float(rect.get("height")),
        }
    except (TypeError, ValueError):
        return None


def _bounds_point(bounds: dict[str, Any]) -> tuple[float, float] | None:
    point = bounds.get("point")
    if not isinstance(point, dict):
        return None
    try:
        return (float(point.get("x")), float(point.get("y")))
    except (TypeError, ValueError):
        return None


def _bounds_position(bounds: dict[str, Any]) -> tuple[float, float] | None:
    rect = _bounds_rect(bounds)
    if rect is not None:
        return (rect["x"], rect["y"])
    return _bounds_point(bounds)


def _bounds_size(bounds: dict[str, Any]) -> tuple[float, float] | None:
    rect = _bounds_rect(bounds)
    if rect is None:
        return None
    return (rect["width"], rect["height"])


def _bounds_matches(
    bounds: dict[str, Any],
    x: float | None,
    y: float | None,
    width: float | None,
    height: float | None,
    *,
    tolerance: float = 0.0,
) -> bool:
    if x is None and y is None and width is None and height is None:
        return _bounds_rect(bounds) is not None or _bounds_point(bounds) is not None

    if x is not None or y is not None:
        position = _bounds_position(bounds)
        if position is None:
            return False
        if x is not None and not _numbers_match(position[0], x, tolerance):
            return False
        if y is not None and not _numbers_match(position[1], y, tolerance):
            return False

    if width is not None or height is not None:
        size = _bounds_size(bounds)
        if size is None:
            return False
        if width is not None and not _numbers_match(size[0], width, tolerance):
            return False
        if height is not None and not _numbers_match(size[1], height, tolerance):
            return False

    return True


def _bounds_within_viewport(
    bounds: dict[str, Any],
    viewport: dict[str, Any],
    *,
    tolerance: float = 0.0,
) -> bool:
    visible_rect = _viewport_visible_rect(viewport)
    if visible_rect is None:
        return False
    left = visible_rect["x"] - tolerance
    top = visible_rect["y"] - tolerance
    right = visible_rect["x"] + visible_rect["width"] + tolerance
    bottom = visible_rect["y"] + visible_rect["height"] + tolerance

    rect = _bounds_rect(bounds)
    if rect is not None:
        return (
            rect["x"] >= left
            and rect["y"] >= top
            and rect["x"] + rect["width"] <= right
            and rect["y"] + rect["height"] <= bottom
        )
    point = _bounds_point(bounds)
    if point is None:
        return False
    return left <= point[0] <= right and top <= point[1] <= bottom


def _bounds_geometry_summary(bounds: dict[str, Any]) -> dict[str, Any]:
    rect = _bounds_rect(bounds)
    if rect is not None:
        return {"rect": rect}
    point = _bounds_point(bounds)
    if point is not None:
        return {"point": {"x": point[0], "y": point[1]}}
    return {}


def _bounds_filter_summary(
    x: float | None,
    y: float | None,
    width: float | None,
    height: float | None,
    *,
    tolerance: float = 0.0,
) -> str:
    parts: list[str] = []
    if x is not None:
        parts.append(f"x={x!r}")
    if y is not None:
        parts.append(f"y={y!r}")
    if width is not None:
        parts.append(f"width={width!r}")
    if height is not None:
        parts.append(f"height={height!r}")
    if tolerance:
        parts.append(f"tolerance={tolerance!r}")
    return "" if not parts else " " + ", ".join(parts)


def _count_matches(count: int, *, min_count: int | None = None, max_count: int | None = None) -> bool:
    if min_count is not None and count < int(min_count):
        return False
    if max_count is not None and count > int(max_count):
        return False
    return True


def _count_filter_summary(*, min_count: int | None = None, max_count: int | None = None) -> str:
    if min_count is not None and max_count is not None and int(min_count) == int(max_count):
        return f"to be {int(min_count)}"
    if min_count is not None and max_count is not None:
        return f"to be between {int(min_count)} and {int(max_count)}"
    if min_count is not None:
        return f"to be at least {int(min_count)}"
    if max_count is not None:
        return f"to be at most {int(max_count)}"
    return "to match count constraints"


def _normalize_text_list(values: list[Any] | tuple[Any, ...]) -> list[str]:
    return ["" if value is None else str(value) for value in values]


def _text_list_matches(actual: list[str], expected: list[str], *, contains: bool = False) -> bool:
    if len(actual) != len(expected):
        return False
    if contains:
        return all(expected_text in actual_text for actual_text, expected_text in zip(actual, expected))
    return actual == expected


def _role_selector(
    role: str,
    *,
    name: str | None = None,
    name_contains: str | None = None,
) -> dict[str, Any]:
    selector: dict[str, Any] = {"role": role}
    if name is not None:
        selector["role_name"] = name
    if name_contains is not None:
        selector["name_contains"] = name_contains
    return selector


def _group_selector(group: str) -> dict[str, Any]:
    return {"group": group}


def _text_selector(text: str, *, exact: bool = True) -> dict[str, Any]:
    return {"text": text} if exact else {"text_contains": text}


def _property_text_selector(property_name: str, text: str, *, exact: bool = True) -> dict[str, Any]:
    if exact:
        return {property_name: text}
    return {f"{property_name}_contains": text}


def _test_id_selector(test_id: str, *, key: str = "test_id") -> dict[str, Any]:
    if key == "test_id":
        return {"test_id": test_id}
    return {"metadata": {key: test_id}}


def _inner_selector(selector: "Locator | str | dict[str, Any]") -> str | dict[str, Any]:
    if isinstance(selector, Locator):
        return selector.selector
    return selector


def _merged_variables(variables: dict[str, Any] | None, inputs: dict[str, Any]) -> dict[str, Any]:
    merged = dict(variables or {})
    merged.update(inputs)
    return merged


def _symbol_names(symbols: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(symbols, (list, tuple)):
        return names
    for entry in symbols:
        if isinstance(entry, dict):
            name = entry.get("name", "")
        else:
            name = entry
        if name is not None:
            names.append(str(name))
    return names


def _snapshot_nodes(snapshot: Any) -> list[dict[str, Any]]:
    if not isinstance(snapshot, dict):
        return []
    nodes = [snapshot]
    for child in snapshot.get("children", []):
        nodes.extend(_snapshot_nodes(child))
    return nodes


def _snapshot_node_matches(
    node: dict[str, Any],
    *,
    name: str | None = None,
    class_name: str | None = None,
    path: str | None = None,
    properties: dict[str, Any] | None = None,
) -> bool:
    if name is not None and node.get("name") != name:
        return False
    if class_name is not None and node.get("class") != class_name:
        return False
    if path is not None and node.get("path") != path:
        return False
    if properties is not None:
        actual_properties = node.get("properties", {})
        if not isinstance(actual_properties, dict) or not _dict_contains(actual_properties, properties):
            return False
    return True


def _snapshot_node_filter_summary(
    *,
    name: str | None = None,
    class_name: str | None = None,
    path: str | None = None,
    properties: dict[str, Any] | None = None,
) -> str:
    filters: list[str] = []
    if name is not None:
        filters.append(f"name={name!r}")
    if class_name is not None:
        filters.append(f"class_name={class_name!r}")
    if path is not None:
        filters.append(f"path={path!r}")
    if properties is not None:
        filters.append(f"properties={properties!r}")
    return "" if not filters else " with " + ", ".join(filters)


def _snapshot_node_brief(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": node.get("name"),
            "class": node.get("class"),
            "path": node.get("path"),
        }
        for node in nodes
    ]


class Godot:
    def __init__(
        self,
        project_path: str | Path,
        *,
        mode: str = "editor",
        executable: str = "godot",
        host: str = "127.0.0.1",
        port: int | None = None,
        headless: bool = True,
        install: bool = True,
        autoload: bool | None = None,
        timeout: float = 20.0,
        extra_args: list[str] | None = None,
        stdout: Any = subprocess.DEVNULL,
        capture_logs: bool = True,
        log_max_events: int = 5000,
    ):
        self.project_path = Path(project_path).expanduser().resolve()
        self.mode = mode
        self.executable = executable
        self.host = host
        self._explicit_port = port is not None
        self.port = port or find_free_port(host)
        self.headless = headless
        self.install = install
        self.autoload = (mode == "runtime") if autoload is None else autoload
        self.timeout = timeout
        self.extra_args = extra_args or []
        self.stdout = stdout
        self.capture_logs = capture_logs
        self.log_max_events = log_max_events
        self.process: subprocess.Popen[Any] | None = None
        self.client = GodotClient(host, self.port, timeout=timeout)
        self._log_collector: _GodotLogCollector | None = None
        self.port_retry_count = 0

    def __enter__(self) -> GodotClient:
        self.start()
        return self.client

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def start(self) -> GodotClient:
        if self.install:
            install_addon(
                self.project_path,
                enable=self.mode == "editor",
                autoload=bool(self.autoload),
            )

        attempts = 1 if self._explicit_port else 3
        last_error: BaseException | None = None
        for attempt in range(attempts):
            if attempt > 0:
                self.port = find_free_port(self.host)
                self.client = GodotClient(self.host, self.port, timeout=self.timeout)
                self.port_retry_count = attempt
            try:
                return self._start_once()
            except BaseException as exc:
                last_error = exc
                should_retry = attempt < attempts - 1 and self._start_failure_may_be_port_race(exc)
                self.close()
                if not should_retry:
                    raise
        assert last_error is not None
        raise last_error

    def _start_once(self) -> GodotClient:
        env = isolated_godot_env(
            host=self.host,
            port=self.port,
            strict_port=self._explicit_port,
            namespace=f"live-{self.mode}",
        )

        cmd = [self.executable, "--path", str(self.project_path)]
        if self.headless:
            cmd.append("--headless")
        if self.mode == "editor":
            cmd.append("--editor")
        elif self.mode == "runtime":
            pass
        else:
            raise ValueError("mode must be 'editor' or 'runtime'")
        cmd.extend(self.extra_args)

        stdout_target = self.stdout
        stderr_target = subprocess.STDOUT if self.stdout is not None else None
        if self.capture_logs:
            self._log_collector = _GodotLogCollector(
                tee=_log_tee_target(self.stdout),
                max_events=self.log_max_events,
            )
            self.client._log_collector = self._log_collector
            stdout_target = subprocess.PIPE
            stderr_target = subprocess.STDOUT

        self.process = subprocess.Popen(
            cmd,
            cwd=self.project_path,
            env=env,
            stdout=stdout_target,
            stderr=stderr_target,
            text=True,
            bufsize=1,
        )
        if self._log_collector is not None and self.process.stdout is not None:
            self._log_collector.start(self.process.stdout)
        try:
            self.client.wait_for_ready(timeout=self.timeout)
        except BaseException:
            self.close()
            raise
        return self.client

    def _start_failure_may_be_port_race(self, error: BaseException) -> bool:
        if self._explicit_port:
            return False
        text = str(error).lower()
        if self._log_collector is not None:
            text += "\n" + self._log_collector.text().lower()
        if "failed to listen" in text or "address already in use" in text:
            return True
        return "did not become ready" in text

    def close(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self._log_collector is not None:
            self._log_collector.close()
        self.process = None


def _log_tee_target(stdout: Any) -> Any:
    if stdout == subprocess.DEVNULL:
        return None
    if stdout is None:
        return sys.stdout
    return stdout


class Expect:
    def __init__(self, locator: Locator):
        self.locator = locator

    def _expected_parent_path(self, parent: str | "Locator" | dict[str, Any]) -> str:
        selector = _inner_selector(parent)
        if isinstance(parent, Locator):
            return str(parent.describe().get("path", ""))
        if isinstance(selector, dict) and str(selector.get("path", "")).startswith("/"):
            return str(selector["path"])
        if isinstance(selector, str) and selector.startswith("/"):
            return selector
        return str(self.locator.client.locator(selector, root=self.locator.root or "edited").describe().get("path", ""))

    def to_exist(self, timeout: float = 5.0) -> dict[str, Any]:
        result = self.locator.wait_for(timeout=timeout, state="attached")
        if result is None:
            raise AssertionError(f"Expected {self.locator.selector!r} to exist")
        return result

    def to_be_attached(self, timeout: float = 5.0) -> dict[str, Any]:
        return self.to_exist(timeout=timeout)

    def not_to_exist(self, timeout: float = 5.0) -> None:
        self.locator.wait_for(timeout=timeout, state="detached")

    def to_be_detached(self, timeout: float = 5.0) -> None:
        self.not_to_exist(timeout=timeout)

    def to_have_property(self, property_name: str, expected: Any, timeout: float = 5.0) -> None:
        self.locator.wait_for_property(property_name, expected, timeout=timeout)

    def not_to_have_property(self, property_name: str, unexpected: Any, timeout: float = 5.0) -> None:
        self.locator.wait_for_property_not(property_name, unexpected, timeout=timeout)

    def to_have_properties(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.locator.wait_for_properties(expected, timeout=timeout, interval=interval)

    def not_to_have_properties(
        self,
        unexpected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.locator.wait_for_properties_not(unexpected, timeout=timeout, interval=interval)

    def to_have_all_properties(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[dict[str, Any]]:
        return self.locator.wait_for_all_properties(expected, timeout=timeout, interval=interval)

    def not_to_have_all_properties(
        self,
        unexpected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[dict[str, Any]]:
        return self.locator.wait_for_all_properties_not(unexpected, timeout=timeout, interval=interval)

    def to_have_meta(
        self,
        name: str,
        expected: Any = _UNSET,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> Any:
        return self.locator.wait_for_meta(name, expected, timeout=timeout, interval=interval)

    def not_to_have_meta(
        self,
        name: str,
        unexpected: Any = _UNSET,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.locator.wait_for_meta_not(name, unexpected, timeout=timeout, interval=interval)

    def to_have_metadata(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.locator.wait_for_metadata(expected, timeout=timeout, interval=interval)

    def not_to_have_metadata(
        self,
        unexpected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.locator.wait_for_metadata_not(unexpected, timeout=timeout, interval=interval)

    def to_match_expression(
        self,
        expression: str,
        expected: Any = _UNSET,
        variables: dict[str, Any] | None = None,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
        **inputs: Any,
    ) -> Any:
        if expected is _UNSET:
            return self.locator.wait_for_function(
                expression,
                variables,
                timeout=timeout,
                interval=interval,
                **inputs,
            )
        return self.locator.wait_for_expression(
            expression,
            expected,
            variables,
            timeout=timeout,
            interval=interval,
            **inputs,
        )

    def not_to_match_expression(
        self,
        expression: str,
        unexpected: Any,
        variables: dict[str, Any] | None = None,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
        **inputs: Any,
    ) -> Any:
        return self.locator.wait_for_expression_not(
            expression,
            unexpected,
            variables,
            timeout=timeout,
            interval=interval,
            **inputs,
        )

    def to_have_text(self, expected: str, timeout: float = 5.0) -> None:
        self.to_have_property("text", expected, timeout=timeout)

    def not_to_have_text(self, unexpected: str, timeout: float = 5.0) -> None:
        self.not_to_have_property("text", unexpected, timeout=timeout)

    def to_have_texts(
        self,
        expected: list[str] | tuple[str, ...],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[str]:
        return self.locator.wait_for_texts(expected, timeout=timeout, interval=interval)

    def to_contain_texts(
        self,
        expected: list[str] | tuple[str, ...],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[str]:
        return self.locator.wait_for_texts(expected, contains=True, timeout=timeout, interval=interval)

    def not_to_have_texts(
        self,
        unexpected: list[str] | tuple[str, ...],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[str]:
        return self.locator.wait_for_texts_not(unexpected, timeout=timeout, interval=interval)

    def to_have_value(self, expected: Any, timeout: float = 5.0) -> None:
        self.locator.wait_for_value(expected, timeout=timeout)

    def not_to_have_value(self, unexpected: Any, timeout: float = 5.0) -> None:
        self.locator.wait_for_value_not(unexpected, timeout=timeout)

    def to_have_state(
        self,
        state_name: str,
        expected: Any = True,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.locator.wait_for_state(state_name, expected, timeout=timeout, interval=interval)

    def not_to_have_state(
        self,
        state_name: str,
        unexpected: Any = True,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.locator.wait_for_states_not({state_name: unexpected}, timeout=timeout, interval=interval)

    def to_match_state(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.locator.wait_for_states(expected, timeout=timeout, interval=interval)

    def not_to_match_state(
        self,
        unexpected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.locator.wait_for_states_not(unexpected, timeout=timeout, interval=interval)

    def to_match_node(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if not expected:
            raise ValueError("expected must not be empty")
        return self.locator.client.wait_for_node(
            self.locator.selector,
            root=self.locator.root or "edited",
            expected=expected,
            timeout=timeout,
            interval=interval,
        )

    def not_to_match_node(
        self,
        unexpected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if not unexpected:
            raise ValueError("unexpected must not be empty")
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.locator.describe()
            if not _dict_contains(last, unexpected):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.locator.selector!r} node summary not to include {unexpected!r}; got {last!r}"
                )
            time.sleep(interval)

    def to_have_parent(
        self,
        parent: str | "Locator" | dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected_parent = self._expected_parent_path(parent)
        return self.to_match_node({"parent": expected_parent}, timeout=timeout, interval=interval)

    def not_to_have_parent(
        self,
        parent: str | "Locator" | dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected_parent = self._expected_parent_path(parent)
        return self.not_to_match_node({"parent": expected_parent}, timeout=timeout, interval=interval)

    def to_have_index(
        self,
        index: int,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.to_match_node({"index": index}, timeout=timeout, interval=interval)

    def not_to_have_index(
        self,
        index: int,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.not_to_match_node({"index": index}, timeout=timeout, interval=interval)

    def to_have_child_count(
        self,
        count: int,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.to_match_node({"child_count": count}, timeout=timeout, interval=interval)

    def not_to_have_child_count(
        self,
        count: int,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.not_to_match_node({"child_count": count}, timeout=timeout, interval=interval)

    def to_be_visible(self, timeout: float = 5.0) -> None:
        self.locator.wait_for(timeout=timeout, state="visible")

    def not_to_be_visible(self, timeout: float = 5.0) -> None:
        self.locator.wait_for(timeout=timeout, state="hidden")

    def to_be_hidden(self, timeout: float = 5.0) -> None:
        self.not_to_be_visible(timeout=timeout)

    def to_be_enabled(self, timeout: float = 5.0) -> None:
        self.locator.wait_for_state("enabled", True, timeout=timeout)

    def not_to_be_enabled(self, timeout: float = 5.0) -> None:
        self.locator.wait_for_state("enabled", False, timeout=timeout)

    def to_be_disabled(self, timeout: float = 5.0) -> None:
        self.locator.wait_for_state("disabled", True, timeout=timeout)

    def not_to_be_disabled(self, timeout: float = 5.0) -> None:
        self.locator.wait_for_state("disabled", False, timeout=timeout)

    def to_be_editable(self, timeout: float = 5.0) -> None:
        self.locator.wait_for_state("editable", True, timeout=timeout)

    def not_to_be_editable(self, timeout: float = 5.0) -> None:
        self.locator.wait_for_state("editable", False, timeout=timeout)

    def to_be_focused(self, timeout: float = 5.0) -> None:
        self.locator.wait_for_state("focused", True, timeout=timeout)

    def not_to_be_focused(self, timeout: float = 5.0) -> None:
        self.locator.wait_for_state("focused", False, timeout=timeout)

    def to_be_actionable(self, timeout: float = 5.0) -> None:
        self.locator.wait_for_state("actionable", True, timeout=timeout)

    def not_to_be_actionable(self, timeout: float = 5.0) -> None:
        self.locator.wait_for_state("actionable", False, timeout=timeout)

    def to_be_focusable(self, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self.to_have_state("focusable", True, timeout=timeout, interval=interval)

    def not_to_be_focusable(self, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self.not_to_have_state("focusable", True, timeout=timeout, interval=interval)

    def to_receive_input(self, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self.to_have_state("receives_input", True, timeout=timeout, interval=interval)

    def not_to_receive_input(self, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self.not_to_have_state("receives_input", True, timeout=timeout, interval=interval)

    def to_be_checked(self, timeout: float = 5.0) -> None:
        self.locator.wait_for_state("checked", True, timeout=timeout)

    def not_to_be_checked(self, timeout: float = 5.0) -> None:
        self.locator.wait_for_state("checked", False, timeout=timeout)

    def to_have_bounds(
        self,
        expected: dict[str, Any] | None = None,
        *,
        x: float | None = None,
        y: float | None = None,
        width: float | None = None,
        height: float | None = None,
        tolerance: float = 0.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.locator.wait_for_bounds(
            expected,
            x=x,
            y=y,
            width=width,
            height=height,
            tolerance=tolerance,
            timeout=timeout,
            interval=interval,
        )

    def to_have_position(
        self,
        x: float,
        y: float,
        *,
        tolerance: float = 0.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.locator.wait_for_position(x, y, tolerance=tolerance, timeout=timeout, interval=interval)

    def to_have_size(
        self,
        width: float,
        height: float,
        *,
        tolerance: float = 0.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.locator.wait_for_size(width, height, tolerance=tolerance, timeout=timeout, interval=interval)

    def to_have_center(
        self,
        x: float,
        y: float,
        *,
        tolerance: float = 0.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> tuple[float, float]:
        return self.locator.wait_for_center(x, y, tolerance=tolerance, timeout=timeout, interval=interval)

    def to_be_within_viewport(
        self,
        *,
        tolerance: float = 0.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.locator.wait_for_within_viewport(tolerance=tolerance, timeout=timeout, interval=interval)

    def to_have_count(self, expected: int, timeout: float = 5.0, interval: float = 0.05) -> int:
        return self.locator.wait_for_count(expected, timeout=timeout, interval=interval)

    def to_have_count_at_least(
        self,
        min_count: int,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> int:
        return self.locator.wait_for_count(min_count=min_count, timeout=timeout, interval=interval)

    def to_have_count_at_most(
        self,
        max_count: int,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> int:
        return self.locator.wait_for_count(max_count=max_count, timeout=timeout, interval=interval)

    def to_have_count_between(
        self,
        min_count: int,
        max_count: int,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> int:
        return self.locator.wait_for_count(
            min_count=min_count,
            max_count=max_count,
            timeout=timeout,
            interval=interval,
        )

    def to_be_empty(self, timeout: float = 5.0, interval: float = 0.05) -> int:
        return self.to_have_count(0, timeout=timeout, interval=interval)

    def not_to_be_empty(self, timeout: float = 5.0, interval: float = 0.05) -> int:
        return self.to_have_count_at_least(1, timeout=timeout, interval=interval)

    def not_to_have_count(self, unexpected: int, timeout: float = 5.0, interval: float = 0.05) -> int:
        deadline = time.monotonic() + timeout
        last_count = -1
        while True:
            last_count = self.locator.count()
            if last_count != unexpected:
                return last_count
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.locator.selector!r} count not to be {unexpected}, got {last_count}"
                )
            time.sleep(interval)

    def to_have_group(
        self,
        group: str,
        *,
        include_internal: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_groups: list[str] = []
        while True:
            result = self.locator.client.node_groups(
                self.locator.selector,
                root=self.locator.root or "edited",
                include_internal=include_internal,
            )
            last_groups = [str(item) for item in result.get("groups", [])]
            if group in last_groups:
                return result
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.locator.selector!r} to be in group {group!r}; groups={last_groups!r}"
                )
            time.sleep(interval)

    def not_to_have_group(
        self,
        group: str,
        *,
        include_internal: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> None:
        deadline = time.monotonic() + timeout
        last_groups: list[str] = []
        while True:
            result = self.locator.client.node_groups(
                self.locator.selector,
                root=self.locator.root or "edited",
                include_internal=include_internal,
            )
            last_groups = [str(item) for item in result.get("groups", [])]
            if group not in last_groups:
                return
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.locator.selector!r} not to be in group {group!r}; groups={last_groups!r}"
                )
            time.sleep(interval)

    def to_have_script(
        self,
        path: str | None = None,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last_script: Any = None
        while True:
            last_script = self.locator.get("script")
            script_path = _script_resource_path(last_script)
            if path is None:
                if last_script:
                    return last_script
            elif script_path == path:
                return last_script
            if time.monotonic() >= deadline:
                if path is None:
                    expected = "a script"
                else:
                    expected = f"script {path!r}"
                raise AssertionError(
                    f"Expected {self.locator.selector!r} to have {expected}; script={last_script!r}"
                )
            time.sleep(interval)

    def not_to_have_script(
        self,
        path: str | None = None,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> None:
        deadline = time.monotonic() + timeout
        last_script: Any = None
        while True:
            last_script = self.locator.get("script")
            script_path = _script_resource_path(last_script)
            if path is None:
                if not last_script:
                    return
            elif script_path != path:
                return
            if time.monotonic() >= deadline:
                if path is None:
                    expected = "a script"
                else:
                    expected = f"script {path!r}"
                raise AssertionError(
                    f"Expected {self.locator.selector!r} not to have {expected}; script={last_script!r}"
                )
            time.sleep(interval)

    def to_pick_camera_collision(
        self,
        screen_x: float,
        screen_y: float,
        *,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_distance: float = 1000.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return Physics3DExpect(self.locator.client).to_pick_camera_collision(
            screen_x,
            screen_y,
            camera=self.locator.selector,
            root=self.locator.root or "edited",
            name=name,
            path=path,
            class_name=class_name,
            groups=groups,
            metadata=metadata,
            fields=fields,
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            max_distance=max_distance,
            timeout=timeout,
            interval=interval,
        )

    def not_to_pick_camera_collision(
        self,
        screen_x: float,
        screen_y: float,
        *,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_distance: float = 1000.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return Physics3DExpect(self.locator.client).not_to_pick_camera_collision(
            screen_x,
            screen_y,
            camera=self.locator.selector,
            root=self.locator.root or "edited",
            name=name,
            path=path,
            class_name=class_name,
            groups=groups,
            metadata=metadata,
            fields=fields,
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            max_distance=max_distance,
            timeout=timeout,
            interval=interval,
        )

    def to_have_animation(
        self,
        name: str,
        *,
        length: float | None = None,
        loop_mode: int | None = None,
        track_count: int | None = None,
        track: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        include_tracks = track is not None
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.locator.animation_describe(include_tracks=include_tracks)
            entry = _animation_entry(
                last,
                name,
                length=length,
                loop_mode=loop_mode,
                track_count=track_count,
                track=track,
                fields=fields,
            )
            if entry is not None:
                return entry
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.locator.selector!r} to have animation {name!r}"
                    f"{_animation_filter_summary(length=length, loop_mode=loop_mode, track_count=track_count, track=track, fields=fields)}; "
                    f"animations={last.get('animations', [])!r}"
                )
            time.sleep(interval)

    def not_to_have_animation(
        self,
        name: str,
        *,
        length: float | None = None,
        loop_mode: int | None = None,
        track_count: int | None = None,
        track: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> None:
        include_tracks = track is not None
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.locator.animation_describe(include_tracks=include_tracks)
            entry = _animation_entry(
                last,
                name,
                length=length,
                loop_mode=loop_mode,
                track_count=track_count,
                track=track,
                fields=fields,
            )
            if entry is None:
                return
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.locator.selector!r} not to have animation {name!r}"
                    f"{_animation_filter_summary(length=length, loop_mode=loop_mode, track_count=track_count, track=track, fields=fields)}; "
                    f"matched={entry!r}"
                )
            time.sleep(interval)

    def to_be_playing_animation(
        self,
        animation: str | None = None,
        *,
        position: float | None = None,
        speed_scale: float | None = None,
        tolerance: float = 0.01,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.locator.animation_describe()
            if _animation_playback_matches(
                last,
                playing=True,
                animation=animation,
                position=position,
                speed_scale=speed_scale,
                tolerance=tolerance,
            ):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.locator.selector!r} to be playing animation"
                    f"{_animation_playback_filter_summary(animation=animation, position=position, speed_scale=speed_scale)}; "
                    f"last={last!r}"
                )
            time.sleep(interval)

    def not_to_be_playing_animation(
        self,
        animation: str | None = None,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.locator.animation_describe()
            if not _animation_playback_matches(last, playing=True, animation=animation):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.locator.selector!r} not to be playing animation"
                    f"{_animation_playback_filter_summary(animation=animation)}; last={last!r}"
                )
            time.sleep(interval)

    def to_have_method(
        self,
        name: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> str:
        deadline = time.monotonic() + timeout
        last_methods: list[str] = []
        while True:
            last_methods = self.locator.methods()
            if name in last_methods:
                return name
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.locator.selector!r} to have method {name!r}; methods={last_methods!r}"
                )
            time.sleep(interval)

    def not_to_have_method(
        self,
        name: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> None:
        deadline = time.monotonic() + timeout
        last_methods: list[str] = []
        while True:
            last_methods = self.locator.methods()
            if name not in last_methods:
                return
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.locator.selector!r} not to have method {name!r}; methods={last_methods!r}"
                )
            time.sleep(interval)

    def to_have_signal(
        self,
        name: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> str:
        deadline = time.monotonic() + timeout
        last_signals: list[str] = []
        while True:
            last_signals = self.locator.signals()
            if name in last_signals:
                return name
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.locator.selector!r} to have signal {name!r}; signals={last_signals!r}"
                )
            time.sleep(interval)

    def not_to_have_signal(
        self,
        name: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> None:
        deadline = time.monotonic() + timeout
        last_signals: list[str] = []
        while True:
            last_signals = self.locator.signals()
            if name not in last_signals:
                return
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.locator.selector!r} not to have signal {name!r}; signals={last_signals!r}"
                )
            time.sleep(interval)

    def to_contain_node(
        self,
        *,
        name: str | None = None,
        class_name: str | None = None,
        path: str | None = None,
        properties: dict[str, Any] | None = None,
        max_depth: int = 8,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_nodes: list[dict[str, Any]] = []
        include_properties = properties is not None
        while True:
            last_nodes = self.locator.snapshot_nodes(max_depth=max_depth, include_properties=include_properties)
            for node in last_nodes:
                if _snapshot_node_matches(node, name=name, class_name=class_name, path=path, properties=properties):
                    return node
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.locator.selector!r} subtree to contain node"
                    f"{_snapshot_node_filter_summary(name=name, class_name=class_name, path=path, properties=properties)}; "
                    f"nodes={_snapshot_node_brief(last_nodes)!r}"
                )
            time.sleep(interval)

    def not_to_contain_node(
        self,
        *,
        name: str | None = None,
        class_name: str | None = None,
        path: str | None = None,
        properties: dict[str, Any] | None = None,
        max_depth: int = 8,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> None:
        deadline = time.monotonic() + timeout
        last_match: dict[str, Any] | None = None
        include_properties = properties is not None
        while True:
            nodes = self.locator.snapshot_nodes(max_depth=max_depth, include_properties=include_properties)
            last_match = next(
                (
                    node
                    for node in nodes
                    if _snapshot_node_matches(node, name=name, class_name=class_name, path=path, properties=properties)
                ),
                None,
            )
            if last_match is None:
                return
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected {self.locator.selector!r} subtree not to contain node"
                    f"{_snapshot_node_filter_summary(name=name, class_name=class_name, path=path, properties=properties)}; "
                    f"matched={last_match!r}"
                )
            time.sleep(interval)

    def to_contain_text(
        self,
        text: str,
        *,
        exact: bool = True,
        max_depth: int = 8,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> str:
        deadline = time.monotonic() + timeout
        last_texts: list[str] = []
        while True:
            last_texts = self.locator.snapshot_texts(max_depth=max_depth)
            for actual in last_texts:
                if actual == text or (not exact and text in actual):
                    return actual
            if time.monotonic() >= deadline:
                mode = "text" if exact else "text containing"
                raise AssertionError(
                    f"Expected {self.locator.selector!r} subtree to contain {mode} {text!r}; texts={last_texts!r}"
                )
            time.sleep(interval)

    def not_to_contain_text(
        self,
        text: str,
        *,
        exact: bool = True,
        max_depth: int = 8,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> None:
        deadline = time.monotonic() + timeout
        last_match: str | None = None
        while True:
            last_texts = self.locator.snapshot_texts(max_depth=max_depth)
            last_match = next(
                (actual for actual in last_texts if actual == text or (not exact and text in actual)),
                None,
            )
            if last_match is None:
                return
            if time.monotonic() >= deadline:
                mode = "text" if exact else "text containing"
                raise AssertionError(
                    f"Expected {self.locator.selector!r} subtree not to contain {mode} {text!r}; matched={last_match!r}"
                )
            time.sleep(interval)

    def to_have_signal_connection(
        self,
        signal: str,
        *,
        target: "Locator | str | dict[str, Any] | None" = None,
        method: str | None = None,
        persistent: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_connections: list[dict[str, Any]] = []
        while True:
            result = self.locator.signal_connections(signal)
            last_connections = [item for item in result.get("connections", []) if isinstance(item, dict)]
            for connection in last_connections:
                if _signal_connection_matches(
                    connection,
                    signal=signal,
                    target=target,
                    method=method,
                    persistent=persistent,
                ):
                    return connection
            if time.monotonic() >= deadline:
                raise AssertionError(
                    "Expected "
                    f"{self.locator.selector!r} to have signal connection "
                    f"{_signal_connection_filter_summary(signal, target=target, method=method, persistent=persistent)}; "
                    f"connections={last_connections!r}"
                )
            time.sleep(interval)

    def not_to_have_signal_connection(
        self,
        signal: str,
        *,
        target: "Locator | str | dict[str, Any] | None" = None,
        method: str | None = None,
        persistent: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> None:
        deadline = time.monotonic() + timeout
        last_match: dict[str, Any] | None = None
        while True:
            result = self.locator.signal_connections(signal)
            connections = [item for item in result.get("connections", []) if isinstance(item, dict)]
            last_match = next(
                (
                    connection
                    for connection in connections
                    if _signal_connection_matches(
                        connection,
                        signal=signal,
                        target=target,
                        method=method,
                        persistent=persistent,
                    )
                ),
                None,
            )
            if last_match is None:
                return
            if time.monotonic() >= deadline:
                raise AssertionError(
                    "Expected "
                    f"{self.locator.selector!r} not to have signal connection "
                    f"{_signal_connection_filter_summary(signal, target=target, method=method, persistent=persistent)}; "
                    f"matched={last_match!r}"
                )
            time.sleep(interval)

def _animation_entry(
    state: dict[str, Any],
    name: str,
    *,
    length: float | None = None,
    loop_mode: int | None = None,
    track_count: int | None = None,
    track: dict[str, Any] | None = None,
    fields: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    for entry in state.get("animations", []):
        if not isinstance(entry, dict) or entry.get("name") != name:
            continue
        if length is not None and not _float_close(entry.get("length"), length):
            continue
        if loop_mode is not None and int(entry.get("loop_mode", -1)) != loop_mode:
            continue
        if track_count is not None and int(entry.get("track_count", 0)) != track_count:
            continue
        if track is not None and _animation_track_entry(entry, track) is None:
            continue
        if fields is not None and not _dict_contains(entry, fields):
            continue
        return entry
    return None


def _animation_track_entry(animation: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any] | None:
    for track in animation.get("tracks", []):
        if isinstance(track, dict) and _dict_contains(track, expected):
            return track
    return None


def _animation_filter_summary(
    *,
    length: float | None = None,
    loop_mode: int | None = None,
    track_count: int | None = None,
    track: dict[str, Any] | None = None,
    fields: dict[str, Any] | None = None,
) -> str:
    filters = []
    if length is not None:
        filters.append(f"length={length!r}")
    if loop_mode is not None:
        filters.append(f"loop_mode={loop_mode!r}")
    if track_count is not None:
        filters.append(f"track_count={track_count!r}")
    if track is not None:
        filters.append(f"track={track!r}")
    if fields is not None:
        filters.append(f"fields={fields!r}")
    return "" if not filters else " with " + ", ".join(filters)


def _animation_playback_matches(
    state: dict[str, Any],
    *,
    playing: bool,
    animation: str | None = None,
    position: float | None = None,
    speed_scale: float | None = None,
    tolerance: float = 0.01,
) -> bool:
    if bool(state.get("is_playing")) != playing:
        return False
    if animation is not None and state.get("current_animation") != animation:
        return False
    if position is not None and not _float_close(state.get("position"), position, tolerance=tolerance):
        return False
    if speed_scale is not None and not _float_close(state.get("speed_scale"), speed_scale, tolerance=tolerance):
        return False
    return True


def _animation_playback_filter_summary(
    *,
    animation: str | None = None,
    position: float | None = None,
    speed_scale: float | None = None,
) -> str:
    filters = []
    if animation is not None:
        filters.append(f"animation={animation!r}")
    if position is not None:
        filters.append(f"position={position!r}")
    if speed_scale is not None:
        filters.append(f"speed_scale={speed_scale!r}")
    return "" if not filters else " with " + ", ".join(filters)


def _float_close(actual: Any, expected: float, *, tolerance: float = 0.000001) -> bool:
    try:
        return abs(float(actual) - float(expected)) <= tolerance
    except (TypeError, ValueError):
        return False


def _script_resource_path(script: Any) -> str:
    if isinstance(script, dict):
        return str(script.get("path") or script.get("resource_path") or "")
    if isinstance(script, str):
        return script
    return ""


def _signal_connection_matches(
    connection: dict[str, Any],
    *,
    signal: str,
    target: "Locator | str | dict[str, Any] | None" = None,
    method: str | None = None,
    persistent: bool | None = None,
) -> bool:
    if signal and connection.get("signal") != signal:
        return False
    if method is not None and connection.get("method") != method:
        return False
    if persistent is not None and bool(connection.get("persistent", False)) != persistent:
        return False
    if target is not None and not _signal_target_matches(connection, target):
        return False
    return True


def _signal_target_matches(connection: dict[str, Any], target: "Locator | str | dict[str, Any]") -> bool:
    selector = _inner_selector(target)
    target_path = str(connection.get("target_path", ""))
    target_name = target_path.rsplit("/", 1)[-1] if target_path else ""
    if isinstance(selector, dict):
        if selector.get("path") is not None:
            return target_path == str(selector.get("path"))
        if selector.get("name") is not None:
            return target_name == str(selector.get("name"))
        if selector.get("test_id") is not None:
            return target_name == str(selector.get("test_id")).title().replace("-", "")
        metadata = selector.get("metadata", selector.get("meta", {}))
        if isinstance(metadata, dict) and metadata.get("test_id") is not None:
            return target_name == str(metadata.get("test_id")).title().replace("-", "")
        return False
    text = str(selector)
    if text.startswith("/"):
        return target_path == text
    expected_name = text.rsplit("/", 1)[-1].lstrip("#")
    return target_name == expected_name


def _signal_connection_filter_summary(
    signal: str,
    *,
    target: "Locator | str | dict[str, Any] | None" = None,
    method: str | None = None,
    persistent: bool | None = None,
) -> str:
    filters = [f"signal={signal!r}"]
    if target is not None:
        filters.append(f"target={_inner_selector(target)!r}")
    if method is not None:
        filters.append(f"method={method!r}")
    if persistent is not None:
        filters.append(f"persistent={persistent!r}")
    return ", ".join(filters)


def _project_autoload_entry(
    state: dict[str, Any],
    name: str,
    *,
    path: str | None = None,
    singleton: bool | None = None,
) -> dict[str, Any] | None:
    for entry in state.get("autoloads", []):
        if not isinstance(entry, dict) or entry.get("name") != name:
            continue
        if path is not None and entry.get("path") != path:
            continue
        if singleton is not None and bool(entry.get("singleton", False)) != singleton:
            continue
        return entry
    return None


def _project_autoload_filter_summary(*, path: str | None = None, singleton: bool | None = None) -> str:
    filters = []
    if path is not None:
        filters.append(f"path={path!r}")
    if singleton is not None:
        filters.append(f"singleton={singleton!r}")
    return "" if not filters else " with " + ", ".join(filters)


def _project_export_preset_entry(
    state: dict[str, Any],
    name: str,
    *,
    platform: str | None = None,
    export_path: str | None = None,
    runnable: bool | None = None,
    options: dict[str, Any] | None = None,
    fields: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    for entry in state.get("presets", []):
        if not isinstance(entry, dict) or entry.get("name") != name:
            continue
        if platform is not None and entry.get("platform") != platform:
            continue
        if export_path is not None and entry.get("export_path") != export_path:
            continue
        if runnable is not None and bool(entry.get("runnable", False)) != runnable:
            continue
        if options is not None:
            entry_options = entry.get("options", {})
            if not isinstance(entry_options, dict) or not _dict_contains(entry_options, options):
                continue
        if fields is not None and not _dict_contains(entry, fields):
            continue
        return entry
    return None


def _project_export_preset_filter_summary(
    *,
    platform: str | None = None,
    export_path: str | None = None,
    runnable: bool | None = None,
    options: dict[str, Any] | None = None,
    fields: dict[str, Any] | None = None,
) -> str:
    filters = []
    if platform is not None:
        filters.append(f"platform={platform!r}")
    if export_path is not None:
        filters.append(f"export_path={export_path!r}")
    if runnable is not None:
        filters.append(f"runnable={runnable!r}")
    if options is not None:
        filters.append(f"options={options!r}")
    if fields is not None:
        filters.append(f"fields={fields!r}")
    return "" if not filters else " with " + ", ".join(filters)


def _input_action_matches(
    state: dict[str, Any],
    *,
    event_count: int | None = None,
    min_event_count: int | None = None,
    deadzone: float | None = None,
) -> bool:
    if not bool(state.get("exists")):
        return False
    if event_count is not None and int(state.get("event_count", 0)) != event_count:
        return False
    if min_event_count is not None and int(state.get("event_count", 0)) < min_event_count:
        return False
    if deadzone is not None and abs(float(state.get("deadzone", 0.0)) - deadzone) > 0.000001:
        return False
    return True


def _input_action_filter_summary(
    *,
    event_count: int | None = None,
    min_event_count: int | None = None,
    deadzone: float | None = None,
) -> str:
    filters = []
    if event_count is not None:
        filters.append(f"event_count={event_count!r}")
    if min_event_count is not None:
        filters.append(f"min_event_count={min_event_count!r}")
    if deadzone is not None:
        filters.append(f"deadzone={deadzone!r}")
    return "" if not filters else " with " + ", ".join(filters)


def _input_action_state_matches(
    state: dict[str, Any],
    *,
    pressed: bool | None = None,
    strength: float | None = None,
    min_strength: float | None = None,
) -> bool:
    if not bool(state.get("exists")):
        return False
    if pressed is not None and bool(state.get("pressed")) != pressed:
        return False
    actual_strength = float(state.get("strength", 0.0))
    if strength is not None and abs(actual_strength - float(strength)) > 0.000001:
        return False
    if min_strength is not None and actual_strength < float(min_strength):
        return False
    return True


def _input_action_state_filter_summary(
    *,
    pressed: bool | None = None,
    strength: float | None = None,
    min_strength: float | None = None,
) -> str:
    filters = []
    if pressed is not None:
        filters.append(f"pressed={pressed!r}")
    if strength is not None:
        filters.append(f"strength={strength!r}")
    if min_strength is not None:
        filters.append(f"min_strength={min_strength!r}")
    return "" if not filters else " with " + ", ".join(filters)


def _input_action_event_entry(
    state: dict[str, Any],
    *,
    event_type: str | None = None,
    key: str | int | None = None,
    button: str | int | None = None,
    axis: str | int | None = None,
    value: float | None = None,
    device: int | None = None,
    modifiers: dict[str, Any] | list[str] | tuple[str, ...] | str | None = None,
    fields: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not bool(state.get("exists")):
        return None
    for event in state.get("events", []):
        if isinstance(event, dict) and _input_action_event_matches(
            event,
            event_type=event_type,
            key=key,
            button=button,
            axis=axis,
            value=value,
            device=device,
            modifiers=modifiers,
            fields=fields,
        ):
            return event
    return None


def _input_action_event_matches(
    event: dict[str, Any],
    *,
    event_type: str | None = None,
    key: str | int | None = None,
    button: str | int | None = None,
    axis: str | int | None = None,
    value: float | None = None,
    device: int | None = None,
    modifiers: dict[str, Any] | list[str] | tuple[str, ...] | str | None = None,
    fields: dict[str, Any] | None = None,
) -> bool:
    if event_type is not None and not _input_event_type_matches(event.get("type"), event_type):
        return False
    if key is not None and not any(
        _input_event_value_matches(event.get(field), key) for field in ("key", "keycode", "physical_keycode", "unicode")
    ):
        return False
    if button is not None and not _input_button_matches(event, button):
        return False
    if axis is not None and not any(
        _input_event_value_matches(event.get(field), axis, aliases=_JOY_AXIS_ALIASES) for field in ("axis", "axis_index")
    ):
        return False
    if value is not None and not _input_float_matches(event.get("value", event.get("axis_value")), value):
        return False
    if device is not None and not _input_event_value_matches(event.get("device"), device):
        return False
    if modifiers is not None:
        actual_modifiers = _input_event_modifiers(event)
        for modifier, expected_value in _normalize_input_modifiers(modifiers).items():
            if actual_modifiers.get(modifier) != expected_value:
                return False
    if fields is not None and not _dict_contains(event, fields):
        return False
    return True


def _input_action_event_filter_summary(
    *,
    event_type: str | None = None,
    key: str | int | None = None,
    button: str | int | None = None,
    axis: str | int | None = None,
    value: float | None = None,
    device: int | None = None,
    modifiers: dict[str, Any] | list[str] | tuple[str, ...] | str | None = None,
    fields: dict[str, Any] | None = None,
) -> str:
    filters = []
    if event_type is not None:
        filters.append(f"event_type={event_type!r}")
    if key is not None:
        filters.append(f"key={key!r}")
    if button is not None:
        filters.append(f"button={button!r}")
    if axis is not None:
        filters.append(f"axis={axis!r}")
    if value is not None:
        filters.append(f"value={value!r}")
    if device is not None:
        filters.append(f"device={device!r}")
    if modifiers is not None:
        filters.append(f"modifiers={modifiers!r}")
    if fields is not None:
        filters.append(f"fields={fields!r}")
    return "" if not filters else " with " + ", ".join(filters)


def _input_button_matches(event: dict[str, Any], expected: str | int) -> bool:
    event_type = event.get("type")
    if _input_event_type_matches(event_type, "joypad_button"):
        aliases = _JOY_BUTTON_ALIASES
    elif _input_event_type_matches(event_type, "mouse_button"):
        aliases = _MOUSE_BUTTON_ALIASES
    else:
        aliases = {**_MOUSE_BUTTON_ALIASES, **_JOY_BUTTON_ALIASES}
    return any(
        _input_event_value_matches(event.get(field), expected, aliases=aliases) for field in ("button", "button_index")
    )


def _input_event_type_matches(actual: Any, expected: str) -> bool:
    if actual is None:
        return False
    actual_normalized = _normalize_input_name(actual)
    expected_normalized = _normalize_input_name(expected)
    for aliases in _INPUT_EVENT_TYPE_ALIASES.values():
        if expected_normalized in aliases:
            return actual_normalized in aliases
    return actual_normalized == expected_normalized


def _input_event_value_matches(
    actual: Any,
    expected: Any,
    *,
    aliases: dict[str, int] | None = None,
) -> bool:
    if actual is None:
        return False
    if actual == expected:
        return True
    if aliases is not None:
        actual_alias = aliases.get(_normalize_input_name(actual))
        expected_alias = aliases.get(_normalize_input_name(expected))
        if actual_alias is not None and expected_alias is not None:
            return actual_alias == expected_alias
        expected_int = _input_int(expected)
        if actual_alias is not None and expected_int is not None:
            return actual_alias == expected_int
        actual_int = _input_int(actual)
        if expected_alias is not None and actual_int is not None:
            return actual_int == expected_alias
    actual_int = _input_int(actual)
    expected_int = _input_int(expected)
    if actual_int is not None and expected_int is not None:
        return actual_int == expected_int
    return str(actual).strip().lower() == str(expected).strip().lower()


def _input_float_matches(actual: Any, expected: float) -> bool:
    try:
        return abs(float(actual) - float(expected)) <= 0.000001
    except (TypeError, ValueError):
        return False


def _input_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"[+-]?\d+", text):
            return int(text)
    return None


def _normalize_input_modifiers(
    value: dict[str, Any] | list[str] | tuple[str, ...] | str,
) -> dict[str, bool]:
    modifiers: dict[str, bool] = {}
    if isinstance(value, dict):
        for key, enabled in value.items():
            modifiers[_normalize_modifier_name(key)] = bool(enabled)
    elif isinstance(value, str):
        modifiers[_normalize_modifier_name(value)] = True
    else:
        for item in value:
            modifiers[_normalize_modifier_name(item)] = True
    return modifiers


def _input_event_modifiers(event: dict[str, Any]) -> dict[str, bool]:
    modifiers: dict[str, bool] = {}
    raw_modifiers = event.get("modifiers")
    if isinstance(raw_modifiers, dict):
        modifiers.update(_normalize_input_modifiers(raw_modifiers))
    elif isinstance(raw_modifiers, (list, tuple, str)):
        modifiers.update(_normalize_input_modifiers(raw_modifiers))
    for key in ("shift", "ctrl", "control", "alt", "meta", "command_or_control"):
        if key in event:
            modifiers[_normalize_modifier_name(key)] = bool(event[key])
    return modifiers


def _normalize_modifier_name(value: Any) -> str:
    normalized = _normalize_input_name(value)
    return _MODIFIER_ALIASES.get(normalized, normalized)


def _normalize_input_name(value: Any) -> str:
    return str(value).strip().lower().replace("-", "").replace("_", "").replace(" ", "")


def _physics2d_collision_entry(
    collisions: Any,
    *,
    name: str | None = None,
    path: str | None = None,
    class_name: str | None = None,
    groups: list[str] | tuple[str, ...] | set[str] | None = None,
    metadata: dict[str, Any] | None = None,
    fields: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(collisions, list):
        return None
    for collision in collisions:
        if isinstance(collision, dict) and _physics2d_collision_matches(
            collision,
            name=name,
            path=path,
            class_name=class_name,
            groups=groups,
            metadata=metadata,
            fields=fields,
        ):
            return collision
    return None


def _physics2d_collision_matches(
    collision: Any,
    *,
    name: str | None = None,
    path: str | None = None,
    class_name: str | None = None,
    groups: list[str] | tuple[str, ...] | set[str] | None = None,
    metadata: dict[str, Any] | None = None,
    fields: dict[str, Any] | None = None,
) -> bool:
    if not isinstance(collision, dict):
        return False
    if name is not None and collision.get("name") != name:
        return False
    if path is not None and collision.get("path") != path:
        return False
    if class_name is not None and collision.get("class") != class_name:
        return False
    if groups is not None:
        actual_groups = {str(group) for group in collision.get("groups", [])}
        if not all(str(group) in actual_groups for group in groups):
            return False
    if metadata is not None:
        actual_metadata = collision.get("metadata", {})
        if not isinstance(actual_metadata, dict) or not _dict_contains(actual_metadata, metadata):
            return False
    if fields is not None and not _dict_contains(collision, fields):
        return False
    return True


def _physics2d_filter_summary(
    *,
    name: str | None = None,
    path: str | None = None,
    class_name: str | None = None,
    groups: list[str] | tuple[str, ...] | set[str] | None = None,
    metadata: dict[str, Any] | None = None,
    fields: dict[str, Any] | None = None,
) -> str:
    filters = []
    if name is not None:
        filters.append(f"name={name!r}")
    if path is not None:
        filters.append(f"path={path!r}")
    if class_name is not None:
        filters.append(f"class_name={class_name!r}")
    if groups is not None:
        filters.append(f"groups={list(groups)!r}")
    if metadata is not None:
        filters.append(f"metadata={metadata!r}")
    if fields is not None:
        filters.append(f"fields={fields!r}")
    return "" if not filters else " with " + ", ".join(filters)


class InspectorExpect:
    def __init__(self, inspector: Inspector):
        self.inspector = inspector

    def to_have_property(
        self,
        property_name: str,
        expected: Any = _UNSET,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        property_expect = InspectorPropertyExpect(self.inspector.property(property_name))
        property_info = property_expect.to_exist(timeout=timeout, interval=interval)
        if expected is not _UNSET:
            property_expect.to_have_value(expected, timeout=timeout, interval=interval)
        return property_info

    def to_have_properties(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if not expected:
            raise ValueError("expected must not be empty")
        deadline = time.monotonic() + timeout
        last_values: dict[str, Any] = {}
        while True:
            last_values = self.inspector.values(properties=list(expected))
            if _dict_contains(last_values, expected):
                return last_values
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected inspector properties to include {expected!r}; got {last_values!r}"
                )
            time.sleep(interval)

    def not_to_have_properties(
        self,
        unexpected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if not unexpected:
            raise ValueError("unexpected must not be empty")
        deadline = time.monotonic() + timeout
        last_values: dict[str, Any] = {}
        while True:
            last_values = self.inspector.values(properties=list(unexpected))
            if not _dict_contains(last_values, unexpected):
                return last_values
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected inspector properties not to include {unexpected!r}; got {last_values!r}"
                )
            time.sleep(interval)


class InspectorPropertyExpect:
    def __init__(self, property: InspectorProperty):
        self.property = property

    def to_exist(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            result = self.property.get()
            last = dict(result.get("property", {}))
            if last.get("exists", False):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected inspector property {self.property.property_name!r} to exist; last={last!r}")
            time.sleep(interval)

    def to_have_value(self, expected: Any, *, timeout: float = 5.0, interval: float = 0.05) -> None:
        deadline = time.monotonic() + timeout
        last_value: Any = None
        while True:
            last_value = self.property.value()
            if last_value == expected:
                return
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected inspector property {self.property.property_name!r} to be {expected!r}, got {last_value!r}"
                )
            time.sleep(interval)


class ScriptExpect:
    def __init__(self, client: GodotClient, path: str):
        self.client = client
        self.path = path

    def to_exist(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.client.editor_filesystem_describe(self.path)
            if last.get("exists") and last.get("is_file"):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected script {self.path!r} to exist; last={last!r}")
            time.sleep(interval)

    def to_have_class_name(self, class_name: str, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_class_name = ""
        while True:
            last = self.client.script_file_describe(self.path)
            last_class_name = str(last.get("class_name", ""))
            if last_class_name == class_name:
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected script {self.path!r} class_name {class_name!r}, got {last_class_name!r}"
                )
            time.sleep(interval)

    def to_extend(self, base_class: str, *, timeout: float = 5.0, interval: float = 0.05) -> None:
        deadline = time.monotonic() + timeout
        last_extends = ""
        while True:
            description = self.client.script_file_describe(self.path)
            last_extends = str(description.get("symbols", {}).get("extends", ""))
            if last_extends == base_class:
                return
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected script {self.path!r} to extend {base_class!r}, got {last_extends!r}")
            time.sleep(interval)

    def to_define_function(self, name: str, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_names: list[str] = []
        while True:
            description = self.client.script_file_describe(self.path)
            functions = _script_function_entries(description)
            last_names = [str(function.get("name", "")) for function in functions]
            for function in functions:
                if function.get("name") == name:
                    return function
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected script {self.path!r} to define function {name!r}; got {last_names!r}")
            time.sleep(interval)

    def to_define_signal(self, name: str, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_names: list[str] = []
        while True:
            description = self.client.script_file_describe(self.path)
            signals = _script_symbol_entries(description, "signals")
            last_names = [str(signal.get("name", "")) for signal in signals]
            for signal in signals:
                if signal.get("name") == name:
                    return signal
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected script {self.path!r} to define signal {name!r}; got {last_names!r}")
            time.sleep(interval)

    def to_define_variable(self, name: str, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_names: list[str] = []
        while True:
            description = self.client.script_file_describe(self.path)
            variables = _script_symbol_entries(description, "variables")
            last_names = [str(variable.get("name", "")) for variable in variables]
            for variable in variables:
                if variable.get("name") == name:
                    return variable
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected script {self.path!r} to define variable {name!r}; got {last_names!r}")
            time.sleep(interval)

    def to_contain_source(self, text: str, *, timeout: float = 5.0, interval: float = 0.05) -> None:
        deadline = time.monotonic() + timeout
        last_source = ""
        while True:
            description = self.client.script_file_describe(self.path, include_source=True)
            last_source = str(description.get("source", ""))
            if text in last_source:
                return
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected script {self.path!r} source to contain {text!r}")
            time.sleep(interval)


class ScriptClassExpect:
    def __init__(self, client: GodotClient, class_name: str):
        self.client = client
        self.class_name = class_name

    def to_be_listed(
        self,
        *,
        path: str = "res://",
        base_class: str = "",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_classes(
            lambda state: _script_class_list_entry(state, self.class_name) is not None,
            lambda state, error: (
                f"Expected script class {self.class_name!r} to be listed"
                f"{_script_class_filter_summary(path=path, base_class=base_class)}; "
                f"classes={state.get('classes', [])!r} error={error!r}"
            ),
            path=path,
            base_class=base_class,
            timeout=timeout,
            interval=interval,
            transform=lambda state: _script_class_list_entry(state, self.class_name) or {},
        )

    def to_extend(
        self,
        base_class: str,
        *,
        path: str = "res://",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        def match(state: dict[str, Any]) -> dict[str, Any] | None:
            entry = _script_class_list_entry(state, self.class_name)
            if entry is None:
                return None
            if entry.get("extends") == base_class or entry.get("parent") == base_class:
                return entry
            return None

        return self._wait_for_classes(
            lambda state: match(state) is not None,
            lambda state, error: (
                f"Expected script class {self.class_name!r} to extend {base_class!r}; "
                f"classes={state.get('classes', [])!r} error={error!r}"
            ),
            path=path,
            timeout=timeout,
            interval=interval,
            transform=lambda state: match(state) or {},
        )

    def to_be_node(
        self,
        *,
        path: str = "res://",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_classes(
            lambda state: bool((_script_class_list_entry(state, self.class_name) or {}).get("is_node")),
            lambda state, error: (
                f"Expected script class {self.class_name!r} to be a Node script class; "
                f"classes={state.get('classes', [])!r} error={error!r}"
            ),
            path=path,
            base_class="Node",
            timeout=timeout,
            interval=interval,
            transform=lambda state: _script_class_list_entry(state, self.class_name) or {},
        )

    def to_be_resource(
        self,
        *,
        path: str = "res://",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_classes(
            lambda state: bool((_script_class_list_entry(state, self.class_name) or {}).get("is_resource")),
            lambda state, error: (
                f"Expected script class {self.class_name!r} to be a Resource script class; "
                f"classes={state.get('classes', [])!r} error={error!r}"
            ),
            path=path,
            base_class="Resource",
            timeout=timeout,
            interval=interval,
            transform=lambda state: _script_class_list_entry(state, self.class_name) or {},
        )

    def to_have_function(
        self,
        function_name: str,
        *,
        path: str = "res://",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        def match(state: dict[str, Any]) -> dict[str, Any] | None:
            entry = _script_class_list_entry(state, self.class_name)
            if entry is None:
                return None
            return _script_class_function(entry, function_name)

        return self._wait_for_classes(
            lambda state: match(state) is not None,
            lambda state, error: (
                f"Expected script class {self.class_name!r} function {function_name!r}; "
                f"classes={state.get('classes', [])!r} error={error!r}"
            ),
            path=path,
            timeout=timeout,
            interval=interval,
            transform=lambda state: match(state) or {},
        )

    def _wait_for_classes(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any], BaseException | None], str],
        *,
        path: str,
        base_class: str = "",
        timeout: float,
        interval: float,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.client.script_classes(
                    path=path,
                    class_name=self.class_name,
                    base_class=base_class,
                    max_results=500,
                )
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if predicate(last):
                    return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last, last_error))
            time.sleep(interval)


class FilesystemExpect:
    def __init__(self, client: GodotClient, path: str = "res://"):
        self.client = client
        self.path = path

    def to_exist(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for_fs_state(
            lambda state: bool(state.get("exists")),
            lambda state: f"Expected filesystem path {self.path!r} to exist; last={state!r}",
            timeout=timeout,
            interval=interval,
        )

    def not_to_exist(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for_fs_state(
            lambda state: not bool(state.get("exists")),
            lambda state: f"Expected filesystem path {self.path!r} not to exist; last={state!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_be_file(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for_fs_state(
            lambda state: _fs_path_matches(state, state="exists", path_type="file"),
            lambda state: f"Expected filesystem path {self.path!r} to be a file; last={state!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_be_directory(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for_fs_state(
            lambda state: _fs_path_matches(state, state="exists", path_type="directory"),
            lambda state: f"Expected filesystem path {self.path!r} to be a directory; last={state!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_be_indexed(
        self,
        *,
        resource_type: str | None = None,
        kind: str | None = None,
        is_file: bool | None = None,
        is_directory: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.wait_for_editor_filesystem_entry(
            self.path,
            resource_type=resource_type,
            kind=kind,
            is_file=is_file,
            is_directory=is_directory,
            timeout=timeout,
            interval=interval,
        )

    def not_to_be_indexed(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self.client.wait_for_editor_filesystem_missing(
            self.path,
            timeout=timeout,
            interval=interval,
        )

    def to_have_text(self, text: str, *, timeout: float = 5.0, interval: float = 0.05) -> str:
        deadline = time.monotonic() + timeout
        last_text = ""
        last_state: dict[str, Any] = {}
        while True:
            last_state = self.client.fs_exists(self.path)
            if _fs_path_matches(last_state, state="exists", path_type="file"):
                last_text = self.client.fs_read_text(self.path)
                if text in last_text:
                    return last_text
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"Expected filesystem file {self.path!r} to contain {text!r}; "
                    f"last_state={last_state!r} last_text={last_text!r}"
                )
            time.sleep(interval)

    def not_to_have_text(self, text: str, *, timeout: float = 5.0, interval: float = 0.05) -> str:
        deadline = time.monotonic() + timeout
        last_text = ""
        last_state: dict[str, Any] = {}
        while True:
            last_state = self.client.fs_exists(self.path)
            if not _fs_path_matches(last_state, state="exists", path_type="file"):
                return ""
            last_text = self.client.fs_read_text(self.path)
            if text not in last_text:
                return last_text
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected filesystem file {self.path!r} not to contain {text!r}")
            time.sleep(interval)

    def _wait_for_fs_state(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any]], str],
        *,
        timeout: float,
        interval: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.client.fs_exists(self.path)
            if predicate(last):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last))
            time.sleep(interval)

    def to_have_resource_type(
        self,
        resource_type: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.to_be_indexed(resource_type=resource_type, timeout=timeout, interval=interval)

    def to_have_indexed_count(
        self,
        count: int,
        *,
        name: str = "",
        name_contains: str = "",
        extension: str = "",
        resource_type: str = "",
        recursive: bool = True,
        include_dirs: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if count < 0:
            raise ValueError("count must be >= 0")
        return self.client.wait_for_editor_filesystem_find(
            self.path,
            recursive=recursive,
            include_dirs=include_dirs,
            name=name,
            name_contains=name_contains,
            extension=extension,
            resource_type=resource_type,
            min_count=count,
            max_count=count,
            max_results=500,
            timeout=timeout,
            interval=interval,
        )

    def to_contain(
        self,
        name: str = "",
        *,
        extension: str = "",
        resource_type: str = "",
        recursive: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        result = self.client.wait_for_editor_filesystem_find(
            self.path,
            recursive=recursive,
            name=name,
            extension=extension,
            resource_type=resource_type,
            min_count=1,
            max_results=500,
            timeout=timeout,
            interval=interval,
        )
        return list(result.get("entries", []))[0]

    def not_to_contain(
        self,
        name: str = "",
        *,
        name_contains: str = "",
        extension: str = "",
        resource_type: str = "",
        recursive: bool = True,
        include_dirs: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.wait_for_editor_filesystem_find(
            self.path,
            recursive=recursive,
            include_dirs=include_dirs,
            name=name,
            name_contains=name_contains,
            extension=extension,
            resource_type=resource_type,
            min_count=0,
            max_count=0,
            max_results=500,
            timeout=timeout,
            interval=interval,
        )


def _resource_state_exists(state: dict[str, Any]) -> bool:
    return bool(state.get("exists", True))


_RESOURCE_IMPORT_EXTENSIONS = {
    ".apng",
    ".bmp",
    ".exr",
    ".fbx",
    ".glb",
    ".gltf",
    ".hdr",
    ".jpg",
    ".jpeg",
    ".mp3",
    ".obj",
    ".ogg",
    ".otf",
    ".png",
    ".svg",
    ".tga",
    ".ttf",
    ".wav",
    ".webp",
    ".woff",
    ".woff2",
}


def _resource_path_uses_import_metadata(path: Any) -> bool:
    return Path(str(path)).suffix.lower() in _RESOURCE_IMPORT_EXTENSIONS


def _resource_properties(state: dict[str, Any]) -> dict[str, Any]:
    properties = state.get("properties", {})
    return properties if isinstance(properties, dict) else {}


def _resource_file_properties(state: dict[str, Any]) -> dict[str, Any]:
    properties = state.get("properties", {})
    if isinstance(properties, dict):
        return properties
    root = state.get("root", {})
    if isinstance(root, dict) and isinstance(root.get("properties"), dict):
        return root["properties"]
    return {}


def _resource_file_ext_resource_matches(
    entry: dict[str, Any],
    *,
    path: str | None = None,
    resource_type: str | None = None,
    uid: str | None = None,
    resource_id: str | None = None,
    exists: bool | None = None,
) -> bool:
    if path is not None and entry.get("path") != path:
        return False
    if resource_type is not None and entry.get("type") != resource_type:
        return False
    if uid is not None and entry.get("uid") != uid:
        return False
    if resource_id is not None and entry.get("id") != resource_id:
        return False
    if exists is not None and bool(entry.get("exists", False)) != exists:
        return False
    return True


def _resource_file_ext_resource_filter_summary(
    *,
    path: str | None = None,
    resource_type: str | None = None,
    uid: str | None = None,
    resource_id: str | None = None,
    exists: bool | None = None,
) -> str:
    filters = []
    if path is not None:
        filters.append(f"path={path!r}")
    if resource_type is not None:
        filters.append(f"resource_type={resource_type!r}")
    if uid is not None:
        filters.append(f"uid={uid!r}")
    if resource_id is not None:
        filters.append(f"resource_id={resource_id!r}")
    if exists is not None:
        filters.append(f"exists={exists!r}")
    return ", ".join(filters) if filters else "any external resource"


def _project_resource_entry(state: dict[str, Any], path: str) -> dict[str, Any] | None:
    for entry in state.get("resources", []):
        if isinstance(entry, dict) and entry.get("path") == path:
            return entry
    return None


def _project_resource_matches(
    entry: dict[str, Any],
    *,
    class_name: str | None = None,
    resource_name: str | None = None,
) -> bool:
    if class_name is not None and entry.get("class") != class_name:
        return False
    if resource_name is not None and entry.get("resource_name") != resource_name:
        return False
    return True


def _project_resource_filter_summary(
    *,
    class_name: str | None = None,
    resource_name: str | None = None,
) -> str:
    filters = []
    if class_name is not None:
        filters.append(f"class_name={class_name!r}")
    if resource_name is not None:
        filters.append(f"resource_name={resource_name!r}")
    return "" if not filters else " with " + ", ".join(filters)


def _resource_readback_expected_properties(properties: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _resource_readback_expected_value(value) for key, value in properties.items()}


def _resource_readback_expected_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_resource_readback_expected_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    type_name = str(value.get("$type", ""))
    if type_name in {"ResourceRef", "ExtResource"}:
        expected: dict[str, Any] = {"$type": "Resource", "path": str(value.get("path") or value.get("resource_path") or "")}
        if value.get("class"):
            expected["class"] = value.get("class")
        return expected
    if type_name in {"Resource", "SubResource"}:
        path = str(value.get("path") or value.get("resource_path") or "")
        expected = {"$type": "Resource"}
        if path:
            expected["path"] = path
        expected["class"] = str(value.get("class") or value.get("class_name") or "Resource")
        if "resource_name" in value:
            expected["resource_name"] = value["resource_name"]
        return expected
    return {str(key): _resource_readback_expected_value(item) for key, item in value.items()}


def _resource_class_property(
    schema: dict[str, Any],
    property_name: str,
    *,
    type_name: str | None = None,
    storage: bool | None = None,
    editor_visible: bool | None = None,
) -> dict[str, Any] | None:
    for entry in schema.get("properties", []):
        if not isinstance(entry, dict) or entry.get("name") != property_name:
            continue
        if type_name is not None and entry.get("type_name") != type_name:
            continue
        if storage is not None and bool(entry.get("storage")) != storage:
            continue
        if editor_visible is not None and bool(entry.get("editor_visible")) != editor_visible:
            continue
        return entry
    return None


def _resource_class_list_entry(state: dict[str, Any], class_name: str) -> dict[str, Any] | None:
    for entry in state.get("classes", []):
        if isinstance(entry, dict) and entry.get("class") == class_name:
            return entry
    return None


def _node_class_list_entry(state: dict[str, Any], class_name: str) -> dict[str, Any] | None:
    for entry in state.get("classes", []):
        if isinstance(entry, dict) and entry.get("class") == class_name:
            return entry
    return None


def _node_class_property(
    schema: dict[str, Any],
    property_name: str,
    *,
    type_name: str | None = None,
    storage: bool | None = None,
    editor_visible: bool | None = None,
) -> dict[str, Any] | None:
    for entry in schema.get("properties", []):
        if not isinstance(entry, dict) or entry.get("name") != property_name:
            continue
        if type_name is not None and entry.get("type_name") != type_name:
            continue
        if storage is not None and bool(entry.get("storage")) != storage:
            continue
        if editor_visible is not None and bool(entry.get("editor_visible")) != editor_visible:
            continue
        return entry
    return None


def _node_class_method(schema: dict[str, Any], method_name: str) -> dict[str, Any] | None:
    for entry in schema.get("methods", []):
        if isinstance(entry, dict) and entry.get("name") == method_name:
            return entry
    return None


def _node_class_signal(schema: dict[str, Any], signal_name: str) -> dict[str, Any] | None:
    for entry in schema.get("signals", []):
        if isinstance(entry, dict) and entry.get("name") == signal_name:
            return entry
    return None


def _script_class_list_entry(state: dict[str, Any], class_name: str) -> dict[str, Any] | None:
    for entry in state.get("classes", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("class_name") == class_name or entry.get("class") == class_name:
            return entry
    return None


def _script_class_function(entry: dict[str, Any], function_name: str) -> dict[str, Any] | None:
    for function in entry.get("functions", []):
        if isinstance(function, dict) and function.get("name") == function_name:
            return function
    return None


def _script_class_filter_summary(*, path: str = "res://", base_class: str = "") -> str:
    filters: list[str] = []
    if path != "res://":
        filters.append(f"path={path!r}")
    if base_class:
        filters.append(f"base_class={base_class!r}")
    return "" if not filters else " with " + ", ".join(filters)


def _project_scene_entry(state: dict[str, Any], path: str) -> dict[str, Any] | None:
    for entry in state.get("scenes", []):
        if isinstance(entry, dict) and entry.get("path") == path:
            return entry
    return None


def _project_scene_root_matches(
    entry: dict[str, Any],
    *,
    root_name: str | None = None,
    root_class: str | None = None,
) -> bool:
    if root_name is not None and entry.get("root_name") != root_name:
        return False
    if root_class is not None and entry.get("root_class") != root_class:
        return False
    return True


def _project_scene_filter_summary(
    *,
    root_name: str | None = None,
    root_class: str | None = None,
) -> str:
    filters: list[str] = []
    if root_name is not None:
        filters.append(f"root_name={root_name!r}")
    if root_class is not None:
        filters.append(f"root_class={root_class!r}")
    return "" if not filters else " with " + ", ".join(filters)


def _project_scene_described_node(
    state: dict[str, Any],
    *,
    name: str | None = None,
    class_name: str | None = None,
    path: str | None = None,
    script: str | None = None,
    instance_path: str | None = None,
    properties: dict[str, Any] | None = None,
    groups: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any] | None:
    expected_groups = {str(group) for group in (groups or [])}
    for entry in state.get("nodes", []):
        if not isinstance(entry, dict):
            continue
        if name is not None and entry.get("name") != name:
            continue
        if class_name is not None and entry.get("class") != class_name and entry.get("type") != class_name:
            continue
        if path is not None and entry.get("path") != path and entry.get("scene_path") != path.lstrip("/"):
            continue
        if script is not None and entry.get("script") != script:
            continue
        if instance_path is not None and entry.get("instance_path") != instance_path:
            continue
        if expected_groups and not expected_groups.issubset({str(group) for group in entry.get("groups", [])}):
            continue
        entry_properties = entry.get("properties", {})
        if properties is not None and (
            not isinstance(entry_properties, dict) or not _dict_contains(entry_properties, properties)
        ):
            continue
        return entry
    return None


def _project_scene_connection(
    state: dict[str, Any],
    *,
    signal: str = "",
    from_node: str | None = None,
    to: str | None = None,
    method: str | None = None,
) -> dict[str, Any] | None:
    for entry in state.get("connections", []):
        if not isinstance(entry, dict):
            continue
        if signal and entry.get("signal") != signal:
            continue
        if from_node is not None and entry.get("from") != from_node:
            continue
        if to is not None and entry.get("to") != to:
            continue
        if method is not None and entry.get("method") != method:
            continue
        return entry
    return None


def _project_scene_node_filter_summary(
    *,
    name: str | None = None,
    class_name: str | None = None,
    path: str | None = None,
    script: str | None = None,
    instance_path: str | None = None,
    properties: dict[str, Any] | None = None,
    groups: list[str] | tuple[str, ...] | set[str] | None = None,
) -> str:
    filters: list[str] = []
    if name is not None:
        filters.append(f"name={name!r}")
    if class_name is not None:
        filters.append(f"class_name={class_name!r}")
    if path is not None:
        filters.append(f"path={path!r}")
    if script is not None:
        filters.append(f"script={script!r}")
    if instance_path is not None:
        filters.append(f"instance_path={instance_path!r}")
    if properties is not None:
        filters.append(f"properties={properties!r}")
    if groups is not None:
        filters.append(f"groups={list(groups)!r}")
    return "" if not filters else " with " + ", ".join(filters)


def _project_scene_connection_filter_summary(
    *,
    signal: str = "",
    from_node: str | None = None,
    to: str | None = None,
    method: str | None = None,
) -> str:
    filters: list[str] = []
    if signal:
        filters.append(f"signal={signal!r}")
    if from_node is not None:
        filters.append(f"from_node={from_node!r}")
    if to is not None:
        filters.append(f"to={to!r}")
    if method is not None:
        filters.append(f"method={method!r}")
    return "" if not filters else " with " + ", ".join(filters)


def _resource_class_property_filter_summary(
    *,
    type_name: str | None = None,
    storage: bool | None = None,
    editor_visible: bool | None = None,
) -> str:
    filters: list[str] = []
    if type_name is not None:
        filters.append(f" type_name={type_name!r}")
    if storage is not None:
        filters.append(f" storage={storage!r}")
    if editor_visible is not None:
        filters.append(f" editor_visible={editor_visible!r}")
    return "".join(filters)


def _resource_dependency_matches(
    dependency: dict[str, Any],
    *,
    path: str | None = None,
    uid: str | None = None,
    dependency_type: str | None = None,
    resource_type: str | None = None,
    exists: bool | None = None,
) -> bool:
    if path is not None and dependency.get("path") != path:
        return False
    if uid is not None and dependency.get("uid") != uid:
        return False
    if dependency_type is not None and dependency.get("type") != dependency_type:
        return False
    if resource_type is not None and dependency.get("resource_type") != resource_type:
        return False
    if exists is not None and bool(dependency.get("exists", False)) != exists:
        return False
    return True


def _resource_reference_entry(state: dict[str, Any], path: str) -> dict[str, Any] | None:
    for entry in state.get("references", []):
        if isinstance(entry, dict) and entry.get("path") == path:
            return entry
    return None


def _resource_dependency_filter_summary(
    *,
    path: str | None = None,
    uid: str | None = None,
    dependency_type: str | None = None,
    resource_type: str | None = None,
    exists: bool | None = None,
) -> str:
    filters = []
    if path is not None:
        filters.append(f"path={path!r}")
    if uid is not None:
        filters.append(f"uid={uid!r}")
    if dependency_type is not None:
        filters.append(f"dependency_type={dependency_type!r}")
    if resource_type is not None:
        filters.append(f"resource_type={resource_type!r}")
    if exists is not None:
        filters.append(f"exists={exists!r}")
    return ", ".join(filters) if filters else "any dependency"


def _resource_import_matches(
    state: dict[str, Any],
    *,
    importer: str | None = None,
    resource_type: str | None = None,
    generated_files_ready: bool | None = None,
    require_resource: bool = True,
) -> bool:
    if not bool(state.get("exists")):
        return False
    if not bool(state.get("imported")):
        return False
    if _resource_import_error_count(state) > 0:
        return False
    if require_resource and not bool(state.get("resource_exists")):
        return False
    if importer is not None and state.get("importer") != importer:
        return False
    if resource_type is not None and state.get("resource_type") != resource_type and state.get("type") != resource_type:
        return False
    if generated_files_ready is not None and bool(state.get("generated_files_ready")) != generated_files_ready:
        return False
    return True


def _resource_import_wait_matches(
    state: dict[str, Any],
    *,
    importer: str | None = None,
    resource_type: str | None = None,
    generated_files_ready: bool | None = None,
    require_resource: bool = True,
) -> bool:
    if not bool(state.get("exists")):
        return False
    if _resource_import_error_count(state) > 0:
        return False
    if require_resource and not bool(state.get("resource_exists")):
        return False
    if importer is not None and state.get("importer") != importer:
        return False
    if resource_type is not None and state.get("resource_type") != resource_type and state.get("type") != resource_type:
        return False
    if generated_files_ready is not None:
        if bool(state.get("generated_files_ready")) != generated_files_ready:
            return False
    else:
        generated_files = list(state.get("generated_files", []))
        if generated_files and not bool(state.get("generated_files_ready")):
            return False
    return True


def _resource_import_error_count(state: dict[str, Any]) -> int:
    try:
        return int(state.get("error_count", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _resource_import_diagnostic_summary(state: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics = state.get("diagnostics", []) if isinstance(state, dict) else []
    if isinstance(diagnostics, list):
        return [item for item in diagnostics if isinstance(item, dict)]
    return []


def _resource_import_list_entry(state: dict[str, Any], path: str) -> dict[str, Any] | None:
    for entry in state.get("imports", []):
        if isinstance(entry, dict) and entry.get("path") == path:
            return entry
    return None


def _resource_import_filter_summary(
    *,
    importer: str | None = None,
    resource_type: str | None = None,
    generated_files_ready: bool | None = None,
    require_resource: bool = True,
) -> str:
    filters = [f"require_resource={require_resource!r}"]
    if importer is not None:
        filters.append(f"importer={importer!r}")
    if resource_type is not None:
        filters.append(f"resource_type={resource_type!r}")
    if generated_files_ready is not None:
        filters.append(f"generated_files_ready={generated_files_ready!r}")
    return ", ".join(filters)


class ResourceExpect:
    def __init__(self, client: GodotClient, path: str):
        self.client = client
        self.path = path

    def to_exist(
        self,
        *,
        type_hint: str = "",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_resource_inspect(
            lambda state: _resource_state_exists(state),
            lambda state, error: f"Expected resource {self.path!r} to exist; last={state!r} error={error!r}",
            type_hint=type_hint,
            timeout=timeout,
            interval=interval,
        )

    def not_to_exist(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for_resource_dependencies(
            lambda state: not bool(state.get("exists")),
            lambda state, error: f"Expected resource {self.path!r} not to exist; last={state!r} error={error!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_be_listed(
        self,
        *,
        class_name: str | None = None,
        resource_name: str | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        def match(state: dict[str, Any]) -> dict[str, Any] | None:
            entry = _project_resource_entry(state, self.path)
            if entry is None or not _project_resource_matches(
                entry,
                class_name=class_name,
                resource_name=resource_name,
            ):
                return None
            return entry

        return self._wait_for_resource_files(
            lambda state: match(state) is not None,
            lambda state, error: (
                f"Expected project resource {self.path!r} to be listed"
                f"{_project_resource_filter_summary(class_name=class_name, resource_name=resource_name)}; "
                f"resources={state.get('resources', [])!r} error={error!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda state: match(state) or {},
        )

    def to_have_class(
        self,
        class_name: str,
        *,
        type_hint: str = "",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_resource_inspect(
            lambda state: _resource_state_exists(state) and state.get("class") == class_name,
            lambda state, error: (
                f"Expected resource {self.path!r} class {class_name!r}; "
                f"got {state.get('class')!r}; last={state!r} error={error!r}"
            ),
            type_hint=type_hint,
            timeout=timeout,
            interval=interval,
        )

    def not_to_have_class(
        self,
        class_name: str,
        *,
        type_hint: str = "",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_resource_inspect(
            lambda state: _resource_state_exists(state) and state.get("class") != class_name,
            lambda state, error: (
                f"Expected resource {self.path!r} class not to be {class_name!r}; "
                f"last={state!r} error={error!r}"
            ),
            type_hint=type_hint,
            timeout=timeout,
            interval=interval,
        )

    def to_have_type(
        self,
        resource_type: str,
        *,
        type_hint: str = "",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.to_have_class(resource_type, type_hint=type_hint, timeout=timeout, interval=interval)

    def to_have_property(
        self,
        property_name: str,
        expected: Any = _UNSET,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        def matches(state: dict[str, Any]) -> bool:
            properties = _resource_properties(state)
            if property_name not in properties:
                return False
            return expected is _UNSET or properties.get(property_name) == expected

        return self._wait_for_resource_inspect(
            matches,
            lambda state, error: (
                f"Expected resource {self.path!r} property {property_name!r}"
                f"{'' if expected is _UNSET else f' to be {expected!r}'}; "
                f"properties={_resource_properties(state)!r} error={error!r}"
            ),
            include_properties=True,
            properties=[property_name],
            timeout=timeout,
            interval=interval,
        )

    def to_have_properties(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_resource_inspect(
            lambda state: _dict_contains(_resource_properties(state), expected),
            lambda state, error: (
                f"Expected resource {self.path!r} properties to include {expected!r}; "
                f"properties={_resource_properties(state)!r} error={error!r}"
            ),
            include_properties=True,
            properties=list(expected),
            timeout=timeout,
            interval=interval,
        )

    def to_have_file_property(
        self,
        property_name: str,
        expected: Any = _UNSET,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        def matches(state: dict[str, Any]) -> bool:
            properties = _resource_file_properties(state)
            if property_name not in properties:
                return False
            return expected is _UNSET or properties.get(property_name) == expected

        return self._wait_for_resource_file_description(
            matches,
            lambda state, error: (
                f"Expected resource file {self.path!r} property {property_name!r}"
                f"{'' if expected is _UNSET else f' to be {expected!r}'}; "
                f"properties={_resource_file_properties(state)!r} error={error!r}"
            ),
            include_properties=True,
            timeout=timeout,
            interval=interval,
        )

    def to_have_file_ext_resource(
        self,
        *,
        path: str | None = None,
        resource_type: str | None = None,
        uid: str | None = None,
        resource_id: str | None = None,
        exists: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if path is None and resource_type is None and uid is None and resource_id is None and exists is None:
            raise ValueError("Provide at least one external resource filter")

        def match(state: dict[str, Any]) -> dict[str, Any] | None:
            for entry in state.get("ext_resources", []):
                if isinstance(entry, dict) and _resource_file_ext_resource_matches(
                    entry,
                    path=path,
                    resource_type=resource_type,
                    uid=uid,
                    resource_id=resource_id,
                    exists=exists,
                ):
                    return entry
            return None

        return self._wait_for_resource_file_description(
            lambda state: match(state) is not None,
            lambda state, error: (
                f"Expected resource file {self.path!r} external resource "
                f"{_resource_file_ext_resource_filter_summary(path=path, resource_type=resource_type, uid=uid, resource_id=resource_id, exists=exists)}; "
                f"ext_resources={state.get('ext_resources', [])!r} error={error!r}"
            ),
            include_resources=True,
            timeout=timeout,
            interval=interval,
            transform=lambda state: match(state) or {},
        )

    def to_have_no_missing_dependencies(
        self,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_resource_dependencies(
            lambda state: bool(state.get("ok")),
            lambda state, error: (
                f"Expected resource {self.path!r} to have no missing dependencies; "
                f"missing={state.get('missing', [])!r} last={state!r} error={error!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_dependency(
        self,
        path: str | None = None,
        *,
        uid: str | None = None,
        dependency_type: str | None = None,
        resource_type: str | None = None,
        exists: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if path is None and uid is None and dependency_type is None and resource_type is None and exists is None:
            raise ValueError("Provide at least one dependency filter")

        def match(state: dict[str, Any]) -> dict[str, Any] | None:
            for dependency in state.get("dependencies", []):
                if isinstance(dependency, dict) and _resource_dependency_matches(
                    dependency,
                    path=path,
                    uid=uid,
                    dependency_type=dependency_type,
                    resource_type=resource_type,
                    exists=exists,
                ):
                    return dependency
            return None

        return self._wait_for_resource_dependencies(
            lambda state: match(state) is not None,
            lambda state, error: (
                f"Expected resource {self.path!r} dependency "
                f"{_resource_dependency_filter_summary(path=path, uid=uid, dependency_type=dependency_type, resource_type=resource_type, exists=exists)}; "
                f"dependencies={state.get('dependencies', [])!r} error={error!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda state: match(state) or {},
        )

    def to_be_referenced_by(
        self,
        path: str,
        *,
        search_path: str = "res://",
        dependency_type: str | None = None,
        resource_type: str | None = None,
        exists: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        def match(state: dict[str, Any]) -> dict[str, Any] | None:
            entry = _resource_reference_entry(state, path)
            if entry is None:
                return None
            dependency = entry.get("dependency", {})
            if not isinstance(dependency, dict):
                return None
            if not _resource_dependency_matches(
                dependency,
                path=self.path,
                dependency_type=dependency_type,
                resource_type=resource_type,
                exists=exists,
            ):
                return None
            return entry

        return self._wait_for_resource_references(
            lambda state: match(state) is not None,
            lambda state, error: (
                f"Expected resource {self.path!r} to be referenced by {path!r}; "
                f"references={state.get('references', [])!r} error={error!r}"
            ),
            search_path=search_path,
            dependency_type=dependency_type or "",
            resource_type=resource_type or "",
            exists=exists,
            timeout=timeout,
            interval=interval,
            transform=lambda state: match(state) or {},
        )

    def to_be_imported(
        self,
        *,
        importer: str | None = None,
        resource_type: str | None = None,
        generated_files_ready: bool | None = None,
        require_resource: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_import_metadata(
            lambda state: _resource_import_matches(
                state,
                importer=importer,
                resource_type=resource_type,
                generated_files_ready=generated_files_ready,
                require_resource=require_resource,
            ),
            lambda state, error: (
                f"Expected resource {self.path!r} to be imported with "
                f"{_resource_import_filter_summary(importer=importer, resource_type=resource_type, generated_files_ready=generated_files_ready, require_resource=require_resource)}; "
                f"diagnostics={_resource_import_diagnostic_summary(state)!r} last={state!r} error={error!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_be_import_listed(
        self,
        *,
        importer: str | None = None,
        resource_type: str | None = None,
        generated_files_ready: bool | None = None,
        imported: bool | None = True,
        ok: bool | None = None,
        require_resource: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        def match(state: dict[str, Any]) -> dict[str, Any] | None:
            entry = _resource_import_list_entry(state, self.path)
            if entry is None:
                return None
            if imported is not None and bool(entry.get("imported", False)) != imported:
                return None
            if ok is not None and bool(entry.get("ok", False)) != ok:
                return None
            if not _resource_import_wait_matches(
                entry,
                importer=importer,
                resource_type=resource_type,
                generated_files_ready=generated_files_ready,
                require_resource=require_resource,
            ):
                return None
            return entry

        return self._wait_for_resource_imports(
            lambda state: match(state) is not None,
            lambda state, error: (
                f"Expected imported resource {self.path!r} to be listed with "
                f"{_resource_import_filter_summary(importer=importer, resource_type=resource_type, generated_files_ready=generated_files_ready, require_resource=require_resource)}; "
                f"imports={state.get('imports', [])!r} error={error!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda state: match(state) or {},
        )

    def _wait_for_resource_inspect(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any], BaseException | None], str],
        *,
        type_hint: str = "",
        include_properties: bool = False,
        properties: list[str] | None = None,
        timeout: float,
        interval: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.client.resource_inspect(
                    self.path,
                    type_hint=type_hint,
                    include_properties=include_properties,
                    properties=properties,
                )
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if predicate(last):
                    return last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last, last_error))
            time.sleep(interval)

    def _wait_for_resource_file_description(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any], BaseException | None], str],
        *,
        timeout: float,
        interval: float,
        include_properties: bool = True,
        include_resources: bool = True,
        include_dependencies: bool = True,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.client.resource_file_describe(
                    self.path,
                    include_properties=include_properties,
                    include_resources=include_resources,
                    include_dependencies=include_dependencies,
                )
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if predicate(last):
                    return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last, last_error))
            time.sleep(interval)

    def _wait_for_resource_dependencies(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any], BaseException | None], str],
        *,
        timeout: float,
        interval: float,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.client.resource_dependencies(self.path)
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if predicate(last):
                    return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last, last_error))
            time.sleep(interval)

    def _wait_for_resource_files(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any], BaseException | None], str],
        *,
        timeout: float,
        interval: float,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.client.resource_files(
                    self.path,
                    include_dependencies=True,
                    max_results=1,
                )
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if predicate(last):
                    return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last, last_error))
            time.sleep(interval)

    def _wait_for_resource_references(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any], BaseException | None], str],
        *,
        search_path: str,
        dependency_type: str = "",
        resource_type: str = "",
        exists: bool | None = None,
        timeout: float,
        interval: float,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.client.resource_references(
                    self.path,
                    search_path=search_path,
                    dependency_type=dependency_type,
                    resource_type=resource_type,
                    exists=exists,
                )
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if predicate(last):
                    return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last, last_error))
            time.sleep(interval)

    def _wait_for_resource_imports(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any], BaseException | None], str],
        *,
        timeout: float,
        interval: float,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.client.resource_imports(
                    self.path,
                    include_missing_metadata=True,
                    max_results=1,
                )
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if predicate(last):
                    return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last, last_error))
            time.sleep(interval)

    def _wait_for_import_metadata(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any], BaseException | None], str],
        *,
        timeout: float,
        interval: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.client.resource_import_metadata(self.path)
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if predicate(last):
                    return last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last, last_error))
            time.sleep(interval)


class ResourceClassExpect:
    def __init__(self, client: GodotClient, class_name: str):
        self.client = client
        self.class_name = class_name

    def to_be_resource(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for_schema(
            lambda schema: bool(schema.get("exists")) and bool(schema.get("can_instantiate")) and bool(schema.get("is_resource")),
            lambda schema, error: f"Expected {self.class_name!r} to be an instantiable Resource class; last={schema!r} error={error!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_be_listed(
        self,
        *,
        base_class: str = "Resource",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_classes(
            lambda state: _resource_class_list_entry(state, self.class_name) is not None,
            lambda state, error: (
                f"Expected resource class {self.class_name!r} to be listed under {base_class!r}; "
                f"classes={state.get('classes', [])!r} error={error!r}"
            ),
            base_class=base_class,
            timeout=timeout,
            interval=interval,
            transform=lambda state: _resource_class_list_entry(state, self.class_name) or {},
        )

    def to_have_property(
        self,
        property_name: str,
        *,
        type_name: str | None = None,
        storage: bool | None = None,
        editor_visible: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        def match(schema: dict[str, Any]) -> dict[str, Any] | None:
            return _resource_class_property(
                schema,
                property_name,
                type_name=type_name,
                storage=storage,
                editor_visible=editor_visible,
            )

        return self._wait_for_schema(
            lambda schema: match(schema) is not None,
            lambda schema, error: (
                f"Expected resource class {self.class_name!r} property {property_name!r}"
                f"{_resource_class_property_filter_summary(type_name=type_name, storage=storage, editor_visible=editor_visible)}; "
                f"properties={schema.get('properties', [])!r} error={error!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda schema: match(schema) or {},
        )

    def to_have_properties(
        self,
        properties: list[str] | tuple[str, ...] | set[str],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected = [str(property_name) for property_name in properties]
        return self._wait_for_schema(
            lambda schema: all(_resource_class_property(schema, property_name) is not None for property_name in expected),
            lambda schema, error: (
                f"Expected resource class {self.class_name!r} properties {expected!r}; "
                f"properties={schema.get('properties', [])!r} error={error!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def _wait_for_schema(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any], BaseException | None], str],
        *,
        timeout: float,
        interval: float,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.client.resource_class_describe(self.class_name)
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if predicate(last):
                    return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last, last_error))
            time.sleep(interval)

    def _wait_for_classes(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any], BaseException | None], str],
        *,
        base_class: str,
        timeout: float,
        interval: float,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.client.resource_classes(
                    base_class=base_class,
                    name_contains=self.class_name,
                    max_results=500,
                )
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if predicate(last):
                    return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last, last_error))
            time.sleep(interval)


class NodeClassExpect:
    def __init__(self, client: GodotClient, class_name: str):
        self.client = client
        self.class_name = class_name

    def to_be_listed(
        self,
        *,
        base_class: str = "Node",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_classes(
            lambda state: _node_class_list_entry(state, self.class_name) is not None,
            lambda state, error: (
                f"Expected node class {self.class_name!r} to be listed under {base_class!r}; "
                f"classes={state.get('classes', [])!r} error={error!r}"
            ),
            base_class=base_class,
            timeout=timeout,
            interval=interval,
            transform=lambda state: _node_class_list_entry(state, self.class_name) or {},
        )

    def to_be_instantiable(
        self,
        *,
        base_class: str = "Node",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        def match(state: dict[str, Any]) -> bool:
            entry = _node_class_list_entry(state, self.class_name)
            return bool(entry and entry.get("is_node") and entry.get("can_instantiate"))

        return self._wait_for_classes(
            match,
            lambda state, error: (
                f"Expected node class {self.class_name!r} to be instantiable under {base_class!r}; "
                f"classes={state.get('classes', [])!r} error={error!r}"
            ),
            base_class=base_class,
            timeout=timeout,
            interval=interval,
            transform=lambda state: _node_class_list_entry(state, self.class_name) or {},
        )

    def to_be_node(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for_schema(
            lambda schema: bool(schema.get("exists")) and bool(schema.get("can_instantiate")) and bool(schema.get("is_node")),
            lambda schema, error: f"Expected {self.class_name!r} to be an instantiable Node class; last={schema!r} error={error!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_have_property(
        self,
        property_name: str,
        *,
        type_name: str | None = None,
        storage: bool | None = None,
        editor_visible: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        def match(schema: dict[str, Any]) -> dict[str, Any] | None:
            return _node_class_property(
                schema,
                property_name,
                type_name=type_name,
                storage=storage,
                editor_visible=editor_visible,
            )

        return self._wait_for_schema(
            lambda schema: match(schema) is not None,
            lambda schema, error: (
                f"Expected node class {self.class_name!r} property {property_name!r}"
                f"{_resource_class_property_filter_summary(type_name=type_name, storage=storage, editor_visible=editor_visible)}; "
                f"properties={schema.get('properties', [])!r} error={error!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda schema: match(schema) or {},
        )

    def to_have_properties(
        self,
        properties: list[str] | tuple[str, ...] | set[str],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected = [str(property_name) for property_name in properties]
        return self._wait_for_schema(
            lambda schema: all(_node_class_property(schema, property_name) is not None for property_name in expected),
            lambda schema, error: (
                f"Expected node class {self.class_name!r} properties {expected!r}; "
                f"properties={schema.get('properties', [])!r} error={error!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_method(
        self,
        method_name: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_schema(
            lambda schema: _node_class_method(schema, method_name) is not None,
            lambda schema, error: (
                f"Expected node class {self.class_name!r} method {method_name!r}; "
                f"methods={schema.get('methods', [])!r} error={error!r}"
            ),
            timeout=timeout,
            interval=interval,
            describe_kwargs={"methods": [method_name], "include_signals": False},
            transform=lambda schema: _node_class_method(schema, method_name) or {},
        )

    def to_have_signal(
        self,
        signal_name: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_schema(
            lambda schema: _node_class_signal(schema, signal_name) is not None,
            lambda schema, error: (
                f"Expected node class {self.class_name!r} signal {signal_name!r}; "
                f"signals={schema.get('signals', [])!r} error={error!r}"
            ),
            timeout=timeout,
            interval=interval,
            describe_kwargs={"signals": [signal_name], "include_methods": False},
            transform=lambda schema: _node_class_signal(schema, signal_name) or {},
        )

    def _wait_for_schema(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any], BaseException | None], str],
        *,
        timeout: float,
        interval: float,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        describe_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.client.node_class_describe(self.class_name, **(describe_kwargs or {}))
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if predicate(last):
                    return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last, last_error))
            time.sleep(interval)

    def _wait_for_classes(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any], BaseException | None], str],
        *,
        base_class: str,
        timeout: float,
        interval: float,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.client.node_classes(
                    base_class=base_class,
                    name_contains=self.class_name,
                    max_results=500,
                )
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if predicate(last):
                    return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last, last_error))
            time.sleep(interval)


class LogExpect:
    def __init__(self, client: GodotClient):
        self.client = client

    def to_have_message(
        self,
        text: str | None = None,
        *,
        severity: str | None = None,
        kind: str | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.wait_for_log(
            text,
            severity=severity,
            kind=kind,
            predicate=predicate,
            timeout=timeout,
            interval=interval,
        )

    def to_have_error(
        self,
        text: str | None = None,
        *,
        kind: str | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.to_have_message(
            text,
            severity="error",
            kind=kind,
            predicate=predicate,
            timeout=timeout,
            interval=interval,
        )

    def to_have_warning(
        self,
        text: str | None = None,
        *,
        kind: str | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.to_have_message(
            text,
            severity="warning",
            kind=kind,
            predicate=predicate,
            timeout=timeout,
            interval=interval,
        )

    def not_to_have_error(
        self,
        text: str | None = None,
        *,
        kind: str | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> None:
        return self.not_to_have_message(
            text,
            severity="error",
            kind=kind,
            predicate=predicate,
            timeout=timeout,
            interval=interval,
        )

    def not_to_have_warning(
        self,
        text: str | None = None,
        *,
        kind: str | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> None:
        return self.not_to_have_message(
            text,
            severity="warning",
            kind=kind,
            predicate=predicate,
            timeout=timeout,
            interval=interval,
        )

    def not_to_have_message(
        self,
        text: str | None = None,
        *,
        severity: str | None = None,
        kind: str | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> None:
        deadline = time.monotonic() + timeout
        while True:
            events = self.client.log_events(severity=severity, kind=kind, text=text)
            for event in events:
                if predicate is None or predicate(event):
                    raise AssertionError(f"Expected Godot log not to contain event {event!r}")
            if time.monotonic() >= deadline:
                return
            time.sleep(interval)


class TraceExpect:
    def __init__(self, client: GodotClient):
        self.client = client

    def to_have_event(
        self,
        event_type: str | None = None,
        *,
        data: dict[str, Any] | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.wait_for_trace_event(
            event_type,
            data=data,
            predicate=predicate,
            timeout=timeout,
            interval=interval,
        )

    def not_to_have_event(
        self,
        event_type: str | None = None,
        *,
        data: dict[str, Any] | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> None:
        deadline = time.monotonic() + timeout
        while True:
            events = self.client.trace_events(event_type=event_type, data=data)
            for event in events:
                if predicate is None or predicate(event):
                    raise AssertionError(f"Expected trace not to contain event {event!r}")
            if time.monotonic() >= deadline:
                return
            time.sleep(interval)

    def to_have_event_sequence(
        self,
        event_types: list[str] | tuple[str, ...],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[dict[str, Any]]:
        return self.client.wait_for_trace_sequence(event_types, timeout=timeout, interval=interval)

    def to_have_event_count(
        self,
        expected: int,
        event_type: str | None = None,
        *,
        data: dict[str, Any] | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        at_least: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[dict[str, Any]]:
        return self.client.wait_for_trace_count(
            expected,
            event_type,
            data=data,
            predicate=predicate,
            at_least=at_least,
            timeout=timeout,
            interval=interval,
        )

    def to_be_empty(self, *, timeout: float = 5.0, interval: float = 0.05) -> list[dict[str, Any]]:
        return self.to_have_event_count(0, timeout=timeout, interval=interval)

    def to_have_rpc(
        self,
        method: str,
        *,
        ok: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"method": method}
        if ok is not None:
            data["ok"] = ok
        return self.to_have_event("rpc", data=data, timeout=timeout, interval=interval)

    def not_to_have_rpc(
        self,
        method: str,
        *,
        ok: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> None:
        data: dict[str, Any] = {"method": method}
        if ok is not None:
            data["ok"] = ok
        return self.not_to_have_event("rpc", data=data, timeout=timeout, interval=interval)

    def to_have_rpc_count(
        self,
        method: str,
        expected: int,
        *,
        ok: bool | None = None,
        at_least: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[dict[str, Any]]:
        data: dict[str, Any] = {"method": method}
        if ok is not None:
            data["ok"] = ok
        return self.to_have_event_count(
            expected,
            "rpc",
            data=data,
            at_least=at_least,
            timeout=timeout,
            interval=interval,
        )


class SignalExpect:
    def __init__(
        self,
        client: GodotClient,
        selector: str | dict[str, Any] | None = None,
        signal: str | None = None,
        *,
        root: str | dict[str, Any] | None = None,
        watch_id: str | None = None,
        once: bool = False,
    ):
        self.client = client
        self.selector = selector
        self.signal = signal
        self.root = root
        self.watch_id = watch_id
        self.once = once

    def __enter__(self) -> "SignalExpect":
        self.watch()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def watch(self) -> "SignalExpect":
        self._ensure_watch()
        return self

    def close(self) -> None:
        if self.watch_id:
            self.client.signal_unwatch(self.watch_id)
            self.watch_id = None

    def clear(self) -> dict[str, Any]:
        return self.client.signal_clear(watch_id=self.watch_id)

    def events(self, *, clear: bool = False) -> list[dict[str, Any]]:
        return self.client.signal_events(watch_id=self.watch_id, clear=clear)

    def to_have_event(
        self,
        signal: str | None = None,
        *,
        path: str | None = None,
        fields: dict[str, Any] | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        action: Callable[[], Any] | None = None,
        clear: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        event_signal = signal or self.signal
        temporary_watch = False
        if self.watch_id is None and self.selector is not None and event_signal is not None:
            self._ensure_watch(signal=event_signal)
            temporary_watch = action is not None
        try:
            if action is not None:
                action()
            return self.client.wait_for_signal_event(
                watch_id=self.watch_id,
                signal=event_signal,
                path=path,
                fields=fields,
                predicate=predicate,
                timeout=timeout,
                interval=interval,
                clear=clear,
            )
        finally:
            if temporary_watch:
                self.close()

    def not_to_have_event(
        self,
        signal: str | None = None,
        *,
        path: str | None = None,
        fields: dict[str, Any] | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> None:
        event_signal = signal or self.signal
        deadline = time.monotonic() + timeout
        self._ensure_watch_if_configured(event_signal)
        while True:
            events = self.client._matching_signal_events(
                watch_id=self.watch_id,
                signal=event_signal,
                path=path,
                fields=fields,
                predicate=predicate,
            )
            if events:
                raise AssertionError(f"Expected signal events not to contain {events[0]!r}")
            if time.monotonic() >= deadline:
                return
            time.sleep(interval)

    def to_have_event_count(
        self,
        expected: int,
        signal: str | None = None,
        *,
        path: str | None = None,
        fields: dict[str, Any] | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        at_least: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[dict[str, Any]]:
        event_signal = signal or self.signal
        self._ensure_watch_if_configured(event_signal)
        return self.client.wait_for_signal_count(
            expected,
            watch_id=self.watch_id,
            signal=event_signal,
            path=path,
            fields=fields,
            predicate=predicate,
            at_least=at_least,
            timeout=timeout,
            interval=interval,
        )

    def to_have_event_sequence(
        self,
        expected: list[str | dict[str, Any]] | tuple[str | dict[str, Any], ...],
        *,
        action: Callable[[], Any] | None = None,
        clear: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[dict[str, Any]]:
        temporary_watch = False
        if self.watch_id is None and self.selector is not None and self.signal is not None:
            self._ensure_watch()
            temporary_watch = action is not None
        try:
            if action is not None:
                action()
            return self.client.wait_for_signal_sequence(
                expected,
                watch_id=self.watch_id,
                timeout=timeout,
                interval=interval,
                clear=clear,
            )
        finally:
            if temporary_watch:
                self.close()

    def to_be_empty(self, *, timeout: float = 5.0, interval: float = 0.05) -> list[dict[str, Any]]:
        return self.to_have_event_count(0, timeout=timeout, interval=interval)

    def _ensure_watch_if_configured(self, signal: str | None = None) -> None:
        if self.watch_id is None and self.selector is not None and (signal or self.signal):
            self._ensure_watch(signal=signal or self.signal)

    def _ensure_watch(self, signal: str | None = None) -> None:
        if self.watch_id is not None:
            return
        if self.selector is None or not (signal or self.signal):
            return
        watch = self.client.signal_watch(
            self.selector,
            str(signal or self.signal),
            root=self.root,
            once=self.once,
        )
        self.watch_id = str(watch["watch_id"])


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


class Physics2DExpect:
    def __init__(self, client: GodotClient):
        self.client = client

    def to_have_point_collision(
        self,
        x: float,
        y: float,
        *,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_results: int = 32,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_point(
            x,
            y,
            lambda state: _physics2d_collision_entry(
                state.get("collisions", []),
                name=name,
                path=path,
                class_name=class_name,
                groups=groups,
                metadata=metadata,
                fields=fields,
            )
            is not None,
            lambda state: (
                f"Expected 2D physics point ({x}, {y}) to collide"
                f"{_physics2d_filter_summary(name=name, path=path, class_name=class_name, groups=groups, metadata=metadata, fields=fields)}; "
                f"collisions={state.get('collisions', [])!r}"
            ),
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            max_results=max_results,
            timeout=timeout,
            interval=interval,
            transform=lambda state: _physics2d_collision_entry(
                state.get("collisions", []),
                name=name,
                path=path,
                class_name=class_name,
                groups=groups,
                metadata=metadata,
                fields=fields,
            )
            or {},
        )

    def not_to_have_point_collision(
        self,
        x: float,
        y: float,
        *,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_results: int = 32,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_point(
            x,
            y,
            lambda state: _physics2d_collision_entry(
                state.get("collisions", []),
                name=name,
                path=path,
                class_name=class_name,
                groups=groups,
                metadata=metadata,
                fields=fields,
            )
            is None,
            lambda state: (
                f"Expected 2D physics point ({x}, {y}) not to collide"
                f"{_physics2d_filter_summary(name=name, path=path, class_name=class_name, groups=groups, metadata=metadata, fields=fields)}; "
                f"collisions={state.get('collisions', [])!r}"
            ),
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            max_results=max_results,
            timeout=timeout,
            interval=interval,
        )

    def to_have_ray_collision(
        self,
        from_x: float,
        from_y: float,
        to_x: float,
        to_y: float,
        *,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_ray(
            from_x,
            from_y,
            to_x,
            to_y,
            lambda state: bool(state.get("hit"))
            and _physics2d_collision_matches(
                state.get("collision", {}),
                name=name,
                path=path,
                class_name=class_name,
                groups=groups,
                metadata=metadata,
                fields=fields,
            ),
            lambda state: (
                f"Expected 2D physics ray ({from_x}, {from_y}) -> ({to_x}, {to_y}) to collide"
                f"{_physics2d_filter_summary(name=name, path=path, class_name=class_name, groups=groups, metadata=metadata, fields=fields)}; "
                f"last={state!r}"
            ),
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            timeout=timeout,
            interval=interval,
            transform=lambda state: dict(state.get("collision", {})),
        )

    def not_to_have_ray_collision(
        self,
        from_x: float,
        from_y: float,
        to_x: float,
        to_y: float,
        *,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_ray(
            from_x,
            from_y,
            to_x,
            to_y,
            lambda state: not bool(state.get("hit"))
            or not _physics2d_collision_matches(
                state.get("collision", {}),
                name=name,
                path=path,
                class_name=class_name,
                groups=groups,
                metadata=metadata,
                fields=fields,
            ),
            lambda state: (
                f"Expected 2D physics ray ({from_x}, {from_y}) -> ({to_x}, {to_y}) not to collide"
                f"{_physics2d_filter_summary(name=name, path=path, class_name=class_name, groups=groups, metadata=metadata, fields=fields)}; "
                f"last={state!r}"
            ),
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            timeout=timeout,
            interval=interval,
        )

    def _wait_for_point(
        self,
        x: float,
        y: float,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any]], str],
        *,
        collision_mask: int | None,
        collide_with_bodies: bool,
        collide_with_areas: bool,
        max_results: int,
        timeout: float,
        interval: float,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.client.physics2d_point(
                x,
                y,
                collision_mask=collision_mask,
                collide_with_bodies=collide_with_bodies,
                collide_with_areas=collide_with_areas,
                max_results=max_results,
            )
            if predicate(last):
                return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last))
            time.sleep(interval)

    def _wait_for_ray(
        self,
        from_x: float,
        from_y: float,
        to_x: float,
        to_y: float,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any]], str],
        *,
        collision_mask: int | None,
        collide_with_bodies: bool,
        collide_with_areas: bool,
        timeout: float,
        interval: float,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.client.physics2d_ray(
                from_x,
                from_y,
                to_x,
                to_y,
                collision_mask=collision_mask,
                collide_with_bodies=collide_with_bodies,
                collide_with_areas=collide_with_areas,
            )
            if predicate(last):
                return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last))
            time.sleep(interval)


class Physics3DExpect:
    def __init__(self, client: GodotClient):
        self.client = client

    def to_have_point_collision(
        self,
        x: float,
        y: float,
        z: float,
        *,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_results: int = 32,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_point(
            x,
            y,
            z,
            lambda state: _physics2d_collision_entry(
                state.get("collisions", []),
                name=name,
                path=path,
                class_name=class_name,
                groups=groups,
                metadata=metadata,
                fields=fields,
            )
            is not None,
            lambda state: (
                f"Expected 3D physics point ({x}, {y}, {z}) to collide"
                f"{_physics2d_filter_summary(name=name, path=path, class_name=class_name, groups=groups, metadata=metadata, fields=fields)}; "
                f"collisions={state.get('collisions', [])!r}"
            ),
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            max_results=max_results,
            timeout=timeout,
            interval=interval,
            transform=lambda state: _physics2d_collision_entry(
                state.get("collisions", []),
                name=name,
                path=path,
                class_name=class_name,
                groups=groups,
                metadata=metadata,
                fields=fields,
            )
            or {},
        )

    def not_to_have_point_collision(
        self,
        x: float,
        y: float,
        z: float,
        *,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_results: int = 32,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_point(
            x,
            y,
            z,
            lambda state: _physics2d_collision_entry(
                state.get("collisions", []),
                name=name,
                path=path,
                class_name=class_name,
                groups=groups,
                metadata=metadata,
                fields=fields,
            )
            is None,
            lambda state: (
                f"Expected 3D physics point ({x}, {y}, {z}) not to collide"
                f"{_physics2d_filter_summary(name=name, path=path, class_name=class_name, groups=groups, metadata=metadata, fields=fields)}; "
                f"collisions={state.get('collisions', [])!r}"
            ),
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            max_results=max_results,
            timeout=timeout,
            interval=interval,
        )

    def to_have_ray_collision(
        self,
        from_x: float,
        from_y: float,
        from_z: float,
        to_x: float,
        to_y: float,
        to_z: float,
        *,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_ray(
            from_x,
            from_y,
            from_z,
            to_x,
            to_y,
            to_z,
            lambda state: bool(state.get("hit"))
            and _physics2d_collision_matches(
                state.get("collision", {}),
                name=name,
                path=path,
                class_name=class_name,
                groups=groups,
                metadata=metadata,
                fields=fields,
            ),
            lambda state: (
                f"Expected 3D physics ray ({from_x}, {from_y}, {from_z}) -> ({to_x}, {to_y}, {to_z}) to collide"
                f"{_physics2d_filter_summary(name=name, path=path, class_name=class_name, groups=groups, metadata=metadata, fields=fields)}; "
                f"last={state!r}"
            ),
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            timeout=timeout,
            interval=interval,
            transform=lambda state: dict(state.get("collision", {})),
        )

    def not_to_have_ray_collision(
        self,
        from_x: float,
        from_y: float,
        from_z: float,
        to_x: float,
        to_y: float,
        to_z: float,
        *,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_ray(
            from_x,
            from_y,
            from_z,
            to_x,
            to_y,
            to_z,
            lambda state: not bool(state.get("hit"))
            or not _physics2d_collision_matches(
                state.get("collision", {}),
                name=name,
                path=path,
                class_name=class_name,
                groups=groups,
                metadata=metadata,
                fields=fields,
            ),
            lambda state: (
                f"Expected 3D physics ray ({from_x}, {from_y}, {from_z}) -> ({to_x}, {to_y}, {to_z}) not to collide"
                f"{_physics2d_filter_summary(name=name, path=path, class_name=class_name, groups=groups, metadata=metadata, fields=fields)}; "
                f"last={state!r}"
            ),
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            timeout=timeout,
            interval=interval,
        )

    def to_pick_camera_collision(
        self,
        screen_x: float,
        screen_y: float,
        *,
        camera: str | dict[str, Any] | None = None,
        root: str | dict[str, Any] | None = None,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_distance: float = 1000.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_camera_pick(
            screen_x,
            screen_y,
            lambda state: bool(state.get("hit"))
            and _physics2d_collision_matches(
                state.get("collision", {}),
                name=name,
                path=path,
                class_name=class_name,
                groups=groups,
                metadata=metadata,
                fields=fields,
            ),
            lambda state: (
                f"Expected 3D camera pick ({screen_x}, {screen_y}) to collide"
                f"{_physics2d_filter_summary(name=name, path=path, class_name=class_name, groups=groups, metadata=metadata, fields=fields)}; "
                f"last={state!r}"
            ),
            camera=camera,
            root=root,
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            max_distance=max_distance,
            timeout=timeout,
            interval=interval,
            transform=lambda state: dict(state.get("collision", {})),
        )

    def not_to_pick_camera_collision(
        self,
        screen_x: float,
        screen_y: float,
        *,
        camera: str | dict[str, Any] | None = None,
        root: str | dict[str, Any] | None = None,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        collision_mask: int | None = None,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = True,
        max_distance: float = 1000.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_camera_pick(
            screen_x,
            screen_y,
            lambda state: not bool(state.get("hit"))
            or not _physics2d_collision_matches(
                state.get("collision", {}),
                name=name,
                path=path,
                class_name=class_name,
                groups=groups,
                metadata=metadata,
                fields=fields,
            ),
            lambda state: (
                f"Expected 3D camera pick ({screen_x}, {screen_y}) not to collide"
                f"{_physics2d_filter_summary(name=name, path=path, class_name=class_name, groups=groups, metadata=metadata, fields=fields)}; "
                f"last={state!r}"
            ),
            camera=camera,
            root=root,
            collision_mask=collision_mask,
            collide_with_bodies=collide_with_bodies,
            collide_with_areas=collide_with_areas,
            max_distance=max_distance,
            timeout=timeout,
            interval=interval,
        )

    def _wait_for_point(
        self,
        x: float,
        y: float,
        z: float,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any]], str],
        *,
        collision_mask: int | None,
        collide_with_bodies: bool,
        collide_with_areas: bool,
        max_results: int,
        timeout: float,
        interval: float,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.client.physics3d_point(
                x,
                y,
                z,
                collision_mask=collision_mask,
                collide_with_bodies=collide_with_bodies,
                collide_with_areas=collide_with_areas,
                max_results=max_results,
            )
            if predicate(last):
                return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last))
            time.sleep(interval)

    def _wait_for_ray(
        self,
        from_x: float,
        from_y: float,
        from_z: float,
        to_x: float,
        to_y: float,
        to_z: float,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any]], str],
        *,
        collision_mask: int | None,
        collide_with_bodies: bool,
        collide_with_areas: bool,
        timeout: float,
        interval: float,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.client.physics3d_ray(
                from_x,
                from_y,
                from_z,
                to_x,
                to_y,
                to_z,
                collision_mask=collision_mask,
                collide_with_bodies=collide_with_bodies,
                collide_with_areas=collide_with_areas,
            )
            if predicate(last):
                return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last))
            time.sleep(interval)

    def _wait_for_camera_pick(
        self,
        screen_x: float,
        screen_y: float,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any]], str],
        *,
        camera: str | dict[str, Any] | None,
        root: str | dict[str, Any] | None,
        collision_mask: int | None,
        collide_with_bodies: bool,
        collide_with_areas: bool,
        max_distance: float,
        timeout: float,
        interval: float,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.client.camera3d_pick(
                screen_x,
                screen_y,
                camera=camera,
                root=root,
                collision_mask=collision_mask,
                collide_with_bodies=collide_with_bodies,
                collide_with_areas=collide_with_areas,
                max_distance=max_distance,
            )
            if predicate(last):
                return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last))
            time.sleep(interval)


class ProjectExpect:
    def __init__(self, client: GodotClient):
        self.client = client

    def to_have_export_preset(
        self,
        name: str,
        *,
        platform: str | None = None,
        export_path: str | None = None,
        runnable: bool | None = None,
        options: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_project_state(
            self.client.project_export_presets,
            lambda state: _project_export_preset_entry(
                state,
                name,
                platform=platform,
                export_path=export_path,
                runnable=runnable,
                options=options,
                fields=fields,
            )
            is not None,
            lambda state: (
                f"Expected export preset {name!r}"
                f"{_project_export_preset_filter_summary(platform=platform, export_path=export_path, runnable=runnable, options=options, fields=fields)}; "
                f"last={state!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda state: _project_export_preset_entry(
                state,
                name,
                platform=platform,
                export_path=export_path,
                runnable=runnable,
                options=options,
                fields=fields,
            )
            or {},
        )

    def not_to_have_export_preset(
        self,
        name: str,
        *,
        platform: str | None = None,
        export_path: str | None = None,
        runnable: bool | None = None,
        options: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_project_state(
            self.client.project_export_presets,
            lambda state: _project_export_preset_entry(
                state,
                name,
                platform=platform,
                export_path=export_path,
                runnable=runnable,
                options=options,
                fields=fields,
            )
            is None,
            lambda state: (
                f"Expected project not to have export preset {name!r}"
                f"{_project_export_preset_filter_summary(platform=platform, export_path=export_path, runnable=runnable, options=options, fields=fields)}; "
                f"last={state!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_main_scene(
        self,
        path: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_project_state(
            lambda: self.client.project_main_scene(),
            lambda state: state.get("path") == path,
            lambda state: f"Expected project main scene {path!r}; last={state!r}",
            timeout=timeout,
            interval=interval,
        )

    def not_to_have_main_scene(
        self,
        path: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_project_state(
            lambda: self.client.project_main_scene(),
            lambda state: state.get("path") != path,
            lambda state: f"Expected project main scene not to be {path!r}; last={state!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_have_autoload(
        self,
        name: str,
        *,
        path: str | None = None,
        singleton: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_project_state(
            self.client.project_autoloads,
            lambda state: _project_autoload_entry(state, name, path=path, singleton=singleton) is not None,
            lambda state: (
                f"Expected project autoload {name!r}"
                f"{_project_autoload_filter_summary(path=path, singleton=singleton)}; last={state!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda state: _project_autoload_entry(state, name, path=path, singleton=singleton) or {},
        )

    def not_to_have_autoload(
        self,
        name: str,
        *,
        path: str | None = None,
        singleton: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_project_state(
            self.client.project_autoloads,
            lambda state: _project_autoload_entry(state, name, path=path, singleton=singleton) is None,
            lambda state: (
                f"Expected project not to have autoload {name!r}"
                f"{_project_autoload_filter_summary(path=path, singleton=singleton)}; last={state!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_input_action(
        self,
        action: str,
        *,
        event_count: int | None = None,
        min_event_count: int | None = None,
        deadzone: float | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if event_count is not None and min_event_count is not None:
            raise ValueError("Use event_count or min_event_count, not both")
        return self._wait_for_project_state(
            lambda: self.client.input_action_describe(action),
            lambda state: _input_action_matches(
                state,
                event_count=event_count,
                min_event_count=min_event_count,
                deadzone=deadzone,
            ),
            lambda state: (
                f"Expected input action {action!r}"
                f"{_input_action_filter_summary(event_count=event_count, min_event_count=min_event_count, deadzone=deadzone)}; "
                f"last={state!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_input_action_pressed(
        self,
        action: str,
        *,
        strength: float | None = None,
        min_strength: float | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if strength is not None and min_strength is not None:
            raise ValueError("Use strength or min_strength, not both")
        return self._wait_for_project_state(
            lambda: self.client.input_action_describe(action, include_events=False),
            lambda state: _input_action_state_matches(
                state,
                pressed=True,
                strength=strength,
                min_strength=min_strength,
            ),
            lambda state: (
                f"Expected input action {action!r} to be pressed"
                f"{_input_action_state_filter_summary(strength=strength, min_strength=min_strength)}; "
                f"last={state!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def not_to_have_input_action_pressed(
        self,
        action: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_project_state(
            lambda: self.client.input_action_describe(action, include_events=False),
            lambda state: not bool(state.get("pressed")),
            lambda state: f"Expected input action {action!r} not to be pressed; last={state!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_have_input_action_strength(
        self,
        action: str,
        *,
        strength: float | None = None,
        min_strength: float | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if strength is None and min_strength is None:
            raise ValueError("strength or min_strength is required")
        if strength is not None and min_strength is not None:
            raise ValueError("Use strength or min_strength, not both")
        return self._wait_for_project_state(
            lambda: self.client.input_action_describe(action, include_events=False),
            lambda state: _input_action_state_matches(
                state,
                strength=strength,
                min_strength=min_strength,
            ),
            lambda state: (
                f"Expected input action {action!r}"
                f"{_input_action_state_filter_summary(strength=strength, min_strength=min_strength)}; "
                f"last={state!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_input_action_event(
        self,
        action: str,
        *,
        event_type: str | None = None,
        key: str | int | None = None,
        button: str | int | None = None,
        axis: str | int | None = None,
        value: float | None = None,
        device: int | None = None,
        modifiers: dict[str, Any] | list[str] | tuple[str, ...] | str | None = None,
        fields: dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_project_state(
            lambda: self.client.input_action_describe(action, include_events=True),
            lambda state: _input_action_event_entry(
                state,
                event_type=event_type,
                key=key,
                button=button,
                axis=axis,
                value=value,
                device=device,
                modifiers=modifiers,
                fields=fields,
            )
            is not None,
            lambda state: (
                f"Expected input action {action!r} to have event"
                f"{_input_action_event_filter_summary(event_type=event_type, key=key, button=button, axis=axis, value=value, device=device, modifiers=modifiers, fields=fields)}; "
                f"events={state.get('events', [])!r}; last={state!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda state: _input_action_event_entry(
                state,
                event_type=event_type,
                key=key,
                button=button,
                axis=axis,
                value=value,
                device=device,
                modifiers=modifiers,
                fields=fields,
            )
            or {},
        )

    def not_to_have_input_action_event(
        self,
        action: str,
        *,
        event_type: str | None = None,
        key: str | int | None = None,
        button: str | int | None = None,
        axis: str | int | None = None,
        value: float | None = None,
        device: int | None = None,
        modifiers: dict[str, Any] | list[str] | tuple[str, ...] | str | None = None,
        fields: dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_project_state(
            lambda: self.client.input_action_describe(action, include_events=True),
            lambda state: _input_action_event_entry(
                state,
                event_type=event_type,
                key=key,
                button=button,
                axis=axis,
                value=value,
                device=device,
                modifiers=modifiers,
                fields=fields,
            )
            is None,
            lambda state: (
                f"Expected input action {action!r} not to have event"
                f"{_input_action_event_filter_summary(event_type=event_type, key=key, button=button, axis=axis, value=value, device=device, modifiers=modifiers, fields=fields)}; "
                f"events={state.get('events', [])!r}; last={state!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def not_to_have_input_action(
        self,
        action: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_project_state(
            lambda: self.client.input_action_describe(action),
            lambda state: not bool(state.get("exists")),
            lambda state: f"Expected input action {action!r} not to exist; last={state!r}",
            timeout=timeout,
            interval=interval,
        )

    def _wait_for_project_state(
        self,
        read_state: Callable[[], dict[str, Any]],
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any]], str],
        *,
        timeout: float,
        interval: float,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = read_state()
            if predicate(last):
                return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last))
            time.sleep(interval)


class EngineExpect:
    def __init__(self, client: GodotClient):
        self.client = client

    def to_be_available(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for(
            lambda info: isinstance(info.get("godot"), dict),
            lambda info: f"Expected engine info to be available; last={info!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_be_editor(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for(
            lambda info: bool(info.get("editor")),
            lambda info: f"Expected engine to be running in editor mode; last={info!r}",
            timeout=timeout,
            interval=interval,
        )

    def not_to_be_editor(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for(
            lambda info: not bool(info.get("editor")),
            lambda info: f"Expected engine not to be running in editor mode; last={info!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_have_godot_version(
        self,
        *,
        major: int | None = None,
        minor: int | None = None,
        patch: int | None = None,
        status: str | None = None,
        string_contains: str | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda info: _engine_version_matches(
                info,
                major=major,
                minor=minor,
                patch=patch,
                status=status,
                string_contains=string_contains,
            ),
            lambda info: (
                "Expected Godot version"
                f"{_engine_version_filter_summary(major=major, minor=minor, patch=patch, status=status, string_contains=string_contains)}; "
                f"got {_engine_version_info(info)!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_project_path(
        self,
        path: str,
        *,
        exact: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda info: _engine_project_path_matches(info, path, exact=exact),
            lambda info: f"Expected project path {path!r} exact={exact}; got {info.get('project_path')!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_have_server_port(self, port: int, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for(
            lambda info: int(info.get("server_port", -1)) == int(port),
            lambda info: f"Expected server port {int(port)}; got {info.get('server_port')!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_match_info(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda info: _dict_contains(info, expected),
            lambda info: f"Expected engine info to include {expected!r}; last={info!r}",
            timeout=timeout,
            interval=interval,
        )

    def _wait_for(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any]], str],
        *,
        timeout: float,
        interval: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.client.engine_info()
            if predicate(last):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last))
            time.sleep(interval)


class ViewportExpect:
    def __init__(self, client: GodotClient):
        self.client = client

    def to_have_size(
        self,
        width: int,
        height: int,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda info: _viewport_size_matches(info, width, height),
            lambda info: (
                f"Expected viewport size {int(width)}x{int(height)}; "
                f"got {_viewport_window_size(info)!r}; last={info!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def not_to_have_size(
        self,
        width: int,
        height: int,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda info: not _viewport_size_matches(info, width, height),
            lambda info: (
                f"Expected viewport size not to be {int(width)}x{int(height)}; "
                f"got {_viewport_window_size(info)!r}; last={info!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_display_server(
        self,
        display_server: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda info: info.get("display_server") == display_server,
            lambda info: f"Expected display server {display_server!r}; got {info.get('display_server')!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_have_mouse_position(
        self,
        x: float,
        y: float,
        *,
        tolerance: float = 0.0,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda info: _viewport_position_matches(info, x, y, tolerance=tolerance),
            lambda info: (
                f"Expected mouse position ({x}, {y}) +/- {tolerance}; "
                f"got {_viewport_mouse_position(info)!r}; last={info!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_screenshot(
        self,
        path: str | Path,
        *,
        width: int | None = None,
        height: int | None = None,
        min_width: int | None = None,
        min_height: int | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.client.wait_for_screenshot(
            path,
            width=width,
            height=height,
            min_width=min_width,
            min_height=min_height,
            timeout=timeout,
            interval=interval,
        )

    def _wait_for(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any]], str],
        *,
        timeout: float,
        interval: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.client.viewport_info()
            if predicate(last):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last))
            time.sleep(interval)


class RuntimeSceneExpect:
    def __init__(self, client: GodotClient):
        self.client = client

    def to_have_path(
        self,
        path: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda scene: scene.get("scene_file_path") == path,
            lambda scene: f"Expected current scene path {path!r}; got {scene.get('scene_file_path')!r}",
            timeout=timeout,
            interval=interval,
        )

    def not_to_have_path(
        self,
        path: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda scene: scene.get("scene_file_path") != path,
            lambda scene: f"Expected current scene path not to be {path!r}; got {scene.get('scene_file_path')!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_have_name(
        self,
        name: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda scene: scene.get("name") == name,
            lambda scene: f"Expected current scene name {name!r}; got {scene.get('name')!r}",
            timeout=timeout,
            interval=interval,
        )

    def not_to_have_name(
        self,
        name: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda scene: scene.get("name") != name,
            lambda scene: f"Expected current scene name not to be {name!r}; got {scene.get('name')!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_match_info(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda scene: _dict_contains(scene, expected),
            lambda scene: f"Expected current scene info to include {expected!r}; last={scene!r}",
            timeout=timeout,
            interval=interval,
        )

    def _wait_for(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any]], str],
        *,
        timeout: float,
        interval: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.client.current_scene()
            if predicate(last):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last))
            time.sleep(interval)


class ProjectSceneExpect:
    def __init__(self, client: GodotClient, path: str):
        self.client = client
        self.path = path

    def to_be_listed(
        self,
        *,
        root_name: str | None = None,
        root_class: str | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        def match(state: dict[str, Any]) -> dict[str, Any] | None:
            entry = _project_scene_entry(state, self.path)
            if entry is None or not _project_scene_root_matches(entry, root_name=root_name, root_class=root_class):
                return None
            return entry

        return self._wait_for_scene_files(
            lambda state: match(state) is not None,
            lambda state, error: (
                f"Expected project scene {self.path!r} to be listed"
                f"{_project_scene_filter_summary(root_name=root_name, root_class=root_class)}; "
                f"scenes={state.get('scenes', [])!r} error={error!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda state: match(state) or {},
        )

    def to_have_root(
        self,
        *,
        name: str | None = None,
        class_name: str | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.to_be_listed(root_name=name, root_class=class_name, timeout=timeout, interval=interval)

    def to_have_no_missing_dependencies(
        self,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        def match(state: dict[str, Any]) -> dict[str, Any] | None:
            entry = _project_scene_entry(state, self.path)
            if entry is not None and bool(entry.get("ok")) and int(entry.get("missing_count", 0)) == 0:
                return entry
            return None

        return self._wait_for_scene_files(
            lambda state: match(state) is not None,
            lambda state, error: (
                f"Expected project scene {self.path!r} to have no missing dependencies; "
                f"scenes={state.get('scenes', [])!r} error={error!r}"
            ),
            timeout=timeout,
            interval=interval,
            include_dependencies=True,
            transform=lambda state: match(state) or {},
        )

    def to_have_node(
        self,
        *,
        name: str | None = None,
        class_name: str | None = None,
        path: str | None = None,
        script: str | None = None,
        instance_path: str | None = None,
        properties: dict[str, Any] | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        include_properties = script is not None or properties is not None

        return self._wait_for_scene_description(
            lambda state: _project_scene_described_node(
                state,
                name=name,
                class_name=class_name,
                path=path,
                script=script,
                instance_path=instance_path,
                properties=properties,
                groups=groups,
            )
            is not None,
            lambda state, error: (
                f"Expected project scene {self.path!r} node"
                f"{_project_scene_node_filter_summary(name=name, class_name=class_name, path=path, script=script, instance_path=instance_path, properties=properties, groups=groups)}; "
                f"nodes={state.get('nodes', [])!r} error={error!r}"
            ),
            timeout=timeout,
            interval=interval,
            include_properties=include_properties,
            transform=lambda state: _project_scene_described_node(
                state,
                name=name,
                class_name=class_name,
                path=path,
                script=script,
                instance_path=instance_path,
                properties=properties,
                groups=groups,
            )
            or {},
        )

    def to_have_connection(
        self,
        signal: str = "",
        *,
        from_node: str | None = None,
        to: str | None = None,
        method: str | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_scene_description(
            lambda state: _project_scene_connection(state, signal=signal, from_node=from_node, to=to, method=method)
            is not None,
            lambda state, error: (
                f"Expected project scene {self.path!r} connection"
                f"{_project_scene_connection_filter_summary(signal=signal, from_node=from_node, to=to, method=method)}; "
                f"connections={state.get('connections', [])!r} error={error!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda state: _project_scene_connection(
                state,
                signal=signal,
                from_node=from_node,
                to=to,
                method=method,
            )
            or {},
        )

    def _wait_for_scene_files(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any], BaseException | None], str],
        *,
        timeout: float,
        interval: float,
        include_dependencies: bool = True,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.client.scene_files(
                    self.path,
                    include_dependencies=include_dependencies,
                    max_results=1,
                )
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if predicate(last):
                    return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last, last_error))
            time.sleep(interval)

    def _wait_for_scene_description(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any], BaseException | None], str],
        *,
        timeout: float,
        interval: float,
        include_properties: bool = False,
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        last_error: BaseException | None = None
        while True:
            try:
                last = self.client.scene_file_describe(
                    self.path,
                    include_nodes=True,
                    include_properties=include_properties,
                    include_connections=True,
                    include_resources=True,
                    include_dependencies=True,
                )
                last_error = None
            except GodotPlaywrightError as exc:
                last_error = exc
            else:
                if predicate(last):
                    return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last, last_error))
            time.sleep(interval)


class EditorExpect:
    def __init__(self, client: GodotClient):
        self.client = client

    def to_be_available(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for(
            lambda status: bool(status.get("editor")),
            lambda status: f"Expected editor API to be available; last={status!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_be_editor(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self.to_be_available(timeout=timeout, interval=interval)

    def to_have_ui(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if not expected:
            raise ValueError("expected must not be empty")
        return self._wait_for(
            lambda status: _dict_contains(_editor_ui_status(status), expected),
            lambda status: f"Expected editor UI status to include {expected!r}; ui={_editor_ui_status(status)!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_have_base_control(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for(
            lambda status: _editor_ui_has_base_control(_editor_ui_status(status)),
            lambda status: f"Expected editor UI to expose a base control; ui={_editor_ui_status(status)!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_have_main_screen(
        self,
        name: str | None = None,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda status: _editor_ui_main_screen_matches(_editor_ui_status(status), name),
            lambda status: (
                f"Expected editor main screen {name!r}; "
                f"ui={_editor_ui_status(status)!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_bottom_panel_capability(
        self,
        *,
        can_make_visible: bool | None = None,
        can_hide: bool | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda status: _editor_ui_bottom_panel_capability_matches(
                _editor_ui_status(status),
                can_make_visible=can_make_visible,
                can_hide=can_hide,
            ),
            lambda status: (
                "Expected editor bottom panel capabilities "
                f"can_make_visible={can_make_visible!r} can_hide={can_hide!r}; "
                f"ui={_editor_ui_status(status)!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_undo(
        self,
        selector: str | dict[str, Any] | None = None,
        *,
        root: str | dict[str, Any] | None = None,
        history_id: int | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_history(
            lambda history: bool(history.get("can_undo")),
            lambda history: f"Expected editor history to have undo; last={history!r}",
            selector=selector,
            root=root,
            history_id=history_id,
            timeout=timeout,
            interval=interval,
        )

    def not_to_have_undo(
        self,
        selector: str | dict[str, Any] | None = None,
        *,
        root: str | dict[str, Any] | None = None,
        history_id: int | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_history(
            lambda history: not bool(history.get("can_undo")),
            lambda history: f"Expected editor history not to have undo; last={history!r}",
            selector=selector,
            root=root,
            history_id=history_id,
            timeout=timeout,
            interval=interval,
        )

    def to_have_redo(
        self,
        selector: str | dict[str, Any] | None = None,
        *,
        root: str | dict[str, Any] | None = None,
        history_id: int | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_history(
            lambda history: bool(history.get("can_redo")),
            lambda history: f"Expected editor history to have redo; last={history!r}",
            selector=selector,
            root=root,
            history_id=history_id,
            timeout=timeout,
            interval=interval,
        )

    def not_to_have_redo(
        self,
        selector: str | dict[str, Any] | None = None,
        *,
        root: str | dict[str, Any] | None = None,
        history_id: int | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_history(
            lambda history: not bool(history.get("can_redo")),
            lambda history: f"Expected editor history not to have redo; last={history!r}",
            selector=selector,
            root=root,
            history_id=history_id,
            timeout=timeout,
            interval=interval,
        )

    def to_match_history(
        self,
        expected: dict[str, Any],
        *,
        selector: str | dict[str, Any] | None = None,
        root: str | dict[str, Any] | None = None,
        history_id: int | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_history(
            lambda history: _dict_contains(history, expected),
            lambda history: f"Expected editor history to include {expected!r}; last={history!r}",
            selector=selector,
            root=root,
            history_id=history_id,
            timeout=timeout,
            interval=interval,
        )

    def to_have_open_scene(self, scene: str, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for(
            lambda status: _editor_open_scenes_include(status, scene),
            lambda status: f"Expected editor to have open scene {scene!r}; got {status.get('open_scenes', [])!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_have_open_scenes(
        self,
        scenes: list[str] | tuple[str, ...] | set[str],
        *,
        exact: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected = [str(scene) for scene in scenes]

        def matches(status: dict[str, Any]) -> bool:
            open_scenes = _editor_status_open_scenes(status)
            if exact and len(open_scenes) != len(expected):
                return False
            return all(_editor_scene_entries_include(open_scenes, scene) for scene in expected)

        return self._wait_for(
            matches,
            lambda status: f"Expected editor open scenes to include {expected!r}; got {status.get('open_scenes', [])!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_have_open_script(self, path: str, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for(
            lambda status: path in _editor_status_open_scripts(status),
            lambda status: (
                f"Expected editor to have open script {path!r}; "
                f"got {_editor_status_open_scripts(status)!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_current_script(self, path: str, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for(
            lambda status: _editor_status_current_script(status) == path,
            lambda status: (
                f"Expected editor current script {path!r}; "
                f"got {_editor_status_current_script(status)!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_edited_scene(self, scene: str, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for(
            lambda status: _editor_status_matches_edited_scene(status, scene),
            lambda status: (
                f"Expected edited scene {scene!r}; got path={status.get('edited_scene')!r} "
                f"name={status.get('edited_scene_name')!r} file={status.get('edited_scene_file_path')!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_edited_scene_name(self, name: str, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for(
            lambda status: _editor_value_matches(status.get("edited_scene_name", ""), name),
            lambda status: f"Expected edited scene name {name!r}, got {status.get('edited_scene_name')!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_have_edited_scene_file_path(
        self,
        path: str,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda status: _editor_value_matches(status.get("edited_scene_file_path", ""), path),
            lambda status: f"Expected edited scene file path {path!r}, got {status.get('edited_scene_file_path')!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_have_selection(
        self,
        expected: int | str | list[str] | tuple[str, ...] | set[str],
        *,
        exact: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if isinstance(expected, int) and not isinstance(expected, bool):
            return self.to_have_selection_count(expected, timeout=timeout, interval=interval)
        return self.to_have_selected_nodes(expected, exact=exact, timeout=timeout, interval=interval)

    def to_have_selection_count(self, count: int, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for(
            lambda status: _editor_selection_count(status) == count,
            lambda status: f"Expected editor selection count {count}, got {_editor_selection_count(status)}; last={status!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_have_selected_node(self, node: str, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self.to_have_selected_nodes(node, timeout=timeout, interval=interval)

    def to_have_selected_nodes(
        self,
        nodes: str | list[str] | tuple[str, ...] | set[str],
        *,
        exact: bool = False,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected = _editor_expected_strings(nodes)

        def matches(status: dict[str, Any]) -> bool:
            selected = _editor_selection_nodes(status)
            if exact and len(selected) != len(expected):
                return False
            return all(any(_editor_selection_node_matches(node, value) for node in selected) for value in expected)

        return self._wait_for(
            matches,
            lambda status: f"Expected selected nodes {expected!r}; got {_editor_selection_nodes(status)!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_be_playing(
        self,
        scene: str | None = None,
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        scene_detail = "" if scene is None else f" {scene!r}"
        return self._wait_for(
            lambda status: bool(status.get("playing")) and (
                scene is None or _editor_value_matches(status.get("playing_scene", ""), scene)
            ),
            lambda status: (
                f"Expected editor to be playing{scene_detail}; got playing={status.get('playing')!r} "
                f"scene={status.get('playing_scene')!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_playing_scene(self, scene: str, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self.to_be_playing(scene, timeout=timeout, interval=interval)

    def not_to_be_playing(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for(
            lambda status: not bool(status.get("playing")),
            lambda status: (
                f"Expected editor not to be playing; got playing={status.get('playing')!r} "
                f"scene={status.get('playing_scene')!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_not_be_playing(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self.not_to_be_playing(timeout=timeout, interval=interval)

    def to_be_stopped(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self.not_to_be_playing(timeout=timeout, interval=interval)

    def to_match_status(
        self,
        expected: dict[str, Any],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for(
            lambda status: all(status.get(key) == value for key, value in expected.items()),
            lambda status: f"Expected editor status to include {expected!r}; last={status!r}",
            timeout=timeout,
            interval=interval,
        )

    def _wait_for(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any]], str],
        *,
        timeout: float,
        interval: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.client.editor_status()
            if predicate(last):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last))
            time.sleep(interval)

    def _wait_for_history(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        message: Callable[[dict[str, Any]], str],
        *,
        selector: str | dict[str, Any] | None = None,
        root: str | dict[str, Any] | None = None,
        history_id: int | None = None,
        timeout: float,
        interval: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.client.editor_history(selector=selector, root=root, history_id=history_id)
            if predicate(last):
                return last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last))
            time.sleep(interval)


def expect(locator: Locator) -> Expect:
    return Expect(locator)


def expect_inspector(target: Inspector | InspectorProperty) -> InspectorExpect | InspectorPropertyExpect:
    if isinstance(target, InspectorProperty):
        return InspectorPropertyExpect(target)
    return InspectorExpect(target)


def expect_script(client: GodotClient, path: str) -> ScriptExpect:
    return ScriptExpect(client, path)


def expect_script_class(client: GodotClient, class_name: str) -> ScriptClassExpect:
    return ScriptClassExpect(client, class_name)


def expect_filesystem(client: GodotClient, path: str = "res://") -> FilesystemExpect:
    return FilesystemExpect(client, path)


def expect_resource(client: GodotClient, path: str) -> ResourceExpect:
    return ResourceExpect(client, path)


def expect_resource_class(client: GodotClient, class_name: str) -> ResourceClassExpect:
    return ResourceClassExpect(client, class_name)


def expect_node_class(client: GodotClient, class_name: str) -> NodeClassExpect:
    return NodeClassExpect(client, class_name)


def expect_trace(client: GodotClient) -> TraceExpect:
    return TraceExpect(client)


def expect_signal(
    client: GodotClient,
    selector: str | dict[str, Any] | None = None,
    signal: str | None = None,
    *,
    root: str | dict[str, Any] | None = None,
    watch_id: str | None = None,
    once: bool = False,
) -> SignalExpect:
    return SignalExpect(client, selector, signal, root=root, watch_id=watch_id, once=once)


def expect_log(client: GodotClient) -> LogExpect:
    return LogExpect(client)


def expect_physics2d(client: GodotClient) -> Physics2DExpect:
    return Physics2DExpect(client)


def expect_physics3d(client: GodotClient) -> Physics3DExpect:
    return Physics3DExpect(client)


def expect_audio(client: GodotClient) -> AudioExpect:
    return AudioExpect(client)


def expect_navigation(client: GodotClient) -> NavigationExpect:
    return NavigationExpect(client)


def expect_project(client: GodotClient) -> ProjectExpect:
    return ProjectExpect(client)


def expect_engine(client: GodotClient) -> EngineExpect:
    return EngineExpect(client)


def expect_viewport(client: GodotClient) -> ViewportExpect:
    return ViewportExpect(client)


def expect_runtime_scene(client: GodotClient) -> RuntimeSceneExpect:
    return RuntimeSceneExpect(client)


def expect_project_scene(client: GodotClient, path: str) -> ProjectSceneExpect:
    return ProjectSceneExpect(client, path)


def expect_editor(client: GodotClient) -> EditorExpect:
    return EditorExpect(client)


def _viewport_window_size(info: dict[str, Any]) -> dict[str, Any]:
    window_size = info.get("window_size", {})
    return window_size if isinstance(window_size, dict) else {}


def _viewport_visible_rect(info: dict[str, Any]) -> dict[str, float] | None:
    visible_rect = info.get("visible_rect")
    if isinstance(visible_rect, dict):
        try:
            return {
                "x": float(visible_rect.get("x")),
                "y": float(visible_rect.get("y")),
                "width": float(visible_rect.get("width")),
                "height": float(visible_rect.get("height")),
            }
        except (TypeError, ValueError):
            return None
    window_size = _viewport_window_size(info)
    try:
        return {
            "x": 0.0,
            "y": 0.0,
            "width": float(window_size.get("width")),
            "height": float(window_size.get("height")),
        }
    except (TypeError, ValueError):
        return None


def _viewport_mouse_position(info: dict[str, Any]) -> dict[str, Any]:
    mouse_position = info.get("mouse_position", {})
    return mouse_position if isinstance(mouse_position, dict) else {}


def _viewport_size_matches(info: dict[str, Any], width: int, height: int) -> bool:
    window_size = _viewport_window_size(info)
    return window_size.get("width") == int(width) and window_size.get("height") == int(height)


def _viewport_position_matches(
    info: dict[str, Any],
    x: float,
    y: float,
    *,
    tolerance: float = 0.0,
) -> bool:
    mouse_position = _viewport_mouse_position(info)
    try:
        actual_x = float(mouse_position.get("x"))
        actual_y = float(mouse_position.get("y"))
    except (TypeError, ValueError):
        return False
    return abs(actual_x - float(x)) <= tolerance and abs(actual_y - float(y)) <= tolerance


def _screenshot_result_matches(
    result: dict[str, Any],
    *,
    width: int | None = None,
    height: int | None = None,
    min_width: int | None = None,
    min_height: int | None = None,
    require_file: bool = False,
) -> bool:
    try:
        actual_width = int(result.get("width"))
        actual_height = int(result.get("height"))
    except (TypeError, ValueError):
        return False
    if width is not None and actual_width != int(width):
        return False
    if height is not None and actual_height != int(height):
        return False
    if min_width is not None and actual_width < int(min_width):
        return False
    if min_height is not None and actual_height < int(min_height):
        return False
    if require_file:
        local_path = _screenshot_local_path(result)
        if local_path is not None and not local_path.is_file():
            return False
    return True


def _screenshot_local_path(result: dict[str, Any]) -> Path | None:
    path_value = result.get("global_path") or result.get("path")
    if not path_value:
        return None
    path_text = str(path_value)
    if "://" in path_text and not Path(path_text).is_absolute():
        return None
    return Path(path_text)


def _frame_sample_sequence(value: list[str | dict[str, Any]] | str | dict[str, Any] | None) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, dict)):
        return [value]
    return list(value)


def _frame_sample_expressions(value: list[str | dict[str, Any]] | dict[str, Any] | str | None) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        if "expression" in value:
            return [value]
        return [{"name": str(name), "expression": expression} for name, expression in value.items()]
    return list(value)


def _editor_filesystem_entry_matches(
    entry: dict[str, Any],
    *,
    resource_type: str | None = None,
    kind: str | None = None,
    is_file: bool | None = None,
    is_directory: bool | None = None,
    selected: bool | None = None,
) -> bool:
    if not bool(entry.get("exists")):
        return False
    if resource_type is not None and entry.get("resource_type") != resource_type:
        return False
    if kind is not None and entry.get("kind") != kind:
        return False
    if is_file is not None and bool(entry.get("is_file")) != is_file:
        return False
    if is_directory is not None and bool(entry.get("is_directory")) != is_directory:
        return False
    if selected is not None and bool(entry.get("selected")) != selected:
        return False
    return True


def _editor_filesystem_find_count(result: dict[str, Any]) -> int:
    try:
        return int(result.get("count", len(result.get("entries", []))))
    except (TypeError, ValueError):
        entries = result.get("entries", [])
        return len(entries) if isinstance(entries, list) else 0


def _editor_filesystem_filter_summary(
    *,
    resource_type: str | None = None,
    kind: str | None = None,
    is_file: bool | None = None,
    is_directory: bool | None = None,
    selected: bool | None = None,
) -> str:
    filters: list[str] = []
    if resource_type is not None:
        filters.append(f"resource_type={resource_type!r}")
    if kind is not None:
        filters.append(f"kind={kind!r}")
    if is_file is not None:
        filters.append(f"is_file={is_file!r}")
    if is_directory is not None:
        filters.append(f"is_directory={is_directory!r}")
    if selected is not None:
        filters.append(f"selected={selected!r}")
    return "" if not filters else " with " + ", ".join(filters)


def _fs_path_matches(entry: dict[str, Any], *, state: str = "exists", path_type: str | None = None) -> bool:
    exists = bool(entry.get("exists"))
    if state == "missing":
        return not exists
    if not exists:
        return False
    if path_type in {None, "any"}:
        return True
    return entry.get("type") == path_type


def _res_parent_path(path: str) -> str:
    if not path.startswith("res://"):
        return ""
    tail = path.removeprefix("res://").strip("/")
    if not tail or "/" not in tail:
        return "res://"
    return "res://" + tail.rsplit("/", 1)[0]


def _engine_version_info(info: dict[str, Any]) -> dict[str, Any]:
    godot = info.get("godot", {})
    return godot if isinstance(godot, dict) else {}


def _engine_version_matches(
    info: dict[str, Any],
    *,
    major: int | None = None,
    minor: int | None = None,
    patch: int | None = None,
    status: str | None = None,
    string_contains: str | None = None,
) -> bool:
    version = _engine_version_info(info)
    if not version:
        return False
    if major is not None and int(version.get("major", -1)) != int(major):
        return False
    if minor is not None and int(version.get("minor", -1)) != int(minor):
        return False
    if patch is not None and int(version.get("patch", -1)) != int(patch):
        return False
    if status is not None and str(version.get("status", "")) != status:
        return False
    if string_contains is not None and string_contains not in str(version.get("string", "")):
        return False
    return True


def _engine_version_filter_summary(
    *,
    major: int | None = None,
    minor: int | None = None,
    patch: int | None = None,
    status: str | None = None,
    string_contains: str | None = None,
) -> str:
    filters = []
    if major is not None:
        filters.append(f"major={major!r}")
    if minor is not None:
        filters.append(f"minor={minor!r}")
    if patch is not None:
        filters.append(f"patch={patch!r}")
    if status is not None:
        filters.append(f"status={status!r}")
    if string_contains is not None:
        filters.append(f"string_contains={string_contains!r}")
    return "" if not filters else " with " + ", ".join(filters)


def _engine_project_path_matches(info: dict[str, Any], expected: str, *, exact: bool = False) -> bool:
    project_path = str(info.get("project_path", ""))
    expected_text = str(expected)
    return project_path == expected_text if exact else expected_text in project_path


def _script_function_entries(description: dict[str, Any]) -> list[dict[str, Any]]:
    functions = list(description.get("methods", []))
    symbols = description.get("symbols", {})
    if isinstance(symbols, dict):
        functions.extend(list(symbols.get("functions", [])))
    return [function for function in functions if isinstance(function, dict)]


def _script_symbol_entries(description: dict[str, Any], name: str) -> list[dict[str, Any]]:
    entries = list(description.get(name, []))
    symbols = description.get("symbols", {})
    if isinstance(symbols, dict):
        entries.extend(list(symbols.get(name, [])))
    return [entry for entry in entries if isinstance(entry, dict)]


def _script_function_names(description: dict[str, Any]) -> set[str]:
    return {str(function.get("name", "")) for function in _script_function_entries(description)}


def _script_extends(description: dict[str, Any]) -> str:
    symbols = description.get("symbols", {})
    if isinstance(symbols, dict):
        return str(symbols.get("extends", ""))
    return ""


def _string_list(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _trace_event_matches(
    event: dict[str, Any],
    *,
    event_type: str | None = None,
    data: dict[str, Any] | None = None,
) -> bool:
    if event_type is not None and event.get("type") != event_type:
        return False
    if data is None:
        return True
    event_data = event.get("data", {})
    return isinstance(event_data, dict) and _dict_contains(event_data, data)


def _signal_event_matches(
    event: dict[str, Any],
    *,
    signal: str | None = None,
    path: str | None = None,
    fields: dict[str, Any] | None = None,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> bool:
    if signal is not None and event.get("signal") != signal:
        return False
    if path is not None and not _signal_event_path_matches(event.get("path", ""), path):
        return False
    if fields is not None and not _dict_contains(event, fields):
        return False
    return predicate is None or predicate(event)


def _signal_event_path_matches(candidate: Any, expected: str) -> bool:
    candidate_text = str(candidate)
    expected_text = str(expected)
    if candidate_text == expected_text:
        return True
    expected_name = expected_text.rsplit("/", 1)[-1].lstrip("#")
    candidate_name = candidate_text.rsplit("/", 1)[-1].lstrip("#")
    return bool(expected_name) and candidate_name == expected_name


def _dict_contains(value: dict[str, Any], expected: dict[str, Any]) -> bool:
    for key, expected_value in expected.items():
        if key not in value:
            return False
        actual_value = value[key]
        if isinstance(actual_value, dict) and isinstance(expected_value, dict):
            if not _dict_contains(actual_value, expected_value):
                return False
        elif actual_value != expected_value:
            return False
    return True


def _trace_event_sequence(events: list[dict[str, Any]], expected: list[str]) -> list[dict[str, Any]] | None:
    matched: list[dict[str, Any]] = []
    index = 0
    for event in events:
        if index >= len(expected):
            break
        if event.get("type") == expected[index]:
            matched.append(event)
            index += 1
    return matched if index == len(expected) else None


def _signal_event_sequence(
    events: list[dict[str, Any]],
    expected: list[str | dict[str, Any]],
) -> list[dict[str, Any]] | None:
    matched: list[dict[str, Any]] = []
    index = 0
    for event in events:
        if index >= len(expected):
            break
        if _signal_event_expectation_matches(event, expected[index]):
            matched.append(event)
            index += 1
    return matched if index == len(expected) else None


def _signal_event_expectation_matches(event: dict[str, Any], expected: str | dict[str, Any]) -> bool:
    if isinstance(expected, str):
        return _signal_event_matches(event, signal=expected)
    signal = expected.get("signal")
    path = expected.get("path")
    fields = expected.get("fields")
    predicate = expected.get("predicate")
    if fields is None:
        fields = {
            key: value
            for key, value in expected.items()
            if key not in {"signal", "path", "fields", "predicate"}
        }
        if not fields:
            fields = None
    if fields is not None and not isinstance(fields, dict):
        raise TypeError("signal event sequence fields must be a dict")
    if predicate is not None and not callable(predicate):
        raise TypeError("signal event sequence predicate must be callable")
    return _signal_event_matches(
        event,
        signal=str(signal) if signal is not None else None,
        path=str(path) if path is not None else None,
        fields=fields,
        predicate=predicate,
    )


def _editor_open_scenes_include(status: dict[str, Any], expected: str) -> bool:
    return _editor_scene_entries_include(_editor_status_open_scenes(status), expected)


def _editor_status_open_scenes(status: dict[str, Any]) -> list[Any]:
    open_scenes = status.get("open_scenes", [])
    if isinstance(open_scenes, str):
        return [open_scenes]
    return list(open_scenes) if isinstance(open_scenes, (list, tuple, set)) else []


def _editor_status_open_scripts(status: dict[str, Any]) -> list[str]:
    script_editor = status.get("script_editor", {})
    if not isinstance(script_editor, dict):
        return []
    open_paths = script_editor.get("open_paths", [])
    if isinstance(open_paths, str):
        return [open_paths]
    return [str(path) for path in open_paths] if isinstance(open_paths, (list, tuple, set)) else []


def _editor_status_current_script(status: dict[str, Any]) -> str:
    script_editor = status.get("script_editor", {})
    if not isinstance(script_editor, dict):
        return ""
    return str(script_editor.get("current_path", "") or "")


def _editor_ui_status(status: dict[str, Any]) -> dict[str, Any]:
    ui = status.get("ui", status)
    return ui if isinstance(ui, dict) else {}


def _editor_ui_has_base_control(ui: dict[str, Any]) -> bool:
    base_control = ui.get("base_control", {})
    return bool(ui.get("has_base_control")) or bool(base_control if isinstance(base_control, dict) else {})


def _editor_ui_main_screen_matches(ui: dict[str, Any], expected: str | None) -> bool:
    if expected is None:
        main_screen = ui.get("main_screen", {})
        return bool(ui.get("main_screen_name") or ui.get("main_screen_path") or (main_screen if isinstance(main_screen, dict) else {}))
    candidates = [ui.get("main_screen_name"), ui.get("main_screen_api_name"), ui.get("main_screen_path")]
    main_screen = ui.get("main_screen", {})
    if isinstance(main_screen, dict):
        candidates.extend([main_screen.get("name"), main_screen.get("api_name"), main_screen.get("path"), main_screen.get("class")])
    main_screens = ui.get("main_screens", [])
    if isinstance(main_screens, (list, tuple, set)):
        for entry in main_screens:
            if isinstance(entry, dict):
                candidates.extend([entry.get("name"), entry.get("api_name"), entry.get("path"), entry.get("class")])
            else:
                candidates.append(entry)
    return any(_editor_value_matches(candidate, expected) for candidate in candidates)


def _editor_ui_bottom_panel_capability_matches(
    ui: dict[str, Any],
    *,
    can_make_visible: bool | None,
    can_hide: bool | None,
) -> bool:
    bottom_panel = ui.get("bottom_panel", {})
    if not isinstance(bottom_panel, dict):
        return False
    if can_make_visible is not None and bool(bottom_panel.get("can_make_visible")) != can_make_visible:
        return False
    if can_hide is not None and bool(bottom_panel.get("can_hide")) != can_hide:
        return False
    return True


def _editor_scene_entries_include(entries: list[Any], expected: str) -> bool:
    return any(_editor_scene_entry_matches(entry, expected) for entry in entries)


def _editor_scene_entry_matches(entry: Any, expected: str) -> bool:
    if isinstance(entry, dict):
        candidates = [
            entry.get("path"),
            entry.get("scene_file_path"),
            entry.get("file_path"),
            entry.get("name"),
        ]
    else:
        candidates = [entry]
    return any(_editor_value_matches(candidate, expected) for candidate in candidates)


def _editor_status_matches_edited_scene(status: dict[str, Any], expected: str) -> bool:
    candidates = [
        status.get("edited_scene"),
        status.get("edited_scene_name"),
        status.get("edited_scene_file_path"),
    ]
    return any(_editor_value_matches(candidate, expected) for candidate in candidates)


def _editor_history_readback_expected(result: dict[str, Any]) -> dict[str, Any]:
    expected: dict[str, Any] = {}
    for key in ("available", "can_undo", "can_redo", "history_id"):
        if key in result:
            expected[key] = result[key]
    version = result.get("version")
    if isinstance(version, int) and version >= 0:
        expected["version"] = version
    return expected or {"available": True}


def _editor_selection(status: dict[str, Any]) -> dict[str, Any]:
    if "nodes" in status or "count" in status:
        return status
    selection = status.get("selection", {})
    return selection if isinstance(selection, dict) else {}


def _editor_selection_nodes(status: dict[str, Any]) -> list[Any]:
    nodes = _editor_selection(status).get("nodes", [])
    return list(nodes) if isinstance(nodes, list) else []


def _editor_selection_count(status: dict[str, Any]) -> int:
    selection = _editor_selection(status)
    count = selection.get("count")
    if isinstance(count, int):
        return count
    return len(_editor_selection_nodes(status))


def _editor_expected_strings(values: str | list[str] | tuple[str, ...] | set[str]) -> list[str]:
    if isinstance(values, str):
        return [values]
    return [str(value) for value in values]


def _editor_selection_expected_from_selector(
    selector: str | dict[str, Any] | list[str | dict[str, Any]],
) -> str | list[str]:
    if isinstance(selector, list):
        return [_editor_selection_selector_label(item) for item in selector]
    return _editor_selection_selector_label(selector)


def _editor_selection_selector_label(selector: str | dict[str, Any]) -> str:
    if isinstance(selector, dict):
        for key in ("path", "name", "test_id", "testid"):
            value = selector.get(key)
            if value:
                return str(value)
        metadata = selector.get("metadata", selector.get("meta", {}))
        if isinstance(metadata, dict):
            for key in ("test_id", "name"):
                value = metadata.get(key)
                if value:
                    return str(value)
    return str(selector)


def _editor_selection_matches(
    selection: dict[str, Any],
    expected: int | str | list[str] | tuple[str, ...] | set[str],
    *,
    exact: bool = False,
) -> bool:
    if isinstance(expected, int) and not isinstance(expected, bool):
        return _editor_selection_count(selection) == expected
    expected_values = _editor_expected_strings(expected)
    selected = _editor_selection_nodes(selection)
    if exact and len(selected) != len(expected_values):
        return False
    return all(any(_editor_selection_node_matches(node, value) for node in selected) for value in expected_values)


def _editor_selection_expectation_summary(
    expected: int | str | list[str] | tuple[str, ...] | set[str],
    *,
    exact: bool,
) -> str:
    if isinstance(expected, int) and not isinstance(expected, bool):
        return f"count {expected}"
    mode = "exactly " if exact else ""
    return f"{mode}nodes {_editor_expected_strings(expected)!r}"


def _editor_selection_node_matches(node: Any, expected: str) -> bool:
    if isinstance(node, dict):
        candidates = [
            node.get("name"),
            node.get("path"),
            node.get("scene_file_path"),
            node.get("owner"),
        ]
    else:
        candidates = [node]
    return any(_editor_value_matches(candidate, expected) for candidate in candidates)


def _editor_value_matches(candidate: Any, expected: str) -> bool:
    if candidate is None:
        return False
    candidate_text = str(candidate)
    expected_text = str(expected)
    if candidate_text == expected_text:
        return True
    if expected_text.startswith("#") and candidate_text == expected_text[1:]:
        return True
    if candidate_text.startswith("#") and candidate_text[1:] == expected_text:
        return True
    return False


def find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])
