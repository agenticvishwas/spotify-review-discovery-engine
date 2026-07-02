"""Evaluation runner for Phase 3 prompt quality.

Runs the LLM extraction pipeline against a hand-labeled dataset and
reports accuracy against defined thresholds. Must pass before any prompt
version bump is promoted to production.

Usage:
    python run_eval.py
    python run_eval.py --dataset eval_dataset.jsonl
    python run_eval.py --prompt-version 1.2 --api-key sk-ant-...
    python run_eval.py --output-dir eval_reports/
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzers.llm_client import LLMClient
from analyzers.response_validator import ResponseValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("phase3.eval")

THRESHOLDS = {
    "sentiment_accuracy": 0.85,
    "discovery_friction_f1": 0.80,
    "feature_mention_precision": 0.90,
    "schema_compliance": 1.0,
    "avg_confidence_score": 0.70,
}

DEFAULT_DATASET = Path(__file__).parent / "eval_dataset.jsonl"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "eval_reports"


def load_dataset(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


async def run_eval(
    dataset: list[dict],
    prompt_version: str,
    api_key: str | None,
    concurrency: int,
) -> dict:
    client = LLMClient(api_key=api_key, prompt_version=prompt_version)
    validator = ResponseValidator()
    semaphore = asyncio.Semaphore(concurrency)

    predictions: list[dict] = []
    schema_failures = 0

    async def evaluate_one(record: dict) -> dict:
        async with semaphore:
            try:
                raw, tokens = await client.extract(
                    clean_text=record["clean_text"],
                    platform=record["platform"],
                    normalized_rating=record.get("normalized_rating"),
                )
                validated, result = validator.validate(raw, record["clean_text"])
                if not result.is_valid:
                    return {"record": record, "success": False, "error": result.errors}
                return {
                    "record": record,
                    "success": True,
                    "predicted": validated,
                    "tokens": tokens,
                    "confidence": result.adjusted_confidence,
                }
            except Exception as exc:
                return {"record": record, "success": False, "error": str(exc)}

    tasks = [evaluate_one(r) for r in dataset]
    outcomes = await asyncio.gather(*tasks)

    for outcome in outcomes:
        if not outcome["success"]:
            schema_failures += 1
            logger.warning(
                "eval failed for review=%s error=%s",
                outcome["record"].get("review_id"), outcome.get("error"),
            )
        else:
            predictions.append(outcome)

    return _compute_metrics(predictions, schema_failures, len(dataset))


def _compute_metrics(predictions: list[dict], schema_failures: int, total: int) -> dict:
    if not predictions:
        return {"error": "no successful predictions"}

    # Sentiment accuracy
    sentiment_correct = sum(
        1 for p in predictions
        if p["predicted"].get("sentiment") == p["record"]["expected"]["sentiment"]
    )
    sentiment_accuracy = sentiment_correct / len(predictions)

    # Discovery friction F1
    tp = fp = fn = 0
    for p in predictions:
        pred = p["predicted"].get("discovery_friction_detected", False)
        expected = p["record"]["expected"]["discovery_friction_detected"]
        if pred and expected:
            tp += 1
        elif pred and not expected:
            fp += 1
        elif not pred and expected:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    # Average confidence
    avg_confidence = sum(p["confidence"] for p in predictions) / len(predictions)

    # Schema compliance
    schema_compliance = (total - schema_failures) / total if total > 0 else 0.0

    metrics = {
        "sentiment_accuracy": round(sentiment_accuracy, 4),
        "discovery_friction_precision": round(precision, 4),
        "discovery_friction_recall": round(recall, 4),
        "discovery_friction_f1": round(f1, 4),
        "avg_confidence_score": round(avg_confidence, 4),
        "schema_compliance": round(schema_compliance, 4),
        "total_evaluated": total,
        "schema_failures": schema_failures,
        "successful_predictions": len(predictions),
    }

    thresholds_passed = {
        k: metrics.get(k, 0.0) >= v
        for k, v in THRESHOLDS.items()
        if k in metrics
    }

    return {
        "metrics": metrics,
        "thresholds": THRESHOLDS,
        "thresholds_passed": thresholds_passed,
        "all_passed": all(thresholds_passed.values()),
    }


def write_report(report: dict, output_dir: Path, prompt_version: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = output_dir / f"eval_v{prompt_version}_{ts}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("eval report written to %s", path)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3 — Prompt Evaluation Runner")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--prompt-version", default="1.2")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    dataset = load_dataset(Path(args.dataset))
    logger.info("Loaded %d evaluation examples", len(dataset))

    report = asyncio.run(
        run_eval(
            dataset=dataset,
            prompt_version=args.prompt_version,
            api_key=args.api_key,
            concurrency=args.concurrency,
        )
    )

    write_report(report, Path(args.output_dir), args.prompt_version)
    print(json.dumps(report, indent=2))

    if not report.get("all_passed", False):
        logger.error("EVALUATION FAILED — one or more thresholds not met. Do not promote this prompt version.")
        return 1

    logger.info("All evaluation thresholds passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
