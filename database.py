from typing import Generator
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import settings

conn_str_eclipse = (
    f"Driver={{ODBC Driver 18 for SQL Server}};"
    f"Server={settings.eclipse_host};"
    f"DATABASE={settings.eclipse_database};"
    f"UID={settings.eclipse_user};"
    f"PWD={settings.eclipse_password};"
    f"TrustServerCertificate=yes;"
)

encoded_eclipse_str = quote_plus(conn_str_eclipse)
ECLIPSE_DATABASE_URL = f"mssql+pyodbc:///?odbc_connect={encoded_eclipse_str}"

engine_eclipse = create_engine(
    ECLIPSE_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionEclipse = sessionmaker(
    autocommit=False, autoflush=False, bind=engine_eclipse
)

POSTGRES_DATABASE_URL = (
    f"postgresql+psycopg://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_database}"
)

engine_postgres = create_engine(
    POSTGRES_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionPostgres = sessionmaker(
    autocommit=False, autoflush=False, bind=engine_postgres
)

def get_eclipse_db() -> Generator[Session, None, None]:
    db = SessionEclipse()
    try:
        yield db
    finally:
        db.close()


def get_postgres_db() -> Generator[Session, None, None]:
    db = SessionPostgres()
    try:
        yield db
    finally:
        db.close()