import json
from functools import lru_cache
from pathlib import Path

REFERENCE_DIR = Path(__file__).resolve().parents[3] / "data/reference"
NAMES = {
    "moscow": ("Москва", "Россия"),
    "saint-petersburg": ("Санкт-Петербург", "Россия"),
    "kazan": ("Казань", "Россия"),
    "sochi": ("Сочи", "Россия"),
    "kaliningrad": ("Калининград", "Россия"),
    "yerevan": ("Ереван", "Армения"),
    "istanbul": ("Стамбул", "Турция"),
    "antalya": ("Анталья", "Турция"),
    "hurghada": ("Хургада", "Египет"),
}


@lru_cache(maxsize=4)
def load_reference(directory=None):
    path = Path(directory) if directory else REFERENCE_DIR
    cities = {c["id"]: c for c in json.loads((path / "cities.json").read_text())}
    weather = json.loads((path / "monthly_weather_sample.json").read_text())
    return cities, weather


def city_info(city_id):
    name, country = NAMES[city_id]
    return {"id": city_id, "name": name, "country": country}


def weather_context(city_id, month, directory=None):
    _, rows = load_reference(directory)
    row = next(
        (r for r in rows if r["city_id"] == city_id and r["month"] == month), None
    )
    if row is None:
        return None
    return {
        **row,
        "label": "Историческая выборка 2021–2025, не прогноз",
        "source": "Open-Meteo / Copernicus ERA5",
        "source_url": "https://open-meteo.com/",
        "license": "CC BY 4.0",
        "attribution": "Weather data by Open-Meteo, based on Copernicus ERA5; aggregated 2021–2025",
        "temperature_label": "Средняя суточная температура воздуха",
    }
