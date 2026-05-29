# Godot Coding Skill（中文说明）

这个 skill 用来约束 AI 在 Godot 项目里写出更像资深 Godot 程序员的代码，而不是把所有逻辑堆进一个脚本。

核心目标：

- 先识别 Godot 版本和项目结构，再写代码。
- 优先使用 Godot 原生抽象：Scene、Node script、Resource、Autoload、Signal、Group。
- 避免常见 AI 反模式：巨型 `main.gd`、滥用全局 Autoload、不用 Resource、硬编码 NodePath、Godot 3/4 API 混用、没有验证。
- 默认写 Godot 4 typed GDScript。
- 和你的 `godot-playwright` / `godot-cli` 形成闭环：inspect → edit → check-script/check-resources/probe/test → report。
- 默认让 `godot-playwright` 自动分配端口并隔离 XDG 用户目录；不要并行裸跑多个会抢 `9777` 的 Godot autoload。
- 截图只用于视觉/layout，headless 下不要把截图当作主要验证；实时玩法优先用节点状态、信号、快照、物理查询和 `runtime.sample_frames`。

推荐放置方式：

```text
skills/
  godot-coding/
    SKILL.md
    guides/
    checklists/
    examples/
    templates/
```

最重要文件：

- `SKILL.md`：主 skill，AI 应优先读取。
- `guides/architecture.md`：Scene / Script / Resource / Autoload 的判断规则。
- `guides/gdscript_patterns.md`：Godot 4 GDScript 模板和惯用写法。
- `guides/godot_playwright_workflow.md`：如何使用你的 Godot Playwright 工具做验证。
- `guides/refactoring_playbook.md`：如何把 AI 写坏的 Godot 代码重构回来。
- `checklists/code_review.md`：代码审查清单。
- `checklists/pre_delivery.md`：交付前验证清单。

建议在 AI harness 中把 `SKILL.md` 作为主入口，并在 Godot 项目任务中强制要求：

```bash
godot-playwright inspect-project <project> --exclude "addons/**" --json
godot-playwright check-scripts <project> res:// --exclude "addons/**"
godot-playwright check-resources <project> res:// --exclude "addons/**"
godot-playwright validate <project> --exclude "addons/**"
```

对于小改动，允许缩小到 changed file / affected scene，但最终回答必须说明跑了哪些验证，没跑就不能声称通过。
