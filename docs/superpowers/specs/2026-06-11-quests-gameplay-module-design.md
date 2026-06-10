# Quests Gameplay Module Design

Date: 2026-06-11

## Context

`godot-playwright` has reusable gameplay modules for JSON save/load, inventory,
state machines, interaction, effects, stats, and abilities. Agents still
rebuild another common layer in many generated games: a generic way to track
quests, objectives, tutorial steps, contracts, milestones, challenges, and
scenario goals.

This design adds `quests` as an installable gameplay module. It is intentionally
broader than RPG quest logs. A quest can represent a repair task, tutorial
step group, daily challenge, room objective, contract, collection request,
survival milestone, puzzle checklist, or mission goal.

The module is a quest and objective state tracker. It does not implement
dialogue, combat, inventory checks, area triggers, reward payout, UI, map
markers, or event matching. Project code remains responsible for deciding when
gameplay events should advance objectives.

## Goals

- Add `quests` as an installable gameplay module.
- Provide Resource-driven quest and objective definitions with stable IDs,
  display data, tags, target amounts, completion policy, rewards, and
  JSON-compatible default data.
- Provide a `QuestLog` node that can be attached to players, parties, towns,
  sessions, level controllers, scenario controllers, or other gameplay owners.
- Support initialization, quest start/fail/complete, explicit objective
  progress mutation, runtime inspection, state export, and state import.
- Use structured dictionary results for expected failures and mutation details.
- Emit signals for quest status changes, objective progress changes, objective
  completion, and generic quest events.
- Keep `save_load`, `inventory`, `stats`, `abilities`, `effects`,
  `interaction`, and `state_machine` optional.
- Include a deterministic demo scene and copied Python test so agents can
  validate installation and behavior.
- Provide human and agent documentation for common usage patterns and
  validation.

## Non-Goals

- Do not build a dialogue system, conversation graph, NPC schedule system, or
  narrative scripting language.
- Do not build a combat objective matcher, kill tracker, loot tracker, area
  trigger system, or automatic event subscription layer in v1.
- Do not build quest stages, quest chains, dependency graphs, prerequisite
  graphs, branching mission flow, or failure recovery scripting in v1.
- Do not automatically grant rewards, mutate stats, add inventory items,
  unlock abilities, apply effects, or spend resources.
- Do not build UI widgets, quest journals, HUD trackers, minimap markers,
  compass indicators, notifications, icons, or localization tooling.
- Do not require or auto-install `save_load`, `inventory`, `stats`,
  `abilities`, `effects`, `interaction`, or `state_machine`.
- Do not automatically register an Autoload.
- Do not store `Node`, `Resource`, `Callable`, `Signal`, or other engine
  objects in saved quest state, definition `default_data`, mutation `data`, or
  rewards.

## Chosen Approach

Use a lightweight `QuestLog` node plus Godot Resource definitions.

Installation uses the existing module CLI:

```sh
godot-playwright module add <project> quests
godot-playwright module add <project> quests --demo
```

The module copies `res://addons/quests/` into the target project. It does not
register an Autoload. A game adds a `QuestLog` node wherever quest state should
live, then assigns a `QuestDatabase` resource containing `QuestDefinition`
resources.

The first version uses explicit progression. Project code calls
`advance_objective()`, `set_objective_progress()`, or `complete_objective()`
when an interaction, pickup, combat event, dialogue choice, ability activation,
area trigger, or scripted event should count toward an objective. This is
preferred over automatic event matching for v1 because it keeps the module
generic and avoids hidden dependencies on combat, inventory, dialogue,
interaction, or physics-specific code.

The first version treats rewards as declarative data. `QuestLog` can report
configured rewards when a quest completes, but it does not automatically grant
coins, items, experience, stats, effects, unlocks, or abilities. Game code
remains responsible for applying rewards through project systems.

This approach is preferred over a global `QuestService` because quest state
often belongs to a specific owner: a player profile, party, save slot, town,
level run, mission controller, or tutorial controller. It is preferred over
Node-tree quest graphs because Resource definitions are easier to reuse,
install, test, save, and generate consistently.

## Repository Layout

Add a new module tree:

