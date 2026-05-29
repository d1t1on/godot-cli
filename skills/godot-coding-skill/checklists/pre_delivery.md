# Godot Pre-delivery Checklist

Before final response on a Godot coding task:

## Context

- [ ] I inspected the project or clearly stated that no project files were available.
- [ ] I know whether this is Godot 4.x or Godot 3.x.
- [ ] I followed the existing project language and folder conventions.

## Architecture statement

- [ ] I can explain why each new/changed file is a scene, script, Resource, Autoload, or test.
- [ ] I did not introduce a generic global manager where a scene/Resource/signal would be better.
- [ ] I did not put unrelated features into a single script.

## Validation evidence

Run the relevant smallest commands:

```bash
godot-playwright check-script PROJECT res://changed/file.gd
godot-playwright inspect-scene PROJECT res://changed/scene.tscn --json
godot-playwright check-resources PROJECT res://changed/folder --exclude "addons/**"
godot-playwright probe PROJECT --scene res://affected/scene.tscn
godot-playwright test PROJECT tests --grep affected_feature --trace retain-on-failure
```

Use the `godot-playwright` wrappers for validation instead of parallel raw
`godot --headless` commands when the project has the Playwright autoload; the
wrappers isolate ports and user-data directories.

Or if `godot-playwright` is unavailable:

```bash
godot --version
godot --headless --path PROJECT --check-only --script res://changed/file.gd
```

## Final response includes

- [ ] Files changed.
- [ ] Architecture choices.
- [ ] Validation commands and pass/fail result.
- [ ] Known limitations or commands the user should run locally if validation was unavailable.
