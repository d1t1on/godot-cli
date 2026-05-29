# Final Response Template for Godot Tasks

Use this structure when replying after a Godot coding task.

```text
完成了。这个改动按 Godot 的架构拆成：
- Resource: ...（为什么是数据/配置）
- Scene/script: ...（为什么由该节点/场景拥有）
- Autoload: ...（如适用，为什么需要跨场景生命周期）

改动文件：
- res://...
- res://...

验证：
- godot-playwright check-script ...: passed
- godot-playwright check-resources ...: passed
- godot-playwright probe ...: passed

注意：
- ...（无法验证的环境限制或后续建议）
```

Do not claim `passed` for commands that were not run.
