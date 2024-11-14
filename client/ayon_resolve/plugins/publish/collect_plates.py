import pyblish.api

from ayon_resolve.otio import utils


class CollectPlate(pyblish.api.InstancePlugin):
    """Collect new plates."""

    order = pyblish.api.CollectorOrder - 0.48
    label = "Collect Plate"
    hosts = ["resolve"]
    families = ["plate"]

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        instance.data["families"].append("clip")

        otio_timeline = instance.context.data["otioTimeline"]
        otio_clip, marker = utils.get_marker_from_clip_index(
            otio_timeline, instance.data["clip_index"]
        )
        if not otio_clip:
            raise RuntimeError("Could not retrieve otioClip for shot %r", instance)

        instance.data["otioClip"] = otio_clip

        # Retrieve instance data from parent instance shot instance.
        parent_instance_id = instance.data["parent_instance_id"]
        edit_shared_data = instance.context.data["editorialSharedData"]
        instance.data.update(
            edit_shared_data[parent_instance_id]
        )
