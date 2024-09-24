import pprint
import pyblish

from ayon_resolve.api import lib
from ayon_resolve.otio import utils


class CollectShot(pyblish.api.InstancePlugin):
    """Collect new shots."""

    order = pyblish.api.CollectorOrder - 0.49
    label = "Collect Shots"
    hosts = ["resolve"]
    families = ["shot"]

    SHARED_KEYS = (
        "folderPath",
        "fps",
        "otioClip",
        "resolutionWidth",
        "resolutionHeight",
        "pixelAspect",        
    )

    @classmethod
    def _inject_editorial_shared_data(cls, instance):
        """
        Args:
            instance (obj): The publishing instance.
        """
        context = instance.context
        instance_id = instance.data["instance_id"]

        # Inject folderPath and other creator_attributes to ensure
        # new shots/hierarchy are properly handled.
        creator_attributes = instance.data['creator_attributes']
        instance.data.update(creator_attributes)

        # Inject/Distribute instance shot data as editorialSharedData
        # to make it available for clip/plate/audio products
        # in sub-collectors.
        if not context.data.get("editorialSharedData"):
            context.data["editorialSharedData"] = {}

        context.data["editorialSharedData"][instance_id] = {
            key: value for key, value in instance.data.items()
            if key in cls.SHARED_KEYS
        }

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        instance.data["integrate"] = False  # no representation for shot

        # Adjust instance data from parent otio timeline.
        otio_timeline = instance.context.data["otioTimeline"]
        otio_clip, marker = utils.get_marker_from_clip_index(
            otio_timeline, instance.data["clip_index"]
        )
        if not otio_clip:
            raise RuntimeError("Could not retrieve otioClip for shot %r", instance)

        # Compute fps from creator attribute.
        if instance.data['creator_attributes']["fps"] == "from_selection":
            instance.data['creator_attributes']["fps"] = instance.context.data["fps"]

        # Retrieve AyonData marker for associated clip.
        instance.data["otioClip"] = otio_clip
        creator_id = instance.data["creator_identifier"]
        inst_data = marker.metadata["resolve_sub_products"].get(creator_id, {})

        # Overwrite settings with clip metadata is "sourceResolution"
        overwrite_clip_metadata = inst_data.get("sourceResolution", False)
        if overwrite_clip_metadata:
            clip_metadata = inst_data["clip_source_resolution"]
            width = clip_metadata["width"]
            height = clip_metadata["height"]
            pixel_aspect = clip_metadata["pixelAspect"]

        else:
            # AYON's OTIO export = resolution from timeline metadata.
            # This is metadata is inserted by ayon_resolve.otio.davinci_export.
            width = height = None
            try:
                width = otio_timeline.metadata["width"]
                height = otio_timeline.metadata["height"]
                pixel_aspect = otio_timeline.metadata["pixelAspect"]

            except KeyError:
                # Retrieve resolution for project.
                project = lib.get_current_project()
                project_settings = project.GetSetting()
                try:
                    pixel_aspect = int(project_settings["timelinePixelAspectRatio"])
                except ValueError:
                    pixel_aspect = 1.0

                width = int(project_settings["timelineResolutionWidth"])
                height = int(project_settings["timelineResolutionHeight"])

        instance.data.update(
            {
                "resolutionWidth": width,
                "resolutionHeight": height,
                "pixelAspect": pixel_aspect,
            }
        )

        self._inject_editorial_shared_data(instance)
        self.log.debug(pprint.pformat(instance.data))
