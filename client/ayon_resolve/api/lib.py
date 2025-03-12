import re
import os
import json
import uuid
import contextlib
import tempfile
from typing import List, Dict, Any

import opentimelineio as otio

from ayon_core.lib import Logger
from ayon_core.pipeline.editorial import (
    is_overlapping_otio_ranges,
    frames_to_timecode
)
from ayon_core.pipeline.context_tools import (
    get_current_project_name,
    get_current_task_entity
)
from ayon_core.pipeline.tempdir import create_custom_tempdir

from . import constants
from ..otio import davinci_export as otio_export

log = Logger.get_logger(__name__)


def get_timeline_media_pool_item(timeline, root=None) -> object:
    """Return MediaPoolItem from Timeline


    Args:
        timeline (resolve.Timeline): timeline object
        root (resolve.Folder): root folder / bin object

    Returns:
        resolve.MediaPoolItem: media pool item from timeline
    """

    # Due to limitations in the Resolve API we can't get
    # the media pool item directly from the timeline.
    # We can find it by name, however names are not
    # enforced to be unique across bins. So, we give it
    # unique name.
    original_name = timeline.GetName()
    identifier = str(uuid.uuid4().hex)
    try:
        timeline.SetName(identifier)
        for item in iter_all_media_pool_clips(root=root):
            if item.GetName() != identifier:
                continue
            return item
    finally:
        # Revert to original name
        timeline.SetName(original_name)


@contextlib.contextmanager
def maintain_current_timeline(to_timeline: object,
                              from_timeline: object = None):
    """Maintain current timeline selection during context

    Attributes:
        from_timeline (resolve.Timeline)[optional]:
    Example:
        >>> print(from_timeline.GetName())
        timeline1
        >>> print(to_timeline.GetName())
        timeline2

        >>> with maintain_current_timeline(to_timeline):
        ...     print(get_current_timeline().GetName())
        timeline2

        >>> print(get_current_timeline().GetName())
        timeline1
    """
    project = get_current_resolve_project()
    working_timeline = from_timeline or project.GetCurrentTimeline()

    # search timeline withing project timelines in case the
    # to_timeline is MediaPoolItem
    # Note: this is a hacky way of identifying if object is timeline since
    #   mediapool item is not having AddTrack attribute. API is not providing
    #   any other way to identify the object type. And hasattr is returning
    #   false info.
    if "AddTrack" not in dir(to_timeline):
        tcount = project.GetTimelineCount()
        for idx in range(0, int(tcount)):
            timeline = project.GetTimelineByIndex(idx + 1)
            if timeline.GetName() == to_timeline.GetName():
                to_timeline = timeline
                break

    try:
        # switch to the input timeline
        result = project.SetCurrentTimeline(to_timeline)
        if not result:
            raise ValueError(f"Failed to switch to timeline: {to_timeline}")

        current_timeline = project.GetCurrentTimeline()
        yield current_timeline
    finally:
        # put the original working timeline to context
        project.SetCurrentTimeline(working_timeline)


@contextlib.contextmanager
def maintain_page_by_name(page_name):
    """Maintain specific page by name.

    Args:
        page_name (str): name of the page

    Example:
        >>> with maintain_page_by_name("Deliver"):
        ...     print("Deliver page is open")
        Deliver page is open
    """
    from . import bmdvr
    current_page = bmdvr.GetCurrentPage()

    if not bmdvr.OpenPage(page_name):
        raise ValueError(f"Could not open page {page_name}")

    try:
        yield
    finally:
        bmdvr.OpenPage(current_page)


def get_project_manager():
    """Get project manager object.

    Returns:
        resolve.ProjectManager
    """
    from . import bmdvr, project_manager
    if not project_manager:
        project_manager = bmdvr.GetProjectManager()

    return project_manager


def get_media_storage():
    """Get media storage object.

    Returns:
        resolve.MediaStorage
    """
    from . import bmdvr, media_storage
    if not media_storage:
        media_storage = bmdvr.GetMediaStorage()
    return media_storage


def get_current_resolve_project():
    """Get current resolve project object.

    Returns:
        resolve.Project
    """
    project_manager = get_project_manager()
    return project_manager.GetCurrentProject()

# alias for backward compatibility
get_current_project = get_current_resolve_project


def get_current_timeline(new=False):
    """Get current timeline object.

    Args:
        new (bool)[optional]: [DEPRECATED] if True it will create
            new timeline if none exists

    Returns:
        object | None: resolve.Timeline
    """
    resolve_project = get_current_resolve_project()
    timeline = resolve_project.GetCurrentTimeline()

    # return current timeline if any
    if timeline:
        return timeline

    # TODO: [deprecated] and will be removed in future
    if new:
        return get_new_timeline()


