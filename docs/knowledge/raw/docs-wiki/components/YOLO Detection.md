---
type: component
---
# YOLO Detection

Модель: YOLOv8n, обученная на GT CSV данных
- v1: `models/price_tag_yolo.pt` (mAP50=0.192, 43_15 only) — **CURRENTLY USED**
- v3: `models/price_tag_yolo_v3.pt` (mAP50=0.056, all videos) — **FAILED, REVERTED**
- Conf threshold: 0.05 (низкий, компенсируется NMS)
- IoU NMS: 0.3
- HSV color fallback enabled when YOLO finds no tags

**v3 Failure** (see [[A19 YOLO v3 result]]):
- mAP50=0.056 (v1 was 0.192)
- Only 1/29 tags detected on 43_15
- Cause: GT bbox timestamps don't align with video frames
- Decision: Revert to v1, use HSV as fallback for other videos

**v1 Weaknesses**: 
- Only trained on 43_15 data → fails on wine/yogurt sections
- 25_12-20: 20 detections, 49_5: 9 detections
- HSV fallback boosts: 49_5→98, 25_2-10→55

**Связи**: [[D3 YOLO Priority]] → [[D4 Multi-Frame NMS]] → [[D5 Current Best Detection]] → [[A21 Color Fallback]]
