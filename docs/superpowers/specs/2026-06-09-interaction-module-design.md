# Interaction Gameplay Module Design

Date: 2026-06-09

## Context

`godot-playwright` now has reusable gameplay modules for JSON save/load and Resource-driven inventory. A state-machine module is being developed in a separate worktree. The next parallel module should avoid depending on state-machine behavior and should avoid high-performance systems that are better suited to a future GDExtension module pattern, such as projectiles, custom navigation, or avoidance.

This design adds `interaction` as an installable gameplay module. It provides a small reusable interaction protocol and range-detection components for common gameplay actions: picking up objects, opening doors and chests, pressing buttons, talking to NPCs, and triggering simple mechanisms. The module follows the existing gameplay-module style: low-intrusion installation, Godot-native scripts, structured dictionary results for expected failures, optional integration boundaries, a deterministic demo, copied demo tests, and agent-focused documentation.

## Goals

- Add `interaction` as an installable gameplay module.
- Provide a generic interaction protocol that does not assume inventory, quest, dialogue, UI, player, NPC, or state-machine semantics.
- Support 2D and 3D range-based interaction through reusable interactor components.
- Keep interactable behavior callable outside range detection so RayCast, UI, grid, or scripted systems can use the same protocol later.
- Support candidate tracking, deterministic best-candidate selection, prompt access, priority, enable/disable behavior, and structured interaction results.
- Provide JSON-compatible state import/export helpers on interactables for simple persistent interaction state.
- Keep `inventory` and `save_load` integration optional while documenting and testing safe integration paths where practical.
- Include a small demo scene and copied Python test so agents can validate installation and behavior.
- Provide human and agent documentation for common usage patterns and validation.

## Non-Goals

- Do not build a quest system.
- Do not build a dialogue tree or conversation graph system.
- Do not build inventory, loot, equipment, crafting, shop, or reward systems inside this module.
- Do not build UI prompt widgets, radial menus, or input remapping.
- Do not build projectile, navigation, avoidance, crowd, or high-volume physics systems.
- Do not depend on the `state_machine` module.
- Do not require or auto-install `inventory` or `save_load`.
- Do not automatically register an Autoload.
- Do not automatically join `save_load` save groups.

## Chosen Approach

Use a pure `Interactable` component plus 2D and 3D range-detection interactors.

Installation uses the existing module CLI:

```sh
godot-playwright module add <project> interaction
godot-playwright module add <project> interaction --demo
```

The module copies `res://addons/interaction/` into the target project. It does not register an Autoload. A game adds an `Interactable` node under objects that can be used, opened, picked up, talked to, or triggered. A player or other actor adds either `Interactor2D` or `Interactor3D` to detect nearby interactables and call the best candidate.

This approach is preferred over a RayCast-only module because range interaction applies to more Godot game types: top-down, side-scroller, RPG, action-adventure, puzzle, and simple 3D games. It is also preferred over a pure duck-typed protocol because agents would still need to rebuild range tracking and priority selection in every project. Keeping `Interactable` as a plain `Node` avoids locking scene structure to `Area2D` or `Area3D` and allows future RayCast, UI, or grid systems to call the same `interact()` method directly.

## Repository Layout

Add a new module tree:

```text
gameplay_modules/interaction/
  module.json
  README.md
  AGENT.md
  addons/interaction/
    interactable.gd
    interactor_2d.gd
    interactor_3d.gd
    interaction_result.gd
    interaction_constants.gd
  demo/
    scenes/
    scripts/
  tests/
```

As with existing gameplay modules, package fallback copies should be kept byte-identical under:

```text
godot_playwright/bundled_gameplay_modules/interaction/
```

`module.json` describes the base copy operation and demo copy operation. The module has no Autoload entries.

## Module Manifest

The manifest should follow the existing schema:

