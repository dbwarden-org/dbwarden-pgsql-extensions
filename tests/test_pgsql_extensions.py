"""Tests for the pg_extension object handler."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from dbwarden.engine.core import Anchor, Op, RunPhase

from dbwarden_pgsql_extensions import PgExtensionHandler


@pytest.fixture
def handler() -> PgExtensionHandler:
    # Registration is what resolves the ordering anchors into statement_order,
    # which emit() reads; do the same here so the handler is fully formed.
    from dbwarden.engine.core.ordering import apply_public_ordering

    instance = PgExtensionHandler()
    apply_public_ordering(instance)
    return instance


def _diff(handler: PgExtensionHandler, snapshot_names, config_names):
    snap = handler.canonicalize(handler.extract({"pg_extensions": list(snapshot_names)}))
    model = handler.canonicalize(
        handler.model_spec_from_config(SimpleNamespace(pg_extensions=list(config_names)))
    )
    return handler.diff(snap, model)


class TestHandlerShape:
    def test_runs_in_the_preamble_before_tables(self, handler: PgExtensionHandler) -> None:
        assert handler.object_type == "pg_extension"
        assert handler.run_phase == RunPhase.PREAMBLE
        assert Anchor.PREAMBLE in handler.ordering.after
        assert Anchor.BEFORE_TABLES in handler.ordering.before

    def test_extract_accepts_a_list_of_names(self, handler: PgExtensionHandler) -> None:
        assert handler.extract({"pg_extensions": ["postgis"]}) == {"postgis": {}}

    def test_extract_accepts_a_mapping(self, handler: PgExtensionHandler) -> None:
        assert handler.extract({"pg_extensions": {"postgis": {"version": "3.4"}}}) == {
            "postgis": {"version": "3.4"}
        }

    def test_extract_falls_back_to_the_extensions_key(self, handler: PgExtensionHandler) -> None:
        assert handler.extract({"extensions": ["hstore"]}) == {"hstore": {}}

    def test_extract_of_an_empty_snapshot_is_empty(self, handler: PgExtensionHandler) -> None:
        assert handler.extract({}) == {}

    def test_canonicalize_lowercases_names(self, handler: PgExtensionHandler) -> None:
        assert handler.canonicalize({"PostGIS": {}}) == {"postgis": {}}

    def test_model_spec_from_tables_is_empty(self, handler: PgExtensionHandler) -> None:
        assert handler.model_spec_from_tables([]) == {}

    def test_model_spec_without_config_is_empty(self, handler: PgExtensionHandler) -> None:
        assert handler.model_spec_from_config(SimpleNamespace()) == {}


class TestDiff:
    def test_extension_added_to_config_is_created(self, handler: PgExtensionHandler) -> None:
        upgrade, rollback = _diff(handler, [], ["postgis"])
        assert [op.object_type for op in upgrade] == ["create_pg_extension"]
        assert [op.object_type for op in rollback] == ["drop_pg_extension"]

    def test_extension_removed_from_config_is_dropped(self, handler: PgExtensionHandler) -> None:
        upgrade, rollback = _diff(handler, ["postgis"], [])
        assert [op.object_type for op in upgrade] == ["drop_pg_extension"]
        assert [op.object_type for op in rollback] == ["create_pg_extension"]

    def test_unchanged_extension_produces_no_ops(self, handler: PgExtensionHandler) -> None:
        upgrade, rollback = _diff(handler, ["postgis"], ["postgis"])
        assert upgrade == []
        assert rollback == []

    def test_ops_are_emitted_in_sorted_name_order(self, handler: PgExtensionHandler) -> None:
        upgrade, _ = _diff(handler, [], ["postgis", "hstore"])
        assert [op.upgrade_attrs["name"] for op in upgrade] == ["hstore", "postgis"]


class TestEmit:
    def test_create_is_idempotent_and_reverses_to_a_drop(self, handler: PgExtensionHandler) -> None:
        upgrade, _ = _diff(handler, [], ["postgis"])
        statement = handler.emit(upgrade[0])[0]
        assert statement.upgrade_sql == 'CREATE EXTENSION IF NOT EXISTS "postgis";'
        assert statement.rollback_sql == 'DROP EXTENSION IF EXISTS "postgis";'

    def test_drop_is_idempotent_and_reverses_to_a_create(self, handler: PgExtensionHandler) -> None:
        upgrade, _ = _diff(handler, ["postgis"], [])
        statement = handler.emit(upgrade[0])[0]
        assert statement.upgrade_sql == 'DROP EXTENSION IF EXISTS "postgis";'
        assert statement.rollback_sql == 'CREATE EXTENSION IF NOT EXISTS "postgis";'

    def test_identifiers_with_quotes_are_escaped(self, handler: PgExtensionHandler) -> None:
        upgrade, _ = _diff(handler, [], ['we"ird'])
        statement = handler.emit(upgrade[0])[0]
        assert statement.upgrade_sql == 'CREATE EXTENSION IF NOT EXISTS "we""ird";'

    def test_unknown_op_type_emits_nothing(self, handler: PgExtensionHandler) -> None:
        assert handler.emit(Op("alter_pg_extension", {"name": "postgis"}, {})) == []
