import pyblish

from ayon_resolve.otio import utils


class PrecollectReview(pyblish.api.InstancePlugin):
    """PreCollect new reviews."""

    order = pyblish.api.CollectorOrder - 0.48
    label = "Precollect Review"
    hosts = ["resolve"]
    families = ["review"]

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        instance.data["folderPath"] = instance.data.pop("hierarchy_path")

        # Adjust instance data from parent otio timeline.
        otio_timeline = instance.context.data["otioTimeline"]
        instance.data["fps"] = instance.context.data["fps"]

        otio_clip, _ = utils.get_marker_from_clip_index(
            otio_timeline, instance.data["clip_index"]
        )
        if not otio_clip:
            raise RuntimeError("Could not retrieve otioClip for shot %r", instance)

        # TODO: really not sure about this one.
        # review media get create but is registered under the selected folder (not associated shot)
        instance.data["otioReviewClips"] = [otio_clip]
        instance.data.update({
            "frameStart": instance.data["workfileFrameStart"],
            "frameEnd": (
                instance.data["workfileFrameStart"] + 
                otio_clip.duration().to_frames()
            ),
        })
