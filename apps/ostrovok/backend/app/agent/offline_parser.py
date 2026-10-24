"""Finite, explicit fallback parser; unrepresented hard constraints stay unresolved."""

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ALIASES = {
    "moscow": r"москв\w*|moscow",
    "saint-petersburg": r"санкт[- ]?петербург\w*|петербург\w*|питер\w*|спб|saint petersburg",
    "kazan": r"казан\w*|kazan",
    "sochi": r"сочи|sochi",
    "kaliningrad": r"калининград\w*|kaliningrad",
    "yerevan": r"ереван\w*|yerevan",
    "istanbul": r"стамбул\w*|istanbul",
    "antalya": r"антал(?:ь|и)\w*|antalya",
    "hurghada": r"хургад\w*|hurghada",
}
DESTINATIONS = [city for city in ALIASES if city != "moscow"]
MONTHS = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "апрел": 4,
    "мая": 5,
    "май": 5,
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "октябр": 10,
    "ноябр": 11,
    "декабр": 12,
}
MONTH_PATTERN = "(?:" + "|".join(MONTHS) + r")[а-я]*"
NUMBERS = {
    "один": 1,
    "одна": 1,
    "одну": 1,
    "два": 2,
    "две": 2,
    "двое": 2,
    "двумя": 2,
    "три": 3,
    "трое": 3,
    "тремя": 3,
    "четыре": 4,
    "четверо": 4,
    "четырьмя": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
    "четырнадцать": 14,
}
NUMBER_PATTERN = r"(\d+|" + "|".join(NUMBERS) + ")"
CHILD_PATTERN = r"(?:ребен\w*|дет(?:и|ей|ьми|ям|ях))"
NON_PLACE_WORDS = {
    "центре",
    "центр",
    "стиле",
    "любом",
    "любой",
    "пределах",
    "бюджете",
    "бюджет",
    "отеле",
    "отель",
    "номере",
    "номер",
    "стоимость",
    "цену",
    "цене",
    "пути",
    "дороге",
    "обе",
    "обоих",
    "одну",
    "одном",
    "один",
    "двух",
    "троем",
    "вдвоем",
    "итоге",
    "этом",
    "этой",
    "первую",
    "первой",
    "конце",
    "начале",
    "середине",
    "течение",
    "отпуск",
    "отпуске",
    "поездке",
    "поездку",
    "пятницу",
    "субботу",
    "воскресенье",
    "понедельник",
    "выходные",
    "выходной",
    "город",
    "городе",
    "городах",
    "время",
    "день",
    "дни",
    "ночь",
    "салоне",
    "багаже",
    "стране",
    "плане",
    "составе",
    "любую",
    "любое",
    "прежние",
    "все",
    "неделю",
    "недели",
    "этот",
    "этого",
    "нее",
    "него",
    "любой",
    "варианте",
}


def number(value):
    return int(value) if value.isdigit() else NUMBERS.get(value)


def _negative(text, match):
    prefix = text[max(0, match.start() - 30) : match.start()]
    return bool(
        re.search(
            r"(?:\bне\s+(?:(?:нуж[а-я]*|надо|хочу|нужен)\s+)?(?:в\s+)?|\bбез\s+|\bкроме\s+)$",
            prefix,
        )
    )


