from datetime import datetime, timezone
from copy import deepcopy
from hypothesis import given, strategies as st
from app.domain.models import TripIntent
from app.domain.engine import build_plans, validate_trip

NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)


def intent(**kw):
    return TripIntent(
        **(
            {
                "origin": "moscow",
                "destinations": ["antalya"],
                "departure_date": "2026-11-07",
                "budget_rub": 180000,
                "adults": 2,
                "children_ages": [7],
                "children_count": 1,
            }
            | kw
        )
    )


def test_full_trip_exact_total_and_demo_disclosure():
    plans = build_plans(intent(), NOW)["plans"]
    assert 1 <= len(plans) <= 3
    for p in plans:
        assert p["total_minor"] == sum(c["total_minor"] for c in p["components"])
        assert {c["kind"] for c in p["components"]} == {
            "transport",
            "hotel",
            "transfer",
        }
        assert all(c["source"]["kind"] == "synthetic" for c in p["components"])
        assert p["validation"]["passed"]


def test_stable_offer_ids_and_prices():
    a = build_plans(intent(), NOW)["plans"]
    b = build_plans(intent(), NOW)["plans"]
    assert a and [(p["plan_id"], p["total_minor"]) for p in a] == [
        (p["plan_id"], p["total_minor"]) for p in b
    ]


def test_budget_has_explanation():
    r = build_plans(intent(budget_rub=1000), NOW)
    assert not r["plans"] and any("budget" in x["rule_id"] for x in r["rejections"])


def test_pet_policy_checked_for_every_component():
    plans = build_plans(intent(pet_kg=8), NOW)["plans"]
    assert plans
    for p in plans:
        assert all(c["details"]["pet_limit_kg"] >= 8 for c in p["components"])


def test_unknown_city_never_creates_inventory():
    assert not build_plans(intent(destinations=["atlantis"]), NOW)["plans"]


def test_stay_must_fit_date_coverage():
    assert not build_plans(intent(departure_date="2027-01-30", nights=7), NOW)["plans"]


def test_validator_catches_tampered_total_and_night_gap():
    plans = build_plans(intent(), NOW)["plans"]
    assert plans
    bad = deepcopy(plans[0])
    bad["total_minor"] += 100
    assert not validate_trip(bad, intent())["passed"]
    bad = deepcopy(plans[0])
    hotel = next(c for c in bad["components"] if c["kind"] == "hotel")
    hotel["details"]["checkin_at"] = "2026-11-08T15:00:00+03:00"
    assert not validate_trip(bad, intent())["passed"]


@given(st.integers(1, 5), st.integers(2, 14))
def test_money_invariant(adults, nights):
    plans = build_plans(intent(adults=adults, nights=nights, budget_rub=1000000), NOW)[
        "plans"
    ]
    assert plans
    for p in plans:
        assert isinstance(p["total_minor"], int)
        assert p["total_minor"] == sum(c["total_minor"] for c in p["components"])


import pytest
from datetime import date, timedelta
from pydantic import ValidationError


def component(plan, kind):
    return next(c for c in plan["components"] if c["kind"] == kind)


def test_pet_presence_and_minimum_weight_are_explicit():
    pending = intent(pet_requested=True)
    result = build_plans(pending, NOW)
    assert not result["plans"] and any(
        r["rule_id"] == "pet_weight" for r in result["rejections"]
    )
    with pytest.raises(ValidationError):
        intent(pet_kg=0.01)


def test_refundable_means_all_components_not_only_hotel():
    plans = build_plans(intent(refundable=True, budget_rub=1000000), NOW)["plans"]
    assert plans
    assert all(
        c["details"]["refundable"] is True for plan in plans for c in plan["components"]
    )


@pytest.mark.parametrize("kind", ["transport", "hotel", "transfer"])
def test_validator_rejects_nonrefundable_component(kind):
    i = intent(refundable=True, budget_rub=1000000)
    plan = deepcopy(build_plans(i, NOW)["plans"][0])
    component(plan, kind)["details"]["refundable"] = False
    assert not validate_trip(plan, i)["passed"]


