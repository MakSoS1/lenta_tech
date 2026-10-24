#!/usr/bin/env python3
"""Refresh optional CC0 Wikidata hotel reference entities, never bookable offers.

Requires a validated core snapshot. Results may include historical/closed hotels.
Current operating status, prices, availability and ratings are not verified.
"""

import argparse
import json
from pathlib import Path
import urllib.parse

from fetch_open_data import acquire, download, publish_snapshot, write_json
from validate_snapshot import DEFAULT_OUTPUT, validate_snapshot

CITY_IDS = ["Q900", "Q118602", "Q1829", "Q656", "Q1953", "Q406", "Q6487", "Q187284"]


def query_url():
    subqueries = []
    for city_id in CITY_IDS:
        subqueries.append(
            "{ SELECT ?city ?hotel ?coord WHERE { VALUES ?city { wd:"
            + city_id
            + " } ?hotel wdt:P31 wd:Q27686; wdt:P131 ?city; wdt:P625 ?coord. } LIMIT 3 }"
        )
    query = (
        "SELECT ?city ?hotel ?hotelLabel ?coord ?website WHERE { {"
        + " UNION ".join(subqueries)
        + '} OPTIONAL { ?hotel wdt:P856 ?website } SERVICE wikibase:label { bd:serviceParam wikibase:language "ru,en". } }'
    )
    return "https://query.wikidata.org/sparql?" + urllib.parse.urlencode(
        {"query": query, "format": "json"}
    )


def build_optional(stage, downloader):
    manifest = [
        row
        for row in json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
        if row["file"] != "raw/wikidata-hotel-pois.json"
    ]
    body = acquire(
        stage,
        manifest,
        query_url(),
        "wikidata-hotel-pois.json",
        "Wikidata Query Service",
        "CC0-1.0",
        downloader,
    )
    bindings = json.loads(body)["results"]["bindings"]
    unique = {}
    for row in bindings:
        entity_id = row["hotel"]["value"].rsplit("/", 1)[-1]
        coordinate = row["coord"]["value"]
        if entity_id not in unique:
            unique[entity_id] = {
                "wikidata_id": entity_id,
                "name": row["hotelLabel"]["value"],
                "city_wikidata_id": row["city"]["value"].rsplit("/", 1)[-1],
                "coordinate_wkt": coordinate,
                "website": row.get("website", {}).get("value"),
                "license": "CC0-1.0",
                "data_kind": "reference_poi_not_bookable_offer",
                "coordinate_candidates_wkt": [coordinate],
            }
        elif coordinate not in unique[entity_id]["coordinate_candidates_wkt"]:
            unique[entity_id]["coordinate_candidates_wkt"].append(coordinate)
    write_json(stage / "hotel_pois.json", list(unique.values()))
    write_json(stage / "manifest.json", manifest)


def refresh(output=DEFAULT_OUTPUT, downloader=download):
    validate_snapshot(output)
    return publish_snapshot(output, lambda stage: build_optional(stage, downloader))


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
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        parser.exit(
            1, f"Optional hotel refresh failed; preceding snapshot preserved: {error}\n"
        )


if __name__ == "__main__":
    main()