def _geography(text, patch):
    positive, excluded = [], set()
    origin_spans = []
    for city, pattern in ALIASES.items():
        for match in re.finditer(r"\b(?:" + pattern + r")\b", text):
            prefix = text[max(0, match.start() - 22) : match.start()]
            if re.search(r"(?:\bиз|отправление|вылет(?:аю)? из)\s*$", prefix):
                patch["origin"] = city
                origin_spans.append(match.span())
            elif _negative(text, match) or re.match(
                r"\s+не\s+(?:подход\w*|нуж\w*)", text[match.end() :]
            ):
                excluded.add(city)
            elif city not in positive:
                positive.append(city)
    # Explicit unknown locations are not converted into open-ended inspiration.
    for match in re.finditer(r"\b(из|во?)\s+([а-яa-z][а-яa-z-]*)", text):
        prep, token = match.group(1), match.group(2)
        if any(re.fullmatch(pattern, token) for pattern in ALIASES.values()):
            continue
        if token in NON_PLACE_WORDS or any(token.startswith(stem) for stem in MONTHS):
            continue
        if prep == "из":
            patch["origin"] = "unsupported:" + token
        elif not re.search(
            r"\bне\s*$", text[max(0, match.start() - 8) : match.start()]
        ):
            positive.append("unsupported:" + token)
    if positive or excluded:
        candidates = positive if positive else DESTINATIONS
        patch["destinations"] = list(
            dict.fromkeys(city for city in candidates if city not in excluded)
        )
        # Do not turn excluding every finite candidate into an unrestricted query.
        if not patch["destinations"]:
            patch["destinations"] = ["unsupported:excluded-all"]


def _dates(text, current, patch, warnings, unresolved):
    def month_number(value):
        return next(
            value_num for stem, value_num in MONTHS.items() if value.startswith(stem)
        )

    def resolve_range(start, end):
        span = (end - start).days
        if not 2 <= span <= 14:
            raise ValueError("Диапазон должен включать от 2 до 14 ночей.")
        patch.update(
            departure_date=start.isoformat(), return_by=end.isoformat(), nights=span
        )

    try:
        iso_range = re.search(
            r"\bс\s*(20\d{2}-\d{2}-\d{2})\s*(?:по|до|—|–|-)\s*(20\d{2}-\d{2}-\d{2})\b",
            text,
        )
        named_range = re.search(
            r"\bс\s*(\d{1,2})\s*("
            + MONTH_PATTERN
            + r")?\s*(20\d{2})?\s*(?:по|до|—|–|-)\s*(\d{1,2})\s*("
            + MONTH_PATTERN
            + r")(?:\s*(20\d{2}))?",
            text,
        )
        if iso_range:
            resolve_range(
                date.fromisoformat(iso_range[1]), date.fromisoformat(iso_range[2])
            )
            return
        if named_range:
            first_day, first_month, first_year, last_day, last_month, last_year = (
                named_range.groups()
            )
            m1, m2 = month_number(first_month or last_month), month_number(last_month)
            y1 = (
                int(first_year)
                if first_year
                else current.year + int(m1 < current.month)
            )
            if last_year and not first_year:
                y1 = int(last_year) - int(m2 < m1)
            y2 = int(last_year) if last_year else y1 + int(m2 < m1)
            resolve_range(date(y1, m1, int(first_day)), date(y2, m2, int(last_day)))
            return
        iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
        named = re.search(
            r"(\d{1,2})\s*(" + MONTH_PATTERN + r")(?:\s*(20\d{2}))?", text
        )
        if iso:
            patch["departure_date"] = date.fromisoformat(iso[1]).isoformat()
        elif named:
            month = month_number(named[2])
            year = (
                int(named[3]) if named[3] else current.year + int(month < current.month)
            )
            patch["departure_date"] = date(year, month, int(named[1])).isoformat()
        elif re.search(r"\bзавтра\b", text):
            patch["departure_date"] = (current + timedelta(days=1)).isoformat()
        elif re.search(r"\b\w*выходн\w*", text):
            days = (5 - current.weekday()) % 7
            if "следующ" in text and days == 0:
                days = 7
            patch.update(
                departure_date=(current + timedelta(days=days)).isoformat(), nights=2
            )
        elif any(re.search(r"\b" + stem, text) for stem in MONTHS):
            warnings.append("Указан месяц: выберите точную дату в форме.")
            unresolved.append("Нужна точная дата отправления вместо месяца.")
    except ValueError:
        warnings.append(
            "Дата или диапазон некорректны: проверьте начало, конец, месяц и год; поддерживаются 2–14 ночей."
        )
        unresolved.append("Некорректная явно указанная дата или диапазон поездки.")
        patch.pop("departure_date", None)
        patch.pop("return_by", None)


