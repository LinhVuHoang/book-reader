class IngestionError(Exception):
    pass


class PdfReadError(IngestionError):
    pass


class DuplicateBookError(IngestionError):
    pass


class NoTextError(IngestionError):
    pass


class InvalidFormatError(IngestionError):
    pass


class EmptyInputError(IngestionError):
    pass


class OcrEngineError(IngestionError):
    pass


class LowConfidenceError(IngestionError):
    def __init__(
        self, page_number: int, confidence: float, threshold: float
    ) -> None:
        self.page_number = page_number
        self.confidence = confidence
        self.threshold = threshold
        super().__init__(
            f"OCR confidence too low on page {page_number}: "
            f"{confidence} < {threshold}"
        )
