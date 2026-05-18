---
type: component
---
# RapidOCR

ONNX-based PaddleOCR runtime (локальный, без PaddlePaddle)
- Модели: ch_PP-OCRv4_det + ch_PP-OCRv4_rec (китайский/английский)
- Скорость: ~0.5s/tag
- Конфиг: 6x upscale + sharpen kernel, conf≥0.3, rel_x 0.1-0.9 filter

**Что читает**: Целые числа (цены), иногда частично имена
**Что НЕ читает**: Десятичные копейки, русские названия, штрихкоды
**Price ending filter**: числа с необычными копейками отфильтрованы (see [[A22 Price Filters]])

**Used as**: OCR fallback when VLM fails or for tags < 200px wide
**Связи**: [[A7 RapidOCR]] → [[A12 Price Logic Fix]] → [[A22 Price Filters]]
