import logging

import pytest

from config.logging_config import HANDLER_TAG, setup_logging


@pytest.fixture #fixutre là udngf để chuẩn bị dữ liệu, khởi tạo tài nguyên, dọn dẹp cho các bài kiểm thử, Pytest tự động inject kết quả của fixture vào hàm test khi khai báo tên fixture làm tham số
def clean_logging():
    root = logging.getLogger()
    previous_level = root.level
    yield #trước yield setup, sau yield teardown (dọn dẹp)
    for handler in list(root.handlers):
        if getattr(handler, HANDLER_TAG, False):
            root.removeHandler(handler)
            handler.close()
    root.setLevel(previous_level)


def test_setup_logging_twice_does_not_duplicate_handlers(
    clean_logging, tmp_path
) -> None:
    log_path = tmp_path / "logs" / "book.log"

    setup_logging("INFO", str(log_path))
    setup_logging("INFO", str(log_path))

    handlers = [
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, HANDLER_TAG, False)
    ]
    assert len(handlers) == 2

    logging.getLogger("test.setup").info("hello key=1")
    for handler in handlers:
        handler.flush()

    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 1


def test_setup_logging_creates_directory_and_file(
    clean_logging, tmp_path
) -> None:
    log_path = tmp_path / "nested" / "logs" / "book.log"

    setup_logging("DEBUG", str(log_path))
    logging.getLogger("test.setup").debug("created key=1")
    for handler in logging.getLogger().handlers:
        if getattr(handler, HANDLER_TAG, False):
            handler.flush()

    assert log_path.exists()
    assert "created key=1" in log_path.read_text(encoding="utf-8")
