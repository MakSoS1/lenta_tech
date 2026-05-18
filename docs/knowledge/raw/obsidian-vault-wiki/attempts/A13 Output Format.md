---
type: attempt
status: completed
date: 2026-05-16
links: "[[Night Run Plan]] [[overview]]"
---
# A13: Output Format Fix

**Problem**: Output CSV doesn't match sample.csv format
**Findings**:
- sample.csv uses POINT decimals: 3789.49, 2011.9
- Our output uses COMMA: 305,00, 1092
- GT CSVs use comma but sample (expected output) uses point
- All 28 fields must be present, even if "нет"
- Bounding boxes are FLOAT not INT
- price_discount field exists but we always set "нет"

**Fix**: 
- Change format_price to use point instead of comma
- Change bbox output to float with 1 decimal
- Match sample.csv exactly