```text
gameplay_modules/quests/
  module.json
  README.md
  AGENT.md
  addons/quests/
    quest_log.gd
    quest_definition.gd
    objective_definition.gd
    quest_database.gd
    quest_result.gd
    quest_constants.gd
  demo/
    scenes/
    scripts/
    resources/
  tests/
```

As with existing gameplay modules, package fallback copies should be kept
byte-identical under:

```text
godot_playwright/bundled_gameplay_modules/quests/
```

`module.json` describes the base copy operation and demo copy operation. The
module has no Autoload entries.

## Module Manifest

The manifest should follow the existing schema:

```json
{
  "name": "quests",
  "version": "0.1.0",
  "display_name": "Quests",
  "description": "Resource-driven quest and objective tracker for Godot projects.",
  "godot_version": ">=4.6",
  "copy": [
    {"from": "addons/quests", "to": "addons/quests"}
  ],
  "autoloads": [],
  "demo": {
    "copy": [
      {"from": "demo/scenes", "to": "scenes/quests_demo"},
      {"from": "demo/scripts", "to": "scripts/quests_demo"},
      {"from": "demo/resources", "to": "resources/quests_demo"},
      {"from": "tests", "to": "tests/quests_demo"}
    ]
  },
  "validation": {
    "commands": [
      "godot-playwright check-scripts /path/to/project res://addons/quests --exclude addons/godot_playwright/**",
      "godot-playwright check-resources /path/to/project res://addons/quests --exclude addons/godot_playwright/**"
    ]
  }
}
```

## Runtime Components

`quest_log.gd` defines `class_name QuestLog` and extends `Node`. It owns
exported configuration, runtime quest storage, initialization, quest mutation,
objective mutation, signals, structured results, and state import/export.

`quest_definition.gd` defines `class_name QuestDefinition` and extends
`Resource`. It stores stable quest configuration.

`objective_definition.gd` defines `class_name ObjectiveDefinition` and extends
`Resource`. It stores stable objective configuration for a single quest.

`quest_database.gd` defines `class_name QuestDatabase` and extends `Resource`.
It contains an exported array of `QuestDefinition` resources and exposes
lookup/validation helpers. Quest IDs must be unique and non-empty.

`quest_result.gd` holds structured result helpers so expected failures return
dictionaries instead of throwing exceptions.

`quest_constants.gd` holds schema version, module version, save group name,
quest status names, objective status names, completion policy names, event
names, and any shared string constants.

## Quest Definition

The initial public fields on `QuestDefinition` are:

```gdscript
@export var quest_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export var objectives: Array[Resource] = []
@export_enum("all", "any") var completion_policy: String = "all"
@export var auto_complete: bool = true
@export var start_active: bool = false
@export var rewards: Dictionary = {}
@export var default_data: Dictionary = {}
```

`quest_id` is the stable identifier used by scripts, saved state, and tests.
IDs should be lowercase and stable, such as `repair_beacon`,
`tutorial_movement`, `daily_harvest`, `clear_room`, `deliver_package`, or
`unlock_gate`.

`objectives` contains `ObjectiveDefinition` resources. Objective IDs must be
unique within a quest and non-empty. The same `objective_id` can appear in
different quests because the quest ID scopes it.

`completion_policy` controls when objective completion can finish the quest.
`all` means all non-optional objectives must be completed. `any` means any
non-optional objective can complete the quest. Optional objectives never block
quest completion.

`auto_complete` controls whether the quest automatically completes when the
completion policy is satisfied by objective mutation. When `false`, project
code must call `complete_quest()` explicitly after objectives are ready.

`start_active` controls the default initialized state. Quests with
`start_active = true` initialize as active. Other quests initialize as inactive
until `start_quest()` or `set_quest_active()` is called.

`rewards` is declarative JSON-compatible data reported on quest completion.
Common examples include `{"coins": 50}`, `{"items": [{"item_id": "gear", "quantity": 2}]}`,
`{"xp": 100}`, or `{"unlock_ability": "dash"}`. The module validates that
rewards are JSON-compatible, but it does not apply them.

