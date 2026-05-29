from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .checks import (
    ResourceCheckError,
    ScriptCheckError,
    check_project_resources,
    check_project_scripts,
    check_script,
)
from .codegen import TraceCodegenError, generate_test_from_trace, load_trace_events
from .client import Godot, GodotClient, GodotPlaywrightError
from .export import ExportError, export_project
from .install import install_addon
from .inventory import ProjectInventoryError, inspect_project
from .locator_index import ProjectNodeQueryError, find_project_nodes
from .probe import ProbeError, probe_project, probe_project_scenes
from .project import ProjectError, init_project
from .runner import TestRunnerError, format_report, run_tests
from .scene import SceneInspectError, inspect_scene
from .validate import ProjectValidationError, validate_project

_AUTO_PORT = "auto"
_LAUNCH_COMMANDS = {"launch", "smoke"}
_CLIENT_COMMANDS = {"health", "snapshot", "rpc"}


def _parse_port_arg(value: str) -> int | str:
    if str(value).lower() == _AUTO_PORT:
        return _AUTO_PORT
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer or 'auto'") from exc
    if port < 0 or port > 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return port


def _add_command_connection_args(parser: argparse.ArgumentParser, *, allow_auto: bool = False) -> None:
    parser.add_argument("--host", dest="command_host", default=None)
    help_text = "Server port"
    if allow_auto:
        help_text += ", or 'auto' to allocate a free port"
    parser.add_argument("--port", dest="command_port", type=_parse_port_arg, default=None, help=help_text)


