---
type: component
---
# Ollama VLM

Локальные VLM через Ollama API (localhost:11434)
- Gemma4:latest — 9.6GB, **ONLY model used for prices** (reads correct kopecks)
- Gemma3:4b — 3.3GB, **REJECTED** (hallucinates .90 kopecks: 349.90, 149.90 etc.)
- Скорость: ~30s/tag (GPU)
- Temperature: 0.05 (temp=0 gives garbage Latin output)

**What works**: Reads card prices correctly (.99, .69, .29 etc)
**What fails**: 
- price_default (small crossed-out price invisible)
- Names partially readable (garbled Cyrillic)
- Barcodes hallucinated
- Reads prices from adjacent tags (bbox overlap)

**Price filters** (see [[A22 Price Filters]]):
- Reject prices < 50 rubles (hallucinated garbage)
- Reject unusual cent endings (only .00, .10, .19, .20, .29, .30, .39, .40, .45, .49, .50, .59, .60, .69, .70, .79, .80, .90, .99)
- Reject when smaller price < 40% of larger (catches 66.00, 50.00 hallucinations)
- Swap if price_default < price_card

**Связи**: [[A8 Ollama VLM]] → [[A15 Tiered VLM Results]] → [[A17 VLM price mapping]] → [[A22 Price Filters]]
