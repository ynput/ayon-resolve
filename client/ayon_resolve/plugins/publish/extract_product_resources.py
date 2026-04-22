import os
from pathlib import Path

import pyblish.api

from ayon_core.pipeline import Anatomy, get_current_project_name, publish
from ayon_core.pipeline.context_tools import get_current_task_entity

from ayon_core.lib import StringTemplate, filter_profiles

from ayon_resolve.api.lib import maintain_current_timeline, maintain_page_by_name
from ayon_resolve.api.rendering import (
    set_render_preset_from_file,
    render_single_timeline,
    set_format_and_codec,
    render_clip_to_intermediate_file,
)

from ayon_resolve.utils import RESOLVE_ADDON_ROOT


class ExtractProductResources(publish.Extractor):
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

        if product_base_type == "editorial_pkg":
            self._process_editorial_pkg(instance, settings, preset_path)
        elif product_base_type == "clip":
            self._process_clip(instance, settings, preset_path)
        else:
            self.log.warning(
                f"ExtractProductResources: unhandled family '{product_base_type}', skipping."
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
        }
        if product_base_type == "editorial_pkg":
            normalized["export_otio"]   = sub.get("export_otio")
            normalized["otio_rootless"] = sub.get("otio_rootless")
        return normalized

    def get_default_settings(self, product_base_type="editorial_pkg"):
        """Return hard-coded defaults when no matching preset is found."""
        if product_base_type == "clip":
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
            rendered_file = self.render_timeline_intermediate_file(
                timeline,
                Path(staging_dir),
                preset_path,
                settings["file_format"],
                settings["codec"],
            )

        self.log.debug(f"Rendered file: {rendered_file}")
        representation = {
            "name":       settings["name"],
            "ext":        os.path.splitext(rendered_file)[1][1:],
            "files":      rendered_file.name,
            "stagingDir": staging_dir,
            "tags":       ["review", "delete"],
            "custom_tags": ["intermediate"],
            "export_otio":   settings.get("export_otio", True),
            "otio_rootless": settings.get("otio_rootless", True),
        }
        instance.data["representations"].append(representation)
        self.log.info(
            f"Added intermediate representation: "
            f"{os.path.join(staging_dir, rendered_file.name)}"
        )

    def _process_clip(self, instance, settings, preset_path):
        """Render a single TimelineItem's frame range on the active timeline."""
        timeline_item = instance.data.get("timelineItem")
        if timeline_item is None:
            raise RuntimeError(
                "instance.data['timelineItem'] is required for 'clip' family "
                "but was not found."
            )

        folder_slug = instance.data["folderPath"].lstrip("/").replace("/", "_")
        clip_name = timeline_item.GetName()
        staging_dir = (
            Path(self.staging_dir(instance)) / f"{folder_slug}_{clip_name}"
        )
        staging_dir.mkdir(parents=True, exist_ok=True)
        self.log.info(f"Staging directory: {staging_dir}")

        with maintain_page_by_name("Deliver"):
            if not set_render_preset_from_file(preset_path.as_posix()):
                raise RuntimeError(
                    f"Unable to load render preset: {preset_path}"
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

        if isinstance(rendered, list):
            representation = {
                "name":       settings["name"],
                "ext":        rendered[0].suffix.lstrip("."),
                "files":      [f.name for f in rendered],
                "stagingDir": str(staging_dir),
                "tags":       ["review"],
                "custom_tags": ["intermediate"],
                "frameStart": timeline_item.GetStart(),
                "frameEnd":   timeline_item.GetEnd(),
            }
        else:
            representation = {
                "name":       settings["name"],
                "ext":        rendered.suffix.lstrip("."),
                "files":      rendered.name,
                "stagingDir": str(staging_dir),
                "tags":       ["review"],
                "custom_tags": ["intermediate"],
            }

        instance.data["representations"].append(representation)
        self.log.info(f"Added clip intermediate representation: {staging_dir}")

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def render_timeline_intermediate_file(
        self,
        timeline,
        target_render_directory,
        preset_path,
        file_format,
        codec,
    ):
        """Render *timeline* to an intermediate file in *target_render_directory*.

        Args:
            timeline: Active Resolve Timeline object.
            target_render_directory (Path): Staging directory for the output.
            preset_path (Path): Path to the render preset XML file.
            file_format (str): Resolve format name (e.g. ``"QuickTime"``).
            codec (str): Resolve codec name (e.g. ``"H.264"``).

        Returns:
            Path: Path to the rendered file.
        """
        self.log.info(f"Rendering timeline to '{target_render_directory}'")

        with maintain_page_by_name("Deliver"):
            if not set_render_preset_from_file(preset_path.as_posix()):
                raise RuntimeError("Unable to load render preset.")

            format_extension = set_format_and_codec(file_format, codec)
            if not format_extension:
                raise RuntimeError("Unable to set render format and codec.")

            if not render_single_timeline(timeline, target_render_directory):
                raise RuntimeError("Unable to render timeline.")

        rendered_files = list(
            target_render_directory.glob(f"*.{format_extension}")
        )
        if not rendered_files:
            raise RuntimeError("No rendered files found.")

        return rendered_files[0]
