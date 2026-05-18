import csv
import tempfile
import unittest
from pathlib import Path

from src.catalog.product_catalog import ProductCatalog


class ProductCatalogTest(unittest.TestCase):
    def test_name_lookup_normalizes_barcode_and_extended_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "products.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["fullname", "barcode"])
                writer.writeheader()
                writer.writerow({"fullname": "  Молоко Лента 3.2%  ", "barcode": "4601234567890"})

            catalog = ProductCatalog(path)

            self.assertEqual(catalog.name_for_barcode("4601234567890"), "Молоко Лента 3.2%")
            self.assertEqual(catalog.name_for_barcode("4601234567890999"), "Молоко Лента 3.2%")
            self.assertEqual(catalog.name_for_barcode("нет"), "")

    def test_missing_catalog_is_empty(self):
        catalog = ProductCatalog("/tmp/lenta-missing-products.csv")
        self.assertEqual(catalog.name_for_barcode("4601234567890"), "")
