import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from agent_config_score.cli import main
from agent_config_score.initializer import CONFIG_CONTENT, WORKFLOW_CONTENT, InitError, initialize_repository


class InitializerTests(unittest.TestCase):
    def test_creates_policy_and_workflow(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            changes = initialize_repository(root)

            self.assertEqual([change.action for change in changes], ["create", "create"])
            self.assertEqual((root / ".agentconfigscore.json").read_text(encoding="utf-8"), CONFIG_CONTENT)
            self.assertEqual(
                (root / ".github" / "workflows" / "agent-config-score.yml").read_text(encoding="utf-8"),
                WORKFLOW_CONTENT,
            )

    def test_conflict_is_atomic_and_does_not_write_partial_config(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            workflow = root / ".github" / "workflows" / "agent-config-score.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("custom workflow\n", encoding="utf-8")

            with self.assertRaisesRegex(InitError, "refusing to overwrite"):
                initialize_repository(root)

            self.assertFalse((root / ".agentconfigscore.json").exists())
            self.assertEqual(workflow.read_text(encoding="utf-8"), "custom workflow\n")

    def test_force_overwrites_conflicting_generated_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            config = root / ".agentconfigscore.json"
            config.write_text('{"custom":true}\n', encoding="utf-8")

            changes = initialize_repository(root, include_workflow=False, force=True)

            self.assertEqual(changes[0].action, "overwrite")
            self.assertEqual(config.read_text(encoding="utf-8"), CONFIG_CONTENT)

    def test_no_workflow_creates_only_policy(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            initialize_repository(root, include_workflow=False)
            self.assertTrue((root / ".agentconfigscore.json").is_file())
            self.assertFalse((root / ".github").exists())

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            changes = initialize_repository(root, dry_run=True)
            self.assertEqual([change.action for change in changes], ["create", "create"])
            self.assertEqual(list(root.iterdir()), [])

    def test_matching_files_are_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            initialize_repository(root)
            changes = initialize_repository(root)
            self.assertEqual([change.action for change in changes], ["unchanged", "unchanged"])

    def test_cli_init_reports_created_files(self):
        with tempfile.TemporaryDirectory() as d:
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main(["init", d])
            self.assertEqual(code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn(".agentconfigscore.json", stdout.getvalue())
            self.assertIn(".github/workflows/agent-config-score.yml", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
