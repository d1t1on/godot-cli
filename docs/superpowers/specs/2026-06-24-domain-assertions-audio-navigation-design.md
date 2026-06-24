# Domain-Specific Assertions: Audio + Navigation (Batch 1)

Date: 2026-06-24

## Objective

Add domain-specific assertion fixtures for Audio and Navigation to the Godot
Playwright test runner. These are the first batch of a multi-batch effort to
expand domain assertion coverage (subsequent batches: Animation/Material,
Physics extensions).

## Background

The project's completion audit marks the "Assertions" capability area as Done,
with `expect`, `expect_physics2d`, `expect_physics3d`, `expect_editor`,
`expect_inspector`, `expect_scene`, `expect_runtime_scene`, `expect_project`,
`expect_resource`, `expect_viewport`, `expect_log`, `expect_trace`,
`expect_signal`, `expect_engine`, `expect_script`, `expect_filesystem`, and
related fixtures already implemented.

However, Audio and Navigation have **zero coverage** today. Nearly every game
uses audio (bus routing, playback state, volume control) and most 3D/2D games
use navigation (pathfinding, agent target reaching, region availability).
Adding these assertions directly serves the most common agent activity: writing
tests that assert game behavior.

## Architecture: Hybrid Strategy

The design uses a hybrid strategy — only add new RPCs where server-side
computation is necessary; reuse existing `node.state` / `evaluate` /
`wait_for_function` mechanisms for node-scoped state that Expression can access
cleanly. This mirrors the existing `expect_physics2d` / `expect_physics3d`
pattern, which combines `physics2d_ray` / `physics3d_ray` RPCs with
`node.state` reads.

### New RPCs (2 only)

1. **`audio.bus.info`** — reads AudioServer bus state. AudioServer is a global
   engine singleton; while technically accessible via `Expression`, the access
   path is deep (`AudioServer.get_bus_volume_db(idx)` etc.) and error messages
   from failed Expression evaluations are unstructured strings. A dedicated RPC
   returns a structured, JSON-compatible bus snapshot.

2. **`navigation.query_path`** — performs an A* reachability query through
   NavigationServer. This requires server-side `NavigationServer3D.query_path()`
   / `NavigationServer2D.query_path()` calls that cannot be reliably executed
   from a client-side `Expression` string.

### Reused Existing Mechanisms

All node-scoped assertions (AudioStreamPlayer playback state, NavigationAgent
target distance, NavigationRegion mesh availability) use the existing
`locator(selector).evaluate('node.get("...")')` and `wait_for_function` polling
patterns. No new RPC is needed for these.

## Component Design

### RPC: `audio.bus.info`

**Addon dispatch** (`addons/godot_playwright/godot_playwright_server.gd`):

```
func _rpc_audio_bus_info(params: Dictionary) -> Dictionary:
    # Resolve bus index from bus_name (optional) or bus_index (optional, default 0=Master)
    # Read via AudioServer: get_bus_count, get_bus_index, get_bus_name,
    #   get_bus_volume_db, is_bus_mute, is_bus_solo, get_bus_effect_count,
    #   get_bus_effect, is_bus_effect_enabled
    # Build children list by scanning all buses for send_target == this bus name
    # _record_event("audio.bus.info", {"bus_name": name, "bus_index": idx})
    # Return _ok({"bus": {...}})
```

**Parameters**:
- `bus_name` (String, optional) — resolve by name; takes precedence over `bus_index`
- `bus_index` (int, optional, default 0) — Master bus

**Return shape**:
```json
{
  "ok": true,
  "bus": {
    "index": 0,
    "name": "Master",
    "volume_db": 0.0,
    "muted": false,
    "solo": false,
    "effect_count": 0,
    "effects": [
      {"index": 0, "class": "AudioEffectReverb", "enabled": true, "resource_name": ""}
    ],
    "send_target": "",
    "children": [
      {"index": 1, "name": "Music"},
      {"index": 2, "name": "SFX"}
    ]
  }
}
```

**Validation**: unknown bus name → `{"ok": false, "errors": ["Unknown bus name: ..."]}`.
Invalid bus index (>= count or < 0) → `{"ok": false, "errors": ["Invalid bus index: ..."]}`.

### RPC: `navigation.query_path`

**Addon dispatch** (`addons/godot_playwright/godot_playwright_server.gd`):

```
func _rpc_navigation_query_path(params: Dictionary) -> Dictionary:
    # Parse start/target positions (2D: x,y; 3D: x,y,z)
    # dimension: int = params.get("dimension", 3)
    # navigation_layers: int = params.get("navigation_layers", -1) (-1 = all)
    # For 3D: NavigationServer3D.map_get_closest_point + query_path
    # For 2D: NavigationServer2D equivalents
    # Build path points array, compute path_length (sum of segment distances)
    # _record_event("navigation.query_path", {...})
    # Return _ok({"path": {"reachable": bool, "points": [...], ...}})
```

