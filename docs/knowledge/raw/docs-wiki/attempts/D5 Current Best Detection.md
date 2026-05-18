---
type: detection_attempt
status: superseded_by_A21
accuracy: "43_15: 24/29 (83%), 49_5: 20/61 (33%) — с HSV fallback"
date: 2026-05-16
links: "[[overview]] [[D4 Multi-Frame NMS]] [[A21 Color Fallback]] [[A20 Final Pipeline]]"
---
# D5→Final: Current Best Detection

**Конфигурация**: YOLOv8n v1 (conf=0.05, NMS IoU=0.3) + HSV color fallback
**Pipeline**: `src/pipeline/price_tag_pipeline.py`

**Results per video (с HSV fallback)**:
| Video | Detection | Mean IoU |
|-------|-----------|----------|
| 43_15 | 24/29 (83%) | 0.524 |
| 25_12-20 | 16/57 (28%) | 0.201 |
| 25_2-10 | 20/56 (36%) | 0.190 |
| 26_12-20 | 31/71 (44%) | 0.278 |
| 49_5 | 20/61 (33%) | 0.138 |

**HSV fallback impact** (see [[A21 Color Fallback]]):
- 49_5: 9→98 raw detections, 4→20 GT matches
- 25_2-10: 15→55 raw, 14→20 matches
- 43_15: no change (YOLO finds tags on every frame)

**Что улучшить**:
1. Frame-accurate YOLO retraining (v3 failed due to timestamp mismatch)
2. HSV tuning for tighter bboxes
3. More frames for non-43_15 videos
