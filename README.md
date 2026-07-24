# dbwarden-pgsql-extensions

PostgreSQL extension management for [DBWarden](https://github.com/dbwarden-org/dbwarden).

Declare extensions in `database_config(pg_extensions=[...])` and this plugin emits `CREATE EXTENSION` / `DROP EXTENSION` in the migration preamble, before any table that depends on them.

## Object type

| Object type | Manages |
|---|---|
| `pg_extension` | `CREATE EXTENSION IF NOT EXISTS` / `DROP EXTENSION IF EXISTS` |

The handler runs in `RunPhase.PREAMBLE`, anchored after `PREAMBLE` and before `BEFORE_TABLES`, so extension-provided types are available by the time tables are created. Both directions are idempotent and reversible.

## Usage

```python
from dbwarden import database_config

database_config(
    database_name="primary",
    database_type="postgresql",
    database_url_sync="postgresql://...",
    pg_extensions=["postgis", "hstore"],
)
```

## Installation

```bash
dbwarden plugin add dbwarden-pgsql-extensions
```

## Trust tier

This is an **official** DBWarden plugin. Its distribution name is classified before any of its code is imported, and `dbwarden plugin add` verifies the PyPI Trusted-Publishing attestation (PEP 740) against `dbwarden-org/dbwarden-pgsql-extensions` before installing. It loads automatically once installed, with no `dbwarden plugin trust` step.

## Development

```bash
uv venv && uv pip install -e . -e ../dbwarden pytest
pytest -q
```

The `tests/test_conformance.py` suite runs DBWarden's shared conformance harness (`dbwarden.plugin_conformance`): entry point resolution, no import-time side effects, hook signatures, public-API-only imports, and idempotent `setup()`.

## License

MIT
