"""QR code decoder for price tag images using pyzbar."""

import logging
import re
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class QRResult:
    qr_code_barcode: str = ""
    price1_qr: str = ""
    price2_qr: str = ""
    price3_qr: str = ""
    price4_qr: str = ""
    wholesale_level_1_count: str = ""
    wholesale_level_1_price: str = ""
    wholesale_level_2_count: str = ""
    wholesale_level_2_price: str = ""
    action_price_qr: str = ""
    action_code_qr: str = ""
    raw_data: str = ""


QR_KEY_MAP: dict[str, str] = {
    "barcode": "qr_code_barcode",
    "b": "qr_code_barcode",
    "price1": "price1_qr",
    "p1": "price1_qr",
    "price2": "price2_qr",
    "p2": "price2_qr",
    "price3": "price3_qr",
    "p3": "price3_qr",
    "price4": "price4_qr",
    "p4": "price4_qr",
    "wholesaleLevel1Count": "wholesale_level_1_count",
    "wL1C": "wholesale_level_1_count",
    "wholesaleLevel1Price": "wholesale_level_1_price",
    "wL1P": "wholesale_level_1_price",
    "wholesaleLevel2Count": "wholesale_level_2_count",
    "wL2C": "wholesale_level_2_count",
    "wholesaleLevel2Price": "wholesale_level_2_price",
    "wL2P": "wholesale_level_2_price",
    "actionPrice": "action_price_qr",
    "aP": "action_price_qr",
    "actionCode": "action_code_qr",
    "aC": "action_code_qr",
}


class QRDecoder:
    def __init__(self) -> None:
        self._pyzbar_available = True
        try:
            from pyzbar.pyzbar import decode as _  # noqa: F401
        except ImportError:
            self._pyzbar_available = False
            logger.warning("pyzbar not installed, QR decoding unavailable")

    def decode_qr_codes(self, image: np.ndarray) -> list[QRResult]:
        if not self._pyzbar_available:
            return []

        try:
            from pyzbar.pyzbar import decode as qr_decode
        except ImportError:
            return []

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

        decoded_objects = qr_decode(gray)
        if not decoded_objects:
            gray_sharp = cv2.GaussianBlur(gray, (0, 0), 3)
            gray_sharp = cv2.addWeighted(gray, 1.5, gray_sharp, -0.5, 0)
            decoded_objects = qr_decode(gray_sharp)

        if not decoded_objects:
            scale = 2
            h, w = gray.shape
            resized = cv2.resize(gray, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
            decoded_objects = qr_decode(resized)

        results: list[QRResult] = []
        for obj in decoded_objects:
            raw = ""
            try:
                raw = obj.data.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                try:
                    raw = obj.data.decode("latin-1")
                except Exception:
                    continue

            if not raw:
                continue

            qr_result = self._parse_qr_data(raw)
            results.append(qr_result)

        logger.debug("Decoded %d QR codes", len(results))
        return results

    def _parse_qr_data(self, raw_data: str) -> QRResult:
        result = QRResult(raw_data=raw_data)

        if raw_data.startswith("{"):
            self._parse_json_format(raw_data, result)
        elif ";" in raw_data or "/" in raw_data:
            self._parse_semicolon_format(raw_data, result)
        else:
            self._parse_simple_format(raw_data, result)

        return result

    def _parse_semicolon_format(self, raw_data: str, result: QRResult) -> None:
        pairs = raw_data.split(";")
        for pair in pairs:
            pair = pair.strip()
            if not pair:
                continue

            if "/" in pair:
                key, _, value = pair.partition("/")
                key = key.strip()
                value = value.strip()
            elif "=" in pair:
                key, _, value = pair.partition("=")
                key = key.strip()
                value = value.strip()
            else:
                continue

            field_name = QR_KEY_MAP.get(key)
            if field_name:
                setattr(result, field_name, value)

    def _parse_json_format(self, raw_data: str, result: QRResult) -> None:
        try:
            import json

            data = json.loads(raw_data)
        except Exception:
            self._parse_semicolon_format(raw_data, result)
            return

        for json_key, csv_field in QR_KEY_MAP.items():
            if json_key in data:
                setattr(result, csv_field, str(data[json_key]))

    def _parse_simple_format(self, raw_data: str, result: QRResult) -> None:
        barcode_match = re.search(r"\b\d{13}\b", raw_data)
        if barcode_match:
            result.qr_code_barcode = barcode_match.group(0)

        prices = re.findall(r"\d+[\.,]\d{1,2}", raw_data)
        price_fields = ["price1_qr", "price2_qr", "price3_qr", "price4_qr"]
        for i, price in enumerate(prices[:4]):
            setattr(result, price_fields[i], price.replace(",", "."))
