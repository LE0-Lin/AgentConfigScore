from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


class ReleaseWorkflowContractTests(unittest.TestCase):
    def test_release_version_is_consistent(self):
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        project_version = re.search(r'^version = "([^"]+)"$', project, re.MULTILINE)

        package_source = (ROOT / "src" / "agent_config_score" / "__init__.py").read_text(
            encoding="utf-8"
        )
        package_version = re.search(r'^__version__ = "([^"]+)"$', package_source, re.MULTILINE)

        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        citation_version = re.search(r"^version: ([^\s]+)$", citation, re.MULTILINE)

        self.assertIsNotNone(package_version)
        self.assertIsNotNone(citation_version)
        self.assertIsNotNone(project_version)
        self.assertEqual(package_version.group(1), project_version.group(1))
        self.assertEqual(citation_version.group(1), project_version.group(1))

    def test_pypi_publish_uses_isolated_oidc_job(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions: {}", workflow)
        self.assertIn("name: Build and verify distributions", workflow)
        self.assertIn("name: Publish GitHub release", workflow)
        self.assertIn("name: Publish to PyPI", workflow)
        self.assertIn("name: pypi", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertNotIn("PYPI_TOKEN", workflow)
        self.assertNotIn("password:", workflow)

    def test_one_verified_artifact_feeds_both_publish_jobs(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        artifact_name = "python-package-distributions-${{ needs.build.outputs.version }}"
        self.assertEqual(workflow.count(artifact_name), 2)
        self.assertIn("if-no-files-found: error", workflow)
        self.assertIn("Validate built wheel", workflow)

    def test_privileged_third_party_publish_action_is_commit_pinned(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
