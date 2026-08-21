import contextlib
import io
import json
import unittest

from agent_config_score import __version__
from agent_config_score.cli import main
from agent_config_score.rules import RULES


class CliTests(unittest.TestCase):
    def test_version_flag(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["--version"])
        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue().strip(), f"AgentConfigScore {__version__}")

    def test_top_level_help_lists_product_commands(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["--help"])
        self.assertEqual(code, 0)
        text = stdout.getvalue()
        self.assertIn("agent-config-score init", text)
        self.assertIn("agent-config-score rules", text)
        self.assertIn("agent-config-score diff BASE_REF", text)
        self.assertIn("agent-config-score compare BASE HEAD", text)
        self.assertIn("agent-config-score --version", text)

    def test_rules_lists_catalog(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["rules"])
        self.assertEqual(code, 0)
        text = stdout.getvalue()
        self.assertIn("curl-pipe-shell", text)
        self.assertIn("contradiction", text)
        self.assertIn(f"{len(RULES)} rules", text)

    def test_rules_single_json_is_machine_readable(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["rules", "curl-pipe-shell", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(stdout.getvalue())
        self.assertEqual(data["code"], "curl-pipe-shell")
        self.assertEqual(data["severity"], "error")
        self.assertEqual(data["category"], "danger")
        self.assertEqual(data["penalty"], 18)

    def test_rules_unknown_id_is_usage_error(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main(["rules", "does-not-exist"])
        self.assertEqual(code, 2)
        self.assertIn("unknown rule ID", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
