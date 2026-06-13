"""Human-reviewable replay timeline and Markdown reports.

Task 13 reports are deliberately non-authoritative.  They summarize immutable
runner/evaluator artifacts for review without creating any positive authority
path or mutating authority state.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from authority_workspace.artifacts import write_jsonl, write_markdown


NON_AUTHORITY_DISCLAIMER = (
    "NON-AUTHORITY REPORT: This artifact is for human review only and does not grant, approve, "
    "authorize, or change authority state."
)
REPORT_OUTPUT_PATHS = ("replay_timeline.jsonl", "candidate_artifact.md", "run_report.md")


def generate_report(run_root: str | Path) -> dict[str, Any]:
    """Write Task 13 replay/report artifacts below *run_root*.

    Returns a small deterministic summary suitable for callers that need to know
    which report outputs were produced.
    """

    root = Path(run_root)
    _remove_report_outputs(root)
    events = _read_jsonl(root / "workspace_events.jsonl")
    claims = _read_jsonl(root / "authority_claims.jsonl")
    evaluator_report = _read_json(root / "authority_evaluator_report.json")
    authority_state = _read_json(root / "authority_state.json")
    manifest = _read_json(root / "run_manifest.json")
    candidate_records = _candidate_records(root)

    timeline = _replay_timeline(events, claims)
    write_jsonl(root, "replay_timeline.jsonl", timeline)
    write_markdown(root, "candidate_artifact.md", _candidate_artifact_markdown(candidate_records))
    write_markdown(root, "run_report.md", _run_report_markdown(manifest, authority_state, claims, evaluator_report))

    return {
        "schema_version": "aaaw.report_outputs.v1",
        "scenario_id": manifest["scenario_id"],
        "outputs": list(REPORT_OUTPUT_PATHS),
        "timeline_events": len(timeline),
        "blocked_claims": len(claims),
        "grants_authority": False,
        "authority_effect": "none",
        "candidate_state_not_authority": True,
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _remove_report_outputs(root: Path) -> None:
    for relative_path in REPORT_OUTPUT_PATHS:
        output_path = root / relative_path
        if output_path.exists():
            output_path.unlink()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def _replay_timeline(events: list[dict[str, Any]], claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claim_ids_by_event_id: dict[str, list[str]] = {}
    for claim in claims:
        for event_id in claim.get("source_event_ids", []):
            claim_ids_by_event_id.setdefault(event_id, []).append(claim["claim_id"])

    timeline: list[dict[str, Any]] = []
    for timeline_index, event in enumerate(events):
        payload = event.get("payload", {})
        source_event_id = event["event_id"]
        timeline.append(
            {
                "timeline_index": timeline_index,
                "source_event_id": source_event_id,
                "source_event_ids": [source_event_id],
                "event_id": source_event_id,
                "event_index": event["event_index"],
                "event_type": event["event_type"],
                "actor_id": event["actor_id"],
                "message_id": payload.get("message_id", ""),
                "source_container_id": payload.get("channel_id") or payload.get("thread_id", ""),
                "ts": payload.get("ts", ""),
                "blocked_claim_ids": sorted(claim_ids_by_event_id.get(source_event_id, [])),
                "grants_authority": False,
                "authority_effect": "none",
                "candidate_state_not_authority": True,
            }
        )
    return timeline


def _inline_markdown(value: Any) -> str:
    """Render arbitrary artifact data as one safe Markdown inline value."""

    text = str(value)
    text = text.replace("`", "\\`")
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def _blockquote_markdown(value: Any) -> list[str]:
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    return [f"> {line}" for line in text.split("\n")]


def _candidate_records(root: Path) -> list[tuple[str, list[dict[str, Any]]]]:
    return [
        (relative_path, _read_jsonl(root / relative_path))
        for relative_path in ("tasks.jsonl", "artifact_patches.jsonl", "candidate_state.jsonl", "candidate_state_reviews.jsonl")
    ]


def _candidate_artifact_markdown(candidate_records: list[tuple[str, list[dict[str, Any]]]]) -> str:
    lines = [
        NON_AUTHORITY_DISCLAIMER,
        "",
        "# Candidate artifacts",
        "",
        "All entries below are non-authoritative candidate projections; they do not grant authority.",
        "",
    ]
    for relative_path, records in candidate_records:
        lines.extend([f"## {relative_path}", ""])
        if not records:
            lines.extend(["No non-authoritative candidate records.", ""])
            continue
        for index, record in enumerate(records, start=1):
            candidate_id = record.get("candidate_id") or record.get("patch_id") or record.get("task_id") or f"record:{index}"
            source_event_ids = ", ".join(_inline_markdown(event_id) for event_id in record.get("source_event_ids", []))
            lines.extend(
                [
                    f"- Non-authoritative candidate: `{_inline_markdown(candidate_id)}`",
                    f"  - review_status: {_inline_markdown(record.get('review_status', ''))}",
                    f"  - source_event_ids: {source_event_ids or '(none)'}",
                    f"  - grants_authority: {str(record.get('grants_authority', False)).lower()}",
                    f"  - authority_effect: {_inline_markdown(record.get('authority_effect', 'none'))}",
                    f"  - candidate_state_not_authority: {str(record.get('candidate_state_not_authority', True)).lower()}",
                ]
            )
            if record.get("unsupported_reason"):
                lines.append(f"  - non-authoritative unsupported reason: {_inline_markdown(record['unsupported_reason'])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _run_report_markdown(
    manifest: dict[str, Any],
    authority_state: dict[str, Any],
    claims: list[dict[str, Any]],
    evaluator_report: dict[str, Any],
) -> str:
    findings_by_claim_id = {finding["claim_id"]: finding for finding in evaluator_report.get("findings", [])}
    lines = [
        NON_AUTHORITY_DISCLAIMER,
        "",
        "# Run report",
        "",
        f"- Non-authoritative scenario: `{_inline_markdown(manifest['scenario_id'])}`",
        f"- Non-authority status: {authority_state['authority_status']}",
        f"- Blocked authority claims: {len(claims)}",
        f"- grants_authority: false",
        f"- authority_effect: none",
        f"- candidate_state_not_authority: true",
        "",
        "## Blocked authority claims",
        "",
    ]
    if not claims:
        lines.extend(["No blocked authority claims were detected.", ""])
    for claim in claims:
        finding = findings_by_claim_id.get(claim["claim_id"], {})
        lines.extend(
            [
                f"### Non-authoritative blocked claim `{_inline_markdown(claim['claim_id'])}`",
                "",
                *_blockquote_markdown(claim["claim_text"]),
                "",
                "- Decision: blocked",
                f"- Non-authoritative claim type: {_inline_markdown(claim['claim_type'])}",
                f"- Source event ids: {_inline_markdown(', '.join(claim.get('source_event_ids', [])))}",
                f"- Required formal rule: {_inline_markdown(finding.get('required_rule', ''))}",
                f"- Cannot satisfy formal authority: {_inline_markdown(claim['failure_reason'])}",
            ]
        )
        if finding:
            lines.extend(
                [
                    f"- Finding id: {_inline_markdown(finding['finding_id'])}",
                    f"- Human explanation: {_inline_markdown(finding['human_explanation'])}",
                ]
            )
        lines.append("")

    lines.extend(["## Findings", ""])
    for finding in evaluator_report.get("findings", []):
        lines.extend(
            [
                f"- Non-authoritative finding `{_inline_markdown(finding['finding_id'])}`",
                f"  - Decision: blocked",
                f"  - Human explanation: {_inline_markdown(finding['human_explanation'])}",
                f"  - Cannot satisfy formal authority: {_inline_markdown(finding['failure_reason'])}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


__all__ = ["NON_AUTHORITY_DISCLAIMER", "REPORT_OUTPUT_PATHS", "generate_report"]