def get_any_timeline():
    """Get any timeline object.

    Returns:
        object | None: resolve.Timeline
    """
    resolve_project = get_current_resolve_project()
    timeline_count = resolve_project.GetTimelineCount()
    if timeline_count > 0:
        return resolve_project.GetTimelineByIndex(1)


def get_new_timeline(timeline_name: str = None):
    """Get new timeline object.

    Arguments:
        timeline_name (str): New timeline name.

    Returns:
        object: resolve.Timeline
    """
    resolve_project = get_current_resolve_project()
    media_pool = resolve_project.GetMediaPool()
    new_timeline = media_pool.CreateEmptyTimeline(
        timeline_name or constants.AYON_TIMELINE_NAME)
    resolve_project.SetCurrentTimeline(new_timeline)
    return new_timeline


def create_bin(name: str,
               root: object = None,
               set_as_current: bool = True) -> object:
    """
    Create media pool's folder.

    Return folder object and if the name does not exist it will create a new.
    If the input name is with forward or backward slashes then it will create
    all parents and return the last child bin object

    Args:
        name (str): name of folder / bin, or hierarchycal name "parent/name"
        root (resolve.Folder)[optional]: root folder / bin object
        set_as_current (resolve.Folder)[optional]: Whether to set the
            resulting bin as current folder or not.

    Returns:
        object: resolve.Folder
    """
    # get all variables
    media_pool = get_current_resolve_project().GetMediaPool()
    root_bin = root or media_pool.GetRootFolder()

    # create hierarchy of bins in case there is slash in name
    if "/" in name.replace("\\", "/"):
        child_bin = None
        for bname in name.split("/"):
            child_bin = create_bin(bname,
                                   root=child_bin or root_bin,
                                   set_as_current=set_as_current)
        if child_bin:
            return child_bin
    else:
        # Find existing folder or create it
        for subfolder in root_bin.GetSubFolderList():
            if subfolder.GetName() == name:
                created_bin = subfolder
                break
        else:
            created_bin = media_pool.AddSubFolder(root_bin, name)

        if set_as_current:
            media_pool.SetCurrentFolder(created_bin)

        return created_bin


def remove_media_pool_item(media_pool_item: object) -> bool:
    """Remove media pool item.

    Args:
        media_pool_item (resolve.MediaPoolItem): resolve's object

    Returns:
        bool: True if success
    """
    resolve_project = get_current_resolve_project()
    media_pool = resolve_project.GetMediaPool()
    return media_pool.DeleteClips([media_pool_item])


def create_media_pool_item(files: list,
                           root: object = None) -> object:
    """ Create media pool item.

    Args:
        files (list): absolute path to a file
        root (resolve.Folder)[optional]: root folder / bin object

    Returns:
        object: resolve.MediaPoolItem
    """
    # get all variables
    resolve_project = get_current_resolve_project()
    media_pool = resolve_project.GetMediaPool()
    root_bin = root or media_pool.GetRootFolder()

    # make sure files list is not empty and first available file exists
    filepath = next((f for f in files if os.path.isfile(f)), None)
    if not filepath:
        raise FileNotFoundError("No file found in input files list")

    # try to search in bin if the clip does not exist
    existing_mpi = get_media_pool_item(filepath, root_bin)

    if existing_mpi:
        return existing_mpi

    # add media to media-pool
    media_pool_items = media_pool.ImportMedia(files)

    if not media_pool_items:
        return False

    # return only first found
    return media_pool_items.pop()


def get_media_pool_item(filepath, root: object = None) -> object:
    """
    Return clip if found in folder with use of input file path.

    Args:
        filepath (str): absolute path to a file
        root (resolve.Folder)[optional]: root folder / bin object

    Returns:
        object: resolve.MediaPoolItem
    """
    resolve_project = get_current_resolve_project()
    media_pool = resolve_project.GetMediaPool()
    root = root or media_pool.GetRootFolder()
    fname = os.path.basename(filepath)

    for _mpi in root.GetClipList():
        _mpi_name = _mpi.GetClipProperty("File Name")
        _mpi_name = get_reformated_path(_mpi_name, first=True)
        if fname in _mpi_name:
            return _mpi
    return None