```json
{
  "name": "interaction",
  "version": "0.1.0",
  "display_name": "Interaction",
  "description": "Range-based interaction components for Godot projects.",
  "godot_version": ">=4.6",
  "copy": [
    {"from": "addons/interaction", "to": "addons/interaction"}
  ],
  "autoloads": [],
  "demo": {
    "copy": [
      {"from": "demo/scenes", "to": "scenes/interaction_demo"},
      {"from": "demo/scripts", "to": "scripts/interaction_demo"},
      {"from": "tests", "to": "tests/interaction_demo"}
    ]
  },
  "validation": {
    "commands": [
      "godot-playwright check-scripts /path/to/project res://addons/interaction --exclude addons/godot_playwright/**",
      "godot-playwright check-resources /path/to/project res://addons/interaction --exclude addons/godot_playwright/**"
    ]
  }
}
```

## Runtime Components

`interactable.gd` defines `class_name Interactable` and extends `Node`. It owns exported interaction identity, prompt text, priority, enabled state, default interaction behavior, prompt lookup, and JSON-compatible state import/export helpers. Games can attach scripts that extend `Interactable` or compose an `Interactable` child under a gameplay object.

`interactor_2d.gd` defines `class_name Interactor2D` and extends `Area2D`. It tracks nearby interactables discovered through `area_entered`, `body_entered`, `area_exited`, and `body_exited` signals.

`interactor_3d.gd` defines `class_name Interactor3D` and extends `Area3D`. It mirrors the `Interactor2D` public API while using 3D area/body signals.

`interaction_result.gd` holds structured result helpers so expected failures return dictionaries instead of throwing exceptions.

`interaction_constants.gd` holds schema version, module version, and any shared names.

## Interactable API

The initial public API on `Interactable` is:

```gdscript
@export var interaction_id: StringName
@export var prompt: String = "Interact"
@export var priority: int = 0
@export var enabled: bool = true

func get_interaction_id() -> String
func get_interaction_prompt(actor: Node = null) -> String
func can_interact(actor: Node, data: Dictionary = {}) -> bool
func interact(actor: Node, data: Dictionary = {}) -> Dictionary
func get_state() -> Dictionary
func apply_state(data: Dictionary) -> Dictionary
```

`get_interaction_id()` resolves a stable ID in this order:

- Use non-empty `interaction_id` when configured.
- Otherwise use the parent node name when the interactable has a parent.
- Otherwise use the interactable node name.

Explicit IDs are recommended for objects whose interaction state will be saved. Node-name fallback is useful during prototyping but fragile after scene edits.

The base `interact()` implementation validates that the target is enabled and returns a structured success result. It does not mutate game state. Game-specific behavior such as opening a door, marking a pickup collected, starting dialogue, or activating a mechanism should be implemented by extending or overriding `can_interact()` and `interact()`.

## Interactor API

Both `Interactor2D` and `Interactor3D` expose the same public API:

```gdscript
func get_candidates() -> Array
func get_best_candidate() -> Node
func get_best_prompt() -> String
func interact_best(data: Dictionary = {}) -> Dictionary
func interact_with(target: Node, data: Dictionary = {}) -> Dictionary
func clear_candidates() -> void
```

`get_candidates()` returns currently valid enabled interactables in deterministic selection order. The returned array should be safe for callers to inspect without mutating the interactor's internal tracking state.

`get_best_candidate()` returns the enabled interactable with the highest priority. If priorities tie, it returns the interactable that entered range first.

`get_best_prompt()` returns the prompt for the best candidate or an empty string when no candidate is available.

`interact_best()` calls `interact_with(get_best_candidate(), data)` and returns a structured failure when no valid candidate exists.

`interact_with(target, data)` validates the target, calls `can_interact(actor, data)`, then calls `interact(actor, data)`. The actor passed to the interactable should be the owner of the interactor when available; otherwise it should be the interactor node itself. This lets a player node own `Interactor2D` while interactables receive the player as the actor.

## Candidate Resolution

When an area or body enters an interactor, the interactor resolves one interactable with these rules:

1. If the entered node is an `Interactable`, use it.
2. Otherwise inspect direct child nodes and use a single `Interactable` child if exactly one exists.
3. Otherwise walk upward through parent nodes and use the first `Interactable` found.
4. If the entered node or its direct children expose multiple possible interactables at the same resolution level, treat the target as ambiguous and ignore it while recording a warning.

