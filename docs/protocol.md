# Protocol

Godot Playwright uses local HTTP JSON-RPC over loopback.

- Health endpoint: `GET /health`
- RPC endpoint: `POST /rpc`
- Default bind: `127.0.0.1:9777`
- Non-strict add-on launches fall back to an available port if the requested
  port is busy. Python/CLI launches use strict explicit ports and auto-allocated
  default ports for live sessions.

RPC requests:

```json
{"jsonrpc":"2.0","id":1,"method":"engine.info","params":{}}
```

RPC success:

```json
{"jsonrpc":"2.0","id":1,"result":{}}
```

RPC error:

```json
{"jsonrpc":"2.0","id":1,"error":{"code":-32000,"message":"..."}}
```

The Python package also includes local command runners outside JSON-RPC.
`Godot(..., capture_logs=True)` captures Godot stdout/stderr in the Python
launcher while the process is running and attaches it to the returned
`GodotClient`. `log_events()`, `wait_for_log()`, `log_text()`, `log_clear()`,
and `expect_log()` provide Playwright-style live log observation without adding
an RPC method, including positive and negative error/warning gates. The CLI
runner still tees the same output into per-test Godot log files.
`run_tests(project, tests=[...])` and `godot-playwright test` discover Python
automation tests, support regex selection with `grep`/`--grep`, inverted
selection, deterministic `current/total` sharding, and list-only planning that
does not launch Godot. Test retries mark fail-then-pass results as flaky and
preserve per-attempt artifacts for debugging. Per-test timeout guards fail stuck
test attempts while still collecting the runner's diagnostics and artifacts.
Python stdout/stderr emitted by test functions and hooks is captured per
attempt, written to `python_stdout`/`python_stderr` artifacts when non-empty,
and summarized in JSON results, diagnostics, text output, and HTML reports.
`max_failures=N` stops launching more default single-worker isolated tests after
N failed results and records the remaining selected tests as `interrupted`.
`max_failures` currently rejects reuse-Godot and multi-worker modes rather than
misreporting tests that may already be running.
`junit_xml="path/to/report.xml"` writes a JUnit XML integration report with
pass/fail/skipped/interrupted outcomes, failure tracebacks, stdout/stderr tails,
and artifact path properties for CI and agent orchestration systems.
Parallel workers run isolated per-test Godot processes concurrently and merge
results back into one deterministic report; reuse-Godot mode remains a single
shared-process mode and does not combine with multiple workers.
`screenshots="only-on-failure"` or `screenshots="on"` captures viewport PNG
artifacts for launched test attempts and links them from JSON, diagnostics, text
output, and HTML. Capture failures, including headless display limitations, are
recorded as diagnostic errors instead of replacing the original test result.
The runner exposes a `step` fixture for Playwright-style intent steps. Step
records include title, status, duration, nesting depth, and step-local failure
metadata, and are written into JSON results, diagnostics, and HTML reports.
The `soft_expect` fixture wraps locator expectations and records assertion
failures without stopping the test immediately. Recorded soft assertions are
included in JSON results, diagnostics, JUnit XML, text output, and HTML reports;
if no hard failure or runtime skip happens, the runner raises a combined
`SoftAssertionError` after the test body and `after_each` hooks finish.
The `expect_poll` fixture retries arbitrary Python callables until equality,
inequality, truthy/falsy, or custom predicate expectations pass. Timeout
failures include the last observed return value or last callable error, then use
the same runner failure diagnostics and report artifacts as other assertions.
The `test_info` fixture provides per-test metadata, `output_path(...)`, and
`attach(...)`; the shorter `attach(...)` fixture writes or copies custom text,
bytes, JSON-like bodies, or files into per-test artifact directories and links
them from JSON results, diagnostics, text output, and HTML reports.
Module-level `before_each` and `after_each` hooks run with the same fixture
injection as tests. `after_each` runs after passed, failed, and runtime-skipped
tests, so hook steps and attachments are preserved in runner artifacts.
Python decorators `skip()` and `expected_failure()` add Playwright-style test
annotations: skipped tests are recorded without launching Godot, expected
failures are green when they fail, and unexpected passes are reported as
failures. Tests can also call `test_info.skip("reason")` after runtime or editor
inspection; those skips preserve evidence gathered before the skip, do not
retry, and are counted as skipped instead of failed.
`generate_test_from_trace(trace)` and `godot-playwright codegen-trace` turn
saved trace JSON artifacts into editable Python tests. Supported trace actions
are replayed as client calls, while unsupported events are preserved as comments
for agent review. The trace/codegen coverage test verifies the live addon event
surface: 116 emitted event types replay as helper calls, while `rpc`,
`trace.start`, and `trace.stop` are intentionally treated as infrastructure
events.
`probe_project(project, scene="...")` and `godot-playwright probe` launch a
runtime scene briefly with `--quit-after`, capture Godot output, and summarize
logged errors/warnings so agents can catch startup/runtime failures.
`probe_project_scenes(project, scenes=[...])` and `godot-playwright
probe-scenes` discover `.tscn`/`.scn` files, launch each scene with the same
single-scene probe primitive, and aggregate per-scene pass/fail counts plus log
diagnostics. Scene discovery supports selected paths and exclude globs.
`check_script(project, script_path)` and `godot-playwright check-script` warm
Godot's import/global-class cache by default, then run `--check-only --script`
and return structured diagnostics.
`expect_script_file(project, script_path)` provides Playwright-style assertions
for generated GDScript files, including file existence, source text, `extends`,
`class_name`, function definitions, Godot parser success, and expected
diagnostics.
`check_project_scripts(project, paths=[...])` and `godot-playwright
check-scripts` discover `.gd` files, aggregate per-script parser reports, and
support exclude globs. Pass `--no-import-cache` only to skip the pre-check cache
warmup. `check_project_resources(project, paths=[...])` and
`godot-playwright check-resources` discover text `.tscn`/`.tres` resources,
parse external resource paths, and report missing dependencies before runtime or
export. `inspect_scene(project, scene_path)` and `godot-playwright
inspect-scene` parse text `.tscn` files into a structured node/resource snapshot
without launching Godot, which lets agents review generated scene structure in
CI or before opening the editor. `expect_scene_file(project, scene_path)`
provides Playwright-style assertions over those saved scene files, including
root nodes, node filters, scripts, groups, instances, external resources, and
signal connections. `inspect_project(project)` and
`godot-playwright inspect-project` parse `project.godot`,
`export_presets.cfg`, autoloads, main scene, and project files into a structured
inventory for planning agent edits. File inventories include aggregate byte
counts, extension counts/bytes, category counts/bytes, directory hot spots,
top directories, path depth, largest files, newest files, and a `scale` summary
that helps agents estimate scan and validation cost. `validate_project(project)` and
`godot-playwright validate` aggregate project inventory, script checks, resource
checks, scene inspection, and runtime scene probes into one project-level validation report,
while preserving the underlying per-check reports for debugging. Validation
reports also expose the inventory `scale` summary at the top level.
`find_project_nodes(project)` and `godot-playwright find-nodes` query text
`.tscn` files with node-level selector predicates such as role, test id, text,
name, type/class, path, metadata, and properties before launching Godot.
`export_project(project, preset, output_path,
mode="release")` and `godot-playwright export` run Godot's `--export-release`,
`--export-debug`, `--export-pack`, or `--export-patch` command and return a
structured report with command, exit code, output artifact state, log path,
duration, and stdout tail. Export reports include export preset preflight
metadata, `preset_found` / `preset_state`, `preset_export_path`,
`output_relative_path`, `output_matches_preset`, `output_changed`, and
structured Godot log diagnostics so agents can distinguish missing presets,
path mismatches, Godot failures, and stale artifacts.