**Parameters**:
- `start_x`, `start_y`, `start_z` (float) — start position (z ignored for 2D)
- `target_x`, `target_y`, `target_z` (float) — target position (z ignored for 2D)
- `dimension` (int, default 3) — 2 or 3
- `navigation_layers` (int, optional, default -1 = all layers)
- `map_rid` (String, optional) — reserved for future explicit map selection; defaults to primary map

**Return shape**:
```json
{
  "ok": true,
  "path": {
    "reachable": true,
    "points": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
    "point_count": 3,
    "path_length": 2.0,
    "start": [0.0, 0.0, 0.0],
    "target": [2.0, 0.0, 0.0],
    "dimension": 3
  }
}
```

**Edge cases**: no navigation map loaded → `reachable=false`, `points=[]`,
`path_length=0.0`. Start/target outside navigable area → snapped to closest
point on navmesh; `reachable` reflects whether a path exists after snapping.

### Python Client (`godot_playwright/client.py`)

**New methods on `GodotClient`**:
```python
def audio_bus_info(
    self, *, bus_name: str | None = None, bus_index: int | None = None
) -> dict[str, Any]:
    """Query AudioServer bus state via audio.bus.info RPC."""

def navigation_query_path(
    self,
    start: tuple[float, ...] | list[float],
    target: tuple[float, ...] | list[float],
    *,
    dimension: int = 3,
    navigation_layers: int | None = None,
) -> dict[str, Any]:
    """Query navigation path reachability via navigation.query_path RPC."""
```

**New wait helpers** (polling variants):
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
    """Poll audio.bus.info until specified fields match."""

def wait_for_navigation_path(
    self,
    start: tuple[float, ...] | list[float],
    target: tuple[float, ...] | list[float],
    *,
    dimension: int = 3,
    reachable: bool | None = None,
    path_length: float | None = None,
    timeout: float = 5.0,
    interval: float = 0.05,
) -> dict[str, Any]:
    """Poll navigation.query_path until specified conditions match."""
```

### Expectation Classes (`godot_playwright/client.py`)

**`AudioExpect`**:

Bus assertions (use `audio.bus.info` RPC):
```python
class AudioExpect:
    def __init__(self, client: GodotClient): ...

    def to_have_bus_volume(
        self, bus: str, volume_db: float, *, tolerance: float = 0.1, timeout: float = 5.0
    ) -> dict[str, Any]: ...

    def to_have_bus_muted(self, bus: str, *, timeout: float = 5.0) -> dict[str, Any]: ...

    def not_to_have_bus_muted(self, bus: str, *, timeout: float = 5.0) -> dict[str, Any]: ...

    def to_have_bus_solo(self, bus: str, *, timeout: float = 5.0) -> dict[str, Any]: ...

    def to_have_bus_effect(
        self, bus: str, effect_class: str, *, enabled: bool | None = None, timeout: float = 5.0
    ) -> dict[str, Any]: ...

    def to_have_bus(
        self, bus: str, *, timeout: float = 5.0
    ) -> dict[str, Any]:
        """Assert a named bus exists on the AudioServer."""
```

Player node assertions (use existing `locator().evaluate()` polling):
```python
    def to_be_playing(self, selector: str | dict, *, timeout: float = 5.0) -> dict[str, Any]: ...

    def not_to_be_playing(self, selector: str | dict, *, timeout: float = 5.0) -> dict[str, Any]: ...

    def to_have_stream(
        self, selector: str | dict, stream_path: str, *, timeout: float = 5.0
    ) -> dict[str, Any]: ...

    def to_have_pitch(
        self, selector: str | dict, pitch: float, *, tolerance: float = 0.01, timeout: float = 5.0
    ) -> dict[str, Any]: ...

    def to_have_volume_db(
        self, selector: str | dict, volume_db: float, *, tolerance: float = 0.1, timeout: float = 5.0
    ) -> dict[str, Any]: ...
