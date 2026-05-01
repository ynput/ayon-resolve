import os
from pathlib import Path
from pprint import pformat

import pyblish.api
from ayon_core.lib import StringTemplate, filter_profiles
from ayon_core.pipeline import Anatomy, get_current_project_name, publish
from ayon_core.pipeline.context_tools import get_current_task_entity
from ayon_resolve.api import rendering
from ayon_resolve.api.lib import (
    maintain_current_timeline,
    maintain_page_by_name,
)
from ayon_resolve.api.rendering import (
    render_clip_to_intermediate_file,
    render_timeline_intermediate_file,
    set_format_and_codec,
    set_render_preset_from_file,
    modify_preset_file,
)
from ayon_resolve.utils import RESOLVE_ADDON_ROOT


class ExtractProductResources(
    publish.Extractor,
    publish.ColormanagedPyblishPluginMixin
):
    """Extract product resources (intermediate files).

    Handles two product base types:
    - ``editorial_pkg``: renders the full active timeline to a video container
      and optionally exports an OTIO file alongside it.
    - ``clip``: renders the exact frame range of a single ``TimelineItem`` on
      the active timeline, producing either a video container or an image
      sequence depending on the configured format.

    Settings are resolved per-instance from
    ``resolve → publish → ExtractProductResources → presets``, matched on task
    type / task name and ``product_base_type``.
    """

    label = "Extract Product Resources"
    order = pyblish.api.ExtractorOrder - 0.45
    families = ["editorial_pkg", "clip"]

    # settings
    profiles = []

    def process(self, instance):
        instance.data.setdefault("representations", [])

        settings = self.get_settings(instance)
        preset_path = Path(self.resolve_preset_path(settings["preset_path"]))
        product_base_type = instance.data["productBaseType"]

        # set rendering logger to inherit from publisher's logger
        rendering.log = self.log

        if product_base_type == "editorial_pkg":
            self._process_editorial_pkg(instance, settings, preset_path)
        elif product_base_type == "plate":
            self._process_plate(instance, settings, preset_path)
        else:
            self.log.warning(
                "ExtractProductResources: unhandled product base type "
                f"'{product_base_type}', skipping."
            )

    def get_settings(self, instance):
        """Return normalised render settings for *instance*.

        Looks up ``resolve → publish → ExtractProductResources → profiles``,
        then profile-matches on task type / task name / product_base_type.

        Returns a flat dict with keys:
            ``file_format``, ``codec``, ``preset_path``,
            and for *editorial_pkg* only: ``export_otio``, ``otio_rootless``.
        """

        entity = get_current_task_entity()
        if not entity:
            self.log.warning("No current task entity — using default settings.")
            product_base_type = instance.data["productBaseType"]
            return self.get_default_settings(product_base_type)

        task_type = entity.get("taskType")
        task_name = entity.get("taskName")
        product_base_type = instance.data["productBaseType"]

        profile = filter_profiles(
            self.profiles,
            {
                "task_types": task_type,
                "task_names": task_name,
                "product_base_type": product_base_type,
            },
        )

        if not profile:
            self.log.debug(
                f"No preset matched for family='{product_base_type}', "
                f"task_type='{task_type}', task_name='{task_name}'. "
                "Using defaults."
            )
            return self.get_default_settings(product_base_type)

        self.log.debug(f"Matched preset: {profile.get('name')}")
        return self._normalize_preset(profile, product_base_type)

    def _normalize_preset(self, preset, product_base_type):
        """Flatten the nested preset structure into a render-ready dict."""
        sub = preset.get(product_base_type, {})
        preset_type = sub.get("preset_type")
        fmt = sub.get(preset_type, {})

        normalized = {
            "name":        preset["name"],
            "file_format": fmt.get("format"),
            "codec":       fmt.get("codec"),
            "preset_path": fmt.get("preset_path"),
            "with_handles": sub.get("with_handles"),
            "tags":        preset["tags"],
            "custom_tags": preset["custom_tags"],
        }
        if product_base_type == "editorial_pkg":
            normalized["export_otio"]   = sub.get("export_otio")
            normalized["otio_rootless"] = sub.get("otio_rootless")
        return normalized

    def get_default_settings(self, product_base_type="editorial_pkg"):
        """Return hard-coded defaults when no matching preset is found."""
        if product_base_type == "plate":
            return {
                "file_format": "EXR",
                "codec":       "RGB half (DWAA)",
                "preset_path": (
                    "{ayon_render_presets}/clip/EXR_RGB_half_(DWAA).xml"
                ),
            }
        return {
            "file_format":   "QuickTime",
            "codec":         "H.264",
            "preset_path":   (
                "{ayon_render_presets}/timeline/QuickTime_H264.xml"
            ),
            "export_otio":   True,
            "otio_rootless": True,
        }

    def resolve_preset_path(self, preset_path):
        """Resolve the path to a render preset file.

        The path can be defined in settings and can contain template keys
        and environment variables. This method will try to resolve the path
        and return the first valid path found. If no valid path is found,
        it will return the original path.
        """

        # If the path is set and it's found on disk, return it directly
        if preset_path and os.path.exists(preset_path):
            return preset_path

        # We may have path for another platform, like C:/path/to/file
        # or a path with template keys, like {project[code]} or both.
        # Try to fill path with environments and anatomy roots
        project_name = get_current_project_name()
        anatomy = Anatomy(project_name)

        # Simple check whether the path contains any template keys
        if "{" in preset_path:
            fill_data = {
                key: value
                for key, value in os.environ.items()
            }
            fill_data["root"] = anatomy.roots
            fill_data["project"] = {
                "name": project_name,
                "code": anatomy.project_code,
            }
            # Add custom key for AYON bundled presets
            fill_data["ayon_render_presets"] = os.path.join(
                RESOLVE_ADDON_ROOT, "presets", "render")

            # Format the template using local fill data
            result = StringTemplate.format_template(preset_path, fill_data)
            if not result.solved:
                return preset_path

            preset_path = result.normalized()
            if os.path.exists(preset_path):
                return preset_path

        # If the path were set in settings using a Windows path and we
        # are now on a Linux system, we try to convert the solved path to
        # the current platform.
        while True:
            try:
                solved_path = anatomy.path_remapper(preset_path)
            except KeyError as missing_key:
                raise KeyError(
                    f"Could not solve key '{missing_key}'"
                    f" in template path '{preset_path}'"
                )

            if solved_path is None:
                solved_path = preset_path
            if solved_path == preset_path:
                break
            preset_path = solved_path

        solved_path = os.path.normpath(solved_path)
        return solved_path

    # ------------------------------------------------------------------
    # Product Base Type handlers
    # ------------------------------------------------------------------

    def _process_editorial_pkg(self, instance, settings, preset_path):
        """Render the active timeline and produce an intermediate representation."""
        folder_path = instance.data["folderPath"]
        timeline_mp_item = instance.data.get("mediaPoolItem")
        if timeline_mp_item is None:
            self.log.warning(
                "No mediaPoolItem on instance — cannot render editorial_pkg."
            )
            return

        timeline_name = timeline_mp_item.GetName()
        folder_path_name = folder_path.lstrip("/").replace("/", "_")
        staging_dir = os.path.normpath(
            os.path.join(
                self.staging_dir(instance),
                f"{folder_path_name}_{timeline_name}",
            )
        )
        self.log.info(f"Staging directory: {staging_dir}")

        with maintain_current_timeline(timeline_mp_item) as timeline:
            self.log.info(f"Rendering timeline: {timeline.GetName()}")
            rendered = render_timeline_intermediate_file(
                timeline,
                Path(staging_dir),
                preset_path,
                settings["file_format"],
                settings["codec"],
            )

        self.log.debug(f"Rendered output: {rendered}")

        representation = {
            "name":       settings["name"],
            "outputName": settings["name"],
            "tags":       settings.get("tags", []),
            "custom_tags": settings.get("custom_tags", []),
            "link_to_otio": True,
            "export_otio":   settings.get("export_otio", True),
            "otio_rootless": settings.get("otio_rootless", True),
        }
        # check if rendered is a list (multiple files) or a single file
        if isinstance(rendered, list):
            files = [file.name for file in rendered]
            representation.update({
                "ext":        rendered[0].suffix.lstrip(".").lower(),
                "files":      files,
                "stagingDir": str(rendered[0].parent),
                "frameStart": timeline.GetStartFrame(),
                "frameEnd":   timeline.GetEndFrame(),
            })
        else:
            representation.update({
                "ext":        rendered.suffix.lstrip(".").lower(),
                "files":      rendered.name,
                "stagingDir": str(rendered),
            })

        # attach colorspace to the representation
        if settings.get("colorspace"):
            colorspace = settings["colorspace"]
            self.set_representation_colorspace(
                representation, instance.context, colorspace)
            self.log.debug(f"Set colorspace: {colorspace}")

        instance.data["representations"].append(representation)
        self.log.info(
            f"Added intermediate representation: "
            f"{os.path.join(staging_dir, rendered_file.name)}"
        )

    def _process_plate(self, instance, settings, preset_path):
        """Render a single TimelineItem's frame range on the active timeline."""
        timeline_item = instance.data.get("timelineItem")
        if timeline_item is None:
            raise RuntimeError(
                "instance.data['timelineItem'] is required for 'plate' "
                "products, but was not found."
            )

        # Adjust handles - use track item handles if they are shorter
        # than expected instance handles.
        available_head = min(
            instance.data["handleStart"], timeline_item.GetLeftOffset())
        available_tail = min(
            instance.data["handleEnd"], timeline_item.GetRightOffset())
        clip_duration = int(timeline_item.GetDuration())
        self.log.info(
            "Available handles: start=%s, end=%s, clip_duration=%s",
            available_head, available_tail, clip_duration)

        frame_start = instance.data["frameStart"]

        with_handles = settings.get("with_handles", False)

        folder_slug = instance.data["folderPath"].lstrip("/").replace("/", "_")
        clip_name = timeline_item.GetName()
        staging_dir = (
            Path(self.staging_dir(instance)) / f"{folder_slug}_{clip_name}"
        )
        staging_dir.mkdir(parents=True, exist_ok=True)
        self.log.info(f"Staging directory: {staging_dir}")

        preset_data = {}
        if with_handles:
            preset_data.update({
                "NumFramesOfHandles": max(available_head, available_tail)
            })
            repre_frame_start = frame_start - available_head
            repre_frame_end = frame_start + available_tail + clip_duration - 1
        else:
            repre_frame_start = frame_start
            repre_frame_end = frame_start + clip_duration - 1

        # Modify preset file
        modified_preset_path = modify_preset_file(
            preset_path,
            Path(self.staging_dir(instance)),
            preset_data,
        )
        self.log.info(f"Modified preset path: {modified_preset_path}")

        with maintain_page_by_name("Deliver"):
            if not set_render_preset_from_file(modified_preset_path.as_posix()):
                raise RuntimeError(
                    f"Unable to load render preset: {modified_preset_path}"
                )

            format_ext = set_format_and_codec(
                settings["file_format"], settings["codec"]
            )
            if not format_ext:
                raise RuntimeError(
                    f"Unable to set render format '{settings['file_format']}' "
                    f"/ codec '{settings['codec']}'."
                )
            rendered = render_clip_to_intermediate_file(
                timeline_item, staging_dir
            )

        representation = {
            "name":       settings["name"],
            "outputName": settings["name"],
            "stagingDir": str(staging_dir),
            "tags":       settings.get("tags", []),
            "custom_tags": settings.get("custom_tags", []),
        }

        # check if rendered_file is folder and return first file
        if isinstance(rendered, list):
            files = [file.name for file in rendered]
            representation.update({
                "ext":        rendered[0].suffix.lstrip(".").lower(),
                "files":      files,
                "stagingDir": str(rendered[0].parent),
                "frameStart": repre_frame_start,
                "frameEnd":   repre_frame_end,
            })
        else:
            representation.update({
                "ext":        rendered.suffix.lstrip(".").lower(),
                "files":      rendered.name,
            })

        # attach colorspace to the representation
        if settings.get("colorspace"):
            colorspace = settings["colorspace"]
            self.set_representation_colorspace(
                representation, instance.context, colorspace)
            self.log.debug(f"Set colorspace: {colorspace}")

        self.log.debug(f"Representation: {pformat(representation)}")
        instance.data["representations"].append(representation)
        self.log.info(f"Added clip intermediate representation: {staging_dir}")
