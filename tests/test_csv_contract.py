import csv
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CsvContractTest(unittest.TestCase):
    def expected_columns(self):
        with (ROOT / "docs" / "sample_contract.csv").open(newline="", encoding="utf-8-sig") as f:
            return next(csv.reader(f))

    def test_unlabeled_outputs_match_sample_contract(self):
        expected = self.expected_columns()
        output_dir = ROOT / "outputs_unlabeled_final"
        files = sorted(output_dir.glob("*.csv"))
        self.assertEqual([p.name for p in files], ["25_12-20_final.csv", "26_12-20_final.csv", "26_2-10_final.csv"])

        for path in files:
            with path.open(newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            self.assertEqual(reader.fieldnames, expected, path.name)
            self.assertGreater(len(rows), 0, path.name)
            for row in rows:
                x_min = float(row["x_min"])
                y_min = float(row["y_min"])
                x_max = float(row["x_max"])
                y_max = float(row["y_max"])
                self.assertGreater(x_max, x_min)
                self.assertGreater(y_max, y_min)
                self.assertGreaterEqual(x_min, 0)
                self.assertGreaterEqual(y_min, 0)

    def test_site_sample_csv_matches_contract(self):
        expected = self.expected_columns()
        with (ROOT / "site" / "assets" / "sample-result.csv").open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(reader.fieldnames, expected)
        self.assertGreater(len(rows), 0)
