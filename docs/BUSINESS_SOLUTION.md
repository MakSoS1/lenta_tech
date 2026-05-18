# Business solution

## Problem

In a large retail network, shelf price tags are operational data. If a printed tag is outdated, unreadable, misplaced, or inconsistent with the promo system, the store gets customer friction, manual rechecks, and price integrity risk.

The hackathon video setup is exactly the kind of workflow that can scale: a robot already moves along shelves, so each pass can become a structured audit event.

## Proposed product

**Lenta Vision Tags** converts robot shelf video into a CSV audit layer:

- detects unique price tags;
- extracts prices, product text, barcode-like identifiers, promo fields, color and timestamp;
- enriches results through a local product catalog;
- produces output in the task schema;
- supports repeat-pass registration for similar shelves.

## Why local-first matters

The task explicitly limits non-reproducible cloud usage. For retail, that is also the right architecture:

- shelf video can contain operationally sensitive assortment data;
- inference must work in stores with unstable connectivity;
- model behavior must be reproducible for audit;
- latency and cost should not scale with cloud VLM calls.

## Operating model

1. Robot records shelf video.
2. Store workstation or edge box runs CLI/API inference.
3. CSV is uploaded into a price integrity workflow.
4. Exceptions are routed to staff: missing tag, price mismatch, outdated print date, wrong promo.
5. Repeat passes use registration to stabilize SKU-level tracking over time.

## What makes the solution practical

- **Time-aware NMS** respects robot movement. Same pixel area at different times can be a different tag.
- **Catalog enrichment** turns partial visual recognition into retail-grade data when barcode is available.
- **Camera undistortion module** makes the system ready for calibrated deployment and retraining.
- **Honest validation** separates public-fit experiments from a production fallback.

## Known limitations and product path

Video quality makes QR/barcode and small crossed-out prices difficult. The product path is not to pretend OCR is perfect, but to combine:

- better capture settings and calibrated undistortion;
- stronger detector training on more stores;
- local barcode/QR super-resolution experiments;
- repeat-pass registration;
- store master-data integration.

That is how the hackathon prototype becomes a maintainable retail process.
