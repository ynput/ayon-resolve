import os

from ayon_core.addon import AYONAddon, IHostAddon

from .version import __version__
from .utils import RESOLVE_ADDON_ROOT


class ResolveAddon(AYONAddon, IHostAddon):
    name = "resolve"
    version = __version__
    host_name = "resolve"

    def add_implementation_envs(self, env, _app):
        # Resolve ships a legacy PySide2 which
        # conflicts with AYON self-required PySide6.
        # Force QtPy to look for pyside6 and not pyside2.
        env["QT_API"]= "pyside6"

    def get_launch_hook_paths(self, app):
        if app.host_name != self.host_name:
            return []
        return [
            os.path.join(RESOLVE_ADDON_ROOT, "hooks")
        ]

    def get_workfile_extensions(self):
        return [".drp"]
