import os
from pathlib import Path

import pyblish.api

from ayon_core.pipeline import publish, get_current_project_name
from ayon_core.pipeline.context_tools import get_current_task_entity

from ayon_core.settings import get_project_settings

from ayon_core.lib import filter_profiles

from ayon_resolve.api.lib import (
    maintain_current_timeline,
    maintain_page_by_name,
)
from ayon_resolve.api.rendering import (
    set_render_preset_from_file,
    render_single_timeline,
    set_format_and_codec,
)

from ayon_resolve.utils import RESOLVE_ADDON_ROOT
from server import settings


class ExtractIntermediateRepresentation(publish.Extractor):
    """
    Extract and Render intermediate file for Editorial Package

    """
    def __init__(self):
        super().__init__()

        self.label = "Extract Intermediate Representation"
        self.order = pyblish.api.ExtractorOrder - 0.45
        self.families = ["editorial_pkg"]
        
        i_s = self.get_settings()
        self.export_otio = i_s["export_otio"]
        self.otio_rootless = i_s["otio_rootless"]
        self.preset_path = i_s["preset_path"]
        self.file_format = i_s["file_format"]
        self.codec = i_s["codec"]

    def get_default_settings(self):
        preset_name = "AYON_intermediates"
        preset_path = Path(
            RESOLVE_ADDON_ROOT, "presets", "render", f"{preset_name}.xml"
        )

        return {
            "name": "AYON_custom_intermediate",
            "export_otio": True,
            "otio_rootless": True,
            "task_types": [],
            "task_names": [],
            "preset_path": preset_path,
            "file_format": "Quicktime",
            "codec": "H.264"
        }

    def get_settings(self):
        project_settings = get_project_settings(get_current_project_name())
        ep_settings = project_settings.get("ayon_resolve", {}).get("create", {}).get("EditorialPackage", {})
        ep_profiles = ep_settings.get("intermediate_presets", [])
        entity = get_current_task_entity()
        if not entity:
            self.log.warning("No current task entity found. Using default settings.")
            return self.get_default_settings()
        task_type = entity.get("taskType")
        profile = filter_profiles(ep_profiles, task_type)
        if profile and len(profile) > 0:
            return profile
        else:
            return self.get_default_settings()

    def process(self, instance):
        # create representation data
        if "representations" not in instance.data:
            instance.data["representations"] = []

        folder_path = instance.data["folderPath"]
        timeline_mp_item = instance.data["mediaPoolItem"]
        timeline_name = timeline_mp_item.GetName()
        folder_path_name = folder_path.lstrip("/").replace("/", "_")

        staging_dir = self.staging_dir(instance)

        subfolder_name = folder_path_name + "_" + timeline_name

        staging_dir = os.path.normpath(
            os.path.join(staging_dir, subfolder_name))

        self.log.info(f"Staging directory: {staging_dir}")

        self.log.info(f"Timeline: {timeline_mp_item}")
        self.log.info(f"Timeline name: {timeline_name}")
        # if timeline was used then switch it to current timeline
        with maintain_current_timeline(timeline_mp_item) as timeline:
            self.log.info(f"Timeline: {timeline}")
            self.log.info(f"Timeline name: {timeline.GetName()}")

            # Render timeline here
            rendered_file = self.render_timeline_intermediate_file(
                timeline,
                Path(staging_dir),
            )

        self.log.debug(f"Rendered file: {rendered_file}")

        # create intermediate workfile representation
        representation_intermediate = {
            "name": "intermediate",
            "ext": os.path.splitext(rendered_file)[1][1:],
            "files": rendered_file.name,
            "stagingDir": staging_dir,
            "tags": ["review"],
            "export_otio": self.export_otio,
            "otio_rootless": self.otio_rootless
        }
        self.log.debug(f"Video representation: {representation_intermediate}")
        instance.data["representations"].append(representation_intermediate)

        self.log.info(
            "Added intermediate file representation: "
            f"{os.path.join(staging_dir, rendered_file)}"
        )

    def render_timeline_intermediate_file(
        self,
        timeline,
        target_render_directory,
    ):
        """Render timeline to intermediate file

        Process is taking a defined timeline and render it to temporary
        intermediate file which will be lately used by Extract Review plugin
        for conversion to review file.
        """
        # get path to ayon_resolve module and get path to render presets

        self.log.info(f"Rendering timeline to '{target_render_directory}'")

        with maintain_page_by_name("Deliver"):
            # first we need to maintain rendering preset
            if not set_render_preset_from_file(self.preset_path.as_posix()):
                raise Exception("Unable to add render preset.")

            # set render format and codec
            format_extension = set_format_and_codec(
                self.file_format, self.codec)

            if not format_extension:
                raise Exception("Unable to set render format and codec.")

            if not render_single_timeline(
                timeline,
                target_render_directory,
            ):
                raise Exception("Unable to render timeline.")

        # get path of the rendered file
        rendered_files = list(
            target_render_directory.glob(f"*.{format_extension}"))

        if not rendered_files:
            raise Exception("No rendered files found.")

        return rendered_files[0]