## Selectors

Selectors can be strings or dictionaries.

String selectors:

- `#Name`: node name
- `.group_name`: first node in group
- `type=Button`: first node whose Godot class matches
- `role=button`: first node with the inferred accessible role
- `test_id=counter-button`: first node whose `test_id` metadata equals this value
- `testid=counter-button`: alias for `test_id=...`
- `name=Player`: first node with this name
- `text=Start`: first node whose `text` property equals this value
- `text*=Play`: first node whose `text` property contains this value
- `placeholder=Name`: first node whose `placeholder_text` property equals this value
- `placeholder*=Nam`: first node whose `placeholder_text` property contains this value
- `tooltip=Save`: first node whose `tooltip_text` property equals this value
- `tooltip*=Sav`: first node whose `tooltip_text` property contains this value
- `/root/Main/Button`: absolute NodePath
- `Button`: fallback name or class match

Dictionary selectors:

```json
{"name":"CounterButton"}
{"type":"Button"}
{"role":"button"}
{"role":"button","role_name":"Clicked 0"}
{"role":"textbox","name_contains":"Nam"}
{"test_id":"counter-button"}
{"metadata":{"test_id":"counter-button"}}
{"group":"enemies"}
{"path":"/root/Main/CounterButton"}
{"type":"Button","text":"Clicked 0"}
{"property":"text","contains":"Clicked"}
{"properties":{"text":"Clicked 0","disabled":false}}
{"all":["role=button",{"test_id":"counter-button"}]}
{"any":[{"test_id":"counter-button"},{"test_id":"name-input"}]}
{"not":{"test_id":"debug-only"}}
{"base":"role=button","has_text":"Clicked","has_not_text":"Next"}
{"base":{"type":"Control"},"has":{"test_id":"counter-button"}}
{"base":{"type":"Control"},"has_not":{"test_id":"debug-only"}}
```

Role selectors infer common UI roles from Godot classes, including `button`,
`checkbox`, `combobox`, `textbox`, `text`, `slider`, `spinbutton`, `progressbar`,
`list`, `tablist`, `tabpanel`, `menu`, `window`, `panel`, and `control`. Accessible names
come from non-empty `text`, `placeholder_text`, `tooltip_text`, and the node name.
Test-id selectors read Godot node metadata. The Python `get_by_test_id()` helper
uses `metadata/test_id` by default and can target another metadata key when needed.
The static `find-nodes` index supports node-level selector predicates over text
`.tscn` files and reports scene-local node paths; group membership and
descendant filter selectors still require the live Godot locator engine.

Boolean selector dictionaries can combine node-level predicates. `all` and `and`
require every nested selector to match the same node; `any` and `or` accept any
nested selector; `not` rejects nodes that match its nested selector. The Python
`Locator.and_()` and `Locator.or_()` helpers build the common intersection and
union forms while preserving the locator root.

Filter dictionaries combine a `base` selector with descendant or text constraints.
`has_text`, `has_text_exact`, and `has_not_text` check the matched node and its
descendants using accessible names. `has` and `has_not` check descendant nodes
against another selector. The Python `Locator.filter()` helper builds these
dictionaries while preserving the locator root.

Most RPC methods accept `root` to limit traversal. Use `edited`, `scene`, `editor`,
`root`, a NodePath string, a selector dictionary, or a locator-root dictionary like
`{"selector":"#Inventory","root":"edited"}`. The `editor` root maps to the editor
base Control when the add-on is running in editor mode.

The Python client implements Playwright-style locator waiting on top of
`node.find` and `node.state`. `Locator.wait_for(state=...)` supports `attached`,
`detached`, `visible`, and `hidden`; hidden passes for either a detached node or a
matched node whose `visible_in_tree` state is false. `expect(locator)` exposes
matching positive and negative assertions.

## RPC Methods

- `protocol.describe`: describe the live automation protocol, including server
  version, transport endpoints, Godot/editor mode, supported RPC methods,
  methods grouped by domain, feature tags, and suggested Python helper names.
  Python exposes `protocol_describe(...)` so agents can discover the connected
  server's capability surface before choosing editor, runtime, resource, trace,
  or filesystem actions.
- `engine.info`: Godot version, project path, mode, server uptime. Python
  helpers include `engine_info()`, `wait_for_engine_info(...)`, and
  `expect_engine(godot)` assertions for editor/runtime mode, Godot version,
  project path, server port, and arbitrary nested info fields.
- `runtime.clock`: process frame count, physics frame count, drawn frame count,
  physics tick rate, time scale, and server uptime. Python helpers use this for
  `wait_for_process_frames()`, `wait_for_physics_frames()`, and
  `wait_for_idle()`.
- `runtime.pause`, `runtime.resume`, `runtime.step_frames`, and
  `runtime.sample_frames`: deterministic frame control for realtime gameplay
  checks. Python exposes these as `pause()`, `resume()`, `step_frames()`, and
  `sample_frames()`; prefer compact state samples over long screenshot runs.
- `runtime.evaluate`: evaluate a Godot `Expression` against a root node. Inputs
  include `tree`, `root`, and caller-provided `variables`; Python exposes this as
  `evaluate()` and polling `wait_for_function()`.
- `animation.describe`: inspect an `AnimationPlayer`, including available
  animations, current/assigned animation, position, length, playback state, and
  optional track summaries.
- `animation.play`, `animation.stop`, `animation.pause`, `animation.seek`, and
  `animation.advance`: deterministic `AnimationPlayer` control for tests.
  `advance` moves the current timeline by seeking to `position + delta`, which is
  stable for automation even when playback speed is zero.
  Locator expectations can assert available animations, selected track fields,
  and current playback state with `to_have_animation(...)` and
  `to_be_playing_animation(...)`.
- `physics2d.point`: query the active 2D physics world at one viewport/world
  coordinate and return matching bodies or areas.
- `physics2d.ray`: ray-cast through the active 2D physics world and return the
  first hit. Python exposes `expect_physics2d(godot)` for point/ray collision
  assertions by collider name, path, class, groups, metadata, or result fields.
- `physics3d.point`: query the active 3D physics world at one world coordinate
  and return matching bodies or areas.
- `physics3d.ray`: ray-cast through the active 3D physics world and return the
  first hit. Python exposes `expect_physics3d(godot)` with the same collider
  filters as the 2D helper.
