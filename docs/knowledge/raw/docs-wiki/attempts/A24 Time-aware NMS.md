---
type: attempt
status: completed
date: 2026-05-17
links: "[[D4 Multi-Frame NMS]] [[D5 Current Best Detection]] [[overview]]"
---
# A24: Time-Aware NMS

## Problem
The previous `_time_aware_nms()` was actually doing **global NMS** — it ignored timestamps completely. Two different physical tags at the same pixel position but different times (e.g., t=0s and t=30s) would be merged into one. This is wrong because the robot moves along the shelf, so same pixel coords at different times = different physical tags.

## Solution
Added `time_window_ms=5000` parameter to `_time_aware_nms()`. Two detections are only merged if:
1. IoU > threshold (0.3), AND
2. Time difference ≤ 5 seconds

If IoU > threshold but time difference > 5s, both detections are kept.

## Code change
```python
def _time_aware_nms(self, all_dets, iou_thr, time_window_ms=5000):
    ...
    for item in sorted_dets:
        for ki, kept in enumerate(keep):
            iou = self._det_iou(det_i, det_k)
            if iou > iou_thr:
                dt = abs(item['ts_ms'] - kept['ts_ms'])
                if dt <= time_window_ms:  # <-- NEW: only suppress if close in time
                    suppressed = True
                    ...
```

## Impact (OCR-only, 60 frames)
| Video | Global NMS | Time-aware NMS | Δ matches |
|-------|-----------|----------------|-----------|
| 25_12-20 | 23/57 40% | **54/57 95%** | +31 |
| 26_12-20 | 38/71 54% | **56/71 79%** | +18 |
| 49_5 | 28/61 46% | **35/61 57%** | +7 |

## Key insight
Global NMS was the biggest bottleneck for non-43_15 videos. The wine section (26_12-20) and spirit section (25_12-20) have many tags at similar positions across time, which global NMS was incorrectly merging.
