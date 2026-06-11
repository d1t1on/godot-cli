# Quests Gameplay Module

`quests` adds a Resource-driven quest and objective tracker for Godot 4.6+ projects.

Install into a Godot project:

```sh
godot-playwright module add /path/to/project quests
```

Install the demo scene, demo resources, and copied demo test:

```sh
godot-playwright module add /path/to/project quests --demo
```

The installer copies `res://addons/quests/`. It does not register an Autoload.

## Quest Definitions

Create one `QuestDefinition` Resource for each quest, tutorial chain, contract, challenge, milestone, or scenario goal. Use stable lowercase `quest_id` values such as `repair_beacon`, `deliver_supplies`, `tutorial_move`, or `daily_patrol`.

Each quest definition includes:

- `quest_id`: stable identifier used by scripts and save data.
- `display_name`: human-readable label.
- `description`: optional descriptive text.
- `tags`: optional labels such as `main`, `side`, `tutorial`, `daily`, or `contract`.
- `objectives`: ordered `ObjectiveDefinition` Resources for the quest.
- `completion_policy`: `all` requires every non-optional objective; `any` requires one non-optional objective.
- `auto_complete`: whether the quest completes as soon as the completion policy is satisfied.
- `start_active`: whether runtime state starts active after initialization.
- `rewards`: JSON-compatible reward data reported in completion results.
- `default_data`: JSON-compatible quest runtime data copied into runtime state.

Create one `ObjectiveDefinition` Resource for each step or counter. Use stable lowercase `objective_id` values such as `collect_parts`, `scan_beacon`, `talk_to_guard`, or `win_round`.

Each objective definition includes:

- `objective_id`: stable identifier used by scripts and save data.
- `display_name`: human-readable label.
- `description`: optional descriptive text.
- `tags`: optional labels such as `collect`, `talk`, `visit`, `kill`, or `craft`.
- `target_amount`: progress required for completion.
- `optional`: whether the objective is ignored by `completion_policy`.
- `hidden`: authoring hint for project UI; runtime state still includes the objective.
- `default_data`: JSON-compatible objective runtime data copied into runtime state.

Add quest definitions to a `QuestDatabase` Resource and assign that database to each `QuestLog` node.

## API

```gdscript
QuestLog.initialize_quests(reset: bool = false) -> Dictionary
QuestLog.has_quest(quest_id: String) -> bool
QuestLog.start_quest(quest_id: String, data: Dictionary = {}) -> Dictionary
QuestLog.advance_objective(quest_id: String, objective_id: String, amount: int = 1, data: Dictionary = {}) -> Dictionary
QuestLog.set_objective_progress(quest_id: String, objective_id: String, amount: int, data: Dictionary = {}) -> Dictionary
QuestLog.complete_objective(quest_id: String, objective_id: String, data: Dictionary = {}) -> Dictionary
QuestLog.complete_quest(quest_id: String, data: Dictionary = {}) -> Dictionary
QuestLog.fail_quest(quest_id: String, data: Dictionary = {}) -> Dictionary
QuestLog.set_quest_active(quest_id: String, active: bool) -> Dictionary
QuestLog.get_quest(quest_id: String) -> Dictionary
QuestLog.get_quests() -> Array
QuestLog.get_state() -> Dictionary
QuestLog.apply_state(data: Dictionary) -> Dictionary
```

Mutating calls return dictionaries with `ok`, `quest_id`, `objective_id`, `status`, `previous_status`, `progress`, `previous_progress`, `target_amount`, `clamped`, `quest`, `rewards`, `data`, `events`, `warnings`, and `errors` fields.

`QuestLog` emits `quest_started`, `quest_completed`, `quest_failed`, `quest_status_changed`, `objective_progress_changed`, `objective_completed`, and `quests_changed`.

## Explicit Progression

Prefer explicit progression from project code when gameplay actually satisfies an objective:

```gdscript
var started := quest_log.start_quest("repair_beacon")
if started.ok:
	var collected := quest_log.advance_objective("repair_beacon", "collect_parts", 1)
```

Use `set_objective_progress()` when project code already owns the absolute value:

```gdscript
quest_log.set_objective_progress("repair_beacon", "collect_parts", inventory.get_item_count("spare_part"))
```

Use `complete_objective()` for binary objectives:

```gdscript
quest_log.complete_objective("repair_beacon", "scan_beacon", {"scanner": "north"})
```

The module does not automatically listen to inventory changes, interactions, stats, abilities, effects, combat, dialogue, physics, input, UI, or state-machine transitions. Project scripts decide when an event should count.

## Completion Policy

`completion_policy = "all"` completes the quest when every non-optional objective is completed. Optional objectives can be completed and saved, but they do not block completion.

`completion_policy = "any"` completes the quest when at least one non-optional objective is completed. This is useful for route choices, branching goals, and fail-forward alternatives.

When `auto_complete` is true, completing an objective can complete the quest in the same mutation result. When `auto_complete` is false, project code calls `complete_quest()` after checking its own requirements.

## Rewards

Rewards are reported in successful quest completion results but the module does not automatically grant coins, items, stats, experience, abilities, effects, unlocks, or dialogue flags.

Apply rewards in project code after a successful completion result:

```gdscript
var result := quest_log.complete_quest("repair_beacon")
if result.ok:
	inventory.add_item("coin", int(result.rewards.get("coins", 0)))
```

Keep `rewards`, quest `default_data`, objective `default_data`, and mutation `data` JSON-compatible. Do not store Nodes, Resources, Callables, Signals, or cyclic containers.

## Saving

Use `get_state()` and `apply_state(data)` for JSON-compatible persistence. The saved state stores schema version, stable `quest_id` values, quest status, quest data, objective status, objective progress, target amounts, and objective data.

If the project also uses `save_load`, set a stable `save_id` on logs that should persist. Logs with a non-empty `save_id` join the `save_participants` group when they enter the tree and expose `save_state()` / `load_state(data)` wrappers. Set `save_id` before the node enters the tree so group membership is ready for `SaveService`.

Do not set `save_id` on temporary previews, generated encounters, or one-scene quest logs unless they must persist.

## Optional Integration

Interaction scripts can call `start_quest()`, `advance_objective()`, or `complete_objective()` after an accepted interaction.

Inventory scripts can count collected items and pass absolute counts to `set_objective_progress()`, or apply reported reward items after completion.

Stats scripts can gate quest completion with health, reputation, stamina, morale, hunger, heat, or other project values.

Abilities scripts can advance objectives when accepted ability activations complete scans, repairs, attacks, or movement actions.

Effects scripts can react to quest signals or add project-specific consequences after completion.

State-machine states can query `has_quest()`, `get_quest()`, or objective status to decide transitions or guards.

Dialogue and combat project code can call the public progression APIs when a line, branch, enemy, wave, or encounter should count.

The core module does not import `interaction`, `inventory`, `stats`, `abilities`, `effects`, `state_machine`, `save_load`, dialogue, combat, animation, input, UI, or AI files.

## Validation

```sh
godot-playwright check-scripts /path/to/project res://addons/quests --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/quests --exclude "addons/godot_playwright/**"
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```
