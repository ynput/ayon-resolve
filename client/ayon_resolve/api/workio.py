"""Host API required Work Files tool"""

import os
from openpype.lib import Logger
from .lib import (
    get_project_manager,
    get_current_project
)


log = Logger.get_logger(__name__)


def file_extensions():
    return [".drp"]


def has_unsaved_changes():
    get_project_manager().SaveProject()
    return False


def save_file(filepath):
    pm = get_project_manager()
    file = os.path.basename(filepath)
    fname, _ = os.path.splitext(file)
    project = get_current_project()
    name = project.GetName()

    response = False
    if name == "Untitled Project":
        response = pm.CreateProject(fname)
        log.info("New project created: {}".format(response))
        pm.SaveProject()
    elif name != fname:
        response = project.SetName(fname)
        log.info("Project renamed: {}".format(response))

    exported = pm.ExportProject(fname, filepath)
    log.info("Project exported: {}".format(exported))


def open_file(filepath):
    """
    Loading project
    """

    from . import bmdvr

    pm = get_project_manager()
    page = bmdvr.GetCurrentPage()
    if page is not None:
        # Save current project only if Resolve has an active page, otherwise
        # we consider Resolve being in a pre-launch state (no open UI yet)
        project = pm.GetCurrentProject()
        print(f"Saving current project: {project}")
        pm.SaveProject()

    file = os.path.basename(filepath)
    fname, _ = os.path.splitext(file)

    try:
        # load project from input path
        project = pm.LoadProject(fname)
        log.info(f"Project {project.GetName()} opened...")

    except AttributeError:
        log.warning((f"Project with name `{fname}` does not exist! It will "
                     f"be imported from {filepath} and then loaded..."))
        if pm.ImportProject(filepath):
            # load project from input path
            project = pm.LoadProject(fname)
            log.info(f"Project imported/loaded {project.GetName()}...")
            return True
        return False
    return True


def current_file():
    pm = get_project_manager()
    file_ext = file_extensions()[0]
    workdir_path = os.getenv("AVALON_WORKDIR")
    project = pm.GetCurrentProject()
    project_name = project.GetName()
    file_name = project_name + file_ext

    # create current file path
    current_file_path = os.path.join(workdir_path, file_name)

    # return current file path if it exists
    if os.path.exists(current_file_path):
        return os.path.normpath(current_file_path)


def work_root(session):
    return os.path.normpath(session["AVALON_WORKDIR"]).replace("\\", "/")
