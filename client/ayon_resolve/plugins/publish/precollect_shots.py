import pyblish

from ayon_resolve.otio import utils


class PrecollectShot(pyblish.api.InstancePlugin):
    """PreCollect new shots."""

    order = pyblish.api.CollectorOrder - 0.48
    label = "Precollect Shots"
    hosts = ["resolve"]
    families = ["shot"]

    @staticmethod
    def _prepare_context_hierarchy(instance):
        """
        TODO: explain
        resolve:
        https://github.com/ynput/ayon-core/blob/6a07de6eb904c139f6d346fd6f2a7d5042274c71/client/ayon_core/plugins/publish/collect_hierarchy.py#L65

        traypublisher:
        https://github.com/ynput/ayon-traypublisher/blob/develop/client/ayon_traypublisher/plugins/publish/collect_shot_instances.py#L188
        """
        instance.data["folderPath"] = instance.data.pop("hierarchy_path")
        instance.data["integrate"] = False  # no representation for shot

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        self._prepare_context_hierarchy(instance)

        # Adjust instance data from parent otio timeline.
        otio_timeline = instance.context.data["otioTimeline"]
        instance.data.update(
            {
                "fps": instance.context.data["fps"],
                "resolutionWidth": otio_timeline.metadata["width"],
                "resolutionHeight": otio_timeline.metadata["height"],
                "pixelAspect": otio_timeline.metadata["pixelAspect"]                
            }
        )

        otio_clip, marker = utils.get_marker_from_clip_index(
            otio_timeline, instance.data["clip_index"]
        )
        if not otio_clip:
            raise RuntimeError("Could not retrieve otioClip for shot %r", instance)

        instance.data["otioClip"] = otio_clip

        # Overwrite settings with clip metadata is "sourceResolution"
        creator_id = instance.data["creator_identifier"]
        inst_data = marker.metadata["resolve_sub_products"].get(creator_id, {})
        overwrite_clip_metadata = inst_data.get("sourceResolution", False)
        if overwrite_clip_metadata:
            clip_metadata = otio_clip.media_reference.metadata
            instance.data.update({
                "resolutionWidth": clip_metadata["width"],
                "resolutionHeight": clip_metadata["height"],
                "pixelAspect": clip_metadata["pixelAspect"]
            })
