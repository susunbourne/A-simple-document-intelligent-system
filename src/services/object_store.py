from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import tempfile
from typing import BinaryIO, Protocol

from src.core.config import settings


class SourceTooLargeError(ValueError):
    pass


class SourceObjectNotFoundError(FileNotFoundError):
    pass


@dataclass(frozen=True)
class StoredSource:
    uri: str
    sha256: str
    size_bytes: int


class DocumentSourceStore(Protocol):
    def put_stream(
        self,
        tenant_id: str,
        stream: BinaryIO,
        *,
        max_bytes: int,
        chunk_bytes: int = 1024 * 1024,
    ) -> StoredSource: ...

    def read(self, uri: str) -> bytes: ...

    def delete(self, uri: str) -> None: ...


class LocalDocumentSourceStore:
    """Content-addressed source storage used by local/dev workers.

    The URI is durable across API and worker processes as long as they share
    the configured volume. Production can replace this adapter with Blob
    Storage without changing the ingestion state machine.
    """

    URI_PREFIX = "local-source://"

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put_stream(
        self,
        tenant_id: str,
        stream: BinaryIO,
        *,
        max_bytes: int,
        chunk_bytes: int = 1024 * 1024,
    ) -> StoredSource:
        tenant_key = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:24]
        digest = hashlib.sha256()
        size = 0
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                while True:
                    block = stream.read(chunk_bytes)
                    if not block:
                        break
                    size += len(block)
                    if size > max_bytes:
                        raise SourceTooLargeError(f"Source exceeds {max_bytes} bytes.")
                    digest.update(block)
                    temporary.write(block)

            sha256 = digest.hexdigest()
            relative = Path(tenant_key) / sha256[:2] / sha256
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                temporary_path.unlink(missing_ok=True)
            else:
                os.replace(temporary_path, destination)
            return StoredSource(
                uri=f"{self.URI_PREFIX}{relative.as_posix()}",
                sha256=sha256,
                size_bytes=size,
            )
        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

    def read(self, uri: str) -> bytes:
        path = self._resolve(uri)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise SourceObjectNotFoundError(uri) from exc

    def delete(self, uri: str) -> None:
        self._resolve(uri).unlink(missing_ok=True)

    def _resolve(self, uri: str) -> Path:
        if not uri.startswith(self.URI_PREFIX):
            raise ValueError("Unsupported source URI.")
        relative = Path(uri.removeprefix(self.URI_PREFIX))
        candidate = (self.root / relative).resolve()
        if self.root not in candidate.parents:
            raise ValueError("Source URI escapes the configured storage root.")
        return candidate


class AzureBlobDocumentSourceStore:
    """Private Blob source storage authenticated with workload identity."""

    URI_PREFIX = "azure-blob://"

    def __init__(
        self,
        account_url: str,
        container: str,
        *,
        service_client=None,
        credential=None,
    ):
        if not account_url:
            raise ValueError("AZURE_BLOB_ACCOUNT_URL is required for the Azure source backend.")
        self.container = container
        if service_client is None:
            from azure.identity import DefaultAzureCredential
            from azure.storage.blob import BlobServiceClient

            service_client = BlobServiceClient(
                account_url=account_url,
                credential=credential or DefaultAzureCredential(),
            )
        self.container_client = service_client.get_container_client(container)

    def put_stream(
        self,
        tenant_id: str,
        stream: BinaryIO,
        *,
        max_bytes: int,
        chunk_bytes: int = 1024 * 1024,
    ) -> StoredSource:
        tenant_key = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:24]
        digest = hashlib.sha256()
        size = 0
        with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as buffered:
            while True:
                block = stream.read(chunk_bytes)
                if not block:
                    break
                size += len(block)
                if size > max_bytes:
                    raise SourceTooLargeError(f"Source exceeds {max_bytes} bytes.")
                digest.update(block)
                buffered.write(block)
            sha256 = digest.hexdigest()
            object_key = f"{tenant_key}/{sha256[:2]}/{sha256}"
            buffered.seek(0)
            blob = self.container_client.get_blob_client(object_key)
            try:
                blob.upload_blob(buffered, overwrite=False)
            except Exception as exc:
                if type(exc).__name__ != "ResourceExistsError":
                    raise
        return StoredSource(
            uri=f"{self.URI_PREFIX}{self.container}/{object_key}",
            sha256=sha256,
            size_bytes=size,
        )

    def read(self, uri: str) -> bytes:
        object_key = self._object_key(uri)
        try:
            return self.container_client.download_blob(object_key).readall()
        except Exception as exc:
            if type(exc).__name__ in {"ResourceNotFoundError", "BlobNotFound"}:
                raise SourceObjectNotFoundError(uri) from exc
            raise

    def delete(self, uri: str) -> None:
        self.container_client.delete_blob(self._object_key(uri), delete_snapshots="include")

    def _object_key(self, uri: str) -> str:
        expected = f"{self.URI_PREFIX}{self.container}/"
        if not uri.startswith(expected):
            raise ValueError("Source URI does not belong to the configured Blob container.")
        object_key = uri.removeprefix(expected)
        if not object_key or ".." in Path(object_key).parts:
            raise ValueError("Invalid Blob source URI.")
        return object_key


def build_document_source_store() -> DocumentSourceStore:
    backend = settings.DOCUMENT_SOURCE_BACKEND.strip().lower()
    if backend == "local":
        return LocalDocumentSourceStore(Path(settings.DOCUMENT_SOURCE_ROOT))
    if backend == "azure_blob":
        return AzureBlobDocumentSourceStore(
            settings.AZURE_BLOB_ACCOUNT_URL or "",
            settings.AZURE_BLOB_CONTAINER,
        )
    raise ValueError(f"Unsupported document source backend: {backend}")
