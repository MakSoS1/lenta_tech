import importlib
import importlib.util
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient


class Clock:
    def __init__(self):
        self.value = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)

    def __call__(self):
        return self.value


class OfflineGateway:
    mode = "offline"
    primary_model = "opencode/deepseek-v4.1-flash-free"
    fallback_model = "opencode/glm-5.3-flash-free"

    async def extract(self, message, intent, reference_now):
        return {"patch": {}, "model": None, "used": False, "reason": "offline"}


def create_client(tmp_path, clock=None, gateway=None):
    assert importlib.util.find_spec("app.main") is not None, (
        "The persistent trip API is missing"
    )
    return TestClient(
        importlib.import_module("app.main").create_app(
            db_path=tmp_path / "trips.sqlite3",
            clock=clock or Clock(),
            gateway=gateway or OfflineGateway(),
        )
    )


def create_trip(client, **patch):
    r = client.post(
        "/api/trips",
        json={
            "message": "Подобрать поездку",
            "patch": {
                "origin": "moscow",
                "destinations": ["kazan"],
                "departure_date": "2026-11-10",
                "nights": 3,
                "adults": 2,
                "budget_rub": 200000,
            }
            | patch,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def mutate(client, trip, path, **body):
    return client.post(
        f"/api/trips/{trip['trip_id']}/{path}",
        json={"expected_version": trip["version"]} | body,
    )


def test_full_pipeline_and_actual_event_replay(tmp_path):
    c = create_client(tmp_path)
    t = create_trip(c)
    assert t["status"] == "ready" and 1 <= len(t["plans"]) <= 3
    assert not t["llm"]["used"] and any("parser" in w.lower() for w in t["warnings"])
    changed = mutate(
        c, t, "messages", message="Теперь завтрак", patch={"meal": "breakfast"}
    ).json()
    assert changed["version"] == t["version"] + 1
    assert (
        changed["intent"]["meal"] == "breakfast"
        and changed["intent"]["departure_date"] == "2026-11-10"
    )
    assert changed["delta"]["changed_fields"] == ["meal"]
    selected = mutate(
        c, changed, "selection", plan_id=changed["plans"][-1]["plan_id"]
    ).json()
    quoted = mutate(c, selected, "quote").json()
    assert quoted["quote"]["plan_version"] == quoted["version"]
    response = c.post(
        f"/api/trips/{t['trip_id']}/demo-orders",
        headers={"Idempotency-Key": "full-flow"},
        json={
            "expected_version": quoted["version"],
            "quote_id": quoted["quote"]["quote_id"],
            "confirmed": True,
            "total_minor": quoted["quote"]["total_minor"],
        },
    )
    assert response.status_code == 200, response.text
    ordered = response.json()
    order = ordered["order"]
    assert ordered["status"] == "ordered" and order["status"] == "simulated_confirmed"
    assert order["total_minor"] == sum(
        x["total_minor"] for x in order["plan"]["components"]
    )
    assert c.get(f"/api/trips/{t['trip_id']}").json() == ordered
    assert c.get(f"/api/demo-orders/{order['order_id']}").json() == order
    assert c.get("/api/trips").json()["trips"][0]["trip_id"] == t["trip_id"]
    events = c.get(f"/api/trips/{t['trip_id']}/events")
    assert (
        events.status_code == 200
        and "text/event-stream" in events.headers["content-type"]
    )
    assert "event: action" in events.text and "demo_order" in events.text


def test_unknown_child_age_and_missing_requirements_need_clarification(tmp_path):
    t = (
        create_client(tmp_path)
        .post("/api/trips", json={"message": "Хочу отдохнуть с ребенком"})
        .json()
    )
    assert t["status"] == "needs_clarification"
    assert {q["key"] for q in t["questions"]} >= {
        "origin",
        "departure_date",
        "budget_rub",
        "children_ages",
    }
    assert (
        t["intent"]["children_count"] == 1
        and t["intent"]["children_ages"] == []
        and not t["plans"]
    )


def test_relative_dates_use_stored_clock_without_coverage_rewrite(tmp_path):
    c = create_client(tmp_path)
    t = c.post(
        "/api/trips",
        json={
            "message": "Из Москвы в Казань на ближайшие выходные, бюджет 80000 рублей"
        },
    ).json()
    assert t["intent"]["departure_date"] == "2026-10-24" and t["status"] == "no_options"
    changed = mutate(c, t, "messages", message="На два дня позже").json()
    assert (
        changed["intent"]["departure_date"] == "2026-10-26"
        and changed["reference_now"] == t["reference_now"]
    )


def test_returning_next_day_uses_new_turn_clock_for_tomorrow(tmp_path):
    from datetime import timedelta

    clock = Clock()
    c = create_client(tmp_path, clock=clock)
    t = create_trip(c)
    clock.value += timedelta(days=1)
    changed = mutate(c, t, "messages", message="А если завтра?").json()
    assert changed["intent"]["departure_date"] == "2026-10-26"
    assert changed["reference_now"] != t["reference_now"]


def test_health_checks_sqlite_instead_of_reporting_constant_success(tmp_path):
    c = create_client(tmp_path)
    assert c.get("/health").status_code == 200
    (tmp_path / "trips.sqlite3").write_bytes(b"not a SQLite database")
    assert c.get("/health").status_code == 503


def test_stale_versions_and_invalid_partial_patch_do_not_mutate(tmp_path):
    c = create_client(tmp_path)
    t = create_trip(c)
    changed = mutate(c, t, "messages", patch={"nights": 4}).json()
    assert mutate(c, t, "messages", patch={"nights": 5}).status_code == 409
    for patch in (
        {"adults": "2"},
        {"nights": True},
        {"order_id": "evil"},
        {"departure_date": "2026-02-30"},
        {"shift_days": 999},
        {"shift_days": None},
    ):
        bad = mutate(c, changed, "messages", patch=patch)
        assert bad.status_code == 422 and isinstance(bad.json()["detail"], str), (
            bad.text
        )
    assert c.get(f"/api/trips/{t['trip_id']}").json()["version"] == changed["version"]


def test_null_shift_is_rejected_instead_of_becoming_a_silent_noop():
    from app.service import apply_patch
    from app.domain.models import TripIntent
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        apply_patch(TripIntent().model_dump(mode="json"), {"shift_days": None})
    assert error.value.status_code == 422


def test_date_shift_cannot_overflow_the_calendar():
    from app.service import apply_patch
    from app.domain.models import TripIntent
    from fastapi import HTTPException

    current = TripIntent().model_dump(mode="json") | {"departure_date": "9999-12-31"}
    with pytest.raises(HTTPException) as error:
        apply_patch(current, {"shift_days": 60})
    assert error.value.status_code == 422


def test_transport_lock_survives_hotel_change_and_conflict_requires_unlock(tmp_path):
    c = create_client(tmp_path)
    t = create_trip(c)
    transport = next(
        x["offer_id"] for x in t["plans"][0]["components"] if x["kind"] == "transport"
    )
    locked = mutate(c, t, "messages", patch={"lock_transport": True}).json()
    assert locked["locked_component_ids"] == [transport]
    hotel = mutate(c, locked, "messages", patch={"meal": "breakfast"}).json()
    assert hotel["status"] == "ready"
    assert all(
        any(x["offer_id"] == transport for x in p["components"]) for p in hotel["plans"]
    )
    conflict = mutate(c, hotel, "messages", patch={"shift_days": 2}).json()
    assert conflict["status"] == "needs_resolution" and conflict["quote"] is None
    assert conflict["locked_component_ids"] == [transport]
    assert mutate(c, conflict, "quote").status_code == 409
    unlocked = mutate(c, conflict, "messages", patch={"lock_transport": False}).json()
    assert unlocked["status"] == "ready" and unlocked["locked_component_ids"] == []


def test_injected_model_gets_only_intent_and_valid_patch_is_used(tmp_path):
    class Gateway(OfflineGateway):
        mode = "opencode"

        async def extract(self, message, intent, reference_now):
            assert not set(intent) & {"trip_id", "session_id", "quote", "order"}
            return {
                "patch": {"meal": "breakfast"},
                "model": self.fallback_model,
                "used": True,
                "reason": None,
            }

    t = create_trip(create_client(tmp_path, gateway=Gateway()))
    assert t["intent"]["meal"] == "breakfast" and t["llm"]["used"]
    assert not any("parser" in w.lower() for w in t["warnings"])


def test_pet_without_weight_requires_clarification_then_weight_and_removal_work(
    tmp_path,
):
    c = create_client(tmp_path)
    t = create_trip(c, pet_requested=True)
    assert t["status"] == "needs_clarification" and not t["plans"]
    assert any(q["key"] == "pet_kg" for q in t["questions"])
    weighted = mutate(c, t, "messages", patch={"pet_kg": 8}).json()
    assert weighted["status"] == "ready" and weighted["intent"]["pet_requested"] is True
    removed = mutate(c, weighted, "messages", patch={"pet_kg": None}).json()
    assert removed["intent"]["pet_requested"] is False


def test_return_deadline_shifts_together_with_departure(tmp_path):
    c = create_client(tmp_path)
    t = create_trip(c, return_by="2026-11-14")
    assert t["status"] == "ready"
    shifted = mutate(c, t, "messages", patch={"shift_days": 2}).json()
    assert shifted["intent"]["departure_date"] == "2026-11-12"
    assert shifted["intent"]["return_by"] == "2026-11-16"


def test_unsupported_hard_constraints_survive_unrelated_form_changes(tmp_path):
    c = create_client(tmp_path)
    r = c.post(
        "/api/trips",
        json={
            "message": "Из Москвы в Казань 10 ноября 2026 на 3 ночи, бюджет 200000 рублей, только безвизовое направление"
        },
    )
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["unresolved_constraints"] and not t["plans"]
    changed = mutate(c, t, "messages", patch={"meal": "breakfast"}).json()
    assert (
        changed["unresolved_constraints"] == t["unresolved_constraints"]
        and not changed["plans"]
    )
    assert mutate(c, changed, "quote").status_code == 409
    cleared = mutate(
        c, changed, "messages", message="Сними неподдерживаемые ограничения"
    ).json()
    assert cleared["unresolved_constraints"] == [] and cleared["status"] == "ready"
