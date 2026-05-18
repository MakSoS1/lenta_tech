"""OCR text extraction from price tag images using PaddleOCR."""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

PRICE_PATTERN = re.compile(r"\d+[\.,]\d{1,2}")
BARCODE_PATTERN = re.compile(r"\b\d{13}\b")
DISCOUNT_PATTERN = re.compile(r"[-−]\s*\d{1,3}\s*[%٪]")
SKU_PATTERN = re.compile(r"\b\d{6,12}\b")
DATETIME_PATTERN = re.compile(r"\d{2}[./\-]\d{2}[./\-]\d{2,4}\s*\d{2}:\d{2}")


@dataclass
class TagFields:
    product_name: str = ""
    price_default: str = ""
    price_card: str = ""
    price_discount: str = ""
    barcode: str = ""
    discount_amount: str = ""
    id_sku: str = ""
    print_datetime: str = ""
    code: str = ""
    additional_info: str = ""
    color: str = ""
    special_symbols: str = ""


class TextExtractor:
    def __init__(self, use_gpu: bool = False) -> None:
        self._ocr = None
        self._ocr_engine = ""
        self._initialized = False
        self._init_ocr(use_gpu)

    def _init_ocr(self, use_gpu: bool) -> None:
        self._easyocr = None

        try:
            import easyocr
            self._easyocr = easyocr.Reader(["ru", "en"], gpu=use_gpu)
            self._ocr = self._easyocr
            self._ocr_engine = "easyocr"
            self._initialized = True
            logger.info("EasyOCR initialized (gpu=%s)", use_gpu)
        except ImportError:
            logger.warning("easyocr not installed")
        except Exception as e:
            logger.warning("Failed to initialize EasyOCR: %s", e)

        if not hasattr(self, '_initialized') or not self._initialized:
            self._initialized = False
            logger.warning("No OCR engine available")

    def _preprocess_for_ocr(self, image: np.ndarray) -> np.ndarray:
        import cv2
        h, w = image.shape[:2]
        target_h = max(h * 2, 200)
        scale = max(1, target_h // max(h, 1))
        if scale > 1:
            image = cv2.resize(image, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_ch, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
        l_ch = clahe.apply(l_ch)
        enhanced = cv2.merge([l_ch, a, b])
        image = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        return image

    def extract_text(self, image: np.ndarray) -> list[tuple[str, float]]:
        if not self._initialized:
            logger.warning("OCR not initialized, returning empty results")
            return []

        texts: list[tuple[str, float]] = []

        preprocessed = self._preprocess_for_ocr(image)

        if self._ocr_engine == "easyocr":
            try:
                results = self._ocr.readtext(preprocessed)
                for bbox, text, conf in results:
                    if text and text.strip():
                        texts.append((text.strip(), float(conf)))
            except Exception as e:
                logger.warning("EasyOCR extraction failed: %s", e)

        elif self._ocr_engine == "paddleocr":
            try:
                result = self._ocr.predict(image)
            except TypeError:
                try:
                    result = self._ocr.ocr(image)
                except Exception as e:
                    logger.warning("PaddleOCR extraction failed: %s", e)
                    return []
            except Exception as e:
                logger.warning("PaddleOCR extraction failed: %s", e)
                return []

            if result is None:
                return texts

            for page in result:
                if page is None:
                    continue
                if hasattr(page, 'rec_texts'):
                    for text, conf in zip(page.rec_texts, page.rec_scores):
                        if text and text.strip():
                            texts.append((text.strip(), float(conf)))
                elif isinstance(page, list):
                    for line in page:
                        if line is None:
                            continue
                        if isinstance(line, dict):
                            text = line.get('rec_text', line.get('text', ''))
                            conf = line.get('rec_score', line.get('score', 0.0))
                            if text:
                                texts.append((text.strip(), float(conf)))
                        elif isinstance(line, (list, tuple)) and len(line) >= 2:
                            text_info = line[1]
                            if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                                texts.append((str(text_info[0]).strip(), float(text_info[1])))

        logger.debug("OCR extracted %d text blocks", len(texts))
        return texts

    def map_fields(self, texts: list[tuple[str, float]], image: np.ndarray = None) -> TagFields:
        fields = TagFields()

        all_text = [t for t, _ in texts]
        full_text = " ".join(all_text)

        barcode_match = BARCODE_PATTERN.search(full_text)
        if barcode_match:
            fields.barcode = barcode_match.group(0)

        discount_match = DISCOUNT_PATTERN.search(full_text)
        if discount_match:
            fields.discount_amount = discount_match.group(0).strip()

        prices = self._extract_prices(all_text)
        if len(prices) >= 1:
            fields.price_default = prices[0]
        if len(prices) >= 2:
            fields.price_card = prices[1]
        if len(prices) >= 3:
            fields.price_discount = prices[2]

        sku_match = SKU_PATTERN.search(full_text)
        if sku_match and (not fields.barcode or sku_match.group(0) != fields.barcode):
            fields.id_sku = sku_match.group(0)

        dt_match = DATETIME_PATTERN.search(full_text)
        if dt_match:
            fields.print_datetime = dt_match.group(0)

        fields.product_name = self._extract_product_name(all_text, fields)

        fields.code = self._extract_code(full_text, fields)

        if image is not None:
            fields.color = self._detect_tag_color(image)

        fields.special_symbols = self._extract_special_symbols(full_text)

        remaining_parts: list[str] = []
        consumed = {
            fields.barcode, fields.discount_amount, fields.price_default,
            fields.price_card, fields.price_discount, fields.id_sku,
            fields.print_datetime, fields.product_name, fields.code,
        }
        for t in all_text:
            if t not in consumed and t.strip():
                remaining_parts.append(t.strip())
        if remaining_parts:
            fields.additional_info = "; ".join(remaining_parts)

        return fields

    def _extract_prices(self, text_lines: list[str]) -> list[str]:
        prices: list[str] = []
        for line in text_lines:
            for m in PRICE_PATTERN.finditer(line):
                val = m.group(0).replace(",", ".")
                if val not in prices:
                    prices.append(val)
        return prices

    def _extract_product_name(self, text_lines: list[str], fields: TagFields) -> str:
        candidates: list[tuple[str, int]] = []
        price_texts = {fields.price_default, fields.price_card, fields.price_discount}
        skip = {fields.barcode, fields.discount_amount, fields.print_datetime, fields.id_sku}

        for line in text_lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped in price_texts or stripped in skip:
                continue
            if BARCODE_PATTERN.fullmatch(stripped):
                continue
            if PRICE_PATTERN.fullmatch(stripped):
                continue
            if DISCOUNT_PATTERN.search(stripped):
                continue
            if DATETIME_PATTERN.search(stripped):
                continue

            has_alpha = any(c.isalpha() for c in stripped)
            if has_alpha:
                candidates.append((stripped, len(stripped)))

        if not candidates:
            return ""

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def _extract_code(self, full_text: str, fields: TagFields) -> str:
        code_pattern = re.compile(r"\b([A-Za-zА-Яа-я]{1,4}[\-]?\d{2,6})\b")
        for m in code_pattern.finditer(full_text):
            candidate = m.group(0)
            if candidate != fields.barcode and candidate != fields.id_sku:
                return candidate
        return ""

    def _detect_tag_color(self, image: np.ndarray) -> str:
        try:
            import cv2

            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            h_mean = hsv[:, :, 0].mean()

            if (0 <= h_mean <= 10) or (170 <= h_mean <= 180):
                return "red"
            elif 20 <= h_mean <= 35:
                return "yellow"
            elif 10 < h_mean < 20:
                return "orange"
            else:
                return "other"
        except Exception:
            return ""

    def _extract_special_symbols(self, full_text: str) -> str:
        symbols: list[str] = []
        star_pattern = re.compile(r"[★☆⭐✦✧]")
        if star_pattern.search(full_text):
            symbols.append("star")
        arrow_pattern = re.compile(r"[→➔➡►◀◄⇒⇐]")
        if arrow_pattern.search(full_text):
            symbols.append("arrow")
        card_pattern = re.compile(r"(?:карт|карт[аы]|card)", re.IGNORECASE)
        if card_pattern.search(full_text):
            symbols.append("card_icon")
        return ";".join(symbols)
