import json
from pathlib import Path
import unittest

from agent_config_score.config import load_policy
from agent_config_score.regression import compare
from agent_config_score.sarif import sarif_report
from agent_config_score.scanner import analyze


CONTRACT_ROOT = Path(__file__).parent / "fixtures" / "contracts"


class ContractFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((CONTRACT_ROOT / "manifest.json").read_text(encoding="utf-8"))

    def test_scan_contracts(self):
        for name, expected in self.manifest["scan_cases"].items():
            with self.subTest(case=name):
                root = CONTRACT_ROOT / "scan" / name
                policy = load_policy(root)
                report = analyze(root, suppressions=policy.suppressions)

                self.assertEqual(report.score, expected["score"])
                self.assertEqual(report.grade, expected["grade"])
                self.assertEqual(
                    [finding.code for finding in report.findings],
                    expected["findings"],
                )
                self.assertEqual(
                    [item.finding.code for item in report.suppressed_findings],
                    expected["suppressed"],
                )

                sarif_codes = [
                    result["ruleId"]
                    for result in sarif_report(report)["runs"][0]["results"]
                ]
                self.assertEqual(sarif_codes, expected["findings"])

    def test_regression_contracts(self):
        for name, expected in self.manifest["regression_cases"].items():
            with self.subTest(case=name):
                root = CONTRACT_ROOT / "regression" / name
                base = root / "base"
                head = root / "head"
                policy = load_policy(base)
                report = compare(base, head, suppressions=policy.suppressions)

                self.assertEqual(report.base.score, expected["base_score"])
                self.assertEqual(report.head.score, expected["head_score"])
                self.assertEqual(report.delta, expected["delta"])
                self.assertEqual(
                    [finding.code for finding in report.new_findings],
                    expected["new_findings"],
                )
                self.assertEqual(
                    [finding.code for finding in report.resolved_findings],
                    expected["resolved_findings"],
                )

    def test_manifest_references_existing_fixture_directories(self):
        scan_root = CONTRACT_ROOT / "scan"
        regression_root = CONTRACT_ROOT / "regression"
        self.assertEqual(
            sorted(path.name for path in scan_root.iterdir() if path.is_dir()),
            sorted(self.manifest["scan_cases"]),
        )
        self.assertEqual(
            sorted(path.name for path in regression_root.iterdir() if path.is_dir()),
            sorted(self.manifest["regression_cases"]),
        )


if __name__ == "__main__":
    unittest.main()
