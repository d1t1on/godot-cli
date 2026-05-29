# Research Sources

Reviewed on 2026-05-26.

## Godot official sources

- Godot homepage: current latest stable download shown as Godot 4.6.3, with a 4.6.3 maintenance release dated 2026-05-20.
  - https://godotengine.org/
- Godot stable documentation: current stable branch is Godot Engine 4.6 docs.
  - https://docs.godotengine.org/en/stable/
- Godot Best practices index: scene organization, scenes vs scripts, Autoloads vs regular nodes, node alternatives, data preferences, logic preferences, project organization, version control.
  - https://docs.godotengine.org/en/stable/tutorials/best_practices/index.html
- Scene organization: keep focused, single-purpose scenes/classes with loose coupling; reusable sub-scenes should not depend on environment-specific node paths.
  - https://docs.godotengine.org/en/stable/tutorials/best_practices/scene_organization.html
- Scenes versus scripts: scenes define declarative composition; scripts define behavior; game-specific concepts should usually be scenes; script classes are useful for reusable tools/types.
  - https://docs.godotengine.org/en/stable/tutorials/best_practices/scenes_versus_scripts.html
- Autoloads versus regular nodes: use Autoloads for broad-scoped systems that own their data; prefer Resources or ordinary objects when sharing data/functionality does not require an Autoload.
  - https://docs.godotengine.org/en/stable/tutorials/best_practices/autoloads_versus_regular_nodes.html
- Node alternatives: Object, RefCounted, and Resource are lighter alternatives to Nodes; Resources serialize properties and are Inspector-compatible.
  - https://docs.godotengine.org/en/stable/tutorials/best_practices/node_alternatives.html
- Project organization: Godot is scene-based and uses the filesystem as-is; group assets close to scenes; use snake_case files/folders and PascalCase node names.
  - https://docs.godotengine.org/en/stable/tutorials/best_practices/project_organization.html
- Resources: custom Resources appear in the Inspector when using `class_name`; constructors should provide default values for Inspector creation/editing.
  - https://docs.godotengine.org/en/stable/tutorials/scripting/resources.html
- GDScript style guide: conventions for readable, consistent GDScript.
  - https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_styleguide.html
- Static typing in GDScript: warnings, typed style, and safer typed operations.
  - https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/static_typing.html
- Godot notifications: when to use `_process`, `_physics_process`, and input callbacks.
  - https://docs.godotengine.org/en/stable/tutorials/best_practices/godot_notifications.html
- Signals: Godot signals reduce coupling and allow nodes to react without direct references.
  - https://docs.godotengine.org/en/stable/getting_started/step_by_step/signals.html
- Controller/input best practices: use InputMap actions instead of hard-coded keys/controller buttons.
  - https://docs.godotengine.org/en/stable/tutorials/inputs/controllers_gamepads_joysticks.html

## godot-playwright / godot-cli sources

- d1t1on/godot-cli repository README: Godot Playwright is a local automation bridge for Godot 4.6+; includes add-on, Python client, CLI, smoke checks, validation, script checks, scene/resource inspection, probes, export, traces, and Playwright-like locators/assertions.
  - https://github.com/d1t1on/godot-cli
- Protocol docs: local HTTP JSON-RPC over loopback, health endpoint, RPC endpoint, default bind `127.0.0.1:9777`, auto/fallback ports for tool-launched sessions, selectors, RPC methods, project validation commands.
  - https://github.com/d1t1on/godot-cli/blob/main/docs/protocol.md