def _normalize_connection_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    args.host = getattr(args, "command_host", None) or args.host or "127.0.0.1"
    raw_port = getattr(args, "command_port", None)
    if raw_port is None:
        raw_port = args.port
    default_auto = args.command in _LAUNCH_COMMANDS
    if raw_port == _AUTO_PORT:
        if args.command in _CLIENT_COMMANDS:
            parser.error(f"{args.command} cannot use --port auto because it does not launch Godot")
        args.port = None
    elif raw_port is None:
        args.port = None if default_auto else 9777
    else:
        args.port = int(raw_port)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="godot-playwright")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=_parse_port_arg, default=None, help="Server port, or 'auto' for launch/smoke.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a small Godot project prepared for automation.")
    init_parser.add_argument("project")
    init_parser.add_argument("--name", default="Godot Playwright Project")
    init_parser.add_argument("--force", action="store_true", help="Allow writing into a non-empty directory.")
    init_parser.add_argument("--no-install", action="store_true", help="Do not install the automation add-on.")

    install_parser = subparsers.add_parser("install", help="Install the Godot add-on into a project.")
    install_parser.add_argument("project")
    install_parser.add_argument("--no-enable", action="store_true", help="Copy files without enabling the editor plugin.")
    install_parser.add_argument("--autoload", action="store_true", help="Add runtime autoload for game automation.")

    launch_parser = subparsers.add_parser("launch", help="Launch Godot and wait for the automation server.")
    launch_parser.add_argument("project")
    launch_parser.add_argument("--mode", choices=["editor", "runtime"], default="editor")
    launch_parser.add_argument("--godot", default="godot", help="Godot executable.")
    launch_parser.add_argument("--no-headless", action="store_true")
    launch_parser.add_argument("--no-install", action="store_true")
    launch_parser.add_argument("--autoload", action="store_true", help="Force runtime autoload installation.")
    _add_command_connection_args(launch_parser, allow_auto=True)

    health_parser = subparsers.add_parser("health", help="Read server health.")
    _add_command_connection_args(health_parser)

    snapshot_parser = subparsers.add_parser("snapshot", help="Print a scene tree snapshot.")
    snapshot_parser.add_argument("--root", default="edited")
    snapshot_parser.add_argument("--max-depth", type=int, default=8)
    snapshot_parser.add_argument("--include-properties", action="store_true")
    _add_command_connection_args(snapshot_parser)

    smoke_parser = subparsers.add_parser("smoke", help="Launch Godot and run a structured automation smoke check.")
    smoke_parser.add_argument("project")
    smoke_parser.add_argument("--mode", choices=["editor", "runtime"], default="runtime")
    smoke_parser.add_argument("--godot", default="godot")
    smoke_parser.add_argument("--no-headless", action="store_true")
    smoke_parser.add_argument("--save-path", default="res://scenes/godot_playwright_smoke.tscn")
    _add_command_connection_args(smoke_parser, allow_auto=True)

    probe_parser = subparsers.add_parser("probe", help="Launch a runtime scene briefly and report Godot log errors.")
    probe_parser.add_argument("project")
    probe_parser.add_argument("--scene", default="", help="Optional scene path or UID to run.")
    probe_parser.add_argument("--frames", type=int, default=5, help="Number of frames to run before quitting.")
    probe_parser.add_argument("--godot", default="godot")
    probe_parser.add_argument("--no-headless", action="store_true")
    probe_parser.add_argument("--timeout", type=float, default=30.0)
    probe_parser.add_argument("--artifacts-dir", default="godot-playwright-report")
    probe_parser.add_argument("--log-path", default="")
    probe_parser.add_argument("--allow-errors", action="store_true", help="Return success when Godot exits cleanly despite logged errors.")
    probe_parser.add_argument("--extra-arg", action="append", default=[], help="Additional Godot CLI argument.")
    probe_parser.add_argument("--json", action="store_true", help="Print the full JSON probe report.")

    probe_scenes_parser = subparsers.add_parser("probe-scenes", help="Launch every selected project scene briefly and aggregate Godot log errors.")
    probe_scenes_parser.add_argument("project")
    probe_scenes_parser.add_argument("scenes", nargs="*", default=[], help="Optional scene files or directories to probe.")
    probe_scenes_parser.add_argument("--exclude", action="append", default=[], help="Glob to exclude, e.g. addons/**.")
    probe_scenes_parser.add_argument("--frames", type=int, default=5, help="Number of frames to run each scene before quitting.")
    probe_scenes_parser.add_argument("--godot", default="godot")
    probe_scenes_parser.add_argument("--no-headless", action="store_true")
    probe_scenes_parser.add_argument("--timeout", type=float, default=30.0)
    probe_scenes_parser.add_argument("--artifacts-dir", default="godot-playwright-report")
    probe_scenes_parser.add_argument("--allow-errors", action="store_true", help="Return success when Godot exits cleanly despite logged errors.")
    probe_scenes_parser.add_argument("--extra-arg", action="append", default=[], help="Additional Godot CLI argument.")
    probe_scenes_parser.add_argument("--json", action="store_true", help="Print the full JSON scene probe report.")

    check_script_parser = subparsers.add_parser("check-script", help="Run Godot's GDScript parser for one script.")
    check_script_parser.add_argument("project")
    check_script_parser.add_argument("script")
    check_script_parser.add_argument("--godot", default="godot")
    check_script_parser.add_argument("--no-headless", action="store_true")
    check_script_parser.add_argument("--timeout", type=float, default=60.0)
    check_script_parser.add_argument("--artifacts-dir", default="godot-playwright-report")
    check_script_parser.add_argument("--log-path", default="")
    check_script_parser.add_argument("--extra-arg", action="append", default=[], help="Additional Godot CLI argument.")
    check_script_parser.add_argument("--no-import-cache", action="store_true", help="Skip the pre-check Godot import/cache warmup.")
    check_script_parser.add_argument("--json", action="store_true", help="Print the full JSON check report.")

    check_scripts_parser = subparsers.add_parser("check-scripts", help="Run Godot's GDScript parser for project scripts.")
    check_scripts_parser.add_argument("project")
    check_scripts_parser.add_argument("paths", nargs="*", default=[])
    check_scripts_parser.add_argument("--exclude", action="append", default=[], help="Glob to exclude, e.g. addons/**.")
    check_scripts_parser.add_argument("--godot", default="godot")
    check_scripts_parser.add_argument("--no-headless", action="store_true")
    check_scripts_parser.add_argument("--timeout", type=float, default=60.0)
    check_scripts_parser.add_argument("--artifacts-dir", default="godot-playwright-report")
    check_scripts_parser.add_argument("--extra-arg", action="append", default=[], help="Additional Godot CLI argument.")
    check_scripts_parser.add_argument("--no-import-cache", action="store_true", help="Skip the pre-check Godot import/cache warmup.")
    check_scripts_parser.add_argument("--json", action="store_true", help="Print the full JSON check report.")

    check_resources_parser = subparsers.add_parser(
        "check-resources",
        help="Check text scene/resource external dependencies without launching Godot.",
    )
    check_resources_parser.add_argument("project")
    check_resources_parser.add_argument("paths", nargs="*", default=[])
    check_resources_parser.add_argument("--exclude", action="append", default=[], help="Glob to exclude, e.g. addons/**.")
    check_resources_parser.add_argument("--json", action="store_true", help="Print the full JSON check report.")

    inspect_scene_parser = subparsers.add_parser(
        "inspect-scene",
        help="Parse a text .tscn file and print its node/resource structure without launching Godot.",
    )
    inspect_scene_parser.add_argument("project")
    inspect_scene_parser.add_argument("scene")
    inspect_scene_parser.add_argument("--no-properties", action="store_true", help="Omit node and sub-resource properties.")
    inspect_scene_parser.add_argument("--json", action="store_true", help="Print the full JSON scene report.")

    inspect_project_parser = subparsers.add_parser(
        "inspect-project",
        help="Inspect project.godot, autoloads, export presets, and project files without launching Godot.",
    )
    inspect_project_parser.add_argument("project")
    inspect_project_parser.add_argument("--exclude", action="append", default=[], help="Glob to exclude, e.g. addons/**.")
    inspect_project_parser.add_argument("--no-settings", action="store_true", help="Omit full parsed settings maps.")
    inspect_project_parser.add_argument("--json", action="store_true", help="Print the full JSON project inventory.")

    find_nodes_parser = subparsers.add_parser(
        "find-nodes",
        help="Query text .tscn nodes by Playwright-style selectors without launching Godot.",
    )
    find_nodes_parser.add_argument("project")
    find_nodes_parser.add_argument("scenes", nargs="*", default=[], help="Optional scene files or directories to query.")
    find_nodes_parser.add_argument("--exclude", action="append", default=[], help="Glob to exclude, e.g. addons/**.")
    find_nodes_parser.add_argument("--selector", default=None, help="String selector or JSON selector object.")
    find_nodes_parser.add_argument("--name", default=None, help="Exact node name.")
    find_nodes_parser.add_argument("--name-contains", default=None, help="Substring of the node name.")
    find_nodes_parser.add_argument("--class", dest="class_name", default=None, help="Exact Godot class/type.")
    find_nodes_parser.add_argument("--role", default=None, help="Inferred accessible role.")
    find_nodes_parser.add_argument("--role-name", default=None, help="Exact accessible name.")
    find_nodes_parser.add_argument("--role-name-contains", default=None, help="Substring of the accessible name.")
    find_nodes_parser.add_argument("--test-id", default=None, help="metadata/test_id value.")
    find_nodes_parser.add_argument("--text", default=None, help="Exact text property.")
    find_nodes_parser.add_argument("--text-contains", default=None, help="Substring of the text property.")
    find_nodes_parser.add_argument("--property", dest="property_name", default=None, help="Property name that must exist.")
    find_nodes_parser.add_argument("--value", dest="property_value", default=None, help="Optional property value, parsed as JSON when possible.")
    find_nodes_parser.add_argument("--include-properties", action="store_true", help="Include parsed node properties in matches.")
    find_nodes_parser.add_argument("--limit", type=int, default=0, help="Maximum matches to return; 0 means unlimited.")
    find_nodes_parser.add_argument("--json", action="store_true", help="Print the full JSON node query report.")

    validate_parser = subparsers.add_parser(
        "validate",
        help="Run a project-level validation gate over scripts, resources, scenes, and runtime probes.",
    )
    validate_parser.add_argument("project")
    validate_parser.add_argument("paths", nargs="*", default=[])
    validate_parser.add_argument("--exclude", action="append", default=[], help="Glob to exclude, e.g. addons/**.")
    validate_parser.add_argument("--godot", default="godot")
    validate_parser.add_argument("--no-headless", action="store_true")
    validate_parser.add_argument("--timeout", type=float, default=60.0)
    validate_parser.add_argument("--artifacts-dir", default="godot-playwright-report")
    validate_parser.add_argument("--frames", type=int, default=5, help="Frames for runtime scene probes.")
    validate_parser.add_argument("--extra-arg", action="append", default=[], help="Additional Godot CLI argument.")
    validate_parser.add_argument("--no-import-cache", action="store_true", help="Skip the pre-check Godot import/cache warmup.")
    validate_parser.add_argument("--allow-runtime-errors", action="store_true")
    validate_parser.add_argument("--skip-inventory", action="store_true")
    validate_parser.add_argument("--skip-scripts", action="store_true")
    validate_parser.add_argument("--skip-resources", action="store_true")
    validate_parser.add_argument("--skip-scene-inspect", action="store_true")
    validate_parser.add_argument("--skip-runtime", action="store_true")
    validate_parser.add_argument("--json", action="store_true", help="Print the full JSON validation report.")

    export_parser = subparsers.add_parser("export", help="Run a Godot export preset and write a structured report.")
    export_parser.add_argument("project")
    export_parser.add_argument("preset")
    export_parser.add_argument("output")
    export_parser.add_argument("--mode", choices=["release", "debug", "pack", "patch"], default="release")
    export_parser.add_argument("--godot", default="godot")
    export_parser.add_argument("--no-headless", action="store_true")
    export_parser.add_argument("--timeout", type=float, default=300.0)
    export_parser.add_argument("--log-path", default="")
    export_parser.add_argument("--no-create-dirs", action="store_true")
    export_parser.add_argument("--patches", default="", help="Comma-separated patch pack paths for --mode patch.")
    export_parser.add_argument("--extra-arg", action="append", default=[], help="Additional Godot CLI argument.")
    export_parser.add_argument("--json", action="store_true", help="Print the full JSON export report.")

    test_parser = subparsers.add_parser("test", help="Run Python automation tests against a Godot project.")
    test_parser.add_argument("project")
    test_parser.add_argument("tests", nargs="*", default=["tests"])
    test_parser.add_argument("--mode", choices=["editor", "runtime"], default="runtime")
    test_parser.add_argument("--godot", default="godot")
    test_parser.add_argument("--no-headless", action="store_true")
    test_parser.add_argument("--timeout", type=float, default=20.0)
    test_parser.add_argument("--test-timeout", type=float, default=0.0, help="Fail each test attempt after this many seconds; 0 disables the guard.")
    test_parser.add_argument("--artifacts-dir", default="godot-playwright-report")
    test_parser.add_argument("--junit-xml", default="", help="Write a JUnit XML report to this path.")
    test_parser.add_argument("--trace", choices=["off", "on", "retain-on-failure"], default="retain-on-failure")
    test_parser.add_argument(
        "--screenshots",
        choices=["off", "on", "only-on-failure"],
        default="off",
        help="Capture viewport PNG artifacts for each test attempt.",
    )
    test_parser.add_argument("--update-snapshots", action="store_true")
    test_parser.add_argument("--reuse-godot", action="store_true", help="Run all tests in one Godot process.")
    test_parser.add_argument("--grep", action="append", default=[], help="Regex filter over test ids; can be used more than once.")
    test_parser.add_argument("--grep-invert", action="store_true", help="Run tests that do not match --grep.")
    test_parser.add_argument("--shard", default=None, help="Run one deterministic test shard, formatted current/total, e.g. 1/3.")
    test_parser.add_argument("--list", action="store_true", help="List selected tests without launching Godot.")
    test_parser.add_argument("--retries", type=int, default=0, help="Retry failed tests up to this many times.")
    test_parser.add_argument("--max-failures", type=int, default=0, help="Stop after this many failed tests; 0 disables fail-fast.")
    test_parser.add_argument("--workers", type=int, default=1, help="Number of isolated test worker processes.")
    test_parser.add_argument("--json", action="store_true", help="Print the full JSON report to stdout.")

    codegen_trace_parser = subparsers.add_parser(
        "codegen-trace",
        help="Generate an editable Python test from a Godot Playwright trace JSON file.",
    )
    codegen_trace_parser.add_argument("trace", help="Trace JSON file produced by --trace on.")
    codegen_trace_parser.add_argument("--test-name", default="test_generated_trace")
    codegen_trace_parser.add_argument("--output", default="", help="Write generated Python to this file instead of stdout.")

    rpc_parser = subparsers.add_parser("rpc", help="Invoke an RPC method.")
    rpc_parser.add_argument("method")
    rpc_parser.add_argument("params", nargs="?", default="{}")
    _add_command_connection_args(rpc_parser)

    args = parser.parse_args(argv)
    _normalize_connection_args(parser, args)

    try:
        if args.command == "init":
            project = init_project(
                args.project,
                name=args.name,
                force=args.force,
                install=not args.no_install,
            )
            print(project)
            return 0

        if args.command == "install":
            target = install_addon(args.project, enable=not args.no_enable, autoload=args.autoload)
            print(target)
            return 0

        if args.command == "launch":
            return _launch(args)

        if args.command == "smoke":
            _print_json(_smoke(args))
            return 0

        if args.command == "probe":
            report = probe_project(
                args.project,
                scene=args.scene,
                executable=args.godot,
                headless=not args.no_headless,
                frames=args.frames,
                timeout=args.timeout,
                artifacts_dir=args.artifacts_dir,
                log_path=args.log_path or None,
                allow_errors=args.allow_errors,
                extra_args=args.extra_arg,
            )
            if args.json:
                _print_json(report)
            else:
                print(_format_probe_report(report))
            return 0 if report["ok"] else 1

        if args.command == "probe-scenes":
            report = probe_project_scenes(
                args.project,
                args.scenes,
                exclude=args.exclude,
                executable=args.godot,
                headless=not args.no_headless,
                frames=args.frames,
                timeout=args.timeout,
                artifacts_dir=args.artifacts_dir,
                allow_errors=args.allow_errors,
                extra_args=args.extra_arg,
            )
            if args.json:
                _print_json(report)
            else:
                print(_format_scene_probe_report(report))
            return 0 if report["ok"] else 1

        if args.command == "check-script":
            report = check_script(
                args.project,
                args.script,
                executable=args.godot,
                headless=not args.no_headless,
                timeout=args.timeout,
                artifacts_dir=args.artifacts_dir,
                log_path=args.log_path or None,
                extra_args=args.extra_arg,
                ensure_import_cache=not args.no_import_cache,
            )
            if args.json:
                _print_json(report)
            else:
                print(_format_script_check_report(report))
            return 0 if report["ok"] else 1

        if args.command == "check-scripts":
            report = check_project_scripts(
                args.project,
                args.paths,
                exclude=args.exclude,
                executable=args.godot,
                headless=not args.no_headless,
                timeout=args.timeout,
                artifacts_dir=args.artifacts_dir,
                extra_args=args.extra_arg,
                ensure_import_cache=not args.no_import_cache,
            )
            if args.json:
                _print_json(report)
            else:
                print(_format_project_script_check_report(report))
            return 0 if report["ok"] else 1

        if args.command == "check-resources":
            report = check_project_resources(
                args.project,
                args.paths,
                exclude=args.exclude,
            )
            if args.json:
                _print_json(report)
            else:
                print(_format_project_resource_check_report(report))
            return 0 if report["ok"] else 1

        if args.command == "inspect-scene":
            report = inspect_scene(
                args.project,
                args.scene,
                include_properties=not args.no_properties,
            )
            if args.json:
                _print_json(report)
            else:
                print(_format_scene_inspect_report(report))
            return 0 if report["ok"] else 1

        if args.command == "inspect-project":
            report = inspect_project(
                args.project,
                exclude=args.exclude,
                include_settings=not args.no_settings,
            )
            if args.json:
                _print_json(report)
            else:
                print(_format_project_inventory_report(report))
            return 0 if report["ok"] else 1

        if args.command == "find-nodes":
            report = find_project_nodes(
                args.project,
                args.scenes,
                exclude=args.exclude,
                selector=_parse_selector_arg(args.selector),
                name=args.name,
                name_contains=args.name_contains,
                class_name=args.class_name,
                role=args.role,
                role_name=args.role_name,
                role_name_contains=args.role_name_contains,
                test_id=args.test_id,
                text=args.text,
                text_contains=args.text_contains,
                property_name=args.property_name,
                property_value=_parse_cli_value(args.property_value),
                include_properties=args.include_properties,
                limit=args.limit,
            )
            if args.json:
                _print_json(report)
            else:
                print(_format_project_node_query_report(report))
            return 0 if report["ok"] else 1

        if args.command == "validate":
            report = validate_project(
                args.project,
                args.paths,
                exclude=args.exclude,
                executable=args.godot,
                headless=not args.no_headless,
                timeout=args.timeout,
                artifacts_dir=args.artifacts_dir,
                frames=args.frames,
                extra_args=args.extra_arg,
                ensure_import_cache=not args.no_import_cache,
                allow_runtime_errors=args.allow_runtime_errors,
                skip_inventory=args.skip_inventory,
                skip_scripts=args.skip_scripts,
                skip_resources=args.skip_resources,
                skip_scene_inspect=args.skip_scene_inspect,
                skip_runtime=args.skip_runtime,
            )
            if args.json:
                _print_json(report)
            else:
                print(_format_project_validation_report(report))
            return 0 if report["ok"] else 1

        if args.command == "export":
            report = export_project(
                args.project,
                args.preset,
                args.output,
                mode=args.mode,
                executable=args.godot,
                headless=not args.no_headless,
                timeout=args.timeout,
                log_path=args.log_path or None,
                create_dirs=not args.no_create_dirs,
                patches=[patch for patch in args.patches.split(",") if patch],
                extra_args=args.extra_arg,
            )
            if args.json:
                _print_json(report)
            else:
                print(_format_export_report(report))
            return 0 if report["ok"] else 1

        if args.command == "test":
            report = run_tests(
                args.project,
                args.tests,
                mode=args.mode,
                executable=args.godot,
                headless=not args.no_headless,
                timeout=args.timeout,
                artifacts_dir=args.artifacts_dir,
                trace=args.trace,
                update_snapshots=args.update_snapshots,
                reuse_godot=args.reuse_godot,
                grep=args.grep,
                grep_invert=args.grep_invert,
                shard=args.shard,
                list_only=args.list,
                retries=args.retries,
                test_timeout=args.test_timeout,
                workers=args.workers,
                screenshots=args.screenshots,
                max_failures=args.max_failures,
                junit_xml=args.junit_xml or None,
            )
            if args.json:
                _print_json(report)
            else:
                print(format_report(report))
            if args.list:
                return 0
            return 0 if report["failed"] == 0 else 1

        if args.command == "codegen-trace":
            code = generate_test_from_trace(load_trace_events(args.trace), test_name=args.test_name)
            if args.output:
                output_path = Path(args.output).expanduser().resolve()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(code, encoding="utf-8")
                print(output_path)
            else:
                print(code, end="")
            return 0

        client = GodotClient(args.host, args.port)
        if args.command == "health":
            _print_json(client.health())
            return 0
        if args.command == "snapshot":
            _print_json(
                client.snapshot(
                    root=args.root,
                    max_depth=args.max_depth,
                    include_properties=args.include_properties,
                )
            )
            return 0
        if args.command == "rpc":
            params = json.loads(args.params)
            if not isinstance(params, dict):
                raise SystemExit("params must be a JSON object")
            _print_json(client.rpc(args.method, params))
            return 0
    except (
        GodotPlaywrightError,
        OSError,
        json.JSONDecodeError,
        ProjectError,
        TestRunnerError,
        ExportError,
        ScriptCheckError,
        ResourceCheckError,
        ProbeError,
        SceneInspectError,
        ProjectValidationError,
        ProjectInventoryError,
        ProjectNodeQueryError,
        TraceCodegenError,
    ) as exc:
        print(f"godot-playwright: {exc}", file=sys.stderr)
        return 1

    parser.error(f"Unhandled command {args.command}")
    return 2


