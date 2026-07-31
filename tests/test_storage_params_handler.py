"""Golden and contract tests for StorageParamsHandler."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from dbwarden.engine.snapshot import (
    MigrationStatement,
    StatementOrder,
    _assemble_migration,
)

from dbwarden_pgsql_extensions.handlers.storage_params_handler import StorageParamsHandler

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeTable:
    name: str = "users"
    pg_table: dict[str, Any] = field(default_factory=dict)
    pg_policies: list[dict[str, Any]] | None = None
    pg_grants: list[dict[str, Any]] | None = None
    columns: list[Any] = field(default_factory=list)


def _inline_storage_params_diff(
    snapshot: dict[str, Any],
    model_tables: list[FakeTable],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    upgrade_ops: list[dict[str, Any]] = []
    rollback_ops: list[dict[str, Any]] = []

    model_by_name = {t.name: t for t in model_tables}
    all_tables = sorted(set(model_by_name.keys()) | {t for t in snapshot.get("tables", {})})

    for tname in all_tables:
        table = model_by_name.get(tname)
        if table is None:
            continue

        snap_entry: dict[str, Any] = {}
        snap_table = snapshot.get("tables", {}).get(tname, {})
        snap_pg = snap_table.get("pg_table") or snap_table.get("backend_table_spec") or {}
        snap_params = snap_pg.get("pg_storage_params", {}) or {}
        for k, v in snap_params.items():
            snap_entry[k] = v

        model_entry: dict[str, Any] = {}
        model_params = table.pg_table.get("pg_storage_params", {}) or {}
        for k, v in model_params.items():
            model_entry[k] = v

        all_keys = set(snap_entry.keys()) | set(model_entry.keys())
        for key in sorted(all_keys):
            snap_val = snap_entry.get(key)
            model_val = model_entry.get(key)
            if snap_val != model_val:
                upgrade_ops.append({
                    "type": "alter_pg_storage_param",
                    "table": tname,
                    "param": key,
                    "to_value": model_val,
                    "from_value": snap_val,
                })
                rollback_ops.append({
                    "type": "alter_pg_storage_param",
                    "table": tname,
                    "param": key,
                    "to_value": snap_val,
                    "from_value": model_val,
                })

    return upgrade_ops, rollback_ops


def _inline_storage_params_emit(
    ops: list[dict[str, Any]],
) -> list[MigrationStatement]:
    stmts: list[MigrationStatement] = []
    for op in ops:
        param = op["param"]
        to_val = op.get("to_value")
        from_val = op.get("from_value")
        if to_val is not None:
            up = f"ALTER TABLE {op['table']} SET ({param} = {to_val});"
        else:
            up = f"ALTER TABLE {op['table']} RESET ({param});"
        if from_val is not None:
            rb = f"ALTER TABLE {op['table']} SET ({param} = {from_val});"
        else:
            rb = f"ALTER TABLE {op['table']} RESET ({param});"
        stmts.append(MigrationStatement(
            order=StatementOrder.ALTER_TABLE_OPTIONS,
            upgrade_sql=up, rollback_sql=rb,
        ))
    return stmts


def _handler_diff_sql(
    handler_cls: Any,
    snapshot: dict[str, Any],
    model_tables: list[FakeTable],
) -> tuple[str, str]:
    handler = handler_cls()
    snap_spec = handler.canonicalize(handler.extract(snapshot))
    model_spec = handler.canonicalize(handler.model_spec_from_tables(model_tables))
    up_ops, rb_ops = handler.diff(snap_spec, model_spec)
    up_stmts = sum((handler.emit(op) for op in up_ops), [])
    rb_stmts = sum((handler.emit(op) for op in rb_ops), [])
    up_sql, rb_sql = _assemble_migration(up_stmts + rb_stmts)
    return up_sql, rb_sql


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

EMPTY_SNAPSHOT: dict[str, Any] = {"tables": {}}

SNAPSHOT_STORAGE = {
    "tables": {
        "users": {
            "pg_table": {
                "pg_storage_params": {
                    "fillfactor": 90,
                },
            },
        },
        "orders": {
            "pg_table": {
                "pg_storage_params": {
                    "autovacuum_enabled": "off",
                    "fillfactor": 100,
                },
            },
        },
    },
}

# model has one param added, one param changed, one param removed
MODEL_STORAGE_CHANGED = [
    FakeTable(
        name="users",
        pg_table={
            "pg_storage_params": {
                "fillfactor": 95,
                "toast_tuple_target": 128,
            },
        },
    ),
    FakeTable(
        name="orders",
        pg_table={
            "pg_storage_params": {
                "fillfactor": 100,
            },
        },
    ),
]

MODEL_STORAGE_NO_STORAGE = [
    FakeTable(name="users", pg_table={}),
    FakeTable(name="orders", pg_table={}),
]

MODEL_STORAGE_NEW_TABLE = [
    FakeTable(
        name="users",
        pg_table={
            "pg_storage_params": {
                "fillfactor": 90,
            },
        },
    ),
    FakeTable(
        name="audit_log",
        pg_table={
            "pg_storage_params": {
                "fillfactor": 75,
            },
        },
    ),
]


# ===================================================================
# Golden byte-equivalence tests: StorageParamsHandler
# ===================================================================

class TestStorageParamsHandlerGolden:
    HANDLER_CLS = StorageParamsHandler

    @pytest.mark.parametrize(
        "snapshot,model_tables,label",
        [
            (EMPTY_SNAPSHOT, [], "empty"),
            (SNAPSHOT_STORAGE, MODEL_STORAGE_CHANGED, "add_change_remove"),
            (SNAPSHOT_STORAGE, MODEL_STORAGE_NO_STORAGE, "remove_all"),
            (EMPTY_SNAPSHOT, MODEL_STORAGE_NEW_TABLE, "new_table"),
            (SNAPSHOT_STORAGE, [
                FakeTable(name="users", pg_table={"pg_storage_params": {"fillfactor": 90}}),
                FakeTable(name="orders", pg_table={"pg_storage_params": {"autovacuum_enabled": "off", "fillfactor": 100}}),
            ], "unchanged"),
        ],
    )
    def test_sql_byte_equivalence(
        self,
        snapshot: dict[str, Any],
        model_tables: list[FakeTable],
        label: str,
    ) -> None:
        inline_up_ops, inline_rb_ops = _inline_storage_params_diff(snapshot, model_tables)
        inline_stmts = _inline_storage_params_emit(inline_up_ops) + _inline_storage_params_emit(inline_rb_ops)
        inline_up_sql, inline_rb_sql = _assemble_migration(inline_stmts)

        handler_up_sql, handler_rb_sql = _handler_diff_sql(
            self.HANDLER_CLS, snapshot, model_tables
        )

        assert handler_up_sql == inline_up_sql, (
            f"Upgrade SQL mismatch for {label}\n"
            f"  inline:  {inline_up_sql!r}\n"
            f"  handler: {handler_up_sql!r}"
        )
        assert handler_rb_sql == inline_rb_sql, (
            f"Rollback SQL mismatch for {label}\n"
            f"  inline:  {inline_rb_sql!r}\n"
            f"  handler: {handler_rb_sql!r}"
        )


# ===================================================================
# Contract tests: StorageParamsHandler
# ===================================================================

class TestStorageParamsHandlerContract:
    HANDLER = StorageParamsHandler()

    def test_canonical_idempotent(self) -> None:
        spec = {"users": {"fillfactor": 90}}
        c1 = self.HANDLER.canonicalize(spec)
        c2 = self.HANDLER.canonicalize(c1)
        assert c1 == c2

    def test_canonical_empty(self) -> None:
        assert self.HANDLER.canonicalize({}) == {}
        assert self.HANDLER.canonicalize(None) == {}

    def test_unchanged_produces_empty_diff(self) -> None:
        snap = self.HANDLER.canonicalize(self.HANDLER.extract(SNAPSHOT_STORAGE))
        model = self.HANDLER.canonicalize(self.HANDLER.model_spec_from_tables([
            FakeTable(name="users", pg_table={"pg_storage_params": {"fillfactor": 90}}),
            FakeTable(name="orders", pg_table={"pg_storage_params": {"autovacuum_enabled": "off", "fillfactor": 100}}),
        ]))
        up, rb = self.HANDLER.diff(snap, model)
        assert up == []
        assert rb == []

    def test_add_param(self) -> None:
        snap = self.HANDLER.canonicalize(self.HANDLER.extract(SNAPSHOT_STORAGE))
        model = self.HANDLER.canonicalize(self.HANDLER.model_spec_from_tables([
            FakeTable(name="users", pg_table={"pg_storage_params": {"fillfactor": 90, "toast_tuple_target": 128}}),
            FakeTable(name="orders", pg_table={"pg_storage_params": {"autovacuum_enabled": "off", "fillfactor": 100}}),
        ]))
        up, rb = self.HANDLER.diff(snap, model)
        assert len(up) == 1
        assert up[0].object_type == "alter_pg_storage_param"
        assert up[0].upgrade_attrs["param"] == "toast_tuple_target"
        assert up[0].upgrade_attrs["to_value"] == 128

    def test_drop_param(self) -> None:
        snap = self.HANDLER.canonicalize(self.HANDLER.extract(SNAPSHOT_STORAGE))
        model = self.HANDLER.canonicalize(self.HANDLER.model_spec_from_tables([
            FakeTable(name="users", pg_table={"pg_storage_params": {}}),
            FakeTable(name="orders", pg_table={"pg_storage_params": {"autovacuum_enabled": "off", "fillfactor": 100}}),
        ]))
        up, _ = self.HANDLER.diff(snap, model)
        assert len(up) == 1
        up_keys = {op.upgrade_attrs["param"] for op in up}
        assert "fillfactor" in up_keys

    def test_emit_reset_when_value_none(self) -> None:
        from dbwarden.engine.core.protocol import Op
        op = Op(
            object_type="alter_pg_storage_param",
            upgrade_attrs={"table": "users", "param": "fillfactor", "to_value": None},
            rollback_attrs={},
        )
        stmts = self.HANDLER.emit(op)
        assert "RESET" in stmts[0].upgrade_sql
