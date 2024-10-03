from pathlib import Path

import pyblish.api
import opentimelineio as otio

from ayon_core.pipeline import publish
from ayon_resolve.api.lib import (
    maintain_current_timeline,
    get_current_project,
    export_timeline_otio_native
)
from ayon_resolve.otio import davinci_export

from ayon_resolve.api import bmdvr


class ExtractEditorialPackage(publish.Extractor):
    """
    Extract and Render intermediate file for Editorial Package

    """

    label = "Extract Editorial Package"
    order = pyblish.api.ExtractorOrder + 0.45
    families = ["editorial_pkg"]

    def process(self, instance):
        # create representation data
        if "representations" not in instance.data:
            instance.data["representations"] = []

        anatomy = instance.context.data["anatomy"]
        folder_path = instance.data["folderPath"]
        timeline_mp_item = instance.data["mediaPoolItem"]
        timeline_name = timeline_mp_item.GetName()
        folder_path_name = folder_path.lstrip("/").replace("/", "_")

        staging_dir = Path(self.staging_dir(instance))
        subfolder_name = folder_path_name + "_" + timeline_name

        # new staging directory for each timeline
        staging_dir = staging_dir / subfolder_name
        self.log.info(f"Staging directory: {staging_dir}")

        # otio file path
        otio_file_path = staging_dir / f"{subfolder_name}.otio"

        # if timeline was used then switch it to current timeline
        with maintain_current_timeline(timeline_mp_item) as timeline:
            timeline_fps = timeline.GetSetting("timelineFrameRate")
            timeline_start_frame = timeline.GetStartFrame()
            timeline_end_frame = timeline.GetEndFrame()
            timeline_duration = timeline_end_frame - timeline_start_frame
            self.log.info(
                f"Timeline: {timeline}, "
                f"Start: {timeline_start_frame}, "
                f"End: {timeline_end_frame}, "
                f"Duration: {timeline_duration}, "
                f"FPS: {timeline_fps}"
            )

            # export otio representation
            self.export_otio_representation(
                get_current_project(), timeline, otio_file_path
            )

        # Find Intermediate file representation file name
        published_file_path = None
        for repre in instance.data["representations"]:
            if repre["name"] == "intermediate":
                published_file_path = self._get_published_path(instance, repre)
                break

        if published_file_path is None:
            raise ValueError("Intermediate representation not found")

        # Finding clip references and replacing them with rootless paths
        # of video files
        otio_timeline = otio.adapters.read_from_file(otio_file_path.as_posix())
        for track in otio_timeline.tracks:
            for clip in track:
                # skip transitions
                if isinstance(clip, otio.schema.Transition):
                    continue
                # skip gaps
                if isinstance(clip, otio.schema.Gap):
                    # get duration of gap
                    continue

                if hasattr(clip.media_reference, "target_url"):
                    path_to_media = Path(published_file_path)
                    # remove root from path
                    success, rootless_path = anatomy.find_root_template_from_path(  # noqa
                        path_to_media.as_posix()
                    )
                    if success:
                        media_source_path = rootless_path
                    else:
                        media_source_path = path_to_media.as_posix()

                    new_media_reference = otio.schema.ExternalReference(
                        target_url=media_source_path,
                        available_range=otio.opentime.TimeRange(
                            start_time=otio.opentime.RationalTime(
                                value=timeline_start_frame, rate=timeline_fps
                            ),
                            duration=otio.opentime.RationalTime(
                                value=timeline_duration, rate=timeline_fps
                            ),
                        ),
                    )
                    clip.media_reference = new_media_reference

                    # replace clip source range with track parent range
                    clip.source_range = otio.opentime.TimeRange(
                        start_time=otio.opentime.RationalTime(
                            value=(
                                timeline_start_frame
                                + clip.range_in_parent().start_time.value
                            ),
                            rate=timeline_fps,
                        ),
                        duration=clip.range_in_parent().duration,
                    )

        # reference video representations also needs to reframe available
        # frames and clip source

        # new otio file needs to be saved as new file
        otio_file_path_replaced = staging_dir / f"{subfolder_name}_remap.otio"
        otio.adapters.write_to_file(
            otio_timeline, otio_file_path_replaced.as_posix())

        self.log.debug(
            f"OTIO file with replaced references: {otio_file_path_replaced}")

        # create drp workfile representation
        representation_otio = {
            "name": "editorial_pkg",
            "ext": "otio",
            "files": f"{subfolder_name}_remap.otio",
            "stagingDir": staging_dir.as_posix(),
        }
        self.log.debug(f"OTIO representation: {representation_otio}")
        instance.data["representations"].append(representation_otio)

        self.log.info(
            "Added OTIO file representation: "
            f"{otio_file_path}"
        )

    def export_otio_representation(self, resolve_project, timeline, filepath):
        # Native otio export is available from Resolve 18.5
        # [major, minor, patch, build, suffix]
        resolve_version = bmdvr.GetVersion()
        if resolve_version[0] < 18 or resolve_version[1] < 5:
            # if it is lower then use ayon's otio exporter
            otio_timeline = davinci_export.create_otio_timeline(
                resolve_project, timeline=timeline
            )
            davinci_export.write_to_file(otio_timeline, filepath.as_posix())
        else:
            # use native otio export
            export_timeline_otio_native(timeline, filepath.as_posix())

        # check if file exists
        if not filepath.exists():
            raise FileNotFoundError(f"OTIO file not found: {filepath}")

    def _get_published_path(self, instance, representation):
        """Calculates expected `publish` folder"""
        # determine published path from Anatomy.
        template_data = instance.data.get("anatomyData")

        template_data["representation"] = representation["name"]
        template_data["ext"] = representation["ext"]
        template_data["comment"] = None

        anatomy = instance.context.data["anatomy"]
        template_data["root"] = anatomy.roots
        template = anatomy.get_template_item("publish", "default", "path")
        template_filled = template.format_strict(template_data)
        file_path = Path(template_filled)
        return file_path.as_posix()