def create_timeline_item(
        media_pool_item: object,
        timeline: object = None,
        timeline_in: int = None,
        source_start: int = None,
        source_end: int = None,
) -> object:
    """
    Add media pool item to current or defined timeline.

    Args:
        media_pool_item (resolve.MediaPoolItem): resolve's object
        timeline (Optional[resolve.Timeline]): resolve's object
        timeline_in (Optional[int]): timeline input frame (sequence frame)
        source_start (Optional[int]): media source input frame (sequence frame)
        source_end (Optional[int]): media source output frame (sequence frame)

    Returns:
        object: resolve.TimelineItem
    """
    # get all variables
    resolve_project = get_current_resolve_project()
    media_pool = resolve_project.GetMediaPool()
    clip_name = media_pool_item.GetClipProperty("File Name")
    timeline = timeline or get_current_timeline()

    # timing variables
    if all([
        timeline_in is not None,
        source_start is not None,
        source_end is not None
    ]):
        fps = timeline.GetSetting("timelineFrameRate")
        duration = source_end - source_start
        timecode_in = frames_to_timecode(timeline_in, fps)
        timecode_out = frames_to_timecode(timeline_in + duration, fps)
    else:
        timecode_in = None
        timecode_out = None

    # if timeline was used then switch it to current timeline
    with maintain_current_timeline(timeline):
        # Add input mediaPoolItem to clip data
        clip_data = {
            "mediaPoolItem": media_pool_item,
        }

        if source_start:
            clip_data["startFrame"] = source_start
        if source_end:
            clip_data["endFrame"] = source_end
        if timecode_in:
            # Note: specifying a recordFrame will fail to place the timeline
            #  item if there's already an existing clip at that time on the
            #  active track.
            clip_data["recordFrame"] = timeline_in

        # add to timeline
        output_timeline_item = media_pool.AppendToTimeline([clip_data])[0]

        # Adding the item may fail whilst Resolve will still return a
        # TimelineItem instance - however all `Get*` calls return None
        # Hence, we check whether the result is valid
        if output_timeline_item.GetDuration() is None:
            output_timeline_item = None

    assert output_timeline_item, AssertionError((
        "Clip name '{}' wasn't created on the timeline: '{}' \n\n"
        "Please check if correct track position is activated, \n"
        "or if a clip is not already at the timeline in \n"
        "position: '{}' out: '{}'. \n\n"
        "Clip data: {}"
    ).format(
        clip_name, timeline.GetName(), timecode_in, timecode_out, clip_data
    ))
    return output_timeline_item


def get_timeline_item(media_pool_item: object,
                      timeline: object = None) -> object:
    """
    Returns clips related to input mediaPoolItem.

    Args:
        media_pool_item (resolve.MediaPoolItem): resolve's object
        timeline (resolve.Timeline)[optional]: resolve's object

    Returns:
        object: resolve.TimelineItem
    """
    clip_name = media_pool_item.GetClipProperty("File Name")
    output_timeline_item = None
    timeline = timeline or get_current_timeline()

    with maintain_current_timeline(timeline):
        # search the timeline for the added clip

        for ti_data in get_current_timeline_items():
            ti_clip_item = ti_data["clip"]["item"]
            ti_media_pool_item = ti_clip_item.GetMediaPoolItem()

            # Skip items that do not have a media pool item, like for example
            # an "Adjustment Clip" or a "Fusion Composition" from the effects
            # toolbox
            if not ti_media_pool_item:
                continue

            if clip_name in ti_media_pool_item.GetClipProperty("File Name"):
                output_timeline_item = ti_clip_item

    return output_timeline_item


def get_video_track_names() -> list:
    timeline = get_current_timeline()
    if not timeline:
        return []

    track_type = "video"

    # get all tracks count filtered by track type
    selected_track_count = timeline.GetTrackCount(track_type)

    # loop all tracks and get items
    tracks = []
    for track_index in range(1, (int(selected_track_count) + 1)):
        track_name = timeline.GetTrackName("video", track_index)
        tracks.append(track_name)

    return tracks


def get_current_timeline_items(
        filter: bool = False,
        track_type: str = None,
        track_name: str = None,
        selecting_color: str = None) -> List[Dict[str, Any]]:
    """Get all available current timeline track items"""
    track_type = track_type or "video"
    selecting_color = selecting_color or constants.SELECTED_CLIP_COLOR
    resolve_project = get_current_resolve_project()

    # get timeline anyhow
    timeline = get_current_timeline() or get_any_timeline()
    if not timeline:
        return []

    selected_clips = []

    # get all tracks count filtered by track type
    selected_track_count = timeline.GetTrackCount(track_type)

    # loop all tracks and get items
    _clips = {}
    for track_index in range(1, (int(selected_track_count) + 1)):
        _track_name = timeline.GetTrackName(track_type, track_index)

        # filter out all unmatched track names
        if track_name and _track_name not in track_name:
            continue

        timeline_items = timeline.GetItemListInTrack(track_type, track_index)
        _clips[track_index] = timeline_items

        _data = {
            "project": resolve_project,
            "timeline": timeline,
            "track": {
                "name": _track_name,
                "index": track_index,
                "type": track_type}
        }
        # get track item object and its color
        for clip_index, ti in enumerate(_clips[track_index]):
            data = _data.copy()
            data["clip"] = {
                "item": ti,
                "index": clip_index
            }
            ti_color = ti.GetClipColor()
            if filter and selecting_color in ti_color or not filter:
                selected_clips.append(data)
    return selected_clips


