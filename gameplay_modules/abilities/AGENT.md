# Agent Instructions: abilities

Use this module when a Godot project needs instant actions such as dashes, attacks, scans, repairs, reloads, build commands, tool uses, or unit commands with cooldowns, charges, enabled state, and structured activation results.

Install with:

```sh
godot-playwright module add /path/to/project abilities
```

Use `--demo` only when adding a demo scene, demo resources, and copied test is acceptable:

```sh
godot-playwright module add /path/to/project abilities --demo
```

## Wiring Abilities

1. Create one `AbilityDefinition` Resource per action.
2. Use stable `ability_id` values. Do not rename `ability_id` values after save data exists unless you also migrate saves.
3. Configure cooldown, charges, enabled state, `costs`, and JSON-compatible `default_data`.
4. Add definitions to an `AbilityDatabase` Resource.
5. Add an `AbilityContainer` node to each gameplay object that can request abilities.
6. Assign the database and choose whether `auto_update` should advance cooldown and charge timers automatically.

## Using Abilities

Call `AbilityContainer.can_activate(ability_id, context)` for guards before accepting player input, AI requests, interactions, UI commands, or state-machine transitions. Call `AbilityContainer.activate(ability_id, context)` only for accepted requests.

Abilities are instant in v1. They validate known `ability_id` values, enabled state, cooldown, charges, and JSON-compatible context, then return structured result dictionaries.

Costs are reported, not automatically spent. Spend stamina, mana, ammo, inventory items, or other resources in project code before or around `activate()`.

## Boundaries

Do not use this module as a combat system, animation system, input buffer, AI planner, resource wallet, targeting system, or effect applicator. Keep combat, animation, input, AI decisions, resource spending, and effect application outside the module.

The `abilities` module can coordinate with `stats`, `inventory`, `effects`, `interaction`, `state_machine`, and `save_load` through IDs, result dictionaries, signals, and saved state, but it does not depend on those modules.

Do not store engine objects in `default_data`, activation `context`, or saved state. Use JSON-compatible values only, not Nodes, Resources, Callables, Signals, or cyclic containers.

## Saving

The module does not require `save_load`. For custom persistence, use `get_state()` and `apply_state(data)`.

When the project uses `save_load`, set a stable `save_id` on containers that should persist. Set `save_id` before the node enters the tree so the container joins the `save_participants` group for `SaveService`.

Do not set `save_id` on temporary ability previews, generated one-shot actors, or one-scene objects unless they must persist.

## Validation Commands

Run targeted checks after installation:

```sh
godot-playwright check-scripts /path/to/project res://addons/abilities --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/abilities --exclude "addons/godot_playwright/**"
```

Run broader validation after wiring game scenes:

```sh
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```

If using `SaveService`, run a save/load round-trip test that mutates cooldowns, charges, and enabled state after save and verifies the original ability runtime is restored after load.
