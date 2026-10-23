"""The optional public-source replay is isolated from ordinary lint CI."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RealWorldSmokeWorkflowTests(unittest.TestCase):
    def workflow(self):
        return (ROOT / ".github/workflows/real-world-smoke.yml").read_text(encoding="utf-8")

    def test_network_replay_is_explicitly_manual_and_read_only(self):
        workflow = self.workflow()
        triggers = workflow.split("on:\n", 1)[1].split("\npermissions:", 1)[0]
        self.assertEqual(triggers.strip(), "workflow_dispatch:")
        self.assertIn("contents: read", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("inputs.", workflow)

    def test_same_runner_propagates_failures_without_external_code_execution(self):
        workflow = self.workflow()
        self.assertIn("timeout-minutes: 15", workflow)
        self.assertIn("set -euo pipefail", workflow)
        self.assertIn("PYTHONPATH: src", workflow)
        self.assertIn("python -u scripts/run_real_world_benchmark.py", workflow)
        self.assertIn("GIT_TERMINAL_PROMPT:", workflow)
        self.assertNotIn("continue-on-error", workflow)
        self.assertNotIn("pip install", workflow)
        self.assertNotIn("pull_request_target", workflow)

    def test_logs_are_retained_even_if_acquisition_fails(self):
        workflow = self.workflow()
        self.assertIn("if: always()", workflow)
        self.assertIn(".agent-config-score/real-world-smoke.json", workflow)
        self.assertIn("2>&1 | tee .agent-config-score/real-world-smoke.log", workflow)
        self.assertIn("retention-days: 7", workflow)
        self.assertRegex(workflow, r"actions/upload-artifact@[0-9a-f]{40}")
        self.assertIn("${{ github.sha }}", workflow)


if __name__ == "__main__":
    unittest.main()
