---
type: overview
banner: 
banner_icon: 🧠
---
# Lenta Tech Life Hack — Knowledge Graph

## Проект
Хакатон Лента Tech Life Hack. Дедлайн: **19 мая 15:00**.
Задача: детекция ценников + OCR + QR → CSV с 28 полями, >0.95 accuracy.
**Все модели локально, без облака.**

## Текущий статус (v2 Pipeline — 17 мая)
- **Пайплайн**: `src/pipeline/price_tag_pipeline.py` + `src/api/app.py`
- **YOLO v4**: обучен на всех 5 видео, mAP50=0.266 (было 0.192)
- **Time-aware NMS**: 5s окно (было global NMS — сливал разные теги)
- **60 кадров** (было 40)

| Video | Detection | Mean IoU | Key Fields (all GT) |
|-------|-----------|----------|---------------------|
| 43_15 | 26/29 90% | 0.471 | 0.174 |
| 25_12-20 | 54/57 95% | 0.629 | 0.181 |
| 25_2-10 | 43/56 77% | 0.483 | 0.152 |
| 26_12-20 | 56/71 79% | 0.558 | 0.147 |
| 49_5 | 35/61 57% | 0.327 | 0.125 |

## Граф попыток

```mermaid
graph TD
    A1[A1: VLM Pipeline] -->|облако| X1[❌ Запрещено]
    A2[A2: Hybrid HSV+VLM] -->|много FP| X2[❌ Отброшен]
    A3[A3: Two-Stage VLM] -->|облако| X1
    A4[A4: Tesseract OCR] -->|мусор| X3[❌ Нечитает]
    A5[A5: EasyOCR GPU] -->|1 символ| X3
    A6[A6: PaddleOCR v5] -->|crash Win| X4[❌ Windows bug]
    A7[A7: RapidOCR] -->|частично| B1[✅ Цены видит]
    A8[A8: Ollama Gemma4] -->|медленно+галлюцинации| B2[⚠️ Частично]
    A9[A9: Fireworks VLM] -->|account suspended| X5[❌ Нет доступа]
    A10[A10: Qwen2-VL-2B] -->|скачивается слишком долго| X6[❌ Timeout]
    A11[A11: Florence-2] -->|баг past_key_values| X7[❌ Transformrs bug]
    
    D1[D1: HSV детекция] -->|узкие bbox| D2[D2: Расширение bbox]
    D2 -->|слишком широко| D3[D3: YOLO priority]
    D3 -->|25/29 match| D4[D4: Multi-frame NMS]
    D4 -->|26/29] D5[D5: Текущий лучший]
    
    B1 --> P1[Pipeline: YOLO+HSV+RapidOCR+Ollama]
    B2 --> P1
    D5 --> P1
    A17[A17: VLM price mapping] -->|pc=46%| P1
    A19[A19: YOLO v3 FAILED] -->|revert v1| D5
    A20[A20: Final Pipeline] --> P1
    A21[A21: Color Fallback] -->|49_5: 4→20 match| P1
    A22[A22: Price Filters] -->|less hallucinations| P1
    A23[A23: YOLO v4 all videos] -->|mAP50 0.266| P2[Pipeline v2]
    A24[A24: Time-aware NMS] -->|5s window| P2
    A25[A25: 60 frames] -->|better coverage| P2
    P1 --> RESULT[Результат: 5 видео, deployable app]
    P2 --> RESULT
```

## Компоненты пайплайна
- [[YOLO Detection]] — детекция ценников
- [[Color Detection]] — определение цвета тега
- [[RapidOCR]] — локальный OCR (ONNX PaddleOCR)
- [[Ollama VLM]] — Gemma3/4 через Ollama
- [[QR Decoding]] — QR коды слишком малы

## Что ещё можно сделать
1. **Улучшить price_default** — VLM не может прочитать мелкую перечёркнутую цену (~3.5%)
2. **Улучшить product_name** — VLM читает криво (~20%)
3. **Увеличить num_frames** — больше кадров = больше GT матчей на др. видео
4. **Улучшить VLM prompt** — русский текст читается плохо
5. **Скорость** — 80 тегов × 30s VLM = ~40 мин/видео

## Все попытки
- [[A1 VLM Pipeline]]
- [[A2 Hybrid Pipeline]]
- [[A3 Two-Stage Pipeline]]
- [[A4 Tesseract OCR]]
- [[A5 EasyOCR GPU]]
- [[A6 PaddleOCR]]
- [[A7 RapidOCR]]
- [[A8 Ollama VLM]]
- [[A9 Fireworks VLM]]
- [[A10 Qwen2-VL]]
- [[A11 Florence-2]]
- [[A12 Price Logic Fix]]
- [[A13 Output Format]]
- [[A14 Sub-crop VLM]]
- [[A15 Tiered VLM]]
- [[A15 Tiered VLM Results]]
- [[A16 Multi-frame VLM]]
- [[A17 VLM price mapping]]
- [[A18 YOLO v3 all videos]]
- [[A19 YOLO v3 result]]
- [[A20 Final Pipeline]]
- [[A21 Color Fallback]]
- [[A22 Price Filters]]
- [[A23 YOLO v4 all videos]]
- [[A24 Time-aware NMS]]
- [[A25 60 frames]]
- [[D1 HSV Detection]]
- [[D2 Bbox Expansion]]
- [[D3 YOLO Priority]]
- [[D4 Multi-Frame NMS]]
- [[D5 Current Best Detection]]
