"""Tamper-evident audit chain.

Each event stores the hash of the previous event; its own hash covers the previous hash and
a canonical JSON form of its content. Changing or deleting any past event breaks every hash
after it, which `verify()` detects. The database also refuses UPDATE and DELETE on the
audit table (see the Alembic migration), so tampering needs both bypassing the database
rule *and* recomputing the whole chain.
"""

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

GENESIS_HASH = "0" * 64


def canonical_json(data: Mapping[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def event_hash(prev_hash: str, content: Mapping[str, Any]) -> str:
    return hashlib.sha256((prev_hash + canonical_json(content)).encode("utf-8")).hexdigest()


def event_content(
    seq: int, ts: str, actor: str, event_type: str, email_id: int | None, payload: Mapping[str, Any]
) -> dict[str, Any]:
    """The exact fields covered by the hash. Keep in sync with the AuditEvent model."""
    return {
        "seq": seq,
        "ts": ts,
        "actor": actor,
        "type": event_type,
        "email_id": email_id,
        "payload": dict(payload),
    }


@dataclass(frozen=True)
class ChainReport:
    ok: bool
    checked: int
    first_broken_seq: int | None = None
    reason: str | None = None


def verify(events: Iterable[tuple[dict[str, Any], str, str]]) -> ChainReport:
    """Verify (content, prev_hash, hash) triples in sequence order."""
    expected_prev = GENESIS_HASH
    checked = 0
    for content, prev_hash, stored_hash in events:
        seq = int(content["seq"])
        if prev_hash != expected_prev:
            return ChainReport(False, checked, seq, "Lien rompu avec l'événement précédent")
        if event_hash(prev_hash, content) != stored_hash:
            return ChainReport(False, checked, seq, "Contenu modifié (empreinte invalide)")
        expected_prev = stored_hash
        checked += 1
    return ChainReport(True, checked)
