import hashlib
import json
import math
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from app.providers.reference import city_info, load_reference, weather_context

DATE_FROM = date(2026, 11, 1)
DATE_TO = date(2027, 1, 31)
# Synthetic return tariffs, hours, nightly room rates, transfer minutes.
TARIFFS = {
    "kazan": (12000, 2, 3000, 35),
    "sochi": (18000, 4, 3600, 50),
    "kaliningrad": (16000, 2.5, 3300, 40),
    "saint-petersburg": (12000, 1.5, 3900, 40),
    "yerevan": (25000, 3.5, 3900, 30),
    "istanbul": (29000, 5, 4500, 75),
    "antalya": (30000, 5.25, 4200, 60),
    "hurghada": (34000, 5.5, 3800, 35),
}


def stable_id(kind, values):
    return (
        kind
        + "_"
        + hashlib.sha256(
            json.dumps(values, sort_keys=True, ensure_ascii=False, default=str).encode()
        ).hexdigest()[:16]
    )


def issue(rule_id, passed, message, status=None):
    return {
        "rule_id": rule_id,
        "status": status or ("pass" if passed else "fail"),
        "severity": "info" if passed else "error",
        "message": message,
    }


def offer(kind, title, total, details, key, now):
    return {
        "offer_id": stable_id(kind, key),
        "kind": kind,
        "title": title,
        "total_minor": total,
        "currency": "RUB",
        "details": details,
        "source": {
            "kind": "synthetic",
            "name": "Демонстрационный каталог О!Собрано v1",
            "url": "https://github.com/MakSoS1/lenta_tech",
            "observed_at": now.isoformat(),
        },
        "expires_at": (now + timedelta(minutes=15)).isoformat(),
    }


ORIGINS = ("moscow", "saint-petersburg")
TRAIN_DESTINATIONS = ("kazan", "sochi", "saint-petersburg")
TERMINAL_BUFFERS = {"flight": 120, "train": 40}
BAGGAGE_BUFFER_MINUTES = 40


def build_plans(intent, now, reference_dir=None):
    rejections = []
    if intent.origin not in ORIGINS:
        rejections.append(
            issue(
                "origin_coverage",
                False,
                "Город отправления вне демокаталога: поддерживаются Москва и Санкт-Петербург.",
            )
        )
    if not intent.departure_date:
        rejections.append(
            issue("departure_date", False, "Нужна точная дата отправления.")
        )
    unsupported = [dest for dest in intent.destinations if dest not in TARIFFS]
    if unsupported:
        rejections.append(
            issue(
                "destination_coverage",
                False,
                "Указанное направление вне демокаталога: "
                + ", ".join(unsupported)
                + ". Другие города автоматически не подставляются.",
            )
        )
    if intent.destinations and any(
        dest == intent.origin for dest in intent.destinations
    ):
        rejections.append(
            issue(
                "same_city",
                False,
                "Город отправления совпадает с направлением: уточните маршрут.",
            )
        )
    if intent.children_count != len(intent.children_ages):
        rejections.append(
            issue(
                "child_ages",
                False,
                "Укажите возраст каждого ребёнка: цены и вместимость пока не подтверждены.",
                status="unknown",
            )
        )
    if intent.pet_requested and intent.pet_kg is None:
        rejections.append(
            issue(
                "pet_weight",
                False,
                "Укажите вес питомца, чтобы проверить допуск и сборы всех компонентов.",
                status="unknown",
            )
        )
    if rejections:
        return {"plans": [], "rejections": rejections}
    cities, _ = load_reference(reference_dir)
    origin_today = now.astimezone(ZoneInfo(cities[intent.origin]["timezone"])).date()
    if (
        intent.departure_date < DATE_FROM
        or intent.departure_date > DATE_TO
        or intent.departure_date < origin_today
    ):
        return {
            "plans": [],
            "rejections": [
                issue(
                    "date_coverage",
                    False,
                    "Дата отправления вне окна 01.11.2026–31.01.2027 или уже прошла.",
                )
            ],
        }
    if intent.return_by and intent.return_by <= intent.departure_date:
        return {
            "plans": [],
            "rejections": [
                issue(
                    "return_deadline",
                    False,
                    "Дата возвращения должна быть позже даты отправления.",
                )
            ],
        }
    plans = []
    for dest in intent.destinations or [
        dest for dest in TARIFFS if dest != intent.origin
    ]:
        if intent.transport == "train" and dest not in TRAIN_DESTINATIONS:
            rejections.append(
                issue(
                    "route_coverage",
                    False,
                    "Поезд на выбранном маршруте не входит в демокаталог.",
                )
            )
            continue
        weather = weather_context(dest, intent.departure_date.month, reference_dir)
        if intent.warm and (
            dest not in ("sochi", "antalya", "hurghada")
            or not weather
            or weather["temperature_mean_c"] < 20
        ):
            rejections.append(
                issue(
                    "warm_season",
                    False,
                    "Историческая средняя температура воздуха ниже 20°C; тёплое море не подтверждено.",
                )
            )
            continue
        for ti in range(3):
            for hi in range(4):
                for xi in range(2):
                    plan = _candidate(intent, dest, ti, hi, xi, cities, weather, now)
                    if plan is None:
                        continue
                    plan["validation"] = validate_trip(plan, intent, now=now)
                    if plan["validation"]["passed"]:
                        plans.append(plan)
                    else:
                        rejections.extend(
                            row
                            for row in plan["validation"]["issues"]
                            if row["status"] != "pass"
                        )
    selected = []
    rankings = [
        ("Дешевле", lambda p: p["total_minor"]),
        ("Комфортнее", lambda p: (-p["_comfort"], p["total_minor"])),
        ("Больше времени", lambda p: (-p["useful_hours"], p["total_minor"])),
    ]
    for title, key in rankings:
        remaining = [
            p
            for p in sorted(plans, key=key)
            if p["plan_id"] not in {row["plan_id"] for row in selected}
        ]
        if remaining:
            chosen = remaining[0].copy()
            chosen["title"] = title
            chosen.pop("_comfort", None)
            selected.append(chosen)
    if not selected and not rejections:
        rejections.append(
            issue(
                "catalog_coverage",
                False,
                "Сочетание условий не входит в конечный демонстрационный каталог.",
            )
        )
    unique = {(row["rule_id"], row["message"]): row for row in rejections}
    return {"plans": selected, "rejections": list(unique.values())[:20]}


