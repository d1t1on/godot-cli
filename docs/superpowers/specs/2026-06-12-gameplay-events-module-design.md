# Gameplay Events Module Design

Date: 2026-06-12

## Context

`godot-playwright` has reusable gameplay modules for JSON save/load,
inventory, state machines, interaction, stats, effects, abilities, and quests.
Those modules deliberately stay independent: quests do not listen to inventory,
abilities do not spend stats, effects do not apply damage, and interactions do
not directly mutate every possible gameplay system.

That boundary is useful, but agents repeatedly rebuild the same glue layer in
generated games: a generic way to announce that something happened, let other
systems react without direct imports, inspect recent events during tests, and
optionally defer reactions until a controlled point in the frame or turn.

This design adds `gameplay_events` as an installable gameplay module. It is a
small Resource-driven event bus for gameplay events such as item collection,
door opening, ability activation, quest progress, enemy defeat, dialogue
choice, puzzle state change, tutorial step completion, or stat depletion.

The module is an event declaration and dispatch layer. It does not implement a
rules engine, payload schema language, quest matcher, achievement system,
analytics service, UI notification system, dialogue system, combat pipeline, or
automatic integration with other modules.

## Goals

- Add `gameplay_events` as an installable gameplay module.
- Provide Resource-driven event definitions with stable IDs, display data,
  tags, JSON-compatible default payload, and default history recording policy.
- Provide a `GameplayEventBus` node that can be placed in scenes, level
  controllers, session controllers, player roots, or tests.
- Support synchronous event dispatch, optional queued dispatch, explicit queue
  flushing, per-event subscriptions, generic signals, history inspection,
  state export, and state import.
- Use structured dictionary results for expected failures and dispatch details.
- Keep event payloads and saved state JSON-compatible.
- Keep `save_load`, `inventory`, `stats`, `effects`, `abilities`, `quests`,
  `interaction`, and `state_machine` optional.
- Include a deterministic demo scene and copied Python test so agents can
  validate installation and behavior.
- Provide human and agent documentation for common usage patterns and
  validation.

## Non-Goals

- Do not build a rule engine, visual scripting graph, event reaction database,
  condition expression language, or automatic cross-module wiring in v1.
- Do not enforce payload schemas beyond JSON compatibility.
- Do not directly call inventory, stats, effects, abilities, quests,
  interaction, state-machine, save-load, combat, dialogue, animation, AI, UI, or
  analytics code.
- Do not automatically register an Autoload.
- Do not require events to be global. Multiple buses may exist in one project.
- Do not guarantee deterministic wall-clock timestamps across machines.
- Do not persist subscribers, because subscribers are object references.
- Do not store `Node`, `Resource`, `Callable`, `Signal`, or other engine objects
  in event definitions, payloads, queued events, history, or saved state.
- Do not build UI widgets, log viewers, notification toasts, localization
  tooling, icons, or debug overlays in v1.

## Chosen Approach

Use a lightweight `GameplayEventBus` node plus Godot Resource definitions.

Installation uses the existing module CLI:

```sh
godot-playwright module add <project> gameplay_events
godot-playwright module add <project> gameplay_events --demo
```

The module copies `res://addons/gameplay_events/` into the target project. It
does not register an Autoload. A game adds a `GameplayEventBus` node wherever
event routing should live, then assigns an `EventDatabase` resource containing
`EventDefinition` resources.

The first version provides both synchronous and queued dispatch. `emit_event()`
dispatches immediately and is the default path for simple gameplay logic.
`queue_event()` stores a JSON-compatible event in FIFO order. `flush_events()`
dispatches queued events explicitly. `auto_flush` can be enabled for projects
that want queued events flushed from `_process()`, but it defaults to `false`
for deterministic tests and turn-based games.

Subscribers are registered by stable `event_id`, target object, and method
name. The bus also emits generic signals so UI, tests, logging, and debugging
code can observe all events without registering per-ID callbacks.

This approach is preferred over a pure signal wrapper because Resource
definitions make project event vocabularies visible and reduce typo-prone
string usage. It is preferred over an event rules engine because v1 should stay
generic, inspectable, and independent from other gameplay modules.

## Repository Layout

Add a new module tree:

```text
gameplay_modules/gameplay_events/
  module.json
  README.md
  AGENT.md
  addons/gameplay_events/
    gameplay_event_bus.gd
    event_definition.gd
    event_database.gd
    gameplay_event_result.gd
    gameplay_event_constants.gd
  demo/
    scenes/
    scripts/
    resources/
  tests/
```

