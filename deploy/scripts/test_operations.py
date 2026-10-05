"""Focused safety tests. No Docker daemon, network, secrets, or real backup data used."""
import datetime as dt
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


update = load("update", "update.py")
retention = load("retention", "retain-backups.py")
NOW = dt.datetime(2026, 10, 5, 12, tzinfo=dt.timezone.utc)


def workflow(number, **changes):
    result = dict(run_number=number, head_branch="main", event="push", status="completed",
                  conclusion="success", head_repository={"full_name": "bmepilots/backend"},
                  head_sha="a" * 40, updated_at="2026-10-05T11:00:00Z")
    result.update(changes)
    return result


class ReleaseSelection(unittest.TestCase):
    def test_ignores_pr_failed_and_foreign_runs(self):
        runs = [workflow(1), workflow(2, event="pull_request"), workflow(3, conclusion="failure"),
                workflow(4, head_repository={"full_name": "other/backend"})]
        self.assertEqual(update.select_run(runs, "bmepilots/backend", NOW, 120)["run_number"], 1)

    def test_older_rerun_cannot_replace_newer_main(self):
        runs = [workflow(2, updated_at="2026-10-05T11:50:00Z"), workflow(3)]
        self.assertEqual(update.select_run(runs, "bmepilots/backend", NOW, 120)["run_number"], 3)

    def test_newest_run_settles_before_deploy(self):
        with self.assertRaises(RuntimeError):
            update.select_run([workflow(3, updated_at="2026-10-05T11:59:30Z")], "bmepilots/backend", NOW, 120)

    def test_invalid_sha_rejected(self):
        with self.assertRaises(RuntimeError):
            update.select_run([workflow(1, head_sha="main")], "bmepilots/backend", NOW, 120)


class Retention(unittest.TestCase):
    def test_retains_latest_complete_partial_and_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ["20260801T000000Z", "20260802T000000Z", "20260803T000000Z", "unrecognized"]:
                (root / name).mkdir()
            (root / "20260801T000000Z/COMPLETE").touch()
            (root / "20260802T000000Z/COMPLETE").touch()
            (root / "unrecognized/COMPLETE").touch()
            expired = retention.expired_backups(root, 7, NOW)
            self.assertEqual([p.name for p in expired], ["20260801T000000Z"])

    def test_keeps_all_recent_backups(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ["20261004T000000Z", "20261005T000000Z"]:
                (root / name).mkdir()
                (root / name / "COMPLETE").touch()
            self.assertEqual(retention.expired_backups(root, 7, NOW), [])


class ApiCompatibility(unittest.TestCase):
    def test_new_frontend_cannot_deploy_before_backend(self):
        with self.assertRaises(RuntimeError):
            update.validate_contracts({"backend": {"api_contracts": ["1"]}, "frontend": {"api_requires": "2"}})

    def test_backward_compatible_backend_allows_old_and_new_frontend(self):
        for required in ("1", "2"):
            update.validate_contracts({"backend": {"api_contracts": ["1", "2"]}, "frontend": {"api_requires": required}})

    def test_bad_labels_fail_closed(self):
        with self.assertRaises(RuntimeError):
            update.validate_contracts({"backend": {"api_contracts": ["all"]}, "frontend": {"api_requires": "2"}})


class RollbackPolicy(unittest.TestCase):
    def exercise_failure(self, after, fail_rollback=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            selected = {s: {"image": f"new-{s}"} for s in update.SERVICES}
            current = {s: {"image": f"old-{s}"} for s in update.SERVICES}
            def operation(*args, **kwargs):
                if args[0] == "up" and (fail_rollback or "new-backend" in (root / "release.env").read_text()):
                    raise RuntimeError("simulated unhealthy application")
            with patch.object(update, "DEPLOY", root), patch.object(update, "run"), \
                 patch.object(update, "schema_fingerprint", side_effect=["before", after]), \
                 patch.object(update, "compose", side_effect=operation) as compose, \
                 patch.object(update, "check_gateway"):
                with self.assertRaises(RuntimeError):
                    update.apply(selected, current)
                import json
                state = json.loads((root / "update-failure.json").read_text())
                return state, (root / "release.env").read_text(), compose.call_args_list

    def test_unchanged_schema_restores_previous_images_and_pauses(self):
        state, release, calls = self.exercise_failure("before")
        self.assertEqual(state["status"], "rolled_back")
        self.assertIn("old-backend", release)
        self.assertEqual(sum(call.args[0] == "up" for call in calls), 2)

    def test_changed_schema_never_starts_old_application(self):
        state, release, calls = self.exercise_failure("after")
        self.assertEqual(state["status"], "schema_changed_or_unreadable")
        self.assertIn("new-backend", release)
        self.assertEqual(sum(call.args[0] == "up" for call in calls), 1)

    def test_unreadable_schema_never_starts_old_application(self):
        state, release, calls = self.exercise_failure(RuntimeError("database unavailable"))
        self.assertEqual(state["status"], "schema_changed_or_unreadable")
        self.assertIn("new-backend", release)

    def test_failed_rollback_remains_gated(self):
        state, release, calls = self.exercise_failure("before", fail_rollback=True)
        self.assertEqual(state["status"], "rollback_failed")


if __name__ == "__main__":
    unittest.main()
