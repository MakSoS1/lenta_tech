#!/usr/bin/env python3
"""Refresh public travel reference data without credentials; preserve snapshot on failure.

Free Open-Meteo hosting is for noncommercial use. See docs/ostrovok/DATA_SOURCES.md.
The downloader is injectable for offline replay of the acquired source responses.
"""

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import shutil
import statistics
import tempfile
import urllib.parse
import urllib.request

from validate_snapshot import DEFAULT_OUTPUT, EXPECTED_AIRPORTS, validate_snapshot

CITIES = [
    ("kazan", "Kazan", "RU"),
    ("sochi", "Sochi", "RU"),
    ("kaliningrad", "Kaliningrad", "RU"),
    ("saint-petersburg", "Saint Petersburg", "RU"),
    ("yerevan", "Yerevan", "AM"),
    ("istanbul", "Istanbul", "TR"),
    ("antalya", "Antalya", "TR"),
    ("hurghada", "Hurghada", "EG"),
    ("moscow", "Moscow", "RU"),
]


def write_json(path, data):
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def download(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "LentaTechTravelResearch/0.1 (+https://github.com/MakSoS1/lenta_tech)",
            "Accept": "application/json,text/csv;q=0.9,*/*;q=0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        if response.status != 200:
            raise ValueError(f"Unexpected HTTP status {response.status}")
        body = response.read(3_000_001)
        if len(body) > 3_000_000:
            raise ValueError("Response exceeded the 3 MB size guard")
        return body, {
            "content_type": response.headers.get("Content-Type"),
            "last_modified": response.headers.get("Last-Modified"),
        }


def acquire(stage, manifest, url, filename, source, license_name, downloader):
    body, metadata = downloader(url)
    if not isinstance(body, bytes) or len(body) > 3_000_000:
        raise ValueError("Invalid or oversized source response")
    (stage / "raw" / filename).write_bytes(body)
    manifest.append(
        {
            "source": source,
            "url": url,
            "file": "raw/" + filename,
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "http_status": 200,
            "content_type": metadata.get("content_type"),
            "last_modified": metadata.get("last_modified"),
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "license": license_name,
        }
    )
    return body


def publish_snapshot(output, builder):
    """Stage and validate all files before directory swap; rollback failed swaps.

    A sibling lock prevents concurrent refreshes. Readers may observe a very brief
    missing-directory interval between the two renames; no partial files are exposed.
    The preceding snapshot remains intact on download/parse/validation failure.
    """
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.parent / f".{output.name}.refresh.lock"
    lock.mkdir()  # Fail immediately if another refresh owns the directory.
    try:
        with tempfile.TemporaryDirectory(
            prefix=f".{output.name}.refresh-", dir=output.parent
        ) as temporary:
            stage = Path(temporary) / "next"
            backup = Path(temporary) / "previous"
            if output.exists():
                shutil.copytree(output, stage)
            else:
                stage.mkdir()
            (stage / "raw").mkdir(exist_ok=True)
            builder(stage)
            result = validate_snapshot(stage)
            write_json(stage / "validation_result.json", result)
            if output.exists():
                output.rename(backup)
            try:
                stage.rename(output)
            except BaseException:
                if backup.exists():
                    backup.rename(output)
                raise
            return result
    finally:
        lock.rmdir()


def build_required(stage, downloader):
    existing_manifest = stage / "manifest.json"
    old = (
        json.loads(existing_manifest.read_text(encoding="utf-8"))
        if existing_manifest.exists()
        else []
    )
    # Optional hotel research remains independently sourced and unchanged.
    manifest = [row for row in old if row["file"] == "raw/wikidata-hotel-pois.json"]
    cities = []
    for city_id, name, country in CITIES:
        params = urllib.parse.urlencode(
            {
                "name": name,
                "countryCode": country,
                "count": 5,
                "language": "en",
                "format": "json",
            }
        )
        raw = json.loads(
            acquire(
                stage,
                manifest,
                "https://geocoding-api.open-meteo.com/v1/search?" + params,
                f"geocoding-{city_id}.json",
                "Open-Meteo / GeoNames",
                "CC BY 4.0; free hosted API noncommercial terms",
                downloader,
            )
        )
        candidates = [
            value
            for value in raw.get("results", [])
            if value.get("country_code") == country
            and value.get("feature_code", "").startswith("PPL")
        ]
        if not candidates:
            raise ValueError(f"No populated place in expected country for {name}")
        value = max(candidates, key=lambda item: item.get("population", 0))
        cities.append(
            {
                "id": city_id,
                "name": value["name"],
                "country_code": country,
                "latitude": value["latitude"],
                "longitude": value["longitude"],
                "timezone": value["timezone"],
                "geonames_id": value["id"],
                "source_file": f"raw/geocoding-{city_id}.json",
            }
        )
    write_json(stage / "cities.json", cities)
    params = urllib.parse.urlencode(
        {
            "latitude": ",".join(str(city["latitude"]) for city in cities),
            "longitude": ",".join(str(city["longitude"]) for city in cities),
            "start_date": "2021-01-01",
            "end_date": "2025-12-31",
            "daily": "temperature_2m_mean,precipitation_sum",
            "models": "era5",
            "timezone": "UTC",
        }
    )
    weather = json.loads(
        acquire(
            stage,
            manifest,
            "https://archive-api.open-meteo.com/v1/archive?" + params,
            "weather-era5-2021-2025.json",
            "Open-Meteo / Copernicus ERA5",
            "CC BY 4.0; free hosted API noncommercial terms",
            downloader,
        )
    )
    if not isinstance(weather, list) or len(weather) != len(cities):
        raise ValueError("Unexpected weather location count")
    monthly = []
    for city, data in zip(cities, weather):
        daily = data["daily"]
        if (
            len(daily["time"]) != 1826
            or len(daily["temperature_2m_mean"]) != 1826
            or len(daily["precipitation_sum"]) != 1826
        ):
            raise ValueError("Incomplete daily weather response")
        for month in range(1, 13):
            indices = [
                i for i, date in enumerate(daily["time"]) if int(date[5:7]) == month
            ]
            temperatures = [daily["temperature_2m_mean"][i] for i in indices]
            precipitation = [daily["precipitation_sum"][i] for i in indices]
            monthly.append(
                {
                    "city_id": city["id"],
                    "month": month,
                    "temperature_mean_c": round(statistics.mean(temperatures), 2),
                    "precipitation_mean_monthly_mm": round(sum(precipitation) / 5, 2),
                    "sample_days": len(indices),
                    "sample_years": 5,
                    "period": "2021-2025",
                    "kind": "five_year_historical_sample_not_climate_normal",
                    "model": "era5",
                    "timezone": "UTC",
                }
            )
    write_json(stage / "monthly_weather_sample.json", monthly)
    airports = []
    for country in ["RU", "AM", "TR", "EG"]:
        body = acquire(
            stage,
            manifest,
            f"https://ourairports.com/countries/{country}/airports.csv",
            f"airports-{country}.csv",
            "OurAirports",
            "Public domain",
            downloader,
        )
        for value in csv.DictReader(io.StringIO(body.decode("utf-8-sig"))):
            if value.get("iata_code") in EXPECTED_AIRPORTS:
                airports.append(
                    {
                        key: value[key]
                        for key in [
                            "id",
                            "ident",
                            "type",
                            "name",
                            "latitude_deg",
                            "longitude_deg",
                            "iso_country",
                            "municipality",
                            "scheduled_service",
                            "iata_code",
                        ]
                    }
                )
    write_json(stage / "airports_subset.json", airports)
    write_json(stage / "manifest.json", manifest)


def refresh(output=DEFAULT_OUTPUT, downloader=download):
    return publish_snapshot(output, lambda stage: build_required(stage, downloader))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Snapshot directory (default: apps/ostrovok/data/reference)",
    )
    args = parser.parse_args()
    try:
        print(json.dumps(refresh(args.output), ensure_ascii=False, indent=2))
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        statistics.StatisticsError,
    ) as error:
        parser.exit(1, f"Refresh failed; preceding snapshot preserved: {error}\n")


if __name__ == "__main__":
    main()
