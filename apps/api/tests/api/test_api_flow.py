"""End-to-end API behaviour, role by role."""

from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import login


async def _seed_and_analyse(client: AsyncClient) -> dict[str, dict[str, str]]:
    h = {
        "g": await login(client, "gestionnaire", "sophie"),
        "g2": await login(client, "gestionnaire", "karim"),
        "r": await login(client, "responsable", "ines"),
        "a": await login(client, "auditeur", "paul"),
        "ia": await login(client, "equipe_ia", "lucas"),
    }
    r = await client.post("/api/admin/seed", headers=h["g"])
    assert r.status_code == 200, r.text
    assert r.json() == {"created": 80, "skipped": 0, "queued_for_analysis": 80}
    r = await client.post("/api/ai/process", headers=h["ia"])
    assert r.json() == {"count": 80}
    return h


def _accept_all(detail: dict[str, Any]) -> dict[str, Any]:
    s = detail["suggestion"]
    return {
        "category": {"verdict": "accepted", "value": s["category"]},
        "fields": {
            k: {"verdict": "accepted", "value": v} for k, v in s["fields"].items() if v is not None
        },
        "seconds_to_decision": 31.5,
    }


async def _first(client: AsyncClient, h: dict[str, str], arm: str) -> dict[str, Any]:
    cases = (await client.get("/api/cases", headers=h)).json()
    return next(c for c in cases if c["arm"] == arm and c["status"] == "nouveau")


# --- system & security ------------------------------------------------------------------


async def test_health_and_metrics_endpoints(client: AsyncClient) -> None:
    assert (await client.get("/api/health/live")).json() == {"status": "ok"}
    ready = (await client.get("/api/health")).json()
    assert ready["database"] is True and ready["worker"] == "disabled"
    r = await client.get("/api/ops/metrics")
    assert "tm_http_requests_total" in r.text


async def test_unauthenticated_request_gets_problem_details(client: AsyncClient) -> None:
    r = await client.get("/api/cases", headers={"X-Request-ID": "abc123"})
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["status"] == 401 and body["request_id"] == "abc123"
    assert r.headers["X-Request-ID"] == "abc123"


async def test_roles_are_public_and_tokens_are_checked(client: AsyncClient) -> None:
    roles = (await client.get("/api/auth/roles")).json()
    assert {r["code"] for r in roles} == {"gestionnaire", "responsable", "auditeur", "equipe_ia"}
    h = await login(client, "auditeur", "paul")
    me = (await client.get("/api/auth/me", headers=h)).json()
    assert me["role_label"] == "Auditeur conformité" and "audit.read" in me["permissions"]
    bad = await client.get("/api/auth/me", headers={"Authorization": "Bearer forged"})
    assert bad.status_code == 401


async def test_each_role_only_reaches_its_own_screens(client: AsyncClient) -> None:
    h = await _seed_and_analyse(client)
    assert (await client.get("/api/pilotage", headers=h["g"])).status_code == 403
    assert (await client.get("/api/audit", headers=h["r"])).status_code == 403
    assert (
        await client.put("/api/ai/config", headers=h["a"], json={"provider": "rules"})
    ).status_code == 403
    case = await _first(client, h["g"], "ai")
    r = await client.post(f"/api/cases/{case['id']}/claim", headers=h["r"])
    assert r.status_code == 403
    assert "Responsable d'équipe" in r.json()["detail"]


# --- the handler's journey ---------------------------------------------------------------


async def test_queue_after_analysis(client: AsyncClient) -> None:
    h = await _seed_and_analyse(client)
    cases = (await client.get("/api/cases", headers=h["g"])).json()
    assert all(c["analysis_status"] == "done" for c in cases)
    assert all(c["category"] is None for c in cases if c["arm"] == "control")
    order = {"urgente": 0, "haute": 1, "normale": 2, "basse": 3}
    ranks = [order[c["priority"] or "normale"] for c in cases]
    assert ranks == sorted(ranks)
    assert {c["sla"]["state"] for c in cases} <= {"ok", "bientot", "en_retard"}


