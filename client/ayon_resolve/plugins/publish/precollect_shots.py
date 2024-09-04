import pyblish

from ayon_resolve.api import lib
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
        instance.data["folderPath"] = instance.data["folder_path"]
        instance.data["integrate"] = False  # no representation for shot

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        self._prepare_context_hierarchy(instance)

        # Adjust instance data from parent otio timeline.
        otio_timeline = instance.context.data["otioTimeline"]
        otio_clip, marker = utils.get_marker_from_clip_index(
            otio_timeline, instance.data["clip_index"]
        )
        if not otio_clip:
            raise RuntimeError("Could not retrieve otioClip for shot %r", instance)

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
                "fps": instance.context.data["fps"],
                "resolutionWidth": width,
                "resolutionHeight": height,
                "pixelAspect": pixel_aspect,
            }
        )