As with existing gameplay modules, package fallback copies should be kept
byte-identical under:

```text
godot_playwright/bundled_gameplay_modules/gameplay_events/
```

`module.json` describes the base copy operation and demo copy operation. The
module has no Autoload entries.

## Module Manifest

The manifest should follow the existing schema:

```json
{
  "name": "gameplay_events",
  "version": "0.1.0",
  "display_name": "Gameplay Events",
  "description": "Resource-driven gameplay event bus for Godot projects.",
  "godot_version": ">=4.6",
  "copy": [
    {"from": "addons/gameplay_events", "to": "addons/gameplay_events"}
  ],
  "autoloads": [],
  "demo": {
    "copy": [
      {"from": "demo/scenes", "to": "scenes/gameplay_events_demo"},
      {"from": "demo/scripts", "to": "scripts/gameplay_events_demo"},
      {"from": "demo/resources", "to": "resources/gameplay_events_demo"},
      {"from": "tests", "to": "tests/gameplay_events_demo"}
    ]
  },
  "validation": {
    "commands": [
      "godot-playwright check-scripts /path/to/project res://addons/gameplay_events --exclude addons/godot_playwright/**",
      "godot-playwright check-resources /path/to/project res://addons/gameplay_events --exclude addons/godot_playwright/**"
    ]
  }
}
```

## Runtime Components

`gameplay_event_bus.gd` defines `class_name GameplayEventBus` and extends
`Node`. It owns exported configuration, synchronous dispatch, queued dispatch,
subscriber registration, history, signals, structured results, and state
import/export.

`event_definition.gd` defines `class_name EventDefinition` and extends
`Resource`. It stores stable event configuration.

`event_database.gd` defines `class_name EventDatabase` and extends `Resource`.
It contains an exported array of `EventDefinition` resources and exposes
lookup/validation helpers. Event IDs must be unique and non-empty.

`gameplay_event_result.gd` holds structured result helpers so expected failures
return dictionaries instead of throwing exceptions.

`gameplay_event_constants.gd` holds schema version, module version, save group
name, event type names, and any shared string constants.

## Event Definition

The initial public fields on `EventDefinition` are:

```gdscript
@export var event_id: StringName
@export var display_name: String
@export_multiline var description: String
@export var tags: Array[StringName] = []
@export var default_payload: Dictionary = {}
@export var record_by_default: bool = true
```

`event_id` is the stable identifier used by scripts, queued events, saved
state, history, and tests. IDs should be lowercase and stable, such as
`item_collected`, `door_opened`, `quest_progressed`, `ability_activated`,
`enemy_defeated`, `dialogue_choice_selected`, `puzzle_solved`, or
`stat_depleted`.

`default_payload` is JSON-compatible data copied into each emitted event before
the caller payload is merged. Caller payload keys override default keys. This
lets a project define harmless defaults such as `{"quantity": 1}`,
`{"source": "unknown"}`, or `{"critical": false}` without requiring schema
validation in v1.

`record_by_default` controls whether events of this type are written to bus
history when `GameplayEventBus.record_history` is enabled and history capacity
allows it.

## Event Database

The initial public API on `EventDatabase` is:

```gdscript
@export var events: Array[Resource] = []

func has_event(event_id: String) -> bool
func get_event(event_id: String) -> Resource
func get_event_ids() -> Array[String]
func get_events() -> Array
func validate() -> Dictionary
```

The database normalizes event IDs with `strip_edges()`. Empty event IDs are
invalid. Duplicate IDs are invalid. `get_events()` returns definitions in
authoring order. Lookup helpers return `null`, `false`, or empty arrays for
invalid input instead of throwing exceptions.

`validate()` returns a structured result with warnings and errors. It should be
used by the bus before dispatch and by tests when checking authored resources.

## GameplayEventBus API

The initial public API on `GameplayEventBus` is:

