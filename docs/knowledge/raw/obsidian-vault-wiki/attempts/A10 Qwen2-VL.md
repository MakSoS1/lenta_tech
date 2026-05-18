---
type: attempt
status: failed
reason: download_timeout
date: 2026-05-15
links: "[[overview]]"
---
# A10: Qwen2-VL-2B-Instruct

**Подход**: Локальный VLM Qwen2-VL-2B через transformers
**Результат**: Скачивание 4GB модели через HuggingFace слишком медленное (>10 мин timeout)
**Qwen2-VL-0.5B**: Требует авторизацию (401 Unauthorized) — gated model
**Урок**: Нужно скачать заранее. Может работать на RTX 2060 (8GB VRAM). Кэш: 0.69GB скачано.
