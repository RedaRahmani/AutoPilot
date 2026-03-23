import socket
import time
from urllib.parse import urlparse

import psycopg

from app.core.config import get_settings


def normalize_postgres_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def wait_for_postgres(database_url: str, timeout: int, interval: int) -> None:
    conninfo = normalize_postgres_url(database_url)
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            with psycopg.connect(conninfo, connect_timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            print("Postgres is ready.", flush=True)
            return
        except psycopg.Error as exc:
            last_error = exc
            print(f"Waiting for Postgres: {exc}", flush=True)
            time.sleep(interval)

    raise SystemExit(
        f"Timed out after {timeout}s waiting for Postgres. Last error: {last_error}"
    )


def wait_for_redis(redis_url: str, timeout: int, interval: int) -> None:
    parsed = urlparse(redis_url)
    host = parsed.hostname or "redis"
    port = parsed.port or 6379
    deadline = time.monotonic() + timeout
    last_error: OSError | None = None

    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"Redis is ready at {host}:{port}.", flush=True)
                return
        except OSError as exc:
            last_error = exc
            print(f"Waiting for Redis at {host}:{port}: {exc}", flush=True)
            time.sleep(interval)

    raise SystemExit(
        f"Timed out after {timeout}s waiting for Redis at {host}:{port}. Last error: {last_error}"
    )


def main() -> None:
    settings = get_settings()
    wait_for_postgres(
        settings.resolved_database_url,
        settings.service_wait_timeout,
        settings.service_wait_interval,
    )
    wait_for_redis(
        settings.resolved_redis_url,
        settings.service_wait_timeout,
        settings.service_wait_interval,
    )


if __name__ == "__main__":
    main()
