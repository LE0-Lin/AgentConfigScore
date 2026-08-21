import contextlib
import io
import unittest

from agent_config_score import __version__
from agent_config_score.cli import main


class CliTests(unittest.TestCase):
    def test_version_flag(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["--version"])
        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue().strip(), f"AgentConfigScore {__version__}")

    def test_top_level_help_lists_regression_commands(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["--help"])
        self.assertEqual(code, 0)
        text = stdout.getvalue()
        self.assertIn("agent-config-score diff BASE_REF", text)
        self.assertIn("agent-config-score compare BASE HEAD", text)
        self.assertIn("agent-config-score --version", text)


if __name__ == "__main__":
    unittest.main()
