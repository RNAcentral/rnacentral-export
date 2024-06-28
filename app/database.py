from typing import List, Dict, Any
from sqlalchemy import create_engine, func, MetaData, Table, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .config import get_settings
from .logger import logger

# synchronous database connection
settings = get_settings()
engine: Engine = create_engine(settings.database)
metadata: MetaData = MetaData()


def fetch_data_from_db(ids: List[str]) -> List[Dict[str, Any]]:
    try:
        with Session(engine) as session:
            precomputed: Table = Table(
                "rnc_rna_precomputed",
                metadata,
                autoload_with=session.bind
            )
            rna: Table = Table(
                "rna",
                metadata,
                autoload_with=session.bind
            )
            r2dt_results: Table = Table(
                "r2dt_results",
                metadata,
                autoload_with=session.bind
            )

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
            results = session.execute(stmt).fetchall()
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
            precomputed_data = [dict(zip(column_names, row)) for row in results]
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

    return precomputed_data
