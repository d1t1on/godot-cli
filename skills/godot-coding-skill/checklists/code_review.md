# Godot Code Review Checklist

Use this checklist before accepting or delivering generated Godot code.

## Version and API

- [ ] The target Godot version is known or clearly stated as unknown.
- [ ] Godot 4 projects do not contain Godot 3-only class names or syntax.
- [ ] New code uses Godot 4 signal syntax unless project conventions require otherwise.
- [ ] Engine APIs were checked against the project version when uncertain.

## Architecture

- [ ] Scenes are used for game-specific node compositions.
- [ ] Large procedural node creation is justified or converted to `.tscn` scenes.
- [ ] Custom Resources are used for shared/editor-tunable data.
- [ ] Runtime mutable state does not accidentally mutate shared loaded Resources.
- [ ] Autoloads are limited to broad, long-lived systems with narrow APIs.
- [ ] Pure data/algorithm classes use `RefCounted`, `Resource`, or static helpers instead of unnecessary Nodes.
- [ ] No new monolithic manager or global state dump was introduced.

## Coupling

- [ ] Reusable scenes do not use absolute paths like `/root/Main/...`.
- [ ] Parent scenes wire child dependencies and signals.
- [ ] Signals are used for event notifications where sender should not know receivers.
- [ ] Groups are documented and not scanned every frame unnecessarily.
- [ ] Hard-coded magic strings are minimized with constants, Resources, or documented IDs.

## GDScript quality

- [ ] Public functions, exported variables, and important locals are typed.
- [ ] Functions have return types.
- [ ] Files/folders use `snake_case`; nodes/classes use `PascalCase`.
- [ ] Node references are cached with `@onready` only when appropriate.
- [ ] Optional node references use null checks.
- [ ] `queue_free()` is used for nodes in the tree; tree changes during callbacks are deferred when needed.
- [ ] `_process()` is not used for logic that belongs in input callbacks, `_physics_process()`, Timer, or signals.

## Input and UI

- [ ] Gameplay input uses InputMap actions, not hard-coded keys/buttons.
- [ ] Movement uses physics processing when it affects physics bodies.
- [ ] UI emits semantic intent signals instead of directly mutating unrelated gameplay systems.
- [ ] Important UI/test targets have stable names, roles, or metadata `test_id`.
- [ ] Control containers are used for layout unless manual positioning is intentional.

## Resources and files

- [ ] New Resource classes have `class_name`, typed exports, and default `_init()` args if custom constructors are used.
- [ ] Moved/renamed resources update references in `.tscn`, `.tres`, and scripts.
- [ ] Third-party code remains under `addons/` or existing vendor structure.
- [ ] No generated files are placed in ignored/import-only folders accidentally.

## Tests and validation

- [ ] Changed scripts pass Godot parser checks.
- [ ] Changed scenes/resources pass dependency checks.
- [ ] Affected runtime scene was probed or tested.
- [ ] Broad refactors run project-level validation or a justified narrowed equivalent.
- [ ] Tests use retryable expectations, not arbitrary sleeps.
- [ ] Test assertions check gameplay intent, not incidental implementation details.