`default_data` is JSON-compatible quest metadata copied into query and mutation
results. It can hold harmless data such as `{"npc": "mechanic"}`,
`{"area": "north_field"}`, or `{"difficulty": "normal"}`. It must not contain
engine objects.

## Objective Definition

The initial public fields on `ObjectiveDefinition` are:

```gdscript
@export var objective_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export_range(1, 999999, 1) var target_amount: int = 1
@export var optional: bool = false
@export var hidden: bool = false
@export var default_data: Dictionary = {}
```

`objective_id` is the stable identifier used by scripts, saved state, and
tests. IDs should be scoped to their quest and stable, such as `collect_parts`,
`scan_beacon`, `repair_beacon`, `talk_to_elder`, or `open_gate`.

`target_amount` is the completion threshold. Progress is stored as an integer
and clamped to `0..target_amount`.

`optional` means the objective can be completed and tracked but does not block
quest completion under the `all` policy and does not count as the required
objective for the `any` policy.

`hidden` is query metadata for project UI. The core module reports it but does
not hide UI elements because it does not render UI.

`default_data` is JSON-compatible objective metadata copied into query and
mutation results. It must not contain engine objects.

## QuestLog API

The initial public API on `QuestLog` is:

```gdscript
@export var database: Resource
@export var save_id: StringName
@export var initialize_on_ready: bool = true

func initialize_quests(reset: bool = false) -> Dictionary
func has_quest(quest_id: String) -> bool
func start_quest(quest_id: String, data: Dictionary = {}) -> Dictionary
func advance_objective(quest_id: String, objective_id: String, amount: int = 1, data: Dictionary = {}) -> Dictionary
func set_objective_progress(quest_id: String, objective_id: String, amount: int, data: Dictionary = {}) -> Dictionary
func complete_objective(quest_id: String, objective_id: String, data: Dictionary = {}) -> Dictionary
func complete_quest(quest_id: String, data: Dictionary = {}) -> Dictionary
func fail_quest(quest_id: String, data: Dictionary = {}) -> Dictionary
func set_quest_active(quest_id: String, active: bool) -> Dictionary
func get_quest(quest_id: String) -> Dictionary
func get_quests() -> Array
func clear_runtime_state() -> void
func get_state() -> Dictionary
func apply_state(data: Dictionary) -> Dictionary
```

`database` must expose the `QuestDatabase` protocol. The exported type can
remain `Resource` to match the inventory, effects, stats, and abilities module
style.

`save_id` is optional. When non-empty, the log joins the shared save participant
group and exposes `get_save_id()`, `save_state()`, and `load_state(data)`
wrappers compatible with `save_load`. Logs with empty `save_id` do not
automatically persist.

`initialize_on_ready` controls whether `_ready()` initializes runtime state
from the database. It defaults to `true` for ordinary scene-driven projects.
Tests and generated setup code can set it to `false` and call
`initialize_quests()` explicitly.

`initialize_quests(false)` should preserve existing runtime state once
initialized. `initialize_quests(true)` clears current runtime state and rebuilds
from definitions.

`has_quest()` returns whether the initialized runtime state contains a quest ID.

`start_quest()` moves an inactive quest to active, initializes its objectives
to active, emits events, and returns the quest snapshot. Starting an already
active quest is a successful no-op. Starting a completed or failed quest fails
unless future versions add reset/restart helpers.

`advance_objective()` adds a positive integer amount to objective progress.
It requires an active quest and an active objective. Progress is clamped to the
objective target. Reaching the target completes the objective and may complete
the quest when `auto_complete` and the completion policy allow it.

`set_objective_progress()` sets objective progress to a specific integer. It
requires an active quest and an active objective. Values are clamped to
`0..target_amount`. Setting progress to the target completes the objective.

`complete_objective()` sets objective progress to target amount and marks the
objective completed. It may complete the quest when `auto_complete` and the
completion policy allow it.

`complete_quest()` marks an active quest completed, completes any required
objectives that are still incomplete only when the completion policy is already
satisfied, emits events, and reports declarative rewards. It does not apply
rewards.

`fail_quest()` marks an inactive or active quest failed and emits events. It
does not undo already reported rewards from project code.

