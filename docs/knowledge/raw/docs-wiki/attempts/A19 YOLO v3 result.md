---
type: attempt
status: failed
date: 2026-05-16
links: "[[A18 YOLO v3 all videos]]"
---
# YOLO v3 Training Result

**mAP50**: 0.056 (v1 was 0.192)
**Detection on 43_15**: 1 tag out of 29 — TERRIBLE, worse than v1
**Cause**: GT bbox timestamps don't align with video frames well; many labels misplaced
**Decision**: REVERT to v1 model (price_tag_yolo.pt)
**Lesson**: Need frame-accurate annotation, not timestamp-based extraction

**Priority shift**: Focus on deployable pipeline + app.py instead of retraining
