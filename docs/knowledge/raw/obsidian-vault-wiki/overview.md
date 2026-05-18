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

## Текущий статус (Final Pipeline — 16 мая 20:30)
- **Пайплайн**: `src/pipeline/price_tag_pipeline.py` + `src/api/app.py`
- **Detection 43_15**: 24/29 (83%) — YOLO v1
- **Detection other**: 20-31% — YOLO + HSV fallback
- **Key fields avg**: 0.068–0.269 (зависит от видео)

| Video | Detection | Mean IoU | Key Fields | price_card | price_default | product_name | color |
|-------|-----------|----------|------------|------------|---------------|--------------|-------|
| 43_15 | 24/29 83% | 0.524 | 0.269 | 25.0% | 8.3% | 25.9% | 72.2% |
| 25_12-20 | 16/57 28% | 0.201 | 0.104 | 25.0% | 6.2% | 21.8% | 64.6% |
| 25_2-10 | 20/56 36% | 0.190 | 0.103 | 10.0% | 5.0% | 14.3% | 55.0% |
| 26_12-20 | 31/71 44% | 0.278 | 0.117 | 9.7% | 9.7% | 20.5% | 54.3% |
| 49_5 | 20/61 33% | 0.138 | 0.068 | 0.0% | 0.0% | 4.8% | 46.7% |

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
    P1 --> RESULT[Результат: 5 видео, deployable app]
```

## Компоненты пайплайна
- [[YOLO Detection]] — детекция ценников
- [[Color Detection]] — определение цвета тега
- [[RapidOCR]] — локальный OCR (ONNX PaddleOCR)
- [[Ollama VLM]] — Gemma3/4 через Ollama
- [[QR Decoding]] — QR коды слишком малы

## Что ещё можно сделать
1. **Улучшить YOLO детекцию** — v3 провалился, нужен frame-accurate annotation или HSV tuning
2. **Лучший price_default** — VLM не может прочитать мелкую перечёркнутую цену
3. **Увеличить num_frames** — больше кадров = больше GT матчей на др. видео
4. **Улучшить VLM prompt** — русский текст читается плохо
5. **Скорость** — 58 тегов × 30s VLM = ~17 мин/видео

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
- [[D1 HSV Detection]]
- [[D2 Bbox Expansion]]
- [[D3 YOLO Priority]]
- [[D4 Multi-Frame NMS]]
- [[D5 Current Best Detection]]