def get_timeline_item_by_name(name: str) -> object:
    """Get timeline item by name.

    Args:
        name (str): name of timeline item

    Returns:
        object: resolve.TimelineItem
    """
    for _ti_data in get_current_timeline_items():
        _ti_clip = _ti_data["clip"]["item"]
        tag_data = get_timeline_item_pype_tag(_ti_clip)
        tag_name = tag_data.get("namespace")
        if not tag_name:
            continue
        if tag_name in name:
            return _ti_clip
    return None


# alias for backward compatibility
get_pype_timeline_item_by_name = get_timeline_item_by_name


def get_timeline_item_ayon_tag(timeline_item):
    """
    Get ayon track item tag created by creator or loader plugin.

    Attributes:
        trackItem (resolve.TimelineItem): resolve object

    Returns:
        dict: ayon tag data
    """
    return_tag = None

    if constants.AYON_MARKER_WORKFLOW:
        return_tag = get_ayon_marker(timeline_item)
    else:
        media_pool_item = timeline_item.GetMediaPoolItem()

        # get all tags from track item
        _tags = media_pool_item.GetMetadata()
        if not _tags:
            return None
        for key, data in _tags.items():
            # return only correct tag defined by global name
            if key in constants.AYON_TAG_NAME:
                return_tag = json.loads(data)

    return return_tag

# alias for backward compatibility
get_timeline_item_pype_tag = get_timeline_item_ayon_tag


def set_timeline_item_ayon_tag(timeline_item, data=None):
    """
    Set ayon track item tag to input timeline_item.

    Attributes:
        trackItem (resolve.TimelineItem): resolve api object

    Returns:
        dict: json loaded data
    """
    data = data or {}

    # get available ayon tag if any
    tag_data = get_timeline_item_ayon_tag(timeline_item)

    if constants.AYON_MARKER_WORKFLOW:
        # delete tag as it is not updatable
        if tag_data:
            delete_ayon_marker(timeline_item)

        tag_data.update(data)
        set_ayon_marker(timeline_item, tag_data)
    else:
        if tag_data:
            media_pool_item = timeline_item.GetMediaPoolItem()
            # it not tag then create one
            tag_data.update(data)
            media_pool_item.SetMetadata(
                constants.AYON_TAG_NAME, json.dumps(tag_data))
        else:
            tag_data = data
            # if ayon tag available then update with input data
            # add it to the input track item
            timeline_item.SetMetadata(
                constants.AYON_TAG_NAME, json.dumps(tag_data))

    return tag_data


# alias for backward compatibility
set_timeline_item_pype_tag = set_timeline_item_ayon_tag


def imprint(timeline_item, data=None):
    """
    Adding `Ayon data` into a timeline item track item tag.

    Also including publish attribute into tag.

    Arguments:
        timeline_item (resolve.TimelineItem): resolve's object
        data (dict): Any data which needs to be imprinted

    Examples:
        data = {
            'asset': 'sq020sh0280',
            'family': 'render',
            'subset': 'subsetMain'
        }
    """
    data = data or {}

    set_timeline_item_ayon_tag(timeline_item, data)

    # add publish attribute
    set_publish_attribute(timeline_item, True)


def set_publish_attribute(timeline_item, value):
    """ Set Publish attribute to marker on timeline item

    Attribute:
        timeline_item (resolve.TimelineItem): resolve's object
    """
    tag_data = get_timeline_item_ayon_tag(timeline_item)
    tag_data["publish"] = value
    # set data to the publish attribute
    set_timeline_item_ayon_tag(timeline_item, tag_data)


def get_publish_attribute(timeline_item):
    """ Get Publish attribute from marker on timeline item

    Attribute:
        timeline_item (resolve.TimelineItem): resolve's object
    """
    tag_data = get_timeline_item_ayon_tag(timeline_item)
    return tag_data["publish"]


def set_ayon_marker(timeline_item, tag_data):
    source_start = timeline_item.GetLeftOffset()
    item_duration = timeline_item.GetDuration()
    frame = int(source_start + (item_duration / 2))

    # marker attributes
    frameId = (frame / 10) * 10
    color = constants.AYON_MARKER_COLOR
    name = constants.AYON_MARKER_NAME
    note = json.dumps(tag_data)
    duration = (constants.AYON_MARKER_DURATION / 10) * 10

    timeline_item.AddMarker(
        frameId,
        color,
        name,
        note,
        duration
    )


