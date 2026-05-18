"""Camera undistortion utilities from the hackathon camera note.

The coefficients are included as an optional preprocessing tool.  It is useful
for retraining/diagnostics and can be enabled for recognition experiments, but
the default inference path keeps original-frame coordinates to preserve the CSV
contract.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class CameraSettings:
    image_size: tuple[int, int] = (3840, 2160)
    diagonal_mm: float = 16.0 / 2.8
    focal_len_mm: float = 2.8


DEFAULT_DISTORTION_COEFFS = [-0.276, 0.06, 0.0084, -0.0016, -0.0044]


class DistortionCorrector:
    def __init__(
        self,
        camera_settings: CameraSettings | None = None,
        distortion_coeffs: list[float] | None = None,
        crop_roi: bool = False,
    ) -> None:
        self.camera_settings = camera_settings or CameraSettings()
        self.width, self.height = self.camera_settings.image_size
        self.dist = np.array(distortion_coeffs or DEFAULT_DISTORTION_COEFFS, dtype=np.float32)
        self.crop_roi = crop_roi
        self.camera_matrix = self._calculate_camera_matrix()
        self.map1, self.map2, self.roi = self._create_undistort_maps()

    def _calculate_camera_matrix(self) -> np.ndarray:
        aspect_ratio = self.width / self.height
        height_mm = self.camera_settings.diagonal_mm / math.sqrt(aspect_ratio**2 + 1)
        width_mm = aspect_ratio * height_mm
        fx = (self.camera_settings.focal_len_mm * self.width) / width_mm
        fy = (self.camera_settings.focal_len_mm * self.height) / height_mm
        return np.array([[fx, 0, self.width / 2], [0, fy, self.height / 2], [0, 0, 1]], dtype=np.float32)

    def _create_undistort_maps(self):
        new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
            self.camera_matrix,
            self.dist,
            (self.width, self.height),
            0,
            (self.width, self.height),
        )
        map1, map2 = cv2.initUndistortRectifyMap(
            self.camera_matrix,
            self.dist,
            None,
            new_camera_matrix,
            (self.width, self.height),
            cv2.CV_32FC1,
        )
        return map1, map2, roi

    def undistort_frame(self, frame: np.ndarray) -> np.ndarray:
        undistorted = cv2.remap(frame, self.map1, self.map2, cv2.INTER_LINEAR)
        if not self.crop_roi:
            return undistorted
        x, y, w, h = self.roi
        return undistorted[y : y + h, x : x + w]
