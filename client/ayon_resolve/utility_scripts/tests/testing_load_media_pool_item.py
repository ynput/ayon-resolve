#! python3
from openpype.pipeline import install_host
from openpype.hosts.resolve import api as bmdvr
from openpype.hosts.resolve.api.lib import (
    create_media_pool_item,
    create_timeline_item,
)


def file_processing(fpath):
    media_pool_item = create_media_pool_item(fpath)
    print(media_pool_item)

    track_item = create_timeline_item(media_pool_item)
    print(track_item)


if __name__ == "__main__":
    path = "C:/CODE/__openpype_projects/jtest03dev/shots/sq01/mainsq01sh030/publish/plate/plateMain/v006/jt3d_mainsq01sh030_plateMain_v006.0996.exr"

    # activate resolve from openpype
    install_host(bmdvr)

    file_processing(path)