def get_ayon_marker(timeline_item, tag_name=constants.AYON_MARKER_NAME):
    timeline_item_markers = timeline_item.GetMarkers() or []
    for marker_frame in timeline_item_markers:
        note = timeline_item_markers[marker_frame]["note"]
        color = timeline_item_markers[marker_frame]["color"]
        name = timeline_item_markers[marker_frame]["name"]
        print(f"_ marker data: {marker_frame} | {name} | {color} | {note}")
        if (
            name == tag_name
            and color == constants.AYON_MARKER_COLOR
        ):
            constants.TEMP_MARKER_FRAME = marker_frame
            return json.loads(note)

    return {}


def delete_ayon_marker(timeline_item):
    timeline_item.DeleteMarkerAtFrame(constants.TEMP_MARKER_FRAME)
    constants.TEMP_MARKER_FRAME = None


def create_compound_clip(clip_data, name, folder):
    """
    Convert timeline object into nested timeline object

    Args:
        clip_data (dict): timeline item object packed into dict
                          with project, timeline (sequence)
        folder (resolve.MediaPool.Folder): media pool folder object,
        name (str): name for compound clip

    Returns:
        resolve.MediaPoolItem: media pool item with compound clip timeline(cct)
    """
    # get basic objects form data
    resolve_project = clip_data["project"]
    timeline = clip_data["timeline"]
    clip = clip_data["clip"]

    # get details of objects
    clip_item = clip["item"]

    mp = resolve_project.GetMediaPool()

    # get clip attributes
    clip_attributes = get_clip_attributes(clip_item)

    mp_item = clip_item.GetMediaPoolItem()
    _mp_props = mp_item.GetClipProperty

    mp_first_frame = int(_mp_props("Start"))
    mp_last_frame = int(_mp_props("End"))

    # initialize basic source timing for otio
    ci_l_offset = clip_item.GetLeftOffset()
    ci_duration = clip_item.GetDuration()
    rate = float(_mp_props("FPS"))

    # source rational times
    mp_in_rc = otio.opentime.RationalTime((ci_l_offset), rate)
    mp_out_rc = otio.opentime.RationalTime((ci_l_offset + ci_duration - 1), rate)

    # get frame in and out for clip swapping
    in_frame = otio.opentime.to_frames(mp_in_rc)
    out_frame = otio.opentime.to_frames(mp_out_rc)

    # keep original sequence
    tl_origin = timeline

    # Set current folder to input media_pool_folder:
    mp.SetCurrentFolder(folder)

    # check if clip doesn't exist already:
    clips = folder.GetClipList()
    cct = next((c for c in clips
                if c.GetName() in name), None)

    if cct:
        print(f"Compound clip exists: {cct}")
    else:
        # Create empty timeline in current folder and give name:
        cct = mp.CreateEmptyTimeline(name)

        # check if clip doesn't exist already:
        clips = folder.GetClipList()
        cct = next((c for c in clips
                    if c.GetName() in name), None)
        print(f"Compound clip created: {cct}")

        with maintain_current_timeline(cct, tl_origin):
            # Add input clip to the current timeline:
            mp.AppendToTimeline([{
                "mediaPoolItem": mp_item,
                "startFrame": mp_first_frame,
                "endFrame": mp_last_frame
            }])

    # Add collected metadata and attributes to the compound clip:
    if mp_item.GetMetadata(constants.AYON_TAG_NAME):
        clip_attributes[constants.AYON_TAG_NAME] = mp_item.GetMetadata(
            constants.AYON_TAG_NAME)[constants.AYON_TAG_NAME]

    # stringify
    clip_attributes = json.dumps(clip_attributes)

    # add attributes to metadata
    for k, v in mp_item.GetMetadata().items():
        cct.SetMetadata(k, v)

    # add metadata to cct
    cct.SetMetadata(constants.AYON_TAG_NAME, clip_attributes)

    # reset start timecode of the compound clip
    cct.SetClipProperty("Start TC", _mp_props("Start TC"))

    # swap clips on timeline
    swap_clips(clip_item, cct, in_frame, out_frame)

    cct.SetClipColor("Pink")
    return cct


def swap_clips(from_clip, to_clip, to_in_frame, to_out_frame):
    """
    Swapping clips on timeline in timelineItem

    It will add take and activate it to the frame range which is inputted

    Args:
        from_clip (resolve.TimelineItem)
        to_clip (resolve.mediaPoolItem)
        to_clip_name (str): name of to_clip
        to_in_frame (float): cut in frame, usually `GetLeftOffset()`
        to_out_frame (float): cut out frame, usually left offset plus duration

    Returns:
        bool: True if successfully replaced

    """
    # copy ACES input transform from timeline clip to new media item
    mediapool_item_from_timeline = from_clip.GetMediaPoolItem()
    _idt = mediapool_item_from_timeline.GetClipProperty('IDT')
    to_clip.SetClipProperty('IDT', _idt)

    _clip_prop = to_clip.GetClipProperty
    to_clip_name = _clip_prop("File Name")
    # add clip item as take to timeline
    take = from_clip.AddTake(
        to_clip,
        float(to_in_frame),
        float(to_out_frame)
    )

    if not take:
        return False

    for take_index in range(1, (int(from_clip.GetTakesCount()) + 1)):
        take_item = from_clip.GetTakeByIndex(take_index)
        take_mp_item = take_item["mediaPoolItem"]
        if to_clip_name in take_mp_item.GetName():
            from_clip.SelectTakeByIndex(take_index)
            from_clip.FinalizeTake()
            return True
    return False


