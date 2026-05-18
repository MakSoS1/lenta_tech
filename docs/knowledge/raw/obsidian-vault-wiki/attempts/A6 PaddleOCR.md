---
type: attempt
status: failed
reason: windows_crash
date: 2026-05-15
links: "[[overview]]"
---
# A6: PaddleOCR

**Подход**: PaddleOCR v5 (server+mobile)
**Результат**: Crash на Windows — `(Unimplemented) ConvertPirAttribute2RuntimeAttribute` (OneDNN bug)
**Альтернатива**: PaddleOCR v4 тоже не ставится (paddlepaddle==2.6.1 нет для Python 3.11)
**Урок**: PaddleOCR нативно не работает на Windows + Python 3.11
