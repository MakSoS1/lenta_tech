"""Functional corpus evaluation in explicitly limited-parser mode; not an LLM benchmark."""

import argparse, json, os, sys, tempfile, time, statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/ostrovok/backend"))
from fastapi.testclient import TestClient
from app.main import create_app


def run_case(c, case):
    c.cookies.clear()
    started = time.monotonic()
    r = c.post(
        "/api/trips", json={"message": case["message"], "patch": case.get("patch")}
    )
    r.raise_for_status()
    s = r.json()
    path = "/api/trips/" + s["trip_id"]
    first_seconds = time.monotonic() - started
    if case.get("select_before_changes"):
        assert s["plans"], "No initial plan to select"
        r = c.post(
            path + "/selection",
            json={
                "plan_id": s["plans"][0]["plan_id"],
                "expected_version": s["version"],
            },
        )
        r.raise_for_status()
        s = r.json()
    for msg in case.get("changes", []):
        r = c.post(
            path + "/messages", json={"message": msg, "expected_version": s["version"]}
        )
        r.raise_for_status()
        s = r.json()
    assert s["status"] == case["expected_status"], (
        f"status {s['status']} != {case['expected_status']}"
    )
    for key, value in case.get("expected_intent", {}).items():
        assert s["intent"][key] == value, (
            f"intent.{key}: {s['intent'][key]!r} != {value!r}"
        )
    purchased = False
    if s["status"] == "ready":
        assert s["plans"] and all(p["validation"]["passed"] for p in s["plans"])
        assert all(
            p["total_minor"] == sum(o["total_minor"] for o in p["components"])
            for p in s["plans"]
        )
        r = c.post(
            path + "/selection",
            json={
                "plan_id": s["plans"][0]["plan_id"],
                "expected_version": s["version"],
            },
        )
        r.raise_for_status()
        s = r.json()
        r = c.post(path + "/quote", json={"expected_version": s["version"]})
        r.raise_for_status()
        s = r.json()
        body = {
            "quote_id": s["quote"]["quote_id"],
            "expected_version": s["version"],
            "confirmed": True,
            "total_minor": s["quote"]["total_minor"],
        }
        r = c.post(
            path + "/demo-orders", json=body, headers={"Idempotency-Key": case["id"]}
        )
        r.raise_for_status()
        s = r.json()
        assert s["order"]["status"] == "simulated_confirmed"
        purchased = True
        assert c.get(path).json()["order"]["order_id"] == s["order"]["order_id"]
    return {
        "id": case["id"],
        "name": case["name"],
        "passed": True,
        "expected_status": case["expected_status"],
        "purchase": purchased,
        "first_recommendation_seconds": round(first_seconds, 4),
        "duration_seconds": round(time.monotonic() - started, 4),
        "llm_used": s["llm"]["used"],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--cases", type=Path, default=Path(__file__).with_name("cases_dev.jsonl")
    )
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    os.environ["LLM_MODE"] = "offline"
    cases = [
        json.loads(line) for line in a.cases.read_text().splitlines() if line.strip()
    ]
    results = []
    with (
        tempfile.TemporaryDirectory() as d,
        TestClient(
            create_app(
                str(Path(d) / "eval.sqlite"),
                lambda: datetime(2026, 10, 24, 12, tzinfo=timezone.utc),
            )
        ) as c,
    ):
        for case in cases:
            try:
                results.append(run_case(c, case))
            except Exception as exc:
                results.append(
                    {
                        "id": case["id"],
                        "name": case["name"],
                        "passed": False,
                        "error": str(exc)[:600],
                        "expected_status": case["expected_status"],
                    }
                )
    passed = sum(r["passed"] for r in results)
    times = sorted(
        r["first_recommendation_seconds"] for r in results if r.get("purchase")
    )
    report = {
        "mode": "offline_limited",
        "not_an_llm_benchmark": True,
        "fixed_reference_now": "2026-10-24T12:00:00Z",
        "cases": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "completed_demo_orders": sum(r.get("purchase", False) for r in results),
        "latency_scope": "In-process FastAPI + SQLite + acquired local reference snapshot; excludes live network/model",
        "first_recommendation_p50_seconds": statistics.median(times) if times else None,
        "first_recommendation_p95_seconds": times[
            min(len(times) - 1, int(len(times) * 0.95))
        ]
        if times
        else None,
        "results": results,
    }
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "results"}, ensure_ascii=False
        )
    )
    for r in results:
        if not r["passed"]:
            print(json.dumps(r, ensure_ascii=False))
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
