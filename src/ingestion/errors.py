class IngestionError(Exception):
    pass


class PdfReadError(IngestionError):
    pass


class DuplicateBookError(IngestionError):
    pass


class NoTextError(IngestionError):
    pass