@pytest.mark.parametrize(
    "values,rule",
    [
        ({"origin": "atlantis"}, "origin_coverage"),
        ({"destinations": ["atlantis"]}, "destination_coverage"),
        (
            {"origin": "saint-petersburg", "destinations": ["saint-petersburg"]},
            "same_city",
        ),
        ({"destinations": ["antalya"], "transport": "train"}, "route_coverage"),
        ({"destinations": ["kazan", "unsupported:тбилиси"]}, "destination_coverage"),
    ],
)
def test_unsupported_explicit_constraints_are_explained_without_substitution(
    values, rule
):
    result = build_plans(intent(**values), NOW)
    assert not result["plans"] and any(
        row["rule_id"] == rule for row in result["rejections"]
    )


def test_actual_arrival_home_must_fit_demo_coverage():
    i = intent(
        destinations=["sochi"],
        departure_date="2027-01-28",
        nights=2,
        budget_rub=1000000,
    )
    result = build_plans(i, NOW)
    assert result["plans"]
    assert all(
        datetime.fromisoformat(
            component(plan, "transport")["details"]["return_arrival"]
        ).date()
        <= date(2027, 1, 31)
        for plan in result["plans"]
    )


def test_explicit_range_deadline_includes_home_arrival():
    i = intent(
        destinations=["kazan"],
        departure_date="2026-11-07",
        nights=4,
        return_by="2026-11-11",
        budget_rub=1000000,
    )
    plans = build_plans(i, NOW)["plans"]
    assert plans
    assert all(
        datetime.fromisoformat(
            component(p, "transport")["details"]["return_arrival"]
        ).date()
        <= date(2026, 11, 11)
        for p in plans
    )


def test_exact_stay_span_includes_only_explicit_previous_night_repair():
    plans = build_plans(
        intent(destinations=["kazan"], nights=2, budget_rub=1000000), NOW
    )["plans"]
    assert plans
    for plan in plans:
        h = component(plan, "hotel")["details"]
        span = (
            datetime.fromisoformat(h["checkout_at"]).date()
            - datetime.fromisoformat(h["checkin_at"]).date()
        ).days
        assert span == h["nights"] == 2 + int(h["extra_night"])


def test_candidates_must_not_depart_in_the_past():
    late = datetime(2026, 11, 7, 20, tzinfo=timezone.utc)
    result = build_plans(intent(), late)
    assert not result["plans"] and any(
        row["rule_id"] == "departure_time" for row in result["rejections"]
    )


@pytest.mark.parametrize(
    "change",
    [
        "buffer",
        "transfer_duration",
        "stay_span",
        "stay_count",
        "transfer_capacity",
        "passengers",
        "mode",
        "route",
        "duplicate_component",
        "missing_policy",
    ],
)
def test_validator_independently_rejects_inconsistent_components(change):
    i = intent(transport="flight", budget_rub=1000000)
    plan = deepcopy(build_plans(i, NOW)["plans"][0])
    t, h, x = [
        component(plan, kind)["details"] for kind in ("transport", "hotel", "transfer")
    ]
    if change == "buffer":
        x.update(
            terminal_buffer_minutes=0,
            return_terminal_arrival=(
                datetime.fromisoformat(t["return_departure"]) - timedelta(minutes=1)
            ).isoformat(),
        )
    elif change == "transfer_duration":
        x["duration_minutes"] += 15
    elif change == "stay_span":
        h["checkout_at"] = h["checkin_at"]
    elif change == "stay_count":
        h["nights"] += 1
    elif change == "transfer_capacity":
        x["capacity"] = 0
    elif change == "passengers":
        t["passengers"] = 0
    elif change == "mode":
        t["mode"] = "train"
    elif change == "route":
        t["origin"] = "saint-petersburg"
    elif change == "duplicate_component":
        plan["components"].append(deepcopy(component(plan, "transport")))
    else:
        x.pop("terminal_buffer_minutes", None)
    assert not validate_trip(plan, i)["passed"]


def test_validator_checks_now_without_requiring_it_for_compatibility():
    i = intent()
    plan = build_plans(i, NOW)["plans"][0]
    assert not validate_trip(plan, i, now=datetime(2026, 11, 8, tzinfo=timezone.utc))[
        "passed"
    ]


def test_room_expansion_stays_inside_declared_catalog_limit():
    plans = build_plans(
        intent(
            adults=8,
            children_ages=[1, 2, 3, 4],
            children_count=4,
            rooms=4,
            budget_rub=1000000,
        ),
        NOW,
    )["plans"]
    assert plans and all(
        component(plan, "hotel")["details"]["rooms"] <= 4 for plan in plans
    )
