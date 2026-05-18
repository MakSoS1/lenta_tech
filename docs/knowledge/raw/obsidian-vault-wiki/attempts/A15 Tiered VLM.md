---
type: attempt
status: completed
date: 2026-05-16
links: "[[Night Run Plan]] [[A14 Sub-crop VLM]] [[A15 Tiered VLM Results]]"
---
# A15: Tiered VLM Strategy

**Problem**: v9 gave 8% price_default, 12% price_card at ±0.5 threshold
**Root causes**:
1. VLM reads price_card as price_default (confuses which is which)
2. VLM reads prices from adjacent tags (bbox overlap)
3. Small tags (<180px) get no VLM, RapidOCR fails → "нет"
4. price_card often correct but assigned to wrong field

**New Strategy**:
1. Lower VLM threshold to 130px (use gemma3:4b for speed)
2. Use gemma4 only for large tags (>=250px) where it's most accurate
3. Better prompt: explicitly describe upper price = default, lower = card
4. After VLM, validate: if pd < pc, swap them
5. For small tags, try multi-frame RapidOCR consensus
6. Increase num_frames back to 40 for better detection
