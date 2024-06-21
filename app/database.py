from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection, create_async_engine
from sqlalchemy.future import select
from sqlalchemy import func, MetaData, Table

from .config import settings

# asynchronous database connection
engine: AsyncEngine = create_async_engine(
    settings.database,
    echo=True,
    future=True
)
metadata: MetaData = MetaData()


async def load_tables(conn: AsyncConnection) -> tuple[Table, Table, Table]:
    precomputed: Table = await conn.run_sync(
        lambda sync_conn: Table(
            "rnc_rna_precomputed",
            metadata,
            autoload_with=sync_conn)
    )
    rna: Table = await conn.run_sync(
        lambda sync_conn: Table("rna", metadata, autoload_with=sync_conn)
    )
    r2dt_results: Table = await conn.run_sync(
        lambda sync_conn: Table(
            "r2dt_results",
            metadata,
            autoload_with=sync_conn)
    )
    return precomputed, rna, r2dt_results


async def fetch_data_from_db(ids: List[str]) -> List[Dict[str, Any]]:
    async with engine.connect() as conn:
        precomputed, rna, r2dt_results = await load_tables(conn)
        stmt = (
            select(
                precomputed.c.id,
                precomputed.c.taxid,
                precomputed.c.description,
                precomputed.c.rna_type,
                precomputed.c.so_rna_type,
                precomputed.c.databases,
                r2dt_results.c.secondary_structure,
                func.coalesce(rna.c.seq_short, rna.c.seq_long).label("sequence")
            )
            .join(rna, rna.c.upi == precomputed.c.upi)
            .join(r2dt_results, r2dt_results.c.urs == precomputed.c.upi)
            .where(precomputed.c.id.in_(ids))
        )
        results = await conn.execute(stmt)
        rows = results.fetchall()
        column_names = [
            "rnacentral_id",
            "taxid",
            "description",
            "rna_type",
            "so_rna_type",
            "databases",
            "secondary_structure",
            "sequence"
        ]
        precomputed_data = [dict(zip(column_names, row)) for row in rows]

    return precomputed_data
