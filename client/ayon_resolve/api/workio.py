"""Host API required Work Files tool"""

import os
import sys
import time
import hashlib
from pathlib import Path
from datetime import datetime as dt

from qtpy import QtWidgets

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
    if "Untitled Project" in name:
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

        if settings["resolve"]["project_db"]["db_type"] == "Disk":
            handle_local_vs_exported_project(
                settings, project_name, filepath
            )

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


def handle_local_vs_exported_project(settings, project_name, file_path):
    project_manager = get_project_manager()

    file_name = Path(file_path).stem
    if settings["resolve"]["project_db"].get("use_db_project_folder", False):
        db_project = get_local_database_root() / project_name / file_name / "Project.db"
    else:
        db_project = get_local_database_root() / file_name / "Project.db"

    mtime_drp = Path(file_path).stat().st_mtime
    mtime_dbp = db_project.stat().st_mtime if db_project.exists() else 0
    if mtime_drp > mtime_dbp:
        choice = ProjectImportChooser(mtime_drp, mtime_dbp).exec_()
        if choice == QtWidgets.QMessageBox.Ok:
            proj = project_manager.LoadProject(file_name)
            sha = hashlib.sha1(
                f"{file_name}_{time.time()}".encode("utf-8")
            ).hexdigest()[:6]
            proj_bkp_name = f"{proj.GetName()}_BKP_{sha}"
            proj.SetName(proj_bkp_name)
            project_manager.SaveProject()
            project_manager.CloseProject(proj_bkp_name)
            project_manager.ImportProject(file_path)


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


def get_local_database_root() -> Path:
    # does anyone use resolve users other than guest?
    if sys.platform == "win32":
        result = (
            Path(os.getenv("APPDATA"))
            / "Blackmagic Design" / "DaVinci Resolve" / "Support"
            / "Resolve Project Library" / "Resolve Projects"
            / "Users" / "guest" / "Projects"
        )
    if sys.platform == "darwin":
        raise NotImplementedError("MacOS database path is not implemented yet.")
    if sys.platform == "linux":
        raise NotImplementedError("Linux database path is not implemented yet.")
    return result


def work_root(session):
    return os.path.normpath(session["AYON_WORKDIR"]).replace("\\", "/")
