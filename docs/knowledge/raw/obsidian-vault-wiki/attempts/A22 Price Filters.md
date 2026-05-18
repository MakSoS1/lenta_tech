---
type: attempt
status: completed
date: 2026-05-16
links: "[[A17 VLM price mapping]] [[A20 Final Pipeline]] [[Ollama VLM]]"
---
# A22: Price Filters (Anti-Hallucination)

**Проблема**: VLM галлюцинирует цены — 66.00, 50.00, 230.50, 14.00, 21.00

**Три уровня фильтрации**:

### 1. Minimum price threshold (из v12)
- Reject prices < 50 рублей
- Убирает мелкие галлюцинации (14.00, 21.00, 16.00)

### 2. Price ending filter (NEW)
- Valid cent endings: .00, .10, .19, .20, .29, .30, .39, .40, .45, .49, .50, .59, .60, .69, .70, .79, .80, .90, .99
- Based on GT data: real Russian retail prices end in these patterns
- Rejects: .05, .15, .25, .35, .55, .65, .75, .85, .95 (unlikely)
- Also applied to OCR numbers

### 3. Price ratio check (NEW)
- When VLM reads two prices: if min < 40% of max → reject the min as hallucination
- Catches: GT pd=259.99, VLM reads pc=66.00 (66/260 = 25%, rejected)
- Catches: GT pd=305.00, VLM reads pc=50.00 (50/305 = 16%, rejected)

**Impact on 43_15**:
- Before: pc=66.00, pc=50.00, pd=230.50 appeared
- After: these filtered out, assigned "нет" instead
- Side effect: fewer price_card matches (some valid low prices filtered)
- price_card: 46.2% → 25.0% (but remaining values are more reliable)

**Code**: `_price_ending_ok()` + ratio check in `PriceTagPipeline.process_video()`
