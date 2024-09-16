import os
import pyblish.api

from ayon_core.pipeline import publish

from ayon_resolve.api.lib import get_project_manager


class ExtractWorkfile(publish.Extractor):
    """
    Extractor export DRP workfile file representation
    """

    label = "Extract Workfile"
    order = pyblish.api.ExtractorOrder
    families = ["workfile"]
    hosts = ["resolve"]

    def process(self, instance):
        project = instance.context.data["activeProject"]

        drp_file_path = instance.context.data["currentFile"]
        drp_file_name = os.path.basename(drp_file_path)

        # write out the drp workfile
        get_project_manager().ExportProject(
            project.GetName(), drp_file_path)

        # create drp workfile representation
        representation_drp = {
            'name': "drp",
            'ext': "drp",
            'files': drp_file_name,
            "stagingDir": os.path.dirname(drp_file_path),
        }
        representations = instance.data.setdefault("representations", [])
        representations.append(representation_drp)

        # add sourcePath attribute to instance
        if not instance.data.get("sourcePath"):
            instance.data["sourcePath"] = drp_file_path

        self.log.debug(
            "Added Resolve file representation: {}".format(representation_drp)
        )
