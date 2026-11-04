import os
import shutil

from ayon_applications import PreLaunchHook, LaunchTypes
from ayon_editorial.lib.otio_install import OTIOInstallHookMixin


class InstallOpenTimelineIOToResolve(OTIOInstallHookMixin, PreLaunchHook):
    """Install OpenTimelineIO into the Python used by Resolve.

    Runs before `PreLaunchResolveSetup` (which has no `order`), so the
    Python home is read from `RESOLVE_PYTHON3_HOME` here directly.
    """

    app_groups = {"resolve"}
    order = 1
    launch_types = {LaunchTypes.local}

    settings_category = "resolve"
    resources_addon_name = "ayon_resolve"

    def get_python_executable(self):
        python3_home = self.launch_context.env.get("RESOLVE_PYTHON3_HOME")
        if not python3_home or not os.path.isdir(python3_home):
            return None

        python_search_path = os.pathsep.join(
            [python3_home, os.path.join(python3_home, "bin")]
        )
        return (
            shutil.which("python3", path=python_search_path)
            or shutil.which("python", path=python_search_path)
        )
