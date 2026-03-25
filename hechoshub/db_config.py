import os
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse


ENGINE_ALIASES = {
    "sqlite": "django.db.backends.sqlite3",
    "postgres": "django.db.backends.postgresql",
    "postgresql": "django.db.backends.postgresql",
    "mysql": "django.db.backends.mysql",
}


def _sqlite_config(base_dir: Path, database_name: Optional[str] = None) -> dict:
    sqlite_name = database_name or os.getenv("DB_SQLITE_NAME") or "db.sqlite3"
    database_path = Path(sqlite_name)
    if not database_path.is_absolute():
        database_path = base_dir / database_path

    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": database_path,
    }


def _url_to_db_config(base_dir: Path, database_url: str) -> dict:
    parsed = urlparse(database_url)
    scheme = (parsed.scheme or "").lower()
    query_params = {key: values[-1] for key, values in parse_qs(parsed.query).items() if values}

    if scheme not in ENGINE_ALIASES:
        raise ValueError(f"Motor de base de datos no soportado en DATABASE_URL: {scheme}")

    if scheme == "sqlite":
        database_name = unquote(parsed.path or "").lstrip("/")
        return _sqlite_config(base_dir, database_name or None)

    config = {
        "ENGINE": ENGINE_ALIASES[scheme],
        "NAME": unquote((parsed.path or "").lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "localhost",
        "PORT": str(parsed.port or ""),
    }

    if query_params:
        config["OPTIONS"] = query_params

    return config


def get_database_config(base_dir: Path) -> dict:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return _url_to_db_config(base_dir, database_url)

    selected_engine = (os.getenv("DB_ENGINE") or "sqlite").lower()
    if selected_engine == "sqlite":
        return _sqlite_config(base_dir, os.getenv("DB_NAME"))

    if selected_engine not in ENGINE_ALIASES:
        raise ValueError(f"DB_ENGINE no soportado: {selected_engine}")

    return {
        "ENGINE": ENGINE_ALIASES[selected_engine],
        "NAME": os.getenv("DB_NAME", ""),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", ""),
    }
