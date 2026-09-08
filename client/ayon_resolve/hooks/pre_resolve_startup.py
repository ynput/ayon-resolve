import os
import re

from ayon_applications import PreLaunchHook, LaunchTypes
from ayon_core import lib

from ayon_resolve import RESOLVE_ADDON_ROOT


class PreLaunchResolveStartup(PreLaunchHook):
    """Special hook to configure startup script.

    """
    order = 11
    app_groups = {"resolve"}
    launch_types = {LaunchTypes.local}

    def execute(self):
        # Detect current Resolve version and license flavor.
        cmd = self.launch_context.launch_args + ["-v"]
        version_output = lib.run_subprocess(cmd)

        if version_output:
            # e.g. DaVinci Resolve Studio Version 21.1.0.0014
            resolve_version = version_output.split("\n")[0]

            is_studio = "studio" in resolve_version.lower()
            version_match = re.search(r"(\d+)\.\d+", resolve_version)
            major_version = int(version_match.group(1)) if version_match else 0

            if not is_studio and major_version >= 21:
                raise RuntimeError(
                    f"AYON is not supported in {resolve_version} "
                    "Only the studio version supports python external scripting: \n"
                    "https://www.reddit.com/r/davinciresolve/comments/1wafb08/davinci_resolve_211_release_notes/",
                )


        # Set the openpype prelaunch startup script path for easy access
        # in the LUA .scriptlib code
        script_path = os.path.join(RESOLVE_ADDON_ROOT, "startup.py")
        key = "AYON_RESOLVE_STARTUP_SCRIPT"
        self.launch_context.env[key] = script_path

        self.log.info(
            f"Setting AYON_RESOLVE_STARTUP_SCRIPT to: {script_path}"
        )
