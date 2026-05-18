"""Validate pipeline output against Lenta GT CSVs."""
from __future__ import annotations

import argparse
import csv
import os
import re
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
VIDEOS = ["43_15", "25_12-20", "25_2-10", "26_12-20", "49_5"]
SKIP_COLS = {"filename", "frame_timestamp", "x_min", "y_min", "x_max", "y_max"}
PRICE_COLS = {
    "price_default", "price_card", "price_discount",
    "price1_qr", "price2_qr", "price3_qr", "price4_qr",
    "wholesale_level_1_price", "wholesale_level_2_price", "action_price_qr",
}
FIELD_ALIASES = {"wholesale_level_1_coun": "wholesale_level_1_count"}
CANONICAL_COLUMNS = [
    "filename", "product_name", "price_default", "price_card", "price_discount",
    "barcode", "discount_amount", "id_sku", "print_datetime", "code",
    "additional_info", "color", "special_symbols", "frame_timestamp",
    "x_min", "y_min", "x_max", "y_max",
    "qr_code_barcode", "price1_qr", "price2_qr", "price3_qr", "price4_qr",
    "wholesale_level_1_count", "wholesale_level_1_price",
    "wholesale_level_2_count", "wholesale_level_2_price",
    "action_price_qr", "action_code_qr",
]


def normalize_key(row: dict) -> dict:
    out = {}
    for key, value in row.items():
        out[FIELD_ALIASES.get(key, key)] = value
    return {col: normalize_cell(out.get(col, ""), col) for col in CANONICAL_COLUMNS}


def normalize_cell(value, col: str) -> str:
    value = "" if value is None else str(value).replace("\ufeff", "").strip()
    if col in {"filename"}:
        return value
    if col in {"frame_timestamp", "x_min", "y_min", "x_max", "y_max"}:
        return value.replace(",", ".")
    if value == "" or value.lower() in {"none", "null", "nan"}:
        return "нет"
    if value.strip().lower() == "нет":
        return "нет"
    if col in PRICE_COLS:
        parsed = parse_price(value)
        return f"{parsed:.2f}" if parsed is not None else value.replace(",", ".")
    return re.sub(r"\s+", " ", value)


def parse_price(value) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(" ", "").replace(",", ".")
    if not text or text.lower() == "нет":
        return None
    match = re.search(r"(-?\d+)\.(\d{1,2})", text)
    if match:
        return float(match.group(1) + "." + match.group(2)[:2].ljust(2, "0"))
    match = re.search(r"(-?\d{2,5})", text)
    if match:
        return float(match.group(1))
    return None


def parse_coord(value) -> float:
    try:
        if value is None or str(value).strip().lower() == "нет":
            return 0.0
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return 0.0


def levenshtein_ratio(s1, s2):
    if not s1 or not s2:
        return 1.0 if not s1 and not s2 else 0.0
    s1, s2 = str(s1).lower().strip(), str(s2).lower().strip()
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    prev = list(range(len2 + 1))
    for i in range(1, len1 + 1):
        cur = [i] + [0] * len2
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return 1.0 - prev[len2] / max(len1, len2)


def compute_iou(a, b):
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    area_a = max((a[2] - a[0]) * (a[3] - a[1]), 1)
    area_b = max((b[2] - b[0]) * (b[3] - b[1]), 1)
    return inter / (area_a + area_b - inter)


def field_match(pred_val, gt_val, col):
    pv = normalize_cell(pred_val, col)
    gv = normalize_cell(gt_val, col)
    if gv == "нет" and pv == "нет":
        return 1.0
    if gv == "нет" and pv != "нет":
        return 0.0
    if gv != "нет" and pv == "нет":
        return 0.0
    if col in PRICE_COLS:
        p = parse_price(pv)
        g = parse_price(gv)
        if p is None or g is None:
            return 1.0 if pv == gv else 0.0
        return 1.0 if abs(p - g) <= 0.5 else 0.0
    return levenshtein_ratio(pv, gv)


def find_gt_path(video_name: str) -> Path:
    for root, _, files in os.walk(PROJECT_ROOT / "data"):
        if f"{video_name}.csv" in files:
            return Path(root) / f"{video_name}.csv"
    raise FileNotFoundError(f"GT not found for {video_name}")


def pred_path_for(video_name: str, pred: str | None, pred_dir: str) -> Path:
    if pred:
        path = Path(pred)
        if path.is_dir():
            return path / f"{video_name}_final.csv"
        return path
    return Path(pred_dir) / f"{video_name}_final.csv"


def read_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [normalize_key(row) for row in csv.DictReader(f)]