async def test_take_decide_close_with_audit_trail(client: AsyncClient) -> None:
    h = await _seed_and_analyse(client)
    nxt = (await client.get("/api/cases/next", headers=h["g"])).json()["id"]
    assert nxt is not None

    detail = (await client.post(f"/api/cases/{nxt}/claim", headers=h["g"])).json()
    assert detail["holder"] == "sophie"
    # someone else cannot take it nor decide on it
    assert (await client.post(f"/api/cases/{nxt}/claim", headers=h["g2"])).status_code == 409
    payload = _accept_all(detail)
    payload["category"] = {"verdict": "edited", "value": "autre"}
    assert (
        await client.post(f"/api/cases/{nxt}/review", headers=h["g2"], json=payload)
    ).status_code == 409

    r = await client.post(f"/api/cases/{nxt}/review", headers=h["g"], json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["reviewer"] == "sophie" and r.json()["diff"]["category"]["to"] == "autre"
    assert (
        await client.post(f"/api/cases/{nxt}/review", headers=h["g"], json=payload)
    ).status_code == 409

    events = (await client.get(f"/api/audit?email_id={nxt}", headers=h["a"])).json()
    types = [e["type"] for e in reversed(events)]
    assert types[:5] == [
        "email.received",
        "pii.masked",
        "ai.suggested",
        "priority.computed",
        "case.claimed",
    ]
    assert "human.edited" in types and types[-1] == "case.closed"
    actors = {e["actor"] for e in events}
    assert "human:sophie (gestionnaire)" in actors and "system:rules" in actors
    assert (await client.get("/api/audit/verify", headers=h["a"])).json()["ok"] is True


async def test_reject_requires_a_reason(client: AsyncClient) -> None:
    h = await _seed_and_analyse(client)
    case = await _first(client, h["g"], "ai")
    detail = (await client.post(f"/api/cases/{case['id']}/claim", headers=h["g"])).json()
    payload = _accept_all(detail)
    payload["category"] = {"verdict": "rejected", "value": "autre"}
    r = await client.post(f"/api/cases/{case['id']}/review", headers=h["g"], json=payload)
    assert r.status_code == 422 and "motif" in r.json()["detail"]
    payload["reason_code"] = "mauvaise_categorie"
    r = await client.post(f"/api/cases/{case['id']}/review", headers=h["g"], json=payload)
    assert r.status_code == 200


async def test_release_gives_the_case_back(client: AsyncClient) -> None:
    h = await _seed_and_analyse(client)
    case = await _first(client, h["g"], "ai")
    await client.post(f"/api/cases/{case['id']}/claim", headers=h["g"])
    assert (
        await client.post(f"/api/cases/{case['id']}/release", headers=h["g"])
    ).status_code == 204
    assert (await client.post(f"/api/cases/{case['id']}/claim", headers=h["g2"])).status_code == 200


async def test_control_arm_hides_ai_until_closed(client: AsyncClient) -> None:
    h = await _seed_and_analyse(client)
    ctrl = await _first(client, h["g"], "control")
    d = (await client.post(f"/api/cases/{ctrl['id']}/claim", headers=h["g"])).json()
    assert d["suggestion"] is None and d["llm_calls"] == []
    r = await client.post(
        f"/api/cases/{ctrl['id']}/review",
        headers=h["g"],
        json={
            "category": {"verdict": "manual_entry", "value": "reclamation"},
            "seconds_to_decision": 60,
        },
    )
    assert r.status_code == 200
    d = (await client.get(f"/api/cases/{ctrl['id']}", headers=h["g"])).json()
    assert d["suggestion"] is not None


# --- manager, AI team, auditor -------------------------------------------------------


async def test_pilotage_measures_the_gain_with_a_control_arm(client: AsyncClient) -> None:
    h = await _seed_and_analyse(client)
    cases = (await client.get("/api/cases", headers=h["g"])).json()
    for c in [x for x in cases if x["arm"] == "ai"][:5]:
        d = (await client.post(f"/api/cases/{c['id']}/claim", headers=h["g"])).json()
        p = _accept_all(d)
        p["seconds_to_decision"] = 30
        assert (
            await client.post(f"/api/cases/{c['id']}/review", headers=h["g"], json=p)
        ).status_code == 200
    for c in [x for x in cases if x["arm"] == "control"][:5]:
        await client.post(f"/api/cases/{c['id']}/claim", headers=h["g"])
        await client.post(
            f"/api/cases/{c['id']}/review",
            headers=h["g"],
            json={
                "category": {"verdict": "manual_entry", "value": "autre"},
                "seconds_to_decision": 90,
            },
        )
    p = (await client.get("/api/pilotage", headers=h["r"])).json()
    assert p["stock"]["open"] == 70
    assert p["flow"]["closed_today"] == 10
    assert p["ai_value"]["enough_data"] is True
    assert p["ai_value"]["seconds_saved_per_case"] == 60
    assert p["ai_value"]["accepted_as_is_rate"] == 1.0
    assert "individuel" in p["privacy_note"]

    q = (await client.get("/api/ai/quality", headers=h["ia"])).json()
    assert q["reviews"] == 5 and q["per_item"]["category"]["accepted"] == 5


async def test_config_change_is_validated_and_audited(client: AsyncClient) -> None:
    h = await _seed_and_analyse(client)
    r = await client.put(
        "/api/ai/config",
        headers=h["ia"],
        json={"provider": "anthropic", "model": "claude-haiku-5-5"},
    )
    assert r.status_code == 422 and "clé" in r.json()["detail"]
    r = await client.put(
        "/api/ai/config", headers=h["ia"], json={"provider": "rules", "prompt_version": "v1"}
    )
    assert r.status_code == 200 and r.json()["overridden"] is True
    events = (await client.get("/api/audit?type=config.changed", headers=h["a"])).json()
    assert len(events) == 1 and events[0]["actor"] == "human:lucas (equipe_ia)"
    assert (await client.post("/api/ai/reanalyze-open", headers=h["ia"])).json()["count"] == 80


async def test_eval_run_from_the_ai_screen(client: AsyncClient) -> None:
    h = {"ia": await login(client, "equipe_ia", "lucas")}
    r = await client.post(
        "/api/ai/eval-runs", headers=h["ia"], json={"provider": "rules", "dataset": "ci"}
    )
    assert r.status_code == 200
    runs = (await client.get("/api/ai/eval-runs", headers=h["ia"])).json()
    assert runs[0]["status"] == "done" and runs[0]["summary"]["n"] == 30


async def test_processing_register_for_the_auditor(client: AsyncClient) -> None:
    h = await _seed_and_analyse(client)
    reg = (await client.get("/api/audit/register", headers=h["a"])).json()
    assert reg["audit"]["chain_ok"] is True
    assert reg["minimisation"]["masked_entities_total"]["CONTRAT"] > 0
    assert reg["recipients"]["model_providers_used"] == ["rules"]


async def test_audit_pagination_and_filters(client: AsyncClient) -> None:
    h = await _seed_and_analyse(client)
    page1 = (await client.get("/api/audit?limit=10", headers=h["a"])).json()
    assert len(page1) == 10
    page2 = (
        await client.get(f"/api/audit?limit=10&before_seq={page1[-1]['seq']}", headers=h["a"])
    ).json()
    assert page2[0]["seq"] == page1[-1]["seq"] - 1
    ai_only = (await client.get("/api/audit?actor_kind=ai&limit=500", headers=h["a"])).json()
    assert ai_only and all(e["actor"].startswith("ai:") for e in ai_only)


async def test_a_broken_log_stream_never_breaks_requests(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: an API process whose stdout pipe was closed answered 500 to everything."""
    from tri_mesure.api import middleware

    def broken(*args: object, **kwargs: object) -> None:
        raise OSError(22, "Invalid argument")  # what Windows raises on a dead pipe

    monkeypatch.setattr(middleware.log, "info", broken)
    r = await client.get("/api/auth/roles")
    assert r.status_code == 200
    r = await client.post("/api/auth/demo-login", json={"name": "Sophie", "role": "gestionnaire"})
    assert r.status_code == 200


async def test_workspace_context_for_the_handler(client: AsyncClient) -> None:
    h = await _seed_and_analyse(client)
    pb = (
        await client.get(
            "/api/playbook?category=declaration_sinistre&type_dommage=degat_des_eaux&fuite_active=true",
            headers=h["g"],
        )
    ).json()
    assert pb["steps"][0]["urgent"] and any("IRSI" in f["name"] for f in pb["frames"])
    pol = (
        await client.get("/api/policies/CT12345678?damage=degat_des_eaux", headers=h["g"])
    ).json()
    assert pol["simulated"] is True and pol["covers_damage"] is True

    ctrl = await _first(client, h["g"], "control")
    tl = (await client.get(f"/api/cases/{ctrl['id']}/timeline", headers=h["g"])).json()
    types = {e["type"] for e in tl}
    assert "email.received" in types
    assert "ai.suggested" not in types  # the control arm never leaks the AI's proposal
    rel = await client.get(f"/api/cases/{ctrl['id']}/related", headers=h["g"])
    assert rel.status_code == 200
