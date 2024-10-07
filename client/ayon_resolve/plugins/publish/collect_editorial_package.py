import pyblish.api

import ayon_api

from ayon_resolve.api import lib, constants


class EditorialPackageInstances(pyblish.api.InstancePlugin):
    """Collect all Track items selection."""

    order = pyblish.api.CollectorOrder - 0.49
    label = "Collect Editorial Package Instances"
    families = ["editorial_pkg"]

    def process(self, instance):
        project_name = instance.context.data["projectName"]
        self.log.info(f"project: {project_name}")

        media_pool_item_id = instance.data["media_pool_item_id"]
        for media_pool_item in lib.iter_all_media_pool_clips():
            if media_pool_item.GetUniqueId() == media_pool_item_id:
                break
        else:
            raise RuntimeError("Could not identify media pool item from instance.")

        # get version from publish data and rise it one up
        version = instance.data.get("version")
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

            instance.data["version"] = version

        instance.data.update(
            {
                "mediaPoolItem": media_pool_item,
                "item": media_pool_item,
            }
        )

        self.log.info(f"Editorial Package: {instance.data}")
