"""Run a labelled dataset through the full pipeline and score it.

Examples:
  python -m tri_mesure.evaluation.run_eval --provider rules --dataset ci --min-macro-f1 0.6
  python -m tri_mesure.evaluation.run_eval --provider anthropic --model claude-haiku-5-5

Exits with code 1 when --min-macro-f1 is given and not reached (CI gate).
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from tri_mesure.domain.taxonomy import CATEGORIES
from tri_mesure.evaluation.metrics import EvalReport
from tri_mesure.llm.gateway import Gateway, make_provider
from tri_mesure.llm.prompts import DEFAULT_VERSION
from tri_mesure.pipeline import suggest
from tri_mesure.settings import REPO_ROOT, get_settings


def load_dataset(name_or_path: str) -> list[dict[str, Any]]:
    path = Path(name_or_path)
    if not path.suffix:
        path = REPO_ROOT / "data" / "gold" / f"{name_or_path}.jsonl"
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


async def evaluate(
    samples: list[dict[str, Any]], gateway: Gateway, concurrency: int = 4
) -> EvalReport:
    report = EvalReport()
    sem = asyncio.Semaphore(concurrency)

    async def one(sample: dict[str, Any]) -> None:
        async with sem:
            received = datetime.fromisoformat(sample["received_at"]).date()
            s = await suggest(gateway, sample["subject"], sample["body"], received)
        extraction = s.outcome.extraction
        assert extraction is not None
        report.add(sample["expected"], extraction.category, extraction.sender_type, s.fields)
        if not s.outcome.used_fallback:
            report.schema_valid += 1
        else:
            report.fallbacks += 1
        if s.needs_manual:
            report.manual += 1
        report.cost_eur += s.outcome.total_cost_eur
        report.latencies_ms.append(sum(a.result.latency_ms for a in s.outcome.attempts))
        for a in s.outcome.attempts:
            report.input_tokens += a.result.usage.input_tokens
            report.output_tokens += a.result.usage.output_tokens
            report.cache_read_tokens += a.result.usage.cache_read_tokens
            if a.result.error:
                report.errors.append({"id": sample["id"], "error": a.result.error})
        if extraction.category != sample["expected"]["category"]:
            report.errors.append(
                {
                    "id": sample["id"],
                    "expected": sample["expected"]["category"],
                    "predicted": extraction.category,
                }
            )

    await asyncio.gather(*(one(s) for s in samples))
    return report


def print_report(report: EvalReport, label: str) -> None:
    s = report.summary()
    print(f"\n=== {label} ===")
    print(
        f"n={s['n']}  accuracy={s['accuracy']:.3f}  macro-F1={s['macro_f1']:.3f}  "
        f"fields micro-F1={s['field_micro_f1']:.3f}  sender acc={s['sender_accuracy']:.3f}"
    )
    print(
        f"schema-valid={s['schema_valid_rate']:.1%}  fallback={s['fallback_rate']:.1%}  "
        f"manual={s['manual_rate']:.1%}"
    )
    print(
        f"cost={s['cost_eur_total']:.4f} €  ({s['cost_eur_per_email'] * 1000:.3f} € / 1000 e-mails)"
        f"  latency p50={s['latency_p50_ms']} ms p95={s['latency_p95_ms']} ms"
    )
    print("\nper category            P      R      F1   (support)")
    for c in CATEGORIES:
        m = report.category[c]
        support = m.tp + m.fn
        if support or m.fp:
            print(f"  {c:<26}{m.precision:6.2f} {m.recall:6.2f} {m.f1:6.2f}   ({support})")
    print("\nper field               P      R      F1")
    for name, m in report.fields.items():
        if m.tp + m.fp + m.fn:
            print(f"  {name:<22}{m.precision:6.2f} {m.recall:6.2f} {m.f1:6.2f}")


async def amain() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a provider on a labelled dataset")
    parser.add_argument("--provider", default=None, help="rules | anthropic | openai_compat")
    parser.add_argument("--model", default=None)
    parser.add_argument("--dataset", default="test", help="dev | test | ci | demo | path")
    parser.add_argument("--prompt-version", default=DEFAULT_VERSION)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--min-macro-f1", type=float, default=None)
    parser.add_argument("--json", type=Path, default=None, help="write the full report here")
    args = parser.parse_args()

    settings = get_settings()
    provider = make_provider(settings, args.provider, args.model)
    gateway = Gateway(
        provider,
        usd_to_eur=settings.usd_to_eur,
        daily_budget_eur=settings.daily_budget_eur,
        prompt_version=args.prompt_version,
    )
    samples = load_dataset(args.dataset)
    if args.limit:
        samples = samples[: args.limit]

    report = await evaluate(samples, gateway, args.concurrency)
    label = f"{provider.name}/{provider.model} · prompt {args.prompt_version} · {args.dataset}"
    print_report(report, label)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "provider": provider.name,
            "model": provider.model,
            "prompt_version": args.prompt_version,
            "dataset": args.dataset,
            **report.to_dict(),
        }
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.min_macro_f1 is not None and report.macro_f1 < args.min_macro_f1:
        print(f"\nFAIL: macro-F1 {report.macro_f1:.3f} < threshold {args.min_macro_f1:.3f}")
        return 1
    return 0


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(amain()))


if __name__ == "__main__":
    main()
