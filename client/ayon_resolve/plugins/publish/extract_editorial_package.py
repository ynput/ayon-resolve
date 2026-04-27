import os
from pathlib import Path

import opentimelineio as otio
import pyblish.api
from ayon_core.pipeline import publish
from ayon_core.pipeline.publish.lib import get_instance_expected_output_path
from ayon_resolve.api import bmdvr
from ayon_resolve.api.lib import (
    export_timeline_otio_native,
    get_current_resolve_project,
    maintain_current_timeline,
)
from ayon_resolve.otio import davinci_export


class ExtractEditorialPackage(publish.Extractor):
    """
    Extract and Render intermediate file for Editorial Package

    """

    label = "Extract Editorial Package"
    order = pyblish.api.ExtractorOrder + 0.45
    families = ["editorial_pkg"]

    def process(self, instance):
        anatomy = instance.context.data["anatomy"]
        folder_path = instance.data["folderPath"]
        timeline_mp_item = instance.data["mediaPoolItem"]
        timeline_name = timeline_mp_item.GetName()
        folder_path_name = folder_path.lstrip("/").replace("/", "_")

        staging_dir = Path(self.staging_dir(instance))
        subfolder_name = folder_path_name + "_" + timeline_name

        # new staging directory for each timeline
        staging_dir = staging_dir / subfolder_name
        os.makedirs(staging_dir, exist_ok=True)
        self.log.info(f"Staging directory: {staging_dir}")

        # otio file path
        otio_file_name = f"{subfolder_name}.otio"
        otio_file_path = staging_dir / otio_file_name

        # Expected representations comming from `ExtractProductResources` plugin
        for repre in instance.data["representations"]:
            # make sure only representations with custom tags
            # or "intermediate" custom tag are processed
            if (
                not repre.get("custom_tags", [])
                and "intermediate" not in repre.get("custom_tags", [])
            ):
                continue

            published_file_path = get_instance_expected_output_path(
                instance,
                representation_name=repre["name"],
                ext=repre["ext"],
            )
            export_otio = repre.get("export_otio", True)
            otio_rootless = repre.get("otio_rootless", True)
            break
        else:
            raise ValueError("Intermediate representation not found")

        self.log.debug(
            f"Export_otio: {export_otio}, otio_rootless: {otio_rootless}"
        )

        # if timeline was used then switch it to current timeline
        with maintain_current_timeline(timeline_mp_item) as timeline:
            timeline_fps = timeline.GetSetting("timelineFrameRate")
            timeline_start_frame = timeline.GetStartFrame()
            timeline_end_frame = timeline.GetEndFrame()
            timeline_duration = timeline_end_frame - timeline_start_frame
            self.log.debug(
                f"Timeline: {timeline}, "
                f"Start: {timeline_start_frame}, "
                f"End: {timeline_end_frame}, "
                f"Duration: {timeline_duration}, "
                f"FPS: {timeline_fps}"
            )

            if export_otio:
                # export otio representation
                self.export_otio_representation(
                    get_current_resolve_project(), timeline, otio_file_path
                )
            else:
                self.log.info("OTIO export not enabled, skipping OTIO export.")
                return


        # Finding clip references and replacing them with rootless paths
        # of video files
        otio_file_name_replaced = otio_file_name
        if export_otio and otio_rootless:
            otio_timeline = otio.adapters.read_from_file(
                otio_file_path.as_posix())
            for track in otio_timeline.tracks:
                for clip in track:
                    # skip transitions
                    if isinstance(clip, otio.schema.Transition):
                        continue
                    # skip gaps
                    if isinstance(clip, otio.schema.Gap):
                        # get duration of gap
                        continue
                    # skip stacks (nested timelines, Fusion clips, etc.)
                    if isinstance(clip, otio.schema.Stack):
                        continue

                    # TODO: Instead of skipping other class types should we
                    #  just check for isinstance(clip, otio.schema.Clip)?
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
                                    value=timeline_start_frame,
                                    rate=timeline_fps
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
            otio_file_name_replaced = f"{subfolder_name}_remap.otio"
            otio_file_path_replaced = staging_dir / otio_file_name_replaced
            otio.adapters.write_to_file(
                otio_timeline, otio_file_path_replaced.as_posix())

            self.log.debug(
                "OTIO file with replaced references: "
                f"{otio_file_path_replaced}")
        else:
            self.log.info(
                "OTIO rootless paths not enabled, "
                "skipping OTIO remapping."
            )

        if export_otio:
            # create drp workfile representation
            representation_otio = {
                "name": "editorial_pkg",
                "ext": "otio",
                "files": otio_file_name_replaced,
                "stagingDir": staging_dir.as_posix(),
            }
            self.log.debug(f"OTIO representation: {representation_otio}")
            instance.data["representations"].append(representation_otio)

            self.log.info(
                "Added OTIO file representation: "
                f"{otio_file_path_replaced}"
            )

    def export_otio_representation(self, resolve_project, timeline, filepath):
        # Native otio export is available from Resolve 18.5
        # [major, minor, patch, build, suffix]
        resolve_version = bmdvr.GetVersion()
        if tuple(resolve_version[:2]) < (18, 5):
            # if it is lower then use ayon's otio exporter
            self.log.debug(
                f"OTIO Export: Using AYON's OTIO exporter: {filepath}"
            )
            otio_timeline = davinci_export.create_otio_timeline(
                resolve_project, timeline=timeline
            )
            davinci_export.write_to_file(otio_timeline, filepath.as_posix())
        else:
            # use native otio export
            export_timeline_otio_native(timeline, filepath.as_posix())
            self.log.debug(
                f"OTIO Export: Using native OTIO exporter: {filepath}"
            )

        # check if file exists
        if not filepath.exists():
            raise FileNotFoundError(f"OTIO file not found: {filepath}")
