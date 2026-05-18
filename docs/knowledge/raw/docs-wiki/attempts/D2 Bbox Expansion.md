---
type: detection_attempt
status: failed
reason: overlap_merging
date: 2026-05-15
links: "[[overview]] [[D1 HSV Detection]]"
---
# D2: Bbox Expansion

**Подход**: Расширение HSV bbox вправо на 2x ширины
**Результат**: 29 тегов (совпадает с GT!), но IoU всего 0.112 (8/29 match)
**Проблема**: Слишком широкие bbox → перекрытие соседних тегов → NMS мёржит разные теги
**Урок**: Простое расширение не работает — нужна YOLO с точными bbox