`set_quest_active()` is a convenience for explicit state changes. `true`
delegates to `start_quest()`. `false` moves an active quest back to inactive
only when it has no completed objective progress; otherwise it fails with a
clear error so callers do not accidentally discard meaningful progress. Project
code can use future reset helpers for destructive rollback if needed.

`get_quest()` and `get_quests()` return copies of runtime dictionaries so
callers cannot accidentally mutate internal state.

## Runtime Quest State

The container stores one runtime dictionary per quest:

```json
{
  "quest_id": "repair_beacon",
  "status": "active",
  "data": {},
  "objectives": [
    {
      "objective_id": "collect_parts",
      "status": "active",
      "progress": 2,
      "target_amount": 3,
      "data": {}
    }
  ]
}
```

Quest statuses are:

- `inactive`: defined and known, but not currently being progressed.
- `active`: available for objective progress.
- `completed`: terminal successful state.
- `failed`: terminal unsuccessful state.

Objective statuses are:

- `inactive`: the parent quest is inactive.
- `active`: the parent quest is active and the objective can progress.
- `completed`: the objective reached its target or was completed explicitly.

The module should preserve deterministic quest order based on the database
definition order and deterministic objective order based on each quest
definition order. Saved state can be applied in any order, but `get_quests()`
and objective snapshots should return definition order for stable tests and
agent inspection.

Runtime state stores only JSON-compatible values. It does not store
`QuestDefinition`, `ObjectiveDefinition`, or any engine object.

## Progression Rules

All public quest IDs and objective IDs are normalized by trimming whitespace.
Empty IDs fail clearly.

An objective can progress only when:

- The quest log has initialized successfully.
- The database is assigned and validates.
- The quest ID exists.
- The objective ID exists within the quest.
- The quest status is `active`.
- The objective status is `active`.
- The provided `data` dictionary is JSON-compatible.
- The amount or target progress is an integer and not negative.

Progress mutation rules:

- `advance_objective()` requires `amount > 0`.
- `set_objective_progress()` accepts `amount >= 0`.
- Progress is clamped to `0..target_amount`.
- Expected clamping is not an error. The result reports `clamped: true` and a
  warning when the requested value differs from the applied value.
- Moving progress from below target to target emits an objective completion
  event.
- Progress for a completed objective is immutable in v1. Calls that try to
  change it fail without state changes.
- Progress for completed or failed quests is immutable in v1.

Quest completion rules:

- Under `all`, every non-optional objective must be completed.
- Under `any`, at least one non-optional objective must be completed.
- If a quest has no non-optional objectives, it can only be completed
  explicitly with `complete_quest()`.
- Optional objective completion is tracked and reported but does not satisfy
  `any` and does not block `all`.
- With `auto_complete = true`, completing an objective checks the completion
  policy and completes the quest when the policy is satisfied.
- With `auto_complete = false`, objective completion never completes the quest
  automatically.

`complete_quest()` validates the completion policy before marking the quest
completed. This prevents project code from accidentally completing an active
quest whose required objectives are not ready. If a project needs scripted
override behavior, it should complete the relevant objectives first or use a
future explicit override API.

## Results

Public mutation methods return dictionaries with consistent fields:

```json
{
  "ok": true,
  "quest_id": "repair_beacon",
  "objective_id": "collect_parts",
  "status": "active",
  "previous_status": "active",
  "progress": 3,
  "previous_progress": 2,
  "target_amount": 3,
  "clamped": false,
  "quest": {},
  "rewards": {},
  "data": {},
  "events": [],
  "warnings": [],
  "errors": []
}
```

Not every method fills every field, but the keys should be stable enough for
agents to inspect expected failures. Expected gameplay failures such as unknown
IDs, invalid progress, inactive quests, terminal quests, and non-JSON data
should return `ok = false` with `errors`; they should not throw exceptions or
silently mutate state.

`quest` is a snapshot after the attempted operation when the quest is known.
`rewards` is populated on successful quest completion and is a duplicate of the
definition rewards dictionary.

## Signals

`QuestLog` should expose these signals:

```gdscript
signal quest_started(quest_id: String, result: Dictionary)
signal quest_completed(quest_id: String, result: Dictionary)
signal quest_failed(quest_id: String, result: Dictionary)
signal quest_status_changed(quest_id: String, status: String, result: Dictionary)
signal objective_progress_changed(quest_id: String, objective_id: String, progress: int, result: Dictionary)
signal objective_completed(quest_id: String, objective_id: String, result: Dictionary)
signal quests_changed(event: Dictionary)
```

Signals are emitted after runtime state changes. `quests_changed` emits compact
event dictionaries suitable for UI refresh, tests, and agent inspection.

## State Import And Export

`get_state()` returns JSON-compatible data:

```json
{
  "schema_version": 1,
  "quests": [
    {
      "quest_id": "repair_beacon",
      "status": "active",
      "data": {},
      "objectives": [
        {
          "objective_id": "collect_parts",
          "status": "active",
          "progress": 2,
          "data": {}
        }
      ]
    }
  ]
}
```

Saved state stores schema version, stable quest IDs, quest statuses, quest
runtime data, stable objective IDs, objective statuses, objective progress, and
objective runtime data. It does not need to store display names, descriptions,
tags, target amounts, rewards, or default data because those come from the
current definitions.

`apply_state(data)` is strict and atomic:

- Validate schema version.
- Validate that the database is assigned and valid.
- Validate that `quests` is an array of dictionaries.
- Reject duplicate saved quest IDs.
- Reject stale or unknown saved quest IDs.
- Reject invalid quest statuses.
- Reject duplicate objective IDs inside a quest.
- Reject stale or unknown objective IDs inside a quest.
- Reject invalid objective statuses.
- Reject objective progress outside `0..target_amount`.
- Reject completed objectives whose progress is below target.
- Reject active/inactive objectives whose progress is at or above target.
- Reject objective statuses inconsistent with parent quest status.
- Reject non-JSON-compatible runtime `data`.
- Reject cycles in saved data or definition dictionaries.
- Reject `NaN`, infinity, Nodes, Resources, Callables, Signals, or other
  engine objects in saved data.

If validation fails, current runtime state remains unchanged. If validation
passes, saved quests are applied and any definitions missing from the saved
state are initialized from the current database defaults in database order.
This allows a game update to add new quests without breaking old saves while
still rejecting stale saved quests whose definitions were removed.

When a container has a non-empty `save_id`, it joins the shared save participant
group in `_enter_tree()` and exposes:

```gdscript
func get_save_id() -> String
func save_state() -> Dictionary
func load_state(data: Dictionary) -> void
```

`load_state(data)` wraps `apply_state(data)` and pushes a warning only when
the load fails, matching the existing module style.

## Validation

`QuestDatabase` should validate:

- The quest list is an array of `QuestDefinition` resources.
- Quest IDs are non-empty after trimming.
- Quest IDs are unique.
- Completion policy is `all` or `any`.
- Rewards and default data are JSON-compatible.
- Each quest has valid objective definitions.
- Objective IDs are non-empty after trimming.
- Objective IDs are unique within their quest.
- Objective target amounts are at least `1`.
- Objective default data is JSON-compatible.

Dictionary validation should detect cycles and reject engine objects. Top-level
scalar reward values may be numbers, booleans, strings, or null. Numeric values
must be finite.

## Optional Integration

Project code can integrate the module without imports inside `quests`:

- Interaction scripts can call `advance_objective()` after talking to an NPC,
  opening a door, repairing a machine, or picking up an object.
- Inventory scripts can check required items before calling
  `complete_objective()` or can apply reward items after quest completion.
- Stats scripts can gate quest completion on health, stamina, temperature,
  morale, or settlement values before calling quest APIs.
- Ability scripts can advance objectives when a scan, repair, dash, build, or
  attack ability succeeds.
- Effects scripts can listen for quest completion and apply project-specific
  buffs or debuffs.
- State-machine states can start quests, fail quests, or guard transitions based
  on quest snapshots.
- Save/load can persist quest logs through stable `save_id` values.

The core module does not import `save_load`, `inventory`, `stats`, `abilities`,
`effects`, `interaction`, `state_machine`, dialogue, combat, UI, AI, or map
marker files.

## Demo

The demo should install under:

```text
scenes/quests_demo/
scripts/quests_demo/
resources/quests_demo/
tests/quests_demo/
```