def parse_message(message, reference_now):
    text = message.lower().replace("ё", "е")
    patch, warnings, unresolved = {}, [], []
    current = (
        datetime.fromisoformat(reference_now)
        .astimezone(ZoneInfo("Europe/Moscow"))
        .date()
    )
    _geography(text, patch)
    adults = re.search(NUMBER_PATTERN + r"\s*(?:взросл\w*|человек\w*)", text)
    if adults:
        patch["adults"] = number(adults[1])
    if re.search(r"\b(?:вдвоем|на двоих)\b", text):
        patch["adults"] = 2
    if re.search(r"\b(?:один|одна)\s*(?:еду|поеду)|еду\s*(?:один|одна)\b", text):
        patch["adults"] = 1
    ages = []
    for match in re.finditer(
        CHILD_PATTERN
        + r"\s*[:\-]?\s*(\d{1,2}(?:\s*(?:,|и)\s*\d{1,2})*)\s*(?:лет|года?|годик)",
        text,
    ):
        ages.extend(int(value) for value in re.findall(r"\d+", match[1]))
    count = re.search(NUMBER_PATTERN + r"\s*" + CHILD_PATTERN, text)
    if ages:
        patch.update(
            children_ages=ages,
            children_count=max(len(ages), number(count[1]) if count else 0),
        )
    elif re.search(CHILD_PATTERN, text):
        patch.update(children_count=number(count[1]) if count else 1, children_ages=[])
    if re.search(r"\bбез\s*(?:детей|ребенка)", text):
        patch.update(children_count=0, children_ages=[])
    pet_word = re.search(r"\b(?:собак\w*|питом\w*|кошк\w*)", text)
    if pet_word:
        pet = re.search(
            r"(?:собак\w*|питом\w*|кошк\w*)[^\d]{0,18}(\d+(?:[.,]\d+)?)\s*кг", text
        )
        patch.update(
            pet_requested=True, pet_kg=float(pet[1].replace(",", ".")) if pet else None
        )
    if re.search(r"\bбез\s*(?:собак\w*|питом\w*|кошк\w*)", text):
        patch.update(pet_requested=False, pet_kg=None)
    # Prefer explicitly monetary candidates; ignore durations and date-range ends.
    money = []
    for match in re.finditer(
        r"(?:\bбюджет\s*(?:до|теперь|не больше|:)?|\bне дороже|\bдо|\bмаксимум)\s*(\d[\d ]*(?:[.,]\d+)?)\s*(тыс\w*|[кk]\b|руб\w*|₽)?",
        text,
    ):
        suffix = match[2] or ""
        tail = text[match.end() :]
        if not suffix and (
            re.match(r"\s*(?:час|минут|дн|ноче|кг)", tail)
            or any(re.match(r"\s*" + stem, tail) for stem in MONTHS)
        ):
            continue
        value = float(match[1].replace(" ", "").replace(",", "."))
        if suffix.startswith("тыс") or suffix in ("к", "k"):
            value *= 1000
        if value >= 1000:
            money.append((bool(suffix), int(value)))
    if money:
        patch["budget_rub"] = max(
            enumerate(money), key=lambda row: (row[1][0], row[0])
        )[1][1]
    nights = re.search(
        r"\bна\s*" + NUMBER_PATTERN + r"\s*(?:ноч\w*|дн\w*|сут\w*)", text
    )
    if nights and not re.search(
        r"позже|раньше", text[nights.end() : nights.end() + 12]
    ):
        patch["nights"] = number(nights[1])
    if re.search(r"\bна\s*(?:одну\s*)?недел", text):
        patch["nights"] = 7
    if "на две недели" in text:
        patch["nights"] = 14
    shift = re.search(
        r"(?:на\s*)?" + NUMBER_PATTERN + r"\s*(?:дня|дней|день)\s*(позже|раньше)", text
    )
    if shift:
        patch["shift_days"] = number(shift[1]) * (1 if shift[2] == "позже" else -1)
    _dates(text, current, patch, warnings, unresolved)
    if re.search(r"без\s*долг\w*\s*перелет", text):
        patch["max_travel_hours"] = 6
    duration = re.search(
        r"(?:перелет\w*|дорога|ехать|лететь)[^\d]{0,18}(\d+(?:[.,]\d+)?)\s*час", text
    )
    if duration:
        patch["max_travel_hours"] = float(duration[1].replace(",", "."))
    if re.search(r"тепл\w*\s*(?:мор\w*|пляж\w*)", text):
        patch["warm"] = True
    modes = {}
    for mode, pattern in [
        ("train", r"\b(?:поезд\w*|жд|ж/д)\b"),
        ("flight", r"\b(?:самолет\w*|авиа\w*|перелет\w*)\b"),
    ]:
        mentions = list(re.finditer(pattern, text))
        if mentions:
            modes[mode] = not _negative(text, mentions[-1])
    if not re.search(
        r"(?:оставь|сохрани|не меняй)\s*(?:этот\s*)?(?:перелет|поезд|транспорт)", text
    ):
        positive = [mode for mode, allowed in modes.items() if allowed]
        if len(positive) == 1:
            patch["transport"] = positive[0]
        elif len(modes) == 1 and not next(iter(modes.values())):
            patch["transport"] = "flight" if "train" in modes else "train"
        elif modes and not positive:
            unresolved.append("Оба поддерживаемых вида транспорта запрещены.")
    if re.search(
        r"\b(?:без\s+завтрак\w*|не\s+(?:(?:нужен|нужны|нужны|нуж\w*|хочу)\s+)?завтрак\w*)",
        text,
    ):
        patch["meal"] = "any"
    elif "все включено" in text or "all inclusive" in text:
        patch["meal"] = "all_inclusive"
    elif "завтрак" in text:
        patch["meal"] = "breakfast"
    if re.search(r"бесплатн\w*\s*отмен|возвратн\w*\s*тариф", text):
        patch["refundable"] = True
    if re.search(r"отмена не важна|невозвратн", text):
        patch["refundable"] = False
    if re.search(r"поближе к центру|в центре", text):
        patch["hotel_preference"] = "center"
    if re.search(r"у пляжа|на пляже|первая линия", text):
        patch["hotel_preference"] = "beach"
    if re.search(
        r"(?:оставь|сохрани|не меняй)\s*(?:этот\s*)?(?:перелет|поезд|транспорт)", text
    ):
        patch["lock_transport"] = True
    if re.search(r"разблокируй|можно поменять перелет|сними фиксацию", text):
        patch["lock_transport"] = False
    if re.search(
        r"(?:без|не хочу|не нужен)\s+ночн\w*\s+(?:прилет\w*|прибыт\w*|рейс\w*)", text
    ):
        unresolved.append(
            "Запрет ночного прибытия: ограниченный parser не поддерживает это условие; уточните его через форму или явно снимите."
        )
    if re.search(
        r"(?:только|обязательно)\s+безвизов\w*|(?:инвалидн\w*\s+коляск\w*|доступн\w*\s+для\s+коляс\w*)",
        text,
    ):
        unresolved.append(
            "Обязательные визовые условия или доступность для коляски не подтверждаются данными демокаталога."
        )
    if unresolved:
        warnings.extend("Нужно уточнение: " + value for value in unresolved)
    if not patch and message.strip():
        warnings.append(
            "Ограниченный parser не распознал изменение. Уточните условия через форму; живой AI сейчас может быть недоступен."
        )
    return {
        "patch": patch,
        "warnings": warnings,
        "recognized": bool(patch),
        "unresolved_constraints": unresolved,
    }
