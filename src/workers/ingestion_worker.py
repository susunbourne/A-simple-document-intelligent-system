import argparse
import asyncio
import logging

from src.core.config import settings
from src.core.logging import configure_logging
from src.db.database import SessionLocal
from src.services.ingestion_service import IngestionWorker


logger = logging.getLogger(__name__)


async def run_worker(*, once: bool = False) -> None:
    while True:
        with SessionLocal() as db:
            processed = await IngestionWorker(db).run_once()
        if once:
            return
        if not processed:
            await asyncio.sleep(settings.INGESTION_POLL_SECONDS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the durable document ingestion worker.")
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit.")
    args = parser.parse_args()
    configure_logging()
    try:
        asyncio.run(run_worker(once=args.once))
    except KeyboardInterrupt:
        logger.info("ingestion_worker_stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
