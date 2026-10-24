from test_pipeline import create_client, create_trip


def test_every_resource_is_owned_and_preferences_require_opt_in(tmp_path):
    owner = create_client(tmp_path)
    other = create_client(tmp_path)
    t = create_trip(owner)
    cookie = next(x for x in owner.cookies.jar if x.name == "ostrovok_session")
    assert len(cookie.value) >= 32 and cookie.has_nonstandard_attr("HttpOnly")
    for method, path, body in [
        ("get", "", None),
        ("get", "/events", None),
        ("post", "/messages", {"expected_version": 1, "message": "Изменить"}),
        ("post", "/quote", {"expected_version": 1}),
        (
            "post",
            "/demo-orders",
            {
                "expected_version": 1,
                "quote_id": "x",
                "confirmed": True,
                "total_minor": 0,
            },
        ),
        ("post", "/service-requests", {"kind": "early_checkin", "message": "Уточнить"}),
    ]:
        r = getattr(other, method)(
            f"/api/trips/{t['trip_id']}{path}", **({"json": body} if body else {})
        )
        assert r.status_code == 404, r.text
    assert other.get("/api/trips").json() == {"trips": []}
    assert owner.get("/api/preferences").json() == {"preferences": {}}
    assert (
        owner.put(
            "/api/preferences",
            json={"preferences": {"meal": "breakfast", "refundable": True}},
        ).status_code
        == 200
    )
    assert other.get("/api/preferences").json() == {"preferences": {}}
    assert owner.get("/api/preferences").json()["preferences"]["meal"] == "breakfast"
    assert owner.delete("/api/preferences").json() == {"preferences": {}}


def test_restart_restores_sqlite_state_session_and_saved_preferences(tmp_path):
    c = create_client(tmp_path)
    t = create_trip(c)
    c.put("/api/preferences", json={"preferences": {"hotel_preference": "center"}})
    restarted = create_client(tmp_path)
    restarted.cookies.update(c.cookies)
    assert restarted.get(f"/api/trips/{t['trip_id']}").json() == t
    assert restarted.get("/api/preferences").json() == {
        "preferences": {"hotel_preference": "center"}
    }
    assert create_trip(restarted)["intent"]["hotel_preference"] == "center"


def test_early_checkin_is_only_a_recorded_demo_request(tmp_path):
    c = create_client(tmp_path)
    t = create_trip(c)
    r = c.post(
        f"/api/trips/{t['trip_id']}/service-requests",
        json={"kind": "early_checkin", "message": "Раннее прибытие"},
    )
    assert r.status_code == 200 and r.json()["status"] == "requested_demo"
    assert "не" in r.json()["message"].lower()
    assert c.get(f"/api/trips/{t['trip_id']}").json()["version"] == t["version"]


def test_service_request_restores_after_restart_and_repeats_are_idempotent(tmp_path):
    c = create_client(tmp_path)
    t = create_trip(c)
    url = f"/api/trips/{t['trip_id']}/service-requests"
    first = c.post(url, json={'kind': 'early_checkin', 'message': 'Раннее прибытие'}).json()
    restarted = create_client(tmp_path)
    restarted.cookies.update(c.cookies)
    restored = restarted.get(f"/api/trips/{t['trip_id']}").json()
    assert restored['service_requests'] == [first]
    again = restarted.post(url, json={'kind': 'early_checkin', 'message': 'Повтор'}).json()
    assert again == first
    assert restored['version'] == t['version']
    assert create_client(tmp_path).get(f"/api/trips/{t['trip_id']}").status_code == 404
