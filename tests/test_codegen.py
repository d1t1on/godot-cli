from __future__ import annotations

import json
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from godot_playwright.cli import main as cli_main
from godot_playwright.codegen import (
    TraceCodegenError,
    _INFRASTRUCTURE_EVENTS,
    generate_test_from_trace,
    load_trace_events,
    normalize_trace_events,
)


ROOT = Path(__file__).resolve().parents[1]


class TraceCodegenTests(unittest.TestCase):
    def test_codegen_covers_addon_trace_event_surface(self) -> None:
        emitted = _recorded_addon_event_types()
        supported = _codegen_supported_event_types()

        self.assertEqual(emitted - supported - _INFRASTRUCTURE_EVENTS, set())
        self.assertEqual(_INFRASTRUCTURE_EVENTS, emitted & _INFRASTRUCTURE_EVENTS)
        self.assertGreaterEqual(len(emitted), 100)
        self.assertGreaterEqual(len(supported), 100)

    def test_generate_test_from_trace_translates_common_events(self) -> None:
        events = [
            {"type": "trace.start", "data": {"max_events": 5000}},
            {"type": "node.click", "data": {"path": "/root/Main/CounterButton"}},
            {"type": "node.fill", "data": {"path": "/root/Main/NameInput", "text": "Ada"}},
            {"type": "node.set_checked", "data": {"path": "/root/Main/AcceptTerms", "checked": True}},
            {"type": "node.set_checked", "data": {"path": "/root/Main/AcceptTerms", "checked": False}},
            {
                "type": "node.select_option",
                "data": {"path": "/root/Main/ThemeSelect", "selected": {"text": "Story", "id": 20, "index": 1}},
            },
            {
                "type": "node.select_tab",
                "data": {
                    "path": "/root/Main/ModeTabs",
                    "selected": {"metadata": {"mode": "advanced"}, "title": "Advanced", "index": 1},
                },
            },
            {
                "type": "node.select_menu_item",
                "data": {
                    "path": "/root/Main/ActionMenu/@PopupMenu@18",
                    "selected": {
                        "metadata": {"action": "snap"},
                        "text": "Snap",
                        "checkable": True,
                        "checked": True,
                    },
                },
            },
            {
                "type": "node.select_item",
                "data": {
                    "path": "/root/Main/InventoryList",
                    "selected": {"items": [{"metadata": {"kind": "key"}, "text": "Key", "index": 2}]},
                },
            },
            {
                "type": "node.select_tree_item",
                "data": {
                    "path": "/root/Main/QuestTree",
                    "selected": {"items": [{"path": ["Cave", "Boss"], "text": "Boss", "column": 0}]},
                },
            },
            {"type": "input.key", "data": {"key": "Enter", "pressed": True, "modifiers": {}}},
            {"type": "input.key", "data": {"key": "Enter", "pressed": False, "modifiers": {}}},
            {"type": "input.key", "data": {"key": "F4", "pressed": True, "modifiers": {"shift": True}}},
            {"type": "input.key", "data": {"key": "F4", "pressed": False, "modifiers": {"shift": True}}},
            {"type": "input.mouse", "data": {"type": "click", "x": 10.0, "y": 20.0, "button": 1}},
            {"type": "input.touch", "data": {"type": "tap", "x": 30.0, "y": 40.0, "index": 2}},
            {"type": "input.joypad", "data": {"type": "axis", "axis": "left_x", "value": 0.5, "device": 0}},
            {"type": "scene.change", "data": {"path": "res://scenes/secondary.tscn", "mode": "runtime"}},
            {"type": "custom.event", "data": {"value": 1}},
        ]

        code = generate_test_from_trace(events, test_name="recorded flow")

        self.assertIn("def test_recorded_flow(godot):", code)
        self.assertIn("godot.locator('/root/Main/CounterButton').click()", code)
        self.assertIn("godot.locator('/root/Main/NameInput').fill('Ada')", code)
        self.assertIn("godot.locator('/root/Main/AcceptTerms').check()", code)
        self.assertIn("godot.locator('/root/Main/AcceptTerms').uncheck()", code)
        self.assertIn("godot.locator('/root/Main/ThemeSelect').select_option('Story')", code)
        self.assertIn("godot.locator('/root/Main/ModeTabs').select_tab({'metadata': {'mode': 'advanced'}})", code)
        self.assertIn(
            "godot.locator('/root/Main/ActionMenu/@PopupMenu@18').select_menu_item({'metadata': {'action': 'snap'}}, checked=True)",
            code,
        )
        self.assertIn("godot.locator('/root/Main/InventoryList').select_item({'metadata': {'kind': 'key'}})", code)
        self.assertIn("godot.locator('/root/Main/QuestTree').select_tree_item({'path': ['Cave', 'Boss']})", code)
        self.assertIn("godot.press('Enter')", code)
        self.assertIn("godot.press('F4', shift=True)", code)
        self.assertIn("godot.mouse_click(10.0, 20.0, button=1)", code)
        self.assertIn("godot.tap(30.0, 40.0, index=2)", code)
        self.assertIn("godot.joypad_axis('left_x', 0.5, device=0)", code)
        self.assertIn("godot.change_scene('res://scenes/secondary.tscn')", code)
        self.assertIn("# Unsupported trace event custom.event: {'value': 1}", code)
        compile(code, "<generated>", "exec")

    def test_generate_test_from_trace_translates_authoring_events(self) -> None:
        events = [
            {
                "type": "node.create_tree",
                "data": {
                    "parent": "/root/Main",
                    "nodes": [
                        {
                            "class": "PanelContainer",
                            "name": "Hud",
                            "children": [
                                {"class": "Label", "name": "Title", "properties": {"text": "Ready"}},
                            ],
                        }
                    ],
                },
            },
            {"type": "node.classes", "data": {"base_class": "Control", "name_contains": "Label", "max_results": 20}},
            {
                "type": "node.class.describe",
                "data": {
                    "class": "Label",
                    "storage_only": True,
                    "properties": ["text"],
                    "methods": ["set_text"],
                    "signals": ["renamed"],
                },
            },
            {
                "type": "script.classes",
                "data": {
                    "path": "res://scripts",
                    "class_name": "AgentTool",
                    "base_class": "Node",
                    "max_results": 20,
                },
            },
            {
                "type": "script.file.describe",
                "data": {
                    "path": "res://scripts/agent_tool.gd",
                    "include_source": True,
                },
            },
            {
                "type": "fs.replace_text",
                "data": {
                    "path": "res://scripts/player.gd",
                    "old_text": "return 1",
                    "new_text": "return 2",
                    "expected_replacements": 1,
                    "dry_run": False,
                },
            },
            {
                "type": "fs.replace_text_many",
                "data": {
                    "path": "res://scripts",
                    "old_text": "extends Node",
                    "new_text": "extends Node2D",
                    "extension": "gd",
                    "expected_files": 2,
                    "expected_replacements": 2,
                    "dry_run": False,
                },
            },
            {
                "type": "resource.save",
                "data": {
                    "path": "res://data/base.tres",
                    "class": "Resource",
                    "properties": {
                        "resource_name": "Base",
                        "dependency": {"$type": "ResourceRef", "path": "res://data/dependency.tres"},
                    },
                },
            },
            {
                "type": "resource.files",
                "data": {
                    "path": "res://data",
                    "name_contains": "base",
                    "class": "Resource",
                    "resource_name": "Base",
                    "max_results": 20,
                },
            },
            {
                "type": "resource.file.describe",
                "data": {
                    "path": "res://data/base.tres",
                    "include_source": True,
                },
            },
            {"type": "resource.classes", "data": {"name_contains": "Gradient", "max_results": 20}},
            {"type": "resource.class.describe", "data": {"class": "GradientTexture1D", "storage_only": True}},
            {
                "type": "resource.set_properties",
                "data": {
                    "path": "res://data/base.tres",
                    "properties": {"resource_name": "BaseV2"},
                    "save": True,
                },
            },
            {
                "type": "resource.duplicate",
                "data": {
                    "source": "res://data/base.tres",
                    "destination": "res://data/variant.tres",
                    "properties": {"resource_name": "Variant"},
                    "deep": True,
                    "overwrite": True,
                },
            },
        ]

        code = generate_test_from_trace(events, test_name="authoring replay")

        self.assertIn("def test_authoring_replay(godot):", code)
        self.assertIn("godot.create_node_tree([{'children': [{'class': 'Label', 'name': 'Title', 'properties': {'text': 'Ready'}}], 'class': 'PanelContainer', 'name': 'Hud'}], parent='/root/Main')", code)
        self.assertIn("godot.node_classes(base_class='Control', name_contains='Label', max_results=20)", code)
        self.assertIn(
            "godot.node_class_describe('Label', storage_only=True, properties=['text'], methods=['set_text'], signals=['renamed'])",
            code,
        )
        self.assertIn(
            "godot.script_classes(path='res://scripts', class_name='AgentTool', base_class='Node', max_results=20)",
            code,
        )
        self.assertIn("godot.script_file_describe('res://scripts/agent_tool.gd', include_source=True)", code)
        self.assertIn("godot.fs_replace_text('res://scripts/player.gd', 'return 1', 'return 2')", code)
        self.assertIn(
            "godot.fs_replace_text_many('extends Node', 'extends Node2D', 'res://scripts', expected_files=2, expected_replacements=2, extension='gd', dry_run=False)",
            code,
        )
        self.assertIn("godot.resource_save('res://data/base.tres', properties={'dependency': {'$type': 'ResourceRef', 'path': 'res://data/dependency.tres'}, 'resource_name': 'Base'})", code)
        self.assertIn(
            "godot.resource_files(path='res://data', name_contains='base', resource_name='Base', class_name='Resource', max_results=20)",
            code,
        )
        self.assertIn("godot.resource_file_describe('res://data/base.tres', include_source=True)", code)
        self.assertIn("godot.resource_classes(name_contains='Gradient', max_results=20)", code)
        self.assertIn("godot.resource_class_describe('GradientTexture1D', storage_only=True)", code)
        self.assertIn("godot.resource_set_properties('res://data/base.tres', {'resource_name': 'BaseV2'})", code)
        self.assertIn("godot.resource_duplicate('res://data/base.tres', 'res://data/variant.tres', properties={'resource_name': 'Variant'})", code)
        compile(code, "<generated-authoring>", "exec")

    def test_generate_test_from_trace_translates_granular_node_authoring_events(self) -> None:
        events = [
            {
                "type": "node.create",
                "data": {
                    "parent": "/root/Main",
                    "class": "Label",
                    "name": "StatusLabel",
                    "owner_scene": False,
                    "undo": False,
                },
            },
            {
                "type": "node.instantiate_scene",
                "data": {
                    "source_scene": "res://scenes/badge.tscn",
                    "parent": "/root/Main/Hud",
                    "name": "BadgeInstance",
                    "index": 1,
                },
            },
            {
                "type": "node.save_as_scene",
                "data": {
                    "source": "/root/Main/Hud",
                    "path": "res://scenes/generated_hud.tscn",
                    "overwrite": False,
                },
            },
            {
                "type": "node.set_properties",
                "data": {"path": "/root/Main/StatusLabel", "values": {"text": "Ready"}, "undo": False},
            },
            {
                "type": "node.set_all_properties",
                "data": {
                    "selector": {"class": "Button"},
                    "root": "/root/Main",
                    "values": {"disabled": True},
                    "limit": 2,
                    "undo": False,
                },
            },
            {
                "type": "node.attach_script",
                "data": {
                    "path": "/root/Main/StatusLabel",
                    "script": "res://scripts/status_label.gd",
                    "inspect": True,
                    "reload": False,
                },
            },
            {"type": "node.detach_script", "data": {"path": "/root/Main/StatusLabel", "inspect": True}},
            {
                "type": "node.set_metadata",
                "data": {"path": "/root/Main/StatusLabel", "values": {"agent_tag": "hud"}, "undo": False},
            },
            {
                "type": "node.remove_metadata",
                "data": {"path": "/root/Main/StatusLabel", "names": ["agent_tag"], "undo": False},
            },
            {
                "type": "node.add_group",
                "data": {"path": "/root/Main/StatusLabel", "group": "agent_ui", "persistent": False},
            },
            {"type": "node.remove_group", "data": {"path": "/root/Main/StatusLabel", "group": "agent_ui"}},
            {
                "type": "node.reparent",
                "data": {
                    "old_path": "/root/Main/StatusLabel",
                    "new_parent": "/root/Main/Hud",
                    "index": 0,
                    "keep_global_transform": False,
                    "owner_scene": False,
                },
            },
            {"type": "node.move", "data": {"path": "/root/Main/Hud/StatusLabel", "index": 2}},
            {
                "type": "node.duplicate",
                "data": {
                    "source": "/root/Main/Hud/StatusLabel",
                    "parent": "/root/Main/Hud",
                    "name": "StatusLabelCopy",
                    "index": 1,
                    "flags": 15,
                    "owner_scene": False,
                },
            },
            {"type": "node.delete", "data": {"path": "/root/Main/Hud/StatusLabelCopy"}},
        ]

        code = generate_test_from_trace(events, test_name="granular node replay")

        self.assertIn("def test_granular_node_replay(godot):", code)
        self.assertIn(
            "godot.create_node('/root/Main', 'Label', name='StatusLabel', owner_scene=False, undo=False)",
            code,
        )
        self.assertIn(
            "godot.instantiate_scene('res://scenes/badge.tscn', parent='/root/Main/Hud', name='BadgeInstance', index=1)",
            code,
        )
        self.assertIn(
            "godot.save_node_as_scene('/root/Main/Hud', 'res://scenes/generated_hud.tscn', overwrite=False)",
            code,
        )
        self.assertIn(
            "godot.set_node_properties('/root/Main/StatusLabel', {'text': 'Ready'}, undo=False)",
            code,
        )
        self.assertIn(
            "godot.locator({'class': 'Button'}, root='/root/Main').set_all_properties({'disabled': True}, undo=False, limit=2)",
            code,
        )
        self.assertIn(
            "godot.attach_script('/root/Main/StatusLabel', 'res://scripts/status_label.gd', inspect=True, reload=False)",
            code,
        )
        self.assertIn("godot.detach_script('/root/Main/StatusLabel', inspect=True)", code)
        self.assertIn(
            "godot.set_node_metadata('/root/Main/StatusLabel', {'agent_tag': 'hud'}, undo=False)",
            code,
        )
        self.assertIn("godot.remove_node_metadata('/root/Main/StatusLabel', ['agent_tag'], undo=False)", code)
        self.assertIn("godot.add_node_group('/root/Main/StatusLabel', 'agent_ui', persistent=False)", code)
        self.assertIn("godot.remove_node_group('/root/Main/StatusLabel', 'agent_ui')", code)
        self.assertIn(
            "godot.reparent_node('/root/Main/StatusLabel', '/root/Main/Hud', index=0, keep_global_transform=False, owner_scene=False)",
            code,
        )
        self.assertIn("godot.move_node('/root/Main/Hud/StatusLabel', 2)", code)
        self.assertIn(
            "godot.duplicate_node('/root/Main/Hud/StatusLabel', parent='/root/Main/Hud', name='StatusLabelCopy', index=1, flags=15, owner_scene=False)",
            code,
        )
        self.assertIn("godot.delete_node('/root/Main/Hud/StatusLabelCopy')", code)
        compile(code, "<generated-granular-node-authoring>", "exec")

    def test_generate_test_from_trace_translates_project_configuration_events(self) -> None:
        events = [
            {
                "type": "project.set_setting",
                "data": {"name": "application/config/name", "value": "Agent Project", "save": True},
            },
            {
                "type": "project.summary",
                "data": {"path": "res://", "max_results": 25, "include_input_events": True},
            },
            {
                "type": "project.doctor",
                "data": {"path": "res://", "max_results": 25, "include_protocol_methods": True},
            },
            {
                "type": "project.set_main_scene",
                "data": {"path": "res://scenes/main.tscn", "save": True, "require_exists": False},
            },
            {
                "type": "project.add_autoload",
                "data": {
                    "name": "AgentState",
                    "path": "res://scripts/agent_state.gd",
                    "singleton": False,
                    "save": True,
                    "overwrite": False,
                    "require_exists": False,
                    "order": 10,
                },
            },
            {"type": "project.remove_autoload", "data": {"name": "OldState", "saved": True}},
            {
                "type": "project.set_export_preset",
                "data": {
                    "index": 0,
                    "name": "Linux",
                    "platform": "Linux/X11",
                    "export_path": "build/game.x86_64",
                    "runnable": False,
                    "options": {"binary_format/embed_pck": True},
                    "fields": {"custom_template/debug": "res://templates/debug"},
                    "overwrite": False,
                },
            },
            {
                "type": "input.action.configure",
                "data": {
                    "action": "agent_jump",
                    "deadzone": 0.25,
                    "events": [{"type": "key", "key": "J", "shift": True}],
                    "replace": True,
                    "create": False,
                },
            },
            {"type": "input.action.erase", "data": {"action": "agent_jump", "events_only": True}},
        ]

        code = generate_test_from_trace(events, test_name="project replay")

        self.assertIn("def test_project_replay(godot):", code)
        self.assertIn("godot.project_set_setting('application/config/name', 'Agent Project', save=True)", code)
        self.assertIn("godot.project_summary(max_results=25, include_input_events=True)", code)
        self.assertIn("godot.project_doctor(max_results=25, include_protocol_methods=True)", code)
        self.assertIn(
            "godot.project_set_main_scene('res://scenes/main.tscn', save=True, require_exists=False)",
            code,
        )
        self.assertIn(
            "godot.project_add_autoload('AgentState', 'res://scripts/agent_state.gd', singleton=False, save=True, overwrite=False, require_exists=False, order=10)",
            code,
        )
        self.assertIn("godot.project_remove_autoload('OldState', save=True)", code)
        self.assertIn(
            "godot.project_set_export_preset('Linux', 'Linux/X11', index=0, export_path='build/game.x86_64', runnable=False, options={'binary_format/embed_pck': True}, fields={'custom_template/debug': 'res://templates/debug'}, overwrite=False)",
            code,
        )
        self.assertIn(
            "godot.input_action_configure('agent_jump', deadzone=0.25, events=[{'key': 'J', 'shift': True, 'type': 'key'}], replace=True, create=False)",
            code,
        )
        self.assertIn("godot.input_action_erase('agent_jump', events_only=True)", code)
        compile(code, "<generated-project-config>", "exec")

    def test_generate_test_from_trace_translates_editor_workflow_events(self) -> None:
        events = [
            {
                "type": "scene.new",
                "data": {"class": "Control", "name": "AgentScene", "close_existing": False},
            },
            {"type": "scene.open", "data": {"path": "res://scenes/main.tscn"}},
            {
                "type": "scene.files",
                "data": {
                    "path": "res://scenes",
                    "name_contains": "main",
                    "root_class": "Control",
                    "include_nodes": True,
                    "max_results": 20,
                },
            },
            {
                "type": "scene.file.describe",
                "data": {
                    "path": "res://scenes/main.tscn",
                    "include_properties": True,
                },
            },
            {"type": "scene.save", "data": {"path": "res://scenes/generated.tscn"}},
            {"type": "editor.play", "data": {"scene": "main"}},
            {"type": "editor.stop", "data": {}},
            {"type": "editor.ui.switch_main_screen", "data": {"name": "Script"}},
            {"type": "editor.ui.hide_bottom_panel", "data": {}},
            {"type": "editor.undo", "data": {"selector": "#Player", "root": "/root/Main", "history_id": 3}},
            {"type": "editor.redo", "data": {"selector": "#Player", "history_id": 3}},
            {
                "type": "editor.selection.set",
                "data": {
                    "selectors": ["#Player", {"path": "/root/Main/Hud"}],
                    "root": "/root/Main",
                    "inspect": True,
                    "property": "position",
                    "inspector_only": True,
                },
            },
            {
                "type": "editor.inspect",
                "data": {"selector": "#Player", "root": "/root/Main", "property": "position", "inspector_only": True},
            },
            {
                "type": "editor.inspector.set_property",
                "data": {
                    "selector": "#Player",
                    "root": "/root/Main",
                    "property": "visible",
                    "value": False,
                    "inspect": False,
                },
            },
            {
                "type": "editor.inspector.set_properties",
                "data": {
                    "resource_path": "res://data/player.tres",
                    "values": {"resource_name": "PlayerData"},
                    "save": True,
                    "inspector_only": True,
                },
            },
            {
                "type": "editor.script.open",
                "data": {
                    "path": "res://scripts/player.gd",
                    "line": 12,
                    "column": 4,
                    "grab_focus": False,
                    "force": True,
                    "restore_external_editor": True,
                },
            },
            {"type": "editor.filesystem.scan", "data": {"paths": ["res://scripts", "res://scenes"]}},
            {"type": "editor.filesystem.select", "data": {"path": "res://scripts/player.gd", "inspect": True}},
            {
                "type": "editor.filesystem.open",
                "data": {
                    "path": "res://data/player.tres",
                    "mode": "resource",
                    "property": "resource_name",
                    "inspector_only": True,
                },
            },
        ]

        code = generate_test_from_trace(events, test_name="editor workflow replay")

        self.assertIn("def test_editor_workflow_replay(godot):", code)
        self.assertIn("godot.editor_new_scene(class_name='Control', name='AgentScene', close_existing=False)", code)
        self.assertIn("godot.editor_open_scene('res://scenes/main.tscn')", code)
        self.assertIn(
            "godot.scene_files(path='res://scenes', name_contains='main', root_class='Control', max_results=20, include_nodes=True)",
            code,
        )
        self.assertIn("godot.scene_file_describe('res://scenes/main.tscn', include_properties=True)", code)
        self.assertIn("godot.editor_save_scene('res://scenes/generated.tscn')", code)
        self.assertIn("godot.editor_play('main')", code)
        self.assertIn("godot.editor_stop()", code)
        self.assertIn("godot.editor_switch_main_screen('Script')", code)
        self.assertIn("godot.editor_hide_bottom_panel()", code)
        self.assertIn("godot.editor_undo('#Player', root='/root/Main', history_id=3)", code)
        self.assertIn("godot.editor_redo('#Player', history_id=3)", code)
        self.assertIn(
            "godot.editor_select(['#Player', {'path': '/root/Main/Hud'}], root='/root/Main', inspect=True, property='position', inspector_only=True)",
            code,
        )
        self.assertIn(
            "godot.editor_inspect('#Player', root='/root/Main', property='position', inspector_only=True)",
            code,
        )
        self.assertIn(
            "godot.editor_inspector_set_property('visible', False, '#Player', root='/root/Main', inspect=False)",
            code,
        )
        self.assertIn(
            "godot.editor_inspector_set_properties({'resource_name': 'PlayerData'}, resource_path='res://data/player.tres', save=True, inspector_only=True)",
            code,
        )
        self.assertIn(
            "godot.editor_open_script('res://scripts/player.gd', line=12, column=4, grab_focus=False, force=True, restore_external_editor=True)",
            code,
        )
        self.assertIn("godot.editor_scan_filesystem(['res://scripts', 'res://scenes'])", code)
        self.assertIn("godot.editor_filesystem_select('res://scripts/player.gd', inspect=True)", code)
        self.assertIn(
            "godot.editor_filesystem_open('res://data/player.tres', mode='resource', property='resource_name', inspector_only=True)",
            code,
        )
        compile(code, "<generated-editor-workflow>", "exec")

    def test_generate_test_from_trace_translates_runtime_probe_and_signal_events(self) -> None:
        events = [
            {"type": "protocol.describe", "data": {"include_features": False}},
            {"type": "node.call_all", "data": {"selector": {"group": "enemies"}, "root": "/root/Main", "method": "queue_free", "limit": 3}},
            {
                "type": "animation.play",
                "data": {
                    "path": "/root/Main/AnimationPlayer",
                    "animation": "intro",
                    "custom_blend": 0.2,
                    "custom_speed": 1.5,
                    "from_end": True,
                },
            },
            {"type": "animation.stop", "data": {"path": "/root/Main/AnimationPlayer", "keep_state": True}},
            {"type": "animation.pause", "data": {"path": "/root/Main/AnimationPlayer"}},
            {
                "type": "animation.seek",
                "data": {"path": "/root/Main/AnimationPlayer", "position": 0.5, "update": False, "update_only": True},
            },
            {
                "type": "animation.advance",
                "data": {"path": "/root/Main/AnimationPlayer", "delta": 0.25, "update": False},
            },
            {"type": "physics2d.point", "data": {"position": {"$type": "Vector2", "x": 10.0, "y": 20.0}, "max_results": 4}},
            {
                "type": "physics2d.ray",
                "data": {
                    "from": {"$type": "Vector2", "x": 0.0, "y": 1.0},
                    "to": {"$type": "Vector2", "x": 40.0, "y": 50.0},
                    "collide_with_areas": False,
                },
            },
            {
                "type": "physics3d.point",
                "data": {"position": {"$type": "Vector3", "x": 1.0, "y": 2.0, "z": 3.0}},
            },
            {
                "type": "physics3d.ray",
                "data": {
                    "from": {"$type": "Vector3", "x": 1.0, "y": 2.0, "z": 3.0},
                    "to": {"$type": "Vector3", "x": 4.0, "y": 5.0, "z": 6.0},
                    "collision_mask": 4,
                },
            },
            {"type": "audio.bus.info", "data": {"bus_name": "Master", "bus_index": 0}},
            {
                "type": "navigation.query_path",
                "data": {
                    "start": [0.0, 0.0, 0.0],
                    "target": [1.0, 2.0, 3.0],
                    "dimension": 3,
                },
            },
            {
                "type": "camera3d.ray",
                "data": {
                    "camera": {"path": "/root/Main/Camera3D", "class": "Camera3D"},
                    "screen_position": {"$type": "Vector2", "x": 320.0, "y": 180.0},
                    "max_distance": 250.0,
                },
            },
            {
                "type": "camera3d.pick",
                "data": {
                    "camera": {"path": "/root/Main/Camera3D"},
                    "screen_position": {"$type": "Vector2", "x": 320.0, "y": 180.0},
                    "collide_with_bodies": False,
                },
            },
            {
                "type": "viewport.set_size",
                "data": {"current": {"window_size": {"width": 1280, "height": 720}}},
            },
            {"type": "fs.read_text", "data": {"path": "res://scripts/player.gd"}},
            {"type": "fs.read_bytes", "data": {"path": "res://assets/icon.png", "max_bytes": 2048}},
            {"type": "fs.grep", "data": {"path": "res://scripts", "query": "TODO", "extension": "gd", "max_results": 12}},
            {"type": "fs.copy", "data": {"source": "res://data/source.tres", "destination": "res://data/copy.tres", "overwrite": False}},
            {"type": "fs.move", "data": {"source": "res://data/copy.tres", "destination": "res://data/moved.tres"}},
            {"type": "resource.dependencies", "data": {"path": "res://scenes/main.tscn"}},
            {
                "type": "resource.references",
                "data": {
                    "path": "res://scripts/main.gd",
                    "search_path": "res://scenes",
                    "dependency_type": "Script",
                    "exists": True,
                    "max_results": 20,
                },
            },
            {
                "type": "resource.move",
                "data": {
                    "source": "res://data/old_gradient.tres",
                    "destination": "res://data/new_gradient.tres",
                    "search_path": "res://data",
                    "extensions": ["tres"],
                    "expected_reference_files": 1,
                    "expected_replacements": 1,
                },
            },
            {
                "type": "resource.imports",
                "data": {
                    "path": "res://assets",
                    "importer": "texture",
                    "generated_files_ready": True,
                    "max_results": 20,
                },
            },
            {"type": "resource.import_metadata", "data": {"path": "res://assets/icon.png"}},
            {"type": "resource.reimport", "data": {"paths": ["res://assets/icon.png"], "force": True}},
            {"type": "signal.watch", "data": {"path": "/root/Main/Button", "signal": "pressed", "once": True}},
            {"type": "signal.event", "data": {"path": "/root/Main/Button", "signal": "pressed", "args": []}},
            {"type": "signal.unwatch", "data": {"id": "signal-1"}},
            {
                "type": "signal.connect",
                "data": {
                    "source": "/root/Main/Button",
                    "signal": "pressed",
                    "target": "/root/Main",
                    "method": "_on_button_pressed",
                    "flags": 1,
                },
            },
            {
                "type": "signal.disconnect",
                "data": {
                    "source": "/root/Main/Button",
                    "signal": "pressed",
                    "target": "/root/Main",
                    "method": "_on_button_pressed",
                },
            },
        ]

        code = generate_test_from_trace(events, test_name="runtime probes and signals")

        self.assertIn("def test_runtime_probes_and_signals(godot):", code)
        self.assertIn("godot.protocol_describe(include_features=False)", code)
        self.assertIn("godot.locator({'group': 'enemies'}, root='/root/Main').call_all('queue_free', limit=3)", code)
        self.assertIn("godot.animation_play('/root/Main/AnimationPlayer', 'intro', blend=0.2, speed=1.5, from_end=True)", code)
        self.assertIn("godot.animation_stop('/root/Main/AnimationPlayer', keep_state=True)", code)
        self.assertIn("godot.animation_pause('/root/Main/AnimationPlayer')", code)
        self.assertIn("godot.animation_seek('/root/Main/AnimationPlayer', 0.5, update=False, update_only=True)", code)
        self.assertIn("godot.animation_advance('/root/Main/AnimationPlayer', 0.25, update=False)", code)
        self.assertIn("godot.physics2d_point(10.0, 20.0, max_results=4)", code)
        self.assertIn("godot.physics2d_ray(0.0, 1.0, 40.0, 50.0, collide_with_areas=False)", code)
        self.assertIn("godot.physics3d_point(1.0, 2.0, 3.0)", code)
        self.assertIn("godot.physics3d_ray(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, collision_mask=4)", code)
        self.assertIn("godot.camera3d_ray(320.0, 180.0, camera='/root/Main/Camera3D', max_distance=250.0)", code)
        self.assertIn("godot.camera3d_pick(320.0, 180.0, camera='/root/Main/Camera3D', collide_with_bodies=False)", code)
        self.assertIn("godot.audio_bus_info(bus_name='Master', bus_index=0)", code)
        self.assertIn("godot.navigation_query_path([0.0, 0.0, 0.0], [1.0, 2.0, 3.0], dimension=3)", code)
        self.assertIn("godot.set_viewport_size(1280, 720)", code)
        self.assertIn("godot.fs_read_text('res://scripts/player.gd')", code)
        self.assertIn("godot.fs_read_bytes('res://assets/icon.png', max_bytes=2048)", code)
        self.assertIn("godot.fs_grep('TODO', 'res://scripts', extension='gd', max_results=12)", code)
        self.assertIn("godot.fs_copy('res://data/source.tres', 'res://data/copy.tres', overwrite=False)", code)
        self.assertIn("godot.fs_move('res://data/copy.tres', 'res://data/moved.tres')", code)
        self.assertIn("godot.resource_dependencies('res://scenes/main.tscn')", code)
        self.assertIn(
            "godot.resource_references('res://scripts/main.gd', search_path='res://scenes', dependency_type='Script', max_results=20, exists=True)",
            code,
        )
        self.assertIn(
            "godot.resource_move('res://data/old_gradient.tres', 'res://data/new_gradient.tres', search_path='res://data', expected_reference_files=1, expected_replacements=1, extensions=['tres'])",
            code,
        )
        self.assertIn(
            "godot.resource_imports(path='res://assets', importer='texture', max_results=20, generated_files_ready=True)",
            code,
        )
        self.assertIn("godot.resource_import_metadata('res://assets/icon.png')", code)
        self.assertIn("godot.resource_reimport('res://assets/icon.png', force=True)", code)
        self.assertIn("_signal_watch = godot.signal_watch('/root/Main/Button', 'pressed', once=True)", code)
        self.assertIn("godot.wait_for_signal_event(signal='pressed', path='/root/Main/Button')", code)
        self.assertIn("godot.signal_unwatch('signal-1')", code)
        self.assertIn(
            "godot.signal_connect('/root/Main/Button', 'pressed', method='_on_button_pressed', target='/root/Main', flags=1)",
            code,
        )
        self.assertIn(
            "godot.signal_disconnect('/root/Main/Button', 'pressed', method='_on_button_pressed', target='/root/Main')",
            code,
        )
        compile(code, "<generated-runtime-probes-signals>", "exec")

    def test_load_trace_events_accepts_array_and_events_object(self) -> None:
        events = [{"type": "node.click", "data": {"path": "/root/Main/Button"}}]
        self.assertEqual(normalize_trace_events({"events": events})[0]["type"], "node.click")

        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.json"
            trace_path.write_text(json.dumps(events), encoding="utf-8")
            self.assertEqual(load_trace_events(trace_path), events)

    def test_normalize_trace_events_rejects_invalid_shapes(self) -> None:
        with self.assertRaises(TraceCodegenError):
            normalize_trace_events({"not_events": []})
        with self.assertRaises(TraceCodegenError):
            normalize_trace_events([{"data": {}}])

    def test_cli_codegen_trace_writes_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_path = root / "trace.json"
            output_path = root / "generated_test.py"
            trace_path.write_text(
                json.dumps([{"type": "node.click", "data": {"path": "/root/Main/CounterButton"}}]),
                encoding="utf-8",
            )

            stdout = StringIO()
            with redirect_stdout(stdout):
                code = cli_main(
                    [
                        "codegen-trace",
                        str(trace_path),
                        "--test-name",
                        "agent playback",
                        "--output",
                        str(output_path),
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(stdout.getvalue().strip(), str(output_path.resolve()))
            generated = output_path.read_text(encoding="utf-8")
            self.assertIn("def test_agent_playback(godot):", generated)
            self.assertIn("godot.locator('/root/Main/CounterButton').click()", generated)
            compile(generated, str(output_path), "exec")

def _recorded_addon_event_types() -> set[str]:
    source = (ROOT / "addons" / "godot_playwright" / "godot_playwright_server.gd").read_text(encoding="utf-8")
    return set(re.findall(r'_record_event\("([^"]+)"', source))


def _codegen_supported_event_types() -> set[str]:
    source = (ROOT / "godot_playwright" / "codegen.py").read_text(encoding="utf-8")
    return set(re.findall(r'event_type == "([^"]+)"', source))


if __name__ == "__main__":
    unittest.main()
