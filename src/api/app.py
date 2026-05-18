from __future__ import annotations

import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

import gradio as gr
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

OUTPUTS_DIR = Path(os.environ.get("LENTA_OUTPUTS_DIR", "outputs"))
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def _get_pipeline() -> Any:
    from src.pipeline.price_tag_pipeline import PriceTagPipeline
    use_vlm = os.environ.get("LENTA_API_USE_VLM", "0") == "1"
    vlm_max_tags = int(os.environ.get("LENTA_API_VLM_MAX_TAGS", "0"))
    return PriceTagPipeline(mode="general", use_vlm=use_vlm, vlm_max_tags=vlm_max_tags)


def _process_video_file(video_path: str, num_frames: int = 60) -> dict[str, Any]:
    from src.pipeline.price_tag_pipeline import PriceTagPipeline
    from dataclasses import asdict

    use_vlm = os.environ.get("LENTA_API_USE_VLM", "0") == "1"
    vlm_max_tags = int(os.environ.get("LENTA_API_VLM_MAX_TAGS", "0"))
    pipeline = PriceTagPipeline(mode="general", use_vlm=use_vlm, vlm_max_tags=vlm_max_tags)
    results = pipeline.process_video(video_path, num_frames=num_frames)
    csv_path = OUTPUTS_DIR / f"result_{uuid.uuid4().hex[:8]}.csv"
    pipeline.save_csv(results, str(csv_path))
    return {
        "results": [asdict(r) for r in results],
        "csv_path": str(csv_path),
        "count": len(results),
    }


def _draw_bboxes_on_frame(video_path: str, results: list[dict[str, Any]]) -> list[str]:
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error("Cannot open video: %s", video_path)
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    preview_dir = OUTPUTS_DIR / f"preview_{uuid.uuid4().hex[:8]}"
    preview_dir.mkdir(parents=True, exist_ok=True)

    image_paths: list[str] = []
    for i, item in enumerate(results):
        frame_idx = int(float(item.get("frame_timestamp", 0)) / 1000.0 * fps)
        if frame_idx <= 0:
            frame_idx = i * max(1, total_frames // max(len(results), 1))

        cap.set(cv2.CAP_PROP_POS_FRAMES, min(frame_idx, total_frames - 1))
        ret, frame = cap.read()
        if not ret:
            continue

        x_min = int(float(item.get('x_min', 0) or 0))
        y_min = int(float(item.get('y_min', 0) or 0))
        x_max = int(float(item.get('x_max', 0) or 0))
        y_max = int(float(item.get('y_max', 0) or 0))

        h, w = frame.shape[:2]
        x_min = max(0, min(x_min, w))
        y_min = max(0, min(y_min, h))
        x_max = max(0, min(x_max, w))
        y_max = max(0, min(y_max, h))

        cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 0, 255), 2)

        label_parts: list[str] = []
        product_name = str(item.get('product_name', ''))
        if product_name and product_name != 'нет':
            label_parts.append(product_name[:40])
        pd_val = str(item.get('price_default', ''))
        pc = str(item.get('price_card', ''))
        if pd_val and pd_val != 'нет':
            label_parts.append(f"pd={pd_val}")
        if pc and pc != 'нет':
            label_parts.append(f"pc={pc}")
        label = " | ".join(label_parts) if label_parts else "price_tag"

        font_scale = 0.5
        thickness = 1
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        cv2.rectangle(frame, (x_min, y_min - th - 6), (x_min + tw, y_min), (0, 0, 255), -1)
        cv2.putText(
            frame, label, (x_min, y_min - 4), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness
        )

        out_path = str(preview_dir / f"tag_{i:04d}.jpg")
        cv2.imwrite(out_path, frame)
        image_paths.append(out_path)

    cap.release()
    return image_paths


