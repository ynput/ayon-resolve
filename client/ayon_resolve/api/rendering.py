"""
Rendering API wrapper for Blackmagic Design DaVinci Resolve.
"""

import time
from pathlib import Path
from pprint import pformat

from ayon_core.lib import Logger

from .lib import (
    get_current_project,
    maintain_current_timeline,
    maintain_page_by_name,
)

log = Logger.get_logger(__name__)


_SLEEP_TIME = 1
_PROCESSING_JOBS = []


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
    bmr_project = get_current_project()
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
        bmr_project.StartRendering()
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
    bmr_project = get_current_project()
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
    bmr_project = get_current_project()
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
    bmr_project = get_current_project()
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
    bmr_project = get_current_project()
    if not _PROCESSING_JOBS:
        return

    for job_id in _PROCESSING_JOBS:
        bmr_project.DeleteRenderJob(job_id)

    _PROCESSING_JOBS.clear()


def set_render_preset_from_file(preset_file_path):
    from . import bmdvr

    bmr_project = get_current_project()
    preset_path = Path(preset_file_path)

    # make sure the file exists
    if not preset_path.exists():
        log.error(f"File not found: {preset_file_path}")
        return

    # get only the file name without extension
    preset_name = preset_path.stem

    # check if the render preset already exists
    if not bmr_project.LoadRenderPreset(preset_name):
        log.info(
            "Render preset does not exists. "
            f"Creating new render preset: '{preset_name}'"
        )
        return bmdvr.ImportRenderPreset(preset_path.as_posix())

    return True


def set_format_and_codec(render_format, render_codec):
    bmr_project = get_current_project()

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
