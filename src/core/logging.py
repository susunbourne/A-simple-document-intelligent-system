import logging
import hashlib


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    safe_fields = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.info("%s %s", event, safe_fields)


def privacy_safe_file_id(filename: str) -> str:
    return hashlib.sha256(filename.encode("utf-8")).hexdigest()[:16]
