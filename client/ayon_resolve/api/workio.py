"""Host API required Work Files tool"""

import os
import sys
import time
import hashlib
from pathlib import Path

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
    project_saved = project_manager.SaveProject()
    if not project_saved:
        log.error("Failed to save current project!")
        return False

    resolve_project = get_current_resolve_project()
    incoming_wf = Path(filepath)
    current_wf = incoming_wf.with_name(
        resolve_project.GetName() + ".drp")

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

    rename_db_project = settings["resolve"].get("rename_db_project_on_increment", True)
    if "Untitled Project" in current_wf.stem:
        # saving initial workfile from currently opened project
        project_manager.CreateProject(incoming_wf.stem)
        project_manager.SaveProject()
        exported = project_manager.ExportProject(incoming_wf.stem, incoming_wf.as_posix())
        log.info(f"New project {incoming_wf.stem} exported: {exported}")
    if current_wf.stem != incoming_wf.stem:
        # workfile shall be incremented
        if rename_db_project:
            # increment with local renaming
            resolve_project.SetName(incoming_wf.stem)
            exported = project_manager.ExportProject(incoming_wf.stem, incoming_wf.as_posix())
            log.info(f"Incremented workfile with local rename to {incoming_wf.as_posix()}: {exported}")
        else:
            # increment without local renaming but reimport
            exported = project_manager.ExportProject(current_wf.stem, current_wf.as_posix())
            exported = project_manager.ExportProject(current_wf.stem, incoming_wf.as_posix())
            project_manager.ImportProject(incoming_wf.as_posix())
            project_manager.LoadProject(incoming_wf.stem)
            log.info(f"Incremented workfile with reimport to {incoming_wf.as_posix()}: {exported}")
    else:
        # workfile export without increment
        exported = project_manager.ExportProject(incoming_wf.stem, incoming_wf.as_posix())
        log.info(f"Project exported without increment to {incoming_wf.as_posix()}: {exported}")


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
        # check if resolve_project is string or binary name
        if isinstance(resolve_project, str):
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

    if not db_project.exists():
        log.warning(f"Project `{file_name}` does not exist in local database. Aborting timestamp comparison.")
        return

    mtime_drp = Path(file_path).stat().st_mtime
    mtime_dbp = db_project.stat().st_mtime if db_project.exists() else 0
    if mtime_drp > mtime_dbp:
        choice = ProjectImportChooser(mtime_drp, mtime_dbp).exec_()
        if choice == QtWidgets.QMessageBox.Ok:
            proj = project_manager.LoadProject(file_name)
            if not proj:
                log.warning(f"Failed to load project `{file_name}` for import. Aborting.")
                return
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
    curr_db = project_manager.GetCurrentDatabase()

    valid_db_settings = False
    for available_db in available_dbs:
        if available_db["DbType"] == settings["db_type"]:
            if available_db["DbName"] == settings["db_name"]:
                # NOTE: Disk databases don't return IP address, so i consider them valid as long as type and name match
                if settings["db_type"] == "Disk":
                    valid_db_settings = True
                    break
                elif available_db.get("IpAddress", "") == settings.get("db_ip", ""):
                    valid_db_settings = True
                    break

    if not valid_db_settings:
        DatabaseMisconfigurationWarning(
            settings, available_dbs
        ).exec_()
        return False

    # check if we're already in the right database
    # reloading the database causes projects to not increment correctly anymore
    curr_db_valid = True
    if settings["db_type"] != curr_db.get("DbType", ""):
        curr_db_valid = False
    if settings["db_name"] != curr_db.get("DbName", ""):
        curr_db_valid = False
    if settings["db_type"] != "Disk" and (
        settings["db_ip"] != curr_db.get("IpAddress", "127.0.0.1")
    ):
        curr_db_valid = False

    if not curr_db_valid:
        db_parms = {
            "DbType": settings["db_type"],
            "DbName": settings["db_name"],
        }
        if settings["db_type"] != "Disk":
            db_parms["IpAddress"] = settings["db_ip"]
        log.info(f"Setting Project Database with Parameters: {db_parms}")
        project_manager.SetCurrentDatabase(db_parms)
    else:
        log.info(f"Using current Project Database: {curr_db}")

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
    elif sys.platform == "darwin":
        result = (
            Path(os.getenv("HOME"))
            / "Library"
            / "Application Support"
            / "Blackmagic Design" / "DaVinci Resolve" / "Support"
            / "Resolve Project Library" / "Resolve Projects"
            / "Users" / "guest" / "Projects"
        )
    else:
        raise NotImplementedError(f"Database path for platform {sys.platform} is not implemented yet.")
    return result


def work_root(session):
    return os.path.normpath(session["AYON_WORKDIR"]).replace("\\", "/")
