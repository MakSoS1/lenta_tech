---
type: attempt
status: completed
date: 2026-05-17
links: "[[A18 YOLO v3 all videos]] [[A19 YOLO v3 result]] [[overview]]"
---
# A23: YOLO v4 — Retrained on All 5 Videos

## Context
YOLO v1 was trained only on 43_15 data (mAP50=0.192). YOLO v3 (A18) failed due to timestamp bug in extract_all_training.py. After fixing the timestamp bug (ms→frame conversion), retraining was possible.

## What changed
- Used `train_yolo.py` (whole-frame approach with multi-bbox labels per image)
- Fixed `find_data_dir()` to hardcode `Данные` path (was picking `yolo_all_videos`)
- Training params: imgsz=1280, batch=2, epochs=300, patience=50
- All 5 videos used for both train and val (80/20 split)

## Results
- **mAP50: 0.266** (up from 0.192 with v1)
- **mAP50-95: 0.112** (up from 0.045)
- Early stopping at epoch 170, best at epoch 120
- Model saved to `models/price_tag_yolo.pt`

## Detection impact (OCR-only, 40 frames)
| Video | v1 Det | v4 Det | Δ |
|-------|--------|--------|---|
| 43_15 | 26/29 90% | 27/29 93% | +1 |
| 25_12-20 | 20/57 35% | 23/57 40% | +3 |
| 25_2-10 | 23/56 41% | 40/56 71% | +17 |
| 26_12-20 | 35/71 49% | 38/71 54% | +3 |
| 49_5 | 20/61 33% | 28/61 46% | +8 |

## Key insight
Training on all 5 videos dramatically improves detection on previously-unseen video types (wine shelves, yogurt sections). The per-crop approach (extract_all_training.py) failed because of timestamp bugs; the whole-frame approach (train_yolo.py) works correctly.
