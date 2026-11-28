from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PageText:
    page_number: int
    content: str
    method: Literal["text", "ocr"] = "text"
    confidence: float | None = None


@dataclass(frozen=True)
class PageSpan:
    page_number: int
    start_offset: int
    end_offset: int


@dataclass(frozen=True)
class ChunkSpec:
    chunk_index: int
    content: str
    spans: list[PageSpan]
