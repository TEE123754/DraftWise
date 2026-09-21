"""Bounded input-only dataset access. Never extracts archives or reads answer keys."""

import hashlib
import json
import re
import stat
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from zipfile import ZipFile

import httpx
from pydantic import Field

from app.ai.grounding import strict_json
from app.domain.errors import DomainError
from app.domain.models import StrictModel

MAX_FILE = 20 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_EMAILS = 10_000
EMAIL_PATH = re.compile(r"inbox/email_[A-Za-z0-9_-]+\.json\Z")
ATTACHMENT_PATH = re.compile(r"attachments/[A-Za-z0-9_. -]+\.(?:txt|pdf|docx|xlsx)\Z", re.I)


def checked_path(name: str) -> str:
    if (
        "\\" in name
        or ".." in PurePosixPath(name).parts
        or not (EMAIL_PATH.fullmatch(name) or ATTACHMENT_PATH.fullmatch(name))
    ):
        raise DomainError(
            "DATASET_PATH_INVALID", "Only inbox records and supported attachments are allowed"
        )
    return name


class InputEmail(StrictModel):
    email_id: str = Field(pattern=r"^email_[A-Za-z0-9_-]+$", max_length=240)
    sender: str = Field(alias="from", min_length=1, max_length=320)
    subject: str = Field(max_length=1000)
    body: str = Field(max_length=100_000)
    attachments: tuple[str, ...] = Field(max_length=20)


def validate_records(records):
    if not isinstance(records, list) or len(records) > MAX_EMAILS:
        raise DomainError("DATASET_LIMIT", "Dataset has an invalid email count")
    parsed = [InputEmail.model_validate(record) for record in records]
    ids = [item.email_id for item in parsed]
    if len(set(ids)) != len(ids):
        raise DomainError("DATASET_DUPLICATE", "Dataset contains duplicate email IDs")
    for item in parsed:
        if len(item.attachments) != len(set(item.attachments)):
            raise DomainError("DATASET_DUPLICATE", "Email contains duplicate attachment references")
        for attachment in item.attachments:
            checked_path(attachment)
            if not ATTACHMENT_PATH.fullmatch(attachment):
                raise DomainError(
                    "DATASET_PATH_INVALID", "Email attachment must refer to a supported attachment"
                )
    return sorted(parsed, key=lambda item: item.email_id)


class DirectorySource:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)

    def read(self, name):
        path = self.root / checked_path(name)
        # Reject links even when their current destination happens to be inside the tree.
        if path.is_symlink() or path.parent.is_symlink():
            raise DomainError("DATASET_PATH_INVALID", "Dataset links are not allowed")
        if not path.resolve().is_relative_to(self.root):
            raise DomainError("DATASET_PATH_INVALID", "Dataset path escapes its root")
        with path.open("rb") as stream:
            data = stream.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            raise DomainError("DATASET_LIMIT", "Dataset file exceeds the size limit")
        return data

    def emails(self):
        names = sorted(p.name for p in (self.root / "inbox").glob("email_*.json"))
        if len(names) > MAX_EMAILS:
            raise DomainError("DATASET_LIMIT", "Dataset has too many emails")
        records = []
        total = 0
        for name in names:
            data = self.read("inbox/" + name)
            total += len(data)
            if total > MAX_TOTAL:
                raise DomainError("DATASET_LIMIT", "Dataset exceeds the aggregate limit")
            record = strict_json(data.decode("utf-8"))
            if record.get("email_id") != Path(name).stem:
                raise DomainError("DATASET_ID_INVALID", "Email ID does not match its filename")
            records.append(record)
        return validate_records(records)

    def close(self):
        pass


