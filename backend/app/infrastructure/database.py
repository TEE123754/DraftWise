from contextlib import asynccontextmanager

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import Settings
from app.domain.errors import DomainError


class Database:
    def __init__(self, settings: Settings, max_size: int = 5):
        self.pool = (
            AsyncConnectionPool(
                settings.database_url.get_secret_value(),
                min_size=1,
                max_size=max_size,
                open=False,
                kwargs={
                    "row_factory": dict_row,
                    "connect_timeout": 15,
                    "options": "-c statement_timeout=15000",
                },
            )
            if settings.database_url
            else None
        )

    async def open(self):
        if self.pool:
            await self.pool.open(wait=True, timeout=20)

    async def close(self):
        if self.pool:
            await self.pool.close()

    @asynccontextmanager
    async def connection(self):
        if not self.pool:
            raise DomainError(
                "DATABASE_UNAVAILABLE",
                "Configure the application database",
                retryable=True,
                status=503,
            )
        async with self.pool.connection() as connection:
            async with connection.transaction():
                yield connection