def _launch(args: argparse.Namespace) -> int:
    godot = Godot(
        args.project,
        mode=args.mode,
        executable=args.godot,
        host=args.host,
        port=args.port,
        headless=not args.no_headless,
        install=not args.no_install,
        autoload=args.autoload if args.autoload else None,
        stdout=None,
    )
    godot.start()
    print(f"Godot Playwright ready on http://{godot.host}:{godot.port}")
    try:
        while godot.process is not None and godot.process.poll() is None:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        godot.close()
    return 0


def _smoke(args: argparse.Namespace) -> dict[str, Any]:
    output: dict[str, Any] = {"mode": args.mode}
    with Godot(
        args.project,
        mode=args.mode,
        executable=args.godot,
        host=args.host,
        port=args.port,
        headless=not args.no_headless,
    ) as godot:
        output["health"] = godot.health()
        output["engine"] = godot.rpc("engine.info")
        output["snapshot"] = godot.snapshot(max_depth=3, include_properties=True)

        if args.mode == "runtime":
            nodes = godot.locator("#CounterButton").find(limit=1)
            output["counter_button_present"] = bool(nodes)
            if nodes:
                button = godot.locator("#CounterButton")
                before = button.get("text")
                button.click()
                after = button.get("text")
                output["counter_button"] = {"before": before, "after": after}
        else:
            godot.editor_new_scene(class_name="Control", name="SmokeScene")
            godot.create_node("edited", "Label", name="SmokeLabel")
            label = godot.locator("#SmokeLabel")
            label.set("text", "saved by godot-playwright smoke")
            output["selection"] = godot.editor_select("#SmokeLabel", inspect=True)
            output["inspected_label"] = godot.editor_inspect(selector="#SmokeLabel", property="text")
            godot.editor_save_scene(args.save_path)
            output["saved_scene"] = args.save_path
            script_path = "res://scripts/godot_playwright_smoke_tool.gd"
            resource_path = "res://data/godot_playwright_smoke_resource.tres"
            godot.fs_write_text(script_path, "extends Node\n\nfunc smoke_value() -> int:\n\treturn 1\n")
            godot.resource_save(resource_path, properties={"resource_name": "GodotPlaywrightSmoke"})
            output["opened_script"] = godot.editor_open_script(script_path, line=3)
            output["script_description"] = godot.editor_script_describe(script_path)
            output["filesystem_scan"] = godot.editor_scan_filesystem([script_path, resource_path])
            output["inspector"] = godot.inspector(resource_path=resource_path).describe(properties=["resource_name"])
            output["inspector_property"] = godot.inspector(resource_path=resource_path).property("resource_name").value()
            godot.inspector(resource_path=resource_path).property("resource_name").set("GodotPlaywrightSmokeV2", save=True)
            godot.resource_reimport([script_path, resource_path])
            output["generated_files"] = {
                "script": godot.fs_exists(script_path),
                "script_entry": godot.editor_filesystem_describe(script_path),
                "script_search": godot.editor_filesystem_find("res://scripts", name="godot_playwright_smoke_tool.gd"),
                "resource": godot.resource_inspect(resource_path),
            }
            output["generated_snapshot"] = godot.snapshot(max_depth=3, include_properties=True)

    return output


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def _parse_selector_arg(value: str | None) -> str | dict[str, Any] | None:
    if value is None:
        return None
    stripped = value.strip()
    if stripped.startswith("{"):
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise ValueError("--selector JSON must be an object")
        return parsed
    return value


