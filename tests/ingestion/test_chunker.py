import pytest

from src.ingestion.chunker import chunk_pages, merge_pages
from src.ingestion.models import ChunkSpec, PageText


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


def test_text_and_ocr_pages_produce_identical_chunks() -> None:
    text_pages = [PageText(page_number=1, content="abcdefghij")]
    ocr_pages = [
        PageText(
            page_number=1,
            content="abcdefghij",
            method="ocr",
            confidence=0.92,
        )
    ]

    assert chunk_pages(text_pages, 4, 1) == chunk_pages(ocr_pages, 4, 1)


def test_mixed_pages_keep_reconstruction_invariant() -> None:
    pages = [
        PageText(page_number=1, content="abcde"),
        PageText(page_number=2, content="fghij", method="ocr", confidence=0.9),
        PageText(page_number=3, content="klmno"),
    ]

    chunks = chunk_pages(pages, chunk_size=7, overlap_size=2)

    assert chunks
    assert all(_reconstruct(chunk, pages) == chunk.content for chunk in chunks)


def test_chunk_crossing_text_and_ocr_has_both_spans() -> None:
    pages = [
        PageText(page_number=1, content="abcde"),
        PageText(page_number=2, content="fghij", method="ocr", confidence=0.9),
    ]

    chunks = chunk_pages(pages, chunk_size=7, overlap_size=0)

    assert [
        (span.page_number, span.start_offset, span.end_offset)
        for span in chunks[0].spans
    ] == [(1, 0, 5), (2, 0, 2)]


def test_empty_page_between_pages_gets_no_spans() -> None:
    pages = [
        PageText(page_number=1, content="ab"),
        PageText(page_number=2, content="", method="ocr"),
        PageText(page_number=3, content="cd"),
    ]

    chunks = chunk_pages(pages, chunk_size=4, overlap_size=0)

    assert chunks[0].content == "abcd"
    assert all(span.page_number != 2 for chunk in chunks for span in chunk.spans)


def test_all_empty_pages_give_no_chunks() -> None:
    pages = [PageText(page_number=1, content=""), PageText(page_number=2, content="")]

    assert chunk_pages(pages, chunk_size=10, overlap_size=1) == []


@pytest.mark.parametrize(
    "pages",
    [
        [PageText(page_number=1, content="a"), PageText(page_number=1, content="b")],
        [PageText(page_number=2, content="a"), PageText(page_number=1, content="b")],
        [PageText(page_number=1, content=None)],
    ],
)
def test_invalid_pages_raise_value_error(pages) -> None:
    with pytest.raises(ValueError):
        chunk_pages(pages, chunk_size=10, overlap_size=1)


def test_chunking_does_not_change_page_metadata() -> None:
    pages = [
        PageText(page_number=1, content="abc", method="ocr", confidence=0.85)
    ]

    chunk_pages(pages, chunk_size=2, overlap_size=0)

    assert pages == [
        PageText(page_number=1, content="abc", method="ocr", confidence=0.85)
    ]


def test_merge_pages_sorts_and_prefers_non_empty_content() -> None:
    native = [
        PageText(page_number=1, content="native"),
        PageText(page_number=2, content="   "),
        PageText(page_number=4, content="four"),
    ]
    ocr = [
        PageText(page_number=2, content="ocr text", method="ocr", confidence=0.9),
        PageText(page_number=3, content="", method="ocr"),
        PageText(page_number=4, content="ocr four", method="ocr", confidence=0.9),
    ]

    merged = merge_pages(native, ocr)

    assert [page.page_number for page in merged] == [1, 2, 3, 4]
    assert merged[0].method == "text"
    assert merged[1].content == "ocr text"
    assert merged[2].method == "ocr"
    assert merged[3].content == "four"


def test_merge_pages_keeps_ocr_method_when_both_are_empty() -> None:
    native = [PageText(page_number=1, content="")]
    ocr = [PageText(page_number=1, content="", method="ocr")]

    merged = merge_pages(native, ocr)

    assert merged == [PageText(page_number=1, content="", method="ocr")]


def test_merge_pages_rejects_gaps() -> None:
    with pytest.raises(ValueError):
        merge_pages([PageText(page_number=2, content="a")], [])
