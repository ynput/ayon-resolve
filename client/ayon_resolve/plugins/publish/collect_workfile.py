import pyblish.api


class CollectWorkfile(pyblish.api.InstancePlugin):
    """Collect additional metadata for workfile instance."""

    label = "Collect Workfile"
    order = pyblish.api.CollectorOrder - 0.45
    hosts = ["resolve"]
    families = ["workfile"]

    def process(self, instance):
        # Mark instance for 'ExtractOTIOFile' in core
        instance.data["families"].append("otio.timeline.workfile")
