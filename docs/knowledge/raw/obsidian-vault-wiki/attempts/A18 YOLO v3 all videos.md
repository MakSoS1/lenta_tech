---
type: attempt
status: failed
date: 2026-05-16
links: "[[v12 Results Summary]] [[A19 YOLO v3 result]]"
---
# YOLO v3 Training on All 5 Videos

**Dataset**: 856 images from all 5 videos (extracted GT bboxes)
**Model**: YOLOv8n, 100 epochs, batch=8, workers=0 (Windows fix)
**Final mAP50**: 0.056 (stopped at epoch 48 by early stopping)
**Detection on 43_15**: 1 tag out of 29 — TERRIBLE

**Cause**: GT bbox timestamps don't align with video frames well; many labels misplaced
**Decision**: REVERT to v1 model — see [[A19 YOLO v3 result]]
**Lesson**: Need frame-accurate annotation, not timestamp-based extraction
