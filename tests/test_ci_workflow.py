"""Contract tests for the GitHub Actions deterministic CI workflow."""

from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


class GitHubActionsCiWorkflowTests(unittest.TestCase):
    def workflow_text(self) -> str:
        return CI_WORKFLOW.read_text(encoding="utf-8")

    def test_ci_workflow_exists_and_uses_python_311(self):
        self.assertTrue(CI_WORKFLOW.exists())
        text = self.workflow_text()
        self.assertIn("actions/checkout@", text)
        self.assertIn("actions/setup-python@", text)
        self.assertIn("python-version: '3.11'", text)

    def test_ci_workflow_runs_deterministic_quality_gates(self):
        text = self.workflow_text()
        self.assertIn("python3 -m unittest discover -s tests -v", text)
        self.assertIn("python3 -m compileall authority_workspace", text)
        self.assertIn("python3 -m json.tool", text)

    def test_ci_workflow_runs_cli_smoke_in_temporary_directory(self):
        text = self.workflow_text()
        self.assertIn("mktemp -d", text)
        self.assertIn("python3 -m authority_workspace.cli run scenarios/fixtures/side_channel_approval.json --out", text)
        self.assertIn("python3 -m authority_workspace.cli evaluate", text)
        self.assertIn("test -f \"$RUN_ROOT/run_report.md\"", text)
        self.assertIn("test -f \"$RUN_ROOT/authority_evaluator_report.json\"", text)

    def test_ci_workflow_is_deterministic_and_secret_free(self):
        text = self.workflow_text().lower()
        self.assertNotIn("secrets.", text)
        self.assertNotIn("id-token: write", text)
        self.assertNotIn("curl ", text)
        self.assertNotIn("pip install", text)


if __name__ == "__main__":
    unittest.main()
