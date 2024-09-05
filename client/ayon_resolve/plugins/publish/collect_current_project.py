import pyblish.api

from ayon_core.pipeline import registered_host

from ayon_resolve import api


class CollectResolveProject(pyblish.api.ContextPlugin):
    """Collect the current Resolve project and current timeline data"""

    label = "Collect Project and Current Timeline"
    order = pyblish.api.CollectorOrder - 0.499
    hosts = ["resolve"]

    def process(self, context):
        resolve_project = api.get_current_resolve_project()
        timeline = resolve_project.GetCurrentTimeline()

        video_tracks = api.get_video_track_names()
        otio_timeline = api.export_timeline_otio(timeline)

        host = registered_host()        
        current_file = host.get_current_workfile()
        fps = timeline.GetSetting("timelineFrameRate")

        # update context with main project attributes
        context.data.update({
            # project
            "activeProject": resolve_project,
            "currentFile": current_file,
            # timeline
            "otioTimeline": otio_timeline,
            "videoTracks": video_tracks,
            "fps": fps,
        })
