import pyblish

from ayon_resolve.otio import utils


class PrecollectAudio(pyblish.api.InstancePlugin):
    """PreCollect new audio."""

    order = pyblish.api.CollectorOrder - 0.48
    label = "Precollect Audio"
    hosts = ["resolve"]
    families = ["audio"]

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        instance.data["folderPath"] = instance.data.pop("hierarchy_path")

        otio_timeline = instance.context.data["otioTimeline"]
        otio_clip, _ = utils.get_marker_from_clip_index(
            otio_timeline, instance.data["clip_index"]
        )
        if not otio_clip:
            raise RuntimeError("Could not retrieve otioClip for shot %r", instance)

        clip_src = otio_clip.source_range
        clip_src_in = clip_src.start_time.to_frames()
        clip_src_out = clip_src_in + clip_src.duration.to_frames()
        instance.data.update({
            "fps": instance.context.data["fps"],
            "clipInH": clip_src_in,
            "clipOutH": clip_src_out,
        })