```

Player assertions resolve `selector` to a `Locator`, then poll
`locator.evaluate('node.get("playing")')`, `node.get("stream").resource_path`,
`node.get("pitch_scale")`, `node.get("volume_db")` respectively. On timeout,
error messages include the last observed value (same pattern as
`Physics2DExpect.to_have_point_collision`).

**`NavigationExpect`**:

Path assertions (use `navigation.query_path` RPC):
```python
class NavigationExpect:
    def __init__(self, client: GodotClient): ...

    def to_be_reachable(
        self,
        start: tuple[float, ...] | list[float],
        target: tuple[float, ...] | list[float],
        *,
        dimension: int = 3,
        navigation_layers: int | None = None,
        timeout: float = 5.0,
    ) -> dict[str, Any]: ...

    def not_to_be_reachable(
        self,
        start: tuple[float, ...] | list[float],
        target: tuple[float, ...] | list[float],
        *,
        dimension: int = 3,
        navigation_layers: int | None = None,
        timeout: float = 5.0,
    ) -> dict[str, Any]: ...

    def to_have_path_length(
        self,
        start: tuple[float, ...] | list[float],
        target: tuple[float, ...] | list[float],
        length: float,
        *,
        tolerance: float = 0.1,
        dimension: int = 3,
        timeout: float = 5.0,
    ) -> dict[str, Any]: ...

    def to_have_path_point_count(
        self,
        start: tuple[float, ...] | list[float],
        target: tuple[float, ...] | list[float],
        count: int,
        *,
        dimension: int = 3,
        timeout: float = 5.0,
    ) -> dict[str, Any]: ...
```

Agent/region node assertions (use existing `locator().evaluate()` polling):
```python
    def to_have_target_reached(
        self, selector: str | dict, *, timeout: float = 5.0
    ) -> dict[str, Any]: ...

    def to_have_target_distance(
        self, selector: str | dict, distance: float, *, tolerance: float = 0.1, timeout: float = 5.0
    ) -> dict[str, Any]: ...

    def to_have_pathway_point_count(
        self, selector: str | dict, count: int, *, timeout: float = 5.0
    ) -> dict[str, Any]: ...

    def to_have_navigation_mesh(
        self, selector: str | dict, *, timeout: float = 5.0
    ) -> dict[str, Any]: ...

    def to_have_region_enabled(
        self, selector: str | dict, *, timeout: float = 5.0
    ) -> dict[str, Any]: ...
```

Agent assertions poll `node.get("target_reached")` /
`node.get("is_navigation_finished")`, `node.get("distance_to_target")`,
`node.get("pathway_points").size()`. Region assertions poll
`node.get("navigation_mesh") != null` and `node.get("enabled")`.

### Factory Functions

```python
def expect_audio(client: GodotClient) -> AudioExpect:
    return AudioExpect(client)

def expect_navigation(client: GodotClient) -> NavigationExpect:
    return NavigationExpect(client)
```

### Runner Registration (`godot_playwright/runner.py`)

Add to the fixture registry dictionary:
```python
"expect_audio": expect_audio(godot),
"expect_navigation": expect_navigation(godot),
```

### Codegen (`godot_playwright/codegen.py`)

Add replay mappings for the 2 new trace event types:
- `audio.bus.info` → `godot.audio_bus_info(bus_name=..., bus_index=...)`
- `navigation.query_path` → `godot.navigation_query_path(start=..., target=..., dimension=...)`

### Exports (`godot_playwright/__init__.py`)

Export `expect_audio` and `expect_navigation` if the existing module exports
expectation factory functions at package level.

## Testing

### Unit Tests (`tests/test_client.py`)

Fake server coverage for:
- `audio_bus_info` success (structured bus snapshot), unknown bus name error,
  invalid bus index error
- `navigation_query_path` reachable, unreachable, 2D vs 3D, empty path
- `wait_for_audio_bus` success/timeout paths
- `wait_for_navigation_path` success/timeout paths
- `AudioExpect.to_have_bus_volume` match/mismatch/timeout
- `AudioExpect.to_have_bus_muted` / `not_to_have_bus_muted`
- `AudioExpect.to_have_bus_effect` with and without `enabled` filter
- `AudioExpect.to_be_playing` / `not_to_be_playing` (fake node state)
- `AudioExpect.to_have_stream` / `to_have_pitch` / `to_have_volume_db`
- `NavigationExpect.to_be_reachable` / `not_to_be_reachable`
- `NavigationExpect.to_have_path_length` / `to_have_path_point_count`
- `NavigationExpect.to_have_target_reached` / `to_have_target_distance`
- `NavigationExpect.to_have_navigation_mesh` / `to_have_region_enabled`

### Codegen Tests (`tests/test_codegen.py`)

Verify `audio.bus.info` and `navigation.query_path` trace events replay as
helper calls. Extend the existing codegen coverage test so new trace events
must either be replayable or explicitly classified.

### Live Integration Tests (`tests/test_godot_integration.py`)

Add a test class `DomainAssertionsIntegrationTests` (guarded by
`@unittest.skipUnless(shutil.which("godot"), ...)`) that:

1. Creates a temp project with an AudioStreamPlayer + custom bus "TestBus"
   child of Master.
2. Launches Godot, plays the stream, asserts `expect_audio.to_be_playing`,
   mutes the bus via `godot.evaluate('AudioServer.set_bus_mute(...)')`,
   asserts `expect_audio.to_have_bus_muted`.
3. Creates a NavigationRegion3D with a simple navmesh, a NavigationAgent3D,
   queries path reachability via `expect_navigation.to_be_reachable`, asserts
   agent target distance via `expect_navigation.to_have_target_distance`.

### Runner Fixture Tests (`tests/test_runner.py`)

Verify `expect_audio` and `expect_navigation` are registered in the fixture
registry and resolve to `AudioExpect` / `NavigationExpect` instances.

## Documentation

### `README.md`

Add to the Python API / fixtures section:

```python
def test_audio(godot, expect_audio):
    player = godot.locator("#BgmPlayer")
    player.call("play")
    expect_audio.to_be_playing("#BgmPlayer")
    expect_audio.to_have_bus_volume("Master", 0.0, tolerance=0.1)
    expect_audio.to_have_bus_muted("Music", timeout=1.0)

