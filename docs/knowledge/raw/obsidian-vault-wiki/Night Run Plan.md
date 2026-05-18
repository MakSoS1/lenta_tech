---
type: plan
status: mostly_completed
date: 2026-05-16
links: "[[overview]] [[A20 Final Pipeline]]"
---
# Night Run Master Plan

## Goal
Win Lenta Tech Life Hack hackathon by building a complete local price tag recognition pipeline.

## Key Criteria (from audio.txt + task)
1. **Local only** — no external networks ("приоритет отдается решениям, которые можно повторить он-прям в контуре Ленты без выхода во внешние сети")
2. **Scalable** — must work across 6000+ stores ("масштабирование в разрезе всего нашего большого количества магазинов")
3. **Efficient** — "эффективным, я думаю, это очень важное слово"
4. **QR codes important** — "оптимизировать не только ценники, но и распознавать QR-коды, в которых зашита масса информации"
5. **New data** — tested on 5 videos, model must generalize

## Current Best Score (Final Pipeline)
- **See [[v12 Results Summary]] for per-video results**
- 43_15: 24/29 detection, key_fields=0.269
- All 5 videos processed, deployable app created

## Critical Issues
1. VLM reads wrong prices from adjacent tags (bbox captures multiple tags)
2. VLM hallucinates (30599,00 instead of 305,99)
3. 68 detections for 29 GT tags — many FPs
4. Output format wrong — sample.csv uses point decimals, we use comma
5. Missing fields: discount_amount, id_sku, print_datetime, code, special_symbols
6. QR codes unreadable at video resolution but GT has them

## Hypotheses Status
### H1: Price sub-crop for VLM — ❌ FAILED (see [[A14 Sub-crop VLM]])
### H2: Multi-frame VLM consensus — ❌ FAILED (see [[A16 Multi-frame VLM]])
### H3: Qwen2.5-VL via transformers — ❌ FAILED (download timeout, see [[A10 Qwen2-VL]])
### H4: Better YOLO training — ❌ FAILED (v3 mAP=0.056, see [[A19 YOLO v3 result]])
### H5: Intelligent field extraction — ✅ PARTIAL (discount_amount from prices, special_symbols from OCR)
### H6: QR code reading — ❌ IMPOSSIBLE (see [[QR Decoding]])
### H7: Output format fix — ✅ DONE (see [[A13 Output Format]])
### H8: FP filtering — ✅ DONE (size, aspect, conf filters + price filters, see [[A22 Price Filters]])

## Execution Status
1. ✅ Fix output format (H7) — [[A13 Output Format]]
2. ✅ Add intelligent field extraction (H5) — discount_amount, special_symbols
3. ❌ Test price sub-crop VLM (H1) — [[A14 Sub-crop VLM]] FAILED
4. ❌ Multi-frame consensus (H2) — [[A16 Multi-frame VLM]] FAILED
5. ❌ Retrain YOLO (H4) — [[A19 YOLO v3 result]] FAILED
6. ❌ Try Qwen2.5-VL (H3) — [[A10 Qwen2-VL]] FAILED
7. ❌ QR super-resolution (H6) — IMPOSSIBLE at video resolution
8. ✅ FP filtering (H8) — [[A22 Price Filters]]
9. ✅ Build final pipeline class — [[A20 Final Pipeline]]
10. ✅ Test on all 5 videos — [[v12 Results Summary]]
11. ✅ Update app.py — [[A20 Final Pipeline]]
12. ⏳ Speed optimization — ~17 min/video

## Notes on Generalization
- 43_15 has 29 red tags (honey/jam section)
- 26_12-20 has 71 rows (wine section) — different layout, colors
- 49_5 has 61 rows, yellow + red tags
- 25_12-20 has 57 rows, yellow + red
- 25_2-10 has 56 rows, red only
- Model must handle different product types, tag sizes, colors
- Wine tags likely larger (visible in sample.csv: 3789.49 rub prices!)
