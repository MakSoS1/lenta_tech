"""Actual free inference + application path; exit 2 is unavailable, never success."""

import argparse, json, os, sys, tempfile, time
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/ostrovok/backend"))
from fastapi.testclient import TestClient
from app.main import create_app
from app.agent.model_gateway import FREE_MODELS


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", choices=sorted(FREE_MODELS), required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    os.environ["LLM_MODE"] = "opencode"
    os.environ["OPENCODE_MODEL"] = a.model
    report = {
        "model": a.model,
        "free_only": True,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "failed",
        "steps": [],
    }
    started = time.monotonic()
    code = 1
    try:
        with (
            tempfile.TemporaryDirectory() as d,
            TestClient(
                create_app(
                    str(Path(d) / "live.sqlite"),
                    lambda: datetime(2026, 10, 24, 12, tzinfo=timezone.utc),
                )
            ) as c,
        ):
            r = c.post(
                "/api/trips",
                json={
                    "message": "Из Москвы в Анталью 7 ноября 2026 на 7 ночей, двое взрослых. Бюджет 180 тысяч рублей."
                },
            )
            r.raise_for_status()
            s = r.json()
            report["inference"] = s["llm"]
            report["steps"].append(
                {
                    "step": "new_request",
                    "status": s["status"],
                    "used_llm": s["llm"]["used"],
                }
            )
            if not s["llm"]["used"]:
                report["status"] = "blocked"
                report["reason"] = s["llm"]["reason"]
                code = 2
            else:
                assert (
                    s["status"] == "ready"
                    and s["intent"]["origin"] == "moscow"
                    and s["intent"]["adults"] == 2
                )
                assert (
                    s["intent"]["departure_date"] == "2026-11-07"
                    and s["intent"]["budget_rub"] == 180000
                )
                path = "/api/trips/" + s["trip_id"]
                r = c.post(
                    path + "/messages",
                    json={
                        "message": "С нами собака 8 кг. Сдвинь поездку на два дня позже.",
                        "expected_version": s["version"],
                    },
                )
                r.raise_for_status()
                s = r.json()
                assert (
                    s["llm"]["used"]
                    and s["status"] == "ready"
                    and s["intent"]["pet_kg"] == 8
                    and s["intent"]["departure_date"] == "2026-11-09"
                )
                report["steps"].append(
                    {"step": "replan", "status": "passed", "used_llm": True}
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
                    path + "/demo-orders",
                    json=body,
                    headers={"Idempotency-Key": "live-eval"},
                )
                r.raise_for_status()
                s = r.json()
                assert s["order"]["status"] == "simulated_confirmed"
                report["steps"].append(
                    {
                        "step": "demo_order",
                        "status": "passed",
                        "total_minor": s["order"]["total_minor"],
                    }
                )
                report["status"] = "passed"
                code = 0
    except Exception as exc:
        report["failure_type"] = type(exc).__name__
        report["reason"] = (
            "Live pipeline assertions did not pass; preceding structured steps show progress."
        )
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
