import json

import pyblish.api

import ayon_api
from ayon_api import get_task_by_id

from ayon_resolve.api import lib, constants


class EditorialPackageInstances(pyblish.api.ContextPlugin):
    """Collect all Track items selection."""

    order = pyblish.api.CollectorOrder - 0.49
    label = "Collect Editorial Package Instances"
    families = ["editorial_pkg"]

    def process(self, context):
        project_name = context.data["projectName"]
        self.log.info(f"project: {project_name}")

        for media_pool_item in lib.iter_all_media_pool_clips():

            data = media_pool_item.GetMetadata(constants.AYON_TAG_NAME)
            if not data:
                continue

            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                self.log.warning(
                    f"Failed to parse json data from media pool item: "
                    f"{media_pool_item.GetName()}"
                )
                continue

            # exclude all which are not productType editorial_pkg
            if (
                data.get("publish")
                and data["publish"].get("productType") != "editorial_pkg"
            ):
                continue

            instance = context.create_instance(name=media_pool_item.GetName())

            publish_data = data["publish"]

            # get version from publish data and rise it one up
            version = publish_data.get("version")
            if version is not None:
                version += 1

                # make sure last version of product is higher than current
                # expected current version from publish data
                folder_entity = ayon_api.get_folder_by_path(
                    project_name=project_name,
                    folder_path=publish_data["folderPath"],
                )
                last_version = ayon_api.get_last_version_by_product_name(
                    project_name=project_name,
                    product_name=publish_data["productName"],
                    folder_id=folder_entity["id"],
                )
                if last_version is not None:
                    last_version = int(last_version["version"])
                    if version <= last_version:
                        version = last_version + 1

                publish_data["version"] = version

            publish_data.update(
                {
                    "mediaPoolItem": media_pool_item,
                    "item": media_pool_item,
                }
            )

            if publish_data.get("taskId"):
                task_entity = get_task_by_id(
                    project_name=project_name,
                    task_id=publish_data["taskId"],
                )
                publish_data["taskEntity"] = task_entity
                publish_data["task"] = task_entity["name"]

            instance.data.update(publish_data)

            self.log.info(f"Editorial Package: {instance.data}")
