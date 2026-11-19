"""Storm mode, drift alerts and the oversight report."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import update

from tests.conftest import login
from tri_mesure.db.models import Email
from tri_mesure.db.session import get_sessionmaker


async def _roles(client: AsyncClient) -> dict[str, dict[str, str]]:
    return {
        "g": await login(client, "gestionnaire", "sophie"),
        "r": await login(client, "responsable", "ines"),
        "a": await login(client, "auditeur", "paul"),
        "ia": await login(client, "equipe_ia", "lucas"),
    }


async def test_storm_mode_floods_the_queue_and_is_followed_live(client: AsyncClient) -> None:
    h = await _roles(client)
    storm = {"name": "Grêle sur Toulouse", "kind": "grele", "volume": 30}
    assert (await client.post("/api/crisis", headers=h["g"], json=storm)).status_code == 403

    r = await client.post("/api/crisis", headers=h["r"], json=storm)
    assert r.status_code == 200, r.text
    event = r.json()
    assert event["received"] == 30 and event["waiting_analysis"] == 30
    assert (await client.post("/api/crisis", headers=h["r"], json=storm)).status_code == 409

    await client.post("/api/ai/process", headers=h["ia"])
    queue = (await client.get("/api/cases", headers=h["g"])).json()
    assert sum(1 for c in queue if c["event_id"] == event["id"]) == 30
    live = (await client.get("/api/crisis", headers=h["r"])).json()
    assert live["waiting_analysis"] == 0 and live["open"] == 30

    r = await client.post(f"/api/crisis/{event['id']}/end", headers=h["r"])
    assert r.json()["ended_at"] is not None
    assert (await client.get("/api/crisis", headers=h["r"])).json() is None
    types = [e["type"] for e in (await client.get("/api/audit?limit=500", headers=h["a"])).json()]
    assert "crisis.started" in types and "crisis.ended" in types


async def _review_ai_cases(
    client: AsyncClient, h: dict[str, dict[str, str]], n: int, change_category: bool
) -> None:
    queue = (await client.get("/api/cases", headers=h["g"])).json()
    todo = [c for c in queue if c["arm"] == "ai" and c["status"] == "nouveau"][:n]
    for c in todo:
        d: dict[str, Any] = (
            await client.post(f"/api/cases/{c['id']}/claim", headers=h["g"])
        ).json()
        cat = d["suggestion"]["category"]
        value = ("autre" if cat != "autre" else "reclamation") if change_category else cat
        verdict = "edited" if change_category else "accepted"
        r = await client.post(
            f"/api/cases/{c['id']}/review",
            headers=h["g"],
            json={
                "category": {"verdict": verdict, "value": value},
                "seconds_to_decision": 25,
            },
        )
        assert r.status_code == 200, r.text


async def test_drift_alert_fires_when_handlers_start_correcting(client: AsyncClient) -> None:
    h = await _roles(client)
    await client.post("/api/admin/seed", headers=h["g"])
    await client.post("/api/ai/process", headers=h["ia"])
    assert (await client.get("/api/ai/alerts", headers=h["ia"])).json() == []

    await _review_ai_cases(client, h, 10, change_category=False)  # baseline: all accepted
    await _review_ai_cases(client, h, 10, change_category=True)  # then: all corrected
    alerts = (await client.get("/api/ai/alerts", headers=h["ia"])).json()
    assert alerts[0]["code"] == "drift.category" and alerts[0]["severity"] == "critique"
    assert "0%" in alerts[0]["detail"] and "100%" in alerts[0]["detail"]


async def test_failed_analyses_raise_an_operational_alert(client: AsyncClient) -> None:
    h = await _roles(client)
    await client.post("/api/admin/seed", headers=h["g"])
    async with get_sessionmaker()() as session:
        await session.execute(update(Email).where(Email.id <= 3).values(analysis_status="failed"))
        await session.commit()
    codes = {a["code"] for a in (await client.get("/api/ai/alerts", headers=h["ia"])).json()}
    assert "ops.failed" in codes


async def test_oversight_report_is_sealed_and_audited(client: AsyncClient) -> None:
    h = await _roles(client)
    await client.post("/api/admin/seed", headers=h["g"])
    await client.post("/api/ai/process", headers=h["ia"])
    await _review_ai_cases(client, h, 3, change_category=False)
    assert (await client.get("/api/audit/report", headers=h["g"])).status_code == 403

    rep = (await client.get("/api/audit/report?days=7", headers=h["a"])).json()
    assert rep["decisions"]["total"] == 3
    assert rep["decisions"]["by_authenticated_human"] == 3
    assert rep["integrity"]["chain_ok"] is True and len(rep["integrity"]["seal_hash"]) == 64
    assert rep["ai_systems"]["suggestions_by_system"]
    assert "Aucune décision" in rep["statement"]
    last = (await client.get("/api/audit?limit=1", headers=h["a"])).json()[0]
    assert last["type"] == "report.generated" and last["actor"] == "human:paul (auditeur)"