def _validate_tc(x):
    # Validate and reformat timecode string

    if len(x) != 11:
        print('Invalid timecode. Try again.')

    c = ':'
    colonized = x[:2] + c + x[3:5] + c + x[6:8] + c + x[9:]

    if colonized.replace(':', '').isdigit():
        print(f"_ colonized: {colonized}")
        return colonized
    else:
        print('Invalid timecode. Try again.')


def get_pype_clip_metadata(clip):
    """
    Get AYON metadata created by creator plugin

    Attributes:
        clip (resolve.TimelineItem): resolve's object

    Returns:
        dict: hierarchy, orig clip attributes
    """
    mp_item = clip.GetMediaPoolItem()
    metadata = mp_item.GetMetadata()

    return metadata.get(constants.AYON_TAG_NAME)


def get_clip_attributes(clip):
    """
    Collect basic attributes from resolve timeline item

    Args:
        clip (resolve.TimelineItem): timeline item object

    Returns:
        dict: all collected attributres as key: values
    """
    mp_item = clip.GetMediaPoolItem()

    return {
        "clipIn": clip.GetStart(),
        "clipOut": clip.GetEnd(),
        "clipLeftOffset": clip.GetLeftOffset(),
        "clipRightOffset": clip.GetRightOffset(),
        "clipMarkers": clip.GetMarkers(),
        "clipFlags": clip.GetFlagList(),
        "sourceId": mp_item.GetMediaId(),
        "sourceProperties": mp_item.GetClipProperty()
    }


def set_project_manager_to_folder_name(folder_name):
    """
    Sets context of Project manager to given folder by name.

    Searching for folder by given name from root folder to nested.
    If no existing folder by name it will create one in root folder.

    Args:
        folder_name (str): name of searched folder

    Returns:
        bool: True if success

    Raises:
        Exception: Cannot create folder in root

    """
    # initialize project manager
    project_manager = get_project_manager()

    set_folder = False

    # go back to root folder
    if project_manager.GotoRootFolder():
        log.info(f"Testing existing folder: {folder_name}")
        folders = _convert_resolve_list_type(
            project_manager.GetFoldersInCurrentFolder())
        log.info(f"Testing existing folders: {folders}")
        # get me first available folder object
        # with the same name as in `folder_name` else return False
        if next((f for f in folders if f in folder_name), False):
            log.info(f"Found existing folder: {folder_name}")
            set_folder = project_manager.OpenFolder(folder_name)

    if set_folder:
        return True

    # if folder by name is not existent then create one
    # go back to root folder
    log.info(f"Folder `{folder_name}` not found and will be created")
    if project_manager.GotoRootFolder():
        try:
            # create folder by given name
            project_manager.CreateFolder(folder_name)
            project_manager.OpenFolder(folder_name)
            return True
        except NameError as e:
            log.error((f"Folder with name `{folder_name}` cannot be created!"
                       f"Error: {e}"))
            return False


def _convert_resolve_list_type(resolve_list):
    """ Resolve is using indexed dictionary as list type.
    `{1.0: 'vaule'}`
    This will convert it to normal list class
    """
    assert isinstance(resolve_list, dict), (
        "Input argument should be dict() type")

    return [resolve_list[i] for i in sorted(resolve_list.keys())]


def get_clip_resolution_from_media_pool(timeline_item_data):
    """Return the clip resolution from media pool data.

    Args:
        timeline_item_data (dict): Timeline item to investigate.

    Returns:
        resolution_info (dict): The parsed resolution data.
    """
    clip_item = timeline_item_data["clip"]["item"]
    media_pool_item = clip_item.GetMediaPoolItem()
    clip_properties = media_pool_item.GetClipProperty()

    try:
        width, height = clip_properties["Resolution"].split("x")
    except (KeyError, ValueError):
        width = height = None

    try:
        clip_par = clip_properties["PAR"]  # Pixel Aspect Resolution
        pixel_aspect = constants.PAR_VALUES[clip_par]

    except (KeyError, ValueError):  # Unknown or undetected PAR
        pixel_aspect = 1.0

    return {"width": width, "height": height, "pixelAspect": pixel_aspect}


