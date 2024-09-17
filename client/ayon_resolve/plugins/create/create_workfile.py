# -*- coding: utf-8 -*-
"""Creator plugin for creating workfiles."""
import json

import ayon_api
from ayon_core.pipeline import (
    AutoCreator,
    CreatedInstance,
)

from ayon_resolve.api import lib


class CreateWorkfile(AutoCreator):
    """Workfile auto-creator."""
    settings_category = "resolve"

    identifier = "io.ayon.creators.resolve.workfile"
    label = "Workfile"
    product_type = "workfile"

    default_variant = "Main"

    def _dumps_data_as_project_setting(self, data):
        """Store workfile as project setting.

        Args:
            data (dict): The data to store on the timeline.
        """
        # Store info as project setting data.
        # Use this hack instead: 
        # https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=
        # 189685&hilit=python+database#p991541
        note = json.dumps(data)
        proj = lib.get_current_project()
        proj.SetSetting("colorVersion10Name", note)

    def _loads_data_from_project_setting(self):
        """Retrieve workfile data from project setting."""
        proj = lib.get_current_project()
        setting_content = proj.GetSetting("colorVersion10Name")

        if setting_content:
            return json.loads(setting_content)

        return None

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

        return data

    def collect_instances(self):
        """Collect from timeline marker or create a new one."""
        data = self._loads_data_from_project_setting()
        if not data:
            return

        current_instance = CreatedInstance(
            self.product_type, data["productName"], data, self)
        self._add_instance_to_context(current_instance)

    def create(self, options=None):
        """Auto-create an instance by default."""
        data = self._loads_data_from_project_setting()
        if data:
            return

        self.log.info("Auto-creating workfile instance...")
        data = self._create_new_instance()
        current_instance = CreatedInstance(
            self.product_type, data["productName"], data, self)
        self._add_instance_to_context(current_instance)

    def update_instances(self, update_list):
        """Store changes in project metadata so they can be recollected.

        Args:
            update_list(List[UpdateData]): Gets list of tuples. Each item
                contain changed instance and its changes.
        """
        for created_inst, _ in update_list:
            data = created_inst.data_to_store()
            self._dumps_data_as_project_setting(data)
