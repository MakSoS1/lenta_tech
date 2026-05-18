---
type: attempt
status: completed
date: 2026-05-15
links: "[[overview]] [[RapidOCR]] [[YOLO Detection]] [[A22 Price Filters]]"
---
# A12: Improved Price Logic

**Проблема**: RapidOCR читает числа с соседних тегов (bbox YOLO захватывает несколько тегов)
**Анализ GT matches**:
- GT[4] pd=652,69 → pred=244,00 (читает цену соседнего тега!)
- GT[7] pd=305,29 → pred=259,00 (VLM галлюцинирует)
- GT[8] pd=221,09 → pred=305,00 (другой тег)
- GT[11] pd=368,42 → pred=39,90 (кусок числа)

**Fix**: 
1. Ограничить кроп tighter (padding=10 вместо 30)
2. Фильтровать OCR по позиции — брать числа из центра кропа
3. Не перезаписывать RapidOCR цены VLM-ом
4. Добавить confidence фильтр к OCR результатам
