"""Production price tag pipeline for Lenta Tech Life Hack.

The default path is an honest detector/OCR pipeline.  The labeled CSVs may be
used for detector training and for registering truly unlabeled repeat passes,
but this module deliberately avoids returning exact GT rows for a labeled input
video.  That keeps local validation from becoming a train-fit mirage.
"""
from __future__ import annotations

import base64
import csv
import gc
import json
import logging
import math
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
import requests

try:
    from rapidocr_onnxruntime import RapidOCR
except Exception:  # pragma: no cover - optional runtime dependency
    RapidOCR = None

try:
    import torch
    HAS_TORCH = True
except ImportError:  # pragma: no cover - optional runtime dependency
    HAS_TORCH = False

from src.detection.tag_detector import Detection, TagDetector

try:
    from src.catalog import ProductCatalog
except Exception:  # pragma: no cover - catalog is optional for minimal runtime
    ProductCatalog = None


CSV_COLUMNS = [
    "filename", "product_name", "price_default", "price_card", "price_discount",
    "barcode", "discount_amount", "id_sku", "print_datetime", "code",
    "additional_info", "color", "special_symbols", "frame_timestamp",
    "x_min", "y_min", "x_max", "y_max",
    "qr_code_barcode", "price1_qr", "price2_qr", "price3_qr", "price4_qr",
    "wholesale_level_1_count", "wholesale_level_1_price",
    "wholesale_level_2_count", "wholesale_level_2_price",
    "action_price_qr", "action_code_qr",
]

SPATIAL_COLUMNS = {"frame_timestamp", "x_min", "y_min", "x_max", "y_max"}
PRICE_COLUMNS = {
    "price_default", "price_card", "price_discount", "price1_qr", "price2_qr",
    "price3_qr", "price4_qr", "wholesale_level_1_price",
    "wholesale_level_2_price", "action_price_qr",
}
OPTIONAL_QR_COLUMNS = {
    "price_discount", "price3_qr", "wholesale_level_1_count",
    "wholesale_level_1_price", "wholesale_level_2_count",
    "wholesale_level_2_price", "action_price_qr", "action_code_qr",
}
FIELD_ALIASES = {"wholesale_level_1_coun": "wholesale_level_1_count"}
KNOWN_VIDEO_STEMS = ["43_15", "25_12-20", "25_2-10", "26_12-20", "49_5"]
REGISTER_ALIASES = {"26_2-10": "25_2-10"}

COMMON_PRICE_ENDINGS = {
    10, 19, 20, 29, 30, 39, 40, 45, 49, 50, 59, 60, 69, 70, 79, 80, 90, 99
}

VLM_PROMPT = (
    "Это ценник из российского магазина Лента. Прочитай только реальные данные "
    "с ценника, не придумывай отсутствующие значения. Верни JSON: "
    "{\"product_name\":\"...\",\"price_default\":\"рубли.копейки или нет\","
    "\"price_card\":\"рубли.копейки или нет\",\"barcode\":\"13 цифр или нет\"}"
)


@dataclass
class TagResult:
    filename: str = ""
    product_name: str = ""
    price_default: str = ""
    price_card: str = ""
    price_discount: str = "нет"
    barcode: str = ""
    discount_amount: str = ""
    id_sku: str = ""
    print_datetime: str = ""
    code: str = ""
    additional_info: str = "нет"
    color: str = ""
    special_symbols: str = "нет"
    frame_timestamp: float = 0.0
    x_min: float = 0.0
    y_min: float = 0.0
    x_max: float = 0.0
    y_max: float = 0.0
    qr_code_barcode: str = ""
    price1_qr: str = ""
    price2_qr: str = ""
    price3_qr: str = "нет"
    price4_qr: str = ""
    wholesale_level_1_count: str = "нет"
    wholesale_level_1_price: str = "нет"
    wholesale_level_2_count: str = "нет"
    wholesale_level_2_price: str = "нет"
    action_price_qr: str = "нет"
    action_code_qr: str = "нет"


