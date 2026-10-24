from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from test_pipeline import Clock, create_client, create_trip, mutate


def quoted_trip(c):
    t = create_trip(c)
    r = mutate(c, t, "quote")
    assert r.status_code == 200, r.text
    t = r.json()
    return t, {
        "quote_id": t["quote"]["quote_id"],
        "expected_version": t["version"],
        "confirmed": True,
        "total_minor": t["quote"]["total_minor"],
    }


def buy(c, t, body, key="checkout-key"):
    return c.post(
        f"/api/trips/{t['trip_id']}/demo-orders",
        json=body,
        headers={"Idempotency-Key": key},
    )


def test_idempotent_replay_precedes_expiry_version_and_purchased_checks(tmp_path):
    clock = Clock()
    c = create_client(tmp_path, clock=clock)
    t, body = quoted_trip(c)
    first = buy(c, t, body)
    assert first.status_code == 200, first.text
    clock.value += timedelta(minutes=30)
    again = buy(c, t, body)
    assert again.status_code == 200 and again.json() == first.json()
    assert buy(c, t, body, key="different").status_code == 409
    assert buy(c, t, body | {"total_minor": 1}).status_code == 409
    assert mutate(c, first.json(), "messages", patch={"nights": 4}).status_code == 409


def test_invalid_total_version_quote_consent_expiry_and_refresh(tmp_path):
    clock = Clock()
    c = create_client(tmp_path, clock=clock)
    t, body = quoted_trip(c)
    for change in (
        {"total_minor": 1},
        {"expected_version": t["version"] - 1},
        {"quote_id": "wrong"},
    ):
        assert buy(c, t, body | change).status_code == 409
    assert buy(c, t, body | {"confirmed": False}).status_code == 422
    clock.value += timedelta(minutes=20)
    assert buy(c, t, body).status_code == 409
    r = mutate(c, t, "quote")
    assert r.status_code == 200, r.text
    refreshed = r.json()
    assert refreshed["quote"]["quote_id"] != body["quote_id"]
    assert refreshed["quote"]["plan_version"] == refreshed["version"]
    assert (
        refreshed["plans"][0]["components"][0]["expires_at"]
        > t["plans"][0]["components"][0]["expires_at"]
    )


def test_idempotency_key_cannot_be_reused_for_another_trip(tmp_path):
    c = create_client(tmp_path)
    t, body = quoted_trip(c)
    assert buy(c, t, body).status_code == 200
    another, otherbody = quoted_trip(c)
    assert buy(c, another, otherbody).status_code == 409


def test_concurrent_doubleclick_has_one_order_and_foreign_replay_is_404(tmp_path):
    c = create_client(tmp_path)
    t, body = quoted_trip(c)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: buy(c, t, body), range(2)))
    assert [r.status_code for r in results] == [200, 200]
    assert (
        results[0].json()["order"]["order_id"] == results[1].json()["order"]["order_id"]
    )
    other = create_client(tmp_path)
    assert buy(other, t, body).status_code == 404
    assert (
        other.get(
            "/api/demo-orders/" + results[0].json()["order"]["order_id"]
        ).status_code
        == 404
    )
