# Versioning and Documentation Policy

Godot changes quickly. AI agents must not assume that remembered APIs are correct for the target project.

## Rule

The target project's engine version is the source of truth.

Detection order:

1. `godot-playwright engine.info` or `godot-playwright rpc engine.info` when an automation server is available.
2. `godot --version` for the local binary.
3. `project.godot` metadata and existing file syntax.
4. User-provided version constraints.

## Stable docs vs latest docs

Use documentation matching the project version. Avoid using the unstable `latest` docs for a stable project unless you are checking upcoming APIs intentionally.

For current Godot 4.x work:

- Prefer `https://docs.godotengine.org/en/stable/` unless the project pins an older version.
- If the project uses Godot 4.4/4.5/4.6, switch the docs URL to `/en/4.4/`, `/en/4.5/`, `/en/4.6/` when exact API details matter.
- If a project is Godot 3.x, use Godot 3 docs and do not apply Godot 4 syntax.

## Common Godot 3 → 4 traps

Do not write these in Godot 4 projects:

| Godot 3 habit | Godot 4 replacement |
|---|---|
| `yield(...)` | `await ...` |
| `KinematicBody2D` / `KinematicBody` | `CharacterBody2D` / `CharacterBody3D` |
| `Spatial` | `Node3D` |
| `Position2D` | `Marker2D` |
| `PoolByteArray` / `PoolVector2Array` | `PackedByteArray` / `PackedVector2Array` |
| `$Button.connect("pressed", self, "_on_pressed")` | `button.pressed.connect(_on_pressed)` |
| `emit_signal("changed", value)` for new code | `changed.emit(value)` |
| `instance()` on PackedScene | `instantiate()` |
| `OS.window_size` | `DisplayServer` / Window APIs depending on need |

Compatibility wrappers may exist, but new Godot 4 code should use Godot 4 idioms.

## When unsure

If an API is uncertain:

1. Check the exact version docs or class reference.
2. Search existing project code for the pattern.
3. Run `check-script` after the smallest possible change.
4. Prefer an explicit note over guessing.

## Harness version coupling

`godot-playwright` itself has a protocol surface. Before using a specific RPC/editor helper, call:

```bash
godot-playwright rpc protocol.describe --port PRINTED_PORT
```

or from Python:

```python
protocol = godot.protocol_describe()
methods = {entry["method"] for entry in protocol["methods"]}
```

Then choose helpers supported by the connected server.