def _parse_cli_value(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _format_export_report(report: dict[str, Any]) -> str:
    status = "PASS" if report.get("ok") else "FAIL"
    lines = [
        f"{status} export {report.get('preset')} ({report.get('mode')})",
        f"  output: {report.get('output_path')}",
        f"  log: {report.get('log_path')}",
        f"  exit_code: {report.get('exit_code')}",
        f"  duration_ms: {report.get('duration_ms')}",
    ]
    if "preset_found" in report:
        if report.get("preset_found"):
            preset_state = report.get("preset_state", {}) if isinstance(report.get("preset_state"), dict) else {}
            lines.append(
                "  preset: found"
                f" platform={preset_state.get('platform', '')}"
                f" configured_path={preset_state.get('export_path', '')}"
            )
        else:
            lines.append("  preset: missing in export_presets.cfg")
    if "output_changed" in report:
        lines.append(f"  output_changed: {report.get('output_changed')}")
    if report.get("output_matches_preset") is not None:
        lines.append(f"  output_matches_preset: {report.get('output_matches_preset')}")
    if report.get("output_exists"):
        lines.append(f"  bytes: {report.get('output_bytes')}")
    for diagnostic in report.get("diagnostics", [])[:8]:
        location = ""
        if diagnostic.get("path"):
            line = diagnostic.get("line")
            location = f" ({diagnostic.get('path')}:{line})" if line is not None else f" ({diagnostic.get('path')})"
        lines.append(f"  {diagnostic.get('kind')}: {diagnostic.get('message')}{location}")
        if diagnostic.get("hint"):
            lines.append(f"    hint: {diagnostic.get('hint')}")
    if not report.get("diagnostics") and not report.get("output_exists") and report.get("stdout_tail"):
        lines.append("  tail:")
        for line in report.get("stdout_tail", [])[-8:]:
            lines.append(f"    {line}")
    return "\n".join(lines)


def _format_script_check_report(report: dict[str, Any]) -> str:
    status = "PASS" if report.get("ok") else "FAIL"
    lines = [
        f"{status} script {report.get('script')}",
        f"  log: {report.get('log_path')}",
        f"  exit_code: {report.get('exit_code')}",
        f"  duration_ms: {report.get('duration_ms')}",
    ]
    for diagnostic in report.get("diagnostics", [])[:8]:
        location = ""
        if diagnostic.get("path"):
            location = f" ({diagnostic.get('path')}:{diagnostic.get('line', '')})"
        lines.append(f"  {diagnostic.get('kind')}: {diagnostic.get('message')}{location}")
        if diagnostic.get("hint"):
            lines.append(f"    hint: {diagnostic.get('hint')}")
    if not report.get("diagnostics") and report.get("stdout_tail") and not report.get("ok"):
        lines.append("  tail:")
        for line in report.get("stdout_tail", [])[-8:]:
            lines.append(f"    {line}")
    return "\n".join(lines)


def _format_probe_report(report: dict[str, Any]) -> str:
    status = "PASS" if report.get("ok") else "FAIL"
    summary = report.get("log_summary", {})
    diagnostics = summary.get("diagnostics", []) if isinstance(summary, dict) else []
    lines = [
        f"{status} probe {report.get('scene') or '<main>'}",
        f"  log: {report.get('log_path')}",
        f"  exit_code: {report.get('exit_code')}",
        f"  errors: {summary.get('error_count', 0) if isinstance(summary, dict) else 0}",
        f"  warnings: {summary.get('warning_count', 0) if isinstance(summary, dict) else 0}",
        f"  duration_ms: {report.get('duration_ms')}",
    ]
    for diagnostic in diagnostics[:10]:
        location = ""
        if diagnostic.get("path"):
            location = f" ({diagnostic.get('path')}:{diagnostic.get('line', '')})"
        lines.append(f"  {diagnostic.get('kind')}: {diagnostic.get('message')}{location}")
    return "\n".join(lines)


def _format_scene_probe_report(report: dict[str, Any]) -> str:
    status = "PASS" if report.get("ok") else "FAIL"
    lines = [
        f"{status} scene probes {report.get('passed')}/{report.get('scene_count')} passed",
        f"  failed: {report.get('failed')}",
        f"  duration_ms: {report.get('duration_ms')}",
        f"  artifacts: {report.get('artifacts_dir')}",
    ]
    for scene in report.get("scenes", []):
        scene_summary = scene.get("log_summary", {}) if isinstance(scene, dict) else {}
        scene_status = "PASS" if scene.get("ok") else "FAIL"
        lines.append(
            f"  {scene_status} {scene.get('scene')}: "
            f"errors={scene_summary.get('error_count', 0) if isinstance(scene_summary, dict) else 0} "
            f"warnings={scene_summary.get('warning_count', 0) if isinstance(scene_summary, dict) else 0} "
            f"log={scene.get('log_path')}"
        )
    for diagnostic in report.get("diagnostics", [])[:12]:
        location = ""
        if diagnostic.get("path"):
            location = f" ({diagnostic.get('path')}:{diagnostic.get('line', '')})"
        lines.append(
            f"  {diagnostic.get('scene')}: {diagnostic.get('kind')}: {diagnostic.get('message')}{location}"
        )
    return "\n".join(lines)


def _format_project_script_check_report(report: dict[str, Any]) -> str:
    status = "PASS" if report.get("ok") else "FAIL"
    lines = [
        f"{status} scripts {report.get('passed')}/{report.get('script_count')} passed",
        f"  failed: {report.get('failed')}",
        f"  duration_ms: {report.get('duration_ms')}",
    ]
    for diagnostic in report.get("diagnostics", [])[:12]:
        location = ""
        if diagnostic.get("path"):
            location = f" ({diagnostic.get('path')}:{diagnostic.get('line', '')})"
        lines.append(
            f"  {diagnostic.get('script')}: {diagnostic.get('kind')}: {diagnostic.get('message')}{location}"
        )
        if diagnostic.get("hint"):
            lines.append(f"    hint: {diagnostic.get('hint')}")
    return "\n".join(lines)


def _format_project_resource_check_report(report: dict[str, Any]) -> str:
    status = "PASS" if report.get("ok") else "FAIL"
    lines = [
        f"{status} resources {report.get('passed')}/{report.get('resource_count')} passed",
        f"  failed: {report.get('failed')}",
        f"  duration_ms: {report.get('duration_ms')}",
    ]
    for diagnostic in report.get("diagnostics", [])[:12]:
        location = ""
        if diagnostic.get("path"):
            location = f" ({diagnostic.get('path')}:{diagnostic.get('line', '')})"
        lines.append(
            f"  {diagnostic.get('resource')}: {diagnostic.get('kind')}: {diagnostic.get('message')}{location}"
        )
    return "\n".join(lines)


def _format_scene_inspect_report(report: dict[str, Any]) -> str:
    status = "PASS" if report.get("ok") else "FAIL"
    root = report.get("root") if isinstance(report.get("root"), dict) else {}
    lines = [
        f"{status} scene {report.get('scene')}",
        f"  root: {root.get('name', '<none>')} ({root.get('class', '')})",
        f"  nodes: {report.get('node_count')}",
        f"  ext_resources: {report.get('ext_resource_count')}",
        f"  sub_resources: {report.get('sub_resource_count')}",
        f"  connections: {report.get('connection_count')}",
        f"  duration_ms: {report.get('duration_ms')}",
    ]
    for node in report.get("nodes", [])[:24]:
        class_name = node.get("class") or node.get("type") or ""
        lines.append(
            f"  node {node.get('path')}: {class_name} "
            f"properties={node.get('property_count', 0)}"
        )
    if len(report.get("nodes", [])) > 24:
        lines.append(f"  ... {len(report.get('nodes', [])) - 24} more nodes")
    for diagnostic in report.get("diagnostics", [])[:8]:
        location = ""
        if diagnostic.get("line") is not None:
            location = f":{diagnostic.get('line')}"
        lines.append(f"  {diagnostic.get('kind')}: {diagnostic.get('message')}{location}")
    return "\n".join(lines)


def _format_project_inventory_report(report: dict[str, Any]) -> str:
    status = "PASS" if report.get("ok") else "FAIL"
    files = report.get("files", {}) if isinstance(report.get("files"), dict) else {}
    main_scene = report.get("main_scene", {}) if isinstance(report.get("main_scene"), dict) else {}
    export_presets = report.get("export_presets", {}) if isinstance(report.get("export_presets"), dict) else {}
    lines = [
        f"{status} project {report.get('project')}",
        f"  name: {report.get('name') or '<unnamed>'}",
        f"  main_scene: {main_scene.get('path', '') or '<none>'} exists={main_scene.get('exists', False)}",
        f"  autoloads: {report.get('autoload_count')}",
        f"  export_presets: {export_presets.get('count', 0)}",
        (
            "  files: "
            f"scenes={files.get('scene_count', 0)} "
            f"scripts={files.get('script_count', 0)} "
            f"resources={files.get('resource_count', 0)} "
            f"assets={files.get('asset_count', 0)} "
            f"bytes={files.get('total_bytes', 0)}"
        ),
        f"  duration_ms: {report.get('duration_ms')}",
    ]
    extension_counts = files.get("extension_counts", {}) if isinstance(files.get("extension_counts"), dict) else {}
    if extension_counts:
        top_extensions = sorted(extension_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))[:8]
        lines.append(
            "  extensions: "
            + " ".join(f"{extension}={count}" for extension, count in top_extensions)
        )
    scale = files.get("scale", {}) if isinstance(files.get("scale"), dict) else {}
    if scale:
        lines.append(
            "  scale: "
            f"dirs={scale.get('directory_count', 0)} "
            f"max_depth={scale.get('max_path_depth', 0)} "
            f"avg_file_bytes={scale.get('average_file_bytes', 0)} "
            f"largest_file_bytes={scale.get('largest_file_bytes', 0)}"
        )
        top_directories = scale.get("top_directories", [])
        if isinstance(top_directories, list) and top_directories:
            parts = [
                f"{entry.get('path')}={entry.get('count')} files/{entry.get('bytes')} bytes"
                for entry in top_directories[:5]
                if isinstance(entry, dict)
            ]
            if parts:
                lines.append("  top_dirs: " + "; ".join(parts))
    for file_entry in files.get("largest_files", [])[:5]:
        lines.append(
            f"  large {file_entry.get('path')}: {file_entry.get('bytes', 0)} bytes"
        )
    for autoload in report.get("autoloads", [])[:12]:
        lines.append(
            f"  autoload {autoload.get('name')}: {autoload.get('path')} "
            f"singleton={autoload.get('singleton')} exists={autoload.get('exists')}"
        )
    for preset in export_presets.get("presets", [])[:12]:
        lines.append(
            f"  export {preset.get('index')}: {preset.get('name')} "
            f"platform={preset.get('platform')} path={preset.get('export_path')}"
        )
    for diagnostic in report.get("diagnostics", [])[:12]:
        lines.append(f"  {diagnostic.get('kind')}: {diagnostic.get('message')}")
    return "\n".join(lines)


