"""Normalize the provided CP1251 product catalog.

Usage:
    python scripts/normalize_catalog.py /path/to/db_hack.csv data/catalog/products.csv
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path


def normalize(src: Path, dst: Path) -> tuple[int, int]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    seen: set[tuple[str, str]] = set()
    rows = 0
    bad = 0
    with src.open("r", encoding="cp1251", errors="replace") as f, dst.open("w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["fullname", "barcode"])
        next(f, None)
        for line in f:
            line = line.strip("\r\n")
            if not line:
                continue
            fullname, separator, barcode = line.rpartition(";")
            fullname = " ".join(fullname.split())
            barcode = "".join(ch for ch in barcode if ch.isdigit())
            if not separator or not fullname or not barcode:
                bad += 1
                continue
            key = (fullname, barcode)
            if key in seen:
                continue
            seen.add(key)
            writer.writerow([fullname, barcode])
            rows += 1
    return rows, bad


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python scripts/normalize_catalog.py /path/to/db_hack.csv data/catalog/products.csv")
    ok, bad_rows = normalize(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"normalized_rows={ok} skipped_rows={bad_rows}")
