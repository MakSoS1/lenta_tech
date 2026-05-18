---
type: attempt
status: failed
reason: single_character_output
date: 2026-05-15
links: "[[overview]]"
---
# A5: EasyOCR GPU

**Подход**: EasyOCR с GPU на 4x upscaled кропах
**Результат**: 1 символ на кроп (хуже RapidOCR)
**Проблема**: EasyOCR не справляется с мелким текстом даже на GPU
**Урок**: EasyOCR хуже RapidOCR для данной задачи
