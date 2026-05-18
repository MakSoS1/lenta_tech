---
type: attempt
status: partial_success
accuracy: "prices: 11/29 (73% on readable), names: 0%, barcodes: 0%"
date: 2026-05-15
links: "[[overview]] [[RapidOCR]]"
---
# A7: RapidOCR (ONNX PaddleOCR)

**Подход**: RapidOCR (ONNX runtime PaddleOCR) на 4x upscaled sharpened кропах
**Результат**: 
- Цены: 11/29 (73% на читаемых тегах, w>200px)
- Имена: 0% — не читает русский
- Штрихкоды: 0%
- На thresholded изображениях хуже, чем на raw 4x
**Лучший конфиг**: scale=4, sharpening kernel, raw image (НЕ thresholded)
**Урок**: RapidOCR читает ЧИСЛА но не русский текст. Работает быстро (~0.5s/tag)
