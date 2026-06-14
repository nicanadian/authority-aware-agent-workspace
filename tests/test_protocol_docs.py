"""Protocol documentation contract tests."""

import unittest
from pathlib import Path

from authority_workspace.runner import RUN_ARTIFACT_PATHS
from authority_workspace.scenario import CONTEXT_MODES


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_DOCS = {
    "raw_chat_v0": REPO_ROOT / "protocols" / "raw_chat_v0.md",
    "typed_evidence_v0": REPO_ROOT / "protocols" / "typed_evidence_v0.md",
}
REQUIRED_SECTIONS = [
    "## Allowed context",
    "## Allowed social actions",
    "## Allowed candidate-state actions",
    "## Authority restrictions",
    "## Expected failure modes",
    "## Artifact contract",
    "## Context exposure behavior",
]
REQUIRED_INVARIANTS = [
    "grants_authority: false",
    "authority_effect: none",
    "candidate state is not authority",
    "candidate_state_not_authority: true",
]
REQUIRED_ARTIFACTS = ["run_manifest.json", *RUN_ARTIFACT_PATHS]


class ProtocolDocsTests(unittest.TestCase):
    def test_protocol_docs_exist(self):
        for protocol, path in PROTOCOL_DOCS.items():
            with self.subTest(protocol=protocol):
                self.assertTrue(path.is_file(), f"missing protocol doc: {path}")

    def test_protocol_docs_include_required_contract_sections(self):
        for protocol, path in PROTOCOL_DOCS.items():
            with self.subTest(protocol=protocol):
                text = path.read_text(encoding="utf-8")
                self.assertIn(f"# {protocol}", text)
                for section in REQUIRED_SECTIONS:
                    self.assertIn(section, text)

    def test_protocol_docs_preserve_no_authority_invariants(self):
        for protocol, path in PROTOCOL_DOCS.items():
            text = path.read_text(encoding="utf-8").lower()
            for invariant in REQUIRED_INVARIANTS:
                with self.subTest(protocol=protocol, invariant=invariant):
                    self.assertIn(invariant, text)

    def test_protocol_docs_link_core_artifacts(self):
        for protocol, path in PROTOCOL_DOCS.items():
            text = path.read_text(encoding="utf-8")
            for artifact in REQUIRED_ARTIFACTS:
                with self.subTest(protocol=protocol, artifact=artifact):
                    self.assertIn(artifact, text)

    def test_protocol_docs_name_supported_context_modes(self):
        for protocol, path in PROTOCOL_DOCS.items():
            text = path.read_text(encoding="utf-8")
            for context_mode in CONTEXT_MODES:
                with self.subTest(protocol=protocol, context_mode=context_mode):
                    self.assertIn(context_mode, text)

    def test_typed_evidence_doc_does_not_claim_current_evaluator_extracts_from_candidate_artifacts(self):
        text = PROTOCOL_DOCS["typed_evidence_v0"].read_text(encoding="utf-8")
        self.assertIn("Current v0 evaluator claim extraction scans `workspace_events.jsonl` raw event payloads", text)
        self.assertNotIn("extracted typed or source-backed claims", text)


if __name__ == "__main__":
    unittest.main()
