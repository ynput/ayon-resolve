from __future__ import annotations

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

    def _query_resolve_version(self) -> str | None:
        """Return the Resolve version string, cached per executable mtime."""
        exec_file = self.launch_context.launch_args[0]
        if not os.path.isfile(exec_file):
            self.log.warning(
                f"Cannot check Resolve version, executable not found: {exec_file}"
            )
            return None

        exec_mtime = os.path.getmtime(exec_file)
        cache_dir = lib.get_addons_resources_dir("ayon_resolve")
        cache_file = os.path.join(cache_dir, "cached_version")

        # Return the cached version if it matches the current executable.
        try:
            with open(cache_file) as f:
                mtime, version = f.read().split("|")
            if float(mtime) == exec_mtime:
                return version

        # Missing, unreadable or corrupted cache, force recompute.
        except (OSError, ValueError):
            pass

        # e.g. "DaVinci Resolve Studio Version 21.1.0.0014"
        output = lib.run_subprocess(self.launch_context.launch_args + ["-v"])
        if not output:
            return None
        version = output.split("\n")[0]

        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_file, "w") as f:
            f.write(f"{exec_mtime}|{version}")
        return version

    @staticmethod
    def _is_supported_version(version: str) -> bool:
        """Free Resolve 21+ dropped external python scripting."""
        is_studio = "studio" in version.lower()
        match = re.search(r"(\d+)\.\d+", version)
        major = int(match.group(1)) if match else 0
        return major < 21 if not is_studio else True

    def execute(self):
        # Detect current Resolve version and license flavor.
        resolve_version = self._query_resolve_version()
        if resolve_version and not self._is_supported_version(resolve_version):
            raise RuntimeError(
                f"AYON is not supported in {resolve_version}. "
                "Only the studio version supports python external scripting:\n"
                "https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=239823"
            )

        # Set the openpype prelaunch startup script path for easy access
        # in the LUA .scriptlib code
        script_path = os.path.join(RESOLVE_ADDON_ROOT, "startup.py")
        key = "AYON_RESOLVE_STARTUP_SCRIPT"
        self.launch_context.env[key] = script_path

        self.log.info(
            f"Setting AYON_RESOLVE_STARTUP_SCRIPT to: {script_path}"
        )