def create_otio_time_range_from_timeline_item_data(timeline_item_data):
    timeline_item = timeline_item_data["clip"]["item"]
    resolve_project = timeline_item_data["project"]
    timeline = timeline_item_data["timeline"]
    timeline_start = timeline.GetStartFrame()

    frame_start = int(timeline_item.GetStart() - timeline_start)
    frame_duration = int(timeline_item.GetDuration())
    fps = resolve_project.GetSetting("timelineFrameRate")

    return otio_export.create_otio_time_range(
        frame_start, frame_duration, fps)


def get_otio_clip_instance_data(otio_timeline, timeline_item_data):
    """
    Return otio objects for timeline, track and clip

    Args:
        timeline_item_data (dict): timeline_item_data from list returned by
                                resolve.get_current_timeline_items()
        otio_timeline (otio.schema.Timeline): otio object

    Returns:
        dict: otio clip object

    """

    timeline_item = timeline_item_data["clip"]["item"]
    track_name = timeline_item_data["track"]["name"]
    timeline_range = create_otio_time_range_from_timeline_item_data(
        timeline_item_data)

    try:  # opentimelineio >= 0.16.0
        all_clips = otio_timeline.find_clips()
    except AttributeError:  # legacy
        all_clips = otio_timeline.each_clip()

    for otio_clip in all_clips:
        track_name = otio_clip.parent().name
        parent_range = otio_clip.range_in_parent()
        if track_name not in track_name:
            continue
        if otio_clip.name not in timeline_item.GetName():
            continue
        if is_overlapping_otio_ranges(
                parent_range, timeline_range, strict=True):

            # add pypedata marker to otio_clip metadata
            for marker in otio_clip.markers:
                if constants.AYON_MARKER_NAME in marker.name:
                    otio_clip.metadata.update(marker.metadata)
            return {"otioClip": otio_clip}

    return None


def _get_otio_temp_file(timeline=None) -> str:
    """Get otio temporary export file.

    Args:
        timeline (resolve.Timeline)[optional]: resolve's object

    Returns:
        str: temporary otio filepath
    """
    project_name = get_current_project_name()

    if timeline is None:
        resolve_project = get_current_resolve_project()
        timeline = resolve_project.GetCurrentTimeline()
        if not timeline:
            raise RuntimeError("No current timeline")

    timeline_name = timeline.GetName()

    # get custom staging dir
    custom_temp_dir = create_custom_tempdir(project_name, None)
    staging_dir = os.path.normpath(
        tempfile.mkdtemp(prefix="resolve_otio_tmp_", dir=custom_temp_dir)
    )
    return os.path.join(
        staging_dir, f"{timeline_name}.otio"
    )


def export_timeline_otio_to_file(timeline, filepath):
    """Export timeline as otio filepath.

    Args:
        timeline (resolve.Timeline): resolve's timeline
        filepath (str): otio file path

    Returns:
        str: temporary otio filepath
    """
    try:
        from . import bmdvr

        if bmdvr.EXPORT_OTIO is None:
            raise AttributeError("Unsupported native Export OTIO")

        timeline.Export(filepath, bmdvr.EXPORT_OTIO)

    except Exception as error:
        log.debug(
            "Cannot use native OTIO export (%r)."
            "Default to AYON own implementation.",
            error
        )
        otio_timeline = otio_export.create_otio_timeline(
            get_current_resolve_project(),
            timeline=timeline
        )
        otio_export.write_to_file(otio_timeline, filepath)


def export_timeline_otio(timeline):
    """ Export timeline as otio.

    Args:
        timeline (resolve.Timeline): resolve's timeline

    Returns:
        otio_timeline (otio.Timeline): Otio timeline.
    """
    # DaVinci Resolve <= 18.5
    # Legacy export (slower) through AYON.
    if not hasattr(timeline, "Export"):
        return otio_export.create_otio_timeline(
            get_current_resolve_project(),
            timeline=timeline
        )

    # DaVinci Resolve >= 18.5
    # Force export through a temporary file (native)
    temp_otio_file = _get_otio_temp_file(timeline=timeline)
    export_timeline_otio_to_file(timeline, temp_otio_file)
    otio_timeline = otio.adapters.read_from_file(temp_otio_file)

    return otio_timeline


def get_reformated_path(path, padded=False, first=False):
    """
    Return fixed python expression path

    Args:
        path (str): path url or simple file name

    Returns:
        type: string with reformatted path

    Example:
        get_reformated_path("plate.[0001-1008].exr") > plate.%04d.exr

    """
    first_frame_pattern = re.compile(r"\[(\d+)\-\d+\]")

    if "[" in path:
        padding_pattern = r"(\d+)(?=-)"
        padding = len(re.findall(padding_pattern, path).pop())
        num_pattern = r"(\[\d+\-\d+\])"
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