- `camera3d.ray`: project a viewport screen coordinate through a `Camera3D` and
  return the world-space origin, direction, and ray endpoint.
- `camera3d.pick`: project a `Camera3D` screen ray and ray-cast through the 3D
  physics world. Python exposes `camera3d_pick(...)` and
  `expect_physics3d(godot).to_pick_camera_collision(...)` for screen-coordinate
  3D picking assertions. Camera locators also expose `camera3d_ray(...)`,
  `camera3d_pick(...)`/`pick_3d(...)`, and
  `expect(camera_locator).to_pick_camera_collision(...)`. Locator-level
  `hover_3d(...)`, `click_3d(...)`, and `drag_3d(...)` wait for a matching pick
  before sending viewport mouse input; the addon supplements 3D
  `CollisionObject3D.input_event` dispatch under the headless display driver so
  these actions are testable in CI.
- `audio.bus.info`: query `AudioServer` bus state by name or index. Parameters:
  `bus_name` (String, optional) resolves a bus by name and takes precedence
  over `bus_index`; `bus_index` (int, optional, default `0`) resolves a bus by
  index. The response is a bus snapshot with `index`, `name`, `volume_db`,
  `muted`, `solo`, `effect_count`, `effects` array, `send_target`, and
  `children` array. Python exposes `expect_audio(godot)` for retryable
  playback state, bus volume, bus mute, bus solo, AudioStreamPlayer pitch, and
  AudioStreamPlayer volume_db assertions.
- `navigation.query_path`: query navigation path reachability through
  `NavigationServer`. Parameters: `start_x`, `start_y`, `start_z` (float) for
  the start position (z ignored for 2D); `target_x`, `target_y`, `target_z`
  (float) for the target position (z ignored for 2D); `dimension` (int,
  default `3`) selects 2D or 3D; `navigation_layers` (int, optional) is a
  layer bitmask filter. The response includes `reachable`, `points`,
  `point_count`, `path_length`, `start`, `target`, and `dimension`. Python
  exposes `expect_navigation(godot)` for retryable reachability, path length,
  NavigationAgent target-reached, NavigationAgent target distance,
  NavigationRegion mesh, and NavigationRegion enabled assertions.
- `tree.snapshot`: JSON snapshot of a subtree. Python exposes whole-scene
  snapshots through `godot.snapshot(...)` and locator-scoped snapshots through
  `locator.snapshot(...)`, `snapshot_nodes()`, `snapshot_texts()`,
  `expect(locator).to_contain_node(...)`, and
  `expect(locator).to_contain_text(...)`.
- `node.find`: find matching nodes. Python exposes exact, minimum, maximum,
  range, empty, and non-empty locator count waits/assertions on top of this.
- `node.describe`: describe one node, including path, parent, child index,
  selected properties, public method names, public signal names, popup menu
  details, and dialog details. Python exposes `locator.methods()`,
  `locator.signals()`, `expect(locator).to_have_method(...)`,
  `expect(locator).to_have_signal(...)`, `expect(locator).to_match_node(...)`,
  `to_have_parent(...)`, `to_have_index(...)`, and `to_have_child_count(...)`
  on top of this payload.
- `node.state`: return Playwright-style actionability state for one node, including
  visibility, enabled/disabled, editable, focused/focusable, bounds, input
  hit-testability, checked state, text, and form value. Python exposes arbitrary
  state-map waits and `expect(locator)` assertions for direct actionability
  fields such as focusable and receives-input state.
- `node.bounds`: return a Control global rect or a Node2D point. Python exposes
  this through `locator.bounds()`, `locator.center()`, geometry waits, and
  `expect(locator)` assertions for bounds, position, size, center, and viewport
  containment.
- `node.click`: activate a node. BaseButton nodes use their pressed signal; other
  2D nodes receive viewport mouse events at their bounds center.
- `node.dialog`: describe an `AcceptDialog`, `ConfirmationDialog`, or derived
  dialog, including title, text, visible state, and OK/Cancel button summaries.
- `node.accept_dialog`: accept a dialog by emitting its native `confirmed` signal
  and hiding it by default.
- `node.dismiss_dialog`: dismiss a dialog by emitting its native `canceled` signal
  and hiding it by default.
- `node.focus`: focus a Control node.
- `node.fill`: set a text-bearing node and emit the appropriate text signal.
- `node.get_property`: read one property.
- `node.get_properties`: read a named property list as a name/value map. If
  `properties` is omitted or empty, the server returns its standard selected
  property snapshot for the node. Python collection helpers use this to expose
  `locator.text_contents()`, `wait_for_texts(...)`, and `expect(locator)`
  text-list assertions.
- `node.set_property`: write one property. In editor mode this records an undo
  action by default; pass `undo: false` to apply directly or `undo_action` to set
  the editor history label. Python direct helper `set_node_property(...)`
  auto-waits for readback and returns `property_state`; locator `set(...)`
  also waits before returning the locator. Pass `wait=False` for fire-and-forget
  behavior.
- `node.set_properties`: write multiple properties on the first matched node. In
  editor mode this records one undo action by default. Python direct helper
  `set_node_properties(...)` auto-waits for batch readback and returns
  `properties_state`; locator `set_properties(...)` also waits before returning.
- `node.set_all_properties`: write multiple properties on every matched node,
  optionally bounded by `limit`. In editor mode this records one undo action for
  the whole matched set by default.
- `node.attach_script`: load a `Script` resource from `res://` and assign it to
  a node. GDScript resources are reloaded from disk by default so freshly written
  scripts are usable; pass `reload: false` to reuse an already loaded live script.
  Python `attach_script(...)` auto-waits for the node's `script` property to
  point at the requested path; pass `wait=False` for fire-and-forget behavior.
- `node.detach_script`: remove a node's script and return the previous script
  summary when one existed. Python `detach_script(...)` auto-waits until the node
  has no script and exposes `wait_for_node_script(...)` for direct script-state
  waits.
Locator expectations include `to_have_script(...)` and
`not_to_have_script(...)` for checking generated node behavior without
hand-reading the `script` property.
- `node.set_value`: set a numeric `Range` control value, covering sliders and
  spin boxes; selected value is surfaced as node `value`.
- `node.set_checked`: set a checkable `BaseButton` state. CheckBox,
  CheckButton, and toggle-mode buttons are supported; changed nodes emit
  `toggled` and `pressed` signals.
- `node.select_option`: select an `OptionButton` item by text, index, or item id.
  Changed nodes emit `item_selected`; selected text is surfaced as node `value`.
- `node.select_tab`: select a `TabBar` or `TabContainer` tab by title, index, or
  tab metadata. Changed nodes emit Godot's native tab signals; selected tab
  title is surfaced as node `value`.
- `node.menu_items`: list a `PopupMenu`'s internal items, or a `MenuButton`'s
  `get_popup()` items. Items include index, id, text, metadata, disabled,
  separator, checkable, radio-checkable, and checked state.
- `node.select_menu_item`: press a `PopupMenu` or `MenuButton` popup item by
  text, index, id, or metadata. The server focuses the item and emits the native
  `index_pressed` and `id_pressed` signals; pass `checked` to set a checkable
  menu item's checked state before emitting.
