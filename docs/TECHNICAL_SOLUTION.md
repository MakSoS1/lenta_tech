# Technical solution

## Components

- `PriceTagPipeline` is the main orchestration class.
- `TagDetector` wraps YOLOv8 inference and HSV fallback.
- `ProductCatalog` loads the normalized local product catalog and maps barcode to product name.
- `DistortionCorrector` implements camera undistortion from the provided coefficients.
- `run_pipeline.py` is the reproducible CLI entrypoint.
- `src/api/app.py` exposes FastAPI and Gradio.

## Recognition strategy

The pipeline is intentionally conservative:

- empty fields stay empty when data is not visible;
- absent QR wholesale/promo fields are written as `нет`;
- integer-only OCR tokens are not accepted as prices;
- VLM is capped with `--vlm-max-tags` because local Gemma4 is slow;
- catalog values are used only when a barcode-like key is found.

## Camera undistortion

The provided camera data is implemented in `src/preprocessing/camera_undistort.py`:

```python
from src.preprocessing import DistortionCorrector

corrector = DistortionCorrector(crop_roi=False)
frame = corrector.undistort_frame(frame)
```

It is optional by default because cropping undistorted frames changes coordinate space. For production, either keep `crop_roi=False` or remap predicted boxes back to the original frame before writing CSV.

## Product catalog

The original `db_hack.csv` is CP1251 and semicolon-delimited, with product names that may contain commas. It is normalized into:

```text
data/catalog/products.csv
fullname,barcode
...
```

Rows: `355835`.

## Validation stance

The repository deliberately blocks exact GT-copy behavior on the five labeled videos. This avoids the false `1.0` metric that can happen when the prediction CSV is generated from ground-truth rows.

The honest general fallback remains weak on full official metric because QR/barcode/product fields are not reliably visible in the video. The release therefore includes:

- honest fallback metrics;
- final repeat-pass CSVs for unlabeled videos;
- a registration mode for the business scenario where a robot revisits known shelves.
