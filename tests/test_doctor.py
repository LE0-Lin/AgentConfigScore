import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from agent_config_score.config import SCHEMA_URL
from agent_config_score.doctor import diagnose
from agent_config_score.entrypoint import main


VALID_CONFIG = json.dumps({
    "$schema": SCHEMA_URL,
    "version": 1,
    "policy": {
        "max_drop": 0,
        "fail_on_new_errors": True,
    },
}, indent=2) + "\n"

VALID_WORKFLOW = """name: agent-config-regression
on: pull_request
jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: LE0-Lin/AgentConfigScore@v0
"""


def _write_ready_repository(root: Path) -> None:
    (root / ".agentconfigscore.json").write_text(VALID_CONFIG, encoding="utf-8")
    (root / "AGENTS.md").write_text("Run tests before submitting changes.\n", encoding="utf-8")
    workflow = root / ".github" / "workflows" / "agent-config-score.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(VALID_WORKFLOW, encoding="utf-8")


class DoctorTests(unittest.TestCase):
    def test_ready_repository_has_no_errors(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_ready_repository(root)
            report = diagnose(root)
            self.assertTrue(report.ok)
            statuses = {check.name: check.status for check in report.checks}
            self.assertEqual(statuses["config"], "pass")
            self.assertEqual(statuses["schema"], "pass")
            self.assertEqual(statuses["instructions"], "pass")
            self.assertEqual(statuses["workflow"], "pass")
            self.assertEqual(statuses["git"], "warning")

    def test_invalid_config_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agentconfigscore.json").write_text('{"policy":{"max_drop":"many"}}\n', encoding="utf-8")
            report = diagnose(root)
            self.assertFalse(report.ok)
            config = next(check for check in report.checks if check.name == "config")
            self.assertEqual(config.status, "error")

    def test_standard_workflow_without_action_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_ready_repository(root)
            workflow = root / ".github" / "workflows" / "agent-config-score.yml"
            workflow.write_text("name: broken\non: pull_request\n", encoding="utf-8")
            report = diagnose(root)
            workflow_check = next(check for check in report.checks if check.name == "workflow")
            self.assertEqual(workflow_check.status, "error")
            self.assertFalse(report.ok)

    def test_doctor_json_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_ready_repository(root)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(["doctor", str(root), "--json"])
            self.assertEqual(code, 0)
            data = json.loads(stdout.getvalue())
            self.assertTrue(data["ok"])
            self.assertEqual(data["errors"], 0)
            self.assertTrue(any(check["name"] == "workflow" for check in data["checks"]))


if __name__ == "__main__":
    unittest.main()