def iter_all_media_pool_clips(root=None):
    """Recursively iterate all media pool clips in current project

    Args:
        root (Optional[resolve.Folder]): root folder / bin object.
            When None, defaults to media pool root folder.
    """
    root = root or get_current_project().GetMediaPool().GetRootFolder()
    queue = [root]
    for folder in queue:
        for clip in folder.GetClipList():
            yield clip
        queue.extend(folder.GetSubFolderList())


def export_timeline_otio_native(timeline, filepath):
    """Get timeline otio filepath.

    Only supported from Resolve 19.5

    Example:
        # Native otio export is available from Resolve 18.5
        # [major, minor, patch, build, suffix]
        resolve_version = bmdvr.GetVersion()
        if resolve_version[0] < 18 or resolve_version[1] < 5:
            # if it is lower then use ayon's otio exporter
            otio_timeline = davinci_export.create_otio_timeline(
                resolve_project, timeline=timeline)
            davinci_export.write_to_file(otio_timeline, filepath)
        else:
            # use native otio export
            export_timeline_otio_native(timeline, filepath)

    Args:
        timeline (resolve.Timeline): resolve's object
        filepath (str): otio file path

    Returns:
        bool: True if success
    """
    from . import bmdvr

    try:
        timeline.Export(filepath, bmdvr.EXPORT_OTIO)
    except Exception as e:
        log.error(f"Failed to export timeline otio: {e}")
        return False
    return True


def set_project_fps():
    """ Attempt to set project frame rate from AYON current task.
    This might not be possible if a timeline already exists within the project.
    """
    task_entity = get_current_task_entity()
    attributes = task_entity["attrib"]

    # Set project frame rate and resolution
    resolve_project = get_current_resolve_project()
    project_fps = attributes["fps"]

    SUPPORTED_FPS = {
        16.0: "16",
        18.0: "18",
        23.976: "23.976",
        24.0: "24",
        25.0: "25",
        29.97: "29.97",
        30.0: "30",
        47.952: "47.952",
        48.0: "48",
        50.0: "50"
    }

    if float(project_fps) in SUPPORTED_FPS:
        if not resolve_project.SetSetting(
            "timelineFrameRate",
            SUPPORTED_FPS[float(project_fps)]
        ):
            # Resolve does not allow to edit timeline fps
            # project settings once a timeline has been created.
            log.warning(
                "Cannot override Project fps from AYON."
                " This could be because a timeline already exists."
            )
    else:
        log.warning(
            "Fps set in AYON project is not supported by Resolve"
            f" attempt to set {project_fps},"
            f" supported are {tuple(SUPPORTED_FPS.keys())}."
        )


def set_project_resolution():
    """ Attempt to set project resolution from AYON current task.
    """
    task_entity = get_current_task_entity()
    attributes = task_entity["attrib"]

    resolve_project = get_current_resolve_project()
    width = attributes["resolutionWidth"]
    height = attributes["resolutionHeight"]

    resolution_params = {
        "timelineResolutionHeight": height,
        "timelineResolutionWidth": width,
    }

    # In order to set vertical resolution in resolve,
    # the "Use vertical resolution" option need to be enabled.
    # This is not exposed from the Python API.
    if height > width:
            log.warning(
                "Cannot override Project resolution from AYON."
                f" Vertical resolution {width}x{height}"
                " is unsupported from the API."
            )
            return

    for resolve_param, value in resolution_params.items():
        if not resolve_project.SetSetting(
            resolve_param,
            str(int(value))
        ):
            log.warning(
                "Cannot override Project resolution from AYON."
                f" trying to set {resolve_param} = {value}"
            )
            return

    SUPPORTED_PIXEL_ASPECTS = {
        1.0: "Square",
        16/9: "16:9 anamorphic",
        4/3: "4:3 standard definition",
        2.0: "Cinemascope",
    }
    pixel_aspect_ratio = round(attributes["pixelAspect"], 2)

    for supported_pa in SUPPORTED_PIXEL_ASPECTS:
        if round(supported_pa, 2) != pixel_aspect_ratio:
            continue

        if not resolve_project.SetSetting(
            "timelinePixelAspectRatio",
            SUPPORTED_PIXEL_ASPECTS[supported_pa]
        ):
            log.warning(
                "Cannot override Project pixel aspect ratio from AYON."
                " trying to set timelinePixelAspectRatio = "
                f"{SUPPORTED_PIXEL_ASPECTS[supported_pa]}"
            )

        break

    else:
        log.warning(
            "Pixel Aspect Ratio set in AYON project is not supported"
            f" by Resolve, attempt to set {pixel_aspect_ratio},"
            f" supported are {tuple(SUPPORTED_PIXEL_ASPECTS.keys())}."
        )
