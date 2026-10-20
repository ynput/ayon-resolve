import os

from ayon_core.addon import AYONAddon, IHostAddon

from .version import __version__
from .utils import RESOLVE_ADDON_ROOT


class ResolveAddon(AYONAddon, IHostAddon):
    name = "resolve"
    version = __version__
    host_name = "resolve"

    def add_implementation_envs(self, env, _app):
        try:
            # Resolve python env might contain a legacy PySide2
            # that AYON used to self-required for previous version.
            # Force QtPy to look for pyside6 and not pyside2 if possible.
            import PySide6 as _  # noqa: F401
            env["QT_API"]= "pyside6"
        except ImportError:
            pass

    def get_launch_hook_paths(self, app):
        if app.host_name != self.host_name:
            return []
        return [
            os.path.join(RESOLVE_ADDON_ROOT, "hooks")
        ]

    def get_workfile_extensions(self):
        return [".drp"]
