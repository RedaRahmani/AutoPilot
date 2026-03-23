import logging
import signal
import time

from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("autopilot.worker")

running = True


def handle_shutdown(signum: int, _frame: object) -> None:
    global running
    running = False
    logger.info("Received signal %s, shutting down worker placeholder.", signum)


def main() -> None:
    settings = get_settings()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info(
        "Worker placeholder started for %s with Postgres at %s:%s and Redis at %s:%s.",
        settings.app_env,
        settings.postgres_host,
        settings.postgres_port,
        settings.redis_host,
        settings.redis_port,
    )
    logger.info(
        "Background job processing is not implemented yet. The runtime is ready for later tickets."
    )

    while running:
        time.sleep(5)

    logger.info("Worker placeholder stopped.")


if __name__ == "__main__":
    main()
