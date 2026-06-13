"""Deterministic raw authority-claim detection.

The detector is intentionally small and stdlib-only.  It scans raw strings and
JSON-like nested values for semantic authority claims without using fixture
metadata such as scenario IDs.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class _ClaimPattern:
    claim_type: str
    regex: re.Pattern[str]
    severity: str = "medium"


_METADATA_KEYS_TO_SKIP = {"scenario_id", "fixture_type"}

_CLAIM_PATTERNS: tuple[_ClaimPattern, ...] = (
    _ClaimPattern(
        "receipt_sufficiency",
        re.compile(
            r"\breceipt\s+(?:attached\s+so\s+proceed|(?:is\s+)?enough\s+(?:to\s+)?(?:proceed|continue|move\s+forward))\b",
            re.IGNORECASE,
        ),
    ),
    _ClaimPattern(
        "blocker_closure",
        re.compile(
            r"\b(?:no\s+blockers?|blockers?\s+(?:resolved|cleared|closed|gone))\b",
            re.IGNORECASE,
        ),
    ),
    _ClaimPattern(
        "approval",
        re.compile(
            r"\b(?:approved|greenlit|good\s+to\s+ship|go\s*-?\s*ahead)\b",
            re.IGNORECASE,
        ),
    ),
    _ClaimPattern(
        "authorization",
        re.compile(
            r"\b(?:authorized|authorised|permission\s+(?:granted|given|received)|sign\s*-?\s*off|signoff)\b",
            re.IGNORECASE,
        ),
    ),
    _ClaimPattern(
        "completion",
        re.compile(
            r"\b(?:legal\s+is\s+done|done|completed|all\s+set)\b",
            re.IGNORECASE,
        ),
    ),
    _ClaimPattern(
        "delegation",
        re.compile(
            r"\b(?:delegated|assigned\s+authority|authority\s+(?:has\s+been\s+)?assigned|owner\s+now)\b",
            re.IGNORECASE,
        ),
    ),
    _ClaimPattern(
        "role_grant",
        re.compile(
            r"\b(?:admin\s+now|owner\s+now|granted\s+(?:the\s+)?(?:role|admin|owner)|role\s+granted)\b",
            re.IGNORECASE,
        ),
    ),
    _ClaimPattern(
        "scope_claim",
        re.compile(
            r"\b(?:(?:can|may|allowed\s+to)\s+(?:ship|deploy|publish|merge|release|proceed)|allowed\s+to\s+proceed)\b",
            re.IGNORECASE,
        ),
    ),
)


def detect_authority_claims(value: Any, source_ref: str | None = None) -> list[dict[str, str | None]]:
    """Detect authority claims in strings inside *value*.

    Args:
        value: A string, Markdown/plain text, or nested JSON-like structure made
            of mappings/sequences/scalars. Only string values are scanned.
        source_ref: Optional caller-provided reference copied onto each claim.

    Returns:
        A deterministic list of claim dictionaries.  Each claim contains:
        ``claim_id``, ``claim_type``, ``claim_text``, ``normalized_claim``,
        ``source_path``, ``source_ref``, and ``severity``.
    """

    claim_entries: list[tuple[int, int, str, dict[str, str | None]]] = []
    for string_order, (source_path, text) in enumerate(_iter_strings(value)):
        for pattern in _CLAIM_PATTERNS:
            for match in pattern.regex.finditer(text):
                if _is_negated_or_denied(text, match.start(), match.end()):
                    continue
                claim_text = match.group(0).strip()
                normalized = _normalize_claim(claim_text)
                claim_entries.append(
                    (
                        string_order,
                        match.start(),
                        pattern.claim_type,
                        {
                            "claim_id": _claim_id(
                                source_ref=source_ref,
                                source_path=source_path,
                                claim_type=pattern.claim_type,
                                start=match.start(),
                                end=match.end(),
                                normalized_claim=normalized,
                            ),
                            "claim_type": pattern.claim_type,
                            "claim_text": claim_text,
                            "normalized_claim": normalized,
                            "source_path": source_path,
                            "source_ref": source_ref,
                            "severity": pattern.severity,
                        },
                    )
                )
    return [claim for _, _, _, claim in sorted(claim_entries, key=lambda entry: entry[:3])]


def _iter_strings(value: Any, path: str = "$", *, key_name: str | None = None) -> Iterator[tuple[str, str]]:
    if key_name in _METADATA_KEYS_TO_SKIP:
        return

    if isinstance(value, str):
        yield path, value
        return

    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            yield from _iter_strings(child, child_path, key_name=key_text)
        return

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            yield from _iter_strings(child, f"{path}[{index}]")


def _normalize_claim(text: str) -> str:
    return " ".join(text.lower().split())


def _is_negated_or_denied(text: str, start: int, end: int) -> bool:
    """Return True when nearby language negates an authority-like phrase."""

    prefix = text[max(0, start - 40):start].lower()
    # Keep the check local to the current clause/sentence so earlier unrelated
    # denials do not suppress a later affirmative claim.
    prefix = re.split(r"[.;:!?\n]", prefix)[-1]
    # "No blockers" is itself an affirmative blocker-closure claim, not a
    # negator for subsequent approval/scope claims in the same sentence.
    prefix = re.sub(r"\bno\s+blockers?\b", "", prefix)
    prefix_negated = bool(
        re.search(
            r"\b(?:not|never|no|without|pending|denied|deny|denies|doesn['’]?t|do\s+not|cannot|can't|isn['’]?t|wasn['’]?t|aren['’]?t|weren['’]?t|won['’]?t)\b",
            prefix,
        )
    )
    if prefix_negated:
        return True

    claim_text = text[start:end].lower()
    suffix = re.split(r"[.;:!?\n]", text[end:end + 40].lower())[0]
    if "signoff" in claim_text or "sign off" in claim_text or "sign-off" in claim_text:
        return bool(
            re.search(
                r"\b(?:pending|not|denied|wasn['’]?t|isn['’]?t|aren['’]?t|received\s+not)\b",
                suffix,
            )
        )
    return False


def _claim_id(
    *,
    source_ref: str | None,
    source_path: str,
    claim_type: str,
    start: int,
    end: int,
    normalized_claim: str,
) -> str:
    raw = "\x1f".join(
        [
            source_ref or "",
            source_path,
            claim_type,
            str(start),
            str(end),
            normalized_claim,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


__all__ = ["detect_authority_claims"]
