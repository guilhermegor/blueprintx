# **FAQ**

Answers to common questions about running and developing this service. Add project-specific
entries as they come up.

> **See also:** [Usage](usage.md) · [Examples](examples.md) · [Contributing](contributing.md).

---

## How do I run it locally?

`make init` then `make run` (or `bash tasks.sh init` / `bash tasks.sh run`). See [Usage](usage.md).

## How do I add or update a dependency?

Use Poetry so the lock file stays authoritative:

```bash
poetry add <package>               # runtime dependency
poetry add --group dev <package>   # dev-only tool
```

Every package the code imports must be a **direct** dependency — never rely on it arriving
transitively through another package.

## Which database backends are supported?

The connection factory supports the common backends (SQLite, PostgreSQL, MariaDB/MySQL, SQL
Server, Oracle); only the driver for the configured `DB_BACKEND` needs to be installed. See
[Architecture](architecture.md).

## Where do secrets go?

In `.env` (git-ignored), never in source or committed config. `.env.example` lists the keys.
