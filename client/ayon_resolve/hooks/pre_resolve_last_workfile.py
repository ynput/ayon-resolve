import os
from ayon_applications import PreLaunchHook, LaunchTypes


class PreLaunchResolveLastWorkfile(PreLaunchHook):
    """Special hook to open last workfile for Resolve.

    Checks 'start_last_workfile', if set to False, it will not open last
    workfile. This property is set explicitly in Launcher.
    """
    order = 10
    app_groups = {"resolve"}
    launch_types = {LaunchTypes.local}

    def execute(self):
        workfile_path = self.get_workfile_path()
        if not workfile_path:
            return

        # Add path to launch environment for the startup script to pick up
        self.log.info(
            "Setting AYON_RESOLVE_OPEN_ON_LAUNCH to launch "
            f"last workfile: {workfile_path}"
        )
        key = "AYON_RESOLVE_OPEN_ON_LAUNCH"
        self.launch_context.env[key] = workfile_path

    def get_workfile_path(self):
        workfile_path = self.data.get("workfile_path")
        if workfile_path:
            return workfile_path

        if not self.data.get("start_last_workfile"):
            self.log.info("It is set to not start last workfile on start.")
            return None

        last_workfile = self.data.get("last_workfile_path")
        if not last_workfile:
            self.log.warning("Last workfile was not collected.")
            return None

        if not os.path.exists(last_workfile):
            self.log.info("Current context does not have any workfile yet.")
            return None
        return last_workfile
