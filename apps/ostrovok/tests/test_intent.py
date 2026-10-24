from app.agent.offline_parser import parse_message

NOW = "2026-10-24T12:00:00+03:00"


def p(s):
    return parse_message(s, NOW)["patch"]


def test_natural_request_extracts_group_and_total_budget():
    r = p(
        "Из Москвы в Анталью 7 ноября на 7 ночей, двое взрослых и ребёнок 7 лет. До 180 тысяч рублей."
    )
    assert r["origin"] == "moscow" and r["destinations"] == ["antalya"]
    assert r["departure_date"] == "2026-11-07" and r["nights"] == 7
    assert r["adults"] == 2 and r["children_ages"] == [7] and r["budget_rub"] == 180000


def test_partial_change_does_not_reset_origin_or_guests():
    r = p("А теперь с нами собака 8 кг, на два дня позже")
    assert r["pet_kg"] == 8 and r["shift_days"] == 2
    assert "origin" not in r and "adults" not in r


def test_relative_dates_use_fixed_clock_not_demo_window():
    assert p("на ближайшие выходные")["departure_date"] == "2026-10-24"
    assert p("завтра")["departure_date"] == "2026-10-25"


def test_date_range_keeps_start_and_number_of_nights():
    r = p("из СПб в Казань с 7 по 11 ноября")
    assert r["departure_date"] == "2026-11-07" and r["nights"] == 4


def test_child_without_age_is_unknown_not_baby():
    r = p("С ребёнком, из Москвы в Сочи 2026-11-07")
    assert r["children_count"] == 1 and not r.get("children_ages")


def test_pet_removal_and_lock_are_explicit():
    assert p("без собаки")["pet_kg"] is None
    assert p("оставь перелёт")["lock_transport"] is True


def test_unknown_request_asks_form_instead_of_fake_understanding():
    assert (
        parse_message("сделай в стиле моей любимой картины", NOW)["recognized"] is False
    )


import pytest


@pytest.mark.parametrize(
    "message", ["Добавь завтрак", "С завтраком", "Не нужен завтрак"]
)
def test_meal_change_does_not_change_departure_date(message):
    assert "departure_date" not in p(message)


@pytest.mark.parametrize(
    "message",
    [
        "Из Москвы в Тбилиси 7 ноября",
        "Из Минска в Казань 7 ноября",
        "Из Москвы в Алматы 7 ноября",
    ],
)
def test_unknown_explicit_geography_is_preserved(message):
    result = parse_message(message, NOW)
    assert any(
        str(value).startswith("unsupported:")
        for value in [
            result["patch"].get("origin"),
            *result["patch"].get("destinations", []),
        ]
    )


@pytest.mark.parametrize(
    "message", ["без самолета, только поездом", "не самолетом, только поездом"]
)
def test_negated_flight_does_not_override_explicit_train(message):
    assert p(message)["transport"] == "train"


def test_negated_train_selects_the_other_supported_mode():
    assert p("без поезда, самолетом")["transport"] == "flight"


def test_excluded_destination_is_removed_from_positive_alternative():
    assert p("не в Сочи, а в Казань")["destinations"] == ["kazan"]


def test_destination_exclusion_filters_the_finite_catalog():
    values = p("К морю, только не в Сочи")["destinations"]
    assert values and "sochi" not in values and "moscow" not in values


def test_negated_meal_clears_meal_requirement():
    assert p("Не нужен завтрак")["meal"] == "any"


def test_repeated_child_age_mentions_preserve_every_child():
    values = p("С ребенком 7 лет и ребенком 10 лет")
    assert values["children_ages"] == [7, 10] and values["children_count"] == 2


@pytest.mark.parametrize(
    "message", ["двое детей 7 и 10 лет", "с двумя детьми 7 и 10 лет"]
)
def test_plural_children_ages_are_parsed(message):
    values = p(message)
    assert values["children_ages"] == [7, 10] and values["children_count"] == 2


def test_unknown_child_ages_preserve_explicit_count():
    values = p("Из Москвы в Сочи с двумя детьми")
    assert values["children_count"] == 2 and not values.get("children_ages")


def test_pet_without_weight_is_pending_and_not_dropped():
    values = p("Из Москвы в Казань 7 ноября с кошкой")
    assert values["pet_requested"] is True and values["pet_kg"] is None


def test_known_pet_weight_and_explicit_removal_record_pet_presence():
    assert p("С собакой 8 кг")["pet_requested"] is True
    assert p("Без собаки") == {"pet_requested": False, "pet_kg": None}


@pytest.mark.parametrize(
    "message,start,end,nights",
    [
        ("С 7 по 11 ноября", "2026-11-07", "2026-11-11", 4),
        ("С 7 ноября по 11 ноября", "2026-11-07", "2026-11-11", 4),
        ("С 30 ноября по 3 декабря", "2026-11-30", "2026-12-03", 3),
        ("С 30 декабря по 3 января", "2026-12-30", "2027-01-03", 4),
        ("С 2026-11-07 по 2026-11-11", "2026-11-07", "2026-11-11", 4),
    ],
)
def test_ranges_preserve_explicit_home_arrival_deadline(message, start, end, nights):
    values = p(message)
    assert values["departure_date"] == start and values["return_by"] == end
    assert values["nights"] == nights


def test_invalid_range_does_not_silently_use_only_its_start():
    result = parse_message("С 30 ноября по 3 ноября", NOW)
    assert "departure_date" not in result["patch"] and result["warnings"]


def test_unrepresented_hard_constraint_is_visible_even_with_other_fields():
    result = parse_message("Из Москвы в Казань 7 ноября без ночного прилета", NOW)
    assert result["unresolved_constraints"] and result["warnings"]


@pytest.mark.parametrize(
    "message",
    [
        "Из Москвы в Казань 10 ноября на 3 ночи, 2 взрослых, лететь до 2 часов, до 80000 рублей",
        "Из Москвы в Казань с 7 до 11 ноября до 80000 рублей",
    ],
)
def test_money_candidates_are_not_confused_with_duration_or_date(message):
    assert p(message)["budget_rub"] == 80000


def test_unsupported_visa_requirement_is_explicit_but_direct_flight_is_supported():
    assert parse_message("только безвизовое направление", NOW)["unresolved_constraints"]
    assert not parse_message("Только прямой перелёт", NOW)["unresolved_constraints"]
