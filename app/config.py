from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"
    database: str = "postgresql+asyncpg://reader:NWDMCE5xdipIjRrp@hh-pgsql-public.ebi.ac.uk:5432/pfmegrnargs"
    dev: bool = False
    esl_binary: str = "/srv/local/infernal-1.1.5/bin/esl-sfetch"
    fasta: str = "/srv/rnacentral-export/app/examples.fasta"

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()
