import os

import pyblish.api

from ayon_core.host.interfaces import SaveWorkfileOptionalData
from ayon_core.pipeline.workfile import save_next_version
from ayon_core.pipeline.publish import (
    OptionalPyblishPluginMixin,
)


class IntegrateVersionUpWorkfile(pyblish.api.ContextPlugin,
                                 OptionalPyblishPluginMixin):
    """Save as new workfile version"""

    order = pyblish.api.IntegratorOrder + 10.1
    label = "Version-up Workfile"
    hosts = ["resolve"]

    optional = True
    active = True

    def process(self, context):
        if not self.is_active(context.data):
            self.log.debug("Project workfile version up was skipped")
            return

        path = context.data["currentFile"]

        current_filename = os.path.basename(path)
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
        self.log.info("Project workfile was versioned up")
