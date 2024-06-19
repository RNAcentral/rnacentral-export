from sqlalchemy import create_engine, func, select, Table, MetaData
from sqlalchemy.orm import sessionmaker

from .config import settings


# initialize the database connection
engine = create_engine(settings.database)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metadata = MetaData()

# fetch data from precomputed and rna tables
precomputed = Table("rnc_rna_precomputed", metadata, autoload_with=engine)
rna = Table("rna", metadata, autoload_with=engine)


def fetch_data_from_db(ids):
    with (SessionLocal() as session):
        stmt = (
            select(
                precomputed.c.id,
                precomputed.c.taxid,
                precomputed.c.description,
                precomputed.c.rna_type,
                precomputed.c.so_rna_type,
                precomputed.c.databases,
                func.coalesce(rna.c.seq_short, rna.c.seq_long).label("sequence")
            )
            .join(rna, rna.c.upi == precomputed.c.upi)
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
            "sequence"
        ]
        precomputed_data = [dict(zip(column_names, row)) for row in results]

    return precomputed_data