- `node.select_item`: select one or more `ItemList` items by text, index, or item
  metadata. Changed nodes emit `item_selected` or `multi_selected`; selected
  item text is surfaced as node `value` for single selection, and selected item
  texts are surfaced as an array for multi-selection.
- `node.select_tree_item`: select one or more `Tree` items by text, flat index,
  text path, or cell metadata. Changed single-selection trees emit `item_selected`
  and `cell_selected`; multi-selection trees emit `multi_selected`. Selected tree
  item text is surfaced as node `value`.
- `node.call`: call a no-vararg method through `Object.callv`.
- `node.call_all`: call a method through `Object.callv` on every matched node.
  Returns per-node summaries, values, count, and error count. Pass `limit` to
  bound the match set or `strict: false` to collect missing-method errors without
  failing the RPC.
- `node.evaluate`: evaluate a Godot `Expression` against one node. Inputs include
  `node`, `tree`, `root`, and caller-provided `variables`; the result is encoded
  with the same value codec as properties and method calls. Python exposes
  locator-scoped polling through `locator.wait_for_function(...)`,
  `locator.wait_for_expression(...)`, and `expect(locator).to_match_expression(...)`.
- `node.evaluate_all`: evaluate a Godot `Expression` against all matched nodes.
  Inputs include `nodes`, `count`, `tree`, `root`, and caller-provided
  `variables`; pass `limit` to bound the match set.
- `node.classes`: list/search Node classes before scene authoring by base
  class, name substring, instantiability, enabled state, and optional property
  counts. Python helpers include `node_classes(...)` and
  `expect_node_class(godot, class_name).to_be_listed(...)` so agents can
  discover candidate classes before `node.create` or `node.create_tree`.
- `node.class.describe`: describe a Node class before scene authoring,
  including whether it exists, can instantiate, is a Node subclass, property
  metadata, type names, hints, storage/editor-visible flags, and optional
  default values, plus optional method and signal metadata with argument
  counts, default-argument counts, type names, hints, and return type metadata
  for safe `node.call`, `node.call_all`, `signal.watch`, and `signal.connect`
  planning. Python helpers include `node_class_describe(...)`,
  `node_schema(...)`, `expect_node_class(godot, class_name).to_have_property(...)`,
  `to_have_method(...)`, and `to_have_signal(...)` so agents can choose valid
  properties before `node.create_tree`/`node.set_properties` and valid
  methods/signals before call or signal wiring operations.
- `node.create`: create a node by class and add it to a parent. In editor mode
  this records an undo action by default; pass `undo: false` to apply directly or
  `undo_action` to set the editor history label.
- `node.create_tree`: create a nested node tree from declarative specs with
  class/name/properties/metadata/groups/script/children fields. Python
  `create_node_tree(...)` auto-waits for every created node plus requested
  property, metadata, group, and script readbacks.
- `node.instantiate_scene`: load a `.tscn` or `.scn` `PackedScene`, instantiate
  it under a parent node, optionally rename/reorder it, and assign edited-scene
  ownership so the instance can be saved.
- `node.save_as_scene`: pack a node subtree into a `.tscn` or `.scn`
  `PackedScene` resource. The server temporarily assigns subtree ownership for
  packing, restores the edited scene's original owners, saves the resource, and
  refreshes the editor filesystem.
- `node.metadata`: read all metadata on a node, or pass `name`/`names` to read a
  selected subset.
- `node.set_metadata`: set one metadata entry with `name`/`value`, or set a
  dictionary with `values`/`metadata`. In editor mode this records one undo
  action by default. Python direct helper `set_node_metadata(...)` auto-waits
  for readback and returns `metadata_state`.
- `node.remove_metadata`: remove one metadata entry with `name`, or multiple
  entries with `names`. In editor mode this records one undo action by default.
  Python direct helper `remove_node_metadata(...)` auto-waits until the selected
  metadata names are absent and returns `metadata_state`. Pass `wait=False` to
  either direct helper for fire-and-forget behavior.
Locator helpers expose these as `metadata()`, `get_meta()`, `set_meta()`,
`set_metadata()`, `remove_meta()`, `to_have_meta()`, and
`to_have_metadata()`; setter/remover helpers wait before returning the locator
for chaining. `wait_for_node_meta(...)` and `wait_for_node_metadata(...)`
expose direct retryable metadata checks, so agents can tag generated nodes and
then select them with `get_by_test_id()` or metadata selectors.
- `node.groups`: list a node's groups.
- `node.add_group`: add a node to a group. Pass `persistent=false` for runtime-only
  membership; persistent groups are saved with editor scenes by default. Python
  direct helper `add_node_group(...)` auto-waits for membership readback and
  returns `groups_state`.
- `node.remove_group`: remove a node from a group. Python direct helper
  `remove_node_group(...)` auto-waits until the membership is absent and returns
  `groups_state`. Pass `wait=False` to either direct helper for fire-and-forget
  behavior.
- `node.reparent`: move a node under another parent, optionally preserving global
  transform, assigning edited-scene ownership, and moving to a child `index`.
- `node.move`: reorder a node within its current parent by child `index`.
- `node.duplicate`: duplicate a node, optionally placing it under a parent,
  renaming it, assigning edited-scene ownership, and moving to a child `index`.
- `node.delete`: remove and free a node.
Python direct helpers for create, instantiate, reparent, move, duplicate, and
delete auto-wait for scene-tree readback and return `node_state` evidence.
Attached-node waits use `node.describe`; delete waits until the absolute deleted
path is detached. Pass `wait=False` to those direct helpers for fire-and-forget
behavior. `wait_for_node(...)` exposes direct attached/detached node checks with
optional expected summary fields.
Locator authoring wrappers expose these RPCs as `create_child(...)`,
`instantiate_scene(...)`, `add_group(...)`, `remove_group(...)`, `reparent(...)`,
`move(...)`, `duplicate(...)`, `attach_script(...)`, `detach_script(...)`, and
`delete()` so generated scene edits can stay anchored to the current node.
Structural and group authoring wrappers wait before returning their result
payload, and `wait_for_node_group(...)` exposes direct retryable present/missing
membership checks.
- `scene.current`: return the current runtime scene name, path, and scene file path.
  Python exposes `expect_runtime_scene(godot)` for retryable current-scene path,
  name, and info assertions; this is separate from visual `expect_scene`.
- `scene.files`: discover project `.tscn`/`.scn` files by path, name, root node
  name/class, node count, and dependency status. Python exposes
  `scene_files(...)` plus `expect_project_scene(...).to_be_listed(...)`,
  `to_have_root(...)`, and `to_have_no_missing_dependencies(...)` so agents can
  confirm scene shape before opening, instantiating, or setting the main scene.
- `scene.file.describe`: inspect one scene file and return root metadata,
  nodes, external resources, signal connections, optional properties, and
  dependency status. Python exposes `scene_file_describe(...)` plus
  `expect_project_scene(...).to_have_node(...)` and `to_have_connection(...)`
  for live-RPC scene structure assertions over saved generated scenes.
