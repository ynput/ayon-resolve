import json
import re
import opentimelineio as otio


def timecode_to_frames(timecode, framerate):
    rt = otio.opentime.from_timecode(timecode, 24)
    return int(otio.opentime.to_frames(rt))


def frames_to_timecode(frames, framerate):
    rt = otio.opentime.from_frames(frames, framerate)
    return otio.opentime.to_timecode(rt)


def frames_to_secons(frames, framerate):
    rt = otio.opentime.from_frames(frames, framerate)
    return otio.opentime.to_seconds(rt)


def get_reformated_path(path, padded=True, first=False):
    """
    Return fixed python expression path

    Args:
        path (str): path url or simple file name

    Returns:
        type: string with reformatted path

    Example:
        get_reformated_path("plate.[0001-1008].exr") > plate.%04d.exr

    """
    num_pattern = r"(\[\d+\-\d+\])"
    padding_pattern = r"(\d+)(?=-)"
    first_frame_pattern = re.compile(r"\[(\d+)\-\d+\]")

    if "[" in path:
        padding = len(re.findall(padding_pattern, path).pop())
        if padded:
            path = re.sub(num_pattern, f"%0{padding}d", path)
        elif first:
            first_frame = re.findall(first_frame_pattern, path, flags=0)
            if len(first_frame) >= 1:
                first_frame = first_frame[0]
            path = re.sub(num_pattern, first_frame, path)
        else:
            path = re.sub(num_pattern, "%d", path)
    return path


def get_padding_from_path(path):
    """
    Return padding number from DaVinci Resolve sequence path style

    Args:
        path (str): path url or simple file name

    Returns:
        int: padding number

    Example:
        get_padding_from_path("plate.[0001-1008].exr") > 4

    """
    padding_pattern = "(\\d+)(?=-)"
    if "[" in path:
        return len(re.findall(padding_pattern, path).pop())

    return None


def unwrap_resolve_otio_marker(marker):
    """
    Args:
        marker (opentimelineio.schema.Marker): The marker to unwrap.

    Returns:
        marker (opentimelineio.schema.Marker): Conformed marker.
    """
    # Resolve native OTIO exporter messes up the marker
    # dict metadata for some reasons.
    # {dict_info} -> {"Resolve_OTIO": {"Note": "string_dict_info"}}
    try:
        marker_note = marker.metadata["Resolve_OTIO"]["Note"]
    except KeyError:
        return marker

    marker_note_dict = json.loads(marker_note)
    marker.metadata.update(marker_note_dict)  # prevent additional resolve keys
    return marker


def get_marker_from_clip_index(otio_timeline, clip_index):
    """
    Args:
        otio_timeline (otio.Timeline): The otio timeline to inspect
        clip_index (int): The clip index metadata to retrieve.

    Returns:
        tuple(otio.Clip, otio.Marker): The associated clip and marker
            or (None, None)
    """
    try:  # opentimelineio >= 0.16.0
        all_clips = otio_timeline.find_clips()
    except AttributeError:  # legacy
        all_clips = otio_timeline.each_clip()

    # Retrieve otioClip from parent context otioTimeline
    # See collect_current_project
    for otio_clip in all_clips:
        for marker in otio_clip.markers:
            marker = unwrap_resolve_otio_marker(marker)
            if marker.metadata.get("clip_index") == clip_index:
                return  otio_clip, marker

    return None, None
