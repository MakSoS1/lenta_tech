---
type: attempt
status: failed
reason: too_many_false_positives
date: 2026-05-15
links: "[[overview]]"
---
# A2: Hybrid Pipeline (HSV detect + VLM OCR)

**Подход**: HSV детекция цвета → кропы → Kimi Vision OCR
**Результат**: HSV даёт слишком много false positives (упаковка тоже красная)
**Урок**: HSV без фильтрации не работает, цвет слишком общий признак
