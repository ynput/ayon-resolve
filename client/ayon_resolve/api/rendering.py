"""
Rendering API wrapper for Blackmagic Design DaVinci Resolve.
"""
from __future__ import annotations

import contextlib
import io
import time
from pathlib import Path
from pprint import pformat
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from ayon_core.lib import Logger

from .lib import (
    get_current_resolve_project,
    maintain_current_timeline,
    maintain_page_by_name,
)

if TYPE_CHECKING:
    # Import the actual class here; it only runs during linting/type-checking
    from .utils import get_resolve_module
    resolve = get_resolve_module()

log = Logger.get_logger(__name__)


_SLEEP_TIME = 1
_PROCESSING_JOBS = []

# File extensions produced by Resolve that are image sequences (not containers)
_IMAGE_SEQUENCE_EXTS = frozenset({
    "exr", "dpx", "png", "tiff", "tif", "jpg", "jpeg", "cin",
})


def add_timeline_to_render(
    bmr_project,
    target_render_directory
):
    render_settings = {
        "SelectAllFrames": 1,
        "TargetDir": target_render_directory.as_posix(),
    }
    log.info(f"Render settings: {pformat(render_settings)}")

    bmr_project.SetRenderSettings(render_settings)
    return bmr_project.AddRenderJob()


def _render_timelines(timelines, target_render_directory):
    """Render timelines to target directory

    Args:
        timelines (list[resolve.Timeline]): List of Timeline objects
        target_render_directory (Path): Path to target render directory

    Returns:
        bool: True if all renders are successful, False otherwise
    """
    bmr_project = get_current_resolve_project()
    failed_timelines = []
    for timeline_to_render in timelines:
        with maintain_current_timeline(timeline_to_render):
            job_id = add_timeline_to_render(
                bmr_project,
                target_render_directory,
            )
        if job_id:
            # adding job id into list of processing
            # jobs in module constant list
            _PROCESSING_JOBS.append(job_id)
            log.info(f"Created render Job ID: {job_id}")
        else:
            failed_timelines.append(timeline_to_render.GetName())
    if len(failed_timelines) != len(timelines):
        bmr_project.StartRendering(_PROCESSING_JOBS, isInteractiveMode=False)
        wait_for_rendering_completion()
        delete_all_processed_jobs()
    if failed_timelines:
        log.error(f"Failed to render timelines: {failed_timelines}")
        return False
    log.info("Rendering is completed.")
    return True


def render_all_timelines(target_render_directory):
    """Render all of the timelines of current project.

    Args:
        target_render_directory (Path): Path to target render directory

    Returns:
        bool: True if all renders are successful, False otherwise
    """
    bmr_project = get_current_resolve_project()
    with maintain_page_by_name("Deliver"):
        timelineCount = bmr_project.GetTimelineCount()
        all_timelines = [
            bmr_project.GetTimelineByIndex(index + 1)
            for index in range(0, int(timelineCount))
        ]
        return _render_timelines(all_timelines, target_render_directory)


def render_single_timeline(timeline, target_render_directory):
    """Render single timeline

    Process is taking a defined timeline and render it to temporary
    intermediate file which will be lately used by Extract Review plugin
    for conversion to review file.

    Args:
        timeline (resolve.Timeline): Timeline object
        target_render_directory (Path): Path to target render directory

    Returns:
        bool: True if rendering is successful, False otherwise
    """
    return _render_timelines([timeline], target_render_directory)


def is_rendering_in_progress():
    """Check if rendering is in progress"""
    bmr_project = get_current_resolve_project()
    if not bmr_project:
        return False

    return bmr_project.IsRenderingInProgress()


def wait_for_rendering_completion():
    """Wait for rendering completion"""
    while is_rendering_in_progress():
        time.sleep(_SLEEP_TIME)
    return


def apply_drx_to_all_timeline_items(timeline, path, grade_mode=0):
    trackCount = timeline.GetTrackCount("video")

    clips = {}
    for index in range(1, int(trackCount) + 1):
        clips.update(timeline.GetItemsInTrack("video", index))
    return timeline.ApplyGradeFromDRX(path, int(grade_mode), clips)


