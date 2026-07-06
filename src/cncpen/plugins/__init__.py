import importlib
import pkgutil


def load_plugins() -> None:
    """Dynamically loads all plugins in the cncpen.plugins directory tree."""
    try:
        import cncpen.plugins
    except ImportError:
        return

    for _, name, is_pkg in pkgutil.walk_packages(cncpen.plugins.__path__,
                                                 cncpen.plugins.__name__ + "."):
        if not is_pkg:
            importlib.import_module(name)
