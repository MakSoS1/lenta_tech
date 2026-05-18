"""Local product catalog helpers.

The hackathon provided a CP1251 product dump with `fullname;code` rows.  The
release repository stores the normalized UTF-8 version in
`data/catalog/products.csv` so runtime code can enrich OCR results without any
network calls.
"""

from __future__ import annotations

import csv
from pathlib import Path


class ProductCatalog:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else Path(__file__).resolve().parents[2] / "data" / "catalog" / "products.csv"
        self._by_barcode: dict[str, str] | None = None

    def _load(self) -> dict[str, str]:
        if self._by_barcode is not None:
            return self._by_barcode

        mapping: dict[str, str] = {}
        if not self.path.exists():
            self._by_barcode = mapping
            return mapping

        with open(self.path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                barcode = "".join(ch for ch in str(row.get("barcode", "")) if ch.isdigit())
                fullname = " ".join(str(row.get("fullname", "")).split())
                if barcode and fullname and barcode not in mapping:
                    mapping[barcode] = fullname
        self._by_barcode = mapping
        return mapping

    def name_for_barcode(self, barcode: str | None) -> str:
        digits = "".join(ch for ch in str(barcode or "") if ch.isdigit())
        if not digits:
            return ""
        catalog = self._load()
        if digits in catalog:
            return catalog[digits]
        if len(digits) > 13 and digits[:13] in catalog:
            return catalog[digits[:13]]
        return ""
