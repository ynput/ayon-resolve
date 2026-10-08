import os

import pyblish.api

from ayon_core.host import IWorkfileHost
from ayon_core.pipeline import registered_host, OptionalPyblishPluginMixin
from ayon_core.pipeline.publish import get_errored_plugins_from_context
from ayon_core.host.interfaces import SaveWorkfileOptionalData
from ayon_core.pipeline.workfile import save_next_version


class IntegrateVersionUpWorkfile(pyblish.api.ContextPlugin,
                                 OptionalPyblishPluginMixin):
    """Save as new workfile version"""

    order = pyblish.api.IntegratorOrder + 10.1
    label = "Version-up Workfile"
    hosts = ["resolve"]

    optional = True
    active = True

    def process(self, context: pyblish.api.Context):
        if not self.is_active(context.data):
            return

        errored_plugins = get_errored_plugins_from_context(context)
        if errored_plugins:
            raise RuntimeError(
                "Skipping incrementing current file because publishing failed."
            )

        current_filepath: str = context.data["currentFile"]
        host: IWorkfileHost = registered_host()
        current_filename = os.path.basename(current_filepath)
        save_next_version(
            description=(
                f"Incremented by publishing from {current_filename}"
            ),
            # Optimize the save by reducing needed queries for context
            prepared_data=SaveWorkfileOptionalData(
                project_entity=context.data["projectEntity"],
                project_settings=context.data["project_settings"],
                anatomy=context.data["anatomy"],
            )
        )
        new_scene_path = host.get_current_workfile()
        self.log.info(f"Incremented workfile to: {new_scene_path}")
