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
        self.assertEqual(workflow.count(artifact_name), 3)
        self.assertIn("if-no-files-found: error", workflow)
        self.assertIn("Validate built wheel", workflow)

    def test_publish_waits_for_source_tests_and_cross_platform_acceptance(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python -m unittest discover -s tests -v", workflow)
        self.assertIn("os: [ubuntu-latest, windows-latest, macos-latest]", workflow)
        self.assertIn("scripts/verify_installed_package.py", workflow)
        self.assertIn("needs: [build, acceptance]", workflow)
        self.assertIn("needs: [build, acceptance, github-release]", workflow)
        self.assertIn("pip install --no-deps", workflow)

    def test_ci_uses_the_same_installed_acceptance_on_all_platforms(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        package = workflow.split("  package:", 1)[1].split("  score_history:", 1)[0]
        self.assertIn("os: [ubuntu-latest, windows-latest, macos-latest]", package)
        self.assertIn("scripts/verify_installed_package.py", package)
        self.assertIn("Scripts/python.exe", package)
        self.assertIn("--expected-version", package)

    def test_privileged_third_party_publish_action_is_commit_pinned(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33",
            workflow,
        )

    def test_current_package_has_versioned_release_notes_and_changelog(self):
        source = (ROOT / "src" / "agent_config_score" / "__init__.py").read_text(encoding="utf-8")
        version = re.search(r'^__version__ = "([^"]+)"$', source, re.MULTILINE).group(1)
        notes = ROOT / "docs" / "releases" / f"v{version}.md"
        self.assertTrue(notes.is_file())
        content = notes.read_text(encoding="utf-8")
        self.assertIn(f"agent-config-score=={version}", content)
        self.assertIn(f"AgentConfigScore {version}", content)
        self.assertIn("Beta", content)
        self.assertIn(f"## v{version}\n", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_release_prefers_reviewed_notes_with_a_generated_fallback(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('notes="docs/releases/$TAG.md"', workflow)
        self.assertIn('note_args=(--notes-file "$notes")', workflow)
        self.assertIn("note_args=(--generate-notes)", workflow)
        self.assertEqual(workflow.count('"${note_args[@]}"'), 2)


if __name__ == "__main__":
    unittest.main()
