from collections.abc import Iterator
from contextlib import contextmanager

from psycopg2.extensions import connection as PgConnection


@contextmanager
def transaction_scope(
    connection: PgConnection,
) -> Iterator[PgConnection]:
    """
    Own a PostgreSQL transaction for one application-level unit of work.

    The caller decides which operations belong inside the transaction.
    On success the transaction is committed. On failure the transaction
    is rolled back and the original exception is re-raised.
    """

    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
