---
type: attempt
status: completed
date: 2026-05-17
links: "[[A24 Time-aware NMS]] [[overview]]"
---
# A25: 60 Frames

## Change
Increased `num_frames` from 40 to 60 in `process_video()`.

## Rationale
- More frames = more opportunities to detect each tag
- Tags visible for only a few frames might be missed at lower frame rates
- The robot moves slowly, so 60 frames gives ~2s intervals instead of ~3s

## Impact (combined with time-aware NMS + YOLO v4)
Already reflected in A24 results. The 60 frames alone adds ~50% more raw detections, but the time-aware NMS ensures they're correctly deduplicated across time.

## Speed impact
- OCR-only: ~2 min/video (60 frames) vs ~1.5 min (40 frames)
- With VLM: ~40 min/video (80 tags × 30s) — VLM is the bottleneck, not frame count
