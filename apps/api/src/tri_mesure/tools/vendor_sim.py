"""Simulated external AI vendor: proves that any AI can plug in with an API key only.

It talks to Tri & Mesure exactly like a real vendor would (HTTP + X-API-Key), receives
masked text only, and posts proposals in the shared schema.

Engines:
  rules  — keyword rules (free); --noise makes it deliberately worse, to demo drift alerts
  groq   — Llama on Groq's free tier through the OpenAI-compatible adapter (needs a key)

Examples:
  python -m tri_mesure.tools.vendor_sim --key tm_xxx
  python -m tri_mesure.tools.vendor_sim --key tm_xxx --engine groq --loop
  python -m tri_mesure.tools.vendor_sim --key tm_xxx --noise 0.4 --name "Fournisseur B"
"""

import argparse
import asyncio
import random
import sys
import time
from datetime import datetime
from typing import Any

import httpx

from tri_mesure.domain.taxonomy import CATEGORIES
from tri_mesure.llm.gateway import build_user_message
from tri_mesure.llm.prompts import load_system_prompt
from tri_mesure.llm.rules_provider import classify


def _degrade(proposal: dict[str, Any], rng: random.Random, noise: float) -> dict[str, Any]:
    """Make a worse vendor on purpose: wrong category, missing or wrong fields."""
    if rng.random() < noise:
        others = [c for c in CATEGORIES if c != proposal["category"]]
        proposal["category"] = rng.choice(others)
        proposal["confidence"] = round(rng.uniform(0.6, 0.95), 2)  # confidently wrong
    for name in list(proposal["fields"]):
        if proposal["fields"][name] is not None and rng.random() < noise / 2:
            proposal["fields"][name] = None
    proposal["evidence"] = [e for e in proposal["evidence"] if proposal["fields"].get(e["field"])]
    return proposal


async def _propose_rules(case: dict[str, Any]) -> tuple[dict[str, Any], str]:
    received = datetime.fromisoformat(case["received_at"]).date()
    return classify(case["body"], received).model_dump(), "vendor-rules-v1"


async def _propose_groq(case: dict[str, Any]) -> tuple[dict[str, Any], str]:
    from tri_mesure.llm.base import Prompt
    from tri_mesure.llm.openai_compat_provider import OpenAICompatProvider
    from tri_mesure.settings import get_settings

    s = get_settings()
    provider = OpenAICompatProvider(
        s.openai_compat_model, s.openai_compat_base_url, s.openai_compat_api_key
    )
    received = datetime.fromisoformat(case["received_at"]).date()
    prompt = Prompt(
        "v1", load_system_prompt("v1"), build_user_message(case["subject"], case["body"], received)
    )
    result = await provider.extract(prompt)
    if result.extraction is None:
        raise RuntimeError(result.error or "no extraction")
    return result.extraction.model_dump(), provider.model


async def run_once(client: httpx.AsyncClient, engine: str, noise: float, seed: int) -> int:
    r = await client.get("/api/ingest/cases", params={"limit": 50})
    r.raise_for_status()
    cases = r.json()
    sent = 0
    for case in cases:
        started = time.perf_counter()
        try:
            proposal, model = await (
                _propose_groq(case) if engine == "groq" else _propose_rules(case)
            )
        except Exception as e:  # a vendor failing on one case must not stop the batch
            print(f"  case {case['id']}: engine error {e}", file=sys.stderr)
            continue
        proposal = _degrade(proposal, random.Random(seed * 100_003 + case["id"]), noise)
        proposal |= {"model": model, "latency_ms": int((time.perf_counter() - started) * 1000)}
        resp = await client.post(f"/api/ingest/cases/{case['id']}/suggestion", json=proposal)
        if resp.status_code == 200:
            sent += 1
        elif resp.status_code != 409:  # 409 = case closed meanwhile or already answered
            print(
                f"  case {case['id']}: HTTP {resp.status_code} {resp.text[:120]}", file=sys.stderr
            )
    return sent


async def main_async(args: argparse.Namespace) -> None:
    headers = {"X-API-Key": args.key}
    async with httpx.AsyncClient(base_url=args.url, headers=headers, timeout=60) as client:
        while True:
            sent = await run_once(client, args.engine, args.noise, args.seed)
            print(f"[{args.name}] {sent} proposition(s) envoyée(s)")
            if not args.loop:
                break
            await asyncio.sleep(args.every)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Simulated external AI vendor")
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--key", required=True, help="API key shown when the source was created")
    p.add_argument("--engine", choices=["rules", "groq"], default="rules")
    p.add_argument("--noise", type=float, default=0.0, help="0..1 — how often it is wrong")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--name", default="Fournisseur simulé")
    p.add_argument("--loop", action="store_true", help="keep polling for new cases")
    p.add_argument("--every", type=float, default=5.0, help="seconds between polls")
    asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    main()
