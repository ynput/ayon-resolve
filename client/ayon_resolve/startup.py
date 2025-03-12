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


def set_project_fps(attributes):
    """ Attempt to set project frame rate.
    This might not be possible if a timeline already exists within the project.
    """
    resolve_project = ayon_resolve.api.get_current_resolve_project()
    project_fps = attributes["fps"]

    SUPPORTED_FPS = {
        16.0: "16",
        18.0: "18",
        23.976: "23.976",
        24.0: "24",
        25.0: "25",
        29.97: "29.97",
        30.0: "30",
        47.952: "47.952",
        48.0: "48",
        50.0: "50"
    }

    if float(project_fps) in SUPPORTED_FPS:
        if not resolve_project.SetSetting(
            "timelineFrameRate",
            SUPPORTED_FPS[float(project_fps)]
        ):
            # Resolve does not allow to edit timeline fps
            # project settings once a timeline has been created.
            log.info(
                "Cannot override Project fps from AYON."
                " This could be because a timeline already exists."
            )
    else:
        log.info(
            "Fps set in AYON project is not supported by Resolve"
            f" attempt to set {project_fps},"
            f" supported are {tuple(SUPPORTED_FPS.keys())}."
        )


def set_project_resolution(attributes):
    """ Attempt to set project resolution.
    """
    resolve_project = ayon_resolve.api.get_current_resolve_project()
    width = attributes["resolutionWidth"]
    height = attributes["resolutionHeight"]

    resolution_params = {
        "timelineResolutionHeight": height,
        "timelineResolutionWidth": width,
    }

    # In order to set vertical resolution in resolve,
    # the "Use vertical resolution" option need to be enabled.
    # This is not exposed from the Python API.
    if height > width:
            log.info(
                "Cannot override Project resolution from AYON."
                f" Vertical resolution {width}x{height}"
                " is unsupported from the API."
            )
            return

    for resolve_param, value in resolution_params.items():
        if not resolve_project.SetSetting(
            resolve_param,
            str(int(value))
        ):
            log.info(
                "Cannot override Project resolution from AYON."
            )
            return

    SUPPORTED_PIXEL_ASPECTS = {
        1.0: "Square",
        16/9: "16:9 anamorphic",
        4/3: "4:3 standard definition",
        2.0: "Cinemascope",
    }
    pixel_aspect_ratio = round(attributes["pixelAspect"], 2)

    for supported_pa in SUPPORTED_PIXEL_ASPECTS:
        if round(supported_pa, 2) != pixel_aspect_ratio:
            continue

        if not resolve_project.SetSetting(
            "timelinePixelAspectRatio",
            SUPPORTED_PIXEL_ASPECTS[supported_pa]
        ):
            log.info(
                "Cannot override Project pixel aspect ratio from AYON."
            )

        break

    else:
        log.info(
            "Pixel Aspect Ratio set in AYON project is not supported"
            f" by Resolve, attempt to set {pixel_aspect_ratio},"
            f" supported are {tuple(SUPPORTED_PIXEL_ASPECTS.keys())}."
        )


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
    from ayon_core.pipeline import Anatomy
    from ayon_core.pipeline.context_tools import get_current_project_name
    project_name = get_current_project_name()
    log.info(f"Current project name in context: {project_name}")

    # Set project frame rate and resolution
    project_anatomy = Anatomy(project_name)
    project_attributes = project_anatomy["attributes"]
    set_project_fps(project_attributes)
    set_project_resolution(project_attributes)

    # Launch AYON menu
    settings = get_project_settings(project_name)
    if settings.get("resolve", {}).get("launch_openpype_menu_on_start", True):
        log.info("Launching AYON menu..")
        launch_menu()


if __name__ == "__main__":
    main()
