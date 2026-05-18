"""YOLOv8-based and color-based price tag detector."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    confidence: float
    class_id: int = 0
    class_name: str = "price_tag"


class TagDetector:
    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        use_color_fallback: bool = True,
    ) -> None:
        self._confidence_threshold = confidence_threshold
        self._iou_threshold = iou_threshold
        self._use_color_fallback = use_color_fallback
        self._yolo_model = None
        self._model_loaded = False

        if model_path and Path(model_path).exists():
            self._load_yolo_model(model_path)
        elif model_path:
            logger.warning("Model path %s does not exist, will use color fallback", model_path)

    def _load_yolo_model(self, model_path: str) -> None:
        try:
            from ultralytics import YOLO

            self._yolo_model = YOLO(model_path)
            self._model_loaded = True
            logger.info("YOLO model loaded from %s", model_path)
        except ImportError:
            logger.warning("ultralytics not installed, YOLO detection unavailable")
        except Exception as e:
            logger.warning("Failed to load YOLO model: %s", e)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        if self._model_loaded and self._yolo_model is not None:
            try:
                yolo_dets = self._detect_yolo(frame)
                if yolo_dets:
                    return yolo_dets
            except Exception as e:
                logger.warning("YOLO detection failed (%s), falling back to color", e)

        if self._use_color_fallback:
            return self._detect_color(frame)

        return []

    def detect_fusion(self, frame: np.ndarray) -> list[Detection]:
        yolo_dets = []
        if self._model_loaded and self._yolo_model is not None:
            try:
                yolo_dets = self._detect_yolo(frame)
            except Exception as e:
                logger.warning("YOLO detection failed in fusion: %s", e)

        if len(yolo_dets) >= 3:
            return yolo_dets

        if self._use_color_fallback:
            hsv_dets = self._detect_color(frame)
            if not yolo_dets:
                return hsv_dets
            merged = list(yolo_dets)
            for hd in hsv_dets:
                overlaps = False
                for yd in yolo_dets:
                    iou = self._det_iou(hd, yd)
                    if iou > 0.2:
                        overlaps = True
                        break
                if not overlaps:
                    merged.append(hd)
            return merged

        return yolo_dets

    @staticmethod
    def _det_iou(a: Detection, b: Detection) -> float:
        x1 = max(a.x_min, b.x_min)
        y1 = max(a.y_min, b.y_min)
        x2 = min(a.x_max, b.x_max)
        y2 = min(a.y_max, b.y_max)
        if x2 <= x1 or y2 <= y1:
            return 0.0
        inter = (x2 - x1) * (y2 - y1)
        area_a = max((a.x_max - a.x_min) * (a.y_max - a.y_min), 1)
        area_b = max((b.x_max - b.x_min) * (b.y_max - b.y_min), 1)
        return inter / (area_a + area_b - inter)

    def _detect_yolo(self, frame: np.ndarray) -> list[Detection]:
        results = self._yolo_model(
            frame,
            conf=self._confidence_threshold,
            iou=self._iou_threshold,
            verbose=False,
        )

        detections: list[Detection] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                xyxy = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0].cpu().numpy())
                cls_id = int(box.cls[0].cpu().numpy())
                cls_name = (
                    self._yolo_model.names.get(cls_id, "price_tag")
                    if hasattr(self._yolo_model, "names")
                    else "price_tag"
                )
                detections.append(
                    Detection(
                        x_min=int(xyxy[0]),
                        y_min=int(xyxy[1]),
                        x_max=int(xyxy[2]),
                        y_max=int(xyxy[3]),
                        confidence=conf,
                        class_id=cls_id,
                        class_name=cls_name,
                    )
                )

        logger.debug("YOLO detected %d price tags", len(detections))
        return detections

    def _detect_color(self, frame: np.ndarray) -> list[Detection]:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        red_mask1 = cv2.inRange(hsv, np.array([0, 70, 80]), np.array([10, 255, 255]))
        red_mask2 = cv2.inRange(hsv, np.array([170, 70, 80]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)

        yellow_mask = cv2.inRange(hsv, np.array([15, 70, 80]), np.array([35, 255, 255]))

        combined_mask = cv2.bitwise_or(red_mask, yellow_mask)

        kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        kernel_large = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel_large, iterations=2)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel_small, iterations=1)
        combined_mask = cv2.dilate(combined_mask, kernel_small, iterations=1)

        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h_frame, w_frame = frame.shape[:2]
        min_area = (w_frame * h_frame) * 0.0008
        max_area = (w_frame * h_frame) * 0.15

        detections: list[Detection] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area or area > max_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.4 or aspect_ratio > 6.0:
                continue

            solidity = area / (w * h) if (w * h) > 0 else 0
            if solidity < 0.4:
                continue

            detections.append(
                Detection(
                    x_min=x,
                    y_min=y,
                    x_max=x + w,
                    y_max=y + h,
                    confidence=min(solidity * 0.9, 0.95),
                    class_id=0,
                    class_name="price_tag_color",
                )
            )

        detections = self._apply_nms(detections, self._iou_threshold)

        if not detections:
            contours_internal, _ = cv2.findContours(combined_mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours_internal:
                area = cv2.contourArea(contour)
                if area < min_area or area > max_area:
                    continue
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h if h > 0 else 0
                if aspect_ratio < 0.4 or aspect_ratio > 6.0:
                    continue
                detections.append(
                    Detection(
                        x_min=x,
                        y_min=y,
                        x_max=x + w,
                        y_max=y + h,
                        confidence=0.3,
                        class_id=0,
                        class_name="price_tag_color_internal",
                    )
                )
            detections = self._apply_nms(detections, self._iou_threshold)

        detections = self._expand_bboxes(detections, frame)

        logger.debug("Color-based detection found %d price tags", len(detections))
        return detections

    @staticmethod
    def _expand_bboxes(detections: list, frame: np.ndarray) -> list[Detection]:
        h_frame, w_frame = frame.shape[:2]
        expanded = []
        for d in detections:
            bw = d.x_max - d.x_min
            bh = d.y_max - d.y_min
            expand_right = int(bw * 1.5)
            expand_left = int(bw * 0.2)
            expand_top = int(bh * 0.15)
            expand_bottom = int(bh * 0.2)
            new_d = Detection(
                x_min=max(0, d.x_min - expand_left),
                y_min=max(0, d.y_min - expand_top),
                x_max=min(w_frame, d.x_max + expand_right),
                y_max=min(h_frame, d.y_max + expand_bottom),
                confidence=d.confidence,
                class_id=d.class_id,
                class_name=d.class_name,
            )
            expanded.append(new_d)
        return expanded

    @staticmethod
    def _apply_nms(detections: list[Detection], iou_threshold: float) -> list[Detection]:
        if not detections:
            return []

        boxes = np.array([[d.x_min, d.y_min, d.x_max, d.y_max] for d in detections])
        scores = np.array([d.confidence for d in detections])

        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        x2 = boxes[:, 2]
        y2 = boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)

        order = scores.argsort()[::-1]
        keep: list[int] = []

        while order.size > 0:
            i = order[0]
            keep.append(i)

            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
            iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)

            remaining = np.where(iou <= iou_threshold)[0]
            order = order[remaining + 1]

        return [detections[i] for i in keep]

    @staticmethod
    def crop_detection(frame: np.ndarray, detection: Detection, padding: int = 5) -> np.ndarray:
        h, w = frame.shape[:2]
        pad_x = max(padding, int((detection.x_max - detection.x_min) * 0.15))
        pad_y = max(padding, int((detection.y_max - detection.y_min) * 0.15))
        x1 = max(0, detection.x_min - pad_x)
        y1 = max(0, detection.y_min - pad_y)
        x2 = min(w, detection.x_max + pad_x)
        y2 = min(h, detection.y_max + pad_y)
        return frame[y1:y2, x1:x2].copy()

    @staticmethod
    def correct_perspective(crop: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return crop

        largest = max(contours, key=cv2.contourArea)
        peri = cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, 0.02 * peri, True)

        if len(approx) != 4:
            return crop

        dst_pts = np.array(
            [[0, 0], [crop.shape[1], 0], [crop.shape[1], crop.shape[0]], [0, crop.shape[0]]],
            dtype=np.float32,
        )
        src_pts = approx.reshape(4, 2).astype(np.float32)
        src_pts = _order_points(src_pts)

        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped = cv2.warpPerspective(
            crop, matrix, (crop.shape[1], crop.shape[0]), flags=cv2.INTER_LINEAR
        )
        return warped


def _order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    d = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(d)]
    rect[3] = pts[np.argmax(d)]
    return rect
