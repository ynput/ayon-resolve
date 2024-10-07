import json
from copy import deepcopy
from ayon_core.tools.context_dialog.window import (
    ContextDialog,
    ContextDialogController
)
from ayon_core.pipeline import get_current_project_name
from ayon_api import get_folder_by_id, get_task_by_id, get_folder_by_path
from ayon_core.pipeline.create.legacy_create import LegacyCreator

from ayon_resolve.api import lib, constants
from ayon_resolve.api.plugin import get_editorial_publish_data


class CreateEditorialPackage(LegacyCreator):
    """Create Editorial Package."""

    name = "editorial_pkg"
    label = "Editorial Package"
    product_type = "editorial_pkg"
    icon = "camera"
    defaults = ["Main"]

    def process(self):
        """Process the creation of the editorial package."""
        project_name = get_current_project_name()
        folder_path = self.data["folderPath"]

        current_folder = get_folder_by_path(project_name, folder_path)
        print(current_folder)

        current_timeline = lib.get_current_timeline()

        context = ask_for_context(
            project_name, current_folder["id"]
        )

        if context is None:
            return

        # Get workfile path to save to.
        project_name = context["project_name"]
        folder = get_folder_by_id(project_name, context["folder_id"])

        # task is optional so we need to check if it is set
        task = None
        if "task_id" in context:
            task = get_task_by_id(project_name, context["task_id"])

        # reset self.data to be pointing in the set context data
        self.data["folderPath"] = folder["path"]

        if task:
            self.data.update({
                "taskId": task["id"],
                "taskName": task["name"],
            })

        if not current_timeline:
            raise RuntimeError("Make sure to have an active current timeline.")

        timeline_media_pool_item = lib.get_timeline_media_pool_item(
            current_timeline
        )

        publish_data = deepcopy(self.data)
        # add publish data for streamline publishing
        publish_data["publish"] = get_editorial_publish_data(
            folder_path=folder["path"],
            product_name=self.data["productName"],
        )

        timeline_media_pool_item.SetMetadata(
            constants.AYON_TAG_NAME, json.dumps(publish_data)
        )


def ask_for_context(
    project_name, folder_id
):
    """Ask for context to create Editorial Package."""
    controller = ContextDialogController()
    window = ContextDialog(controller=controller)
    controller.set_expected_selection(
        project_name, folder_id)
    window.exec_()

    return controller.get_selected_context()
