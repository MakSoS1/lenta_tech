---
type: attempt
status: completed
date: 2026-05-16
links: "[[A17 VLM price mapping]] [[A21 Color Fallback]] [[A22 Price Filters]] [[overview]]"
---
# A20: Final Deployable Pipeline

**Цель**: Создать чистый класс-пайплайн, пригодный для FastAPI+Gradio деплоя

**Файлы**:
- `src/pipeline/price_tag_pipeline.py` — класс PriceTagPipeline
- `src/api/app.py` — обновлён для нового пайплайна, Gradio 6.0
- `run_api.py` — убран hardcoded Fireworks API key

**Pipeline flow**:
1. YOLO detect → NMS (IoU=0.3) → FP filter (size, aspect, conf)
2. Map NMS detections to best crop (Laplacian sharpness)
3. Detect color (HSV left strip)
4. OCR fallback (RapidOCR, scale=6, sharpen, conf≥0.3, price ending filter)
5. VLM for tags ≥200px (gemma4, temp=0.05)
6. Price validation (ending check, ratio check, swap if pd<pc)
7. Compute discount_amount from prices
8. Extract special_symbols from OCR text
9. Output CSV with 28 fields, UTF-8-BOM, point decimals

**Results on all 5 videos**: see [[v12 Results Summary]]

**Speed**: ~17 min/video (mainly VLM calls, ~30s each)
