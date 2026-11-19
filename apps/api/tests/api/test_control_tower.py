"""Plug any AI: external vendors, champion vs shadow, unbiased scoring, privacy."""

from datetime import datetime
from typing import Any

from httpx import AsyncClient

from tests.conftest import login
from tri_mesure.llm.rules_provider import classify


async def _setup(client: AsyncClient) -> dict[str, Any]:
    h = {
        "g": await login(client, "gestionnaire", "sophie"),
        "a": await login(client, "auditeur", "paul"),
        "ia": await login(client, "equipe_ia", "lucas"),
    }
    await client.post("/api/admin/seed", headers=h["g"])
    await client.post("/api/ai/process", headers=h["ia"])
    r = await client.post("/api/ai/sources", headers=h["ia"], json={"name": "Fournisseur B"})
    assert r.status_code == 200, r.text
    return {"h": h, "code": r.json()["code"], "key": {"X-API-Key": r.json()["api_key"]}}


def _proposal(case: dict[str, Any], **override: Any) -> dict[str, Any]:
    p = classify(case["body"], datetime.fromisoformat(case["received_at"]).date()).model_dump()
    return p | {"model": "vendor-b-1", "latency_ms": 120} | override


async def test_only_the_ai_team_plugs_vendors_and_keys_are_checked(client: AsyncClient) -> None:
    g = await login(client, "gestionnaire", "sophie")
    assert (await client.post("/api/ai/sources", headers=g, json={"name": "X"})).status_code == 403
    r = await client.get("/api/ingest/cases", headers={"X-API-Key": "tm_forged"})
    assert r.status_code == 401
    assert (await client.get("/api/ingest/cases")).status_code == 401


async def test_vendors_receive_masked_text_only(client: AsyncClient) -> None:
    t = await _setup(client)
    cases = (await client.get("/api/ingest/cases", headers=t["key"])).json()
    assert len(cases) == 50  # default page
    blob = " ".join(c["subject"] + c["body"] for c in cases)
    assert "<CONTRAT_" in blob and "<TELEPHONE_" in blob
    assert "@" not in blob  # no e-mail addresses
    assert not any(tok in blob for tok in ("CT1", "CT2", "CT3", "CT4", "CT5", "CT6", "CT7"))


async def test_shadow_then_champion(client: AsyncClient) -> None:
    t = await _setup(client)
    h = t["h"]
    queue = (await client.get("/api/cases", headers=h["g"])).json()
    ai_case_id = next(c["id"] for c in queue if c["arm"] == "ai")
    cases = (await client.get("/api/ingest/cases?limit=200", headers=t["key"])).json()
    case = next(c for c in cases if c["id"] == ai_case_id)

    # 1. shadow: the vendor proposes, handlers still see the internal pipeline
    r = await client.post(
        f"/api/ingest/cases/{ai_case_id}/suggestion",
        headers=t["key"],
        json=_proposal(case, category="autre", confidence=0.9),
    )
    assert r.json()["mode"] == "shadow"
    d = (await client.get(f"/api/cases/{ai_case_id}", headers=h["g"])).json()
    assert d["suggestion"]["source"] == "interne"
    # a vendor cannot answer twice
    r = await client.post(
        f"/api/ingest/cases/{ai_case_id}/suggestion", headers=t["key"], json=_proposal(case)
    )
    assert r.status_code == 409

    # 2. promote the vendor: handlers now see its proposal, and decisions are attributed to it
    r = await client.put("/api/ai/champion", headers=h["ia"], json={"source": t["code"]})
    assert r.status_code == 200
    d = (await client.post(f"/api/cases/{ai_case_id}/claim", headers=h["g"])).json()
    assert d["suggestion"]["source"] == t["code"] and d["suggestion"]["category"] == "autre"
    r = await client.post(
        f"/api/cases/{ai_case_id}/review",
        headers=h["g"],
        json={
            "category": {"verdict": "accepted", "value": "autre"},
            "seconds_to_decision": 20,
        },
    )
    assert r.status_code == 200
    board = {s["code"]: s for s in (await client.get("/api/ai/sources", headers=h["ia"])).json()}
    assert board[t["code"]]["champion"] is True
    assert board[t["code"]]["shown_to_handlers"] == 1
    assert board["interne"]["shown_to_handlers"] == 0
    # the champion cannot be switched off
    r = await client.put(f"/api/ai/sources/{t['code']}", headers=h["ia"], json={"active": False})
    assert r.status_code == 409
    # every change is in the audit log
    types = {e["type"] for e in (await client.get("/api/audit?limit=500", headers=h["a"])).json()}
    assert {"source.created", "champion.changed"} <= types


async def test_unbiased_score_uses_control_arm_cases(client: AsyncClient) -> None:
    t = await _setup(client)
    h = t["h"]
    queue = (await client.get("/api/cases", headers=h["g"])).json()
    ctrl = next(c for c in queue if c["arm"] == "control")
    cases = {
        c["id"]: c
        for c in (await client.get("/api/ingest/cases?limit=200", headers=t["key"])).json()
    }
    proposal = _proposal(cases[ctrl["id"]])
    await client.post(f"/api/ingest/cases/{ctrl['id']}/suggestion", headers=t["key"], json=proposal)
    # the handler decides without seeing any AI
    await client.post(f"/api/cases/{ctrl['id']}/claim", headers=h["g"])
    await client.post(
        f"/api/cases/{ctrl['id']}/review",
        headers=h["g"],
        json={
            "category": {"verdict": "manual_entry", "value": proposal["category"]},
            "seconds_to_decision": 50,
        },
    )
    board = {s["code"]: s for s in (await client.get("/api/ai/sources", headers=h["ia"])).json()}
    vendor = board[t["code"]]
    assert vendor["unbiased_cases"] == 1 and vendor["category_agreement_unbiased"] == 1.0
    # a closed case no longer accepts proposals
    r = await client.post(
        f"/api/ingest/cases/{ctrl['id']}/suggestion", headers=t["key"], json=proposal
    )
    assert r.status_code == 409


async def test_vendor_placeholders_are_mapped_back_server_side(client: AsyncClient) -> None:
    t = await _setup(client)
    cases = (await client.get("/api/ingest/cases?limit=200", headers=t["key"])).json()
    case = next(c for c in cases if "<CONTRAT_1>" in c["body"])
    p = _proposal(case)
    p["fields"]["numero_contrat"] = "<CONTRAT_1>"
    await client.post(f"/api/ingest/cases/{case['id']}/suggestion", headers=t["key"], json=p)
    await client.put("/api/ai/champion", headers=t["h"]["ia"], json={"source": t["code"]})
    d = (await client.get(f"/api/cases/{case['id']}", headers=t["h"]["g"])).json()
    if d["suggestion"] is not None:  # AI arm: visible now
        assert d["suggestion"]["fields"]["numero_contrat"].startswith("CT")