- `scene.change`: change the runtime scene to a `.tscn`/`.scn` path.
- `scene.reload`: reload the current runtime scene.
- `scene.new`: create a new edited scene root. Python `editor_new_scene(...)`
  closes the current edited scene by default, retries through editor tab/root
  timing races, auto-waits for the edited-scene name, and returns the observed
  `editor_status` alongside the created root summary.
- `scene.open`: open a scene in the editor. Python `editor_open_scene(...)`
  auto-waits for edited-scene readback, preserves the raw open result, and
  returns `editor_status`; pass `wait=False` for fire-and-forget behavior.
- `scene.save`: save the edited scene. Python `editor_save_scene(path)` auto-waits
  for the edited scene path, saved file, and editor filesystem index entry when a
  `res://` path is provided.
- `editor.play`: run the current, main, or custom scene from the editor.
  Python helper: `editor_play(scene="current")`, with optional wait for
  `playing=true` and the expected scene path. Waited results preserve the raw RPC
  response and include `editor_status` evidence.
- `editor.stop`: stop the editor play session. Python helper:
  `editor_stop()`, with optional wait for the stopped state and `editor_status`
  evidence.
- `editor.status`: return editor availability, open scenes, edited scene,
  selection, editor UI state, ScriptEditor state, and play-session state.
  Python waits: `wait_for_editor_playing(scene=None)` and
  `wait_for_editor_stopped()`.
- `editor.ui.status`: report editor base-control evidence, main-screen control
  evidence, main-screen capability flags, and bottom-panel capability flags.
  `main_screens` is best-effort UI-tree evidence because Godot exposes
  `set_main_screen_editor(name)` but no stable API for listing every main
  screen. Bottom-panel `visible` and `items` are null/empty unless Godot exposes
  direct read APIs; `can_make_visible` and `can_hide` reflect the available
  `EditorPlugin` methods. Python exposes `editor_ui_status(...)`,
  `wait_for_editor_ui(...)`, `expect_editor(...).to_have_base_control(...)`,
  `expect_editor(...).to_have_main_screen(...)`,
  `expect_editor(...).to_have_ui(...)`, and
  `expect_editor(...).to_have_bottom_panel_capability(...)`.
- `editor.ui.switch_main_screen`: switch the editor main screen with
  `EditorInterface.set_main_screen_editor(name)` and return before/after UI
  evidence. Python `editor_switch_main_screen(name)` auto-waits for
  `editor.ui.status` readback and returns `ui_state`; pass `wait=False` for
  fire-and-forget behavior.
- `editor.ui.hide_bottom_panel`: hide the editor bottom panel with
  `EditorPlugin.hide_bottom_panel()` when available and return UI capability
  evidence. Python `editor_hide_bottom_panel()` returns `ui_state` readback;
  `visible` remains null unless Godot exposes a direct bottom-panel visibility
  API.
- `editor.history`: inspect the editor undo/redo history for the edited scene
  root, a selected node, or an explicit `history_id`. Python exposes
  `wait_for_editor_history(...)` for retryable history payload checks.
- `editor.undo`: run one editor undo operation and return the before/after
  history state. Python `editor_undo(...)` auto-waits for history readback and
  returns `history_state`; pass `wait=False` for fire-and-forget behavior.
- `editor.redo`: run one editor redo operation and return the before/after
  history state. Python `editor_redo(...)` auto-waits for history readback and
  returns `history_state`; pass `wait=False` for fire-and-forget behavior.
Editor expectations include `to_have_undo(...)`, `not_to_have_undo(...)`,
`to_have_redo(...)`, `not_to_have_redo(...)`, and `to_match_history(...)` for
polling the `editor.history` payload after generated editor edits.
- `editor.selection.get`: return the current editor node selection. Python
  exposes `wait_for_editor_selection(...)` for retryable selection checks.
- `editor.selection.set`: select one or more edited-scene nodes, optionally
  inspecting the first. Python `editor_select(...)` auto-waits for selection
  readback and returns `selection_state`; pass `wait=False` for fire-and-forget
  behavior.
- `editor.inspect`: send a node or Resource to the editor Inspector. Python
  `editor_inspect(...)` auto-waits for Inspector describe readback and returns
  `inspector_state`; pass `wait=False` for fire-and-forget behavior.
- `editor.inspector.describe`: describe Inspector-visible properties for the selected target.
- `editor.inspector.get_property`: read one Inspector property.
- `editor.inspector.set_property`: write one Inspector property and optionally save a Resource.
  Python Inspector helpers auto-wait for readback and return `property_state`;
  pass `wait=False` for fire-and-forget behavior.
- `editor.inspector.set_properties`: write multiple Inspector properties in one
  request and optionally save a Resource. Python Inspector helpers expose
  `values(...)`, `set_properties(...)`, and
  `expect_inspector(...).to_have_properties(...)` for batch editor assertions.
  `set_properties(...)` auto-waits for batch readback and returns
  `properties_state`; pass `wait=False` for fire-and-forget behavior.
- `editor.script.open`: open a Script in the editor. In headless mode this loads
  and reports the script without invoking a desktop editor unless `force` is
  passed. Python `editor_open_script(...)` auto-waits for script describe
  readback and, when the editor opens the script, ScriptEditor tab evidence as
  `script_editor`; pass `wait=False` for fire-and-forget behavior.
- `editor.script.status`: report ScriptEditor availability, open script paths,
  open script count, current script path, and capability flags. Python exposes
  `editor_script_status(...)`, `wait_for_editor_script(path, current=True)`,
  `expect_editor(...).to_have_open_script(path)`, and
  `expect_editor(...).to_have_current_script(path)`.
- `editor.script.describe`: load a Script and return source-derived symbols plus
  Godot-reported methods, properties, and signals. Python helpers include
  `wait_for_script(...)` and `write_script(...)` so agent-authored GDScript can
  wait for saved source, `GDScript` indexing, `extends`, function symbols, and
  source snippets before dependent editor actions continue.
- `script.file.describe`: inspect one `.gd` file directly and return path,
  load/resource state, `class_name`, `extends`, functions, variables, constants,
  signals, optional source text, and source-derived symbols without requiring
  ScriptEditor state. Python exposes `script_file_describe(...)` plus
  `expect_script(...).to_have_class_name(...)`, `to_define_signal(...)`, and
  `to_define_variable(...)` for direct generated-script assertions.
- `script.classes`: scan project `.gd` files and return GDScript `class_name`,
  `extends`, path/global path, source-derived functions/signals/variables, and
  Node/Resource classification. Python exposes `script_classes(...)` plus
  `expect_script_class(...).to_be_listed(...)`, `to_extend(...)`,
  `to_be_node(...)`, `to_be_resource(...)`, and `to_have_function(...)` so
  agents can discover custom Node/Resource classes before attaching scripts,
  wiring autoloads, or creating custom resources.
