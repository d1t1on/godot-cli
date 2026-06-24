from __future__ import annotations

import json
import shutil
import tempfile
import textwrap
import time
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from godot_playwright.cli import main as cli_main
from godot_playwright.runner import TestRunnerError, discover_tests, expect_poll, format_report, run_tests, select_tests
from godot_playwright.project import init_project


class _UnitFakeGodot:
    launches = 0

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        type(self).launches += 1

    def __enter__(self):  # type: ignore[no-untyped-def]
        return _UnitFakeGodotClient()

    def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
        return None


class _UnitFakeGodotClient:
    def rpc(self, method, params=None):  # type: ignore[no-untyped-def]
        return {"method": method}

    def current_scene(self):  # type: ignore[no-untyped-def]
        return {"path": "res://scenes/main.tscn"}

    def log_events(self, *, severity=None):  # type: ignore[no-untyped-def]
        return []

    def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
        return {"name": "Main", "class": "Control", "path": "/root/Main", "child_count": 0, "children": []}


class RunnerUnitTests(unittest.TestCase):
    def test_discover_tests_finds_functions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tests_dir = Path(tmp) / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                "def test_one():\n    pass\n\ndef helper():\n    pass\n",
                encoding="utf-8",
            )
            discovered = discover_tests([tests_dir])
            self.assertEqual([test.name for test in discovered], ["test_one"])

    def test_select_tests_supports_grep_invert_and_shard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tests_dir = Path(tmp) / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                textwrap.dedent(
                    """\
                    def test_alpha():
                        pass

                    def test_beta():
                        pass

                    def test_gamma():
                        pass
                    """
                ),
                encoding="utf-8",
            )
            discovered = discover_tests([tests_dir])

            selected, selection = select_tests(discovered, grep="alpha|gamma")
            self.assertEqual([test.name for test in selected], ["test_alpha", "test_gamma"])
            self.assertEqual(selection["after_grep"], 2)

            inverted, inverted_selection = select_tests(discovered, grep="alpha|gamma", grep_invert=True)
            self.assertEqual([test.name for test in inverted], ["test_beta"])
            self.assertEqual(inverted_selection["after_grep"], 1)

            shard, shard_selection = select_tests(discovered, shard="2/2")
            self.assertEqual([test.name for test in shard], ["test_beta"])
            self.assertEqual(shard_selection["shard"]["current"], 2)
            self.assertEqual(shard_selection["shard"]["total"], 2)

            with self.assertRaises(TestRunnerError):
                select_tests(discovered, shard="4/3")

    def test_run_tests_can_list_selected_tests_without_godot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                textwrap.dedent(
                    """\
                    def test_alpha():
                        pass

                    def test_beta():
                        pass
                    """
                ),
                encoding="utf-8",
            )
            artifacts = root / "artifacts"

            report = run_tests(
                root / "project",
                [tests_dir],
                artifacts_dir=artifacts,
                grep="beta",
                list_only=True,
            )

            self.assertTrue(report["list_only"])
            self.assertEqual(report["discovered"], 2)
            self.assertEqual(report["total"], 1)
            self.assertEqual(report["tests"][0]["status"], "listed")
            self.assertEqual(report["tests"][0]["name"], "test_beta")
            self.assertTrue((artifacts / "results.json").exists())
            self.assertTrue((artifacts / "report.html").exists())
            self.assertIn("LIST 1 selected / 2 discovered", format_report(report))

    def test_run_tests_respects_skip_without_godot(self) -> None:
        class FailIfLaunchedGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                raise AssertionError("Godot should not launch for skipped tests")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_skip.py").write_text(
                textwrap.dedent(
                    """\
                    from godot_playwright import skip

                    @skip("waiting on generated fixture")
                    def test_skipped_case():
                        raise AssertionError("should not run")
                    """
                ),
                encoding="utf-8",
            )
            artifacts = root / "artifacts"

            with mock.patch("godot_playwright.runner.Godot", FailIfLaunchedGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=artifacts, trace="off")

            self.assertEqual(report["passed"], 0)
            self.assertEqual(report["failed"], 0)
            self.assertEqual(report["skipped"], 1)
            result = report["tests"][0]
            self.assertEqual(result["status"], "skipped")
            self.assertEqual(result["outcome"], "skipped")
            self.assertEqual(result["annotation_reason"], "waiting on generated fixture")
            self.assertEqual(result["annotations"], [{"type": "skip", "reason": "waiting on generated fixture"}])
            self.assertIn("SKIP", format_report(report))
            self.assertIn("waiting on generated fixture", Path(report["report_html"]).read_text(encoding="utf-8"))

    def test_run_tests_marks_expected_failure_as_green(self) -> None:
        class FakeGodot:
            launches = 0

            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                FakeGodot.launches += 1

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            def rpc(self, method, params=None):  # type: ignore[no-untyped-def]
                return {"method": method}

            def current_scene(self):  # type: ignore[no-untyped-def]
                return {"path": "res://scenes/main.tscn"}

            def log_events(self, *, severity=None):  # type: ignore[no-untyped-def]
                return []

            def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
                return {"name": "Main", "class": "Control", "path": "/root/Main", "child_count": 0, "children": []}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_expected_failure.py").write_text(
                textwrap.dedent(
                    """\
                    from godot_playwright import expected_failure

                    @expected_failure("known editor bug")
                    def test_known_failure():
                        raise AssertionError("still broken")
                    """
                ),
                encoding="utf-8",
            )
            artifacts = root / "artifacts"

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=artifacts, trace="off", retries=2)

            self.assertEqual(FakeGodot.launches, 1)
            self.assertEqual(report["passed"], 1)
            self.assertEqual(report["failed"], 0)
            self.assertEqual(report["expected_failed"], 1)
            self.assertEqual(report["unexpected_passed"], 0)
            result = report["tests"][0]
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["outcome"], "expected_failed")
            self.assertTrue(result["expected_failure"])
            self.assertEqual(result["annotation_reason"], "known editor bug")
            self.assertEqual(result["error"]["type"], "AssertionError")
            self.assertTrue(Path(result["artifacts"]["failure_scene"]).exists())
            self.assertTrue(Path(result["artifacts"]["diagnostics"]).exists())
            self.assertIn("EXPECTED-FAIL", format_report(report))

    def test_run_tests_fails_unexpected_pass(self) -> None:
        class FakeGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                pass

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            pass

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_unexpected_pass.py").write_text(
                textwrap.dedent(
                    """\
                    from godot_playwright import expected_failure

                    @expected_failure("known editor bug")
                    def test_unexpected_pass():
                        pass
                    """
                ),
                encoding="utf-8",
            )
            artifacts = root / "artifacts"

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=artifacts, trace="off")

            self.assertEqual(report["passed"], 0)
            self.assertEqual(report["failed"], 1)
            self.assertEqual(report["expected_failed"], 0)
            self.assertEqual(report["unexpected_passed"], 1)
            result = report["tests"][0]
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["outcome"], "unexpected_passed")
            self.assertEqual(result["annotation_reason"], "known editor bug")
            self.assertEqual(result["error"]["type"], "UnexpectedPassError")
            self.assertIn("Expected failure passed unexpectedly", result["error"]["message"])
            self.assertIn("UNEXPECTED-PASS", format_report(report))

    def test_run_tests_retries_failed_test_and_marks_flaky(self) -> None:
        class FakeGodot:
            launches = 0

            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                FakeGodot.launches += 1

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            def rpc(self, method, params=None):  # type: ignore[no-untyped-def]
                return {"method": method}

            def current_scene(self):  # type: ignore[no-untyped-def]
                return {"path": "res://scenes/main.tscn"}

            def log_events(self, *, severity=None):  # type: ignore[no-untyped-def]
                return []

            def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
                return {"name": "Main", "class": "Control", "path": "/root/Main", "child_count": 0, "children": []}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_flaky.py").write_text(
                textwrap.dedent(
                    """\
                    attempts = {"count": 0}

                    def test_flaky_once():
                        attempts["count"] += 1
                        if attempts["count"] == 1:
                            raise AssertionError("first attempt failed")
                    """
                ),
                encoding="utf-8",
            )
            artifacts = root / "artifacts"

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(
                    root / "project",
                    [tests_dir],
                    artifacts_dir=artifacts,
                    trace="off",
                    retries=1,
                )

            self.assertEqual(FakeGodot.launches, 2)
            self.assertEqual(report["passed"], 1)
            self.assertEqual(report["failed"], 0)
            self.assertEqual(report["flaky"], 1)
            result = report["tests"][0]
            self.assertTrue(result["flaky"])
            self.assertEqual(result["outcome"], "flaky")
            self.assertEqual(result["attempt_count"], 2)
            self.assertEqual(result["retry_count"], 1)
            self.assertEqual([attempt["status"] for attempt in result["attempts"]], ["failed", "passed"])
            self.assertTrue(Path(result["attempts"][0]["artifacts"]["failure_scene"]).exists())
            self.assertTrue(Path(result["attempts"][0]["artifacts"]["diagnostics"]).exists())
            self.assertIn("FLAKY", format_report(report))

    def test_run_tests_fails_timed_out_test_with_diagnostics(self) -> None:
        class FakeGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                pass

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            def rpc(self, method, params=None):  # type: ignore[no-untyped-def]
                return {"method": method}

            def current_scene(self):  # type: ignore[no-untyped-def]
                return {"path": "res://scenes/main.tscn"}

            def log_events(self, *, severity=None):  # type: ignore[no-untyped-def]
                return []

            def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
                return {"name": "Main", "class": "Control", "path": "/root/Main", "child_count": 0, "children": []}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_timeout.py").write_text(
                textwrap.dedent(
                    """\
                    import time

                    def test_timeout():
                        time.sleep(1)
                    """
                ),
                encoding="utf-8",
            )
            artifacts = root / "artifacts"
            started = time.monotonic()

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(
                    root / "project",
                    [tests_dir],
                    artifacts_dir=artifacts,
                    trace="off",
                    test_timeout=0.05,
                )

            self.assertLess(time.monotonic() - started, 0.5)
            self.assertEqual(report["passed"], 0)
            self.assertEqual(report["failed"], 1)
            self.assertEqual(report["test_timeout"], 0.05)
            result = report["tests"][0]
            self.assertEqual(result["error"]["type"], "TestTimeoutError")
            self.assertIn("Timed out after 0.05 seconds", result["error"]["message"])
            self.assertTrue(Path(result["artifacts"]["failure_scene"]).exists())
            self.assertTrue(Path(result["artifacts"]["diagnostics"]).exists())

    def test_run_tests_records_structured_steps(self) -> None:
        class FakeGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                pass

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            pass

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_steps.py").write_text(
                textwrap.dedent(
                    """\
                    def test_steps(step):
                        with step("arrange scene"):
                            pass
                        with step("interact"):
                            with step("click button"):
                                pass
                        step("assert result", lambda: None)
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off")

            self.assertEqual(report["passed"], 1)
            result = report["tests"][0]
            self.assertEqual([step["title"] for step in result["steps"]], ["arrange scene", "interact", "click button", "assert result"])
            self.assertEqual([step["status"] for step in result["steps"]], ["passed", "passed", "passed", "passed"])
            self.assertEqual([step["depth"] for step in result["steps"]], [0, 0, 1, 0])
            self.assertIn("STEP arrange scene", format_report(report))
            self.assertIn("STEP click button", format_report(report))
            self.assertIn("Steps", Path(report["report_html"]).read_text(encoding="utf-8"))

    def test_run_tests_records_failed_step_in_diagnostics(self) -> None:
        class FakeGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                pass

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            def rpc(self, method, params=None):  # type: ignore[no-untyped-def]
                return {"method": method}

            def current_scene(self):  # type: ignore[no-untyped-def]
                return {"path": "res://scenes/main.tscn"}

            def log_events(self, *, severity=None):  # type: ignore[no-untyped-def]
                return []

            def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
                return {"name": "Main", "class": "Control", "path": "/root/Main", "child_count": 0, "children": []}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_failed_step.py").write_text(
                textwrap.dedent(
                    """\
                    def test_failed_step(step):
                        with step("explode"):
                            raise AssertionError("boom")
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off")

            self.assertEqual(report["failed"], 1)
            result = report["tests"][0]
            self.assertEqual(result["steps"][0]["title"], "explode")
            self.assertEqual(result["steps"][0]["status"], "failed")
            self.assertEqual(result["steps"][0]["error"]["type"], "AssertionError")
            self.assertIn("boom", result["steps"][0]["error"]["message"])
            self.assertIn("STEP-FAIL explode", format_report(report))
            diagnostics = json.loads(Path(result["artifacts"]["diagnostics"]).read_text(encoding="utf-8"))
            self.assertEqual(diagnostics["steps"][0]["title"], "explode")
            self.assertEqual(diagnostics["steps"][0]["status"], "failed")

    def test_run_tests_records_soft_expect_failures_after_test_finishes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_soft_expect.py").write_text(
                textwrap.dedent(
                    """\
                    class FakeLocator:
                        selector = "#Title"

                        def wait_for_property(self, property_name, expected, timeout=5.0):
                            raise AssertionError(f"Expected {property_name} to be {expected!r}")


                    def test_soft_expect_continues(soft_expect, attach):
                        soft_expect(FakeLocator()).to_have_text("Ready", timeout=0.01)
                        attach("after-soft", body="continued")
                    """
                ),
                encoding="utf-8",
            )
            artifacts = root / "artifacts"
            junit_path = artifacts / "junit.xml"

            with mock.patch("godot_playwright.runner.Godot", _UnitFakeGodot):
                report = run_tests(
                    root / "project",
                    [tests_dir],
                    artifacts_dir=artifacts,
                    trace="off",
                    junit_xml=junit_path,
                )

            self.assertEqual(report["passed"], 0)
            self.assertEqual(report["failed"], 1)
            self.assertEqual(report["soft_assertion_failures"], 1)
            result = report["tests"][0]
            self.assertEqual(result["error"]["type"], "SoftAssertionError")
            self.assertEqual(result["attachments"][0]["name"], "after-soft")
            self.assertEqual(len(result["soft_assertions"]), 1)
            self.assertEqual(result["soft_assertions"][0]["method"], "to_have_text")
            self.assertIn("Expected text to be 'Ready'", result["soft_assertions"][0]["message"])
            self.assertIn("soft assertion 1", format_report(report))
            html = Path(report["report_html"]).read_text(encoding="utf-8")
            self.assertIn("Soft Assertions", html)
            diagnostics = json.loads(Path(result["artifacts"]["diagnostics"]).read_text(encoding="utf-8"))
            self.assertEqual(diagnostics["summary"]["soft_assertion_failures"], 1)
            self.assertEqual(diagnostics["soft_assertions"][0]["method"], "to_have_text")

            properties = {
                prop.get("name"): prop.get("value")
                for prop in ET.parse(junit_path).getroot().findall(".//testcase/properties/property")
            }
            self.assertEqual(properties["soft_assertion_failures"], "1")
            self.assertIn("to_have_text", properties["soft_assertion.1"])

    def test_run_tests_keeps_hard_failure_primary_when_soft_expect_failed_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_soft_then_hard.py").write_text(
                textwrap.dedent(
                    """\
                    class FakeLocator:
                        selector = "#Status"

                        def wait_for_property(self, property_name, expected, timeout=5.0):
                            raise AssertionError("soft mismatch")


                    def test_soft_then_hard(soft_expect):
                        soft_expect(FakeLocator()).to_have_text("Ready", timeout=0.01)
                        raise AssertionError("hard stop")
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", _UnitFakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off")

            result = report["tests"][0]
            self.assertEqual(report["failed"], 1)
            self.assertEqual(result["error"]["type"], "AssertionError")
            self.assertEqual(result["error"]["message"], "hard stop")
            self.assertEqual(len(result["soft_assertions"]), 1)
            self.assertEqual(result["diagnostics"]["soft_assertion_failures"], 1)

    def test_run_tests_runtime_skip_after_soft_expect_remains_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_soft_skip.py").write_text(
                textwrap.dedent(
                    """\
                    class FakeLocator:
                        selector = "#Optional"

                        def wait_for_property(self, property_name, expected, timeout=5.0):
                            raise AssertionError("optional UI missing")


                    def test_soft_then_skip(soft_expect, test_info):
                        soft_expect(FakeLocator()).to_have_text("Ready", timeout=0.01)
                        test_info.skip("runtime feature not available")
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", _UnitFakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off")

            self.assertEqual(report["passed"], 0)
            self.assertEqual(report["failed"], 0)
            self.assertEqual(report["skipped"], 1)
            result = report["tests"][0]
            self.assertEqual(result["status"], "skipped")
            self.assertEqual(result["annotation_reason"], "runtime feature not available")
            self.assertIsNone(result["error"])
            self.assertEqual(len(result["soft_assertions"]), 1)

    def test_run_tests_provides_expect_poll_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_expect_poll.py").write_text(
                textwrap.dedent(
                    """\
                    def test_expect_poll(expect_poll):
                        state = {"count": 0}

                        def read_count():
                            state["count"] += 1
                            return state["count"]

                        assert expect_poll(read_count, description="counter").to_equal(3, timeout=1, interval=0.001) == 3
                        assert expect_poll(lambda: "ready").not_to_equal("loading", timeout=0) == "ready"
                        assert expect_poll(lambda: True).to_be_truthy(timeout=0) is True
                        assert expect_poll(lambda: False).to_be_falsy(timeout=0) is False
                        assert expect_poll(lambda: "Potion").to_satisfy(
                            lambda value: value.startswith("Pot"),
                            "to start with Pot",
                            timeout=0,
                        ) == "Potion"
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", _UnitFakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off")

            self.assertEqual(report["passed"], 1)
            self.assertEqual(report["failed"], 0)

    def test_run_tests_expect_poll_failure_reports_last_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_expect_poll_failure.py").write_text(
                textwrap.dedent(
                    """\
                    def test_expect_poll_failure(expect_poll):
                        def read_status():
                            raise RuntimeError("rpc not ready")

                        expect_poll(read_status, description="status").to_equal("ready", timeout=0.01, interval=0.001)
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", _UnitFakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off")

            self.assertEqual(report["failed"], 1)
            result = report["tests"][0]
            self.assertEqual(result["error"]["type"], "AssertionError")
            self.assertIn("Expected poll 'status' to equal 'ready'", result["error"]["message"])
            self.assertIn("last error was RuntimeError: rpc not ready", result["error"]["message"])
            self.assertTrue(Path(result["artifacts"]["diagnostics"]).exists())

    def test_expect_poll_validates_arguments(self) -> None:
        with self.assertRaises(TestRunnerError):
            expect_poll("not callable")  # type: ignore[arg-type]
        with self.assertRaises(TestRunnerError):
            expect_poll(lambda: True).to_be_truthy(timeout=-1)
        with self.assertRaises(TestRunnerError):
            expect_poll(lambda: True).to_be_truthy(interval=0)
        with self.assertRaises(TestRunnerError):
            expect_poll(lambda: True).to_satisfy("not callable")  # type: ignore[arg-type]

    def test_run_tests_records_test_info_attachments(self) -> None:
        class FakeGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                pass

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            pass

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_attachments.py").write_text(
                textwrap.dedent(
                    """\
                    def test_attachments(test_info, attach):
                        state_path = test_info.output_path("state.json")
                        state_path.write_text('{"ok": true}', encoding="utf-8")
                        test_info.attach("state", path=state_path, content_type="application/json")
                        attach("note", body="hello")
                        attach("payload", body={"ok": True})
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off")

            self.assertEqual(report["passed"], 1)
            result = report["tests"][0]
            self.assertEqual([attachment["name"] for attachment in result["attachments"]], ["state", "note", "payload"])
            self.assertEqual(result["attachments"][0]["content_type"], "application/json")
            self.assertEqual(result["attachments"][1]["content_type"], "text/plain")
            self.assertEqual(result["attachments"][2]["content_type"], "application/json")
            for attachment in result["attachments"]:
                self.assertTrue(Path(attachment["path"]).exists())
            self.assertEqual(json.loads(Path(result["attachments"][2]["path"]).read_text(encoding="utf-8")), {"ok": True})
            self.assertIn("attachment state:", format_report(report))
            html = Path(report["report_html"]).read_text(encoding="utf-8")
            self.assertIn("Attachments", html)
            self.assertIn("payload", html)

    def test_run_tests_preserves_attachments_in_diagnostics(self) -> None:
        class FakeGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                pass

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            def rpc(self, method, params=None):  # type: ignore[no-untyped-def]
                return {"method": method}

            def current_scene(self):  # type: ignore[no-untyped-def]
                return {"path": "res://scenes/main.tscn"}

            def log_events(self, *, severity=None):  # type: ignore[no-untyped-def]
                return []

            def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
                return {"name": "Main", "class": "Control", "path": "/root/Main", "child_count": 0, "children": []}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_failed_attachment.py").write_text(
                textwrap.dedent(
                    """\
                    def test_failed_attachment(attach):
                        attach("debug-state", body={"before": "failure"})
                        raise AssertionError("boom")
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off")

            result = report["tests"][0]
            self.assertEqual(report["failed"], 1)
            self.assertEqual(result["attachments"][0]["name"], "debug-state")
            diagnostics = json.loads(Path(result["artifacts"]["diagnostics"]).read_text(encoding="utf-8"))
            self.assertEqual(diagnostics["attachments"][0]["name"], "debug-state")
            self.assertTrue(Path(diagnostics["attachments"][0]["path"]).exists())

    def test_run_tests_captures_python_stdout_and_stderr(self) -> None:
        class FakeGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                pass

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            pass

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_output.py").write_text(
                textwrap.dedent(
                    """\
                    import sys
                    from godot_playwright import after_each, before_each

                    @before_each
                    def prepare():
                        print("setup stdout")

                    @after_each
                    def cleanup():
                        print("cleanup stderr", file=sys.stderr)

                    def test_output():
                        print("body stdout")
                        print("body stderr", file=sys.stderr)
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off")

            self.assertEqual(report["passed"], 1)
            result = report["tests"][0]
            self.assertEqual(result["output"]["stdout"]["line_count"], 2)
            self.assertEqual(result["output"]["stderr"]["line_count"], 2)
            stdout_path = Path(result["output"]["stdout"]["path"])
            stderr_path = Path(result["output"]["stderr"]["path"])
            self.assertTrue(stdout_path.exists())
            self.assertTrue(stderr_path.exists())
            self.assertIn("setup stdout", stdout_path.read_text(encoding="utf-8"))
            self.assertIn("body stderr", stderr_path.read_text(encoding="utf-8"))
            self.assertEqual(result["artifacts"]["python_stdout"], str(stdout_path))
            self.assertEqual(result["artifacts"]["python_stderr"], str(stderr_path))
            report_text = format_report(report)
            self.assertIn("stdout:", report_text)
            self.assertIn("stderr:", report_text)
            html = Path(report["report_html"]).read_text(encoding="utf-8")
            self.assertIn("Python stdout", html)
            self.assertIn("body stdout", html)
            self.assertIn("Python stderr", html)
            self.assertIn("cleanup stderr", html)

    def test_python_output_is_preserved_in_failed_diagnostics(self) -> None:
        class FakeGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                pass

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            def rpc(self, method, params=None):  # type: ignore[no-untyped-def]
                return {"method": method}

            def current_scene(self):  # type: ignore[no-untyped-def]
                return {"path": "res://scenes/main.tscn"}

            def log_events(self, *, severity=None):  # type: ignore[no-untyped-def]
                return []

            def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
                return {"name": "Main", "class": "Control", "path": "/root/Main", "child_count": 0, "children": []}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_failed_output.py").write_text(
                textwrap.dedent(
                    """\
                    import sys

                    def test_failed_output():
                        print("debug before failure")
                        print("stderr before failure", file=sys.stderr)
                        raise AssertionError("boom")
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off")

            result = report["tests"][0]
            self.assertEqual(report["failed"], 1)
            diagnostics = json.loads(Path(result["artifacts"]["diagnostics"]).read_text(encoding="utf-8"))
            self.assertEqual(diagnostics["output"]["stdout"]["tail"], ["debug before failure"])
            self.assertEqual(diagnostics["output"]["stderr"]["tail"], ["stderr before failure"])
            self.assertTrue(Path(diagnostics["artifacts"]["python_stdout"]).exists())
            self.assertTrue(Path(diagnostics["artifacts"]["python_stderr"]).exists())

    def test_run_tests_records_runtime_skip_with_attachments_and_steps(self) -> None:
        class FakeGodot:
            launches = 0

            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                FakeGodot.launches += 1

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            def trace_start(self, **kwargs):  # type: ignore[no-untyped-def]
                return None

            def trace_stop(self):  # type: ignore[no-untyped-def]
                return None

            def trace_events(self, *, clear=True):  # type: ignore[no-untyped-def]
                return [{"type": "runtime.skip.probe", "uptime_ms": 1, "data": {"clear": clear}}]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_runtime_skip.py").write_text(
                textwrap.dedent(
                    """\
                    def test_runtime_skip(test_info, step, attach):
                        attach("note", body="before skip")
                        with step("inspect platform"):
                            test_info.skip("missing Vulkan feature")
                        raise AssertionError("should not run")
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="on")

            self.assertEqual(FakeGodot.launches, 1)
            self.assertEqual(report["passed"], 0)
            self.assertEqual(report["failed"], 0)
            self.assertEqual(report["skipped"], 1)
            result = report["tests"][0]
            self.assertEqual(result["status"], "skipped")
            self.assertEqual(result["outcome"], "skipped")
            self.assertTrue(result["runtime_skip"])
            self.assertEqual(result["annotation_reason"], "missing Vulkan feature")
            self.assertIsNone(result["error"])
            self.assertNotIn("diagnostics", result)
            self.assertEqual(result["steps"][0]["title"], "inspect platform")
            self.assertEqual(result["steps"][0]["status"], "skipped")
            self.assertEqual(result["steps"][0]["error"]["type"], "TestSkipped")
            self.assertEqual(result["attachments"][0]["name"], "note")
            self.assertTrue(Path(result["attachments"][0]["path"]).exists())
            self.assertIn("trace", result["artifacts"])
            self.assertIn("godot_log", result["artifacts"])
            self.assertTrue(Path(result["artifacts"]["trace"]).exists())
            self.assertTrue(Path(result["artifacts"]["godot_log"]).exists())
            self.assertEqual(result["trace_summary"]["event_count"], 1)
            report_text = format_report(report)
            self.assertIn("SKIP", report_text)
            self.assertIn("STEP-SKIP inspect platform", report_text)
            self.assertIn("attachment note:", report_text)
            html = Path(report["report_html"]).read_text(encoding="utf-8")
            self.assertIn("Reason", html)
            self.assertIn("missing Vulkan feature", html)
            self.assertIn("runtime.skip.probe", html)

    def test_runtime_skip_does_not_retry(self) -> None:
        class FakeGodot:
            launches = 0

            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                FakeGodot.launches += 1

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            pass

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_runtime_skip_retry.py").write_text(
                textwrap.dedent(
                    """\
                    def test_runtime_skip_retry(test_info):
                        test_info.skip("not applicable")
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off", retries=2)

            self.assertEqual(FakeGodot.launches, 1)
            result = report["tests"][0]
            self.assertEqual(report["skipped"], 1)
            self.assertEqual(result["attempt_count"], 1)
            self.assertEqual(result["retry_count"], 0)
            self.assertNotIn("attempts", result)

    def test_expected_failure_runtime_skip_counts_skipped(self) -> None:
        class FakeGodot:
            launches = 0

            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                FakeGodot.launches += 1

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            pass

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_expected_runtime_skip.py").write_text(
                textwrap.dedent(
                    """\
                    from godot_playwright import expected_failure

                    @expected_failure("known editor bug")
                    def test_expected_runtime_skip(test_info):
                        test_info.skip("not applicable on this platform")
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off", retries=2)

            self.assertEqual(FakeGodot.launches, 1)
            self.assertEqual(report["passed"], 0)
            self.assertEqual(report["failed"], 0)
            self.assertEqual(report["skipped"], 1)
            self.assertEqual(report["expected_failed"], 0)
            self.assertEqual(report["unexpected_passed"], 0)
            result = report["tests"][0]
            self.assertEqual(result["status"], "skipped")
            self.assertEqual(result["outcome"], "skipped")
            self.assertTrue(result["runtime_skip"])
            self.assertEqual(result["annotation_reason"], "not applicable on this platform")
            self.assertEqual(result["annotations"], [{"type": "expected_failure", "reason": "known editor bug"}])
            self.assertNotIn("expected_failure", result)

    def test_package_exports_runtime_skip_exception(self) -> None:
        from godot_playwright import TestSkipped

        self.assertTrue(issubclass(TestSkipped, Exception))

    def test_run_tests_runs_before_and_after_each_hooks_with_fixtures(self) -> None:
        class FakeGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                pass

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            pass

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_hooks.py").write_text(
                textwrap.dedent(
                    """\
                    from godot_playwright import after_each, before_each

                    @before_each
                    def prepare(test_info, step, attach):
                        with step("prepare scene"):
                            attach("setup", body=test_info.name)

                    @after_each
                    def cleanup(test_info, step, attach):
                        with step("cleanup scene"):
                            attach("cleanup", body=test_info.name)

                    def test_hooked(test_info, attach):
                        attach("body", body="ok")
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off")

            self.assertEqual(report["passed"], 1)
            result = report["tests"][0]
            self.assertEqual([attachment["name"] for attachment in result["attachments"]], ["setup", "body", "cleanup"])
            self.assertEqual([step["title"] for step in result["steps"]], ["prepare scene", "cleanup scene"])
            self.assertEqual([step["status"] for step in result["steps"]], ["passed", "passed"])
            self.assertIn("STEP prepare scene", format_report(report))
            self.assertIn("attachment cleanup:", format_report(report))

    def test_after_each_runs_for_failed_tests_and_keeps_evidence(self) -> None:
        class FakeGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                pass

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            def rpc(self, method, params=None):  # type: ignore[no-untyped-def]
                return {"method": method}

            def current_scene(self):  # type: ignore[no-untyped-def]
                return {"path": "res://scenes/main.tscn"}

            def log_events(self, *, severity=None):  # type: ignore[no-untyped-def]
                return []

            def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
                return {"name": "Main", "class": "Control", "path": "/root/Main", "child_count": 0, "children": []}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_failed_hooked.py").write_text(
                textwrap.dedent(
                    """\
                    from godot_playwright import after_each

                    @after_each
                    def cleanup(step, attach):
                        with step("cleanup failed test"):
                            attach("cleanup", body="cleanup evidence")

                    def test_failure():
                        raise AssertionError("boom")
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off")

            self.assertEqual(report["failed"], 1)
            result = report["tests"][0]
            self.assertEqual(result["error"]["type"], "AssertionError")
            self.assertEqual(result["attachments"][0]["name"], "cleanup")
            self.assertEqual(result["steps"][0]["title"], "cleanup failed test")
            diagnostics = json.loads(Path(result["artifacts"]["diagnostics"]).read_text(encoding="utf-8"))
            self.assertEqual(diagnostics["attachments"][0]["name"], "cleanup")
            self.assertEqual(diagnostics["steps"][0]["title"], "cleanup failed test")

    def test_before_each_runtime_skip_still_runs_after_each(self) -> None:
        class FakeGodot:
            launches = 0

            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                FakeGodot.launches += 1

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            pass

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_hook_skip.py").write_text(
                textwrap.dedent(
                    """\
                    from godot_playwright import after_each, before_each

                    @before_each
                    def prepare(test_info, attach):
                        attach("setup", body="before skip")
                        test_info.skip("fixture not available")

                    @after_each
                    def cleanup(attach):
                        attach("cleanup", body="after skip")

                    def test_not_run(attach):
                        attach("body", body="should not run")
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off", retries=2)

            self.assertEqual(FakeGodot.launches, 1)
            self.assertEqual(report["skipped"], 1)
            result = report["tests"][0]
            self.assertEqual(result["status"], "skipped")
            self.assertTrue(result["runtime_skip"])
            self.assertEqual(result["annotation_reason"], "fixture not available")
            self.assertEqual(result["attempt_count"], 1)
            self.assertEqual([attachment["name"] for attachment in result["attachments"]], ["setup", "cleanup"])
            self.assertNotIn("diagnostics", result)

    def test_after_each_failure_fails_otherwise_passing_test(self) -> None:
        class FakeGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                pass

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            def rpc(self, method, params=None):  # type: ignore[no-untyped-def]
                return {"method": method}

            def current_scene(self):  # type: ignore[no-untyped-def]
                return {"path": "res://scenes/main.tscn"}

            def log_events(self, *, severity=None):  # type: ignore[no-untyped-def]
                return []

            def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
                return {"name": "Main", "class": "Control", "path": "/root/Main", "child_count": 0, "children": []}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_after_failure.py").write_text(
                textwrap.dedent(
                    """\
                    from godot_playwright import after_each

                    @after_each
                    def cleanup():
                        raise AssertionError("cleanup failed")

                    def test_passes():
                        pass
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off")

            self.assertEqual(report["passed"], 0)
            self.assertEqual(report["failed"], 1)
            result = report["tests"][0]
            self.assertEqual(result["error"]["type"], "AssertionError")
            self.assertIn("cleanup failed", result["error"]["message"])
            self.assertTrue(Path(result["artifacts"]["diagnostics"]).exists())

    def test_run_tests_captures_failure_screenshot_when_enabled(self) -> None:
        class FakeGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                pass

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            def rpc(self, method, params=None):  # type: ignore[no-untyped-def]
                return {"method": method}

            def current_scene(self):  # type: ignore[no-untyped-def]
                return {"path": "res://scenes/main.tscn"}

            def log_events(self, *, severity=None):  # type: ignore[no-untyped-def]
                return []

            def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
                return {"name": "Main", "class": "Control", "path": "/root/Main", "child_count": 0, "children": []}

            def screenshot(self, path):  # type: ignore[no-untyped-def]
                Path(path).write_bytes(b"\x89PNG\r\n\x1a\n")
                return {"path": str(path)}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_failure_screenshot.py").write_text(
                textwrap.dedent(
                    """\
                    def test_failure():
                        raise AssertionError("boom")
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(
                    root / "project",
                    [tests_dir],
                    artifacts_dir=root / "artifacts",
                    trace="off",
                    screenshots="only-on-failure",
                )

            self.assertEqual(report["screenshots"], "only-on-failure")
            result = report["tests"][0]
            self.assertEqual(result["status"], "failed")
            self.assertTrue(Path(result["artifacts"]["screenshot"]).exists())
            self.assertIn("screenshot:", format_report(report))
            diagnostics = json.loads(Path(result["artifacts"]["diagnostics"]).read_text(encoding="utf-8"))
            self.assertEqual(diagnostics["artifacts"]["screenshot"], result["artifacts"]["screenshot"])
            html = Path(report["report_html"]).read_text(encoding="utf-8")
            self.assertIn("Screenshot", html)
            self.assertIn("screenshot.png", html)

    def test_screenshot_capture_failure_is_recorded_as_diagnostic_error(self) -> None:
        class FakeGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                pass

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            def rpc(self, method, params=None):  # type: ignore[no-untyped-def]
                return {"method": method}

            def current_scene(self):  # type: ignore[no-untyped-def]
                return {"path": "res://scenes/main.tscn"}

            def log_events(self, *, severity=None):  # type: ignore[no-untyped-def]
                return []

            def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
                return {"name": "Main", "class": "Control", "path": "/root/Main", "child_count": 0, "children": []}

            def screenshot(self, path):  # type: ignore[no-untyped-def]
                raise RuntimeError("headless display")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_screenshot_diagnostic.py").write_text(
                textwrap.dedent(
                    """\
                    def test_failure():
                        raise AssertionError("boom")
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(
                    root / "project",
                    [tests_dir],
                    artifacts_dir=root / "artifacts",
                    trace="off",
                    screenshots="only-on-failure",
                )

            result = report["tests"][0]
            self.assertEqual(result["status"], "failed")
            self.assertNotIn("screenshot", result["artifacts"])
            self.assertEqual(result["diagnostic_errors"][0]["source"], "viewport.screenshot")
            self.assertIn("headless display", result["diagnostic_errors"][0]["message"])
            diagnostics = json.loads(Path(result["artifacts"]["diagnostics"]).read_text(encoding="utf-8"))
            self.assertEqual(diagnostics["diagnostic_errors"][0]["source"], "viewport.screenshot")
            self.assertEqual(diagnostics["summary"]["diagnostic_error_count"], 1)

    def test_screenshots_on_captures_passing_attempts(self) -> None:
        class FakeGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                pass

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            def screenshot(self, path):  # type: ignore[no-untyped-def]
                Path(path).write_bytes(b"\x89PNG\r\n\x1a\n")
                return {"path": str(path)}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_pass_screenshot.py").write_text("def test_pass():\n    pass\n", encoding="utf-8")

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off", screenshots="on")

            result = report["tests"][0]
            self.assertEqual(report["passed"], 1)
            self.assertTrue(Path(result["artifacts"]["screenshot"]).exists())
            self.assertNotIn("diagnostics", result)

    def test_run_tests_stops_after_max_failures_and_marks_remaining_interrupted(self) -> None:
        class FakeGodot:
            launches = 0

            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                FakeGodot.launches += 1

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            def rpc(self, method, params=None):  # type: ignore[no-untyped-def]
                return {"method": method}

            def current_scene(self):  # type: ignore[no-untyped-def]
                return {"path": "res://scenes/main.tscn"}

            def log_events(self, *, severity=None):  # type: ignore[no-untyped-def]
                return []

            def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
                return {"name": "Main", "class": "Control", "path": "/root/Main", "child_count": 0, "children": []}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_max_failures.py").write_text(
                textwrap.dedent(
                    """\
                    def test_a_fails():
                        raise AssertionError("boom")

                    def test_b_interrupted():
                        raise AssertionError("should not run")

                    def test_c_interrupted():
                        raise AssertionError("should not run")
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off", max_failures=1)

            self.assertEqual(FakeGodot.launches, 1)
            self.assertEqual(report["failed"], 1)
            self.assertEqual(report["interrupted"], 2)
            self.assertTrue(report["stopped_early"])
            self.assertEqual(report["max_failures"], 1)
            self.assertEqual([result["status"] for result in report["tests"]], ["failed", "interrupted", "interrupted"])
            self.assertEqual(report["tests"][1]["outcome"], "interrupted")
            self.assertIn("Stopped after 1 failure", report["tests"][1]["annotation_reason"])
            self.assertNotIn("godot_log", report["tests"][1]["artifacts"])
            report_text = format_report(report)
            self.assertIn("INTERRUPTED", report_text)
            self.assertIn("2 interrupted", report_text)
            html = Path(report["report_html"]).read_text(encoding="utf-8")
            self.assertIn("Interrupted", html)

    def test_max_failures_does_not_count_expected_failures(self) -> None:
        class FakeGodot:
            launches = 0

            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                FakeGodot.launches += 1

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            def rpc(self, method, params=None):  # type: ignore[no-untyped-def]
                return {"method": method}

            def current_scene(self):  # type: ignore[no-untyped-def]
                return {"path": "res://scenes/main.tscn"}

            def log_events(self, *, severity=None):  # type: ignore[no-untyped-def]
                return []

            def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
                return {"name": "Main", "class": "Control", "path": "/root/Main", "child_count": 0, "children": []}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_max_failures_expected.py").write_text(
                textwrap.dedent(
                    """\
                    from godot_playwright import expected_failure

                    @expected_failure("known bug")
                    def test_a_expected_failure():
                        raise AssertionError("expected")

                    def test_b_real_failure():
                        raise AssertionError("boom")

                    def test_c_interrupted():
                        raise AssertionError("should not run")
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off", max_failures=1)

            self.assertEqual(FakeGodot.launches, 2)
            self.assertEqual(report["expected_failed"], 1)
            self.assertEqual(report["failed"], 1)
            self.assertEqual(report["interrupted"], 1)
            self.assertEqual([result["outcome"] for result in report["tests"]], ["expected_failed", "failed", "interrupted"])

    def test_run_tests_writes_junit_xml_report(self) -> None:
        class FakeGodot:
            launches = 0

            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                FakeGodot.launches += 1

            def __enter__(self):  # type: ignore[no-untyped-def]
                return FakeGodotClient()

            def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
                return None

        class FakeGodotClient:
            def rpc(self, method, params=None):  # type: ignore[no-untyped-def]
                return {"method": method}

            def current_scene(self):  # type: ignore[no-untyped-def]
                return {"path": "res://scenes/main.tscn"}

            def log_events(self, *, severity=None):  # type: ignore[no-untyped-def]
                return []

            def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
                return {"name": "Main", "class": "Control", "path": "/root/Main", "child_count": 0, "children": []}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_junit.py").write_text(
                textwrap.dedent(
                    """\
                    import sys
                    from godot_playwright import skip

                    @skip("fixture unavailable")
                    def test_a_skipped():
                        pass

                    def test_b_passes():
                        print("passing stdout")

                    def test_c_fails():
                        print("failure stderr", file=sys.stderr)
                        raise AssertionError("boom")

                    def test_d_interrupted():
                        raise AssertionError("should not run")
                    """
                ),
                encoding="utf-8",
            )
            junit_path = root / "artifacts" / "junit.xml"

            with mock.patch("godot_playwright.runner.Godot", FakeGodot):
                report = run_tests(
                    root / "project",
                    [tests_dir],
                    artifacts_dir=root / "artifacts",
                    trace="off",
                    max_failures=1,
                    junit_xml=junit_path,
                )

            self.assertEqual(FakeGodot.launches, 2)
            self.assertTrue(junit_path.exists())
            self.assertEqual(report["junit_xml"], str(junit_path.resolve()))
            self.assertIn("junit:", format_report(report))
            tree = ET.parse(junit_path)
            root_element = tree.getroot()
            suite = root_element.find("testsuite")
            self.assertIsNotNone(suite)
            assert suite is not None
            self.assertEqual(suite.attrib["tests"], "4")
            self.assertEqual(suite.attrib["failures"], "1")
            self.assertEqual(suite.attrib["skipped"], "2")
            cases = {case.attrib["name"]: case for case in suite.findall("testcase")}
            self.assertIn("test_b_passes", cases)
            self.assertEqual(cases["test_b_passes"].findtext("system-out"), "passing stdout")
            failure = cases["test_c_fails"].find("failure")
            self.assertIsNotNone(failure)
            assert failure is not None
            self.assertEqual(failure.attrib["type"], "AssertionError")
            self.assertIn("boom", failure.attrib["message"])
            self.assertEqual(cases["test_c_fails"].findtext("system-err"), "failure stderr")
            skipped = cases["test_a_skipped"].find("skipped")
            interrupted = cases["test_d_interrupted"].find("skipped")
            self.assertIsNotNone(skipped)
            self.assertIsNotNone(interrupted)
            assert skipped is not None
            assert interrupted is not None
            self.assertEqual(skipped.attrib["type"], "skipped")
            self.assertEqual(interrupted.attrib["type"], "interrupted")
            property_names = {
                property_node.attrib["name"]
                for property_node in cases["test_c_fails"].findall("./properties/property")
            }
            self.assertIn("artifact.diagnostics", property_names)
            self.assertIn("artifact.godot_log", property_names)

    def test_run_tests_parallel_workers_preserve_skips_without_godot(self) -> None:
        class FailIfLaunchedGodot:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                raise AssertionError("Godot should not launch for skipped tests")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_skip_parallel.py").write_text(
                textwrap.dedent(
                    """\
                    from godot_playwright import skip

                    @skip("first")
                    def test_a():
                        raise AssertionError("should not run")

                    @skip("second")
                    def test_b():
                        raise AssertionError("should not run")
                    """
                ),
                encoding="utf-8",
            )

            with (
                mock.patch("godot_playwright.runner.Godot", FailIfLaunchedGodot),
                mock.patch("godot_playwright.runner.install_addon", side_effect=AssertionError("install should not run")),
            ):
                report = run_tests(root / "project", [tests_dir], artifacts_dir=root / "artifacts", trace="off", workers=2)

            self.assertEqual(report["workers"], 2)
            self.assertEqual(report["skipped"], 2)
            self.assertEqual(report["failed"], 0)
            self.assertEqual([result["name"] for result in report["tests"]], ["test_a", "test_b"])
            self.assertEqual([result["annotation_reason"] for result in report["tests"]], ["first", "second"])
            self.assertIn("workers: 2", format_report(report))

    def test_run_tests_validates_worker_options(self) -> None:
        with self.assertRaises(TestRunnerError):
            run_tests("/tmp/project", ["/tmp/missing-tests"], workers=0)
        with self.assertRaises(TestRunnerError):
            run_tests("/tmp/project", ["/tmp/missing-tests"], workers=2, reuse_godot=True)
        with self.assertRaises(TestRunnerError):
            run_tests("/tmp/project", ["/tmp/missing-tests"], screenshots="sometimes")
        with self.assertRaises(TestRunnerError):
            run_tests("/tmp/project", ["/tmp/missing-tests"], max_failures=-1)
        with self.assertRaises(TestRunnerError):
            run_tests("/tmp/project", ["/tmp/missing-tests"], max_failures=1, workers=2)
        with self.assertRaises(TestRunnerError):
            run_tests("/tmp/project", ["/tmp/missing-tests"], max_failures=1, reuse_godot=True)

    def test_cli_test_selection_options_are_forwarded(self) -> None:
        report = {
            "project": "/tmp/project",
            "mode": "runtime",
            "total": 1,
            "discovered": 3,
            "passed": 0,
            "failed": 0,
            "flaky": 0,
            "duration_ms": 1.0,
            "artifacts_dir": "/tmp/artifacts",
            "results_json": "/tmp/artifacts/results.json",
            "report_html": "/tmp/artifacts/report.html",
            "junit_xml": "/tmp/artifacts/junit.xml",
            "reuse_godot": False,
            "list_only": True,
            "test_timeout": 3.5,
            "workers": 3,
            "screenshots": "only-on-failure",
            "max_failures": 2,
            "stopped_early": False,
            "selection": {
                "discovered": 3,
                "grep": ["counter"],
                "grep_invert": False,
                "after_grep": 2,
                "shard": {"current": 1, "total": 2, "before_shard": 2},
                "selected": 1,
            },
            "tests": [{"id": "/tmp/tests/test_counter.py::test_counter", "name": "test_counter", "status": "listed"}],
        }
        stdout = StringIO()
        with mock.patch("godot_playwright.cli.run_tests", return_value=report) as run:
            with redirect_stdout(stdout):
                code = cli_main(
                    [
                        "test",
                        "/tmp/project",
                        "/tmp/tests",
                        "--list",
                        "--grep",
                        "counter",
                        "--shard",
                        "1/2",
                        "--retries",
                        "2",
                        "--test-timeout",
                        "3.5",
                        "--workers",
                        "3",
                        "--screenshots",
                        "only-on-failure",
                        "--max-failures",
                        "2",
                        "--junit-xml",
                        "/tmp/artifacts/junit.xml",
                    ]
                )

        self.assertEqual(code, 0)
        self.assertIn("LIST 1 selected / 3 discovered", stdout.getvalue())
        run.assert_called_once()
        self.assertEqual(run.call_args.args[:2], ("/tmp/project", ["/tmp/tests"]))
        self.assertEqual(run.call_args.kwargs["grep"], ["counter"])
        self.assertEqual(run.call_args.kwargs["shard"], "1/2")
        self.assertTrue(run.call_args.kwargs["list_only"])
        self.assertEqual(run.call_args.kwargs["retries"], 2)
        self.assertEqual(run.call_args.kwargs["test_timeout"], 3.5)
        self.assertEqual(run.call_args.kwargs["workers"], 3)
        self.assertEqual(run.call_args.kwargs["screenshots"], "only-on-failure")
        self.assertEqual(run.call_args.kwargs["max_failures"], 2)
        self.assertEqual(run.call_args.kwargs["junit_xml"], "/tmp/artifacts/junit.xml")


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class RunnerIntegrationTests(unittest.TestCase):
    def test_runner_executes_godot_test_and_writes_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Runner Project")
            tests_dir = root / "automation"
            tests_dir.mkdir()
            (tests_dir / "test_counter.py").write_text(
                textwrap.dedent(
                    """\
                    def test_counter_button(godot, expect, expect_trace, expect_log, expect_runtime_scene, expect_signal, get_by_role, get_by_test_id):
                        expect_runtime_scene.to_have_path("res://scenes/main.tscn")
                        expect_runtime_scene.to_have_name("Main")
                        expect(get_by_test_id("counter-button")).to_have_count(1)
                        expect(get_by_role("button", name="Clicked 0")).to_have_count(1)
                        button = get_by_test_id("counter-button")
                        expect(button).to_have_property("text", "Clicked 0")
                        godot.log_clear()
                        godot.evaluate('print("runner live log marker")')
                        expect_log.to_have_message("runner live log marker")
                        button.click()
                        expect(button).to_have_property("text", "Clicked 1")
                        expect_signal("#CounterButton", "pressed").to_have_event(action=button.click)
                        expect_trace.to_have_event("node.click", data={"strategy": "pressed_signal"})
                        expect_trace.to_have_rpc("node.click")


                    def test_scene_snapshot(expect_scene):
                        expect_scene.to_have_node(name="CounterButton", class_name="Button", properties={"text": "Clicked 0"})
                        expect_scene.to_contain_text("Godot Playwright")
                        expect_scene.to_match_snapshot("main.scene.json", max_depth=2)
                    """
                ),
                encoding="utf-8",
            )

            artifacts = root / "artifacts"
            report = run_tests(
                project,
                [tests_dir],
                mode="runtime",
                timeout=20,
                artifacts_dir=artifacts,
                trace="on",
                update_snapshots=True,
            )

            self.assertEqual(report["passed"], 2)
            self.assertEqual(report["failed"], 0)
            self.assertTrue((artifacts / "results.json").exists())
            report_path = Path(report["report_html"])
            self.assertTrue(report_path.exists())
            report_text = report_path.read_text(encoding="utf-8")
            self.assertIn("Godot Playwright", report_text)
            self.assertIn("test_counter_button", report_text)
            self.assertIn("node.click", report_text)
            self.assertIn("Godot Log", report_text)
            trace_path = Path(report["tests"][0]["artifacts"]["trace"])
            self.assertTrue(trace_path.exists())
            trace_text = trace_path.read_text(encoding="utf-8")
            self.assertIn("node.click", trace_text)
            self.assertGreater(report["tests"][0]["trace_summary"]["event_count"], 0)
            log_path = Path(report["tests"][0]["artifacts"]["godot_log"])
            self.assertTrue(log_path.exists())
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("Godot Engine", log_text)
            self.assertIn("runner live log marker", log_text)
            self.assertGreater(report["tests"][0]["godot_log_summary"]["line_count"], 0)
            self.assertTrue((tests_dir / "__snapshots__" / "main.scene.json").exists())

    def test_runner_runtime_skip_with_real_godot_keeps_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Runner Runtime Skip Project")
            tests_dir = root / "automation"
            tests_dir.mkdir()
            (tests_dir / "test_runtime_skip.py").write_text(
                textwrap.dedent(
                    """\
                    def test_runtime_skip(godot, test_info, step, attach):
                        attach("scene-before-skip", body=godot.current_scene())
                        with step("inspect runtime"):
                            godot.wait_for_process_frames(1)
                            test_info.skip("runtime condition not available")
                        raise AssertionError("should not run after skip")
                    """
                ),
                encoding="utf-8",
            )

            artifacts = root / "artifacts"
            report = run_tests(
                project,
                [tests_dir],
                mode="runtime",
                timeout=20,
                artifacts_dir=artifacts,
                trace="on",
                update_snapshots=False,
            )

            self.assertEqual(report["passed"], 0)
            self.assertEqual(report["failed"], 0)
            self.assertEqual(report["skipped"], 1)
            result = report["tests"][0]
            self.assertEqual(result["status"], "skipped")
            self.assertEqual(result["outcome"], "skipped")
            self.assertTrue(result["runtime_skip"])
            self.assertEqual(result["annotation_reason"], "runtime condition not available")
            self.assertEqual(result["steps"][0]["status"], "skipped")
            self.assertEqual(result["attachments"][0]["name"], "scene-before-skip")
            self.assertTrue(Path(result["attachments"][0]["path"]).exists())
            self.assertTrue(Path(result["artifacts"]["trace"]).exists())
            self.assertTrue(Path(result["artifacts"]["godot_log"]).exists())
            self.assertNotIn("diagnostics", result)
            self.assertIn("STEP-SKIP inspect runtime", format_report(report))

    def test_runner_html_report_includes_failure_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Runner Failure Report Project")
            tests_dir = root / "automation"
            tests_dir.mkdir()
            (tests_dir / "test_failure.py").write_text(
                textwrap.dedent(
                    """\
                    def test_failure(godot, expect):
                        expect(godot.locator("#CounterButton")).to_have_text("Wrong")
                    """
                ),
                encoding="utf-8",
            )

            artifacts = root / "artifacts"
            report = run_tests(
                project,
                [tests_dir],
                mode="runtime",
                timeout=20,
                artifacts_dir=artifacts,
                trace="on",
                update_snapshots=False,
            )

            self.assertEqual(report["passed"], 0)
            self.assertEqual(report["failed"], 1)
            report_path = Path(report["report_html"])
            self.assertTrue(report_path.exists())
            html = report_path.read_text(encoding="utf-8")
            self.assertIn("test_failure", html)
            self.assertIn("Expected", html)
            self.assertIn("Wrong", html)
            self.assertIn("Trace", html)
            self.assertIn("Godot Log", html)
            self.assertIn("Diagnostics", html)
            self.assertIn("failed", html)
            self.assertTrue(Path(report["tests"][0]["artifacts"]["trace"]).exists())
            self.assertTrue(Path(report["tests"][0]["artifacts"]["godot_log"]).exists())
            self.assertTrue(Path(report["tests"][0]["artifacts"]["failure_scene"]).exists())
            diagnostics_path = Path(report["tests"][0]["artifacts"]["diagnostics"])
            self.assertTrue(diagnostics_path.exists())
            diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
            self.assertEqual(diagnostics["error"]["type"], "AssertionError")
            self.assertEqual(diagnostics["scene_snapshot"]["name"], "Main")
            self.assertGreaterEqual(diagnostics["scene_snapshot"]["tree_node_count"], 1)
            self.assertGreaterEqual(diagnostics["summary"]["trace_events"], 1)
            self.assertEqual(report["tests"][0]["diagnostics"]["scene_root"], "Main")
            self.assertGreater(report["tests"][0]["godot_log_summary"]["line_count"], 0)

    def test_runner_exposes_editor_semantic_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Runner Editor Project")
            tests_dir = root / "automation"
            tests_dir.mkdir()
            (tests_dir / "test_editor_semantics.py").write_text(
                textwrap.dedent(
                    """\
                    def test_editor_semantics(godot, expect, editor_locator, editor_get_by_role, expect_engine, expect_editor, expect_physics2d, expect_physics3d, expect_audio, expect_navigation, expect_project, expect_project_scene, expect_node_class, expect_resource_class, expect_script_class, expect_script, expect_script_file, expect_filesystem, expect_resource, expect_scene_file, expect_runtime_scene, expect_viewport, mode):
                        if mode != "editor":
                            return

                        assert expect_engine is not None
                        assert expect_physics2d is not None
                        assert expect_physics3d is not None
                        assert expect_audio is not None
                        assert expect_navigation is not None
                        assert expect_viewport is not None
                        assert expect_runtime_scene is not None
                        expect(editor_locator("Panel")).to_exist()
                        expect(editor_get_by_role("panel")).to_exist()
                        expect_engine.to_be_available()
                        expect_engine.to_be_editor()
                        godot.editor_open_scene("res://scenes/main.tscn")
                        expect_editor.to_be_available()
                        expect_editor.to_match_history({"available": True})
                        expect_project.to_have_main_scene("res://scenes/main.tscn")
                        expect_project_scene("res://scenes/main.tscn").to_have_root(name="Main", class_name="Control")
                        expect_node_class("Label").to_be_listed(base_class="Control")
                        expect_resource_class("Resource").to_be_listed()
                        expect_editor.to_have_open_scene("res://scenes/main.tscn")
                        expect_editor.to_have_edited_scene("res://scenes/main.tscn")
                        expect_editor.not_to_be_playing()
                        godot.editor_select("#CounterButton")
                        expect_editor.to_have_selection_count(1)
                        expect_editor.to_have_selection("CounterButton")
                        expect_script("res://scripts/main.gd").to_extend("Control")
                        expect_script("res://scripts/main.gd").to_define_function("_ready")
                        expect_script_file("res://scripts/main.gd").to_extend("Control")
                        expect_script_file("res://scripts/main.gd").to_define_function("_ready")
                        godot.fs_write_text("res://scripts/runner_tool.gd", "class_name RunnerTool\\nextends Node\\n")
                        expect_script_class("RunnerTool").to_be_listed(base_class="Node")
                        expect_filesystem("res://scripts").to_contain("main.gd", extension="gd")
                        expect_resource("res://scripts/main.gd").to_have_class("GDScript")
                        expect_resource("res://scenes/main.tscn").to_have_no_missing_dependencies()
                        expect_scene_file("res://scenes/main.tscn").to_have_node(name="CounterButton", class_name="Button")
                    """
                ),
                encoding="utf-8",
            )

            artifacts = root / "artifacts"
            report = run_tests(
                project,
                [tests_dir],
                mode="editor",
                timeout=30,
                artifacts_dir=artifacts,
                trace="off",
                update_snapshots=False,
            )

            self.assertEqual(report["passed"], 1)
            self.assertEqual(report["failed"], 0)


if __name__ == "__main__":
    unittest.main()
