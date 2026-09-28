from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    eclipse_host: str = Field(alias="ECLIPSE_HOST")
    eclipse_user: str = Field(alias="ECLIPSE_USER")
    eclipse_password: str = Field(alias="ECLIPSE_PASSWORD")
    eclipse_database: str = Field(alias='ECLIPSE_NAME')

    postgres_host: str = Field(alias="DB_HOST")
    postgres_user: str = Field(alias="DB_USER")
    postgres_password: str = Field(alias="DB_PASSWORD")
    postgres_database: str = Field(alias='DB_NAME')
    postgres_port: str = Field(alias='DB_PORT')

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()