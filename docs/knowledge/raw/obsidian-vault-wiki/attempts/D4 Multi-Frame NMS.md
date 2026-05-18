---
type: detection_attempt
status: best
accuracy: "26/29 match (90%), IoU mean=0.446"
date: 2026-05-15
links: "[[overview]] [[D3 YOLO Priority]]"
---
# D4: Multi-Frame NMS

**Подход**: YOLO на 30 кадрах (каждый 10-й) → 480 raw → NMS (IoU 0.3) → 65 уникальных
**Результат**: 26/29 GT тегов совпадают с pred (IoU >= 0.3), Mean IoU=0.446
**3 ненайденных GT**: GT[17] (3219,1067), GT[21] (2251,510), GT[28] (338,854)
**Проблема**: 65 pred тегов → много false positives, но GT matching работает
**Урок**: Multi-frame + NMS даёт лучшую recall. Без агрегации результаты лучше.
