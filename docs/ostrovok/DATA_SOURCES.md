# Open travel reference data: sources, licenses, schema, and refresh

Research and retrieval date: 2026-10-24 UTC. Actual per-source timestamps and exact response SHA-256 values are in `manifest.json`.

## What was actually fetched and validated

The fetches completed over public HTTPS without credentials or browser scraping. The total of 15 retained source responses is 908,511 bytes. `python apps/ostrovok/scripts/validate_snapshot.py` validates fully offline. Paths in the table below are relative to `apps/ostrovok/data/reference/`.

| Output | Rows | Provenance and permitted purpose |
|---|---:|---|
| `cities.json` | 9 | Open-Meteo Geocoding / GeoNames populated places: eight destinations plus Moscow. Country filtering plus maximum population disambiguates similarly named places. St Petersburg serves as both origin and destination. |
| `monthly_weather_sample.json` | 108 | Open-Meteo Historical Weather API, model `era5`, UTC daily mean air temperature and daily precipitation for 2021-01-01 through 2025-12-31. Nine cities × 1,826 dates = 16,434 date rows, aggregated into twelve month rows per city. |
| `airports_subset.json` | 12 | OurAirports country CSV exports for RU, AM, TR, EG, filtered by IATA codes SVO/DME/VKO/LED/KZN/AER/KGD/EVN/IST/SAW/AYT/HRG. |
| `hotel_pois.json` | 16 unique entities | Small Wikidata CC0 sample, up to three query results per city, with coordinates and optional website. Six cities represented; none returned for Sochi or Kaliningrad in this intentionally small direct-P131 query. Coordinates may have multiple Wikidata candidates. **Historical entities occur: this is an entity-reference research sample, not a verified current hotel inventory.** |

City identifiers are `kazan`, `sochi`, `kaliningrad`, `saint-petersburg`, `yerevan`, `istanbul`, `antalya`, `hurghada`, `moscow`. Adapt identifiers explicitly when joining to another schema.

## License, terms, and attribution

- Open-Meteo currently states API data is CC BY 4.0. The free hosted API has separate **noncommercial-use** conditions and rate limits; a production commercial travel service needs its paid commercial endpoint or an appropriate alternative, even though obtained data has an attribution license. Place `Weather data by Open-Meteo (https://open-meteo.com/), based on Copernicus ERA5; aggregated 2021–2025` next to displayed weather summaries, link CC BY 4.0, and mention aggregation. Geocoding documentation explicitly credits GeoNames, so also attribute `Location data: GeoNames via Open-Meteo`. Current generic terms and licensing links govern this research snapshot; the geocoding GitHub README contains an older conflicting CC BY-NC statement, so retain attribution and noncommercial demo use until production license scope is confirmed.
- OurAirports explicitly releases its data to the public domain. Credit is appreciated but not required. Keep source and retrieval time for traceability. This dataset's `scheduled_service=1` is a source catalog field, not proof of a currently operating route or a ticket available for the requested dates.
- Wikidata structured item data is CC0. This does **not** license arbitrary hotel photos or website descriptions, and none were acquired. Hotel entity metadata alone supplies neither live status nor rates, availability, booking conditions, or endorsement. Records such as historic hotels mean this sample should be used for data engineering/entity resolution only, or manually curated and status-verified before user-facing selection.

Official sources checked:

- https://open-meteo.com/en/terms
- https://open-meteo.com/en/pricing
- https://open-meteo.com/en/docs/geocoding-api
- https://open-meteo.com/en/docs/historical-weather-api
- https://github.com/open-meteo/open-meteo/blob/main/README.md
- https://github.com/open-meteo/geocoding-api/blob/main/README.md
- https://ourairports.com/data/
- https://ourairports.com/help/data-dictionary.html
- https://www.wikidata.org/wiki/Wikidata:Data_access
- https://www.wikidata.org/wiki/Wikidata:Database_download
- https://creativecommons.org/licenses/by/4.0/
- https://creativecommons.org/publicdomain/zero/1.0/

## Concrete values from the fetched weather sample

| City | January mean °C | July mean °C | January mean precipitation/month mm | July mean precipitation/month mm |
|---|---:|---:|---:|---:|
| Kazan | -9.69 | 21.04 | 54.02 | 45.12 |
| Antalya | 11.75 | 32.42 | 192.54 | 1.26 |
| Hurghada | 18.56 | 32.36 | 1.46 | 0.00 |

These are daily mean air temperatures, **not** mean daytime maxima, sea temperatures, current forecasts, or a promise about future travel dates. The five-year sample is **not** a WMO 30-year climate normal. Temperature is the arithmetic mean of non-null daily means for that calendar month across the five years. Precipitation is the sum for that calendar month divided by five. Leap-day coverage is included. The API grid coordinate may differ from the exact city coordinate; raw files preserve the returned grid position.

## Practical acquisition and fallback plan

