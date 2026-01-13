"""Host API required Work Files tool"""

import os
from ayon_core.lib import Logger
from ayon_core.settings import get_project_settings
from ayon_core.pipeline.context_tools import get_current_project_name

from .lib import (
    get_project_manager,
    get_current_resolve_project,
    set_project_manager_to_folder_name
)
from .menu import DatabaseMisconfigurationWarning, ProjectImportChooser


log = Logger.get_logger(__name__)


def file_extensions():
    return [".drp"]


def has_unsaved_changes():
    project_manager = get_project_manager()
    project_manager.SaveProject()
    return False


def save_file(filepath):
    project_manager = get_project_manager()
    file = os.path.basename(filepath)
    fname, _ = os.path.splitext(file)
    resolve_project = get_current_resolve_project()
    name = resolve_project.GetName()

    # handle project db override if set
    project_name = get_current_project_name()
    settings = get_project_settings(project_name)
    override_is_valid = True
    if settings["resolve"]["project_db"].get("enabled", False):
        log.info("Handling project database override...")
        overrides = settings["resolve"]["project_db"]
        override_is_valid = handle_project_db_override(
            project_name, overrides
        )
        if not override_is_valid:
            return False

    response = False
    if name == "Untitled Project":
        response = project_manager.CreateProject(fname)
        log.info("New project created: {}".format(response))
        project_manager.SaveProject()
    elif name != fname:
        response = resolve_project.SetName(fname)
        log.info("Project renamed: {}".format(response))

    exported = project_manager.ExportProject(fname, filepath)
    log.info("Project exported: {}".format(exported))


def open_file(filepath):
    """
    Loading project
    """

    from . import bmdvr

    project_manager = get_project_manager()
    page = bmdvr.GetCurrentPage()
    if page is not None:
        # Save current project only if Resolve has an active page, otherwise
        # we consider Resolve being in a pre-launch state (no open UI yet)
        resolve_project = get_current_resolve_project()
        print(f"Saving current resolve project: {resolve_project}")
        project_manager.SaveProject()

    file = os.path.basename(filepath)
    fname, _ = os.path.splitext(file)

    # handle project db override if set
    project_name = get_current_project_name()
    settings = get_project_settings(project_name)
    override_is_valid = True
    if settings["resolve"]["project_db"].get("enabled", False):
        log.info("Handling project database override...")
        overrides = settings["resolve"]["project_db"]
        override_is_valid = handle_project_db_override(
            project_name, overrides
        )
        if not override_is_valid:
            return False
    try:
        # load project from input path
        resolve_project = project_manager.LoadProject(fname)
        log.info(f"Project {resolve_project.GetName()} opened...")

    except AttributeError:
        log.warning((f"Project with name `{fname}` does not exist! It will "
                     f"be imported from {filepath} and then loaded..."))
        if project_manager.ImportProject(filepath):
            # load project from input path
            resolve_project = project_manager.LoadProject(fname)
            log.info(f"Project imported/loaded {resolve_project.GetName()}...")
            return True
        return False
    return True


def current_file():
    resolve_project = get_current_resolve_project()
    file_ext = file_extensions()[0]
    workdir_path = os.getenv("AYON_WORKDIR")

    project_name = resolve_project.GetName()
    file_name = project_name + file_ext

    # create current file path
    current_file_path = os.path.join(workdir_path, file_name)

    # return current file path if it exists
    if os.path.exists(current_file_path):
        return os.path.normpath(current_file_path)



def handle_project_db_override(project_name, settings) -> bool:
    project_manager = get_project_manager()

    available_dbs = project_manager.GetDatabaseList() or []
    db_names = [db["DbName"] for db in available_dbs]

    valid_db_settings = False
    for available_db in available_dbs:
        if available_db["DbType"] == settings["db_type"]:
            if available_db["DbName"] == settings["db_name"]:
                valid_db_settings = True
                break

    if not valid_db_settings:
        DatabaseMisconfigurationWarning(
            settings, available_dbs
        ).exec_()
        return False

    project_manager.SetCurrentDatabase({
        "DbType": settings["db_type"],
        "DbName": settings["db_name"],
        "IpAddress": settings["db_ip"]
    })

    if settings.get("use_db_project_folder", False):
        set_project_manager_to_folder_name(project_name)

    return True

def work_root(session):
    return os.path.normpath(session["AYON_WORKDIR"]).replace("\\", "/")
