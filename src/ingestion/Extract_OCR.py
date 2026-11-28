from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pymupdf as fitz
import pytesseract
from PIL import Image

from config import settings
from src.ingestion.errors import LowConfidenceError, OcrEngineError
from src.ingestion.models import PageText

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float | None


class OcrEngine(Protocol):
    def recognize(self, image: Image.Image) -> OcrResult: ...


class TesseractEngine:
    def __init__(
        self,
        languages: str | None = None,
        tesseract_cmd: str | None = None,
    ) -> None:
        self.languages = languages or settings.OCR_LANGUAGES
        configured_cmd = tesseract_cmd or settings.TESSERACT_CMD
        previous_cmd = pytesseract.pytesseract.tesseract_cmd
        if configured_cmd:
            pytesseract.pytesseract.tesseract_cmd = configured_cmd
        try:
            available = set(pytesseract.get_languages(config=""))
        except Exception as exc:
            if configured_cmd:
                pytesseract.pytesseract.tesseract_cmd = previous_cmd
            raise OcrEngineError("Tesseract is not available") from exc

        missing = [
            language
            for language in self.languages.split("+")
            if language and language not in available
        ]
        if missing:
            if configured_cmd:
                pytesseract.pytesseract.tesseract_cmd = previous_cmd
            raise OcrEngineError(
                f"Missing Tesseract language data: {', '.join(missing)}"
            )

        self.tesseract_cmd = configured_cmd
        if configured_cmd:
            pytesseract.pytesseract.tesseract_cmd = configured_cmd
        logger.debug("tesseract engine ready languages=%s", self.languages)

    def recognize(self, image: Image.Image) -> OcrResult:
        try:
            data = pytesseract.image_to_data(
                image, lang=self.languages, output_type=pytesseract.Output.DICT
            )
        except Exception as exc:
            raise OcrEngineError("OCR engine call failed") from exc
        return result_from_data(data)


def result_from_data(data: dict[str, Sequence[object]]) -> OcrResult:
    groups: dict[tuple[int, int, int], list[str]] = {}
    confidences: list[float] = []
    columns = (
        data.get("text", []),
        data.get("conf", []),
        data.get("block_num", []),
        data.get("par_num", []),
        data.get("line_num", []),
    )
    for text, conf, block, paragraph, line in zip(*columns):
        word = str(text).strip()
        if not word:
            continue
        try:
            score = float(conf)
        except (TypeError, ValueError):
            continue
        if score < 0:
            continue
        groups.setdefault((int(block), int(paragraph), int(line)), []).append(word)
        confidences.append(score)

    paragraphs: dict[tuple[int, int], list[str]] = {}
    for (block, paragraph, _), words in sorted(groups.items()):
        paragraphs.setdefault((block, paragraph), []).append(" ".join(words))
    text = "\n\n".join(
        "\n".join(lines) for lines in paragraphs.values()
    )

    confidence = sum(confidences) / len(confidences) if confidences else None
    return OcrResult(text=text, confidence=confidence)


def normalize_ocr_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", normalized).strip("\n")


def ocr_pages(
    file_path: str | Path,
    page_numbers: Iterable[int],
    engine: OcrEngine | None = None,
    dpi: int | None = None,
    min_confidence: float | None = None,
) -> list[PageText]:
    effective_dpi = settings.OCR_DPI if dpi is None else dpi
    threshold = (
        settings.OCR_MIN_CONFIDENCE if min_confidence is None else min_confidence
    )
    if effective_dpi <= 0:
        raise ValueError("dpi must be greater than 0")

    active_engine = engine if engine is not None else TesseractEngine()
    pages: list[PageText] = []
    with fitz.open(file_path) as document:
        for number in page_numbers:
            if number < 1 or number > document.page_count:
                raise ValueError(f"Page number out of range: {number}")
            pixmap = document[number - 1].get_pixmap(dpi=effective_dpi)
            image = Image.frombytes(
                "RGB", (pixmap.width, pixmap.height), pixmap.samples
            )
            try:
                result = active_engine.recognize(image)
            except OcrEngineError:
                raise
            except Exception as exc:
                raise OcrEngineError(
                    f"OCR failed on page {number}"
                ) from exc

            content = normalize_ocr_text(result.text)
            score = result.confidence
            if content:
                if score is None:
                    raise OcrEngineError(
                        f"OCR confidence missing on page {number}"
                    )
                if score < threshold:
                    raise LowConfidenceError(number, score, threshold)
                confidence = score / 100
            else:
                confidence = None
                logger.warning("ocr page empty page_number=%d", number)

            logger.debug(
                "ocr page completed page_number=%d confidence=%s characters=%d",
                number,
                score,
                len(content),
            )
            pages.append(
                PageText(
                    page_number=number,
                    content=content,
                    method="ocr",
                    confidence=confidence,
                )
            )
    return pages
