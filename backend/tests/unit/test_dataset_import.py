import json
from zipfile import ZipFile

import httpx
import pytest

from app.domain.errors import DomainError
from app.services.dataset_import import (
    ArchiveSource,
    DirectorySource,
    DockerSource,
    build_manifest,
    checked_path,
)


def record(attachments=None):
    return {
        "email_id": "email_001",
        "from": "test@example.test",
        "subject": "Review draft BL",
        "body": "Please check",
        "attachments": attachments or ["attachments/test.txt"],
    }


def test_directory_archive_http_have_identical_manifest(tmp_path):
    (tmp_path / "inbox").mkdir()
    (tmp_path / "attachments").mkdir()
    payload = json.dumps(record()).encode()
    (tmp_path / "inbox/email_001.json").write_bytes(payload)
    (tmp_path / "attachments/test.txt").write_bytes(b"Shipping instructions")
    (tmp_path / "ground_truth.json").write_text("NOT JSON: must never be read")
    archive = tmp_path / "bundle.zip"
    with ZipFile(archive, "w") as z:
        z.writestr("inbox/email_001.json", payload)
        z.writestr("attachments/test.txt", b"Shipping instructions")
        z.writestr("ground_truth.json", "MUST NEVER READ")
        z.writestr("README.md", "MUST NEVER READ")
    paths = []

    def handle(request):
        paths.append(request.url.path)
        if request.url.path == "/emails":
            return httpx.Response(200, json=[record()])
        assert request.url.path == "/attachments/test.txt"
        return httpx.Response(200, content=b"Shipping instructions")

    sources = [
        DirectorySource(tmp_path),
        ArchiveSource(archive),
        DockerSource("http://127.0.0.1:8080", httpx.Client(transport=httpx.MockTransport(handle))),
    ]
    try:
        manifests = [build_manifest(source) for source in sources]
        assert manifests[0] == manifests[1] == manifests[2]
        assert manifests[0]["summary"]["emails"] == 1
        assert paths == ["/emails", "/attachments/test.txt"]
    finally:
        for source in sources:
            source.close()


@pytest.mark.parametrize(
    "path",
    [
        "../ground_truth.json",
        "attachments/../../secret.txt",
        "attachments\\test.txt",
        "/attachments/test.txt",
        "attachments/test.exe",
        "inbox/README.md",
    ],
)
def test_non_input_paths_rejected(path):
    with pytest.raises(DomainError):
        checked_path(path)


def test_missing_attachment_is_explicit_and_duplicate_email_rejected(tmp_path):
    archive = tmp_path / "bundle.zip"
    with ZipFile(archive, "w") as z:
        z.writestr("data_v2/inbox/email_001.json", json.dumps(record()))
    source = ArchiveSource(archive)
    try:
        manifest = build_manifest(source)
        assert manifest["summary"]["missing"] == 1
        assert manifest["attachments"] == [{"path": "attachments/test.txt", "state": "missing"}]
    finally:
        source.close()
    source = DockerSource(
        "http://localhost:8080",
        httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[record(), record()]))
        ),
    )
    try:
        with pytest.raises(DomainError, match="duplicate"):
            source.emails()
    finally:
        source.close()


def test_remote_docker_origin_rejected():
    with pytest.raises(DomainError):
        DockerSource("https://example.com")
