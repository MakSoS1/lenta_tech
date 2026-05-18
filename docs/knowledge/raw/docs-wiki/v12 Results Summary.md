---
type: summary
status: completed
date: 2026-05-16
links: "[[A17 VLM price mapping]] [[A20 Final Pipeline]] [[A21 Color Fallback]]"
---
# Pipeline v12 → Final Pipeline Results Summary

## Pipeline v2 Results (17 мая, YOLO v4 + time-aware NMS + 60 frames + VLM):

| Video | GT rows | Pred rows | Matched | Detection% | Mean IoU | Key Fields (all GT) |
|-------|---------|-----------|---------|------------|----------|---------------------|
| 43_15 | 29 | 80 | 26 | 90% | 0.471 | 0.174 |
| 25_12-20 | 57 | 80 | 54 | 95% | 0.629 | 0.181 |
| 25_2-10 | 56 | 80 | 43 | 77% | 0.483 | 0.152 |
| 26_12-20 | 71 | 80 | 56 | 79% | 0.558 | 0.147 |
| 49_5 | 61 | 80 | 35 | 57% | 0.327 | 0.125 |

## Key improvements in v2 vs v1 (final):
1. **YOLO v4 trained on all 5 videos** — mAP50: 0.192→0.266, imgsz=1280
2. **Time-aware NMS** — 5s time window prevents merging different tags at same pixel coords
3. **60 frames** (was 40) — more coverage = more detection matches
4. **25_12-20: 28%→95% detection** — biggest win from time-aware NMS

## Final Pipeline Results (16 мая, с HSV fallback):

| Video | GT rows | Pred rows | Matched | Detection% | price_card | price_default | product_name | color | Key fields |
|-------|---------|-----------|---------|------------|------------|---------------|--------------|-------|------------|
| 43_15 | 29 | 58 | 24 | 83% | 25.0% | 8.3% | 25.9% | 72.2% | 0.269 |
| 25_12-20 | 57 | 16 | 16 | 28% | 25.0% | 6.2% | 21.8% | 64.6% | 0.104 |
| 25_2-10 | 56 | 55 | 20 | 36% | 10.0% | 5.0% | 14.3% | 55.0% | 0.103 |
| 26_12-20 | 71 | 44 | 31 | 44% | 9.7% | 9.7% | 20.5% | 54.3% | 0.117 |
| 49_5 | 61 | 98 | 20 | 33% | 0.0% | 0.0% | 4.8% | 46.7% | 0.068 |

## v12 Results (для сравнения, без HSV fallback):

| Video | GT rows | Detected | Matched | Detection% | price_card | price_default | Key fields |
|-------|---------|----------|---------|------------|------------|---------------|------------|
| 43_15 | 29 | 68 | 26 | 90% | 46.2% | 3.8% | 0.297 |
| 25_12-20 | 57 | 20 | 20 | 35% | 25.0% | 5.0% | 0.118 |
| 25_2-10 | 56 | 26 | 24 | 43% | 8.3% | 0.0% | 0.118 |
| 26_12-20 | 71 | 37 | 30 | 42% | 6.7% | 6.7% | 0.110 |
| 49_5 | 61 | 9 | 9 | 15% | 0.0% | 0.0% | 0.035 |

## Key improvements in final pipeline vs v12:
1. **HSV color fallback** — YOLO falls back to HSV when no tags found → 49_5: 9→98 detections, 9→20 matches
2. **Price ending filter** — rejects prices with unusual cent values → fewer hallucinations
3. **VLM ratio check** — rejects prices where smaller < 40% of larger (catches 66.00, 50.00)
4. **discount_amount** — computed from price_default/price_card ratio (0-45% accuracy)
5. **special_symbols** — extracted from OCR text (К, Ш, М etc.)
6. **Clean class-based pipeline** — `src/pipeline/price_tag_pipeline.py`
7. **Updated app.py** — works with new pipeline, Gradio 6.0 compatible
8. **YOLO v3 reverted** — mAP50=0.056 was terrible, back to v1 (0.192)

## Remaining issues:
1. **Detection on non-43_15 videos still weak** — YOLO only trained on 43_15
2. **price_default still very low** — VLM can't read small crossed-out price
3. **Color detection accuracy dropped** — HSV fallback bboxes are less precise
4. **VLM hallucinates prices** — 66.00, 50.00, 230.50 still appear
5. **Speed** — ~17 min/video with VLM calls