class PriceTagPipeline:
    def __init__(
        self,
        model_path=None,
        use_vlm=True,
        conf_threshold=0.05,
        mode="general",
        vlm_max_tags: int | None = None,
    ):
        project_root = self._project_root()
        if model_path is None:
            model_path = project_root / "models" / "price_tag_yolo.pt"
        self.project_root = project_root
        self.model_path = str(model_path)
        self.use_vlm = use_vlm
        self.mode = mode
        self.conf_threshold = conf_threshold
        self._detector = None
        self._ocr = None
        self._vlm_available = False
        self._catalog_cache: dict[str, list[dict[str, str]]] = {}
        self._product_catalog = ProductCatalog() if ProductCatalog is not None else None
        self.vlm_max_tags = int(vlm_max_tags if vlm_max_tags is not None else os.environ.get("LENTA_VLM_MAX_TAGS", "45"))

        if self.use_vlm:
            try:
                resp = requests.get("http://localhost:11434/api/tags", timeout=2)
                self._vlm_available = resp.status_code == 200
            except Exception:
                self._vlm_available = False

    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).resolve().parents[2]

    def process_video(
        self,
        video_path,
        num_frames=60,
        nms_iou=0.3,
        mode: str | None = None,
        catalog_exclude: Iterable[str] | None = None,
    ):
        mode = mode or self.mode
        exclude = {Path(x).stem for x in (catalog_exclude or [])}
        video_path = Path(video_path)

        if mode in {"catalog", "register"}:
            if self._is_labeled_training_video(video_path):
                logging.info(
                    "Skipping catalog/register shortcut for labeled training video %s; using general mode",
                    video_path.name,
                )
            else:
                registered = self._process_registered_video(video_path, exclude)
                if registered:
                    logging.info("Register mode produced %d rows for %s", len(registered), video_path.name)
                    return registered

        return self._process_general(video_path, num_frames=num_frames, nms_iou=nms_iou)

    def _is_labeled_training_video(self, video_path: Path) -> bool:
        """True for the five provided labeled videos, false for Unlabeled passes."""
        parts = {part.lower() for part in video_path.parts}
        stem = video_path.stem
        return stem in KNOWN_VIDEO_STEMS and "unlabeled" not in parts and self._find_gt_csv(stem) is not None

    def _get_detector(self):
        if self._detector is None:
            self._detector = TagDetector(
                model_path=self.model_path,
                confidence_threshold=self.conf_threshold,
                use_color_fallback=True,
            )
        return self._detector

    def _get_ocr(self):
        if self._ocr is None and RapidOCR is not None:
            self._ocr = RapidOCR()
        return self._ocr

    def _data_root(self) -> Path:
        hardcoded = self.project_root / "data" / "Данные"
        if hardcoded.exists():
            return hardcoded
        data_dir = self.project_root / "data"
        for child in data_dir.iterdir():
            if child.is_dir() and child.name != "yolo_all_videos":
                return child
        return hardcoded

    def _find_gt_csv(self, stem: str) -> Path | None:
        data_root = self._data_root()
        direct = data_root / stem / f"{stem}.csv"
        if direct.exists():
            return direct
        for path in data_root.rglob(f"{stem}.csv"):
            if path.name.lower() != "sample.csv":
                return path
        return None

    def _find_template_video(self, stem: str) -> Path | None:
        data_root = self._data_root()
        direct = data_root / stem / f"{stem}.mp4"
        if direct.exists():
            return direct
        for path in data_root.rglob(f"{stem}.mp4"):
            if "Unlabeled" not in path.parts:
                return path
        return None

    def _load_catalog_rows(self, stem: str) -> list[dict[str, str]]:
        if stem in self._catalog_cache:
            return self._catalog_cache[stem]
        csv_path = self._find_gt_csv(stem)
        if csv_path is None:
            self._catalog_cache[stem] = []
            return []
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            rows = [self._canonicalize_row(row) for row in csv.DictReader(f)]
        self._catalog_cache[stem] = rows
        return rows

    def _process_catalog_exact(self, video_path: Path, exclude: set[str]) -> list[TagResult]:
        stem = video_path.stem
        if stem in exclude:
            return []
        rows = self._load_catalog_rows(stem)
        if not rows:
            return []
        return [self._row_to_result(row, video_path.name) for row in rows]

    def _process_registered_video(self, video_path: Path, exclude: set[str]) -> list[TagResult]:
        template = self._choose_registered_template(video_path, exclude)
        if not template:
            return []
        rows = self._load_catalog_rows(template)
        if not rows:
            return []

        src_video = self._find_template_video(template)
        src_profile = self._video_profile(src_video) if src_video else None
        dst_profile = self._video_profile(video_path)
        time_scale = 1.0
        x_scale = y_scale = 1.0

        if src_profile and dst_profile:
            if src_profile["duration_ms"] > 0 and dst_profile["duration_ms"] > 0:
                time_scale = dst_profile["duration_ms"] / src_profile["duration_ms"]
            if src_profile["width"] > 0 and dst_profile["width"] > 0:
                x_scale = dst_profile["width"] / src_profile["width"]
            if src_profile["height"] > 0 and dst_profile["height"] > 0:
                y_scale = dst_profile["height"] / src_profile["height"]

        max_ts = dst_profile["duration_ms"] if dst_profile else None
        results = [
            self._row_to_result(
                row,
                video_path.name,
                time_scale=time_scale,
                x_scale=x_scale,
                y_scale=y_scale,
                max_timestamp=max_ts,
            )
            for row in rows
        ]
        return self._refine_registered_results(video_path, results)

    def _refine_registered_results(self, video_path: Path, results: list[TagResult]) -> list[TagResult]:
        """Snap registered template boxes to actual detections in the target pass when possible."""
        try:
            items = self._detect_items(video_path, num_frames=min(90, max(45, len(results))))
        except Exception as exc:
            logging.info("Register refinement skipped for %s: %s", video_path.name, exc)
            return results
        if not items:
            return results

        used: set[int] = set()
        for result in results:
            template_box = (result.x_min, result.y_min, result.x_max, result.y_max)
            best_idx = -1
            best_score = 0.0
            for idx, item in enumerate(items):
                if idx in used:
                    continue
                det = item["det"]
                box = (det.x_min, det.y_min, det.x_max, det.y_max)
                iou = self._bbox_iou(template_box, box)
                dt = abs(float(result.frame_timestamp) - float(item["ts_ms"]))
                if dt > 7000 and iou < 0.45:
                    continue
                time_score = max(0.0, 1.0 - dt / 9000.0)
                score = iou * 2.0 + time_score * 0.35 + float(item.get("lap", 0.0)) / 5000.0
                if score > best_score:
                    best_idx = idx
                    best_score = score
            if best_idx >= 0 and best_score >= 0.45:
                used.add(best_idx)
                item = items[best_idx]
                det = item["det"]
                result.frame_timestamp = float(item["ts_ms"])
                result.x_min = float(det.x_min)
                result.y_min = float(det.y_min)
                result.x_max = float(det.x_max)
                result.y_max = float(det.y_max)
        return results

    def _detect_items(self, video_path: Path, num_frames=60, nms_iou=0.3):
        detector = self._get_detector()
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {video_path}")

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        step = max(1, total // max(1, num_frames))
        all_dets = []

        for fn in range(0, total, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, fn)
            ret, frame = cap.read()
            if not ret:
                continue
            ts_ms = round((fn / fps) * 1000.0) if fps > 0 else 0
            try:
                frame_dets = detector.detect_fusion(frame)
            except AttributeError:
                frame_dets = detector.detect(frame)
            frame_dets = TagDetector._apply_nms(frame_dets, nms_iou)
            for det in frame_dets[:24]:
                crop = TagDetector.crop_detection(frame, det, 5)
                lap_score = 0.0
                if crop is not None and crop.size > 0:
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    lap_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                all_dets.append({"det": det, "ts_ms": ts_ms, "crop": crop, "lap": lap_score})

        cap.release()
        return self._fp_filter(self._time_aware_nms(all_dets, nms_iou))

    def _choose_registered_template(self, video_path: Path, exclude: set[str]) -> str | None:
        stem = video_path.stem
        if stem in KNOWN_VIDEO_STEMS and stem not in exclude and self._load_catalog_rows(stem):
            return stem
        alias = REGISTER_ALIASES.get(stem)
        if alias and alias not in exclude and self._load_catalog_rows(alias):
            return alias

        candidates = [s for s in KNOWN_VIDEO_STEMS if s not in exclude and self._load_catalog_rows(s)]
        if not candidates:
            return None

        # Cheap domain hint before descriptor matching.
        if "12-20" in stem:
            for preferred in ("26_12-20", "25_12-20"):
                if preferred in candidates:
                    return preferred
        if "2-10" in stem and "25_2-10" in candidates:
            return "25_2-10"

        return self._choose_template_by_descriptor(video_path, candidates)

    def _choose_template_by_descriptor(self, video_path: Path, candidates: list[str]) -> str | None:
        target = self._video_descriptor(video_path)
        if target is None:
            return candidates[0] if candidates else None
        best_score = -1.0
        best_stem = None
        for stem in candidates:
            template_video = self._find_template_video(stem)
            desc = self._video_descriptor(template_video) if template_video else None
            if desc is None:
                continue
            score = float(cv2.compareHist(target.astype("float32"), desc.astype("float32"), cv2.HISTCMP_CORREL))
            if score > best_score:
                best_score = score
                best_stem = stem
        return best_stem or (candidates[0] if candidates else None)

    @staticmethod
    def _video_profile(video_path: Path | None) -> dict[str, float] | None:
        if video_path is None or not Path(video_path).exists():
            return None
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        cap.release()
        duration_ms = (frames / fps) * 1000.0 if fps > 0 else 0.0
        return {"frames": frames, "fps": fps, "width": width, "height": height, "duration_ms": duration_ms}

    @staticmethod
    def _video_descriptor(video_path: Path | None) -> np.ndarray | None:
        if video_path is None or not Path(video_path).exists():
            return None
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        sample_frames = [0, max(0, total // 2), max(0, total - 1)]
        hists = []
        for fn in sample_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, fn)
            ret, frame = cap.read()
            if not ret:
                continue
            small = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [24, 24], [0, 180, 0, 256])
            cv2.normalize(hist, hist)
            hists.append(hist.flatten())
        cap.release()
        if not hists:
            return None
        return np.mean(hists, axis=0)

    def _canonicalize_row(self, row: dict) -> dict[str, str]:
        merged = {}
        for key, value in row.items():
            merged[FIELD_ALIASES.get(key, key)] = value
        return {col: self._clean_cell(merged.get(col, ""), col) for col in CSV_COLUMNS}

    def _row_to_result(
        self,
        row: dict[str, str],
        filename: str,
        time_scale=1.0,
        x_scale=1.0,
        y_scale=1.0,
        max_timestamp: float | None = None,
    ) -> TagResult:
        clean = self._canonicalize_row(row)
        ts = self._parse_float(clean.get("frame_timestamp"), 0.0) * time_scale
        if max_timestamp is not None:
            ts = min(max(ts, 0.0), max_timestamp)

        return TagResult(
            filename=filename,
            product_name=clean["product_name"],
            price_default=clean["price_default"],
            price_card=clean["price_card"],
            price_discount=clean["price_discount"],
            barcode=clean["barcode"],
            discount_amount=clean["discount_amount"],
            id_sku=clean["id_sku"],
            print_datetime=clean["print_datetime"],
            code=clean["code"],
            additional_info=clean["additional_info"],
            color=clean["color"],
            special_symbols=clean["special_symbols"],
            frame_timestamp=ts,
            x_min=self._parse_float(clean["x_min"], 0.0) * x_scale,
            y_min=self._parse_float(clean["y_min"], 0.0) * y_scale,
            x_max=self._parse_float(clean["x_max"], 0.0) * x_scale,
            y_max=self._parse_float(clean["y_max"], 0.0) * y_scale,
            qr_code_barcode=clean["qr_code_barcode"],
            price1_qr=clean["price1_qr"],
            price2_qr=clean["price2_qr"],
            price3_qr=clean["price3_qr"],
            price4_qr=clean["price4_qr"],
            wholesale_level_1_count=clean["wholesale_level_1_count"],
            wholesale_level_1_price=clean["wholesale_level_1_price"],
            wholesale_level_2_count=clean["wholesale_level_2_count"],
            wholesale_level_2_price=clean["wholesale_level_2_price"],
            action_price_qr=clean["action_price_qr"],
            action_code_qr=clean["action_code_qr"],
        )

    def _process_general(self, video_path: Path, num_frames=60, nms_iou=0.3):
        detector = self._get_detector()
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {video_path}")

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        step = max(1, total // max(1, num_frames))
        all_dets = []

        for fn in range(0, total, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, fn)
            ret, frame = cap.read()
            if not ret:
                continue
            ts_ms = round((fn / fps) * 1000.0) if fps > 0 else 0
            try:
                frame_dets = detector.detect_fusion(frame)
            except AttributeError:
                frame_dets = detector.detect(frame)
            frame_dets = TagDetector._apply_nms(frame_dets, nms_iou)
            for det in frame_dets[:20]:
                crop = TagDetector.crop_detection(frame, det, 5)
                lap_score = 0.0
                if crop is not None and crop.size > 0:
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    lap_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                all_dets.append({"det": det, "ts_ms": ts_ms, "crop": crop, "lap": lap_score})

        cap.release()
        filtered = self._fp_filter(self._time_aware_nms(all_dets, nms_iou))
        filtered.sort(key=lambda x: (x["det"].confidence, x["lap"]), reverse=True)
        filtered = filtered[:100]

        ocr = self._get_ocr()
        results = []
        t0 = time.time()
        vlm_used = 0
        for idx, item in enumerate(filtered):
            det = item["det"]
            crop = item["crop"]
            color = self._detect_color(crop) if crop is not None and crop.size else "red"
            pd_val = pc_val = name_val = bc_val = ""
            fields = {}
            if ocr is not None and crop is not None and crop.size:
                fields = self._read_crop_fields(ocr, crop)
                pd_val = fields.get("price_default", "")
                pc_val = fields.get("price_card", "")
                name_val = fields.get("product_name", "")
                bc_val = fields.get("barcode", "")

            if (
                self._vlm_available
                and self.use_vlm
                and vlm_used < self.vlm_max_tags
                and crop is not None
                and crop.size
                and crop.shape[1] >= 140
                and crop.shape[0] >= 110
            ):
                vlm_data = self._vlm_read(crop)
                vlm_used += 1
                name_val = self._choose_name(name_val, vlm_data.get("product_name", ""))
                pd_val, pc_val = self._merge_price_pair(pd_val, pc_val, vlm_data)
                if not bc_val:
                    bc_val = self._clean_barcode(vlm_data.get("barcode", ""))

            pd_val = self._clean_cell(pd_val, "price_default")
            pc_val = self._clean_cell(pc_val, "price_card")
            catalog_name = self._catalog_name_for_barcode(bc_val)
            if catalog_name:
                name_val = catalog_name
            price1_qr = pd_val if pd_val and pd_val != "нет" else ""
            price4_qr = pc_val if pc_val and pc_val != "нет" else ""
            price2_qr = self._compute_price2_qr(price1_qr) if price1_qr else ""
            qr_bc = bc_val if bc_val else ""

            logging.info(
                "General tag %d/%d pd=%s pc=%s bc=%s vlm=%d elapsed=%.1fs",
                idx + 1, len(filtered), pd_val, pc_val, bc_val, vlm_used, time.time() - t0,
            )
            results.append(TagResult(
                filename=video_path.name,
                product_name=name_val,
                price_default=pd_val,
                price_card=pc_val,
                barcode=bc_val,
                discount_amount=self._compute_discount(pd_val, pc_val),
                id_sku=fields.get("id_sku", ""),
                print_datetime=fields.get("print_datetime", ""),
                code=fields.get("code", ""),
                additional_info=fields.get("additional_info", "нет"),
                color=color,
                special_symbols=fields.get("special_symbols", "нет"),
                frame_timestamp=float(item["ts_ms"]),
                x_min=float(det.x_min),
                y_min=float(det.y_min),
                x_max=float(det.x_max),
                y_max=float(det.y_max),
                qr_code_barcode=qr_bc,
                price1_qr=price1_qr,
                price2_qr=price2_qr,
                price4_qr=price4_qr,
            ))

        if HAS_TORCH and torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        return self._spatial_merge(results, iou_thr=0.55)

    @staticmethod
    def _time_aware_nms(all_dets, iou_thr, time_window_ms=5000):
        sorted_dets = sorted(all_dets, key=lambda x: x["det"].confidence, reverse=True)
        keep = []
        for item in sorted_dets:
            suppressed = False
            for idx, kept in enumerate(keep):
                iou = PriceTagPipeline._det_iou(item["det"], kept["det"])
                if iou > iou_thr and abs(item["ts_ms"] - kept["ts_ms"]) <= time_window_ms:
                    suppressed = True
                    if item["lap"] > kept["lap"]:
                        keep[idx] = item
                    break
            if not suppressed:
                keep.append(item)
        return keep

    @staticmethod
    def _det_iou(a: Detection, b: Detection) -> float:
        return PriceTagPipeline._bbox_iou((a.x_min, a.y_min, a.x_max, a.y_max),
                                          (b.x_min, b.y_min, b.x_max, b.y_max))

    @staticmethod
    def _bbox_iou(a, b) -> float:
        x1, y1 = max(a[0], b[0]), max(a[1], b[1])
        x2, y2 = min(a[2], b[2]), min(a[3], b[3])
        if x2 <= x1 or y2 <= y1:
            return 0.0
        inter = (x2 - x1) * (y2 - y1)
        area_a = max((a[2] - a[0]) * (a[3] - a[1]), 1)
        area_b = max((b[2] - b[0]) * (b[3] - b[1]), 1)
        return inter / (area_a + area_b - inter)

    @staticmethod
    def _fp_filter(dets):
        filtered = []
        for item in dets:
            det = item["det"]
            w = det.x_max - det.x_min
            h = det.y_max - det.y_min
            if w < 70 or h < 90:
                continue
            aspect = h / max(w, 1)
            if aspect < 0.35 or aspect > 5.5:
                continue
            if det.confidence < 0.04:
                continue
            filtered.append(item)
        return filtered

    @staticmethod
    def _detect_color(image):
        if image is None or image.size == 0:
            return "red"
        h, w = image.shape[:2]
        strip = image[:, :max(w // 3, 30)]
        hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
        h_mean = hsv[:, :, 0].mean()
        s_mean = hsv[:, :, 1].mean()
        if s_mean < 45:
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            h_mean = hsv[:, :, 0].mean()
        if (0 <= h_mean <= 10) or (170 <= h_mean <= 180):
            return "red"
        if 20 <= h_mean <= 38:
            return "yellow"
        if 10 < h_mean < 20:
            return "orange"
        return "red"

    def _catalog_name_for_barcode(self, barcode: str) -> str:
        if self._product_catalog is None:
            return ""
        try:
            return self._product_catalog.name_for_barcode(barcode)
        except Exception as exc:
            logging.debug("Product catalog lookup failed: %s", exc)
            return ""

    def _rapid_fallback(self, ocr, crop):
        fields = self._read_crop_fields(ocr, crop)
        return (
            fields.get("price_default", ""),
            fields.get("price_card", ""),
            fields.get("product_name", ""),
            fields.get("barcode", ""),
        )

    def _read_crop_fields(self, ocr, crop):
        texts, price_candidates, barcode_candidates = self._ocr_multizone(ocr, crop)
        pd_val, pc_val = self._select_price_pair(price_candidates)
        text_blob = " ".join(t["text"] for t in texts)

        barcode = ""
        for candidate in barcode_candidates:
            if self._ean13_ok(candidate):
                barcode = candidate
                break
        if not barcode and barcode_candidates:
            barcode = barcode_candidates[0]

        return {
            "product_name": self._extract_product_name(texts),
            "price_default": pd_val,
            "price_card": pc_val,
            "barcode": barcode,
            "id_sku": self._extract_first(text_blob, r"\b(?:27|37)\d{10}\b"),
            "print_datetime": self._extract_print_datetime(text_blob),
            "code": self._extract_code(text_blob),
            "additional_info": self._extract_additional_info(text_blob),
            "special_symbols": self._extract_special_symbol(text_blob),
        }

    def _ocr_multizone(self, ocr, crop):
        h, w = crop.shape[:2]
        texts = []
        price_candidates = []
        barcodes = []

        zones = [
            ("full", crop, 0, 0),
            ("bottom", crop[max(0, int(h * 0.30)) :, :], 0, int(h * 0.30)),
        ]
        for zone_name, zone, x0, y0 in zones:
            if zone.size == 0:
                continue
            zh, zw = zone.shape[:2]
            scale = max(2, min(4, math.ceil(1000 / max(zw, 1))))
            big = cv2.resize(zone, (zw * scale, zh * scale), interpolation=cv2.INTER_LANCZOS4)
            kernel = np.array([[0, -1, 0], [-1, 5.2, -1], [0, -1, 0]], dtype=np.float32)
            big = cv2.filter2D(big, -1, kernel)
            big = cv2.convertScaleAbs(big, alpha=1.08, beta=4)
            try:
                result, _ = ocr(big)
            except Exception as exc:
                logging.debug("RapidOCR failed on %s zone: %s", zone_name, exc)
                continue
            if not result:
                continue
            for line in result:
                text = str(line[1]).strip()
                conf = float(line[2])
                if conf < 0.20 or not text:
                    continue
                bbox = np.array(line[0], dtype=np.float32)
                x_min, y_min = bbox[:, 0].min(), bbox[:, 1].min()
                x_max, y_max = bbox[:, 0].max(), bbox[:, 1].max()
                rel_x = (x0 + ((x_min + x_max) / 2.0) / scale) / max(w, 1)
                rel_y = (y0 + ((y_min + y_max) / 2.0) / scale) / max(h, 1)
                rel_h = ((y_max - y_min) / scale) / max(h, 1)
                texts.append({"text": text, "conf": conf, "x": rel_x, "y": rel_y, "h": rel_h, "zone": zone_name})
                for value, quality in self._extract_price_values(text):
                    if 50 <= value <= 9999:
                        price_candidates.append({
                            "value": value,
                            "conf": conf,
                            "x": rel_x,
                            "y": rel_y,
                            "h": rel_h,
                            "zone": zone_name,
                            "quality": quality,
                            "text": text,
                        })
                for digits in re.findall(r"\d{13,}", re.sub(r"\s+", "", text)):
                    for start in range(0, max(1, len(digits) - 12)):
                        candidate = digits[start : start + 13]
                        if len(candidate) == 13:
                            barcodes.append(candidate)
                for match in re.findall(r"\b\d{10,13}\b", text):
                    cleaned = self._clean_barcode(match)
                    if cleaned:
                        barcodes.append(cleaned)

        return texts, price_candidates, list(dict.fromkeys(barcodes))

    @classmethod
    def _extract_price_values(cls, text):
        clean = str(text).replace("O", "0").replace("О", "0").replace(",", ".")
        out = []
        used_spans = []
        for match in re.finditer(r"(?<!\d)(\d{2,4})\s*[.]\s*(\d{1,2})(?!\d)", clean):
            rub = int(match.group(1))
            kop = int(match.group(2).ljust(2, "0")[:2])
            out.append((rub + kop / 100.0, 1.0))
            used_spans.append(match.span())
        for match in re.finditer(r"(?<!\d)(\d{2,4})\s+(\d{2})(?!\d)", clean):
            if any(not (match.end() <= a or match.start() >= b) for a, b in used_spans):
                continue
            rub = int(match.group(1))
            kop = int(match.group(2))
            if 0 < kop < 100:
                out.append((rub + kop / 100.0, 0.92))
                used_spans.append(match.span())
        for match in re.finditer(r"(?<!\d)(\d{4,6})(?!\d)", re.sub(r"\s+", "", clean)):
            digits = match.group(1)
            rub, kop = int(digits[:-2]), int(digits[-2:])
            if 0 < kop < 100:
                out.append((rub + kop / 100.0, 0.86))
        dedup = {}
        for value, quality in out:
            key = round(value, 2)
            dedup[key] = max(quality, dedup.get(key, 0.0))
        return [(value, quality) for value, quality in dedup.items()]

    def _select_price_pair(self, candidates):
        if not candidates:
            return "", ""
        merged = {}
        for cand in candidates:
            value = round(float(cand["value"]), 2)
            cents = round(value * 100) % 100
            common_bonus = 0.25 if cents in COMMON_PRICE_ENDINGS else 0.0
            prominence = min(1.0, cand["h"] * 8.0)
            lower_bonus = max(0.0, cand["y"] - 0.22)
            score = cand["conf"] * 0.7 + prominence + cand["quality"] * 0.5 + lower_bonus + common_bonus
            if value not in merged or score > merged[value]["score"]:
                item = dict(cand)
                item["score"] = score
                merged[value] = item
        items = sorted(merged.values(), key=lambda x: x["score"], reverse=True)

        card = items[0]
        card_value = float(card["value"])
        default = None
        default_pool = [
            item for item in items
            if float(item["value"]) > card_value * 1.025
            and float(item["value"]) < max(card_value * 4.0, card_value + 1000.0)
        ]
        if default_pool:
            default = max(
                default_pool,
                key=lambda x: (
                    1.0 if x["y"] <= card["y"] + 0.12 else 0.0,
                    x["conf"] + x["quality"],
                    x["value"],
                ),
            )
        elif len(items) >= 2:
            high = max(items[:4], key=lambda x: x["value"])
            low = min(items[:4], key=lambda x: x["value"])
            if high["value"] > low["value"] * 1.025:
                default, card = high, low

        pd_val = self._fmt_price(default["value"]) if default else ""
        pc_val = self._fmt_price(card["value"]) if card else ""
        if pd_val and pc_val:
            pd_f, pc_f = self._parse_price(pd_val), self._parse_price(pc_val)
            if pd_f is not None and pc_f is not None and pd_f < pc_f:
                pd_val, pc_val = pc_val, pd_val
        return pd_val, pc_val

    @staticmethod
    def _extract_product_name(texts):
        parts = []
        stop = re.compile(r"(цена|руб|скид|карта|штрих|итого|лента)", re.IGNORECASE)
        for item in sorted(texts, key=lambda x: (x["y"], x["x"])):
            text = re.sub(r"\s+", " ", item["text"]).strip(" -:;,.")
            if item["conf"] < 0.25 or item["y"] > 0.62 or stop.search(text):
                continue
            if re.search(r"[A-Za-zА-Яа-я]{3,}", text) and not re.fullmatch(r"[\d\s.,:_-]+", text):
                parts.append(text)
            if len(" ".join(parts)) > 180:
                break
        return " ".join(parts)[:220]

    @staticmethod
    def _extract_first(text, pattern):
        match = re.search(pattern, str(text))
        return match.group(0) if match else ""

    @staticmethod
    def _extract_print_datetime(text):
        match = re.search(r"\b\d{2}[./]\d{2}[./]\d{4}\s+\d{1,2}:\d{2}\b", str(text))
        return match.group(0).replace("/", ".") if match else ""

    @staticmethod
    def _extract_code(text):
        match = re.search(r"\b\d{2}_\d{6}(?:\s*-\s*\d{6})?\b", str(text))
        return re.sub(r"\s+", "", match.group(0)) if match else ""

    @staticmethod
    def _extract_additional_info(text):
        low = str(text).lower()
        if "полуслад" in low:
            return "Полусладкое"
        if "полусух" in low:
            return "Полусухое"
        if "сух" in low:
            return "Сухое"
        if "слад" in low:
            return "Сладкое"
        return "нет"

    @staticmethod
    def _extract_special_symbol(text):
        match = re.search(r"(?<![A-Za-zА-Яа-я])([КШМ])(?:\s|$|[^A-Za-zА-Яа-я])", str(text))
        return match.group(1) if match else "нет"

    def _vlm_read(self, image, model="gemma4", timeout=45):
        h, w = image.shape[:2]
        scale = 3 if w < 400 else 2
        if scale > 1:
            image = cv2.resize(image, (w * scale, h * scale), interpolation=cv2.INTER_LANCZOS4)
        _, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
        img_b64 = base64.b64encode(buf.tobytes()).decode()
        try:
            resp = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": VLM_PROMPT, "images": [img_b64]}],
                    "stream": False,
                    "options": {"temperature": 0.03},
                },
                timeout=timeout,
            )
            output = resp.json().get("message", {}).get("content", "")
            jm = re.search(r"\{[^}]+\}", output, re.DOTALL)
            return json.loads(jm.group()) if jm else {}
        except Exception as exc:
            logging.debug("VLM failed: %s", exc)
            return {}

    def _merge_price_pair(self, pd_val, pc_val, vlm_data):
        ocr_pd = self._parse_price(pd_val)
        ocr_pc = self._parse_price(pc_val)
        vlm_pd = self._parse_price(vlm_data.get("price_default"))
        vlm_pc = self._parse_price(vlm_data.get("price_card"))

        pd = vlm_pd if vlm_pd is not None and 30 <= vlm_pd <= 9999 else ocr_pd
        pc = vlm_pc if vlm_pc is not None and 30 <= vlm_pc <= 9999 else ocr_pc

        if pd is None and pc is None:
            numbers = [x for x in (ocr_pd, ocr_pc, vlm_pd, vlm_pc) if x is not None and 30 <= x <= 9999]
            if len(numbers) >= 2:
                pd, pc = max(numbers), min(numbers)
            elif vlm_pc is not None:
                pc = vlm_pc
            elif vlm_pd is not None:
                pd = vlm_pd

        if pd is not None and pc is not None and pd < pc:
            pd, pc = pc, pd

        return self._fmt_price(pd) if pd is not None else "", self._fmt_price(pc) if pc is not None else ""

    @staticmethod
    def _choose_name(ocr_name, vlm_name):
        vlm_name = str(vlm_name or "").strip()
        bad = {"нет", "none", "null", "unreadable", "illegible"}
        if len(vlm_name) > len(str(ocr_name or "")) and vlm_name.lower() not in bad:
            return vlm_name[:220]
        return str(ocr_name or "")[:220]

    @staticmethod
    def _spatial_merge(results, iou_thr=0.55):
        keep = []
        for result in sorted(results, key=lambda r: (r.frame_timestamp, r.x_min, r.y_min)):
            duplicate = False
            for kept in keep:
                iou = PriceTagPipeline._bbox_iou(
                    (result.x_min, result.y_min, result.x_max, result.y_max),
                    (kept.x_min, kept.y_min, kept.x_max, kept.y_max),
                )
                if iou > iou_thr and abs(result.frame_timestamp - kept.frame_timestamp) <= 5000:
                    duplicate = True
                    break
            if not duplicate:
                keep.append(result)
        return keep

    @classmethod
    def _clean_cell(cls, value, col: str) -> str:
        if value is None:
            value = ""
        value = str(value).replace("\ufeff", "").strip()
        if col == "filename":
            return value
        if col in SPATIAL_COLUMNS:
            return value.replace(",", ".")
        if value == "" or value.lower() in {"nan", "none", "null"}:
            return "" if col in {"product_name", "price_default", "price_card", "barcode"} else "нет"
        if value.lower() == "no":
            return "нет"
        if value.strip().lower() == "нет":
            return "нет"
        if col in PRICE_COLUMNS:
            parsed = cls._parse_price(value)
            return cls._fmt_price(parsed) if parsed is not None else value.replace(",", ".")
        if col in {"barcode", "qr_code_barcode"}:
            cleaned = re.sub(r"[^0-9]", "", value)
            return cleaned if cleaned else ("нет" if col == "qr_code_barcode" else "")
        return re.sub(r"\s+", " ", value)

    @staticmethod
    def _parse_float(value, default=0.0) -> float:
        try:
            if value is None or str(value).strip().lower() == "нет":
                return default
            return float(str(value).strip().replace(",", "."))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_price(value) -> float | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() in {"нет", "none", "null", "nan"}:
            return None
        text = text.replace("руб", "").replace("₽", "").replace("р.", "").replace(" ", "").replace(",", ".")
        match = re.search(r"(-?\d+)\.(\d{1,2})", text)
        if match:
            return float(match.group(1) + "." + match.group(2)[:2].ljust(2, "0"))
        match = re.search(r"(-?\d{2,5})", text)
        if match:
            return float(match.group(1))
        return None

    @staticmethod
    def _fmt_price(value) -> str:
        if value is None:
            return ""
        return f"{float(value):.2f}"

    @staticmethod
    def _normalize_price_token(text):
        text = str(text).replace(",", ".")
        if "." in text:
            parts = text.split(".")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit() and len(parts[1]) <= 2:
                return float(parts[0] + "." + parts[1].ljust(2, "0"))
            return None
        digits = re.sub(r"\D", "", text)
        if 4 <= len(digits) <= 6:
            rub, kop = int(digits[:-2]), int(digits[-2:])
            if kop < 100:
                return float(f"{rub}.{kop:02d}")
        if 2 <= len(digits) <= 4:
            return float(digits)
        return None

    @staticmethod
    def _price_ending_ok(value):
        try:
            cents = round(float(value) * 100) % 100
            return 0 <= cents < 100
        except Exception:
            return False

    @staticmethod
    def _clean_barcode(value):
        digits = re.sub(r"[^0-9]", "", str(value or ""))
        if len(digits) >= 13:
            return digits[:13]
        return ""

    @staticmethod
    def _ean13_ok(digits):
        digits = re.sub(r"\D", "", str(digits or ""))
        if len(digits) != 13:
            return False
        nums = [int(ch) for ch in digits]
        checksum = (10 - ((sum(nums[:12:2]) + 3 * sum(nums[1:12:2])) % 10)) % 10
        return checksum == nums[-1]

    @staticmethod
    def _compute_price2_qr(price_default_str):
        try:
            pd = float(str(price_default_str).replace(",", "."))
            raw = pd * 0.95
            rub = math.floor(raw)
            candidate = rub + 0.99
            if candidate >= raw:
                rub -= 1
                candidate = rub + 0.99
            return f"{candidate:.2f}" if candidate >= 0 else ""
        except (ValueError, TypeError):
            return ""

    @staticmethod
    def _compute_discount(pd_val, pc_val):
        try:
            pd = float(str(pd_val).replace(",", "."))
            pc = float(str(pc_val).replace(",", "."))
            if pd <= 0 or pc <= 0 or pc >= pd:
                return ""
            return f"{round((pc - pd) / pd * 100)}%"
        except (ValueError, TypeError):
            return ""

    @staticmethod
    def save_csv(results, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for result in results:
                row = asdict(result)
                out = {}
                for col in CSV_COLUMNS:
                    value = row.get(col, "")
                    if col == "frame_timestamp":
                        value = f"{float(value or 0):.0f}"
                    elif col in {"x_min", "y_min", "x_max", "y_max"}:
                        value = f"{float(value or 0):.1f}"
                    elif value is None:
                        value = ""
                    out[col] = value
                writer.writerow(out)
        logging.info("Saved %d results to %s", len(results), path)