def _format_project_node_query_report(report: dict[str, Any]) -> str:
    status = "PASS" if report.get("ok") else "FAIL"
    query = report.get("query", {})
    query_text = json.dumps(query, ensure_ascii=False, sort_keys=True) if query else "{}"
    lines = [
        f"{status} node query {report.get('match_count')}/{report.get('node_count')} nodes matched",
        f"  scenes: {report.get('scene_count')}",
        f"  query: {query_text}",
        f"  duration_ms: {report.get('duration_ms')}",
    ]
    for node in report.get("matches", [])[:24]:
        if not isinstance(node, dict):
            continue
        class_name = node.get("class") or node.get("type") or ""
        test_id = node.get("test_id") or ""
        names = node.get("accessible_names", [])
        accessible = ""
        if isinstance(names, list) and names:
            accessible = f" name={names[0]!r}"
        test_id_text = f" test_id={test_id}" if test_id else ""
        lines.append(
            f"  {node.get('scene')} {node.get('path')}: "
            f"{class_name} role={node.get('role')}{test_id_text}{accessible}"
        )
    if len(report.get("matches", [])) > 24:
        lines.append(f"  ... {len(report.get('matches', [])) - 24} more matches")
    for diagnostic in report.get("diagnostics", [])[:12]:
        lines.append(
            f"  {diagnostic.get('scene', diagnostic.get('path', ''))}: "
            f"{diagnostic.get('kind')}: {diagnostic.get('message')}"
        )
    return "\n".join(lines)


