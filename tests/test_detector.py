"""Tests for deterministic raw authority-claim detection."""

import unittest

from authority_workspace.detector import detect_authority_claims


class AuthorityClaimDetectorTests(unittest.TestCase):
    def claim_types_for(self, value):
        return {claim["claim_type"] for claim in detect_authority_claims(value)}

    def test_detects_required_claim_categories(self):
        text = "\n".join(
            [
                "Build approved by QA.",
                "Ops authorized the rollout.",
                "Legal is done with review.",
                "No blockers remain for launch.",
                "Release authority delegated to Morgan.",
                "Receipt attached so proceed with payment.",
                "Priya is admin now for this project.",
                "You can deploy the service tonight.",
            ]
        )

        self.assertEqual(
            self.claim_types_for(text),
            {
                "approval",
                "authorization",
                "completion",
                "blocker_closure",
                "delegation",
                "receipt_sufficiency",
                "role_grant",
                "scope_claim",
            },
        )

    def test_detects_paraphrases(self):
        claims = detect_authority_claims(
            "The migration is greenlit. The hotfix is good to ship."
        )

        self.assertGreaterEqual(len(claims), 2)
        self.assertEqual({claim["claim_type"] for claim in claims}, {"approval"})
        self.assertTrue(any("greenlit" in claim["normalized_claim"] for claim in claims))
        self.assertTrue(any("good to ship" in claim["normalized_claim"] for claim in claims))

    def test_scans_nested_json_payloads_and_reports_paths(self):
        payload = {
            "ticket": {
                "comments": [
                    {"body": "Informational only."},
                    {"body": "Blockers resolved; owner now Sam."},
                ],
                "metadata": {"approval": "Finance signoff received."},
            }
        }

        claims = detect_authority_claims(payload, source_ref="case-123")
        claim_types = {claim["claim_type"] for claim in claims}

        self.assertIn("blocker_closure", claim_types)
        self.assertIn("role_grant", claim_types)
        self.assertIn("authorization", claim_types)
        self.assertTrue(all(claim["source_ref"] == "case-123" for claim in claims))
        self.assertTrue(any(claim["source_path"].endswith(".ticket.comments[1].body") for claim in claims))
        self.assertTrue(any(claim["source_path"].endswith(".ticket.metadata.approval") for claim in claims))

    def test_scans_markdown_text(self):
        markdown = """
# Release Review

- Status: all set for release.
- Decision: team has the go-ahead.
- Scope: allowed to proceed with publish.
"""

        claim_types = self.claim_types_for(markdown)

        self.assertIn("completion", claim_types)
        self.assertIn("approval", claim_types)
        self.assertIn("scope_claim", claim_types)

    def test_does_not_rely_on_scenario_id_or_fixture_type(self):
        payload = {
            "scenario_id": "approved_authorized_completed_no_blockers_owner_admin_can_deploy",
            "fixture_type": "greenlit_good_to_ship",
            "notes": "Plain bookkeeping text without authority semantics.",
        }

        self.assertEqual(detect_authority_claims(payload), [])

    def test_negated_or_denied_authority_language_is_not_positive_claim(self):
        text = "\n".join(
            [
                "This change is not approved.",
                "Approval is still pending; not authorized.",
                "Permission denied by Legal.",
                "The legal review is not done.",
                "Users are not allowed to proceed.",
                "No one can deploy this yet.",
            ]
        )

        self.assertEqual(detect_authority_claims(text), [])

    def test_affirmative_permission_requires_grant_language(self):
        claims = detect_authority_claims(
            "Permission granted for release. Permission received from Legal. Permission denied for deploy."
        )

        self.assertEqual([claim["claim_type"] for claim in claims], ["authorization", "authorization"])
        self.assertTrue(all("denied" not in str(claim["claim_text"]).lower() for claim in claims))

    def test_contract_negators_and_pending_signoff_are_not_positive_claims(self):
        text = "\n".join(
            [
                "This isn’t approved.",
                "This isn't authorized.",
                "Signoff wasn't received.",
                "Signoff pending from Legal.",
                "Sign-off wasn't received.",
                "Sign-off pending from Legal.",
            ]
        )

        self.assertEqual(detect_authority_claims(text), [])

    def test_no_blockers_does_not_suppress_later_affirmative_claims(self):
        claims = detect_authority_claims(
            "No blockers and the release is approved. No blockers, you can deploy."
        )

        self.assertEqual(
            [claim["claim_type"] for claim in claims],
            ["blocker_closure", "approval", "blocker_closure", "scope_claim"],
        )

    def test_raw_claim_detected_even_if_derived_candidate_omits_it(self):
        payload = {
            "raw": {
                "email": "Finance approved the invoice. Receipt is enough to proceed.",
            },
            "derived": {
                "candidate_text": "Invoice discussion summarized for review.",
            },
        }

        claim_types = self.claim_types_for(payload)

        self.assertIn("approval", claim_types)
        self.assertIn("receipt_sufficiency", claim_types)

    def test_claim_fields_are_deterministic_and_useful(self):
        text = "Release approved. Release approved."

        first = detect_authority_claims(text, source_ref="doc-A")
        second = detect_authority_claims(text, source_ref="doc-A")

        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertNotEqual(first[0]["claim_id"], first[1]["claim_id"])
        for claim in first:
            self.assertEqual(
                set(claim),
                {
                    "claim_id",
                    "claim_type",
                    "claim_text",
                    "normalized_claim",
                    "source_path",
                    "source_ref",
                    "severity",
                },
            )
            self.assertEqual(claim["source_ref"], "doc-A")
            self.assertEqual(claim["source_path"], "$")
            self.assertEqual(claim["severity"], "medium")
            self.assertTrue(claim["claim_text"])
            self.assertEqual(claim["normalized_claim"], claim["claim_text"].lower())


if __name__ == "__main__":
    unittest.main()
