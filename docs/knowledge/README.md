# Research Knowledge Graph

Эта папка сохраняет Obsidian-граф как презентационный research pack: исходные заметки, связи между гипотезами, краткие выводы и JSON для интерактивной страницы.

## Executive Story

1. Сначала проверялись быстрые OCR/VLM-гипотезы: Tesseract, EasyOCR, PaddleOCR, RapidOCR, локальный Ollama и несколько VLM-направлений.
2. Затем фокус сместился в детекцию: HSV, bbox expansion, YOLO priority, multi-frame NMS, YOLO v4 и time-aware NMS.
3. Отдельный поток закрыл CSV-контракт, price filters, цвет, QR-ограничения и API/UI для сдачи.
4. Финальный вывод для презентации: задача не сводится к OCR, это edge-контур контроля ценников с честным fallback и repeat-pass registration.

## Graph Snapshot

- Notes: `39`
- Links: `62`
- Attempts: `31`
- Components: `5`
- Attempt statuses: `{'failed': 17, 'done': 11, 'partial': 3}`

## Core Notes

- [Night Run Master Plan](raw/docs-wiki/Night%20Run%20Plan.md) — Win Lenta Tech Life Hack hackathon by building a complete local price tag recognition pipeline. 1. **Local only** — no external networks ("приоритет отдается решениям, которые можно повторить он-прям в контуре Ленты без
- [Lenta Tech Life Hack — Knowledge Graph](raw/docs-wiki/overview.md) — Хакатон Лента Tech Life Hack. Дедлайн: **19 мая 15:00**. Задача: детекция ценников + OCR + QR → CSV с 28 полями, >0.95 accuracy. **Все модели локально, без облака.** **Пайплайн**: `src/pipeline/price_tag_pipeline.py` + `
- [Pipeline v12 → Final Pipeline Results Summary](raw/docs-wiki/v12%20Results%20Summary.md) — 1. **YOLO v4 trained on all 5 videos** — mAP50: 0.192→0.266, imgsz=1280 2. **Time-aware NMS** — 5s time window prevents merging different tags at same pixel coords 3. **60 frames** (was 40) — more coverage = more detecti

## Components

- [Color Detection](raw/docs-wiki/components/Color%20Detection.md) — HSV-based определение цвета ценника: Red: H 0-10 или 170-180 Yellow: H 20-35 Orange: H 10-20 Default: "red" **Текущая accuracy**: 54-72% (varies by video) **Method**: Анализировать левую треть кропа (где цветная полоска)
- [Ollama VLM](raw/docs-wiki/components/Ollama%20VLM.md) — Локальные VLM через Ollama API (localhost:11434) Gemma4:latest — 9.6GB, **ONLY model used for prices** (reads correct kopecks) Gemma3:4b — 3.3GB, **REJECTED** (hallucinates .90 kopecks: 349.90, 149.90 etc.)
- [QR Decoding](raw/docs-wiki/components/QR%20Decoding.md) — QR коды НЕ найдены ни одним декодером: pyzbar: 0 QR на всём видео zxing-cpp: 0 QR на всём видео (scan 299 frames) Проблема: QR коды на ценниках слишком малы (ценник 100-200px, QR ~20-30px)
- [RapidOCR](raw/docs-wiki/components/RapidOCR.md) — ONNX-based PaddleOCR runtime (локальный, без PaddlePaddle) Модели: ch_PP-OCRv4_det + ch_PP-OCRv4_rec (китайский/английский) Скорость: ~0.5s/tag Конфиг: 6x upscale + sharpen kernel, conf≥0.3, rel_x 0.1-0.9 filter
- [YOLO Detection](raw/docs-wiki/components/YOLO%20Detection.md) — Модель: YOLOv8n, обученная на GT CSV данных v1: `models/price_tag_yolo.pt` (mAP50=0.192, 43_15 only) — **CURRENTLY USED** v3: `models/price_tag_yolo_v3.pt` (mAP50=0.056, all videos) — **FAILED, REVERTED**

## Attempt Timeline

- `failed` [A1: VLM Pipeline (Kimi K2.6 Vision)](raw/docs-wiki/attempts/A1%20VLM%20Pipeline.md) — **Подход**: Полный кадр → Kimi K2.6 Vision (Fireworks API) → все теги за 1 вызов **Результат**: 10-16 тегов на кадр, найдены все поля **Причина отказа**: Облако запрещено правилами хакатона — "приоритет отдается решениям
- `failed` [A10: Qwen2-VL-2B-Instruct](raw/docs-wiki/attempts/A10%20Qwen2-VL.md) — **Подход**: Локальный VLM Qwen2-VL-2B через transformers **Результат**: Скачивание 4GB модели через HuggingFace слишком медленное (>10 мин timeout) **Qwen2-VL-0.5B**: Требует авторизацию (401 Unauthorized) — gated model
- `failed` [A11: Florence-2-base](raw/docs-wiki/attempts/A11%20Florence-2.md) — **Подход**: Microsoft Florence-2 через transformers **Результат**: Загружается (0.9GB VRAM), но generate() падает с: 1. `past_key_values[0][0].shape[2]` — NoneType (патчили)
- `done` [A12: Improved Price Logic](raw/docs-wiki/attempts/A12%20Price%20Logic%20Fix.md) — **Проблема**: RapidOCR читает числа с соседних тегов (bbox YOLO захватывает несколько тегов) **Анализ GT matches**: GT[4] pd=652,69 → pred=244,00 (читает цену соседнего тега!)
- `done` [A13: Output Format Fix](raw/docs-wiki/attempts/A13%20Output%20Format.md) — **Problem**: Output CSV doesn't match sample.csv format **Findings**: sample.csv uses POINT decimals: 3789.49, 2011.9 Our output uses COMMA: 305,00, 1092 GT CSVs use comma but sample (expected output) uses point
- `failed` [A14: Sub-crop VLM (Price + Name separate calls)](raw/docs-wiki/attempts/A14%20Sub-crop%20VLM.md) — **Hypothesis**: Sub-crop lower 60% for price, upper 45% for name → less adjacent tag bleed **Result**: FAILED Price sub-crop too small → VLM reads random numbers (15.00, 30.00, 19.00, 14.00)
- `done` [A15 Results: Tiered VLM](raw/docs-wiki/attempts/A15%20Tiered%20VLM%20Results.md) — **Setup**: gemma4 for tags ≥250px, gemma3:4b for tags ≥130px **Result**: price_default: 3.8%, price_card: 7.7%, product_name: 20.8% Detection: 26/29, Mean IoU: 0.446 **Key Finding**: gemma3:4b HALLUCINATES .90 kopecks (3
- `done` [A15: Tiered VLM Strategy](raw/docs-wiki/attempts/A15%20Tiered%20VLM.md) — **Problem**: v9 gave 8% price_default, 12% price_card at ±0.5 threshold **Root causes**: 1. VLM reads price_card as price_default (confuses which is which) 2. VLM reads prices from adjacent tags (bbox overlap)
- `failed` [A16: Multi-frame VLM consensus](raw/docs-wiki/attempts/A16%20Multi-frame%20VLM.md) — **Hypothesis**: Read same tag from 2 frames, take consensus **Result**: FAILED - too slow (1800s for 37/68 tags, would take 60+ min total) **Insight**: Multi-frame VLM doubles time with minimal accuracy gain
- `failed` [A17: VLM price mapping fix](raw/docs-wiki/attempts/A17%20VLM%20price%20mapping.md) — **Hypothesis**: VLM reads prominent number as price_default, but it's actually price_card. Fix mapping: VLM→price_card, use OCR for price_default. **Result**: price_card 46.2% (up from 0%), price_default stuck at 3.8%
- `failed` [YOLO v3 Training on All 5 Videos](raw/docs-wiki/attempts/A18%20YOLO%20v3%20all%20videos.md) — **Dataset**: 856 images from all 5 videos (extracted GT bboxes) **Model**: YOLOv8n, 100 epochs, batch=8, workers=0 (Windows fix) **Final mAP50**: 0.056 (stopped at epoch 48 by early stopping)
- `failed` [YOLO v3 Training Result](raw/docs-wiki/attempts/A19%20YOLO%20v3%20result.md) — **mAP50**: 0.056 (v1 was 0.192) **Detection on 43_15**: 1 tag out of 29 — TERRIBLE, worse than v1 **Cause**: GT bbox timestamps don't align with video frames well; many labels misplaced
- `failed` [A2: Hybrid Pipeline (HSV detect + VLM OCR)](raw/docs-wiki/attempts/A2%20Hybrid%20Pipeline.md) — **Подход**: HSV детекция цвета → кропы → Kimi Vision OCR **Результат**: HSV даёт слишком много false positives (упаковка тоже красная) **Урок**: HSV без фильтрации не работает, цвет слишком общий признак
- `done` [A20: Final Deployable Pipeline](raw/docs-wiki/attempts/A20%20Final%20Pipeline.md) — **Цель**: Создать чистый класс-пайплайн, пригодный для FastAPI+Gradio деплоя **Файлы**: `src/pipeline/price_tag_pipeline.py` — класс PriceTagPipeline `src/api/app.py` — обновлён для нового пайплайна, Gradio 6.0
- `done` [A21: HSV Color Fallback for Detection](raw/docs-wiki/attempts/A21%20Color%20Fallback.md) — **Проблема**: YOLO v1 trained only on 43_15 → fails on other videos (49_5: 9/61 detected) **Решение**: Включить HSV color fallback в TagDetector.detect() — YOLO пробует первым, если 0 результатов → HSV
- `done` [A22: Price Filters (Anti-Hallucination)](raw/docs-wiki/attempts/A22%20Price%20Filters.md) — **Проблема**: VLM галлюцинирует цены — 66.00, 50.00, 230.50, 14.00, 21.00 **Три уровня фильтрации**: Reject prices < 50 рублей Убирает мелкие галлюцинации (14.00, 21.00, 16.00)
- `failed` [A23: YOLO v4 — Retrained on All 5 Videos](raw/docs-wiki/attempts/A23%20YOLO%20v4%20all%20videos.md) — YOLO v1 was trained only on 43_15 data (mAP50=0.192). YOLO v3 (A18) failed due to timestamp bug in extract_all_training.py. After fixing the timestamp bug (ms→frame conversion), retraining was possible.
- `done` [A24: Time-Aware NMS](raw/docs-wiki/attempts/A24%20Time-aware%20NMS.md) — The previous `_time_aware_nms()` was actually doing **global NMS** — it ignored timestamps completely. Two different physical tags at the same pixel position but different times (e.g., t=0s and t=30s) would be merged int
- `done` [A25: 60 Frames](raw/docs-wiki/attempts/A25%2060%20frames.md) — Increased `num_frames` from 40 to 60 in `process_video()`. More frames = more opportunities to detect each tag Tags visible for only a few frames might be missed at lower frame rates
- `failed` [A3: Two-Stage Pipeline (VLM detect + VLM OCR)](raw/docs-wiki/attempts/A3%20Two-Stage%20Pipeline.md) — **Подход**: VLM детекция → VLM OCR на кропах **Результат**: 29/29 тегов, но низкая точность полей (7/29 bbox, 0% field match) **Причина отказа**: Облако + низкая точность **Урок**: VLM не точен для bbox координат
- `failed` [A4: Tesseract OCR](raw/docs-wiki/attempts/A4%20Tesseract%20OCR.md) — **Подход**: YOLO детекция → Tesseract OCR на кропах **Результат**: Полный мусор — одиночные символы, бессмысленный текст **Проблема**: Кропы ценников слишком малы (100-200px), текст нечитаем даже при 4x upscale
- `failed` [A5: EasyOCR GPU](raw/docs-wiki/attempts/A5%20EasyOCR%20GPU.md) — **Подход**: EasyOCR с GPU на 4x upscaled кропах **Результат**: 1 символ на кроп (хуже RapidOCR) **Проблема**: EasyOCR не справляется с мелким текстом даже на GPU **Урок**: EasyOCR хуже RapidOCR для данной задачи
- `failed` [A6: PaddleOCR](raw/docs-wiki/attempts/A6%20PaddleOCR.md) — **Подход**: PaddleOCR v5 (server+mobile) **Результат**: Crash на Windows — `(Unimplemented) ConvertPirAttribute2RuntimeAttribute` (OneDNN bug) **Альтернатива**: PaddleOCR v4 тоже не ставится (paddlepaddle==2.6.1 нет для
- `partial` [A7: RapidOCR (ONNX PaddleOCR)](raw/docs-wiki/attempts/A7%20RapidOCR.md) — **Подход**: RapidOCR (ONNX runtime PaddleOCR) на 4x upscaled sharpened кропах **Результат**: Цены: 11/29 (73% на читаемых тегах, w>200px) Имена: 0% — не читает русский Штрихкоды: 0%
- `partial` [A8: Ollama VLM (Gemma3:4b / Gemma4)](raw/docs-wiki/attempts/A8%20Ollama%20VLM.md) — **Подход**: Ollama Gemma3:4b или Gemma4 через API на 4x кропах **Результат**: Цены: частично (37.9% на GT кропах, но медленно ~30s/tag) Имена: галлюцинирует ("Мясо", "Детское питание" вместо мёда)
- `failed` [A9: Fireworks VLM (kimi-k2p6)](raw/docs-wiki/attempts/A9%20Fireworks%20VLM.md) — **Подход**: Fireworks API с моделью kimi-k2p6 **Результат**: Account suspended (412 Precondition Failed) — "monthly spending limit" **Урок**: Fireworks VLM работал ранее (A1) но аккаунт исчерпан. Нельзя полагаться на обл
- `partial` [D1: HSV Color Detection](raw/docs-wiki/attempts/D1%20HSV%20Detection.md) — **Подход**: HSV маска (red+yellow) → контуры → bbox **Результат**: 23-28 тегов на кадр, но bbox слишком узкие (только цветная полоска, не весь тег) **Проблема**: HSV детектирует только красную/жёлтую часть ценника, без т
- `failed` [D2: Bbox Expansion](raw/docs-wiki/attempts/D2%20Bbox%20Expansion.md) — **Подход**: Расширение HSV bbox вправо на 2x ширины **Результат**: 29 тегов (совпадает с GT!), но IoU всего 0.112 (8/29 match) **Проблема**: Слишком широкие bbox → перекрытие соседних тегов → NMS мёржит разные теги
- `done` [D3: YOLO Priority Detection](raw/docs-wiki/attempts/D3%20YOLO%20Priority.md) — **Подход**: YOLOv8n (mAP50=0.192, 13 val images) → только YOLO детекции **Результат**: YOLO даёт 10-11 точных bbox на кадр (IoU 0.4-0.6), HSV не используется **10/11 YOLO bbox совпадают с GT** — высокая precision но низк
- `done` [D4: Multi-Frame NMS](raw/docs-wiki/attempts/D4%20Multi-Frame%20NMS.md) — **Подход**: YOLO на 30 кадрах (каждый 10-й) → 480 raw → NMS (IoU 0.3) → 65 уникальных **Результат**: 26/29 GT тегов совпадают с pred (IoU >= 0.3), Mean IoU=0.446 **3 ненайденных GT**: GT[17] (3219,1067), GT[21] (2251,510
- `failed` [D5→Final: Current Best Detection](raw/docs-wiki/attempts/D5%20Current%20Best%20Detection.md) — **Конфигурация**: YOLOv8n v1 (conf=0.05, NMS IoU=0.3) + HSV color fallback **Pipeline**: `src/pipeline/price_tag_pipeline.py` **Results per video (с HSV fallback)**: **HSV fallback impact** (see A21 Color Fallback):

## Presentation Hooks

- **Не магия модели, а инженерный поиск:** видно, какие гипотезы отбрасывались и почему.
- **Локальность как бизнес-требование:** облачные VLM были исследованы, но финальный путь локальный.
- **Честность метрик:** в заметках отделены public-fit эксперименты от production fallback.
- **Путь к масштабу:** повторные проходы робота дают регистрацию и стабильный контроль полки.

## Raw Sources

- [`raw/docs-wiki`](raw/docs-wiki) — наиболее полная Markdown-копия wiki.
- [`raw/obsidian-vault-wiki`](raw/obsidian-vault-wiki) — исходный Obsidian vault с `.canvas`.
- [`graph.json`](graph.json) — нормализованный граф для сайта.
