---
type: attempt
status: completed
date: 2026-05-16
links: "[[D1 HSV Detection]] [[D5 Current Best Detection]] [[A20 Final Pipeline]]"
---
# A21: HSV Color Fallback for Detection

**Проблема**: YOLO v1 trained only on 43_15 → fails on other videos (49_5: 9/61 detected)

**Решение**: Включить HSV color fallback в TagDetector.detect() — YOLO пробует первым, если 0 результатов → HSV

**Detection counts (raw → NMS → filtered)**:
| Video | YOLO only | YOLO+HSV | Improvement |
|-------|-----------|----------|-------------|
| 49_5 | 24 raw → 9 filtered | 399 raw → 102 filtered | 9→102 (11x!) |
| 25_2-10 | 121 raw → 15 filtered | 224 raw → 59 filtered | 15→59 (4x) |
| 26_12-20 | 172 raw → 34 filtered | 198 raw → 47 filtered | 34→47 |
| 25_12-20 | 151 raw → 16 filtered | 151 raw → 16 filtered | no change (YOLO finds tags) |
| 43_15 | 618 raw → 58 filtered | 618 raw → 58 filtered | no change (YOLO dominant) |

**GT matches (IoU≥0.3)**:
| Video | YOLO only | YOLO+HSV | Δ |
|-------|-----------|----------|---|
| 49_5 | 4/61 (7%) | 20/61 (33%) | +16 matches |
| 25_2-10 | 14/56 (25%) | 20/56 (36%) | +6 matches |
| 26_12-20 | 29/71 (41%) | 31/71 (44%) | +2 matches |

**Issue**: HSV bboxes less precise → lower Mean IoU (0.138 vs 0.036 for 49_5)
**Tradeoff**: More detections but more FPs + lower IoU per detection

**Code**: `tag_detector.detect()` calls `_detect_yolo()` then `_detect_color()` if empty