def apply_drx_to_all_timelines(path, grade_mode=0):
    bmr_project = get_current_resolve_project()
    if not bmr_project:
        return False
    timelineCount = bmr_project.GetTimelineCount()

    for index in range(0, int(timelineCount)):
        timeline = bmr_project.GetTimelineByIndex(index + 1)
        bmr_project.SetCurrentTimeline(timeline)
        if not apply_drx_to_all_timeline_items(timeline, path, grade_mode):
            return False
    return True


def delete_all_processed_jobs():
    """Delete all processed jobs"""
    bmr_project = get_current_resolve_project()
    if not _PROCESSING_JOBS:
        return

    for job_id in _PROCESSING_JOBS:
        bmr_project.DeleteRenderJob(job_id)

    _PROCESSING_JOBS.clear()


@contextlib.contextmanager
def _solo_video_track(timeline_item):
    """Disable all video tracks except the one containing *timeline_item*.

    Saves the enabled state of every video track on the current timeline,
    disables all tracks that are not the clip's own track, ensures the
    clip's track is enabled, then restores every track to its original
    state on exit.  This prevents neighbouring clips on other tracks from
    being baked into a single-clip render job.

    If the timeline item does not live on a video track the context
    manager is a no-op.

    Args:
        timeline_item: A Resolve ``TimelineItem`` whose track should be
            the only active video track during the context.
    """
    bmr_project = get_current_resolve_project()
    timeline = bmr_project.GetCurrentTimeline()

    track_type, item_track_index = timeline_item.GetTrackTypeAndIndex()

    if track_type != "video":
        yield
        return

    track_count = int(timeline.GetTrackCount(track_type))
    original_states = {
        i: timeline.GetIsTrackEnabled(track_type, i)
        for i in range(1, track_count + 1)
    }

    with maintain_page_by_name("Edit"):
        # Disable every enabled video track that is not the clip's track.
        for i, enabled in original_states.items():
            if i != item_track_index and enabled:
                timeline.SetTrackEnable(track_type, i, False)

        # Guarantee the clip's own track is enabled.
        if not original_states.get(item_track_index):
            timeline.SetTrackEnable(track_type, item_track_index, True)

    try:
        yield
    finally:
        with maintain_page_by_name("Edit"):
            for i, was_enabled in original_states.items():
                if timeline.GetIsTrackEnabled(track_type, i) != was_enabled:
                    timeline.SetTrackEnable(track_type, i, was_enabled)


def render_clip_to_intermediate_file(
    timeline_item: resolve.TimelineItem,
    target_render_directory: Path
) -> Path | list[Path]:
    """Render a single TimelineItem's range on the currently active timeline.

    Uses the render settings already configured on the project (format, codec,
    preset). Caller is responsible for setting those up before calling this
    function (e.g. via ``set_render_preset_from_file`` and
    ``set_format_and_codec``).

    Args:
        timeline_item: A Resolve ``TimelineItem`` object from the active timeline.
        target_render_directory (Path): Directory where rendered files are written.

    Returns:
        Path: Single file path for container formats (QuickTime, MXF, …).
        list[Path]: Sorted list of frame paths for image sequences (EXR, DPX, …).

    Raises:
        RuntimeError: If the render job cannot be created, started, or completes
            with a non-"Complete" status, or if no output files are found.
    """
    bmr_project = get_current_resolve_project()
    media_pool_item = timeline_item.GetMediaPoolItem()

    render_settings = {
        "SelectAllFrames": False,
        "MarkIn":    timeline_item.GetStart(),
        "MarkOut":   timeline_item.GetEnd() - 1,
        "TargetDir": target_render_directory.as_posix(),
        "CustomName": timeline_item.GetName(),
        "FrameRate": float(media_pool_item.GetClipProperty("FPS")),
    }
    log.info(f"Clip render settings: {pformat(render_settings)}")

    if not bmr_project.SetRenderSettings(render_settings):
        raise RuntimeError("SetRenderSettings failed for clip render.")

    with _solo_video_track(timeline_item):
        job_id = bmr_project.AddRenderJob()
        if not job_id:
            raise RuntimeError("AddRenderJob failed for clip render.")

        log.info(f"Clip render job created: {job_id}")
        try:
            if not bmr_project.StartRendering([job_id], isInteractiveMode=False):
                raise RuntimeError(f"StartRendering failed for job '{job_id}'.")
            wait_for_rendering_completion()

            status = bmr_project.GetRenderJobStatus(job_id)
            if status.get("JobStatus") != "Complete":
                raise RuntimeError(
                    f"Clip render job '{job_id}' did not complete: {status}"
                )
        finally:
            log.info(f"Deleting clip render job: {job_id}")
            bmr_project.DeleteRenderJob(job_id)

    # Collect all rendered files, handling two layouts:
    #   1. Flat:   target_render_directory/*.<ext>
    #   2. Nested: target_render_directory/**/*.<ext>
    #              (files may live inside one or more levels of sub-folders)
    rendered = sorted(
        f for f in target_render_directory.rglob("*") if f.is_file()
    )
    if not rendered:
        msg = f"No rendered files found in '{target_render_directory}'."
        raise RuntimeError(msg)

    if rendered[0].suffix.lstrip(".").lower() in _IMAGE_SEQUENCE_EXTS:
        log.info("Clip rendered as image sequence: %d frames", len(rendered))
        return rendered  # list[Path]

    log.info("Clip rendered as single file: %s", rendered[0])
    return rendered[0]  # Path