1. Keep a versioned snapshot of normalized city, airport, and monthly-weather fixtures with a provenance manifest and source attributions. This prototype also commits its fifteen original responses (908,511 bytes) once so every derivative and hash can be audited offline. Larger future refreshes can remain separate CI artifacts. Local tests and pull requests do not need a live network source.
2. The implemented `ostrovok-data.yml` GitHub Actions workflow supports manual dispatch and runs when acquisition scripts or the workflow change. It uses Python stdlib, no API keys for the noncommercial demo, timeouts and response-size caps. The script makes nine geocoding calls, one batched weather call, and four country-airport calls; the optional hotel query is separate. The job stores artifacts and validation results without replacing the approved application snapshot. A real [Actions run](https://github.com/MakSoS1/lenta_tech/actions/runs/40123913358) passed: fourteen fresh source responses, 896,630 bytes, nine cities, 108 monthly summaries and twelve airport records.
3. Validate exact raw hashes, country/coordinate ranges, unique cities and airport codes, all 12 calendar months per city, complete date coverage, finite temperature values, nonnegative precipitation, and unique Wikidata IDs. The included `validate_snapshot.py` implements the relevant snapshot checks and records `validation_result.json`.
4. On a timeout, 429, or invalid payload, retain the last validated snapshot, show its data period/retrieval time, and state that the weather is historical. Do not silently substitute random numbers or label cached output as newly fetched. A source refresh command should return nonzero on a failed required source; application offline lookup can still use the last validated fixtures.
5. Keep hotel offers and flight offers in a separate provider interface. Without a supplied authorized provider key, use unmistakably synthetic demo offers with `synthetic=true`, `source=demo`, `availability=unknown/demo`, and explain no live price check occurred. Open datasets cannot supply actual bookable prices or availability. Live integration should use the supplier's documented authorized API and provider-specific contract. Airport coordinates can support distance estimates but cannot prove direct-flight schedules.
6. Avoid mixing historical Wikidata properties into synthetic offer claims about a named real hotel. Use invented demo property names for offer examples; keep real POIs in a distinctly marked reference view only after appropriate curation.

## Reproduction and safe refresh

From the repository root, using Python 3.10 or later and the standard library only:

```bash
# Offline validation; optional recorded evidence inside the snapshot.
python apps/ostrovok/scripts/validate_snapshot.py --write-report

# Required public sources: nine geocoding calls, one weather call, four country CSVs.
python apps/ostrovok/scripts/fetch_open_data.py

# Optional research-only hotel entity catalog; requires a valid core snapshot.
python apps/ostrovok/scripts/fetch_hotel_pois.py

# All three commands accept a custom directory.
python apps/ostrovok/scripts/fetch_open_data.py --output /tmp/ostrovok-reference
python apps/ostrovok/scripts/validate_snapshot.py --output /tmp/ostrovok-reference
```

The default path is resolved from the script location, so commands work from any current directory. A relative `--output` path is resolved against the caller's current directory. Source response sizes are capped at 3 MB and public requests have a 45-second timeout. No secret, API key, login, or paid service is required for this noncommercial demonstration. GitHub Actions can run the same commands without third-party Python packages. API throttling, timeout, response/schema changes, and data validation failures cause a nonzero exit; callers should retain the committed snapshot and show its date.

Both fetch scripts download/derive into a temporary sibling directory, validate the entire candidate snapshot, and then swap directories. The old output remains byte-for-byte unchanged on acquisition, parsing, or validation failure. A sibling lock rejects concurrent refresh attempts. Failed swaps restore the preceding directory; a successful swap removes its temporary backup. There is a very brief directory-absence interval between the two portable renames, so an already running server should load its reference dataset once at startup or refresh while offline. This is transactional staging, not a filesystem promise of one atomic exchange of nonempty directories. Forcefully terminating the process can leave a sibling lock or temporary recovery directory; inspect those before manually cleaning up.

The core refresh preserves existing optional hotel source/normalized files and validates them. The hotel refresh replaces only its own source/normalized files and provenance, then validates the whole snapshot. The shipped raw responses and hashes already form a complete validated snapshot: no further download is required to run the demonstration.

## Consumer schema

Both primary consumer files are UTF-8 JSON arrays.

| File / field | Type | Meaning |
|---|---|---|
| `cities.json` / `id` | string | Stable local join key; the nine identifiers listed above. |
| `name` | string | Source display name, e.g. `Kazan’`, `St Petersburg`. Map to local UI labels if needed. |
| `country_code` | string | ISO 3166 alpha-2 country. |
| `latitude`, `longitude` | number | Source WGS84 city coordinates in decimal degrees. |
| `timezone` | string | Source IANA timezone. |
| `geonames_id` | integer | Source populated-place identifier. |
| `source_file` | string | Relative path to the exact acquired geocoding JSON inside the snapshot. |
| `monthly_weather_sample.json` / `city_id` | string | Joins to `cities.json.id`. |
| `month` | integer | Calendar month 1–12. |
| `temperature_mean_c` | number | Mean of all daily mean air temperatures in this month across 2021–2025, rounded to two decimals. |
| `precipitation_mean_monthly_mm` | number | Total precipitation for this calendar month over the five years divided by five, rounded to two decimals. |
| `sample_days` | integer | Number of daily values; February includes leap-day coverage. |
| `sample_years` | integer | `5`. |
| `period` | string | `2021-2025`. |
| `kind` | string | `five_year_historical_sample_not_climate_normal`. |
| `model`, `timezone` | string | `era5`, `UTC`. |

Airport fields retain the source CSV string representation, including coordinate strings and `scheduled_service` values such as `1`. Consumers should parse coordinates explicitly. Hotel POIs are deliberately a separate array: `wikidata_id`, `name`, `city_wikidata_id`, `coordinate_wkt`, `coordinate_candidates_wkt`, optional `website`, `license=CC0-1.0`, and `data_kind=reference_poi_not_bookable_offer`. Never join those records to simulated price or availability claims about named real hotels.

## Recorded verification

`validation_result.json` records source hashes and coverage validation outcome for the shipped data. The standalone validator checks source-manifest uniqueness and required coverage; exact raw byte lengths and SHA-256 hashes; HTTPS and retrieval timestamps; expected city countries and coordinates matched back to raw responses; exact weather date sequence/units/numeric bounds; all monthly values recomputed from acquired raw weather; required airport-code uniqueness and all normalized airport fields matched back to acquired CSVs; and hotel provenance/classification/entity uniqueness. It does not verify current operating status or provider availability.
