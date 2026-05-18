import unittest

from validate import compute_iou, field_match, normalize_cell, normalize_key, parse_price


class ValidateUtilsTest(unittest.TestCase):
    def test_price_and_missing_value_normalization(self):
        self.assertEqual(normalize_cell("", "price_card"), "нет")
        self.assertEqual(normalize_cell("123,4", "price_card"), "123.40")
        self.assertEqual(normalize_cell("  1 234,99  ", "price_default"), "1234.99")
        self.assertEqual(parse_price("3789.49"), 3789.49)

    def test_alias_and_field_matching(self):
        row = normalize_key({"wholesale_level_1_coun": "2", "price_card": "100,49"})
        self.assertEqual(row["wholesale_level_1_count"], "2")
        self.assertEqual(row["price_card"], "100.49")
        self.assertEqual(field_match("100.49", "100.50", "price_card"), 1.0)
        self.assertLess(field_match("wrong", "right", "product_name"), 0.8)

    def test_iou(self):
        self.assertEqual(compute_iou([0, 0, 10, 10], [20, 20, 30, 30]), 0.0)
        self.assertAlmostEqual(compute_iou([0, 0, 10, 10], [5, 5, 15, 15]), 25 / 175)
