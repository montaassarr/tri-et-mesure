from typing import Any

from tri_mesure.audit.chain import GENESIS_HASH, event_content, event_hash, verify


def _build(n: int) -> list[tuple[dict[str, Any], str, str]]:
    events = []
    prev = GENESIS_HASH
    for i in range(1, n + 1):
        content = event_content(i, f"2026-11-18T10:00:0{i}", "ai", "ai.suggested", 1, {"i": i})
        h = event_hash(prev, content)
        events.append((content, prev, h))
        prev = h
    return events


def test_valid_chain_verifies() -> None:
    report = verify(_build(5))
    assert report.ok
    assert report.checked == 5


def test_modified_payload_is_detected() -> None:
    events = _build(5)
    content, prev, h = events[2]
    events[2] = ({**content, "payload": {"i": 999}}, prev, h)
    report = verify(events)
    assert not report.ok
    assert report.first_broken_seq == 3


def test_deleted_event_is_detected() -> None:
    events = _build(5)
    del events[1]
    report = verify(events)
    assert not report.ok
    assert report.first_broken_seq == 3


def test_hash_is_key_order_independent() -> None:
    a = event_hash(GENESIS_HASH, {"b": 1, "a": 2})
    b = event_hash(GENESIS_HASH, {"a": 2, "b": 1})
    assert a == b
