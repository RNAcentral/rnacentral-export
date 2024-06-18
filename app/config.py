from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"
    database: str = "postgresql://reader:NWDMCE5xdipIjRrp@hh-pgsql-public.ebi.ac.uk:5432/pfmegrnargs"

    class Config:
        env_file = ".env"


settings = Settings()
