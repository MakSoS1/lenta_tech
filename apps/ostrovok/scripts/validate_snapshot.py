#!/usr/bin/env python3
"""Offline validation of open travel reference data; Python standard library only."""

import argparse
import collections
import csv
import io
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "reference"
EXPECTED_CITIES = {
    "kazan": "RU",
    "sochi": "RU",
    "kaliningrad": "RU",
    "saint-petersburg": "RU",
    "yerevan": "AM",
    "istanbul": "TR",
    "antalya": "TR",
    "hurghada": "EG",
    "moscow": "RU",
}
EXPECTED_AIRPORTS = {
    "SVO",
    "DME",
    "VKO",
    "LED",
    "KZN",
    "AER",
    "KGD",
    "EVN",
    "IST",
    "SAW",
    "AYT",
    "HRG",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def finite_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def validate_snapshot(output=DEFAULT_OUTPUT):
    root = Path(output).resolve()
    manifest = read_json(root / "manifest.json")
    files = [row["file"] for row in manifest]
    require(len(files) == len(set(files)), "Duplicate source manifest filenames")
    expected_raw = (
        {f"raw/geocoding-{city}.json" for city in EXPECTED_CITIES}
        | {f"raw/airports-{country}.csv" for country in ["RU", "AM", "TR", "EG"]}
        | {"raw/weather-era5-2021-2025.json"}
    )
    require(expected_raw <= set(files), "Missing required source response in manifest")
    for source in manifest:
        path = (root / source["file"]).resolve()
        require(path.is_relative_to(root), "Manifest path escapes snapshot")
        body = path.read_bytes()
        require(
            hashlib.sha256(body).hexdigest() == source["sha256"],
            f"SHA-256 mismatch: {source['file']}",
        )
        require(
            len(body) == source["bytes"] and source["http_status"] == 200,
            f"Invalid response metadata: {source['file']}",
        )
        require(
            source["url"].startswith("https://") and bool(source["license"]),
            "Missing HTTPS URL or license",
        )
        require(
            dt.datetime.fromisoformat(source["fetched_at"]).tzinfo is not None,
            "Retrieval time must contain timezone",
        )
    cities = read_json(root / "cities.json")
    require(
        len(cities) == len(EXPECTED_CITIES)
        and {c["id"] for c in cities} == set(EXPECTED_CITIES),
        "Unexpected or duplicate city IDs",
    )
    for city in cities:
        require(
            city["country_code"] == EXPECTED_CITIES[city["id"]],
            f"Wrong country for {city['id']}",
        )
        require(
            finite_number(city["latitude"]) and -90 <= city["latitude"] <= 90,
            "Invalid city latitude",
        )
        require(
            finite_number(city["longitude"]) and -180 <= city["longitude"] <= 180,
            "Invalid city longitude",
        )
        candidates = read_json(root / city["source_file"])["results"]
        match = next((v for v in candidates if v["id"] == city["geonames_id"]), None)
        require(
            match is not None
            and match["latitude"] == city["latitude"]
            and match["longitude"] == city["longitude"],
            "City does not match its acquired raw response",
        )
    weather = read_json(root / "raw/weather-era5-2021-2025.json")
    require(len(weather) == len(cities), "Unexpected weather location count")
    expected_dates = [
        (dt.date(2021, 1, 1) + dt.timedelta(days=n)).isoformat() for n in range(1826)
    ]
    monthly = read_json(root / "monthly_weather_sample.json")
    require(len(monthly) == len(cities) * 12, "Unexpected monthly row count")
    for city, source in zip(cities, weather):
        daily = source["daily"]
        require(
            daily["time"] == expected_dates,
            "Weather dates are incomplete, reordered, or duplicated",
        )
        require(
            source["daily_units"]["temperature_2m_mean"] == "°C"
            and source["daily_units"]["precipitation_sum"] == "mm",
            "Unexpected weather units",
        )
        temperatures, precipitation = (
            daily["temperature_2m_mean"],
            daily["precipitation_sum"],
        )
        require(
            len(temperatures) == len(precipitation) == 1826,
            "Unexpected daily weather length",
        )
        require(
            all(finite_number(t) and -90 < t < 65 for t in temperatures),
            "Missing or invalid weather temperature",
        )
        require(
            all(finite_number(p) and p >= 0 for p in precipitation),
            "Missing or invalid precipitation",
        )
        rows = [row for row in monthly if row["city_id"] == city["id"]]
        require(
            sorted(row["month"] for row in rows) == list(range(1, 13)),
            "Monthly coverage incomplete or duplicated",
        )
        for row in rows:
            inds = [
                i
                for i, date in enumerate(expected_dates)
                if int(date[5:7]) == row["month"]
            ]
            mean = round(sum(temperatures[i] for i in inds) / len(inds), 2)
            rain = round(sum(precipitation[i] for i in inds) / 5, 2)
            require(
                abs(row["temperature_mean_c"] - mean) <= 0.01
                and abs(row["precipitation_mean_monthly_mm"] - rain) <= 0.01,
                "Monthly aggregates disagree with acquired raw weather",
            )
            require(
                row["sample_days"] == len(inds) and row["sample_years"] == 5,
                "Incorrect sample size",
            )
            require(
                row["period"] == "2021-2025"
                and row["kind"] == "five_year_historical_sample_not_climate_normal"
                and row["model"] == "era5"
                and row["timezone"] == "UTC",
                "Incorrect historical weather provenance",
            )
    airports = read_json(root / "airports_subset.json")
    require(
        len(airports) == len(EXPECTED_AIRPORTS)
        and {a["iata_code"] for a in airports} == EXPECTED_AIRPORTS,
        "Unexpected or duplicate airports",
    )
    raw_airports = {}
    for country in ["RU", "AM", "TR", "EG"]:
        for row in csv.DictReader(
            io.StringIO(
                (root / f"raw/airports-{country}.csv").read_text(encoding="utf-8-sig")
            )
        ):
            if row.get("iata_code") in EXPECTED_AIRPORTS:
                raw_airports[row["iata_code"]] = row
    for airport in airports:
        source = raw_airports.get(airport["iata_code"], {})
        require(
            all(source.get(key) == value for key, value in airport.items()),
            "Airport does not match its acquired raw response",
        )
        require(
            -90 <= float(airport["latitude_deg"]) <= 90
            and -180 <= float(airport["longitude_deg"]) <= 180,
            "Invalid airport coordinates",
        )
    hotels = (
        read_json(root / "hotel_pois.json")
        if (root / "hotel_pois.json").exists()
        else []
    )
    require(
        not hotels or "raw/wikidata-hotel-pois.json" in files,
        "Hotel POIs lack raw source provenance",
    )
    require(
        len({h["wikidata_id"] for h in hotels}) == len(hotels),
        "Duplicate hotel entities",
    )
    require(
        all(
            h["data_kind"] == "reference_poi_not_bookable_offer"
            and h["license"] == "CC0-1.0"
            for h in hotels
        ),
        "Hotel POI misrepresented as an offer",
    )
    return {
        "validation": "PASS",
        "raw_sources": len(manifest),
        "raw_source_bytes": sum(s["bytes"] for s in manifest),
        "cities": len(cities),
        "daily_weather_observations": len(cities) * 1826,
        "monthly_weather_rows": len(monthly),
        "airport_rows": len(airports),
        "hotel_entities": len(hotels),
        "hotel_city_coverage": dict(
            collections.Counter(h["city_wikidata_id"] for h in hotels)
        ),
        "hotel_caveat": "Reference only; includes historical buildings. Current operating status, price and availability are unverified.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Snapshot directory (default: apps/ostrovok/data/reference)",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Save validation_result.json in the snapshot",
    )
    args = parser.parse_args()
    try:
        result = validate_snapshot(args.output)
        if args.write_report:
            (args.output / "validation_result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as error:
        parser.exit(1, f"Snapshot validation failed: {error}\n")


if __name__ == "__main__":
    main()
