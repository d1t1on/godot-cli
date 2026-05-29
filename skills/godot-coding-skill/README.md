# Godot Coding Skill

A reusable AI skill for writing, reviewing, refactoring, and validating Godot 4.x projects.

It teaches an AI agent to work like a strong Godot programmer instead of a generic script generator:

- inspect the project and Godot version before editing;
- choose between Scene, Node script, Resource, RefCounted helper, Autoload, Signal, Group, and tests intentionally;
- avoid giant scripts, global-state dumps, hard-coded NodePaths, untyped public APIs, and Godot 3/4 API mixing;
- use custom Resources for editor-tunable shared data;
- keep Autoloads narrow and system-owned;
- validate changes with `godot-playwright` / `godot-cli` when available.
- use auto-allocated Godot Playwright ports and isolated XDG user data for parallel audits;
- avoid headless screenshots for gameplay logic; prefer semantic state, signals, snapshots, physics, and frame sampling.

## Suggested installation

```text
skills/
  godot-coding/
    SKILL.md
    guides/
    checklists/
    examples/
    templates/
```

Use `SKILL.md` as the main entry point for the harness. Load the supporting guides only when the task needs deeper detail.

## Main files

- `SKILL.md` — main skill instructions.
- `guides/architecture.md` — scene/script/resource/autoload decision rules.
- `guides/gdscript_patterns.md` — Godot 4 GDScript patterns.
- `guides/godot_playwright_workflow.md` — validation workflow using Godot Playwright.
- `guides/refactoring_playbook.md` — how to fix common AI-generated Godot anti-patterns.
- `checklists/code_review.md` — review checklist.
- `checklists/pre_delivery.md` — final delivery checklist.
- `examples/` — small reusable examples.
- `templates/agent_system_prompt.md` — optional harness-level system prompt wrapper.

## Scope

Optimized for Godot 4.6+ and the `d1t1on/godot-cli` / `godot-playwright` workflow, while still requiring agents to inspect the actual project version before assuming APIs.
