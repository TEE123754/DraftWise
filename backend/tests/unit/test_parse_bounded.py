import multiprocessing

import pytest

from app.config import Settings
from app.domain.errors import DomainError
from app.infrastructure import parsing
from app.infrastructure.parsing import IN_PROCESS_TEXT_LIMIT, parse_bounded

SI = b"SHIPPING INSTRUCTIONS\nShipper: Acme Export\nGross Weight: 22,000 KG\n"


class SubprocessUsed(Exception):
    pass


@pytest.fixture
def no_subprocess(monkeypatch):
    def refuse(*args, **kwargs):
        raise SubprocessUsed

    monkeypatch.setattr(multiprocessing, "get_context", refuse)


def test_a_small_text_file_is_read_in_process(no_subprocess):
    document = parse_bounded(SI, "si", Settings())
    assert document.format == "txt"
    assert [block.text for block in document.blocks][1] == "Shipper: Acme Export"


def test_in_process_reading_reports_the_same_errors_as_the_isolated_parser(no_subprocess):
    with pytest.raises(DomainError) as binary:
        parse_bounded(b"text\x00binary", "x", Settings())
    assert binary.value.code == "FILE_UNSUPPORTED"
    with pytest.raises(DomainError) as empty:
        parse_bounded(b"", "x", Settings())
    assert empty.value.code == "FILE_EMPTY"
    with pytest.raises(DomainError) as blank:
        parse_bounded(b"  \n\n  ", "x", Settings())
    assert blank.value.code == "EVIDENCE_INCOMPLETE"


def test_unexpected_parser_failures_become_a_corrupt_file_error(monkeypatch, no_subprocess):
    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(parsing, "parse_document", explode)
    with pytest.raises(DomainError) as error:
        parse_bounded(SI, "x", Settings())
    assert error.value.code == "FILE_CORRUPT"


@pytest.mark.parametrize(
    "data",
    [
        b"%PDF-1.4 anything",  # a container format keeps the isolated, time-limited process
        b"PK\x03\x04 anything",
        b"x" * (IN_PROCESS_TEXT_LIMIT + 1),  # so does text too large to read on the worker itself
    ],
    ids=["pdf", "office", "large-text"],
)
def test_containers_and_large_files_still_use_the_isolated_process(no_subprocess, data):
    with pytest.raises(SubprocessUsed):
        parse_bounded(data, "x", Settings())


def test_a_large_text_file_still_parses_through_the_isolated_process():
    data = b"Shipper: Acme Export\n" * (IN_PROCESS_TEXT_LIMIT // 20)
    assert len(data) > IN_PROCESS_TEXT_LIMIT
    assert parse_bounded(data, "big", Settings()).format == "txt"