```gdscript
@export var database: Resource
@export var save_id: StringName
@export var record_history: bool = true
@export_range(0, 10000, 1) var max_history: int = 100
@export var save_history: bool = false
@export var auto_flush: bool = false
@export_range(0, 10000, 1) var auto_flush_limit: int = 0

func emit_event(event_id: String, payload: Dictionary = {}) -> Dictionary
func queue_event(event_id: String, payload: Dictionary = {}) -> Dictionary
func flush_events(limit: int = 0) -> Array[Dictionary]
func clear_queue() -> void

func subscribe(event_id: String, target: Object, method: StringName) -> Dictionary
func unsubscribe(event_id: String, target: Object, method: StringName) -> Dictionary
func clear_subscribers(event_id: String = "") -> void

func has_event(event_id: String) -> bool
func get_event_definition(event_id: String) -> Resource
func get_event_ids() -> Array[String]

func get_history(limit: int = 0) -> Array
func clear_history() -> void

func get_state() -> Dictionary
func apply_state(data: Dictionary) -> Dictionary
```

`database` must expose the `EventDatabase` protocol. The exported type can
remain `Resource` to match the existing inventory, stats, effects, abilities,
and quests module style.

`save_id` is optional. When non-empty, the bus joins the shared save participant
group and exposes `get_save_id()`, `save_state()`, and `load_state(data)`
wrappers compatible with `save_load`. Buses with empty `save_id` do not
automatically persist.

`record_history` controls whether emitted events can enter history.
`max_history` limits retained history. `max_history = 0` disables history
retention even when `record_history = true`.

`save_history` controls whether retained history is included in exported state.
It defaults to `false` to avoid growing save files with debug-style data.

`auto_flush` controls whether `_process(delta)` calls `flush_events()` for
queued events. It defaults to `false`. If `auto_flush_limit = 0`, auto-flush
drains the whole queue. Otherwise it dispatches at most that many queued events
per frame.

## Signals

`GameplayEventBus` emits:

```gdscript
signal event_emitted(event_id: String, event: Dictionary, result: Dictionary)
signal event_queued(event_id: String, event: Dictionary, result: Dictionary)
signal event_failed(event_id: String, result: Dictionary)
signal queue_flushed(events: Array)
signal events_changed(event: Dictionary)
```

`event_emitted` fires after an event is accepted and recorded in history, before
subscriber callback processing. The dispatch order is: validate, create event,
record history, emit `event_emitted`, call subscribers, emit `events_changed`.

`event_queued` fires when an event is accepted into the queue. It does not mean
subscribers have been called.

`event_failed` fires for known expected failures, including unknown event IDs,
invalid payloads, invalid databases, and listener failures.

`queue_flushed` fires after `flush_events()` finishes and includes the emitted
event dictionaries for successful dispatches.

`events_changed` is a generic signal for UI, debug panels, logs, and tests.

## Event Data Model

Accepted emitted and queued events use JSON-compatible dictionaries:

```json
{
  "event_id": "item_collected",
  "payload": {
    "item_id": "coin",
    "quantity": 1
  },
  "sequence": 12,
  "queued": false,
  "timestamp_msec": 123456
}
```

`event_id` is normalized with `strip_edges()`.

`payload` is a deep copy of `EventDefinition.default_payload` overlaid with a
deep copy of the caller payload. Caller keys win.

`sequence` is a bus-local monotonically increasing integer assigned when an
event is accepted by `emit_event()` or `queue_event()`. Queued events keep their
original sequence when later flushed.

`queued` is `false` for immediate `emit_event()` calls and `true` while stored
in the queue. When a queued event is flushed, the event passed to subscribers
should preserve the original sequence and include a flag that makes its origin
inspectable. The simplest v1 shape is to keep `queued = true`.

`timestamp_msec` is captured from `Time.get_ticks_msec()` when the event is
accepted. It is for local ordering and debugging only, not cross-machine
determinism.

## Dispatch Flow

`emit_event(event_id, payload)` performs these steps:

1. Normalize `event_id`.
2. Validate non-empty event ID, configured database, known event definition, and
   JSON-compatible payload.
3. Copy and merge default payload with caller payload.
4. Increment the bus sequence and create an event dictionary.
5. Record history if allowed by `record_history`, `max_history`, and the event
   definition's `record_by_default`.
6. Emit `event_emitted`.
7. Invoke subscribers registered for the event ID.
8. Add subscriber errors to the result without aborting remaining subscribers.
9. Emit `event_failed` if any subscriber error made the result fail.
10. Emit `events_changed`.
11. Return a structured result.

The result includes:

```gdscript
{
  "ok": true,
  "event_id": "item_collected",
  "payload": {"item_id": "coin", "quantity": 1},
  "event": {},
  "subscriber_count": 2,
  "warnings": [],
  "errors": [],
  "events": []
}
```

