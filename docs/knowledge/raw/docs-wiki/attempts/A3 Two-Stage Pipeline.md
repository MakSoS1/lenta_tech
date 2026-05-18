---
type: attempt
status: failed
reason: cloud_api_forbidden
date: 2026-05-15
links: "[[overview]]"
---
# A3: Two-Stage Pipeline (VLM detect + VLM OCR)

**Подход**: VLM детекция → VLM OCR на кропах
**Результат**: 29/29 тегов, но низкая точность полей (7/29 bbox, 0% field match)
**Причина отказа**: Облако + низкая точность
**Урок**: VLM не точен для bbox координат
