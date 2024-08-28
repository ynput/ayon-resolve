# -*- coding: utf-8 -*-
"""Creator plugin for creating workfiles."""
import json

import ayon_api
from ayon_core.pipeline import (
    AutoCreator,
    CreatedInstance,
)

from ayon_resolve.api import lib
from ayon_resolve.api import constants


class CreateWorkfile(AutoCreator):
    """Workfile auto-creator."""
    settings_category = "resolve"

    identifier = "io.ayon.creators.resolve.workfile"
    label = "Workfile"
    product_type = "workfile"

    default_variant = "Main"

    def _dumps_data_as_marker(self, data):
        """Store workfile as timeline marker.

        Args:
            data (dict): The data to store on the timeline.
        """
        # Append global project 
        # (timeline metadata is not maintained by Resolve native OTIO)
        timeline = lib.get_current_timeline()
        timeline_settings = timeline.GetSetting()

        try:
            pixel_aspect = int(timeline_settings["timelinePixelAspectRatio"])
        except ValueError:
            pixel_aspect = 1.0

        data.update({
            "width": timeline_settings["timelineResolutionWidth"],
            "height": timeline_settings["timelineResolutionHeight"],
            "pixelAspect": pixel_aspect
        })

        # Store as marker note data
        note = json.dumps(data)

        timeline.AddMarker(
            timeline.GetStartFrame(),
            constants.ayon_marker_color,
            constants.ayon_marker_name,
            note,
            constants.ayon_marker_duration
        )

    def _get_timeline_marker(self):
        """Retrieve workfile marker from timeline."""
        timeline = lib.get_current_timeline()
        for idx, marker_info in timeline.GetMarkers().items():
            if (
                marker_info["name"] == constants.ayon_marker_name
                and marker_info["color"] == constants.ayon_marker_color
            ):
                return idx, marker_info

        return None, None

    def _loads_data_from_marker(self):
        """Retrieve workfile from timeline marker."""
        _, marker_info = self._get_timeline_marker()
        if not marker_info:
            return {}

        return json.loads(marker_info["note"])

    def _create_new_instance(self):
        """Create new instance."""
        variant = self.default_variant
        project_name = self.create_context.get_current_project_name()
        folder_path = self.create_context.get_current_folder_path()
        task_name = self.create_context.get_current_task_name()
        host_name = self.create_context.host_name

        folder_entity = ayon_api.get_folder_by_path(
            project_name, folder_path)
        task_entity = ayon_api.get_task_by_name(
            project_name, folder_entity["id"], task_name
        )
        product_name = self.get_product_name(
            project_name,
            folder_entity,
            task_entity,
            self.default_variant,
            host_name,
        )
        data = {
            "folderPath": folder_path,
            "task": task_name,
            "variant": variant,
            "productName": product_name,
        }
        data.update(
            self.get_dynamic_data(
                variant,
                task_name,
                folder_entity,
                project_name,
                host_name,
                False,
            )
        )

        self._dumps_data_as_marker(data)
        return data

    def collect_instances(self):
        """Collect from timeline marker or create a new one."""
        data = self._loads_data_from_marker()
        if not data:
            self.log.info("Auto-creating workfile instance...")
            data = self._create_new_instance()
            self._dumps_data_as_marker(data)

        current_instance = CreatedInstance(
            self.product_type, data["productName"], data, self)
        self._add_instance_to_context(current_instance)

    def create(self, options=None):
        # no need to create if it is created
        # in `collect_instances`
        pass

    def update_instances(self, update_list):
        """Store changes in project metadata so they can be recollected.

        Args:
            update_list(List[UpdateData]): Gets list of tuples. Each item
                contain changed instance and it's changes.
        """
        timeline = lib.get_current_timeline()
        frame_id, _ = self._get_timeline_marker()

        if frame_id is not None:
            timeline.DeleteMarkerAtFrame(frame_id)

        for created_inst, _changes in update_list:
            data = created_inst.data_to_store()
            self._dumps_data_as_marker(data)
