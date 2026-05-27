"""Alembic environment configuration.

Reads DB_SCHEMA (default 'public') and sets the PostgreSQL search_path so all
migrations run inside the correct schema. For non-PostgreSQL backends the
search_path override is skipped.
"""

from __future__ import annotations

import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import URL, engine_from_config, pool

# Register ORM models so Base.metadata reflects the full schema
from chassis.db_schema.infrastructure import Base
from chassis.db_schema.infrastructure import models as _models  # noqa: F401


load_dotenv(override=True)

# ─── READ RUNTIME CONFIG ──────────────────────────────────────────────────────

_DB_SCHEMA: str = os.getenv("DB_SCHEMA", "public")

_DB_BACKEND: str = os.getenv("DB_BACKEND", "sqlite").lower()
_DB_USER: str = os.getenv("DB_USER", "")
_DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
_DB_HOST: str = os.getenv("DB_HOST", "localhost")
_DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
_DB_NAME: str = os.getenv("DB_NAME", "app")

_DRIVER_MAP: dict[str, str] = {
	"postgresql": "postgresql+psycopg",
	"mariadb": "mysql+pymysql",
	"mysql": "mysql+pymysql",
	"mssql": "mssql+pyodbc",
	"oracle": "oracle+oracledb",
	"sqlite": "sqlite",
}

_DSN: str = os.getenv("DB_DSN", "")

if _DSN:
	# Escape % for ConfigParser (alembic.ini interpolation)
	_DSN = _DSN.replace("%", "%%")
elif _DB_BACKEND == "sqlite":
	_DSN = f"sqlite:///{os.getenv('DB_PATH', './data/app.db')}"
else:
	_str_driver = _DRIVER_MAP.get(_DB_BACKEND, "postgresql+psycopg")
	_url_obj = URL.create(
		drivername=_str_driver,
		username=_DB_USER,
		password=_DB_PASSWORD,
		host=_DB_HOST,
		port=_DB_PORT,
		database=_DB_NAME,
	)
	_DSN = str(_url_obj).replace("%", "%%")

# ─── ALEMBIC CONFIG ───────────────────────────────────────────────────────────

config = context.config
config.set_main_option("sqlalchemy.url", _DSN)

target_metadata = Base.metadata


# ─── OFFLINE MIGRATIONS ───────────────────────────────────────────────────────

def run_migrations_offline() -> None:
	"""Run migrations in 'offline' mode (no live DB connection required).

	Generates SQL scripts that can be reviewed and applied manually.
	"""
	url = config.get_main_option("sqlalchemy.url")
	context.configure(
		url=url,
		target_metadata=target_metadata,
		literal_binds=True,
		dialect_opts={"paramstyle": "named"},
	)
	with context.begin_transaction():
		context.run_migrations()


# ─── ONLINE MIGRATIONS ────────────────────────────────────────────────────────

def run_migrations_online() -> None:
	"""Run migrations against a live database connection.

	Sets the PostgreSQL search_path to DB_SCHEMA so all DDL is issued inside
	the correct schema. For non-PostgreSQL backends the search_path override is
	skipped.

	TODO — Contribution point:
	    Decide how to handle the case when DB_SCHEMA is absent in your project:
	    - Current default: fall back to 'public' (safe for local dev and SQLite).
	    - Alternative: raise ValueError so misconfigured environments fail fast.
	    Also consider: should the schema be auto-created here, or rely on
	    db_setup_schema.sh to create it before migrations run?
	"""
	connectable = engine_from_config(
		config.get_section(config.config_ini_section, {}),
		prefix="sqlalchemy.",
		poolclass=pool.NullPool,
	)

	with connectable.connect() as connection:
		if "postgresql" in (connectable.dialect.name or ""):
			connection.execute(
				__import__("sqlalchemy").text(
					f"SET search_path TO {_DB_SCHEMA}"
				)
			)

		context.configure(
			connection=connection,
			target_metadata=target_metadata,
			version_table_schema=_DB_SCHEMA,
		)
		with context.begin_transaction():
			context.run_migrations()


if context.is_offline_mode():
	run_migrations_offline()
else:
	run_migrations_online()