Use a small "repair beacon" scenario:

- Quest ID: `repair_beacon`
- Completion policy: `all`
- Auto complete: `true`
- Rewards: `{"coins": 50, "reputation": 5}`
- Objectives:
  - `collect_parts`, target `3`
  - `scan_beacon`, target `1`
  - `repair_beacon`, target `1`

The scene can use a simple `Control` root with buttons or scripted steps that
start the quest, advance each objective, and display compact labels for status
and progress. The demo should keep UI minimal; its purpose is deterministic
behavior evidence, not a full quest journal.

The demo test should verify:

- The scene launches without runtime errors.
- Starting the quest changes status to active.
- Advancing `collect_parts` from 0 to 3 completes that objective.
- Completing scan and repair objectives auto-completes the quest.
- The final completion result reports rewards but no rewards are automatically
  applied to stats, inventory, or other systems.

## Tests

Add module installer tests:

- Repository module is discoverable.
- Base install copies all quest scripts and registers no Autoload.
- Demo install copies demo scene, scripts, resources, and copied test.

Add Godot module tests for:

- Database validation rejects missing IDs, duplicate quest IDs, duplicate
  objective IDs, invalid completion policies, invalid target amounts, and
  non-JSON-compatible dictionaries.
- Initialization creates inactive or active quests based on `start_active`.
- `start_quest()` transitions inactive quests to active and initializes
  objectives.
- `advance_objective()` and `set_objective_progress()` validate IDs, active
  state, amount rules, clamping, and objective completion.
- `completion_policy = all` and `completion_policy = any` behave correctly.
- Optional objectives do not block or satisfy required completion.
- `auto_complete = true` completes the quest when policy is satisfied.
- `auto_complete = false` leaves the quest active until `complete_quest()`.
- `complete_quest()` reports rewards but does not apply them.
- `fail_quest()` creates a terminal failed state.
- Terminal quests and completed objectives reject further progress.
- Runtime snapshots are deep copies.
- `get_state()` returns JSON-compatible state.
- `apply_state()` accepts valid state, rejects malformed state, rejects stale
  IDs, rejects inconsistent statuses/progress, and is atomic on failure.
- Save/load wrappers work when `save_id` is set.

Add demo tests under `gameplay_modules/quests/tests/` and mirror them under the
bundled module tree when implementation begins.

## Documentation

`README.md` should explain:

- What the module does and does not do.
- How to create `QuestDefinition`, `ObjectiveDefinition`, and `QuestDatabase`
  resources.
- How to attach and initialize `QuestLog`.
- How explicit progression works.
- How completion policies and optional objectives work.
- How rewards are reported but not applied.
- How to persist through `get_state()` / `apply_state()` and optional
  `save_load` wrappers.
- How to integrate with interaction, inventory, stats, abilities, effects,
  state machines, and project-specific dialogue or combat.
- Validation commands.

`AGENT.md` should give concise generation guidance:

- Prefer explicit progression calls from project code.
- Use stable lowercase IDs.
- Keep rewards and data JSON-compatible.
- Do not put Nodes, Resources, Callables, Signals, or UI references in saved
  state.
- Do not add hidden dependencies on other modules.
- Preserve source and bundled module trees byte-identically.

## Implementation Sequence

1. Add failing installer discovery and copy tests for `quests`.
2. Add the source module shell: manifest, initial docs, constants, result
   helper, definitions, database, and log stubs.
3. Implement Resource validation and JSON compatibility checks.
4. Implement `QuestLog` initialization and runtime snapshots.
5. Implement quest status transitions.
6. Implement objective progress mutation and completion policies.
7. Implement state export/import and save/load wrappers.
8. Add the demo resources, scene, script, and demo test.
9. Mirror the source module into bundled package data and update package
   metadata.
10. Update root README module list and installer docs.
11. Run focused unit tests, Godot module tests, demo tests, mirror diffs, and
   `git diff --check`.

## Open Decisions

No open design decisions remain for v1. Future versions can consider event
matching, quest stages, dependency graphs, restart/reset helpers, localization
metadata, and UI helpers after the core tracker proves stable.
