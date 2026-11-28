import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf as fitz
import pytest
from PIL import Image

from config import settings
from src.database.init_db import init_db
from src.ingestion.Extract_OCR import OcrResult, TesseractEngine


@dataclass
class FakeOcrEngine:
    results: list[OcrResult] = field(default_factory=list)
    default: OcrResult = OcrResult("", None)
    calls: list[tuple[int, int]] = field(default_factory=list)

    def recognize(self, image: Image.Image) -> OcrResult:
        self.calls.append(image.size)
        index = len(self.calls) - 1
        return self.results[index] if index < len(self.results) else self.default


@pytest.fixture
def fake_engine() -> FakeOcrEngine:
    return FakeOcrEngine()


@pytest.fixture
def real_engine():
    if not (settings.TESSERACT_CMD or shutil.which("tesseract")):
        pytest.skip("Tesseract is not installed")
    try:
        return TesseractEngine(languages="eng")
    except Exception as exc:
        pytest.skip(f"Tesseract is unavailable: {type(exc).__name__}")


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "book_reader.db"
    init_db(path)
    return path


@pytest.fixture
def make_pdf(tmp_path: Path) -> Callable[[list[str], str], Path]:
    def _make(texts: list[str], name: str = "sample.pdf") -> Path:
        path = tmp_path / name
        document = fitz.open()
        for text in texts:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        document.save(path)
        document.close()
        return path

    return _make


@pytest.fixture
def make_scanned_pdf(tmp_path: Path) -> Callable[[list[str], str], Path]:
    def _make(texts: list[str], name: str = "scanned.pdf") -> Path:
        path = tmp_path / name
        source = fitz.open()
        output = fitz.open()
        for text in texts:
            native_page = source.new_page()
            if text:
                native_page.insert_text((72, 72), text)
            image_bytes = native_page.get_pixmap(dpi=300).tobytes("png")
            page = output.new_page(width=native_page.rect.width, height=native_page.rect.height)
            page.insert_image(page.rect, stream=image_bytes)
        output.save(path)
        output.close()
        source.close()
        return path

    return _make


@pytest.fixture
def make_text_image(tmp_path: Path) -> Callable[[str, str], Path]:
    def _make(text: str, name: str = "page.png") -> Path:
        path = tmp_path / name
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), text, fontsize=18)
        page.get_pixmap(dpi=300).save(path)
        document.close()
        return path

    return _make


@pytest.fixture
def make_zero_page_pdf(tmp_path: Path) -> Callable[[str], Path]:
    def _make(name: str = "zero.pdf") -> Path:
        path = tmp_path / name
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [] /Count 0 >>",
        ]
        data = bytearray(b"%PDF-1.4\n")
        offsets: list[int] = []
        for number, obj in enumerate(objects, start=1):
            offsets.append(len(data))
            data.extend(f"{number} 0 obj\n".encode())
            data.extend(obj)
            data.extend(b"\nendobj\n")
        xref_position = len(data)
        data.extend(f"xref\n0 {len(objects) + 1}\n".encode())
        data.extend(b"0000000000 65535 f \n")
        for offset in offsets:
            data.extend(f"{offset:010d} 00000 n \n".encode())
        data.extend(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_position}\n%%EOF\n".encode()
        )
        path.write_bytes(data)
        return path

    return _make
