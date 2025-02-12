import pprint
import pyblish

from ayon_core.pipeline import PublishError
from ayon_resolve.otio import utils


class CollectAudio(pyblish.api.InstancePlugin):
    """Collect new audio."""

    order = pyblish.api.CollectorOrder - 0.48
    label = "Collect Audio"
    hosts = ["resolve"]
    families = ["audio"]

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        otio_timeline = instance.context.data["otioTimeline"]
        otio_clip, marker = utils.get_marker_from_clip_index(
            otio_timeline, instance.data["clip_index"]
        )
        if not otio_clip:
            raise PublishError(
                "Could not retrieve otioClip for audio"
                f' {dict(instance.data)}'
            )

        instance.data["otioClip"] = otio_clip

        # Retrieve instance data from parent instance shot instance.
        parent_instance_id = instance.data["parent_instance_id"]
        edit_shared_data = instance.context.data["editorialSharedData"]
        instance.data.update(
            edit_shared_data[parent_instance_id]
        )

        # solve reviewable options
        review_switch = instance.data["creator_attributes"].get("review")

        if review_switch is True:
            instance.data["reviewAudio"] = True
            instance.data.pop("review", None)

        clip_src = instance.data["otioClip"].source_range
        clip_src_in = clip_src.start_time.to_frames()
        clip_src_out = clip_src_in + clip_src.duration.to_frames()
        instance.data.update({
            "clipInH": clip_src_in,
            "clipOutH": clip_src_out
        })

        self.log.debug(pprint.pformat(instance.data))