def _candidate(i, dest, ti, hi, xi, cities, weather, now):
    base, hours, night_rate, transfer_min = TARIFFS[dest]
    oz = ZoneInfo(cities[i.origin]["timezone"])
    dz = ZoneInfo(cities[dest]["timezone"])
    mode = (
        "train"
        if i.transport == "train"
        or (
            i.transport == "any"
            and ti == 2
            and dest in ("kazan", "sochi", "saint-petersburg")
        )
        else "flight"
    )
    if mode == "train":
        if dest not in ("kazan", "sochi", "saint-petersburg"):
            return None
        hours = {"kazan": 12, "sochi": 24, "saint-petersburg": 8}[dest] + (
            10 if i.origin == "saint-petersburg" else 0
        )
        base = base * 65 // 100
    elif i.origin == "saint-petersburg":
        hours += 0.5
        base += 2000
    depart = datetime.combine(i.departure_date, time([8, 21, 11][ti]), tzinfo=oz)
    arrive = (depart.astimezone(timezone.utc) + timedelta(hours=hours)).astimezone(dz)
    back_depart = datetime.combine(
        arrive.date() + timedelta(days=i.nights), time(18), tzinfo=dz
    )
    back_arrive = (
        back_depart.astimezone(timezone.utc) + timedelta(hours=hours)
    ).astimezone(oz)
    passengers = i.adults + len(i.children_ages)
    units = 100 * i.adults + sum(15 if age < 2 else 70 for age in i.children_ages)
    transport_pet = [0, 8, 20][ti]
    fare_minor = base * units * (100 + ti * 8) // 100 + (300000 if i.pet_kg else 0)
    tdetails = {
        "origin": i.origin,
        "destination": dest,
        "return_origin": dest,
        "return_destination": i.origin,
        "stops": 0,
        "mode": mode,
        "duration_hours": hours,
        "outbound_departure": depart.isoformat(),
        "outbound_arrival": arrive.isoformat(),
        "return_departure": back_depart.isoformat(),
        "return_arrival": back_arrive.isoformat(),
        "passengers": passengers,
        "pet_limit_kg": transport_pet,
        "refundable": ti == 2,
        "baggage_included": True,
        "price_basis": "Туда и обратно на всю группу; багаж и обязательные сборы включены",
    }
    t = offer(
        "transport",
        ("Поезд" if mode == "train" else "Перелёт")
        + " · "
        + ["эконом", "вечерний", "гибкий"][ti],
        fare_minor,
        tdetails,
        [
            i.origin,
            dest,
            i.departure_date,
            i.nights,
            i.adults,
            i.children_ages,
            i.pet_kg,
            ti,
            mode,
        ],
        now,
    )
    transfer_minutes = transfer_min + (20 if xi == 0 else 0)
    hotel_arrival = arrive + timedelta(minutes=40 + transfer_minutes)
    room_ready = datetime.combine(hotel_arrival.date(), time(15), tzinfo=dz)
    # Requested nights start on the transport arrival date; a previous date is
    # an explicitly priced extra-night repair, rather than an unchecked increase.
    nominal_checkin = datetime.combine(arrive.date(), time(15), tzinfo=dz)
    extra_night = hotel_arrival < nominal_checkin - timedelta(hours=3)
    checkin = nominal_checkin - timedelta(days=int(extra_night))
    checkout = datetime.combine(back_depart.date(), time(12), tzinfo=dz)
    charged_nights = (checkout.date() - checkin.date()).days
    rooms = max(i.rooms, math.ceil(passengers / (4 if hi in (1, 2) else 2)))
    if rooms > 4:
        return None
    board = ["any", "breakfast", "all_inclusive", "breakfast"][hi]
    pet_limit = [0, 10, 20, None][hi]
    hotel_total = (
        night_rate * (100 + hi * 22) // 100 * charged_nights * rooms
        + (600 * charged_nights if i.pet_kg else 0)
    ) * 100
    hdetails = {
        "destination": dest,
        "adults": i.adults,
        "children_ages": i.children_ages,
        "room_capacity": 4 if hi in (1, 2) else 2,
        "checkin_at": checkin.isoformat(),
        "checkout_at": checkout.isoformat(),
        "nights": charged_nights,
        "requested_nights": i.nights,
        "extra_night": extra_night,
        "rooms": rooms,
        "capacity": rooms * (4 if hi in (1, 2) else 2),
        "meal": board,
        "refundable": hi in (1, 2),
        "pet_limit_kg": pet_limit,
        "reception_24h": hi in (1, 2),
        "location": "beach" if hi == 2 else "center",
        "mandatory_fees_included": True,
        "price_basis": "Все ночи, номера, обязательные сборы; питомец включён при наличии",
    }
    h = offer(
        "hotel",
        "Демо-отель "
        + ["Тихий двор", "Семейный берег", "Солнечный сад", "Городской свет"][hi],
        hotel_total,
        hdetails,
        [
            dest,
            checkin.date(),
            checkout.date(),
            i.adults,
            i.children_ages,
            i.pet_kg,
            rooms,
            hi,
        ],
        now,
    )
    airport_buffer = 120 if mode == "flight" else 40
    return_pickup = back_depart - timedelta(minutes=airport_buffer + transfer_minutes)
    child_seats = sum(age < 7 for age in i.children_ages)
    xdetails = {
        "destination": dest,
        "passengers": passengers,
        "refundable": True,
        "baggage_buffer_minutes": 40,
        "duration_minutes": transfer_minutes,
        "hotel_arrival": hotel_arrival.isoformat(),
        "return_pickup": return_pickup.isoformat(),
        "return_terminal_arrival": (
            return_pickup + timedelta(minutes=transfer_minutes)
        ).isoformat(),
        "terminal_buffer_minutes": airport_buffer,
        "pet_limit_kg": 0 if xi == 0 else 20,
        "child_seats": child_seats,
        "capacity": max(4, passengers),
        "private": xi == 1,
        "price_basis": "В обе стороны на всю группу; детские кресла и обязательные сборы включены",
    }
    xtotal = (
        1800 * (xi + 1) * 2 + child_seats * 1000 + (1000 if i.pet_kg else 0)
    ) * 100
    x = offer(
        "transfer",
        "Трансфер · " + ("индивидуальный" if xi else "общий"),
        xtotal,
        xdetails,
        [
            dest,
            arrive.isoformat(),
            back_depart.isoformat(),
            i.adults,
            i.children_ages,
            i.pet_kg,
            hi,
            xi,
        ],
        now,
    )
    total = sum(c["total_minor"] for c in (t, h, x))
    tradeoffs = []
    if not hdetails["refundable"]:
        tradeoffs.append("Тариф отеля без бесплатной отмены.")
    if not tdetails["refundable"]:
        tradeoffs.append("Транспорт по невозвратному демонстрационному тарифу.")
    if extra_night:
        tradeoffs.append(
            "Для раннего прибытия включена предыдущая ночь: её стоимость уже в корзине."
        )
    if room_ready > hotel_arrival and not extra_night:
        tradeoffs.append("Номер доступен с 15:00; до заселения есть ожидание.")
    if return_pickup > checkout:
        tradeoffs.append(
            "После 12:00 номер освобождается; до трансфера остаётся свободное время. Хранение багажа не подтверждено."
        )
    reasons = [
        "Все компоненты рассчитаны на всю группу.",
        f"Размещение: {charged_nights} ночей, {rooms} номер(а).",
    ]
    if i.pet_kg:
        reasons.append(
            f"В демоусловиях всех компонентов разрешён питомец до {i.pet_kg:g} кг."
        )
    if weather:
        reasons.append(
            f"Историческая средняя температура воздуха: {weather['temperature_mean_c']} °C; это не прогноз."
        )
    if i.warm:
        tradeoffs.append(
            "Температура моря неизвестна: сезонный подбор основан только на исторической температуре воздуха, условия купания не подтверждены."
        )
    return {
        "plan_id": stable_id("plan", [t["offer_id"], h["offer_id"], x["offer_id"]]),
        "destination": city_info(dest),
        "title": "Вариант поездки",
        "total_minor": total,
        "currency": "RUB",
        "components": [t, h, x],
        "timeline": [
            {
                "at": depart.isoformat(),
                "label": "Отправление",
                "detail": city_info(i.origin)["name"],
            },
            {
                "at": arrive.isoformat(),
                "label": "Прибытие",
                "detail": city_info(dest)["name"],
            },
            {
                "at": hotel_arrival.isoformat(),
                "label": "Трансфер до отеля",
                "detail": "40 минут на выход и багаж включены",
            },
            {
                "at": max(checkin, hotel_arrival).isoformat(),
                "label": "Заселение",
                "detail": h["title"],
            },
            {
                "at": min(checkout, return_pickup).isoformat(),
                "label": "Выезд из номера",
                "detail": "Фактический выезд может быть раньше 12:00",
            },
            {
                "at": return_pickup.isoformat(),
                "label": "Обратный трансфер",
                "detail": f"Буфер до отправления: {airport_buffer} минут",
            },
            {
                "at": back_depart.isoformat(),
                "label": "Обратное отправление",
                "detail": city_info(dest)["name"],
            },
            {
                "at": back_arrive.isoformat(),
                "label": "Возвращение",
                "detail": city_info(i.origin)["name"],
            },
        ],
        "validation": {},
        "reasons": reasons,
        "tradeoffs": tradeoffs,
        "useful_hours": round(
            (return_pickup - max(checkin, hotel_arrival)).total_seconds() / 3600, 1
        ),
        "weather": weather,
        "_comfort": hi * 3 + xi * 2 + int(ti == 2),
    }


