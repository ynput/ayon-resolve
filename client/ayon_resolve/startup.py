"""This script is used as a startup script in Resolve through a .scriptlib file

It triggers directly after the launch of Resolve and it's recommended to keep
it optimized for fast performance since the Resolve UI is actually interactive
while this is running. As such, there's nothing ensuring the user isn't
continuing manually before any of the logic here runs. As such we also try
to delay any imports as much as possible.

This code runs in a separate process to the main Resolve process.

"""
import os
from ayon_core.lib import Logger
import ayon_resolve.api

log = Logger.get_logger(__name__)


def ensure_installed_host():
    """Install resolve host with openpype and return the registered host.

    This function can be called multiple times without triggering an
    additional install.
    """
    from ayon_core.pipeline import install_host, registered_host
    host = registered_host()
    if host:
        return host

    # Register injected "app" variable at class level for future uses.
    # For free version of DaVinci Resolve, this seems to be
    # the only way to gather the Resolve/Fusion applications.
    #
    # https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=113252
    ayon_resolve.api.ResolveHost.set_resolve_modules_from_app(app)  # noqa: F821

    host = ayon_resolve.api.ResolveHost()
    install_host(host)
    return registered_host()


def launch_menu():
    print("Launching Resolve AYON menu..")
    ensure_installed_host()
    ayon_resolve.api.launch_ayon_menu()


def open_workfile(path):
    # Avoid the need to "install" the host
    host = ensure_installed_host()
    host.open_workfile(path)


def main():
    # Open last workfile
    workfile_path = os.environ.get("AYON_RESOLVE_OPEN_ON_LAUNCH")

    if workfile_path and os.path.exists(workfile_path):
        log.info(f"Opening last workfile: {workfile_path}")
        open_workfile(workfile_path)
    else:
        log.info("No last workfile set to open. Skipping..")

    # Gathered project settings
    from ayon_core.settings import get_project_settings
    from ayon_core.pipeline.context_tools import get_current_project_name
    project_name = get_current_project_name()
    log.info(f"Current project name in context: {project_name}")

    # Launch AYON menu
    settings = get_project_settings(project_name)
    if settings.get("resolve", {}).get("launch_ayon_menu_on_start", True):
        log.info("Launching AYON menu..")
        launch_menu()


if __name__ == "__main__":
    main()
