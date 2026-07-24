from __future__ import annotations

from dbwarden_pgsql_extensions.handler import PgExtensionHandler
from dbwarden_pgsql_extensions.handlers.event_trigger_handler import EventTriggerHandler
from dbwarden_pgsql_extensions.handlers.extended_statistics_handler import ExtendedStatisticsHandler
from dbwarden_pgsql_extensions.handlers.function_handler import FunctionHandler
from dbwarden_pgsql_extensions.handlers.storage_params_handler import StorageParamsHandler
from dbwarden_pgsql_extensions.handlers.trigger_handler import TriggerHandler

__version__ = "0.1.0"

# The DBWarden plugin contract this package targets. Core refuses to load a
# plugin declaring a version it does not provide, so a mismatched pairing fails
# at load with one clear message instead of somewhere inside a migration.
DBWARDEN_PLUGIN_API = 1

HANDLER_CLASSES = (
    PgExtensionHandler,
    EventTriggerHandler,
    ExtendedStatisticsHandler,
    FunctionHandler,
    StorageParamsHandler,
    TriggerHandler,
)


def setup(registrar) -> None:
    for handler_class in HANDLER_CLASSES:
        registrar.register_object_handler(handler_class())


__all__ = [
    "EventTriggerHandler",
    "ExtendedStatisticsHandler",
    "FunctionHandler",
    "HANDLER_CLASSES",
    "PgExtensionHandler",
    "StorageParamsHandler",
    "TriggerHandler",
    "setup",
]