def score_video(video_name: str, pred: str | None = None, pred_dir: str = "outputs", verbose=True):
    gt_rows = read_rows(find_gt_path(video_name))
    pred_rows = read_rows(pred_path_for(video_name, pred, pred_dir))
    all_cols = [c for c in CANONICAL_COLUMNS if c not in SKIP_COLS]

    used_pred = set()
    matched_pairs = []
    iou_scores = []
    tag_field_rates = []
    failures = Counter()
    per_field_scores = defaultdict(list)

    for i, gt in enumerate(gt_rows):
        gt_bbox = [parse_coord(gt["x_min"]), parse_coord(gt["y_min"]), parse_coord(gt["x_max"]), parse_coord(gt["y_max"])]
        best_iou = 0.0
        best_j = -1
        for j, pred_row in enumerate(pred_rows):
            if j in used_pred:
                continue
            pred_bbox = [
                parse_coord(pred_row["x_min"]), parse_coord(pred_row["y_min"]),
                parse_coord(pred_row["x_max"]), parse_coord(pred_row["y_max"]),
            ]
            iou = compute_iou(gt_bbox, pred_bbox)
            if iou > best_iou:
                best_iou = iou
                best_j = j

        if best_iou >= 0.3 and best_j >= 0:
            used_pred.add(best_j)
            matched_pairs.append((i, best_j, best_iou))
            iou_scores.append(best_iou)
            pred_row = pred_rows[best_j]
            correct = 0
            total = 0
            bad_cols = []
            for col in all_cols:
                score = field_match(pred_row.get(col, ""), gt.get(col, "нет"), col)
                per_field_scores[col].append(score)
                if score >= 0.8:
                    correct += 1
                else:
                    bad_cols.append(col)
                total += 1
            rate = correct / total if total else 0.0
            tag_field_rates.append(rate)
            if rate < 0.8:
                for col in bad_cols:
                    failures[col] += 1
        else:
            iou_scores.append(0.0)
            tag_field_rates.append(0.0)
            failures["missed_detection"] += 1
            for col in all_cols:
                per_field_scores[col].append(0.0)

    matched = len(matched_pairs)
    successful = sum(1 for rate in tag_field_rates if rate >= 0.8)
    official_metric = successful / len(gt_rows) if gt_rows else 0.0
    mean_iou = sum(iou_scores) / len(iou_scores) if iou_scores else 0.0

    result = {
        "video": video_name,
        "gt": len(gt_rows),
        "pred": len(pred_rows),
        "matched": matched,
        "mean_iou": mean_iou,
        "successful": successful,
        "official_metric": official_metric,
        "tag_field_rates": tag_field_rates,
        "per_field": {col: (sum(vals) / len(vals) if vals else 0.0) for col, vals in per_field_scores.items()},
        "failures": failures,
    }

    if verbose:
        print(f"GT: {len(gt_rows)} rows, Pred: {len(pred_rows)} rows")
        print(f"\nDetection: {matched}/{len(gt_rows)} matched (IoU>=0.3)")
        print(f"Mean IoU: {mean_iou:.3f}")
        print(f"\nOfficial metric (>=80% fields correct): {successful}/{len(gt_rows)} = {official_metric:.3f}")
        print("\nPer-tag field accuracy distribution:")
        for lo, hi in [(0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)]:
            cnt = sum(1 for rate in tag_field_rates if lo <= rate < hi)
            print(f"  {lo:.0%}-{hi:.0%}: {cnt} tags")
        print(f"\nPer-field accuracy ({len(gt_rows)} GT tags):")
        for col in sorted(result["per_field"]):
            print(f"  {col:30s}: {result['per_field'][col]:.3f}")
        print("\nTop failure reasons:")
        for col, count in failures.most_common(12):
            print(f"  {col:30s}: {count}")
    return result


def print_aggregate(results):
    total_gt = sum(r["gt"] for r in results)
    total_success = sum(r["successful"] for r in results)
    total_matched = sum(r["matched"] for r in results)
    all_failures = Counter()
    for r in results:
        all_failures.update(r["failures"])
    print("\n===== AGGREGATE =====")
    print(f"Videos: {len(results)}")
    print(f"Detection: {total_matched}/{total_gt} = {total_matched / total_gt if total_gt else 0:.3f}")
    print(f"Official metric: {total_success}/{total_gt} = {total_success / total_gt if total_gt else 0:.3f}")
    print("Top aggregate failure reasons:")
    for col, count in all_failures.most_common(15):
        print(f"  {col:30s}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Validate Lenta price-tag CSV predictions")
    parser.add_argument("video", nargs="?", default=None, help="Video stem, e.g. 43_15")
    parser.add_argument("--all", action="store_true", help="Validate all labeled videos")
    parser.add_argument("--pred", default=None, help="Prediction CSV path or directory")
    parser.add_argument("--pred-dir", default="outputs", help="Prediction directory")
    args = parser.parse_args()

    videos = VIDEOS if args.all or args.video is None else [args.video]
    results = []
    for idx, video in enumerate(videos):
        if len(videos) > 1:
            print(f"\n===== {video} =====")
        results.append(score_video(video, pred=args.pred, pred_dir=args.pred_dir, verbose=True))
    if len(results) > 1:
        print_aggregate(results)


if __name__ == "__main__":
    main()