- `editor.filesystem.scan`: request an editor filesystem scan or targeted file
  update. Python `editor_scan_filesystem(path_or_paths)` auto-waits for
  targeted path readback and returns `filesystem_state` or `filesystem_states`;
  pass `wait=False` for fire-and-forget behavior. Untargeted scans preserve raw
  request behavior because there is no concrete path to verify.
- `editor.filesystem.describe`: return metadata for one `res://` path.
- `editor.filesystem.find`: search project files by path, name, extension, or resource type.
  Python helpers include `wait_for_editor_filesystem_entry(...)`,
  `wait_for_editor_filesystem_missing(...)`, `wait_for_editor_filesystem_find(...)`,
  and `expect_filesystem(godot, path).to_be_indexed(...)` /
  `not_to_be_indexed(...)`, `to_have_indexed_count(...)`, and
  `not_to_contain(...)` so agent-authored file changes can wait for Godot's
  editor import/index state before continuing. Search waits can bound both
  `min_count` and `max_count`.
- `editor.filesystem.select`: select a file in the editor FileSystem dock when supported.
  The server records the last successful selection in `editor.filesystem.describe`
  and `editor.filesystem.find`. Python `editor_filesystem_select(...)`
  auto-waits for selected readback and returns `filesystem_state`; pass
  `wait=False` for fire-and-forget behavior.
- `editor.filesystem.open`: select a `res://` path and dispatch by file kind:
  `.tscn`/`.scn` scenes open in the editor, GDScript files open in the
  ScriptEditor, loadable resources open in the Inspector, and directories or
  unknown files are selected only. Python `editor_filesystem_open(...)`
  auto-waits for selected readback plus scene/script/Inspector evidence when
  applicable; pass `wait=False` for fire-and-forget behavior.
- `input.actions`: list `InputMap` actions, with optional event summaries.
- `input.action.describe`: describe one `InputMap` action, including deadzone,
  bound events, pressed state, and action strength.
- `input.action.configure`: create or update an `InputMap` action. Pass
  `deadzone`, `replace`, and `events` specs such as `{"type":"key","key":"Space"}`,
  `{"type":"mouse_button","button":"left"}`, `{"type":"joypad_button","button":"a"}`,
  or `{"type":"joypad_axis","axis":"left_x","value":1.0}`. Python helpers
  auto-wait for action readback and return `action_state`; pass `wait=False`
  for fire-and-forget behavior.
- `input.action.erase`: erase an action, clear all bound events with
  `events_only`, or erase selected event specs. Python auto-waits for action
  or event removal readback and returns `action_state`; pass `wait=False` for
  fire-and-forget behavior.
- `input.action`: press or release an input action. Python helpers include
  `action_down(...)`, `action_up(...)`, `press_action(...)`,
  `wait_for_input_action(...)`, `expect_project.to_have_input_action_pressed(...)`,
  `not_to_have_input_action_pressed(...)`, and `to_have_input_action_strength(...)`.
  Python press/release helpers auto-wait for pressed-state readback and return
  `pressed_state`; pass `wait=False` for fire-and-forget behavior.
- `input.key`: push a keyboard event into the active viewport. `key` can be a
  single key or a combo such as `Ctrl+S`; modifiers can also be passed through
  `modifiers`, `shift`, `ctrl`, `alt`, `meta`, or `command_or_control`.
- `input.text`: push text input into the active viewport.
- `input.mouse`: push mouse move, button, click, or wheel events into the active viewport.
  Use `type` values `move`, `down`, `up`, `click`, or `wheel`; wheel input accepts
  `delta_x` and `delta_y`. In headless mode the server supplements Godot's viewport
  routing for Control motion/release events so hover and drag tests remain deterministic.
- `input.touch`: push touch events into the active viewport. Use `type` values
  `down`, `up`, `tap`, or `drag` with `x`, `y`, and optional pointer `index`.
  In headless mode the server also routes touch events to `Control.gui_input` at
  the target position.
- `input.joypad`: push joypad button or axis events through `Input.parse_input_event`.
  Button inputs use `type` values `button`, `down`, or `up` with `button`,
  optional `pressed`, `pressure`, and `device`. Axis inputs use `type` `axis`
  with `axis`, `value`, and optional `device`. Common aliases are accepted,
  including `a`/`b`/`x`/`y`, `cross`/`circle`/`square`/`triangle`, `lb`/`rb`,
  `l1`/`r1`, d-pad directions, `left_x`/`left_y`/`right_x`/`right_y`, and
  `lt`/`rt`.
- `viewport.info`: return the active display driver, window size, visible viewport
  rect, and last automation mouse position.
- `viewport.set_size`: set the active window size with positive `width` and
  `height` values. Returns the same payload as `viewport.info`; Python exposes
  this as `set_viewport_size(width, height)`.
  Python helpers also include `wait_for_viewport_size(width, height)` and
  `expect_viewport(godot).to_have_size(...)`, `not_to_have_size(...)`,
  `to_have_display_server(...)`, `to_have_mouse_position(...)`, and
  `to_have_screenshot(...)`.
- `fs.exists`: check whether a `res://` project path exists.
- `fs.info`: describe a `res://` file or directory with type, extension, byte
  size for files, and resource type when available.
- `fs.find`: recursively find files and optionally directories under `res://`
  by name, substring, extension, or resource type.
- `fs.grep`: search text files under `res://` by substring. It supports the same
  file filters as `fs.find`, case-sensitive or insensitive matching, max result
  limits, and optional before/after context lines.
- `fs.read_text`: read a UTF-8 text file from `res://`.
- `fs.write_text`: write a UTF-8 text file under `res://`, creating parent directories by default.
  Python `fs_write_text(...)` auto-waits for the saved file, verifies the written
  text, and includes editor filesystem scan/index evidence when available; pass
  `wait=False` for fire-and-forget behavior.
- `fs.replace_text`: safely replace text in one `res://` text file. It defaults
  to `expected_replacements=1`, refuses to write when the match count differs,
  supports case-sensitive or insensitive matching, dry-run previews, max
  replacement caps, and before/after line evidence. Python `fs_replace_text(...)`
  auto-waits for the saved file, verifies the final text when available, and
  includes editor filesystem scan/index evidence when available; pass `wait=False`
  for fire-and-forget behavior.
- `fs.replace_text_many`: safely preview or apply the same text replacement
  across files under `res://` using the same filters as `fs.find`/`fs.grep`.
  It defaults to dry-run mode and reports changed files, total replacements,
  and per-file before/after evidence. Committed writes require
  `expected_files` or `expected_replacements`, and Python
  `fs_replace_text_many(...)` auto-waits on each changed file and includes editor
  filesystem scan/index evidence when available.
- `fs.read_bytes`: read a binary file from `res://`; the wire payload returns base64 and the Python helper returns `bytes`.
- `fs.write_bytes`: write a binary file under `res://` from base64, creating parent directories by default.
  Python `fs_write_bytes(...)` auto-waits for the saved file and includes editor
  filesystem scan/index evidence when available; pass `wait=False` for fire-and-forget behavior.
