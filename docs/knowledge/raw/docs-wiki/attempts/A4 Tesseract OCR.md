---
type: attempt
status: failed
reason: garbage_output
date: 2026-05-15
links: "[[overview]] [[RapidOCR]]"
---
# A4: Tesseract OCR

**Подход**: YOLO детекция → Tesseract OCR на кропах
**Результат**: Полный мусор — одиночные символы, бессмысленный текст
**Проблема**: Кропы ценников слишком малы (100-200px), текст нечитаем даже при 4x upscale
**Урок**: Tesseract не подходит для мелкого русского текста на ценниках
