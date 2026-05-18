---
type: attempt
status: partial_success
date: 2026-05-16
links: "[[A16 Multi-frame VLM]] [[Night Run Plan]] [[A20 Final Pipeline]]"
---
# A17: VLM price mapping fix

**Hypothesis**: VLM reads prominent number as price_default, but it's actually price_card. Fix mapping: VLM→price_card, use OCR for price_default.
**Result**: price_card 46.2% (up from 0%), price_default stuck at 3.8%

**Key findings**:
- VLM `price_default` field → actually reads card price (prominent large number)
- When VLM reads both prices: max=price_default, min=price_card (correct!)
- Single price from VLM → assign to price_card (most common case)
- price_default hard because: VLM can't see small crossed-out price, OCR too noisy
- Top-crop VLM for price_default: FAILED (wrong numbers, 600s extra)

**CRASH**: Running 26_12-20 video caused PC reboot — VLM + YOLO overloaded 8GB VRAM
- Must: clear VRAM between VLM calls, reduce VLM to only large tags, add gc.collect()
- Wine video (26_12-20) has larger tags (400x500px) → more VRAM for VLM upscale

**Best v12 result on 43_15**:
- Detection: 26/29 (90%)
- price_card: 46.2% ✓✓
- price_default: 3.8%
- product_name: 27.1%
- color: 82.1%
- Key fields: 0.309