def _format_project_validation_report(report: dict[str, Any]) -> str:
    status = "PASS" if report.get("ok") else "FAIL"
    lines = [
        f"{status} validation {report.get('passed')}/{report.get('check_count')} checks passed",
        f"  failed: {report.get('failed')}",
        f"  duration_ms: {report.get('duration_ms')}",
        f"  artifacts: {report.get('artifacts_dir')}",
    ]
    scale = report.get("scale", {}) if isinstance(report.get("scale"), dict) else {}
    if scale:
        lines.append(
            "  scale: "
            f"files={scale.get('file_count', 0)} "
            f"dirs={scale.get('directory_count', 0)} "
            f"bytes={scale.get('total_bytes', 0)} "
            f"max_depth={scale.get('max_path_depth', 0)}"
        )
        top_extensions = scale.get("top_extensions", [])
        if isinstance(top_extensions, list) and top_extensions:
            parts = [
                f"{entry.get('extension')}={entry.get('count')}"
                for entry in top_extensions[:6]
                if isinstance(entry, dict)
            ]
            if parts:
                lines.append("  scale_extensions: " + " ".join(parts))
    checks = report.get("checks", {})
    if isinstance(checks, dict):
        for name, check_report in checks.items():
            if not isinstance(check_report, dict):
                continue
            check_status = "PASS" if check_report.get("ok") else "FAIL"
            summary = _validation_check_summary(name, check_report)
            lines.append(f"  {check_status} {name}: {summary}")
    for diagnostic in report.get("diagnostics", [])[:16]:
        location = ""
        if diagnostic.get("path"):
            line = diagnostic.get("line")
            location = f" ({diagnostic.get('path')}:{line})" if line is not None else f" ({diagnostic.get('path')})"
        elif diagnostic.get("scene"):
            location = f" ({diagnostic.get('scene')})"
        elif diagnostic.get("script"):
            location = f" ({diagnostic.get('script')})"
        elif diagnostic.get("resource"):
            location = f" ({diagnostic.get('resource')})"
        lines.append(
            f"  {diagnostic.get('check')}: {diagnostic.get('kind')}: {diagnostic.get('message')}{location}"
        )
    return "\n".join(lines)


