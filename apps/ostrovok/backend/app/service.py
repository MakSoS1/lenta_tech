"""Trip orchestration; models extract intent, trusted code controls all actions."""

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import re
import secrets
import sqlite3
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import ValidationError

from app.agent.offline_parser import parse_message
from app.domain.models import TripIntent
from app.domain import engine
from app.providers.reference import (
    NAMES,
    REFERENCE_DIR,
    city_info,
    load_reference,
    weather_context,
)
from app.storage import encode


def uid(prefix):
    return prefix + "_" + secrets.token_urlsafe(12)


def trace(state, tool, status, detail):
    state["action_trace"].append({"tool": tool, "status": status, "detail": detail})


def selected(state):
    return next(
        (p for p in state["plans"] if p["plan_id"] == state["selected_plan_id"]), None
    )


def apply_patch(current, patch):
    if not isinstance(patch, dict):
        raise HTTPException(422, "Изменение условий должно быть JSON-объектом.")
    if not set(patch).issubset(set(TripIntent.model_fields) | {"shift_days"}):
        raise HTTPException(422, "Изменение содержит неизвестные поля.")
    patch = deepcopy(patch)
    has_shift = "shift_days" in patch
    shift = patch.pop("shift_days", None)
    if has_shift and (type(shift) is not int or not -60 <= shift <= 60):
        raise HTTPException(422, "shift_days: нужно целое число от −60 до 60.")
    values = deepcopy(current) | patch
    for field in ("departure_date", "return_by"):
        if values.get(field) is None:
            continue
        value = values[field]
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise HTTPException(422, field + ": используйте дату YYYY-MM-DD.")
        try:
            values[field] = date.fromisoformat(value)
        except ValueError:
            raise HTTPException(422, "Дата отправления некорректна.")
    if shift is not None:
        if not values.get("departure_date"):
            raise HTTPException(422, "Сначала укажите дату для сдвига поездки.")
        try:
            values["departure_date"] += timedelta(days=shift)
            if values.get("return_by"):
                values["return_by"] += timedelta(days=shift)
        except OverflowError:
            raise HTTPException(422, "Сдвиг даты выходит за границы календаря.")
    if "pet_kg" in patch and "pet_requested" not in patch:
        values["pet_requested"] = patch["pet_kg"] is not None
    if (
        "children_ages" in patch
        and "children_count" not in patch
        and isinstance(patch["children_ages"], list)
    ):
        values["children_count"] = len(patch["children_ages"])
    for key in ("pet_kg", "max_travel_hours"):
        value = values.get(key)
        limit = 50 if key == "pet_kg" else 96
        if value is not None and (
            type(value) not in (int, float)
            or not 0 < value <= limit
            or not math.isfinite(value)
        ):
            raise HTTPException(422, f"{key}: нужно конечное положительное число.")
    if values.get("pet_kg") is not None and values["pet_kg"] < 0.1:
        raise HTTPException(422, "Вес питомца должен быть не меньше 0.1 кг.")
    try:
        result = TripIntent.model_validate(values, strict=True)
    except ValidationError as error:
        first = error.errors()[0]
        raise HTTPException(
            422, f"{'.'.join(str(x) for x in first['loc'])}: {first['msg']}"
        )
    return result.model_dump(mode="json")


