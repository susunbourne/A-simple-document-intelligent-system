import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from src.core.config import settings
from src.db.database import SessionLocal
from src.repositories.ingestion_repository import IngestionRepository
from src.services.object_store import build_document_source_store


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".png", ".jpg"}


def build_source_version_key(relative_path: str, source_sha256: str) -> str:
    identity = f"directory-v1\0{relative_path.replace('\\', '/').lower()}\0{source_sha256}"
    return f"directory-{hashlib.sha256(identity.encode('utf-8')).hexdigest()}"


def iter_source_files(root: Path, max_files: int):
    count = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if count >= max_files:
            break
        count += 1
        yield path


def enqueue_directory(root: Path, workspace: str, max_files: int) -> dict[str, int]:
    resolved_root = root.resolve(strict=True)
    if not resolved_root.is_dir():
        raise ValueError(f"Source root is not a directory: {resolved_root}")

    counts = {"discovered": 0, "created": 0, "already_present": 0, "failed": 0}
    store = build_document_source_store()
    with SessionLocal() as db:
        repository = IngestionRepository(db)
        for path in iter_source_files(resolved_root, max_files):
            counts["discovered"] += 1
            try:
                relative_path = path.relative_to(resolved_root).as_posix()
                with path.open("rb") as stream:
                    source = store.put_stream(
                        workspace,
                        stream,
                        max_bytes=settings.MAX_UPLOAD_BYTES,
                    )
                job, created = repository.enqueue(
                    tenant_id=workspace,
                    idempotency_key=build_source_version_key(relative_path, source.sha256),
                    request_id=str(uuid4()),
                    filename=path.name,
                    source=source,
                    max_attempts=settings.INGESTION_MAX_ATTEMPTS,
                )
                counts["created" if created else "already_present"] += 1
            except Exception:
                db.rollback()
                counts["failed"] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Incrementally enqueue a directory into the durable ingestion queue."
    )
    parser.add_argument("root", type=Path)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--max-files", type=int, default=10_000)
    args = parser.parse_args()
    if args.max_files < 1:
        parser.error("--max-files must be positive")
    print(json.dumps(enqueue_directory(args.root, args.workspace, args.max_files), indent=2))


if __name__ == "__main__":
    main()