The actual `event` field contains the emitted event dictionary. The `events`
array holds generic result events such as `event_emitted`,
`event_queued`, `queue_flushed`, or `event_failed`.

## Queue Flow

`queue_event(event_id, payload)` performs the same validation and event creation
as `emit_event()`, but stores the event in `_queue` instead of calling
subscribers. It emits `event_queued` and `events_changed`, then returns a
structured result. Queueing an event should not write it to history until the
event is flushed and emitted.

`flush_events(limit)` dispatches queued events in FIFO order.

`limit = 0` means drain the whole queue. A positive `limit` dispatches at most
that many events and leaves the rest queued. Negative limits are invalid and
return an empty result array with a warning or failure event.

Each flushed event is dispatched through the same subscriber path as
`emit_event()`, preserving the queued event's `sequence`, `timestamp_msec`, and
merged payload. `flush_events()` returns the per-event dispatch results.

`clear_queue()` removes queued events without dispatching them and emits an
`events_changed` event when the queue was not empty.

## Subscriber Model

`subscribe(event_id, target, method)` registers a callback for a single event
ID. Callback methods receive one argument:

```gdscript
func _on_item_collected(event: Dictionary) -> void:
    pass
```

This stable one-argument shape is easier for generated code than variable
payload parameters.

The bus validates that:

- `event_id` is non-empty and known.
- `target` is not `null`.
- `method` is non-empty.
- `target.has_method(method)` is true.

Duplicate subscriptions for the same event ID, target instance, and method are
ignored and return a successful result with a warning.

`unsubscribe()` removes a matching subscription. Removing a missing
subscription is a successful no-op with a warning.

`clear_subscribers("")` clears all subscribers. `clear_subscribers(event_id)`
clears subscribers for one event ID.

Subscribers are runtime object references and are not included in
`get_state()`.

## State And Save Load

`get_state()` returns JSON-compatible data:

```json
{
  "schema_version": 1,
  "sequence": 12,
  "queue": [],
  "history": []
}
```

`queue` contains queued event dictionaries that have not yet been flushed.

`history` contains retained emitted event dictionaries only when
`save_history = true`. When `save_history = false`, `get_state()` returns an
empty history array even if runtime history exists. This keeps ordinary save
files small while preserving a stable state shape.

`apply_state(data)` restores schema version, sequence, queue, and history. It
validates that queued and history events are JSON-compatible dictionaries with
known event IDs. Invalid entries fail the result instead of partially applying
state.

If the project also uses `save_load`, set a stable `save_id` on buses that
should persist queued events or sequence state. Buses with non-empty `save_id`
join the `save_participants` group when they enter the tree and expose
`save_state()` / `load_state(data)` wrappers. Set `save_id` before the node
enters the tree so group membership is ready for `SaveService`.

Do not set `save_id` on temporary debug buses, scene-local buses, or test-only
buses unless their queued event state must persist.

## Structured Results

Result dictionaries should use the same conventions as existing gameplay
modules:

```gdscript
{
  "ok": false,
  "event_id": "item_collected",
  "payload": {},
  "event": {},
  "subscriber_count": 0,
  "warnings": [],
  "errors": ["Unknown event_id: item_collected"],
  "events": []
}
```

Expected failures return `ok = false` and populate `errors`. Recoverable or
idempotent conditions return `ok = true` and populate `warnings`.

Mutating methods should include enough detail for tests and generated game code
to make decisions without string-parsing warnings or errors.

## Error Handling

Expected failures include:

- Empty `event_id`.
- Missing database.
- Database missing required methods.
- Unknown event ID.
- Invalid or duplicate event definitions.
- Payload, default payload, queued event, or history event is not
  JSON-compatible.
- `subscribe()` target is `null`.
- `subscribe()` method is empty or missing on the target.
- Subscriber callback fails or is no longer valid during dispatch.
- `flush_events(limit)` receives a negative limit.
- `apply_state()` receives malformed state.

The module should not throw exceptions for these cases. It should return
structured failures and emit `event_failed` where appropriate.

Listener failures should not prevent remaining listeners for the same event from
running. The dispatch result records the failure and reports `ok = false` after
all listeners have been attempted.

## Optional Integration

Project scripts can call `emit_event()` after meaningful actions:

