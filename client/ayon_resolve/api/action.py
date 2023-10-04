# absolute_import is needed to counter the `module has no cmds error` in Maya
from __future__ import absolute_import

import pyblish.api


from openpype.pipeline.publish import get_errored_instances_from_context


class SelectInvalidAction(pyblish.api.Action):
    """Select invalid clips in Resolve timeline when plug-in failed.

    To retrieve the invalid nodes this assumes a static `get_invalid()`
    method is available on the plugin.

    """
    label = "Select invalid"
    on = "failed"  # This action is only available on a failed plug-in
    icon = "search"  # Icon from Awesome Icon

    def process(self, context, plugin):

        try:
            from .lib import get_project_manager
            pm = get_project_manager()
            self.log.debug(pm)
        except ImportError:
            raise ImportError("Current host is not Resolve")

        errored_instances = get_errored_instances_from_context(context,
                                                               plugin=plugin)

        # Get the invalid nodes for the plug-ins
        self.log.info("Finding invalid clips..")
        invalid = list()
        for instance in errored_instances:
            invalid_nodes = plugin.get_invalid(instance)
            if invalid_nodes:
                if isinstance(invalid_nodes, (list, tuple)):
                    invalid.extend(invalid_nodes)
                else:
                    self.log.warning("Plug-in returned to be invalid, "
                                     "but has no selectable nodes.")

        # Ensure unique (process each node only once)
        invalid = list(set(invalid))

        if invalid:
            self.log.info("Selecting invalid nodes: %s" % ", ".join(invalid))
            # TODO: select resolve timeline track items in current timeline
        else:
            self.log.info("No invalid nodes found.")