The MVP should not randomly select among ambiguous interactables. Ambiguity should be visible in results or demo diagnostics so agents can fix scene structure by adding a single clear interactable component or targeting a specific object directly.

Candidate tracking rules:

- Ignore targets that cannot resolve to an `Interactable`.
- Ignore invalid or freed targets when querying candidates.
- Ignore disabled interactables when selecting the best candidate.
- Preserve an increasing enter order for deterministic tie-breaking.
- Remove candidates when their area or body exits.
- `clear_candidates()` removes all tracked candidates and resets local tracking state.

## Structured Results

Expected failures should be returned in result dictionaries, matching the existing gameplay-module style:

```gdscript
{
  "ok": false,
  "interaction_id": "door_01",
  "target": "Door",
  "warnings": [],
  "errors": ["Interactable is disabled"]
}
```

Successful interaction results should include `ok: true`, `interaction_id`, `target`, `warnings`, and `errors`. Game-specific interactables may add fields such as `opened`, `picked_up`, `item_id`, or `quantity`, but they should keep the common fields so agents and tests can inspect results consistently.

Common expected failures:

- No candidate is available.
- The target is null, freed, or not an `Interactable`.
- Candidate resolution is ambiguous.
- The interactable is disabled.
- `can_interact()` rejects the interaction.
- `interact()` returns a non-dictionary value.

The module should avoid throwing exceptions for expected gameplay or wiring errors. Parser errors, missing script dependencies, and other hard Godot failures remain validation failures outside the result-dictionary contract.

## State Format

`Interactable.get_state()` returns JSON-compatible data:

```json
{
  "schema_version": 1,
  "interaction_id": "door_01",
  "enabled": true,
  "prompt": "Open",
  "priority": 10
}
```

`Interactable.apply_state(data)` validates the schema, interaction ID shape, enabled value, prompt shape, and priority shape before mutating. It should not overwrite a non-empty configured `interaction_id` with saved data; the saved ID is used for diagnostics. Invalid state returns `ok: false` and does not partially mutate the interactable.

The base state intentionally stores only generic interaction fields. Game-specific subclasses can extend `get_state()` and `apply_state(data)` with fields such as `opened`, `picked_up`, or `used_count` while preserving the base schema fields.

## Optional Module Integration

The module must be usable without `inventory`, `save_load`, or `state_machine`.

For projects using `inventory`, an interactable pickup can call an `Inventory` node from its overridden `interact()` method. The core module should not import or preload inventory scripts. The demo may optionally detect an `Inventory` node or class and verify an integration path when available, but the copied demo must pass without installing `inventory`.

For projects using `save_load`, interactables can be persisted by wrapping `get_state()` and `apply_state(data)` in save participant methods on the owning node. The module should not automatically join `save_participants`, because many interactables are temporary triggers, UI controls, generated pickups, or one-scene objects that should not persist by default.

For projects using the parallel `state_machine` module, states may call an interactor or interactable from state logic, but `interaction` must not depend on `state_machine` files, classes, or lifecycle behavior.

## Demo

`--demo` installs a small 2D runtime scene. The demo should be compact and deterministic, not a full game template.

Scene contents:

- One actor node with an `Interactor2D` child and a collision shape.
- One pickup object with an `Interactable`-derived script that marks itself picked up and disables itself after interaction.
- One door object with an `Interactable`-derived script that toggles open/closed state.
- Two overlapping interactables with different priorities to validate best-candidate selection.

The demo root script exposes:

```gdscript
func run_interaction_demo() -> Dictionary
```

The demo should validate:

- A detected target appears in `get_candidates()`.
- `get_best_candidate()` uses priority first and enter order second.
- `get_best_prompt()` exposes the selected target's prompt.
- `interact_best()` calls the target and returns a structured success result.
- Disabled interactables are not selected.
- `clear_candidates()` causes `interact_best()` to return a structured no-candidate failure.
- A door or pickup state round-trip through `get_state()` and `apply_state()` restores generic and game-specific interaction state.
- If an inventory integration object is present, pickup behavior can add an item; if not, the demo still passes by validating local picked-up state.

The copied Python demo test should load the scene through `godot-playwright`, call `run_interaction_demo()`, and assert a structured success result.

