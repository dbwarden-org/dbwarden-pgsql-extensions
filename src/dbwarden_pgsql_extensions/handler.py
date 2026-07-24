from __future__ import annotations

from typing import Any

from dbwarden.engine.core import Anchor, MigrationStatement, Op, OrderingConstraint, RunPhase


class PgExtensionHandler:
    object_type = "pg_extension"
    op_types = ("create_pg_extension", "drop_pg_extension")
    run_phase = RunPhase.PREAMBLE
    ordering = OrderingConstraint(after=(Anchor.PREAMBLE,), before=(Anchor.BEFORE_TABLES,))

    def extract(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        raw = snapshot.get("pg_extensions") or snapshot.get("extensions") or {}
        if isinstance(raw, dict):
            return {str(name): dict(value or {}) for name, value in raw.items()}
        return {str(name): {} for name in raw}

    def model_spec_from_config(self, config: Any) -> dict[str, Any]:
        raw = getattr(config, "pg_extensions", None) or []
        return {str(name): {} for name in raw}

    def model_spec_from_tables(self, model_tables: list[Any]) -> dict[str, Any]:
        return {}

    def canonicalize(self, spec: dict[str, Any]) -> dict[str, Any]:
        return {str(name).lower(): dict(value or {}) for name, value in sorted((spec or {}).items())}

    def diff(self, snap_spec: dict[str, Any], model_spec: dict[str, Any]):
        upgrade_ops: list[Op] = []
        rollback_ops: list[Op] = []

        snap = snap_spec or {}
        model = model_spec or {}
        for name in sorted(set(model) - set(snap)):
            attrs = {"name": name}
            upgrade_ops.append(Op("create_pg_extension", attrs, attrs))
            rollback_ops.insert(0, Op("drop_pg_extension", attrs, attrs))
        for name in sorted(set(snap) - set(model)):
            attrs = {"name": name}
            upgrade_ops.append(Op("drop_pg_extension", attrs, attrs))
            rollback_ops.insert(0, Op("create_pg_extension", attrs, attrs))

        return upgrade_ops, rollback_ops

    def emit(self, op: Op, db_name: str | None = None, **kwargs: Any) -> list[MigrationStatement]:
        name = _quote_identifier(str(op.upgrade_attrs["name"]))
        if op.object_type == "create_pg_extension":
            return [
                MigrationStatement(
                    order=self.statement_order,
                    upgrade_sql=f"CREATE EXTENSION IF NOT EXISTS {name};",
                    rollback_sql=f"DROP EXTENSION IF EXISTS {name};",
                )
            ]
        if op.object_type == "drop_pg_extension":
            return [
                MigrationStatement(
                    order=self.statement_order,
                    upgrade_sql=f"DROP EXTENSION IF EXISTS {name};",
                    rollback_sql=f"CREATE EXTENSION IF NOT EXISTS {name};",
                )
            ]
        return []


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
