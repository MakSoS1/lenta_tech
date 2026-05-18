---
type: attempt
status: failed
date: 2026-05-16
links: "[[Night Run Plan]] [[A12 Price Logic Fix]]"
---
# A14: Sub-crop VLM (Price + Name separate calls)

**Hypothesis**: Sub-crop lower 60% for price, upper 45% for name → less adjacent tag bleed
**Result**: FAILED
- Price sub-crop too small → VLM reads random numbers (15.00, 30.00, 19.00, 14.00)
- Two VLM calls per tag = 2x slower (90s/tag)
- 68 tags × 90s = way too slow
- Sub-crops lose context needed for VLM

**Key Insight**: VLM needs the FULL tag to understand context. The problem isn't the crop, it's that YOLO bbox includes adjacent tags. Need BETTER bboxes, not sub-crops.

**Decision**: 
1. Use SINGLE gemma4 call per tag (full crop) 
2. Only for tags >= 180px wide (larger = more accurate)
3. Skip VLM for small tags, use RapidOCR fallback
4. This reduces VLM calls from 68 to ~25, cutting time from 90min to ~15min