def set_render_preset_from_file(preset_file_path):
    from . import bmdvr

    bmr_project = get_current_resolve_project()
    preset_path = Path(preset_file_path)

    # make sure the file exists
    if not preset_path.exists():
        log.error(f"File not found: {preset_file_path}")
        return

    # get only the file name without extension
    preset_name = preset_path.stem

    # check if the render preset already exists
    if bmr_project.LoadRenderPreset(preset_name):
        delete_preset = bmr_project.DeleteRenderPreset(preset_name)
        log.info(f"Deleted already existing preset: {delete_preset}")

    log.info(
        "Render preset does not exists. "
        f"Creating new render preset: '{preset_name}'"
    )
    return bmdvr.ImportRenderPreset(preset_path.as_posix())



def set_format_and_codec(render_format, render_codec):
    bmr_project = get_current_resolve_project()

    available_render_formats = bmr_project.GetRenderFormats()
    log.debug(f"Available formats: {pformat(available_render_formats)}")

    # get render format value from key
    render_format_val = available_render_formats.get(render_format)
    if not render_format_val:
        log.error(f"Invalid render format: '{render_format}'")
        return False

    available_render_codecs = bmr_project.GetRenderCodecs(render_format_val)
    log.debug(
        f"Available codecs for format '{render_format_val}': "
        f"{pformat(available_render_codecs)}"
    )

    # get render codec value from key
    render_codec_val = available_render_codecs.get(render_codec)
    if not render_codec_val:
        log.error(f"Invalid render codec: '{render_codec}'")
        return False

    if not bmr_project.SetCurrentRenderFormatAndCodec(
        render_format_val, render_codec_val
    ):
        log.error(
            f"Failed to set render format '{render_format}' "
            f"and codec '{render_codec}'"
        )
        return False

    return render_format_val


def render_timeline_intermediate_file(
    timeline: resolve.Timeline,
    target_render_directory: Path,
    preset_path: Path,
    file_format: str,
    codec: str,
) -> Path | list[Path]:
    """Render *timeline* to an intermediate file in *target_render_directory*.

    Args:
        timeline: Active Resolve Timeline object.
        target_render_directory (Path): Staging directory for the output.
        preset_path (Path): Path to the render preset XML file.
        file_format (str): Resolve format name (e.g. ``"QuickTime"``).
        codec (str): Resolve codec name (e.g. ``"H.264"``).

    Returns:
        Path: Path to the rendered file.
        list[Path]: List of paths to the rendered files.

    Raises:
        RuntimeError: If the render preset cannot be loaded, the format and codec
            cannot be set, or the timeline cannot be rendered.
    """
    log.info(f"Rendering timeline to '{target_render_directory}'")

    with maintain_page_by_name("Deliver"):
        if not set_render_preset_from_file(preset_path.as_posix()):
            raise RuntimeError("Unable to load render preset.")

        format_extension = set_format_and_codec(file_format, codec)
        if not format_extension:
            raise RuntimeError("Unable to set render format and codec.")

        if not render_single_timeline(timeline, target_render_directory):
            raise RuntimeError("Unable to render timeline.")

    # Collect all files matching the format extension, handling two layouts:
    #   1. Flat:   target_render_directory/*.{format_extension}
    #   2. Nested: target_render_directory/**/*.{format_extension}
    #              (files may live inside one or more levels of sub-folders)
    rendered_files = sorted(
        target_render_directory.rglob(f"*.{format_extension}")
    )
    if not rendered_files:
        msg = (
            f"No rendered files with extension '{format_extension}' found "
            f"in '{target_render_directory}'."
        )
        raise RuntimeError(msg)

    if len(rendered_files) > 1:
        return rendered_files

    return rendered_files[0]