- `fs.mkdir`: create a directory under `res://`.
  Python `fs_mkdir(...)` auto-waits for the directory and includes editor
  filesystem scan/index evidence when available; pass `wait=False` for
  fire-and-forget behavior.
- `fs.list`: list files and directories under a `res://` directory.
- `fs.copy`: copy a file under `res://`.
- `fs.move`: move or rename a file or directory under `res://`.
  Python `fs_copy(...)` and `fs_move(...)` auto-wait for destination readback
  and editor filesystem index evidence; `fs_move(...)` also waits for source
  removal. Pass `wait=False` for fire-and-forget behavior.
- `fs.delete`: delete a file or empty directory under `res://`.
  Python `fs_delete(...)` auto-waits for the path to be missing and includes
  editor filesystem scan/missing-index evidence when available; pass
  `wait=False` for fire-and-forget behavior.
  Python helpers include `wait_for_fs_path(...)`, `wait_for_file(...)`,
  `wait_for_directory(...)`, `wait_for_files(...)`, and
  `expect_filesystem(godot, path)` assertions for file/directory existence,
  missing paths, text containment, editor index state, and resource type.
- `resource.save`: instantiate and save a Resource to `res://`. Python
  `resource_save(...)` auto-waits for the saved file, loadable resource, and
  editor filesystem index evidence when available; pass `wait=False` for
  fire-and-forget behavior. Resource property values may include
  `{"$type":"ResourceRef","path":"res://..."}` / `ExtResource` for external
  references and `{"$type":"SubResource","class":"Gradient","properties":{...}}`
  for nested resources. The server validates referenced paths/classes before
  saving and returns `dependency_state` evidence.
- `resource.files`: discover project `.tres`/`.res` files by path, name,
  class/type, resource name, and dependency status. Python exposes
  `resource_files(...)` plus `expect_resource(...).to_be_listed(...)` so agents
  can confirm saved resources before inspecting, mutating, duplicating, or
  wiring them into scenes.
- `resource.file.describe`: describe one saved `.tres`/`.res` resource file by
  path, text/binary format, load status, dependencies, root resource metadata,
  root properties, text external resources, text subresources, and optional
  source text. Python exposes `resource_file_describe(...)` plus
  `expect_resource(...).to_have_file_property(...)` and
  `expect_resource(...).to_have_file_ext_resource(...)` for static resource
  graph assertions before mutation, duplication, or scene wiring.
- `resource.inspect`: load and describe a Resource, optionally including selected properties.
- `resource.classes`: list/search Resource classes before authoring by base
  class, name substring, instantiability, Resource-subclass state, enabled
  state, and optional property counts. Python helpers include
  `resource_classes(...)` and
  `expect_resource_class(godot, class_name).to_be_listed(...)` so agents can
  discover candidate classes before calling `resource.class.describe`.
- `resource.class.describe`: describe a Resource class before authoring,
  including whether it exists, can instantiate, is a Resource subclass,
  property metadata, type names, hints, storage/editor-visible flags, and
  optional default values. Python helpers include
  `resource_class_describe(...)`, `resource_schema(...)`, and
  `expect_resource_class(godot, class_name).to_have_property(...)` so agents
  can choose valid properties before `resource.save` or
  `resource.set_properties`.
- `resource.set_properties`: load an existing Resource, validate target
  properties by default, apply decoded values, and save by default. Returns
  previous/current property evidence. Python `resource_set_properties(...)`
  auto-waits for resource property readback, saved file existence, and editor
  filesystem index evidence when available; pass `wait=False` for
  fire-and-forget behavior. Resource graph values use the same `ResourceRef`,
  `ExtResource`, and `SubResource` specs as `resource.save`.
- `resource.duplicate`: load an existing Resource, duplicate it, optionally
  apply decoded property overrides, and save the variant to another `res://`
  path. Python `resource_duplicate(...)` auto-waits for source/variant resource
  readback, saved file existence, and editor filesystem index evidence when
  available; pass `wait=False` for fire-and-forget behavior. Saved variants
  include `dependency_state` evidence after property overrides are applied.
- `resource.dependencies`: ask Godot for a resource's dependencies and report missing `res://` targets.
- `resource.references`: scan project scene/resource files and return files
  whose Godot dependency list references a target resource path or UID. Python
  exposes `resource_references(...)` plus
  `expect_resource(...).to_be_referenced_by(...)` so agents can check reverse
  dependencies before deleting, renaming, replacing, or exporting resources.
- `resource.move`: move a referenced `res://` file and optionally update exact
  path references in text scene/resource files (`.tscn`/`.tres` by default).
  It supports dry-run previews, expected reference-file/replacement counts,
  truncation limits, per-file edit evidence, and before/after reverse-reference
  summaries. Python `resource_move(...)` auto-waits for destination readback,
  source removal, editor filesystem evidence, rewritten reference file readback,
  and refreshed reverse-reference summaries when committed.
- `resource.import_metadata`: read a generated `.import` file and report
  remap/dependency/parameter sections, imported resource type, source/import
  file state, destination files, generated file readiness, missing/stale
  generated files, and structured import diagnostics.
- `resource.imports`: scan importable project assets and return `.import`
  metadata summaries with importer/resource type, loadability, generated-file
  readiness, stale/missing generated files, diagnostics, and truncation state.
  Python exposes `resource_imports(...)` plus
  `expect_resource(...).to_be_import_listed(...)` so agents can confirm
  external assets are imported before wiring them into scenes or exports.
- `resource.reimport`: refresh editor filesystem state for paths; pass `force` to call Godot's reimport hook.
  Python `resource_reimport(...)` auto-waits for import metadata on common
  external assets such as images, audio, fonts, and 3D models, returning `imports`
  and `import_count`. The immediate RPC result includes source/import file
  preflight evidence, forced reimport path counts, and scan fallback state; the
  waited import reports include `diagnostics`, `diagnostic_count`,
  `missing_generated_files`, and `stale_generated_files`. It also returns editor filesystem index readback as
  `editor_filesystem` for one path or `editor_filesystem_states` for multiple
  paths; pass `wait=False` for fire-and-forget behavior.
The Python client and runner expose `expect_resource(godot, path)` for
Playwright-style resource assertions including existence, class/type, selected
properties, dependencies, missing dependency checks, and import metadata.
- `viewport.screenshot`: save the active viewport to a PNG file. This requires a
  render-capable display driver; Godot headless mode cannot provide viewport pixels.
  Python exposes `wait_for_screenshot(...)` and
  `expect_viewport(godot).to_have_screenshot(...)` for screenshot artifact and
  dimension checks. Visual screenshot assertions compare PNG pixels with optional
  tolerances and write actual, diff PNG, and JSON metric artifacts on mismatch.
  Targeted assertions can also check individual pixels or sampled rectangular regions.
  Python `expect_scene.inspect_screenshot(...)` captures an actual PNG and writes
  a sibling `*.visual.json` inspection report with dimensions, SHA-256, sampled
  pixels, region average/dominant colors, and optional color-match metrics.