def _aware_time(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp has no UTC offset")
    return parsed


def validate_trip(plan, intent, now=None):
    """Recompute constraints from component facts; absent required facts never pass."""
    try:
        return _validate_trip(plan, intent, now)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
        return {
            "passed": False,
            "issues": [
                issue(
                    "required_fields",
                    False,
                    "Обязательные поля или временные данные отсутствуют либо некорректны.",
                    status="unknown",
                )
            ],
        }


def _validate_trip(plan, intent, now):
    components = plan["components"]
    if len(components) != 3 or {row["kind"] for row in components} != {
        "transport",
        "hotel",
        "transfer",
    }:
        return {
            "passed": False,
            "issues": [
                issue(
                    "components",
                    False,
                    "Нужны ровно один транспорт, один отель и один трансфер в обе стороны.",
                )
            ],
        }
    parts = {row["kind"]: row for row in components}
    t, h, x = (parts[kind]["details"] for kind in ("transport", "hotel", "transfer"))
    checks = []

    def check(rule, condition, message, unknown=False):
        checks.append(
            issue(rule, condition, message, status="unknown" if unknown else None)
        )

    check(
        "money",
        type(plan["total_minor"]) is int
        and all(
            type(row["total_minor"]) is int
            and row["total_minor"] >= 0
            and row["currency"] == "RUB"
            for row in components
        ),
        "Цены всех компонентов — неотрицательные целые копейки в RUB.",
    )
    check(
        "total",
        plan["total_minor"] == sum(row["total_minor"] for row in components),
        "Сумма равна стоимости всех компонентов.",
    )
    check(
        "budget",
        intent.budget_rub is None or plan["total_minor"] <= intent.budget_rub * 100,
        "Полная стоимость должна укладываться в бюджет.",
    )
    destination = plan["destination"]["id"]
    route_ok = (
        intent.origin in ORIGINS
        and destination in TARIFFS
        and destination != intent.origin
        and (not intent.destinations or destination in intent.destinations)
        and all(
            dest in TARIFFS and dest != intent.origin for dest in intent.destinations
        )
    )
    check(
        "route",
        route_ok
        and t["origin"] == intent.origin
        and t["destination"] == destination
        and t["return_origin"] == destination
        and t["return_destination"] == intent.origin
        and h["destination"] == destination
        and x["destination"] == destination,
        "Маршрут всех компонентов соответствует отправлению, направлению и обратной дороге.",
    )
    if not route_ok:
        return {"passed": False, "issues": checks}
    mode = t["mode"]
    check(
        "transport_mode",
        mode in TERMINAL_BUFFERS
        and (intent.transport == "any" or mode == intent.transport),
        "Вид транспорта соответствует явному ограничению.",
    )
    check(
        "route_coverage",
        mode != "train" or destination in TRAIN_DESTINATIONS,
        "Маршрут и вид транспорта входят в демокаталог.",
    )
    check(
        "direct_transport",
        t["stops"] == 0,
        "Демокаталог поддерживает только прямой транспорт без пересадок.",
    )
    passengers = intent.adults + len(intent.children_ages)
    check(
        "child_ages",
        intent.children_count == len(intent.children_ages),
        "Возраст каждого ребёнка указан.",
    )
    check(
        "passengers",
        t["passengers"] == passengers
        and x["passengers"] == passengers
        and h["adults"] == intent.adults
        and h["children_ages"] == intent.children_ages,
        "Состав гостей одинаков во всех компонентах.",
    )
    rooms = h["rooms"]
    check(
        "rooms",
        type(rooms) is int
        and intent.rooms <= rooms <= 4
        and h["room_capacity"] in (2, 4),
        "Количество номеров в пределах каталога и не меньше запрошенного.",
    )
    check(
        "occupancy",
        h["capacity"] == rooms * h["room_capacity"] and h["capacity"] >= passengers,
        "Вместимость отеля соответствует группе и числу номеров.",
    )
    check(
        "transfer_capacity",
        type(x["capacity"]) is int and x["capacity"] >= passengers,
        "В трансфере есть место для каждого путешественника.",
    )
    check(
        "meal",
        intent.meal == "any" or h["meal"] == intent.meal,
        "Питание соответствует запросу.",
    )
    check(
        "location",
        intent.hotel_preference == "any" or h["location"] == intent.hotel_preference,
        "Расположение соответствует запросу.",
    )
    if intent.refundable:
        for kind, details in [("transport", t), ("hotel", h), ("transfer", x)]:
            policy = details.get("refundable")
            check(
                "cancellation_" + kind,
                policy is True,
                "Бесплатная отмена требуется для компонента " + kind + ".",
                unknown=policy is None,
            )
    if intent.pet_requested or intent.pet_kg is not None:
        check(
            "pet_weight",
            intent.pet_kg is not None,
            "Вес питомца нужен для проверки допуска.",
            unknown=intent.pet_kg is None,
        )
        if intent.pet_kg is not None:
            for kind, details in [("transport", t), ("hotel", h), ("transfer", x)]:
                limit = details.get("pet_limit_kg")
                check(
                    "pet_" + kind,
                    limit is not None and limit >= intent.pet_kg,
                    "Питомец разрешён в " + kind + ".",
                    unknown=limit is None,
                )
    cities, _ = load_reference()
    oz, dz = (
        ZoneInfo(cities[intent.origin]["timezone"]),
        ZoneInfo(cities[destination]["timezone"]),
    )
    depart = _aware_time(t["outbound_departure"]).astimezone(oz)
    arrive = _aware_time(t["outbound_arrival"]).astimezone(dz)
    back = _aware_time(t["return_departure"]).astimezone(dz)
    home = _aware_time(t["return_arrival"]).astimezone(oz)
    hotel_arrival = _aware_time(x["hotel_arrival"]).astimezone(dz)
    checkin = _aware_time(h["checkin_at"]).astimezone(dz)
    checkout = _aware_time(h["checkout_at"]).astimezone(dz)
    pickup = _aware_time(x["return_pickup"]).astimezone(dz)
    terminal = _aware_time(x["return_terminal_arrival"]).astimezone(dz)
    utc = lambda stamp: stamp.astimezone(timezone.utc)
    outbound_hours = (utc(arrive) - utc(depart)).total_seconds() / 3600
    return_hours = (utc(home) - utc(back)).total_seconds() / 3600
    check(
        "transport_timing",
        0 < outbound_hours <= 96
        and 0 < return_hours <= 96
        and abs(outbound_hours - t["duration_hours"]) < 1e-6
        and abs(return_hours - t["duration_hours"]) < 1e-6
        and depart < arrive < back < home,
        "Длительность обоих переездов рассчитана по UTC и совпадает с заявленной.",
    )
    check(
        "travel_time",
        intent.max_travel_hours is None
        or max(outbound_hours, return_hours) <= intent.max_travel_hours,
        "Длительность каждого переезда соответствует ограничению.",
    )
    check(
        "departure_date",
        depart.date() == intent.departure_date,
        "Фактическая локальная дата отправления совпадает с запросом.",
    )
    check(
        "date_coverage",
        DATE_FROM <= depart.date() <= DATE_TO and home.date() <= DATE_TO,
        "Все даты, включая прибытие домой, должны быть в окне 01.11.2026–31.01.2027.",
    )
    check(
        "return_deadline",
        intent.return_by is None or home.date() <= intent.return_by,
        "Возвращение домой должно быть не позже явно указанного конца диапазона.",
    )
    if now is not None:
        check("departure_time", utc(depart) > utc(now), "Отправление ещё не произошло.")
    duration = x["duration_minutes"]
    baggage_buffer = x["baggage_buffer_minutes"]
    check(
        "outbound_transfer",
        duration > 0
        and baggage_buffer >= BAGGAGE_BUFFER_MINUTES
        and utc(hotel_arrival)
        == utc(arrive) + timedelta(minutes=baggage_buffer + duration),
        "Прибытие в отель включает дорогу и независимый минимальный буфер получения багажа.",
    )
    check(
        "transfer_timing",
        utc(terminal) == utc(pickup) + timedelta(minutes=duration)
        and hotel_arrival < pickup,
        "Времена трансфера согласованы с его длительностью и проживанием.",
    )
    required_buffer = TERMINAL_BUFFERS.get(mode, 120)
    declared_buffer = x.get("terminal_buffer_minutes")
    check(
        "return_transfer",
        declared_buffer is not None
        and declared_buffer >= required_buffer
        and terminal <= back - timedelta(minutes=required_buffer)
        and terminal <= back - timedelta(minutes=declared_buffer),
        "Обратный трансфер прибывает минимум за 120 минут до рейса или за 40 минут до поезда.",
        unknown=declared_buffer is None,
    )
    span = (checkout.date() - checkin.date()).days
    extra = h["extra_night"]
    expected_start = arrive.date() - timedelta(days=int(extra))
    check(
        "stay",
        type(extra) is bool
        and type(h["nights"]) is int
        and span == h["nights"] == intent.nights + int(extra)
        and h["requested_nights"] == intent.nights
        and checkin.date() == expected_start
        and checkout.date()
        == back.date()
        == arrive.date() + timedelta(days=intent.nights)
        and max(checkin, hotel_arrival) < checkout <= back,
        "Оплачены ровно запрошенные ночи и только явно включённая предыдущая ночь; даты согласованы.",
    )
    check(
        "checkin_gap",
        checkin <= hotel_arrival + timedelta(hours=3),
        "Разрыв до заселения не более 3 часов; ночной разрыв требует предыдущую ночь.",
    )
    check(
        "late_reception",
        h.get("reception_24h") is True or 8 <= hotel_arrival.hour < 22,
        "Для ночного прибытия нужна подтверждённая круглосуточная стойка.",
    )
    check(
        "child_seat",
        type(x["child_seats"]) is int
        and x["child_seats"] >= sum(age < 7 for age in intent.children_ages),
        "Детские кресла учтены.",
    )
    return {"passed": all(row["status"] == "pass" for row in checks), "issues": checks}