def _gradio_process(
    video_file: str | None,
    num_frames: int,
    progress: gr.Progress = gr.Progress(),
) -> tuple[list[str] | None, str | None, pd.DataFrame | None, str]:
    if video_file is None:
        return None, None, None, "No video uploaded"

    progress(0.1, desc="Initializing pipeline...")
    try:
        result = _process_video_file(video_file, num_frames=num_frames)
    except Exception as exc:
        logger.exception("Pipeline failed")
        return None, None, None, f"Error: {exc}"

    progress(0.6, desc="Generating previews...")
    results = result["results"]
    csv_path = result["csv_path"]

    try:
        preview_paths = _draw_bboxes_on_frame(video_file, results)
    except Exception as exc:
        logger.exception("Preview generation failed")
        preview_paths = []

    progress(0.85, desc="Building summary table...")

    summary_rows: list[dict[str, str]] = []
    for r in results:
        pn = str(r.get("product_name", ""))
        pd_val = str(r.get("price_default", ""))
        pc = str(r.get("price_card", ""))
        bc = str(r.get("barcode", ""))
        summary_rows.append(
            {
                "Product": pn[:60],
                "Price Default": pd_val,
                "Price Card": pc,
                "Barcode": bc,
            }
        )

    summary_df = pd.DataFrame(summary_rows) if summary_rows else pd.DataFrame()
    summary_str = f"Detected {result['count']} price tags"

    progress(1.0, desc="Done!")

    return preview_paths, csv_path, summary_df, summary_str


def _build_gradio_interface() -> gr.Blocks:
    with gr.Blocks(title="Lenta Price Tag Detector") as demo:
        gr.Markdown("# Lenta Tech Life Hack — Price Tag Detector")
        gr.Markdown("Upload a video of store shelves to detect and extract price tag data.")

        with gr.Row():
            with gr.Column(scale=1):
                video_input = gr.Video(label="Upload Video (.mp4)", sources=["upload"])
                num_frames_slider = gr.Slider(
                    minimum=10, maximum=100, value=60, step=5, label="Number of Frames to Extract"
                )
                process_btn = gr.Button("Process", variant="primary")
                status_text = gr.Textbox(label="Status", interactive=False)

            with gr.Column(scale=2):
                gallery = gr.Gallery(
                    label="Detected Price Tags", columns=3, height=400, object_fit="contain"
                )
                csv_download = gr.File(label="Download CSV Results")
                summary_table = gr.Dataframe(
                    label="Summary of Detected Items",
                    headers=["Product", "Price Default", "Price Card", "Barcode"],
                )

        process_btn.click(
            fn=_gradio_process,
            inputs=[video_input, num_frames_slider],
            outputs=[gallery, csv_download, summary_table, status_text],
        )

    return demo


def create_app() -> FastAPI:
    app = FastAPI(title="Lenta Price Tag Detector API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if OUTPUTS_DIR.exists():
        app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")

    @app.get("/api/health")
    async def health_check() -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content={"status": "healthy", "service": "lenta-price-tag-detector", "version": "1.0.0"},
        )

    @app.post("/api/process")
    async def process_video(file: UploadFile = File(...)) -> JSONResponse:
        if not file.filename or not file.filename.lower().endswith(".mp4"):
            raise HTTPException(status_code=400, detail="Only .mp4 video files are accepted")

        tmp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmp_dir, file.filename)
        try:
            with open(tmp_path, "wb") as f:
                shutil.copyfileobj(file.file, f)

            result = _process_video_file(tmp_path)
            results = result["results"]

            response_data: dict[str, Any] = {
                "count": result["count"],
                "csv_path": result["csv_path"],
                "items": results[:500],
            }
            return JSONResponse(status_code=200, content=response_data)
        except Exception as exc:
            logger.exception("Processing failed")
            raise HTTPException(status_code=500, detail=str(exc))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @app.get("/api/download/{csv_filename}")
    async def download_csv(csv_filename: str) -> FileResponse:
        csv_path = OUTPUTS_DIR / csv_filename
        if not csv_path.exists():
            raise HTTPException(status_code=404, detail="CSV file not found")
        return FileResponse(path=str(csv_path), media_type="text/csv", filename=csv_filename)

    gradio_app = _build_gradio_interface()
    app = gr.mount_gradio_app(app, gradio_app, path="/")

    return app