class TripService:
    def __init__(self, store, clock, gateway):
        self.store = store
        self.clock = clock
        self.gateway = gateway

    def now(self):
        value = self.clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def capabilities(self):
        manifest = json.loads((REFERENCE_DIR / "manifest.json").read_text())
        return {
            "llm": {
                "mode": getattr(self.gateway, "mode", "opencode"),
                "primary_model": getattr(
                    self.gateway, "primary_model", "opencode/deepseek-v4.1-flash-free"
                ),
                "fallback_model": getattr(
                    self.gateway, "fallback_model", "opencode/glm-5.3-flash-free"
                ),
                "free_only": True,
            },
            "catalog": {
                "origins": [city_info(k) for k in ("moscow", "saint-petersburg")],
                "destinations": [city_info(k) for k in engine.TARIFFS],
                "date_from": engine.DATE_FROM.isoformat(),
                "date_to": engine.DATE_TO.isoformat(),
                "min_nights": 2,
                "max_nights": 14,
            },
            "data_sources": manifest,
        }

    @staticmethod
    def check_version(state, version):
        if state["version"] != version:
            raise HTTPException(
                409, "Поездка уже изменена. Обновите состояние и повторите действие."
            )

    @staticmethod
    def mutable(state):
        if state.get("order"):
            raise HTTPException(
                409, "Оформленный демозаказ неизменяем. Создайте новую поездку."
            )

    async def extract(self, state, message, explicit):
        # An explicit patch is an exact form operation; display copy is not intent.
        if explicit is not None:
            apply_patch(state["intent"], explicit)
            self.resolve_date_issue(state, explicit)
            state["llm"] = {
                "mode": getattr(self.gateway, "mode", "opencode"),
                "model": None,
                "used": False,
                "reason": "explicit_form_patch",
            }
            trace(
                state, "apply_form_patch", "ok",
                "Применены явно заданные условия формы.",
            )
            return deepcopy(explicit), []
        parsed = parse_message(message, state["reference_now"])
        self.resolve_date_issue(state, parsed["patch"])
        state.setdefault("field_issues", {}).update(parsed.get("field_issues", {}))
        state.setdefault("unresolved_constraints", [])
        if re.search(r"сними\s+неподдерживаемые\s+ограничения", message, re.I):
            state["unresolved_constraints"] = []
            trace(
                state,
                "constraint_guard",
                "ok",
                "Пользователь явно снял неподдерживаемые ограничения.",
            )
        else:
            state["unresolved_constraints"] = list(
                dict.fromkeys(
                    state["unresolved_constraints"]
                    + parsed.get("unresolved_constraints", [])
                )
            )
            if state["unresolved_constraints"]:
                trace(
                    state,
                    "constraint_guard",
                    "needs_clarification",
                    "Сохранены неподтверждённые жёсткие ограничения: "
                    + "; ".join(state["unresolved_constraints"]),
                )
        try:
            llm = await self.gateway.extract(
                message, deepcopy(state["intent"]), state["reference_now"]
            )
        except Exception:
            llm = {"patch": {}, "model": None, "used": False, "reason": "model_error"}
        if not isinstance(llm, dict):
            llm = {
                "patch": {},
                "model": None,
                "used": False,
                "reason": "invalid_model_output",
            }
        used = llm.get("used") is True
        patch = llm.get("patch", {}) if used else {}
        if used:
            try:
                apply_patch(state["intent"], patch)
            except HTTPException:
                used = False
                llm = {**llm, "reason": "invalid_model_output"}
        state["llm"] = {
            "mode": getattr(self.gateway, "mode", "opencode"),
            "model": llm.get("model"),
            "used": used,
            "reason": None if used else llm.get("reason", "model_unavailable"),
        }
        trace(
            state,
            "extract_intent",
            "ok" if used else "unavailable",
            "Условия извлечены языковой моделью."
            if used
            else "Живой AI недоступен: " + str(state["llm"]["reason"]) + ".",
        )
        warnings = []
        if not used:
            patch = parsed["patch"]
            warnings = [
                "Живой AI недоступен. Использован ограниченный parser; условия формы применяются напрямую."
            ]
            if not explicit:
                warnings.extend(parsed["warnings"])
            trace(
                state,
                "limited_parser",
                "ok" if parsed["recognized"] or explicit else "needs_clarification",
                f"Распознаны поля: {', '.join(sorted(patch)) or 'нет'}.",
            )
        patch = deepcopy(patch)
        # Unsupported explicit geography is an application-owned coverage boundary.
        # A schema-valid model omission must not turn it into inspiration.
        for field in ("origin", "destinations"):
            current = state["intent"].get(field)
            detected = parsed["patch"].get(field)

            def unsupported(value):
                values = value if isinstance(value, list) else [value]
                return any(
                    isinstance(v, str) and v.startswith("unsupported:")
                    for v in values
                )

            if unsupported(detected) or unsupported(current):
                patch[field] = detected if field in parsed["patch"] else current
        # A model may not remove an existing transport lock without an explicit request.
        if (
            state["intent"].get("lock_transport")
            and patch.get("lock_transport") is False
            and (explicit or {}).get("lock_transport") is not False
        ):
            if not re.search(
                r"разблок|сними.*фикс|можно.*поменять|unlock", message, re.I
            ):
                patch.pop("lock_transport", None)
        if explicit is not None:
            if not isinstance(explicit, dict):
                raise HTTPException(422, "patch должен быть JSON-объектом.")
            patch.update(explicit)
            trace(
                state,
                "apply_form_patch",
                "ok",
                "Применены явно заданные условия формы.",
            )
        return patch, warnings

    @staticmethod
    def resolve_date_issue(state, patch):
        issues = state.setdefault("field_issues", {})
        # Migrate persisted pre-fix date blockers without touching hard conditions.
        legacy = {
            "Нужна точная дата отправления вместо месяца.",
            "Некорректная явно указанная дата или диапазон поездки.",
        }
        remaining = []
        for value in state.get("unresolved_constraints", []):
            if value in legacy:
                issues["departure_date"] = value
            else:
                remaining.append(value)
        state["unresolved_constraints"] = remaining
        if patch.get("departure_date"):
            issues.pop("departure_date", None)

    async def create(self, owner, message, explicit=None):
        now = self.now()
        base = TripIntent().model_dump(mode="json")
        base = apply_patch(base, self.store.preferences(owner))
        state = {
            "trip_id": uid("trip"),
            "version": 1,
            "status": "needs_clarification",
            "intent": base,
            "reference_now": now.astimezone(ZoneInfo("Europe/Moscow")).isoformat(),
            "origin_timezone": "Europe/Moscow",
            "plans": [],
            "selected_plan_id": None,
            "questions": [],
            "assumptions": [],
            "messages": [],
            "delta": None,
            "quote": None,
            "order": None,
            "action_trace": [],
            "llm": {
                "mode": getattr(self.gateway, "mode", "opencode"),
                "model": None,
                "used": False,
                "reason": None,
            },
            "warnings": [],
            "locked_component_ids": [],
            "service_requests": [],
        }
        patch, warnings = await self.extract(state, message, explicit)
        state["intent"] = apply_patch(base, patch)
        if "adults" not in patch:
            state["assumptions"].append(
                "Число взрослых не указано: по умолчанию один взрослый."
            )
        if "nights" not in patch:
            state["assumptions"].append(
                "Длительность не указана: по умолчанию 7 ночей."
            )
        self.unlimited_budget(state, patch, message)
        state["warnings"] = warnings
        self.replan(state, now)
        self.conversation(state, message)
        self.store.save(state, owner, now)
        return state

    @staticmethod
    def unlimited_budget(state, patch, message):
        marker = "Бюджет без ограничения явно подтверждён пользователем."
        if "budget_rub" in patch:
            state["assumptions"] = [x for x in state["assumptions"] if x != marker]
            if patch["budget_rub"] is None:
                state["assumptions"].append(marker)
        elif re.search(
            r"без\s*ограничени[йя]\s*(?:по\s*)?бюджет|бюджет\s*не\s*ограничен",
            message,
            re.I,
        ):
            state["intent"]["budget_rub"] = None
            if marker not in state["assumptions"]:
                state["assumptions"].append(marker)

    async def change(self, trip_id, owner, version, message, explicit=None):
        old = self.store.get(trip_id, owner)
        self.check_version(old, version)
        self.mutable(old)
        state = deepcopy(old)
        start = len(state["action_trace"])
        now = self.now()
        state["reference_now"] = now.astimezone(
            ZoneInfo(state["origin_timezone"])
        ).isoformat()
        patch, warnings = await self.extract(state, message, explicit)
        state["intent"] = apply_patch(old["intent"], patch)
        state["assumptions"] = [
            x
            for x in state["assumptions"]
            if not ("adults" in patch and x.startswith("Число взрослых"))
            and not ("nights" in patch and x.startswith("Длительность"))
        ]
        self.unlimited_budget(state, patch, message)
        if state["intent"]["lock_transport"]:
            if not state["locked_component_ids"]:
                plan = selected(old)
                state["locked_component_ids"] = (
                    [
                        c["offer_id"]
                        for c in plan["components"]
                        if c["kind"] == "transport"
                    ]
                    if plan
                    else []
                )
        else:
            state["locked_component_ids"] = []
        state["warnings"] = warnings
        state["version"] += 1
        state["quote"] = None
        self.replan(state, now)
        self.delta(old, state)
        self.conversation(
            state,
            message
            or (
                "Условия обновлены через форму."
                if explicit
                else "Проверить условия поездки."
            ),
        )
        self.store.save(state, owner, now, version, start)
        return state

    def questions(self, state):
        i = state["intent"]
        out = []
        if i["origin"] not in ("moscow", "saint-petersburg"):
            out.append(
                {
                    "key": "origin",
                    "label": "Откуда отправляемся? Демокаталог поддерживает Москву и Санкт-Петербург.",
                    "suggestions": ["Из Москвы", "Из Санкт-Петербурга"],
                }
            )
        if not i["departure_date"] or state.get("field_issues", {}).get("departure_date"):
            out.append(
                {
                    "key": "departure_date",
                    "label": state.get("field_issues", {}).get(
                        "departure_date", "Укажите точную дату отправления."
                    ),
                    "suggestions": ["10 ноября 2026", "15 ноября 2026"],
                }
            )
        if i["budget_rub"] is None and not any(
            x.startswith("Бюджет без ограничения") for x in state["assumptions"]
        ):
            out.append(
                {
                    "key": "budget_rub",
                    "label": "Какой бюджет на всю поездку в рублях?",
                    "suggestions": ["Бюджет 100000 рублей", "Бюджет 180000 рублей"],
                }
            )
        if i["children_count"] != len(i["children_ages"]):
            out.append(
                {
                    "key": "children_ages",
                    "label": "Укажите возраст каждого ребёнка: неизвестный возраст не заменяется нулём.",
                    "suggestions": ["Ребёнок 7 лет", "Без детей"],
                }
            )
        if i.get("pet_requested") and i["pet_kg"] is None:
            out.append(
                {
                    "key": "pet_kg",
                    "label": "Сколько весит питомец? Без веса нельзя проверить условия всех компонентов.",
                    "suggestions": ["Собака 8 кг", "Без питомца"],
                }
            )
        if state.get("unresolved_constraints"):
            out.append(
                {
                    "key": "unresolved_constraints",
                    "label": "Не могу подтвердить жёсткие ограничения: "
                    + "; ".join(state["unresolved_constraints"])
                    + ". Уточните их или явно снимите неподдерживаемые ограничения.",
                    "suggestions": ["Сними неподдерживаемые ограничения"],
                }
            )
        return out

    def replan(self, state, now):
        state["quote"] = None
        state["questions"] = self.questions(state)
        demo = "Цены и наличие синтетические: демонстрация без реального бронирования и оплаты."
        if demo not in state["warnings"]:
            state["warnings"].append(demo)
        if state["questions"]:
            state.update(status="needs_clarification", plans=[], selected_plan_id=None)
            trace(
                state,
                "clarify_intent",
                "needs_clarification",
                f"Нужно уточнить: {', '.join(x['key'] for x in state['questions'])}.",
            )
            return
        intent = TripIntent.model_validate(state["intent"])
        result = engine.build_plans(intent, now)
        plans = result["plans"]
        trace(
            state,
            "search_demo_catalog",
            "ok" if plans else "no_options",
            f"Рассчитаны транспорт туда-обратно, все ночи отеля и оба трансфера; найдено вариантов: {len(plans)}.",
        )
        if intent.lock_transport:
            locked = state["locked_component_ids"]
            plans = self.locked_plans(intent, now, plans, locked)
            if not plans:
                state.update(status="needs_resolution", plans=[], selected_plan_id=None)
                state["questions"] = [
                    {
                        "key": "lock_transport",
                        "label": "Зафиксированный транспорт несовместим с новыми условиями. Снимите фиксацию или верните прежние параметры.",
                        "suggestions": ["Разблокируй транспорт"],
                    }
                ]
                trace(
                    state,
                    "preserve_transport",
                    "needs_resolution",
                    "Зафиксированный компонент не заменён. Для пересборки требуется явное снятие фиксации.",
                )
                return
            trace(
                state,
                "preserve_transport",
                "ok",
                "Сохранён тот же идентификатор транспорта; совместимые отели и трансферы пересчитаны.",
            )
        previous = state["selected_plan_id"]
        state["plans"] = plans
        state["selected_plan_id"] = (
            previous
            if any(p["plan_id"] == previous for p in plans)
            else plans[0]["plan_id"]
            if plans
            else None
        )
        state["status"] = "ready" if plans else "no_options"
        if plans:
            trace(
                state,
                "validate_trip",
                "ok",
                f"Проверены бюджет, вместимость, возраст детей, питомец, заселение и обратный трансфер: {len(plans)} полных корзин.",
            )
            trace(
                state,
                "rank_trips",
                "ok",
                "Сравнены полная стоимость, комфорт и полезное время; выбрано не более трёх разных вариантов.",
            )
        else:
            reasons = [x["message"] for x in result["rejections"]]
            if not reasons:
                reasons = [
                    "Направление или сочетание условий не входит в демонстрационное покрытие."
                ]
            state["warnings"].extend(dict.fromkeys(reasons))
            trace(
                state, "validate_trip", "no_options", "; ".join(dict.fromkeys(reasons))
            )

    @staticmethod
    def locked_plans(intent, now, ranked, locked):
        if not locked:
            return []
        matches = [
            p
            for p in ranked
            if all(any(c["offer_id"] == key for c in p["components"]) for key in locked)
        ]
        if matches or not ranked:
            return matches
        # Rank selection can hide an available fixed transport. Search the same
        # finite candidate inventory before declaring an incompatibility.
        cities, _ = load_reference()
        candidates = []
        for dest in intent.destinations or list(engine.TARIFFS):
            if dest not in engine.TARIFFS or dest == intent.origin:
                continue
            weather = weather_context(dest, intent.departure_date.month)
            if intent.warm and (
                dest not in ("sochi", "antalya", "hurghada")
                or not weather
                or weather["temperature_mean_c"] < 20
            ):
                continue
            for ti in range(3):
                for hi in range(4):
                    for xi in range(2):
                        p = engine._candidate(
                            intent, dest, ti, hi, xi, cities, weather, now
                        )
                        if p is None or not all(
                            any(c["offer_id"] == key for c in p["components"])
                            for key in locked
                        ):
                            continue
                        p["validation"] = engine.validate_trip(p, intent, now=now)
                        if p["validation"]["passed"]:
                            candidates.append(p)
        for p in sorted(candidates, key=lambda p: p["total_minor"])[:3]:
            p.pop("_comfort", None)
            p["title"] = "С тем же транспортом"
            matches.append(p)
        return matches

    @staticmethod
    def delta(old, state):
        before = selected(old)
        after = selected(state)
        old_ids = {x["offer_id"] for x in before["components"]} if before else set()
        new_ids = {x["offer_id"] for x in after["components"]} if after else set()
        changed = sorted(
            k for k in state["intent"] if state["intent"][k] != old["intent"].get(k)
        )
        price = (
            after["total_minor"] - before["total_minor"] if before and after else None
        )
        summary = (
            ["Изменены условия: " + ", ".join(changed) + "."]
            if changed
            else ["Условия поездки сохранены."]
        )
        if price is not None:
            summary.append(f"Изменение полной стоимости: {price / 100:+,.0f} ₽.")
        if old_ids & new_ids:
            summary.append(f"Сохранено компонентов: {len(old_ids & new_ids)}.")
        state["delta"] = {
            "changed_fields": changed,
            "preserved_offer_ids": sorted(old_ids & new_ids),
            "invalidated_offer_ids": sorted(old_ids - new_ids),
            "price_delta_minor": price,
            "summary": summary,
        }

    @staticmethod
    def conversation(state, message):
        if message:
            state["messages"].append({"role": "user", "text": message})
        if state["status"] in ("needs_clarification", "needs_resolution"):
            answer = " ".join(q["label"] for q in state["questions"])
        elif state["status"] == "ready":
            plan = selected(state)
            answer = f"Собрано вариантов: {len(state['plans'])}. {plan['destination']['name']}, {state['intent']['nights']} ночей: {plan['total_minor'] / 100:,.0f} ₽ за всю группу, транспорт, отель и оба трансфера. Это демонстрационная корзина."
        else:
            answer = "Для текущих условий подходящих вариантов в демокаталоге нет. " + (
                " ".join(state["warnings"][-2:])
            )
        state["messages"].append({"role": "assistant", "text": answer})

    def select(self, trip_id, owner, version, plan_id):
        state = self.store.get(trip_id, owner)
        self.check_version(state, version)
        self.mutable(state)
        if not any(p["plan_id"] == plan_id for p in state["plans"]):
            raise HTTPException(
                422, "Выбранный вариант не принадлежит текущей поездке."
            )
        start = len(state["action_trace"])
        state["selected_plan_id"] = plan_id
        state["quote"] = None
        state["version"] += 1
        trace(
            state,
            "select_plan",
            "ok",
            "Выбран вариант " + selected(state)["destination"]["name"] + ".",
        )
        self.store.save(state, owner, self.now(), version, start)
        return state

    def quote(self, trip_id, owner, version):
        state = self.store.get(trip_id, owner)
        self.check_version(state, version)
        self.mutable(state)
        if state["status"] != "ready" or not selected(state):
            raise HTTPException(
                409,
                "Для проверки цены сначала соберите и выберите совместимый вариант.",
            )
        start = len(state["action_trace"])
        now = self.now()
        wanted = state["selected_plan_id"]
        self.replan(state, now)
        if state["status"] != "ready" or not any(
            p["plan_id"] == wanted for p in state["plans"]
        ):
            raise HTTPException(
                409, "Выбранный вариант больше не доступен. Обновите условия поездки."
            )
        state["selected_plan_id"] = wanted
        state["version"] += 1
        plan = selected(state)
        expiry = min(
            now + timedelta(minutes=5),
            *(datetime.fromisoformat(c["expires_at"]) for c in plan["components"]),
        )
        state["quote"] = {
            "quote_id": uid("quote"),
            "plan_id": wanted,
            "plan_version": state["version"],
            "total_minor": plan["total_minor"],
            "currency": "RUB",
            "expires_at": expiry.isoformat(),
            "requires_confirmation": True,
        }
        trace(
            state,
            "refresh_quote",
            "ok",
            f"Демотарифы и сроки обновлены; итог {plan['total_minor']} копеек. Требуется явное подтверждение.",
        )
        self.store.save(state, owner, now, version, start)
        return state

    def purchase(self, trip_id, owner, body, key):
        now = self.now()
        digest = hashlib.sha256(
            encode({"trip_id": trip_id, "body": body}).encode()
        ).hexdigest()
        try:
            with self.store.transaction(write=True) as db:
                # Ownership and completed idempotency precede ALL stale/expiry tests.
                state = self.store.owned(db, trip_id, owner)
                if not key or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", key):
                    raise HTTPException(
                        422, "Нужен корректный Idempotency-Key длиной до 128 символов."
                    )
                previous = db.execute(
                    "SELECT request_hash,response FROM idempotency WHERE owner=? AND key=?",
                    (owner, key),
                ).fetchone()
                if previous:
                    if previous["request_hash"] != digest:
                        raise HTTPException(
                            409, "Этот ключ уже использован для другого запроса."
                        )
                    return json.loads(previous["response"])
                self.mutable(state)
                self.check_version(state, body["expected_version"])
                if body["confirmed"] is not True:
                    raise HTTPException(
                        422, "Подтвердите состав поездки и демонстрационную сумму."
                    )
                quote = state.get("quote")
                plan = selected(state)
                if (
                    not quote
                    or quote["quote_id"] != body["quote_id"]
                    or quote["plan_version"] != state["version"]
                    or not plan
                    or quote["plan_id"] != plan["plan_id"]
                ):
                    raise HTTPException(
                        409,
                        "Цена или выбранный вариант изменились. Проверьте итог заново.",
                    )
                if datetime.fromisoformat(quote["expires_at"]) <= now:
                    raise HTTPException(
                        409, "Срок цены истёк. Проверьте итоговую сумму заново."
                    )
                if (
                    body["total_minor"] != quote["total_minor"]
                    or plan["total_minor"] != quote["total_minor"]
                    or plan["total_minor"]
                    != sum(c["total_minor"] for c in plan["components"])
                ):
                    raise HTTPException(
                        409, "Подтверждённая сумма не совпадает с актуальной корзиной."
                    )
                if not engine.validate_trip(
                    plan, TripIntent.model_validate(state["intent"]), now=now
                )["passed"]:
                    raise HTTPException(409, "Корзина не прошла повторную проверку.")
                start = len(state["action_trace"])
                version = state["version"]
                order = {
                    "order_id": uid("order"),
                    "trip_id": trip_id,
                    "quote_id": quote["quote_id"],
                    "total_minor": quote["total_minor"],
                    "currency": "RUB",
                    "status": "simulated_confirmed",
                    "created_at": now.isoformat(),
                    "plan": deepcopy(plan),
                }
                db.execute(
                    "INSERT INTO orders(order_id,owner,trip_id,quote_id,body) VALUES(?,?,?,?,?)",
                    (
                        order["order_id"],
                        owner,
                        trip_id,
                        quote["quote_id"],
                        encode(order),
                    ),
                )
                state.update(order=order, status="ordered", version=version + 1)
                trace(
                    state,
                    "demo_order",
                    "ok",
                    "Создан один неизменяемый демозаказ; реальные поставщики не уведомлены, деньги не списаны.",
                )
                state["messages"].append(
                    {
                        "role": "assistant",
                        "text": f"Демозаказ {order['order_id']} создан. Итог {order['total_minor'] / 100:,.0f} ₽. Реального бронирования и списания не было.",
                    }
                )
                self.store.persist(db, state, owner, now, version, start)
                db.execute(
                    "INSERT INTO idempotency(owner,key,request_hash,trip_id,order_id,response) VALUES(?,?,?,?,?,?)",
                    (owner, key, digest, trip_id, order["order_id"], encode(state)),
                )
                return state
        except sqlite3.IntegrityError:
            raise HTTPException(
                409, "Для этой поездки или цены демозаказ уже оформлен."
            )

    def service_request(self, trip_id, owner, kind, message):
        with self.store.transaction(write=True) as db:
            state = self.store.owned(db, trip_id, owner)
            if kind != "early_checkin":
                raise HTTPException(
                    422, "Поддерживается только запрос раннего заселения."
                )
            if not selected(state) and not state.get("order"):
                raise HTTPException(409, "Сначала выберите вариант с отелем.")
            existing = next(
                (request for request in state["service_requests"]
                 if request["kind"] == kind),
                None,
            )
            if existing:
                return existing
            value = {
                "kind": kind,
                "request_id": uid("request"),
                "status": "requested_demo",
                "message": "Запрос раннего заселения сохранён в деморежиме. Отель не уведомлён, подтверждение не получено.",
            }
            db.execute(
                "INSERT INTO service_requests VALUES(?,?,?,?,?)",
                (
                    value["request_id"],
                    owner,
                    trip_id,
                    encode({"kind": kind, "user_message": message, **value}),
                    self.now().isoformat(),
                ),
            )
            return value

    def preferences(self, owner, value=None):
        if value is None:
            return self.store.preferences(owner)
        if not isinstance(value, dict) or not set(value).issubset(
            {"meal", "refundable", "hotel_preference"}
        ):
            raise HTTPException(
                422, "Можно сохранить только питание, возврат и расположение отеля."
            )
        apply_patch(TripIntent().model_dump(mode="json"), value)
        return self.store.set_preferences(owner, value)