## CLI And Installer Behavior

The existing `godot-playwright module list` should show `interaction` once this module is present.

`godot-playwright module add <project> interaction` should copy only the base module files and use existing safe installer behavior:

- Refuse to overwrite files by default.
- Allow `--force` only for module-owned paths.
- Reject duplicate planned targets.
- Avoid symlink target overwrites.
- Return a clear installation report.
- Add no Autoload entries.

`godot-playwright module add <project> interaction --demo` should also copy demo scenes, demo scripts, and copied tests into module-specific paths such as:

```text
res://scenes/interaction_demo/
res://scripts/interaction_demo/
tests/interaction_demo/
```

## Documentation

`README.md` should explain:

- How to install the module.
- How to add an `Interactable` node to a door, pickup, NPC, button, chest, or trigger.
- How to add `Interactor2D` or `Interactor3D` to an actor.
- How candidate priority and enter-order tie-breaking work.
- How to call `interact_best()` and inspect result dictionaries.
- How to expose prompts to a project's own UI.
- How to save simple interaction state through `get_state()` and `apply_state(data)`.
- How to validate the module after installation.

`AGENT.md` should give operational instructions:

- Use this module when a game needs nearby object interaction, pickups, doors, chests, buttons, NPC use prompts, or simple mechanisms.
- Do not use this module as a quest system, dialogue graph, inventory system, or UI system.
- Prefer stable explicit `interaction_id` values for objects that may be saved.
- Keep `Interactable.interact()` methods small and domain-specific.
- Put UI prompt rendering in the game UI, using `get_best_prompt()` or the best candidate's prompt data.
- Use `Inventory` only when the project has installed the inventory module and the interaction needs item transfer.
- Use `SaveService` only through explicit save participant wrappers on objects that should persist.
- Validate with targeted script/resource checks and the copied demo test.

## Testing Strategy

Python tests should cover:

- Module discovery lists `interaction` with version `0.1.0`.
- `module add interaction` copies base files and does not add Autoloads.
- `module add interaction --demo` copies demo files and copied tests.
- Package fallback data contains the bundled interaction module.
- Source and bundled module trees stay byte-identical.
- `pyproject.toml` includes bundled interaction package data.
- Existing installer safety behavior still applies to the new module.

Godot validation should cover when Godot is available:

- Interaction module scripts pass Godot parser checks.
- Demo scene/resource dependencies are valid.
- Demo runtime method validates candidate discovery, priority selection, prompt lookup, successful interaction, disabled target filtering, no-candidate failure, and state round-trip.

If Godot is unavailable, Python installer tests still provide coverage, and final reporting must state that live Godot validation was skipped.

## Future Extensions

- RayCast2D and RayCast3D interactor helpers for cursor, first-person, or third-person aiming.
- UI prompt helper scenes that render the best candidate prompt without coupling the core module to a specific UI style.
- Input action helper that calls `interact_best()` when a configured action is pressed.
- One-shot interactables, cooldowns, and usage limits as optional subclasses.
- Loot-table integration after a loot module exists.
- Quest and dialogue integration after those modules exist.
- GDExtension-backed high-volume perception or spatial-query helpers if future performance requirements justify them.

## Acceptance Criteria

- `godot-playwright module list` shows `interaction`.
- `godot-playwright module add <project> interaction` installs `res://addons/interaction/` without registering an Autoload.
- `godot-playwright module add <project> interaction --demo` installs demo scene, scripts, and copied demo test.
- `Interactable` supports interaction IDs, prompts, priority, enabled state, default interaction, state export, and state import.
- `Interactor2D` and `Interactor3D` expose matching APIs for candidates, best-candidate selection, prompt lookup, targeted interaction, best interaction, and clearing candidates.
- Candidate selection is deterministic: highest priority wins, then earliest enter order.
- Disabled, freed, invalid, and ambiguous candidates fail or filter clearly.
- Expected interaction failures return structured dictionaries instead of exceptions.
- Demo validates candidate discovery, priority selection, prompt lookup, interaction, disabled filtering, no-candidate failure, and state round-trip.
- Human and agent docs explain usage, non-goals, optional integrations, and validation.
