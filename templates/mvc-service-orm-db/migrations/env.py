"""Alembic environment configuration.

Builds the connection URL through the SAME seam the application uses
(``config.connection_db.build_database_url``) rather than re-deriving the DSN-composition
logic here — the seam already knows every supported backend (sqlite/postgresql/mariadb/
mysql/mssql/oracle) and DB_DSN precedence; duplicating it in two places is exactly the drift
this template's CLAUDE.md warns against ("the seam knows the vendor; the callers do not").
"""

from __future__ import annotations

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from config.connection_db import build_database_url

# Every entity module must import THIS Base (see src/model/CLAUDE.md's "Adding a new model
# entity" convention: "inherit from a shared Base") so autogenerate sees the full schema
# through one metadata object — a second `class Base(DeclarativeBase)` elsewhere would give
# Alembic a metadata object with no models registered on it.
from model.example_entity import Base


load_dotenv(override=True)

# ─── ALEMBIC CONFIG ───────────────────────────────────────────────────────────

config = context.config
# Escape % for ConfigParser (alembic.ini interpolation) — mirrors ddd-service-orm-db's env.py.
config.set_main_option("sqlalchemy.url", build_database_url().replace("%", "%%"))

target_metadata = Base.metadata


# ─── OFFLINE MIGRATIONS ───────────────────────────────────────────────────────

def run_migrations_offline() -> None:
	"""Run migrations in 'offline' mode (no live DB connection required).

	Generates SQL scripts that can be reviewed and applied manually.
	"""
	url = config.get_main_option("sqlalchemy.url")
	# A batch_alter_table migration still cannot run here without copy_from — the
	# constraint is the migration's, not this config's. See migrations/CLAUDE.md rule 5.
	context.configure(
		url=url,
		target_metadata=target_metadata,
		literal_binds=True,
		dialect_opts={"paramstyle": "named"},
		compare_type=True,
		render_as_batch=True,
	)
	with context.begin_transaction():
		context.run_migrations()


# ─── ONLINE MIGRATIONS ────────────────────────────────────────────────────────

def run_migrations_online() -> None:
	"""Run migrations against a live database connection."""
	connectable = engine_from_config(
		config.get_section(config.config_ini_section, {}),
		prefix="sqlalchemy.",
		poolclass=pool.NullPool,
	)

	with connectable.connect() as connection:
		context.configure(
			connection=connection,
			target_metadata=target_metadata,
			compare_type=True,
			render_as_batch=True,
		)
		with context.begin_transaction():
			context.run_migrations()


if context.is_offline_mode():
	run_migrations_offline()
else:
	run_migrations_online()