- Inventory scripts can emit `item_collected`, `item_removed`, or
  `item_used`.
- Interaction scripts can emit `door_opened`, `npc_talked_to`, or
  `pickup_used`.
- Ability scripts can emit `ability_activated` after a successful activation.
- Effects scripts can emit `effect_applied`, `effect_ticked`, or
  `effect_expired`.
- Stats scripts can emit `stat_depleted`, `stat_filled`, or `stat_changed`.
- Quest scripts can subscribe to project events and explicitly call quest APIs
  when an event should count.
- UI and debug scripts can listen to `event_emitted` or inspect history.

The core module does not import or require any of those modules.

## Demo

The demo should install resources and a scene under:

```text
scenes/gameplay_events_demo/
scripts/gameplay_events_demo/
resources/gameplay_events_demo/
tests/gameplay_events_demo/
```

Suggested demo events:

- `item_collected` with default payload `{"quantity": 1}`.
- `door_opened` with default payload `{"locked": false}`.
- `quest_progressed` with default payload `{"amount": 1}`.

The demo scene should contain a `GameplayEventBus` with an assigned
`EventDatabase`. The demo script should:

1. Subscribe to `item_collected`.
2. Emit `item_collected` synchronously.
3. Queue `door_opened` and `quest_progressed`.
4. Flush queued events.
5. Inspect history.
6. Print or expose deterministic labels that the copied Python test can assert.

The demo should not require `inventory`, `quests`, `interaction`, or any other
gameplay module.

## Tests

Add a copied demo test under `gameplay_modules/gameplay_events/tests/` and keep
the bundled copy byte-identical.

Test coverage should include:

- Event database lookup, validation, empty IDs, and duplicate IDs.
- `emit_event()` merges default payload with caller payload.
- Unknown events fail with structured errors.
- Non-JSON-compatible payloads fail.
- `subscribe()` validates target and method.
- `subscribe()` ignores duplicates with a warning.
- `unsubscribe()` removes callbacks.
- Subscriber callbacks receive one event dictionary.
- Subscriber failures are recorded without skipping later subscribers.
- `queue_event()` preserves FIFO order.
- `flush_events(limit)` leaves unflushed events queued.
- `auto_flush = false` leaves queued events untouched during idle frames.
- `max_history` trims older events.
- `max_history = 0` disables history retention.
- `get_state()` / `apply_state()` restore sequence and queue.
- `save_history = false` omits runtime history from exported state.
- `save_history = true` includes retained history in exported state.
- The demo scene runs and produces expected observable output.

Validation commands should mirror existing modules:

```sh
godot-playwright check-scripts /path/to/project res://addons/gameplay_events --exclude "addons/godot_playwright/**"
godot-playwright check-resources /path/to/project res://addons/gameplay_events --exclude "addons/godot_playwright/**"
godot-playwright validate /path/to/project --exclude "addons/godot_playwright/**"
```

## Documentation

`README.md` should explain:

- Installation with and without demo.
- How to create `EventDefinition` and `EventDatabase` resources.
- How to add a `GameplayEventBus` node to a scene.
- The difference between `emit_event()`, `queue_event()`, and
  `flush_events()`.
- How to subscribe to one event ID.
- How history and saved state work.
- Why the module does not directly integrate with other gameplay modules.
- Validation commands.

`AGENT.md` should give agents concise usage guidance:

- Prefer stable lowercase event IDs.
- Keep payloads JSON-compatible.
- Use explicit project code for cross-module consequences.
- Use `queue_event()` when event order should be controlled.
- Do not store engine objects in payloads or history.
- Do not assume a global Autoload unless the project created one.

## Implementation Notes

Use GDScript style consistent with existing gameplay modules:

- `class_name` on public Resource and Node classes.
- Exported `database: Resource` for assignment flexibility.
- Structured dictionary results with `ok`, `warnings`, `errors`, and `events`.
- Defensive copies for returned events, history, queue, and payloads.
- `String(event_id).strip_edges()` normalization.
- `_is_json_compatible()` helper equivalent to other modules.
- `get_save_id()`, `save_state()`, and `load_state(data)` wrappers when
  `save_id` is non-empty.
- No direct dependencies on other gameplay modules.

The implementation should keep the bus small enough for agents to reason about.
If subscriber management, state parsing, or JSON validation begins to dominate
the file, extract only narrowly scoped helpers that match existing module style.
