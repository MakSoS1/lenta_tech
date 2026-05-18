---
type: attempt
status: failed
date: 2026-05-16
links: "[[Night Run Plan]] [[A15 Tiered VLM Results]]"
---
# A16: Multi-frame VLM consensus

**Hypothesis**: Read same tag from 2 frames, take consensus
**Result**: FAILED - too slow (1800s for 37/68 tags, would take 60+ min total)
**Insight**: Multi-frame VLM doubles time with minimal accuracy gain

**Alternative approach**: 
1. Use SINGLE VLM call per tag (gemma4, ≥180px)
2. Use RapidOCR as cross-validation: if RapidOCR reads integer part matching VLM, trust VLM
3. If VLM reads price far from RapidOCR, likely hallucinating adjacent tag
4. Focus on getting the INTEGER part right — kopecks less important for ±0.5 threshold