def _extract_prolog(text: str) -> str:
    """Return the XML prolog — everything before the root element.

    Consumed tokens: whitespace, ``<?...?>`` processing instructions (including
    the XML declaration), and ``<!--...-->`` comments.  Stops at the first
    character that could start a real element tag.

    Python's :mod:`xml.etree.ElementTree` silently drops prolog-level comments
    when parsing.  Extracting the prolog as raw text lets ``modify_preset_file``
    re-attach it to the written output so nothing is lost.
    """
    pos = 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
        elif text[pos:pos + 2] == "<?":
            end = text.find("?>", pos)
            pos = end + 2
        elif text[pos:pos + 4] == "<!--":
            end = text.find("-->", pos)
            pos = end + 3
        else:
            break
    return text[:pos]


def modify_preset_file(
    xml_path: Path,
    staging_dir: Path,
    data: dict,
) -> Path:
    """Copy *xml_path* to *staging_dir* and apply *data* overrides.

    Each key in *data* is either a bare element tag name (e.g.
    ``"NumFramesOfHandles"``) or a slash-separated path expression (e.g.
    ``"Parent/Child"``).

    * **Bare name** – every matching element in the document is updated.
    * **Path** – the leaf element at the given path is updated; if absent
      it is created as the first child of its parent element.

    Args:
        xml_path (Path): Source XML preset file.
        staging_dir (Path): Directory where the modified copy is written.
        data (dict): Mapping of XML tag / path → new text value.

    Returns:
        Path: Path to the modified copy of the preset in *staging_dir*.

    Raises:
        AttributeError: Logged as a warning when a bare tag is not found.
    """
    temp_path = staging_dir / xml_path.name

    # Read raw text upfront so we can extract the prolog (XML declaration +
    # any prolog-level comments).  Python's ElementTree parser drops prolog
    # comments silently; we preserve them by re-attaching the prolog to the
    # written output.
    raw_text = xml_path.read_text(encoding="utf-8")
    prolog = _extract_prolog(raw_text)

    # insert_comments=True preserves comments that live *inside* elements.
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    tree = ET.parse(xml_path, parser=parser)

    for key, value in data.items():
        log.debug(f"Setting {key} to {value}")
        try:
            if "/" in key:
                # Normalise to a descendant XPath expression.
                xpath = key if key.startswith("./") else f".//{key}"

                *parent_parts, leaf = xpath.split("/")
                parent_path = "/".join(parent_parts)

                parent = tree.find(parent_path)
                element = parent.find(leaf)
                if element is None:
                    _append_element(parent, leaf, value)
                else:
                    log.debug(f"Setting string 1 {key} to {value}")
                    element.text = str(value)
            else:
                elements = tree.findall(f".//{key}")
                if not elements:
                    raise AttributeError(key)
                for element in elements:
                    log.debug(f"Setting string 2 {key} to {value}")
                    element.text = str(value)
        except AttributeError:
            log.warning(f"Cannot set '{key}': tag not found. Skipping.")

    # Write the modified element tree as unicode text (no xml_declaration —
    # the original prolog, which already contains the declaration and any
    # prolog-level comments, is prepended directly).
    buf = io.StringIO()
    tree.write(buf, encoding="unicode", xml_declaration=False)
    temp_path.write_text(prolog + buf.getvalue(), encoding="utf-8")

    return temp_path


def _append_element(parent: ET.Element, tag: str, value) -> None:
    """Insert a new *tag* element with *value* as the first child of *parent*."""
    element = ET.Element(tag)
    element.text = str(value)
    parent.insert(0, element)
    log.debug(f"Appended new XML element <{tag}> = {value!r}")