class ArchiveSource:
    def __init__(self, archive):
        self.archive = ZipFile(archive)
        try:
            entries = self.archive.infolist()
            if len(entries) > 25_000:
                raise DomainError("DATASET_LIMIT", "Archive has too many entries")
            # Support the static root and Docker data_v2 prefix, never server source.
            self.prefix = (
                "" if any(EMAIL_PATH.fullmatch(x.filename) for x in entries) else "data_v2/"
            )
            self.entries = {}
            total = 0
            for entry in entries:
                if not entry.filename.startswith(self.prefix):
                    continue
                name = entry.filename[len(self.prefix) :]
                if not (EMAIL_PATH.fullmatch(name) or ATTACHMENT_PATH.fullmatch(name)):
                    continue
                checked_path(name)
                if name in self.entries or stat.S_ISLNK(entry.external_attr >> 16):
                    raise DomainError(
                        "DATASET_DUPLICATE", "Archive contains duplicate entries or links"
                    )
                total += entry.file_size
                if (
                    entry.file_size > MAX_FILE
                    or total > MAX_TOTAL
                    or entry.file_size > max(entry.compress_size, 1) * 500
                ):
                    raise DomainError(
                        "DATASET_LIMIT", "Archive exceeds bounded decompression limits"
                    )
                self.entries[name] = entry
            if not any(EMAIL_PATH.fullmatch(name) for name in self.entries):
                raise DomainError("DATASET_EMPTY", "Archive contains no supported inbox")
        except Exception:
            self.archive.close()
            raise

    def read(self, name):
        entry = self.entries.get(checked_path(name))
        if entry is None:
            raise FileNotFoundError(name)
        with self.archive.open(entry) as stream:
            data = stream.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            raise DomainError("DATASET_LIMIT", "Dataset file exceeds the size limit")
        return data

    def emails(self):
        names = sorted(name for name in self.entries if EMAIL_PATH.fullmatch(name))
        if len(names) > MAX_EMAILS:
            raise DomainError("DATASET_LIMIT", "Dataset has too many emails")
        records = []
        for name in names:
            record = strict_json(self.read(name).decode("utf-8"))
            if record.get("email_id") != PurePosixPath(name).stem:
                raise DomainError("DATASET_ID_INVALID", "Email ID does not match its filename")
            records.append(record)
        return validate_records(records)

    def close(self):
        self.archive.close()


class DockerSource:
    """Local organizer service only; caller cannot fetch arbitrary network hosts."""

    def __init__(self, origin, client=None):
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise DomainError("DATASET_ORIGIN_INVALID", "Use the loopback organizer HTTP server")
        self.origin = origin.rstrip("/")
        self.client = client or httpx.Client(timeout=20, follow_redirects=False, trust_env=False)

    def _read(self, path, limit):
        with self.client.stream("GET", self.origin + path) as response:
            if response.status_code == 404:
                raise FileNotFoundError(path)
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > limit:
                    raise DomainError("DATASET_LIMIT", "Dataset response exceeds its size limit")
            return bytes(data)

    def read(self, name):
        return self._read("/" + checked_path(name), MAX_FILE)

    def emails(self):
        return validate_records(strict_json(self._read("/emails", MAX_TOTAL).decode("utf-8")))

    def close(self):
        self.client.close()


def open_source(source):
    if str(source).startswith(("http://", "https://")):
        return DockerSource(str(source))
    return ArchiveSource(source) if Path(source).is_file() else DirectorySource(source)


def build_manifest(source):
    records = source.emails()
    if not records:
        raise DomainError("DATASET_EMPTY", "Dataset contains no emails")
    files = {}
    emails = []
    total = 0
    for item in records:
        payload = item.model_dump(mode="json", by_alias=True)
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
        total += len(canonical)
        emails.append(
            {
                "email_id": item.email_id,
                "sha256": hashlib.sha256(canonical).hexdigest(),
                "attachments": list(item.attachments),
            }
        )
        for name in item.attachments:
            if name in files:
                continue
            try:
                data = source.read(name)
            except FileNotFoundError:
                files[name] = {"path": name, "state": "missing"}
                continue
            total += len(data)
            files[name] = {
                "path": name,
                "state": "available",
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "format": PurePosixPath(name).suffix[1:].lower(),
            }
            if total > MAX_TOTAL:
                raise DomainError("DATASET_LIMIT", "Dataset exceeds aggregate size limit")
        if total > MAX_TOTAL:
            raise DomainError("DATASET_LIMIT", "Dataset exceeds aggregate size limit")
    manifest = {
        "version": "input-manifest-v1",
        "emails": emails,
        "attachments": sorted(files.values(), key=lambda x: x["path"]),
    }
    digest = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        **manifest,
        "sha256": digest,
        "summary": {
            "emails": len(emails),
            "attachments": len(files),
            "missing": sum(x["state"] == "missing" for x in files.values()),
            "formats": dict(
                Counter(x["format"] for x in files.values() if x["state"] == "available")
            ),
            "input_bytes": total,
        },
    }
