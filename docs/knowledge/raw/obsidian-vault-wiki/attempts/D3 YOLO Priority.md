---
type: detection_attempt
status: good
accuracy: "25/29 match (86%), IoU mean=0.5"
date: 2026-05-15
links: "[[overview]] [[YOLO Detection]]"
---
# D3: YOLO Priority Detection

**Подход**: YOLOv8n (mAP50=0.192, 13 val images) → только YOLO детекции
**Результат**: YOLO даёт 10-11 точных bbox на кадр (IoU 0.4-0.6), HSV не используется
**10/11 YOLO bbox совпадают с GT** — высокая precision но низкая recall
**Урок**: YOLO точнее HSV, но нужна больше recall → multi-frame