- `project.get_setting`: read a ProjectSettings value.
- `project.set_setting`: write and optionally persist a ProjectSettings value.
  Python `project_set_setting(...)` auto-waits for readback through
  `project.get_setting`; pass `wait=False` for fire-and-forget behavior.
- `project.summary`: aggregate main scene, autoloads, export presets, InputMap
  actions, scene files, script classes, resource files, import assets, counts,
  and diagnostics into one live project health snapshot. Python exposes
  `project_summary(...)` so agents can plan the next inspection or fix without
  manually chaining many discovery calls.
- `project.doctor`: combine protocol capability discovery, engine/editor state,
  project summary, resource/import diagnostics, pass/warn/fail readiness checks,
  and actionable next steps into one live triage report. Python exposes
  `project_doctor(...)` so agents can decide whether a connected project is
  ready for authoring, runtime probing, trace recording, and validation.
- `project.export_presets`: read `res://export_presets.cfg` and return configured export presets.
- `project.set_export_preset`: create or update a preset in `res://export_presets.cfg`, including common preset fields and arbitrary option keys.
  Python auto-waits until `project.export_presets` exposes the requested preset
  fields/options.
- `project.main_scene`: return the configured `application/run/main_scene` path
  and whether that scene resource exists.
- `project.set_main_scene`: set the main scene to a `.tscn` or `.scn` resource,
  optionally saving `project.godot`. Python auto-waits until
  `project.main_scene` reads back the requested path.
- `project.autoloads`: list configured autoload entries from ProjectSettings,
  including name, path, raw setting value, singleton marker, and resource existence.
- `project.add_autoload`: create or update an `autoload/<Name>` setting. By
  default the stored value is singleton-prefixed with `*`; pass `singleton: false`
  for non-singleton autoload resources. Python auto-waits until
  `project.autoloads` exposes the requested entry.
- `project.remove_autoload`: remove an `autoload/<Name>` setting, optionally
  saving `project.godot`. Python auto-waits until the matching autoload is absent.
The Python client and runner expose `expect_project(godot)` for Playwright-style
project assertions over export presets, main scene, autoloads, and InputMap
actions. Export preset expectations can match top-level preset fields and nested
`options` values. InputMap expectations can also match concrete bound events by
type, key, button, axis, axis value, device, modifiers, or event fields.
- `trace.start`: enable lightweight in-memory tracing.
- `trace.stop`: disable tracing.
- `trace.events`: read recorded events, optionally clearing them.
- `trace.clear`: clear recorded events.
  Python helpers include `trace_count(...)`, `wait_for_trace_count(...)`, and
  `expect_trace(godot)` assertions for exact/minimum event counts, RPC counts,
  absent RPCs, empty traces, single events, and event sequences.
  `godot-playwright codegen-trace` can replay common interaction events plus
  semantic authoring events such as `protocol.describe`, `node.classes`, `node.class.describe`, `node.create`, `node.create_tree`,
  `node.instantiate_scene`, `node.save_as_scene`, `node.set_properties`,
  `node.set_all_properties`, `node.attach_script`, `node.detach_script`,
  `node.set_metadata`, `node.remove_metadata`, `node.add_group`,
  `node.remove_group`, `node.reparent`, `node.move`, `node.duplicate`,
  `node.delete`, `node.call_all`, `fs.read_text`, `fs.read_bytes`, `fs.grep`,
  `fs.copy`, `fs.move`, `fs.replace_text`, `fs.replace_text_many`,
  `resource.save`, `resource.set_properties`, `resource.duplicate`,
  `resource.files`, `resource.file.describe`, `resource.classes`,
  `resource.class.describe`, `resource.dependencies`, `resource.references`,
  `resource.move`, `resource.imports`, `resource.import_metadata`, and
  `resource.reimport`, plus
  animation, physics, camera, signal, project
  configuration, and InputMap mutation events such as `animation.play`,
  `physics2d.point`, `camera3d.pick`, `signal.watch`, `signal.connect`,
  `project.set_setting`, `project.set_main_scene`, `project.add_autoload`,
  `project.remove_autoload`, `project.set_export_preset`, `project.summary`,
  `project.doctor`,
  `input.action.configure`, and `input.action.erase`, and editor workflow
  events such as `scene.files`, `scene.file.describe`, `resource.files`,
  `resource.file.describe`, `resource.references`, `resource.move`, `resource.imports`,
  `scene.new`, `scene.open`, `scene.save`, `editor.play`,
  `editor.stop`, `editor.undo`, `editor.redo`, `editor.selection.set`,
  `editor.inspect`, `editor.inspector.set_property`,
  `editor.inspector.set_properties`, `editor.script.open`,
  `script.file.describe`, `script.classes`,
  `editor.ui.switch_main_screen`, `editor.ui.hide_bottom_panel`,
  `editor.filesystem.scan`, `editor.filesystem.select`, and
  `editor.filesystem.open` as editable Python helper calls.
  A regression test compares the addon `_record_event(...)` surface with
  codegen handlers so new trace events must either replay or be classified as
  intentional infrastructure/comment-preserved events.
  The CLI runner combines retained traces, per-test Godot logs, optional
  screenshots, Python tracebacks, runtime/editor status, and failure scene
  snapshots into a `*-diagnostics.json` artifact for failed tests.
- `signal.watch`: subscribe to a node signal.
- `signal.unwatch`: remove a signal subscription.
- `signal.events`: read captured signal events, optionally clearing them.
- `signal.clear`: clear captured signal events.
  Python helpers include `wait_for_signal(selector, signal, action=...)` and
  `wait_for_signal_event(...)` for Playwright-style event waits with automatic
  watcher cleanup and optional signal/path/predicate filters.
  `wait_for_signal_sequence(...)` and `expect_signal(...).to_have_event_sequence(...)`
  add ordered signal assertions over one watch or the combined captured event stream.
  `expect_signal(...)` adds retryable signal event, sequence, event-count, empty,
  field, and negative assertions with explicit watcher cleanup.
- `signal.connections`: inspect live signal connections for one node, optionally
  filtered to a single signal.
- `signal.connect`: connect a source node signal to a target node method. Editor
  connections are persistent by default so they save into `.tscn` scenes; pass
  `persistent=false` for runtime-only connections. Supports bound arguments and
  deferred, one-shot, reference-counted, or explicit Godot connection flags.
  Python `signal_connect(...)` and locator `connect_signal(...)` auto-wait for
  the live connection to appear; pass `wait=False` for fire-and-forget behavior.
- `signal.disconnect`: remove a previously authored source signal to target
  method connection. Python `signal_disconnect(...)` and locator
  `disconnect_signal(...)` auto-wait until the matching connection is absent and
  expose `wait_for_signal_connection(...)` for direct connected/disconnected
  waits.
Locator expectations include `to_have_signal_connection(...)` and
`not_to_have_signal_connection(...)` so generated scenes can assert signal,
target, method, and persistent-connection state without hand-inspecting the
`signal.connections` payload.
Locator expectations also include `to_have_group(...)` and
`not_to_have_group(...)` for checking group membership produced by scene
authoring helpers.