def _validation_check_summary(name: str, report: dict[str, Any]) -> str:
    if name == "inventory":
        files = report.get("files", {}) if isinstance(report.get("files"), dict) else {}
        scale = files.get("scale", {}) if isinstance(files.get("scale"), dict) else {}
        scale_text = ""
        if scale:
            scale_text = (
                f", {scale.get('directory_count', 0)} dirs, "
                f"depth {scale.get('max_path_depth', 0)}"
            )
        return (
            f"{files.get('count', 0)} files, "
            f"{files.get('total_bytes', 0)} bytes, "
            f"{report.get('autoload_count', 0)} autoloads, "
            f"{report.get('export_presets', {}).get('count', 0) if isinstance(report.get('export_presets'), dict) else 0} export presets"
            f"{scale_text}"
        )
    if name == "scripts":
        return f"{report.get('passed')}/{report.get('script_count')} scripts passed"
    if name == "resources":
        return f"{report.get('passed')}/{report.get('resource_count')} resources passed"
    if name == "scene_inspect":
        return f"{report.get('passed')}/{report.get('scene_count')} scenes inspected"
    if name == "runtime":
        return f"{report.get('passed')}/{report.get('scene_count')} scenes probed"
    return f"ok={report.get('ok')}"


if __name__ == "__main__":
    raise SystemExit(main())
