"""Plugin architecture — in-process research extensions with a host policy boundary."""
from backend.app.plugins.host import PluginHost
from backend.app.plugins.protocols import PLUGIN_KINDS
from backend.app.plugins.registry import (
    PLUGIN_DIR,
    discover_plugins,
    get_registry,
    register_builtin_plugins,
)

__all__ = [
    "PLUGIN_DIR",
    "PLUGIN_KINDS",
    "PluginHost",
    "discover_plugins",
    "get_registry",
    "register_builtin_plugins",
]
