#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

from ayon_core.lib import Logger

from ayon_resolve.api.lib import (
    get_current_project,
    maintain_page_by_name,
)
from ayon_resolve.api.rendering import (
    set_render_preset_from_file,
    render_single_timeline,
    set_format_and_codec,
)

from ayon_resolve.utils import RESOLVE_ADDON_ROOT
from ayon_resolve.api.utils import get_resolve_module

log = Logger.get_logger(__name__)


def main(
    target_render_directory,
    render_format,
    render_codec,
):
    get_resolve_module()

    render_preset_name = "AYON_intermediates"
    # get path to ayon_resolve module and get path to render presets
    render_preset_path = Path(
        RESOLVE_ADDON_ROOT, "presets", "render", f"{render_preset_name}.xml"
    )

    log.info(f"Rendering timeline to '{target_render_directory}'")

    with maintain_page_by_name("Deliver"):
        # first we need to maintain rendering preset
        if not set_render_preset_from_file(render_preset_path.as_posix()):
            log.error("Unable to add render preset.")

        # set render format and codec
        if not set_format_and_codec(render_format, render_codec):
            log.error("Unable to set render format and codec.")
            sys.exit()

        timeline = get_current_project().GetCurrentTimeline()

        if not render_single_timeline(
            timeline,
            target_render_directory,
        ):
            log.error("Unable to render timeline.")
            sys.exit()


if __name__ == "__main__":
    target_render_directory = Path(
        "~/Videos/test_resolve_automatic_001").expanduser()
    # ensure target directory exists
    target_render_directory.mkdir(parents=True, exist_ok=True)

    main(
        target_render_directory=target_render_directory,
        render_format="QuickTime",
        render_codec="H.265",
    )
