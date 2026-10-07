import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agent_config_score import __version__


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package_acceptance", ROOT / "scripts" / "verify_installed_package.py")
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


class PackageAcceptanceTests(unittest.TestCase):
    def test_module_entrypoint_has_full_product_help_and_version(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        with tempfile.TemporaryDirectory() as directory:
            for option in ("--help", "--version"):
                result = subprocess.run([sys.executable, "-m", "agent_config_score", option],
                                        cwd=directory, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                if option == "--version":
                    self.assertEqual(result.stdout.strip(), f"AgentConfigScore {__version__}")
                else:
                    self.assertIn("doctor", result.stdout)
                    self.assertIn("diff [BASE_REF]", result.stdout)

    def test_nonzero_status_cannot_become_a_success(self):
        result = subprocess.CompletedProcess(["tool"], 2, stdout="{}", stderr="error")
        with patch.object(acceptance.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(acceptance.AcceptanceError, "Expected exit 0, got 2"):
                acceptance.run(["tool"], ROOT)

    def test_expected_gate_failure_is_accepted_but_tracebacks_are_not(self):
        result = subprocess.CompletedProcess(["tool"], 1, stdout="report", stderr="")
        with patch.object(acceptance.subprocess, "run", return_value=result):
            self.assertEqual(acceptance.run(["tool"], ROOT, expected=1), "report")
        result.stderr = "Traceback (most recent call last)"
        with patch.object(acceptance.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(acceptance.AcceptanceError, "Unexpected traceback"):
                acceptance.run(["tool"], ROOT, expected=1)

    def test_source_fallback_environment_is_removed(self):
        result = subprocess.CompletedProcess(["tool"], 0, stdout="ok", stderr="")
        with patch.dict(os.environ, {"PYTHONPATH": "source", "PYTHONHOME": "source"}):
            with patch.object(acceptance.subprocess, "run", return_value=result) as mocked:
                acceptance.run(["tool"], ROOT)
                env = mocked.call_args.kwargs["env"]
                self.assertNotIn("PYTHONPATH", env)
                self.assertNotIn("PYTHONHOME", env)
                self.assertEqual(env["PYTHONNOUSERSITE"], "1")
                self.assertEqual(os.environ["PYTHONPATH"], "source")

    def test_timeout_is_a_failed_acceptance(self):
        with patch.object(acceptance.subprocess, "run", side_effect=subprocess.TimeoutExpired(["tool"], 60)):
            with self.assertRaises(acceptance.AcceptanceError):
                acceptance.run(["tool"], ROOT)

    def test_main_does_not_claim_success_after_a_failed_verification(self):
        with patch.object(acceptance, "verify", side_effect=acceptance.AcceptanceError("failed check")):
            with patch("builtins.print") as printed:
                self.assertEqual(acceptance.main(["--python", sys.executable, "--expected-version", __version__]), 1)
            self.assertTrue(all("PASS" not in str(call) for call in printed.call_args_list))

    def test_main_preserves_the_virtualenv_interpreter_path(self):
        python = Path("wheel-env") / "bin" / "python"
        with patch.object(acceptance, "verify", return_value=[]) as verify:
            with patch("pathlib.Path.resolve", side_effect=AssertionError("Would leave the venv")):
                with patch("builtins.print"):
                    self.assertEqual(acceptance.main(["--python", str(python), "--expected-version", __version__]), 0)
        verify.assert_called_once_with(python.absolute(), __version__)


if __name__ == "__main__":
    unittest.main()
