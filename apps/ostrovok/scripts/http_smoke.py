"""Real HTTP pipeline smoke; private cookie state remains outside public reports."""

import argparse, json, http.cookiejar, urllib.request
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--base-url", default="http://127.0.0.1:8080")
p.add_argument("--state", type=Path, default=Path("/tmp/ostrovok-session.json"))
p.add_argument("--resume", action="store_true")
p.add_argument(
    "--report", type=Path, default=Path("reports/ostrovok/http-pipeline.json")
)
args = p.parse_args()
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def request(path, body=None, headers=None):
    req = urllib.request.Request(
        args.base_url + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with opener.open(req, timeout=90) as r:
        return json.load(r)


if args.resume:
    saved = json.loads(args.state.read_text())
    cookie = saved["cookie"]
    req = urllib.request.Request(
        args.base_url + "/api/trips/" + saved["trip_id"], headers={"Cookie": cookie}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        s = json.load(r)
    assert s["order"]["order_id"] == saved["order_id"]
    result = {
        "status": "passed",
        "check": "persistence_after_restart",
        "order_status": s["order"]["status"],
    }
else:
    assert request("/health")["status"] == "ok"
    s = request(
        "/api/trips",
        {
            "message": "Из Москвы в Анталью 7 ноября на неделю, двое взрослых, до 180 тысяч рублей."
        },
    )
    assert s["status"] == "ready", s
    path = "/api/trips/" + s["trip_id"]
    s = request(
        path + "/messages",
        {
            "message": "С нами собака 8 кг, на два дня позже",
            "expected_version": s["version"],
        },
    )
    assert (
        s["intent"]["departure_date"] == "2026-11-09" and s["intent"]["pet_kg"] == 8
    ), s
    s = request(
        path + "/selection",
        {"plan_id": s["plans"][0]["plan_id"], "expected_version": s["version"]},
    )
    s = request(path + "/quote", {"expected_version": s["version"]})
    body = {
        "quote_id": s["quote"]["quote_id"],
        "expected_version": s["version"],
        "confirmed": True,
        "total_minor": s["quote"]["total_minor"],
    }
    s = request(path + "/demo-orders", body, {"Idempotency-Key": "http-smoke-order"})
    repeated = request(
        path + "/demo-orders", body, {"Idempotency-Key": "http-smoke-order"}
    )
    assert (
        s["order"] == repeated["order"]
        and s["order"]["status"] == "simulated_confirmed"
    )
    args.state.write_text(
        json.dumps(
            {
                "trip_id": s["trip_id"],
                "order_id": s["order"]["order_id"],
                "cookie": "; ".join(c.name + "=" + c.value for c in jar),
            }
        )
    )
    args.state.chmod(0o600)
    result = {
        "status": "passed",
        "check": "real_http_full_pipeline",
        "mode": s["llm"],
        "total_minor": s["order"]["total_minor"],
        "currency": "RUB",
        "idempotency": "passed",
    }
args.report.parent.mkdir(parents=True, exist_ok=True)
args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False))
