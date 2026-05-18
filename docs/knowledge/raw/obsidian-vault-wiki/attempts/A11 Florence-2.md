---
type: attempt
status: failed
reason: transformers_bug
date: 2026-05-15
links: "[[overview]]"
---
# A11: Florence-2-base

**Подход**: Microsoft Florence-2 через transformers
**Результат**: Загружается (0.9GB VRAM), но generate() падает с:
1. `past_key_values[0][0].shape[2]` — NoneType (патчили)
2. `torch.cat([past_key_value[0], key_states])` — NoneType в tensor
**Проблема**: Несовместимость Florence-2 с новыми transformers
**Урок**: Florence-2 слишком баганный на текущей версии transformers
