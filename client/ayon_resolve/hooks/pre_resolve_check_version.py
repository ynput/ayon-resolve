from __future__ import annotations

import os
import re
import json

from ayon_applications import (
    PreLaunchHook,
    LaunchTypes,
    ApplicationLaunchFailed
)
from ayon_core import lib


class PreLaunchResolveCheckVersion(PreLaunchHook):
    """Special hook to ensure installed version is compatible with AYON.
    """
    order = 10
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
        cache_file = os.path.join(cache_dir, "cached_versions.json")

        # Load the cache mapping each executable path to its mtime/version.
        try:
            with open(cache_file) as f:
                cache = json.load(f)
        # Missing, unreadable or corrupted cache, force recompute.
        except (OSError, ValueError):
            cache = {}
        if not isinstance(cache, dict):
            cache = {}

        # Return the cached version if it matches the current executable.
        entry = cache.get(exec_file)
        if isinstance(entry, dict) and entry.get("mtime") == exec_mtime:
            cached_version = entry.get("version")
            if isinstance(cached_version, str):
                return cached_version

        # e.g. "DaVinci Resolve Studio Version 21.1.0.0014"
        try:
            output = lib.run_subprocess([exec_file, "-v"])
        except (OSError, RuntimeError):
            self.log.warning(
                "Could not determine Resolve version.", exc_info=True
            )
            return None
        if not output:
            return None
        version = output.split("\n")[0]

        cache[exec_file] = {"mtime": exec_mtime, "version": version}
        try:
            os.makedirs(cache_dir, exist_ok=True)
            with open(cache_file, "w") as f:
                json.dump(cache, f, indent=4)
        except OSError:
            self.log.warning(
                f"Could not persist Resolve version cache to {cache_file}.",
                exc_info=True,
            )
        return version

    @staticmethod
    def _is_supported_version(version: str) -> bool:
        """Free Resolve 21+ dropped external python scripting."""
        is_studio = "studio" in version.lower()
        match = re.search(r"(\d+)\.\d+", version)
        major = int(match.group(1)) if match else 0
        return major < 21 if not is_studio else True

    def _should_run_resolve_check_version(self) -> bool:
        resolve_settings = self.data["project_settings"]["resolve"]
        return resolve_settings["check_compatible_ayon_version_on_start"]

    def execute(self):
        if not self._should_run_resolve_check_version():
            return

        # Detect current Resolve version and license flavor.
        resolve_version = self._query_resolve_version()
        if resolve_version and not self._is_supported_version(resolve_version):
            raise ApplicationLaunchFailed(
                f"AYON is not supported in {resolve_version}. "
                "Only the studio version supports python external scripting:\n"
                "https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=239823"
            )
