import pytest

from src.ingestion.chunker import ChunkSpec, chunk_pages
from src.ingestion.pdf_extractor import PageText


def _reconstruct(chunk: ChunkSpec, pages: list[PageText]) -> str:
    contents = {page.page_number: page.content for page in pages}
    return "".join(
        contents[span.page_number][span.start_offset : span.end_offset]
        for span in chunk.spans
    )


def test_chunks_respect_size_and_overlap() -> None:
    pages = [PageText(page_number=1, content="A" * 1000 + "B" * 1000 + "C" * 1000)]

    chunks = chunk_pages(pages, chunk_size=1000, overlap_size=200)

    assert len(chunks) == 4
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2, 3]
    assert all(len(chunk.content) <= 1000 for chunk in chunks)
    for previous, current in zip(chunks, chunks[1:]):
        assert previous.content[-200:] == current.content[:200]


def test_text_shorter_than_chunk_size_gives_one_chunk() -> None:
    chunks = chunk_pages(
        [PageText(page_number=1, content="short")],
        chunk_size=1000,
        overlap_size=200,
    )

    assert len(chunks) == 1
    assert chunks[0].content == "short"


def test_empty_input_gives_no_chunks() -> None:
    assert chunk_pages([], chunk_size=1000, overlap_size=200) == []
    assert (
        chunk_pages(
            [PageText(page_number=1, content="")],
            chunk_size=1000,
            overlap_size=200,
        )
        == []
    )


def test_cross_page_spans_have_correct_offsets() -> None:
    pages = [
        PageText(page_number=1, content="abcde"),
        PageText(page_number=2, content="fghij"),
    ]

    chunks = chunk_pages(pages, chunk_size=7, overlap_size=2)

    assert chunks[0].content == "abcdefg"
    assert [
        (span.page_number, span.start_offset, span.end_offset)
        for span in chunks[0].spans
    ] == [(1, 0, 5), (2, 0, 2)]
    assert chunks[1].content == "fghij"
    assert [
        (span.page_number, span.start_offset, span.end_offset)
        for span in chunks[1].spans
    ] == [(2, 0, 5)]


def test_page_longer_than_chunk_size_is_covered_by_several_chunks() -> None:
    pages = [PageText(page_number=1, content="x" * 2500)]

    chunks = chunk_pages(pages, chunk_size=1000, overlap_size=200)

    assert len(chunks) == 3
    assert all(
        span.page_number == 1 for chunk in chunks for span in chunk.spans
    )


def test_reconstruction_invariant_and_unicode_offsets() -> None:
    pages = [
        PageText(page_number=1, content="Tiếng Việt — test"),
        PageText(page_number=2, content="abcdef"),
    ]

    chunks = chunk_pages(pages, chunk_size=8, overlap_size=2)

    assert chunks
    assert all(_reconstruct(chunk, pages) == chunk.content for chunk in chunks)
    assert any("Việt" in chunk.content for chunk in chunks)


@pytest.mark.parametrize(
    ("chunk_size", "overlap_size"),
    [(0, 0), (-1, 0), (10, -1), (10, 10), (10, 11)],
)
def test_invalid_parameters_raise_value_error(
    chunk_size: int, overlap_size: int
) -> None:
    with pytest.raises(ValueError):
        chunk_pages(
            [PageText(page_number=1, content="abc")],
            chunk_size=chunk_size,
            overlap_size=overlap_size,
        )
