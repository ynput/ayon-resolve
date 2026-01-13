import os, sys
import subprocess
from pathlib import Path

from ayon_applications import PreLaunchHook, LaunchTypes
from ayon_resolve import RESOLVE_ADDON_ROOT


class PreWorkfileLoadingSplash(PreLaunchHook):
    order = 12
    app_groups = {"resolve"}
    launch_types = {LaunchTypes.local}

    def execute(self):
        if not self.launch_context.env.get("AYON_RESOLVE_OPEN_ON_LAUNCH"):
            return

        splash_script = Path(RESOLVE_ADDON_ROOT) / "api" / "splash.py"
        env = os.environ.copy()
        # inject current PYTHONPATH so process finds Qt
        env["PYTHONPATH"] = os.pathsep.join(sys.path)

        creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
        proc = subprocess.Popen(
            [sys.executable, splash_script.as_posix()],
            env=env,
            creationflags=creation_flags,
            close_fds=True
        )
        if not proc.pid:
            raise RuntimeError("Failed to launch splash screen subprocess")

        self.launch_context.env["AYON_RESOLVE_SPLASH_PID"] = str(proc.pid)
