"""How these handlers participate in the migration pipeline.

Object handlers reach real migrations through two different paths, and the split
is easy to get wrong in core without any single plugin noticing:

* ``RunPhase.PREAMBLE`` handlers diff against the **config** and are emitted by
  make_migrations' preamble step.
* ``RunPhase.DIFF`` handlers diff against the **models** and run inside
  ``diff_models_against_snapshot``.

The model diff has no config, so running a PREAMBLE handler there would compare
live objects against an empty spec and emit spurious drops. These tests pin that
boundary from the plugin's side.
"""

from __future__ import annotations

import pytest

from dbwarden.engine.core import RunPhase
from dbwarden.engine.snapshot import diff_models_against_snapshot

import dbwarden_pgsql_extensions

EMPTY_SNAPSHOT = {"tables": {}, "enums": {}, "indexes": {}, "constraints": {}}


@pytest.mark.parametrize("handler_class", dbwarden_pgsql_extensions.HANDLER_CLASSES)
def test_handler_declares_a_run_phase(handler_class) -> None:
    assert handler_class.run_phase in (RunPhase.PREAMBLE, RunPhase.DIFF)


def test_preamble_handlers_emit_nothing_in_the_model_diff() -> None:
    """A PREAMBLE handler must not drop everything when config is absent."""
    preamble_types = {
        handler_class.object_type
        for handler_class in dbwarden_pgsql_extensions.HANDLER_CLASSES
        if handler_class.run_phase == RunPhase.PREAMBLE
    }
    if not preamble_types:
        pytest.skip("no PREAMBLE handlers in this plugin")

    upgrade_ops, rollback_ops = diff_models_against_snapshot([], EMPTY_SNAPSHOT)

    for ops in (upgrade_ops, rollback_ops):
        for op in ops:
            for object_type in preamble_types:
                assert object_type not in op.get("type", ""), (
                    f"PREAMBLE handler '{object_type}' emitted {op['type']} from the "
                    "model diff, which has no config to diff against"
                )
