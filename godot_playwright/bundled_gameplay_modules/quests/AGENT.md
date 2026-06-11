# Agent Instructions: quests

Use this module when a Godot project needs quests, objectives, tutorial steps, contracts, milestones, challenges, or scenario goals.

Install with:

```sh
godot-playwright module add /path/to/project quests
```

Use `--demo` only when adding a demo scene, demo resources, and copied test is acceptable:

```sh
godot-playwright module add /path/to/project quests --demo
```

## Wiring Quests

1. Create one `ObjectiveDefinition` Resource per objective.
2. Create one `QuestDefinition` Resource per quest and attach its objectives.
3. Use stable lowercase `quest_id` and `objective_id` values. Do not rename IDs after save data exists unless you also migrate saves.
4. Add quest definitions to a `QuestDatabase` Resource.
5. Add a `QuestLog` node to the scene or actor that owns quest state.
6. Assign the database and set a stable `save_id` only when this log should persist through `save_load`.

## Progression

Prefer explicit progression. Project code calls `start_quest()`, `advance_objective()`, `set_objective_progress()`, `complete_objective()`, `complete_quest()`, or `fail_quest()` only when gameplay should count toward a quest.

Do not add hidden listeners that automatically watch inventory, interaction, stats, abilities, effects, dialogue, combat, input, UI, or state machines. Those systems should call the public API when they accept an event.

Rewards are reported in completion results, not automatically granted. Spend or grant items, currency, stats, abilities, effects, unlocks, or flags in project code after checking `result.ok`.

## Boundaries

Do not add hidden dependencies on other modules. The module can coordinate with `interaction`, `inventory`, `stats`, `abilities`, `effects`, `state_machine`, and `save_load` through IDs, result dictionaries, signals, and saved state, but it must not import those modules.

Rewards, quest runtime data, objective runtime data, mutation data, and saved state must be JSON-compatible. Use strings, numbers, booleans, nulls, arrays, and dictionaries with string keys. Do not store Nodes, Resources, Callables, Signals, UI references, or cyclic containers.

Use `completion_policy = "all"` when every required objective must finish. Use `completion_policy = "any"` for route choices or alternatives. Optional objectives do not block either policy.

## Saving

The module does not require `save_load`. For custom persistence, use `get_state()` and `apply_state(data)`.

When the project uses `save_load`, set a stable `save_id` before the node enters the tree so the `QuestLog` joins the `save_participants` group.

Preserve byte-identical source and bundled trees when editing this module:

```sh
diff -qr gameplay_modules/quests godot_playwright/bundled_gameplay_modules/quests
```

## Validation Commands

```sh
godot-playwright check-scripts /path/to/project res://addons/quests --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/quests --exclude "addons/godot_playwright/**"
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```
