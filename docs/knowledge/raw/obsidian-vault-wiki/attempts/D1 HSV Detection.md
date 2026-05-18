---
type: detection_attempt
status: partial_success
accuracy: "23 tags/frame, но bbox не совпадают с GT"
date: 2026-05-15
links: "[[overview]] [[Color Detection]]"
---
# D1: HSV Color Detection

**Подход**: HSV маска (red+yellow) → контуры → bbox
**Результат**: 23-28 тегов на кадр, но bbox слишком узкие (только цветная полоска, не весь тег)
**Проблема**: HSV детектирует только красную/жёлтую часть ценника, без текстовой области
**GT bbox**: 100-200px шириной, HSV bbox: 80-100px (только цветная полоска слева)
**Урок**: HSV находит теги но bbox неточные. Нужно расширение вправо (где текст)
