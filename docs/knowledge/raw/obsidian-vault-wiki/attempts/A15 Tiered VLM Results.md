---
type: attempt
status: completed
date: 2026-05-16
links: "[[Night Run Plan]] [[A15 Tiered VLM]]"
---
# A15 Results: Tiered VLM

**Setup**: gemma4 for tags ≥250px, gemma3:4b for tags ≥130px
**Result**: 
- price_default: 3.8%, price_card: 7.7%, product_name: 20.8%
- Detection: 26/29, Mean IoU: 0.446

**Key Finding**: gemma3:4b HALLUCINATES .90 kopecks (349.90, 149.90, 249.90, 169.90, 139.90, 129.90)
- These are NOT real prices — GT has .99, .42, .29, .69, .26, .89 etc
- gemma4 reads correct kopecks (319.99, 305.99, 469.99, 259.99, 679.99, 377.99, 244.99, 178.99, 347.30)
- But gemma4 is slow (~30-45s per tag)

**Decision**: 
- Use ONLY gemma4 for VLM (not gemma3:4b)
- Accept slower speed for accuracy
- Reduce VLM calls by using larger threshold (≥180px) 
- Skip tiny tags (<130px) entirely — RapidOCR can't read them anyway
- Focus on getting correct prices for the tags we CAN read

**Next**: Test multi-frame consensus to reduce hallucination on gemma4
