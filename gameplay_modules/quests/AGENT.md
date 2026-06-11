# Agent Instructions: quests

Use this module when a Godot project needs quests, objectives, tutorial steps, contracts, milestones, challenges, or scenario goals.

Install with:

```sh
godot-playwright module add /path/to/project quests
```

Keep progression explicit: project code calls `advance_objective()`, `set_objective_progress()`, or `complete_objective()` when gameplay should count toward an objective.