def test_navigation(godot, expect_navigation):
    expect_navigation.to_be_reachable(start=(0, 0, 0), target=(10, 0, 0))
    expect_navigation.to_have_path_length(start=(0, 0, 0), target=(10, 0, 0), length=10.0, tolerance=0.5)
    agent = godot.locator("#NavAgent")
    expect_navigation.to_have_target_reached("#NavAgent", timeout=5.0)
    expect_navigation.to_have_target_distance("#NavAgent", 0.0, tolerance=0.1)
```

### `docs/protocol.md`

Document `audio.bus.info` and `navigation.query_path` RPC methods: parameters,
return shapes, error cases, and example invocations.

## File Touch List

| File | Change |
| --- | --- |
| `addons/godot_playwright/godot_playwright_server.gd` | Add `_rpc_audio_bus_info` + `_rpc_navigation_query_path` + dispatch entries + `_record_event` calls |
| `godot_playwright/client.py` | Add `audio_bus_info` + `navigation_query_path` + `wait_for_audio_bus` + `wait_for_navigation_path` + `AudioExpect` + `NavigationExpect` classes + `expect_audio` / `expect_navigation` factory functions |
| `godot_playwright/runner.py` | Register `expect_audio` + `expect_navigation` in fixture registry |
| `godot_playwright/codegen.py` | Add replay mappings for `audio.bus.info` + `navigation.query_path` |
| `godot_playwright/__init__.py` | Export `expect_audio` + `expect_navigation` (if pattern matches existing exports) |
| `tests/test_client.py` | Fake server + expectation unit tests |
| `tests/test_codegen.py` | Codegen replay coverage for 2 new events |
| `tests/test_godot_integration.py` | Live Audio + Navigation integration tests |
| `tests/test_runner.py` | Fixture registration verification |
| `README.md` | Audio + Navigation assertion examples and API docs |
| `docs/protocol.md` | `audio.bus.info` + `navigation.query_path` documentation |

## Verification Criteria

1. `godot --headless --check-only --script addons/godot_playwright/godot_playwright_server.gd` passes.
2. `.venv/bin/python -m py_compile godot_playwright/*.py tests/test_client.py tests/test_codegen.py tests/test_godot_integration.py tests/test_runner.py` passes.
3. `.venv/bin/python -m unittest discover -s tests` passes (all existing + new tests).
4. `tests.test_client` fake server tests cover all new RPCs and expectation methods.
5. `tests.test_codegen` covers the 2 new trace events.
6. Live integration tests pass with real AudioServer/NavigationServer calls.
7. No `as any`, `@ts-ignore`, or type suppressions.
8. No pre-existing tests are weakened or deleted.

## Scope Boundaries

**In scope (batch 1)**:
- 2 new RPCs: `audio.bus.info`, `navigation.query_path`
- 2 new expectation classes: `AudioExpect`, `NavigationExpect`
- Bus state assertions (volume, mute, solo, effects, existence)
- Player node playback assertions (playing, stream, pitch, volume_db)
- Path reachability and length assertions
- NavigationAgent/NavigationRegion node assertions

**Out of scope (deferred to subsequent batches)**:
- Animation state machine assertions (AnimationTree, Blend spaces)
- Material/Shader parameter assertions
- Physics extensions (collision body parameters, Area monitoring, physics material)
- Audio effect parameter deep inspection (effect-specific property reads)
- NavigationGroup / NavLink assertions
- Multiplayer / network assertions
- Recording audio output for comparison
- Visual/audio diff baselines

## Error Handling

- Unknown bus name → structured error in result dict, `ok=false`, no exception raised.
- Invalid bus index → same.
- No navigation map loaded → `reachable=false`, not an error; result `ok=true` with empty path.
- Node selector not found → timeout error with last observed state (same pattern as existing locator assertions).
- Expression evaluation failure on node state polling → timeout error with the expression error in the error message.
